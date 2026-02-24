from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .storage import AppStorage, auth_seconds_remaining, parse_iso

LOGGER = logging.getLogger("tiktok_manager.tiktok_api")

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
DIRECT_POST_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
PUBLISH_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

DEFAULT_SCOPES = ["user.info.basic", "video.publish"]


class TikTokAPIError(RuntimeError):
    def __init__(self, message: str, *, code: Optional[str] = None, log_id: Optional[str] = None, http_status: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.log_id = log_id
        self.http_status = http_status


@dataclass
class UploadResult:
    publish_id: str
    status: str
    raw_status: Dict[str, Any]


class TikTokAPI:
    def __init__(
        self,
        storage: AppStorage,
        *,
        client_key: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        timeout_seconds: int = 45,
    ):
        self.storage = storage
        self.client_key = (client_key or os.getenv("TIKTOK_CLIENT_KEY") or "").strip()
        self.client_secret = (client_secret or os.getenv("TIKTOK_CLIENT_SECRET") or "").strip()
        self.redirect_uri = (redirect_uri or os.getenv("TIKTOK_REDIRECT_URI") or "http://localhost:8000/callback").strip()
        self.timeout_seconds = timeout_seconds

    def _require_client_credentials(self) -> None:
        if not self.client_key or not self.client_secret:
            raise TikTokAPIError(
                "TikTok client credentials are missing. Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET."
            )

    def build_authorize_url(self, state: str, scopes: Optional[list[str]] = None) -> str:
        self._require_client_credentials()
        scope_value = ",".join(scopes or DEFAULT_SCOPES)
        query = urllib.parse.urlencode(
            {
                "client_key": self.client_key,
                "scope": scope_value,
                "response_type": "code",
                "redirect_uri": self.redirect_uri,
                "state": state,
            }
        )
        return f"{AUTH_URL}?{query}"

    def _request_json(
        self,
        *,
        url: str,
        method: str,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        payload = None
        merged_headers = {"Accept": "application/json"}
        if headers:
            merged_headers.update(headers)

        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            merged_headers.setdefault("Content-Type", "application/json")

        request = urllib.request.Request(url=url, data=payload, headers=merged_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw or "{}")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            details = self._parse_error_payload(raw)
            raise TikTokAPIError(
                f"TikTok API request failed ({exc.code}): {details['message']}",
                code=details.get("code"),
                log_id=details.get("log_id"),
                http_status=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise TikTokAPIError(f"TikTok API network error: {exc.reason}") from exc

    def _request_form(self, *, url: str, body: Dict[str, str]) -> Dict[str, Any]:
        payload = urllib.parse.urlencode(body).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw or "{}")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            details = self._parse_error_payload(raw)
            raise TikTokAPIError(
                f"TikTok OAuth request failed ({exc.code}): {details['message']}",
                code=details.get("code"),
                log_id=details.get("log_id"),
                http_status=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise TikTokAPIError(f"TikTok OAuth network error: {exc.reason}") from exc

    def _parse_error_payload(self, raw: str) -> Dict[str, str]:
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return {"message": raw.strip() or "Unknown API error", "code": "unknown", "log_id": ""}

        if "error" in payload and isinstance(payload["error"], dict):
            err = payload["error"]
            return {
                "message": str(err.get("message") or payload.get("message") or "Unknown API error"),
                "code": str(err.get("code") or payload.get("code") or "unknown"),
                "log_id": str(err.get("log_id") or payload.get("log_id") or ""),
            }

        return {
            "message": str(payload.get("message") or "Unknown API error"),
            "code": str(payload.get("code") or "unknown"),
            "log_id": str(payload.get("log_id") or ""),
        }

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        self._require_client_credentials()
        payload = self._request_form(
            url=TOKEN_URL,
            body={
                "client_key": self.client_key,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
            },
        )
        return self._persist_auth_response(payload)

    def refresh_access_token(self, refresh_token: Optional[str] = None) -> Dict[str, Any]:
        self._require_client_credentials()
        auth = self.storage.get_auth()
        current_refresh_token = refresh_token or (auth or {}).get("refresh_token")
        if not current_refresh_token:
            raise TikTokAPIError("No refresh token is available. Reconnect TikTok OAuth.")

        payload = self._request_form(
            url=TOKEN_URL,
            body={
                "client_key": self.client_key,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": str(current_refresh_token),
            },
        )
        return self._persist_auth_response(payload)

    def _persist_auth_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        error_info = payload.get("error")
        if error_info:
            message = str(error_info.get("message") or "OAuth request failed")
            raise TikTokAPIError(
                message,
                code=str(error_info.get("code") or "oauth_error"),
                log_id=str(error_info.get("log_id") or ""),
            )

        access_token = str(payload.get("access_token") or "")
        refresh_token = str(payload.get("refresh_token") or "")
        expires_in_seconds = int(payload.get("expires_in") or 0)

        if not access_token or not refresh_token or expires_in_seconds <= 0:
            raise TikTokAPIError("OAuth response is missing required token fields.")

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
        auth_row = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at.isoformat(),
            "open_id": str(payload.get("open_id") or ""),
            "scope": str(payload.get("scope") or ""),
        }
        self.storage.save_auth(**auth_row)
        LOGGER.info("Stored TikTok OAuth tokens (expires in %s seconds)", expires_in_seconds)
        return auth_row

    def ensure_valid_access_token(self) -> str:
        auth = self.storage.get_auth()
        if not auth:
            raise TikTokAPIError("TikTok account is not connected. Complete OAuth first.")

        if auth_seconds_remaining(auth) <= 300:
            LOGGER.info("Access token expiring soon, refreshing")
            auth = self.refresh_access_token(auth.get("refresh_token"))
            persisted_auth = self.storage.get_auth()
            if persisted_auth:
                auth = persisted_auth

        token = str((auth or {}).get("access_token") or "")
        if not token:
            raise TikTokAPIError("TikTok access token missing after refresh")
        return token

    def get_auth_status(self) -> Dict[str, Any]:
        auth = self.storage.get_auth()
        if not auth:
            return {
                "connected": False,
                "expires_at": None,
                "seconds_remaining": 0,
            }

        seconds_remaining = auth_seconds_remaining(auth)
        return {
            "connected": seconds_remaining > 0,
            "expires_at": auth.get("expires_at"),
            "seconds_remaining": seconds_remaining,
            "scope": auth.get("scope"),
        }

    def query_creator_info(self, access_token: Optional[str] = None) -> Dict[str, Any]:
        token = access_token or self.ensure_valid_access_token()
        response = self._request_json(
            url=CREATOR_INFO_URL,
            method="POST",
            body={},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
        )

        if response.get("error"):
            err = response["error"]
            raise TikTokAPIError(
                str(err.get("message") or "Creator info query failed"),
                code=str(err.get("code") or "creator_info_error"),
                log_id=str(err.get("log_id") or ""),
            )

        return response.get("data") or {}

    def _select_privacy_level(self, creator_info: Dict[str, Any]) -> str:
        options = creator_info.get("privacy_level_options") or []
        option_set = {str(value) for value in options}
        for candidate in ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"):
            if candidate in option_set:
                return candidate
        if options:
            return str(options[0])
        return "SELF_ONLY"

    def initialize_file_upload(self, *, access_token: str, video_path: Path, caption: str) -> Tuple[str, str]:
        creator_info = self.query_creator_info(access_token)
        privacy_level = self._select_privacy_level(creator_info)

        video_size = int(video_path.stat().st_size)
        payload = {
            "post_info": {
                "title": caption,
                "privacy_level": privacy_level,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000,
                "brand_content_toggle": False,
                "brand_organic_toggle": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,
                "total_chunk_count": 1,
            },
        }

        response = self._request_json(
            url=DIRECT_POST_INIT_URL,
            method="POST",
            body=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
        )

        if response.get("error"):
            err = response["error"]
            raise TikTokAPIError(
                str(err.get("message") or "Upload init failed"),
                code=str(err.get("code") or "upload_init_error"),
                log_id=str(err.get("log_id") or ""),
            )

        data = response.get("data") or {}
        publish_id = str(data.get("publish_id") or "")
        upload_url = str(data.get("upload_url") or "")

        if not publish_id or not upload_url:
            raise TikTokAPIError("Upload init response missing publish_id or upload_url")

        return publish_id, upload_url

    def upload_binary(self, *, upload_url: str, video_path: Path) -> None:
        video_size = int(video_path.stat().st_size)
        with video_path.open("rb") as handle:
            payload = handle.read()

        request = urllib.request.Request(
            url=upload_url,
            data=payload,
            method="PUT",
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(video_size),
                "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds):
                return
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise TikTokAPIError(
                f"Video binary upload failed ({exc.code}): {raw[:400]}",
                http_status=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise TikTokAPIError(f"Video binary upload network error: {exc.reason}") from exc

    def fetch_publish_status(self, *, access_token: str, publish_id: str) -> Dict[str, Any]:
        response = self._request_json(
            url=PUBLISH_STATUS_URL,
            method="POST",
            body={"publish_id": publish_id},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
        )

        if response.get("error"):
            err = response["error"]
            raise TikTokAPIError(
                str(err.get("message") or "Publish status fetch failed"),
                code=str(err.get("code") or "publish_status_error"),
                log_id=str(err.get("log_id") or ""),
            )

        return response.get("data") or {}

    def upload_video(self, *, video_path: Path, caption: str, poll_attempts: int = 24, poll_delay_seconds: int = 5) -> UploadResult:
        for auth_attempt in range(2):
            token = self.ensure_valid_access_token()
            try:
                publish_id, upload_url = self.initialize_file_upload(
                    access_token=token,
                    video_path=video_path,
                    caption=caption,
                )
                self.upload_binary(upload_url=upload_url, video_path=video_path)

                last_status: Dict[str, Any] = {}
                status_value = "UNKNOWN"
                for _ in range(max(1, poll_attempts)):
                    last_status = self.fetch_publish_status(access_token=token, publish_id=publish_id)
                    status_value = str(last_status.get("status") or "").upper()

                    if status_value in {"PUBLISH_COMPLETE", "SUCCESS", "POSTED"}:
                        return UploadResult(publish_id=publish_id, status=status_value, raw_status=last_status)

                    if status_value in {"FAILED", "PUBLISH_FAILED", "REJECTED"}:
                        fail_reason = last_status.get("fail_reason") or "TikTok reported publish failure"
                        raise TikTokAPIError(str(fail_reason))

                    time.sleep(max(1, poll_delay_seconds))

                raise TikTokAPIError(
                    f"Timed out waiting for TikTok publish completion (last status: {status_value})"
                )
            except TikTokAPIError as exc:
                if exc.http_status == 401 and auth_attempt == 0:
                    LOGGER.warning("Access token expired during upload, refreshing")
                    self.refresh_access_token()
                    continue
                raise

        raise TikTokAPIError("Upload failed after token refresh attempts")
