from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .caption_engine import CaptionContext, CaptionEngine
from .storage import AppStorage, utc_now_iso
from .tiktok_api import TikTokAPI
from .video_engine import VideoEngine

LOGGER = logging.getLogger("tiktok_manager.upload_queue")


class UploadQueueWorker:
    """Retry-safe upload worker that survives restarts via SQLite state."""

    def __init__(
        self,
        *,
        storage: AppStorage,
        video_engine: VideoEngine,
        caption_engine: CaptionEngine,
        tiktok_api: TikTokAPI,
        max_retries: int = 3,
        poll_interval_seconds: int = 8,
    ):
        self.storage = storage
        self.video_engine = video_engine
        self.caption_engine = caption_engine
        self.tiktok_api = tiktok_api
        self.max_retries = max(1, int(max_retries))
        self.poll_interval_seconds = max(1, int(poll_interval_seconds))

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        reset_count = self.storage.reset_inflight_uploads()
        if reset_count:
            LOGGER.info("Recovered %s uploads that were left in uploading state", reset_count)

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="upload-queue-worker", daemon=True)
        self._thread.start()
        LOGGER.info("Upload queue worker started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        LOGGER.info("Upload queue worker stopped")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            processed = self.run_once(process_all=True)
            if processed == 0:
                self._stop_event.wait(self.poll_interval_seconds)

    def run_once(self, *, process_all: bool = True) -> int:
        candidates = self.storage.fetch_upload_candidates(max_retries=self.max_retries, limit=10)
        if not candidates:
            return 0

        if not process_all:
            candidates = candidates[:1]

        for upload in candidates:
            self._process_upload(upload)

        return len(candidates)

    def _resolve_video_source(self, video_row: dict) -> Path:
        # Prefer source file for clean re-render, fallback to current export.
        source_path = str(video_row.get("source_path") or "").strip()
        export_path = str(video_row.get("export_path") or "").strip()

        if source_path and Path(source_path).exists():
            return Path(source_path)
        if export_path and Path(export_path).exists():
            return Path(export_path)

        raise RuntimeError("Video source file is missing for queued upload")

    def _process_upload(self, upload_row: dict) -> None:
        upload_id = int(upload_row["id"])
        video_id = int(upload_row["video_id"])
        retry_count = int(upload_row.get("retry_count") or 0)

        self.storage.update_upload(
            upload_id,
            status="uploading",
            last_attempt=utc_now_iso(),
            error_message="",
        )
        self.storage.update_video(video_id, status="uploading")

        try:
            video_row = self.storage.get_video_by_id(video_id)
            if not video_row:
                raise RuntimeError(f"Video {video_id} does not exist")

            source_path = self._resolve_video_source(video_row)

            caption = str(video_row.get("caption") or "").strip()
            if not caption:
                context = CaptionContext(
                    filename=str(video_row.get("filename") or source_path.name),
                    content_theme=self._infer_theme(str(video_row.get("filename") or source_path.name)),
                    clip_format="background_layer",
                    source_hint=source_path.stem,
                )
                caption = self.caption_engine.generate_caption(context)
                self.storage.update_video(video_id, caption=caption)

            output_name = f"video_{video_id}_final.mp4"
            rendered_path = self.video_engine.render_for_posting(
                source_path=source_path,
                caption=caption,
                output_filename=output_name,
            )

            self.storage.update_video(video_id, export_path=str(rendered_path), status="uploading")

            result = self.tiktok_api.upload_video(video_path=rendered_path, caption=caption)

            self.storage.update_upload(
                upload_id,
                status="posted",
                retry_count=retry_count,
                last_attempt=utc_now_iso(),
                publish_id=result.publish_id,
                error_message="",
            )
            self.storage.update_video(video_id, status="posted")
            LOGGER.info("Upload %s posted successfully (publish_id=%s)", upload_id, result.publish_id)
        except Exception as exc:
            next_retry_count = retry_count + 1
            self.storage.update_upload(
                upload_id,
                status="failed",
                retry_count=next_retry_count,
                last_attempt=utc_now_iso(),
                error_message=str(exc)[:1500],
            )
            self.storage.update_video(video_id, status="failed")
            LOGGER.exception("Upload %s failed (retry %s/%s)", upload_id, next_retry_count, self.max_retries)

    def _infer_theme(self, filename: str) -> str:
        lower = filename.lower()
        if "game" in lower or "gta" in lower or "subway" in lower:
            return "gaming"
        if "story" in lower:
            return "story"
        if "drama" in lower:
            return "drama"
        if "motivation" in lower:
            return "motivation"
        if "podcast" in lower:
            return "podcast"
        return "story"
