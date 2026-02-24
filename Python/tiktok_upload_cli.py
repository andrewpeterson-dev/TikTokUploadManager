#!/usr/bin/env python3
"""Production TikTok upload CLI using official OAuth and Content Posting API."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import configure_logging
from app.services.caption_engine import CaptionContext, CaptionEngine
from app.services.storage import AppStorage
from app.services.tiktok_api import TikTokAPI
from app.services.upload_queue import UploadQueueWorker
from app.services.video_engine import VideoEngine

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")


def log(message: str) -> None:
    print(message, flush=True)


def build_services() -> tuple[AppStorage, VideoEngine, CaptionEngine, TikTokAPI, UploadQueueWorker]:
    storage = AppStorage(PROJECT_ROOT / "app")
    video_engine = VideoEngine(storage)
    caption_engine = CaptionEngine()
    tiktok_api = TikTokAPI(storage)
    worker = UploadQueueWorker(
        storage=storage,
        video_engine=video_engine,
        caption_engine=caption_engine,
        tiktok_api=tiktok_api,
        max_retries=3,
        poll_interval_seconds=8,
    )
    return storage, video_engine, caption_engine, tiktok_api, worker


def ensure_video_record(storage: AppStorage, source_path: Path) -> int:
    row = storage.get_video_by_path(str(source_path))
    if row:
        return int(row["id"])
    return storage.create_or_update_video(
        filename=source_path.name,
        source_path=str(source_path),
        export_path=str(source_path),
        status="ready",
    )


def queue_and_upload(
    *,
    video: str,
    caption: str,
    content_theme: str,
    clip_format: str,
    process_now: bool,
) -> int:
    storage, _, caption_engine, _, worker = build_services()

    source_path = Path(video).expanduser().resolve()
    if not source_path.exists():
        log(f"ERROR: Video file not found: {source_path}")
        return 1

    video_id = ensure_video_record(storage, source_path)

    final_caption = caption.strip()
    if not final_caption:
        final_caption = caption_engine.generate_caption(
            CaptionContext(
                filename=source_path.name,
                content_theme=content_theme,
                clip_format=clip_format,
                source_hint=source_path.stem,
            )
        )

    storage.update_video(video_id, caption=final_caption, status="ready")
    upload_id = storage.enqueue_upload(video_id)

    log(f"QUEUE: video_id={video_id} upload_id={upload_id}")

    if process_now:
        processed = worker.run_once(process_all=True)
        log(f"QUEUE_PROCESSED: {processed}")

    video_row = storage.get_video_by_id(video_id) or {}
    upload_row = storage.get_upload_by_video_id(video_id) or {}

    payload = {
        "video_id": video_id,
        "upload_id": upload_id,
        "video_status": video_row.get("status"),
        "upload_status": upload_row.get("status"),
        "retry_count": upload_row.get("retry_count"),
        "caption": final_caption,
    }
    log("UPLOAD_JSON: " + json.dumps(payload))

    return 0 if upload_row.get("status") == "posted" or not process_now else 1


def oauth_connect(timeout: int) -> int:
    from app.main import command_oauth_connect

    class Args:
        def __init__(self, timeout: int):
            self.timeout = timeout

    return command_oauth_connect(Args(timeout=timeout))


def oauth_status() -> int:
    storage, _, _, api, _ = build_services()
    status = api.get_auth_status()
    auth = storage.get_auth()
    if auth:
        status["expires_at"] = auth.get("expires_at")
    log("AUTH_JSON: " + json.dumps(status))
    return 0


def list_videos() -> int:
    storage, _, _, _, _ = build_services()
    log("VIDEOS_JSON: " + json.dumps(storage.get_video_queue_view()))
    return 0


def retry_video(video_path: str) -> int:
    storage, _, _, _, worker = build_services()
    target = Path(video_path).expanduser().resolve()
    row = storage.get_video_by_path(str(target))
    if not row:
        log(f"ERROR: No video record found for {target}")
        return 1

    video_id = int(row["id"])
    upload_id = storage.reset_upload(video_id)
    if upload_id is None:
        upload_id = storage.enqueue_upload(video_id)
    storage.update_video(video_id, status="ready")

    processed = worker.run_once(process_all=True)
    log("RETRY_JSON: " + json.dumps({"video_id": video_id, "upload_id": upload_id, "processed": processed}))

    upload = storage.get_upload_by_video_id(video_id) or {}
    return 0 if upload.get("status") == "posted" else 1


def delete_video(video_path: str) -> int:
    storage, _, _, _, _ = build_services()
    target = Path(video_path).expanduser().resolve()
    row = storage.get_video_by_path(str(target))
    if not row:
        log(f"ERROR: No video record found for {target}")
        return 1

    deleted = storage.delete_video(int(row["id"]))
    if not deleted:
        log("ERROR: Failed to delete video record")
        return 1

    for key in ("source_path", "export_path"):
        value = str(deleted.get(key) or "").strip()
        if not value:
            continue
        candidate = Path(value)
        if candidate.exists() and candidate.is_file():
            candidate.unlink(missing_ok=True)

    log("DELETE_JSON: " + json.dumps({"video_id": row["id"], "deleted": True}))
    return 0


def run_worker(once: bool) -> int:
    _, _, _, _, worker = build_services()
    if once:
        processed = worker.run_once(process_all=True)
        log(f"WORKER_PROCESSED: {processed}")
        return 0

    worker.start()

    def _stop_handler(signum, frame):
        worker.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _stop_handler)
    signal.signal(signal.SIGINT, _stop_handler)

    while True:
        time.sleep(1)


def main() -> int:
    configure_logging()

    parser = argparse.ArgumentParser(description="TikTok upload CLI")
    parser.add_argument("--video", help="Path to video file")
    parser.add_argument("--caption", default="", help="Caption text")
    parser.add_argument("--cookies", help="Deprecated: not used with official OAuth")

    parser.add_argument("--oauth-connect", action="store_true", help="Start OAuth authorization flow")
    parser.add_argument("--oauth-status", action="store_true", help="Get OAuth connection status")

    parser.add_argument("--worker", action="store_true", help="Run queue worker")
    parser.add_argument("--once", action="store_true", help="When used with --worker, process queue once and exit")

    parser.add_argument("--list-videos-json", action="store_true", help="List all videos and statuses as JSON")
    parser.add_argument("--retry-video", help="Retry upload for this video path")
    parser.add_argument("--delete-video", help="Delete video and metadata by path")

    parser.add_argument("--queue-only", action="store_true", help="Queue upload without processing immediately")
    parser.add_argument("--content-theme", default="story")
    parser.add_argument("--clip-format", default="background_layer")
    parser.add_argument("--oauth-timeout", type=int, default=240)

    args = parser.parse_args()

    try:
        if args.oauth_connect:
            return oauth_connect(args.oauth_timeout)
        if args.oauth_status:
            return oauth_status()
        if args.worker:
            return run_worker(args.once)
        if args.list_videos_json:
            return list_videos()
        if args.retry_video:
            return retry_video(args.retry_video)
        if args.delete_video:
            return delete_video(args.delete_video)

        if not args.video:
            parser.print_help()
            return 1

        if args.cookies:
            log("INFO: --cookies is ignored. Official OAuth tokens from SQLite are used instead.")

        return queue_and_upload(
            video=args.video,
            caption=args.caption,
            content_theme=args.content_theme,
            clip_format=args.clip_format,
            process_now=not args.queue_only,
        )
    except Exception as exc:
        log(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
