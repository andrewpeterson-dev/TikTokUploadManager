from __future__ import annotations

import argparse
import json
import logging
import os
import random
import secrets
import signal
import subprocess
import sys
import threading
import time
import warnings
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

APP_ROOT = Path(__file__).resolve().parent
LOG_PATH = APP_ROOT.parent / "logs" / "app.log"

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

try:
    from app.services.caption_engine import CaptionContext, CaptionEngine
    from app.services.storage import AppStorage, auth_seconds_remaining
    from app.services.tiktok_api import TikTokAPI, TikTokAPIError
    from app.services.upload_queue import UploadQueueWorker
    from app.services.video_engine import GeneratedClip, VideoEngine
    from app.services.shortform_ai_engine import SHORTFORM_AI_ENABLED, optimize_shortform_video
    from app.services.ai_video_generator import AIVideoGenerator
except ModuleNotFoundError:
    project_root = APP_ROOT.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from services.caption_engine import CaptionContext, CaptionEngine
    from services.storage import AppStorage, auth_seconds_remaining
    from services.tiktok_api import TikTokAPI, TikTokAPIError
    from services.upload_queue import UploadQueueWorker
    from services.video_engine import GeneratedClip, VideoEngine
    from services.shortform_ai_engine import SHORTFORM_AI_ENABLED, optimize_shortform_video
    from services.ai_video_generator import AIVideoGenerator


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(logging.INFO)

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(stream_handler)


LOGGER = logging.getLogger("tiktok_manager.main")


class CallbackHTTPServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.callback_event = threading.Event()
        self.payload: Dict[str, str] = {}


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        query = parse_qs(parsed.query)
        payload = {key: values[0] for key, values in query.items() if values}

        server: CallbackHTTPServer = self.server  # type: ignore[assignment]
        server.payload = payload
        server.callback_event.set()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h3>TikTok authorization complete.</h3><p>You can close this window and return to the app.</p></body></html>"
        )

    def log_message(self, fmt: str, *args: object) -> None:
        return


def build_services() -> tuple[AppStorage, VideoEngine, CaptionEngine, TikTokAPI, UploadQueueWorker]:
    storage = AppStorage(APP_ROOT)
    video_engine = VideoEngine(storage)
    caption_engine = CaptionEngine()
    tiktok_api = TikTokAPI(storage)
    upload_worker = UploadQueueWorker(
        storage=storage,
        video_engine=video_engine,
        caption_engine=caption_engine,
        tiktok_api=tiktok_api,
        max_retries=3,
        poll_interval_seconds=8,
    )
    return storage, video_engine, caption_engine, tiktok_api, upload_worker


def _human_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    kb = num_bytes / 1024
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f} MB"
    gb = mb / 1024
    return f"{gb:.2f} GB"


def _pick_background_video_for_theme(storage: AppStorage, theme: str) -> Path:
    candidates = [
        item
        for item in storage.backgrounds_dir.iterdir()
        if item.is_file() and item.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm"}
    ]
    if not candidates:
        raise RuntimeError(
            f"No background videos found in {storage.backgrounds_dir}. Add files to continue."
        )

    lower_theme = theme.lower().strip()
    themed = [item for item in candidates if lower_theme and lower_theme in item.name.lower()]
    return random.choice(themed or candidates)


def _build_ai_fallback_caption(theme: str, video_type: str) -> tuple[str, str]:
    hook_map = {
        "scary": "This ending is darker than it looks.",
        "dating": "This relationship twist hits fast.",
        "crazy": "Chaos escalates in seconds.",
        "mystery": "A hidden detail changes everything.",
        "motivational": "Small moves create big momentum.",
        "interesting": "Watch what happens when the pattern breaks.",
    }
    hook = hook_map.get(theme.lower(), "This clip builds fast and pays off at the end.")
    body = (
        f"{hook} Built as a {video_type} short with clean pacing, readable captions, "
        "and a gameplay background tuned for retention."
    )
    hashtags = f"#{theme.lower()} #viral #fyp #shorts #tiktok"
    caption = f"{body} {hashtags}"
    transcript = body
    return caption, transcript


def _render_local_ai_video_fallback(
    *,
    storage: AppStorage,
    video_engine: VideoEngine,
    theme: str,
    duration: int,
    video_type: str,
    progress_callback,
) -> tuple[str, str, str]:
    duration_seconds = max(10, int(duration))
    background = _pick_background_video_for_theme(storage, theme)
    caption, transcript = _build_ai_fallback_caption(theme, video_type)

    temp_source = storage.videos_dir / f"ai_fallback_source_{int(time.time())}.mp4"
    trim_cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-stream_loop",
        "-1",
        "-i",
        str(background),
        "-t",
        str(duration_seconds),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        str(temp_source),
    ]

    result = subprocess.run(trim_cmd, capture_output=True, text=True)
    if result.returncode != 0 or not temp_source.exists():
        message = (result.stderr or result.stdout or "ffmpeg fallback trim failed").strip()
        raise RuntimeError(message)

    day_folder = Path.home() / "TikTok_Videos" / time.strftime("%Y-%m-%d")
    day_folder.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    output_path = day_folder / f"TikTok_AI_{video_type}_{timestamp}_fallback.mp4"

    try:
        progress_callback(f"Fallback source: {background.name}")
        final_path = video_engine.render_vertical(
            source_path=temp_source,
            output_path=output_path,
            caption=caption,
            apply_shortform_optimization=False,
        )
    finally:
        temp_source.unlink(missing_ok=True)

    return str(final_path), caption, transcript


def command_generate(args: argparse.Namespace) -> int:
    storage, video_engine, _, _, _ = build_services()

    def progress(message: str) -> None:
        print(message, flush=True)

    clips = video_engine.generate_clips(
        source_reference=args.source,
        clip_duration=args.duration,
        max_clips=args.max_clips,
        content_theme=args.content_theme,
        progress_callback=progress,
    )

    for clip in clips:
        video_id = storage.create_or_update_video(
            filename=clip.filename,
            source_path=clip.path,
            export_path=clip.path,
            status="ready",
        )
        payload = {
            "videoId": video_id,
            "fileName": clip.filename,
            "duration": clip.duration,
            "size": _human_size(clip.size_bytes),
            "path": clip.path,
            "status": "ready",
        }
        print(f"CLIP_GENERATED: {clip.filename}", flush=True)
        print(f"CLIP_JSON: {json.dumps(payload)}", flush=True)

    print(f"DONE: Generated {len(clips)} clips", flush=True)
    return 0


def command_oauth_connect(args: argparse.Namespace) -> int:
    _, _, _, api, _ = build_services()

    state = secrets.token_urlsafe(24)
    auth_url = api.build_authorize_url(state)
    server = CallbackHTTPServer(("127.0.0.1", 8000), OAuthCallbackHandler)

    def run_server() -> None:
        server.handle_request()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    print("OAUTH: Opening browser for TikTok authorization...", flush=True)
    print(f"OAUTH_URL: {auth_url}", flush=True)
    webbrowser.open(auth_url)

    if not server.callback_event.wait(timeout=max(30, int(args.timeout))):
        server.server_close()
        raise RuntimeError("OAuth callback timed out. No authorization code received.")

    payload = dict(server.payload)
    server.server_close()

    if payload.get("state") != state:
        raise RuntimeError("OAuth state mismatch; authorization was rejected for safety.")

    if payload.get("error"):
        raise RuntimeError(f"TikTok authorization error: {payload.get('error_description') or payload['error']}")

    code = payload.get("code")
    if not code:
        raise RuntimeError("TikTok callback did not include an authorization code.")

    auth = api.exchange_code_for_token(code)
    print(
        "AUTH_JSON: "
        + json.dumps(
            {
                "connected": True,
                "expires_at": auth.get("expires_at"),
                "scope": auth.get("scope"),
            }
        ),
        flush=True,
    )
    return 0


def command_oauth_status(_: argparse.Namespace) -> int:
    storage, _, _, api, _ = build_services()
    status = api.get_auth_status()
    auth = storage.get_auth()
    if auth:
        status["seconds_remaining"] = auth_seconds_remaining(auth)
    print("AUTH_JSON: " + json.dumps(status), flush=True)
    return 0


def _ensure_video_record(storage: AppStorage, source_path: Path) -> int:
    existing = storage.get_video_by_path(str(source_path))
    if existing:
        return int(existing["id"])

    return storage.create_or_update_video(
        filename=source_path.name,
        source_path=str(source_path),
        export_path=str(source_path),
        status="ready",
    )


def command_queue_upload(args: argparse.Namespace) -> int:
    storage, _, caption_engine, _, worker = build_services()

    source_path = Path(args.video).expanduser().resolve()
    if not source_path.exists():
        raise RuntimeError(f"Video path not found: {source_path}")

    video_id = _ensure_video_record(storage, source_path)

    caption = (args.caption or "").strip()
    if not caption:
        context = CaptionContext(
            filename=source_path.name,
            content_theme=args.content_theme,
            clip_format=args.clip_format,
            source_hint=source_path.stem,
        )
        caption = caption_engine.generate_caption(context)

    storage.update_video(video_id, caption=caption, status="ready")
    upload_id = storage.enqueue_upload(video_id)
    print(f"QUEUE: video_id={video_id} upload_id={upload_id}", flush=True)

    if args.process_now:
        processed = worker.run_once(process_all=True)
        print(f"QUEUE_PROCESSED: {processed}", flush=True)

    video = storage.get_video_by_id(video_id) or {}
    upload = storage.get_upload_by_video_id(video_id) or {}
    print(
        "UPLOAD_JSON: "
        + json.dumps(
            {
                "video_id": video_id,
                "upload_id": upload_id,
                "video_status": video.get("status"),
                "upload_status": upload.get("status"),
                "retry_count": upload.get("retry_count"),
                "caption": caption,
            }
        ),
        flush=True,
    )
    return 0


def command_worker(args: argparse.Namespace) -> int:
    _, _, _, _, worker = build_services()
    if args.once:
        processed = worker.run_once(process_all=True)
        print(f"WORKER_PROCESSED: {processed}", flush=True)
        return 0

    worker.start()

    def _stop_handler(signum, frame):
        worker.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _stop_handler)
    signal.signal(signal.SIGINT, _stop_handler)

    while True:
        time.sleep(1)


def command_list_videos(_: argparse.Namespace) -> int:
    storage, _, _, _, _ = build_services()
    rows = storage.get_video_queue_view()
    print("VIDEOS_JSON: " + json.dumps(rows), flush=True)
    return 0


def command_retry(args: argparse.Namespace) -> int:
    storage, _, _, _, worker = build_services()
    target = Path(args.video).expanduser().resolve()
    row = storage.get_video_by_path(str(target))
    if not row:
        raise RuntimeError(f"No database video record found for {target}")

    video_id = int(row["id"])
    upload_id = storage.reset_upload(video_id)
    if upload_id is None:
        upload_id = storage.enqueue_upload(video_id)

    storage.update_video(video_id, status="ready")
    processed = worker.run_once(process_all=True)
    print(f"RETRY_JSON: {json.dumps({'video_id': video_id, 'upload_id': upload_id, 'processed': processed})}", flush=True)
    return 0


def command_delete(args: argparse.Namespace) -> int:
    storage, _, _, _, _ = build_services()
    target = Path(args.video).expanduser().resolve()
    row = storage.get_video_by_path(str(target))
    if not row:
        raise RuntimeError(f"No database video record found for {target}")

    video_id = int(row["id"])
    deleted = storage.delete_video(video_id)
    if not deleted:
        raise RuntimeError(f"Failed to delete video id {video_id}")

    for key in ("source_path", "export_path"):
        value = str(deleted.get(key) or "").strip()
        if not value:
            continue
        file_path = Path(value)
        if file_path.exists() and file_path.is_file():
            file_path.unlink(missing_ok=True)

    print(f"DELETE_JSON: {json.dumps({'video_id': video_id, 'deleted': True})}", flush=True)
    return 0


def command_list_backgrounds(_: argparse.Namespace) -> int:
    storage, _, _, _, _ = build_services()
    backgrounds = [
        str(item.name)
        for item in storage.backgrounds_dir.iterdir()
        if item.is_file() and item.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm", ".jpg", ".jpeg", ".png"}
    ]
    backgrounds.sort()
    print("BACKGROUNDS_JSON: " + json.dumps(backgrounds), flush=True)
    return 0


def command_generate_ai_video(args: argparse.Namespace) -> int:
    storage, video_engine, _, _, _ = build_services()

    def safe_emit(line: str) -> None:
        try:
            print(line, flush=True)
        except BrokenPipeError:
            LOGGER.warning("stdout pipe closed while emitting AI video progress/output")

    def progress(message: str) -> None:
        safe_emit(f"PROGRESS: {message}")

    generator = AIVideoGenerator()
    video_path = generator.generate_video(
        theme=args.theme,
        duration=args.duration,
        video_type=args.video_type,
        progress_callback=progress,
    )

    transcript = (getattr(generator, "last_transcript", "") or "").strip()
    caption_for_storage = (getattr(generator, "last_caption", "") or "").strip() or None

    if not video_path:
        progress("Primary AI generation unavailable. Rendering resilient local fallback...")
        fallback_path, fallback_caption, fallback_transcript = _render_local_ai_video_fallback(
            storage=storage,
            video_engine=video_engine,
            theme=args.theme,
            duration=args.duration,
            video_type=args.video_type,
            progress_callback=progress,
        )
        video_path = fallback_path
        caption_for_storage = fallback_caption
        transcript = fallback_transcript

    # Integration point:
    # video = generate_video()
    # if SHORTFORM_AI_ENABLED:
    #     video = optimize_shortform_video(video, transcript)
    if SHORTFORM_AI_ENABLED:
        progress("Running short-form AI optimization...")
        video_path = optimize_shortform_video(video_path, transcript)

    # Create video record in database
    video_file = Path(video_path)
    video_id = storage.create_or_update_video(
        filename=video_file.name,
        source_path=str(video_file),
        export_path=str(video_file),
        caption=caption_for_storage,
        status="ready",
    )

    # Get video stats
    duration_sec = args.duration
    size_bytes = video_file.stat().st_size if video_file.exists() else 0

    payload = {
        "videoId": video_id,
        "fileName": video_file.name,
        "duration": duration_sec,
        "size": _human_size(size_bytes),
        "path": str(video_path),
        "status": "ready",
        "theme": args.theme,
        "videoType": args.video_type,
    }

    safe_emit(f"AI_VIDEO_GENERATED: {video_file.name}")
    safe_emit(f"AI_VIDEO_JSON: {json.dumps(payload)}")
    safe_emit("DONE: AI video generation complete")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TikTok Upload Manager backend")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate clips")
    generate.add_argument("--source", required=True)
    generate.add_argument("--duration", type=int, default=30)
    generate.add_argument("--max-clips", type=int, default=2)
    generate.add_argument("--content-theme", default="story")
    generate.set_defaults(func=command_generate)

    oauth_connect = subparsers.add_parser("oauth-connect", help="Run OAuth connect flow")
    oauth_connect.add_argument("--timeout", type=int, default=240)
    oauth_connect.set_defaults(func=command_oauth_connect)

    oauth_status = subparsers.add_parser("oauth-status", help="Show OAuth status")
    oauth_status.set_defaults(func=command_oauth_status)

    queue_upload = subparsers.add_parser("queue-upload", help="Queue video for upload")
    queue_upload.add_argument("--video", required=True)
    queue_upload.add_argument("--caption", default="")
    queue_upload.add_argument("--content-theme", default="story")
    queue_upload.add_argument("--clip-format", default="background_layer")
    queue_upload.add_argument("--process-now", action="store_true")
    queue_upload.set_defaults(func=command_queue_upload)

    worker = subparsers.add_parser("worker", help="Run upload queue worker")
    worker.add_argument("--once", action="store_true")
    worker.set_defaults(func=command_worker)

    list_videos = subparsers.add_parser("list-videos", help="List videos")
    list_videos.set_defaults(func=command_list_videos)

    retry = subparsers.add_parser("retry", help="Retry a failed upload")
    retry.add_argument("--video", required=True)
    retry.set_defaults(func=command_retry)

    delete = subparsers.add_parser("delete", help="Delete a video and metadata")
    delete.add_argument("--video", required=True)
    delete.set_defaults(func=command_delete)

    backgrounds = subparsers.add_parser("list-backgrounds", help="List background assets")
    backgrounds.set_defaults(func=command_list_backgrounds)

    generate_ai = subparsers.add_parser("generate-ai-video", help="Generate AI-powered video")
    generate_ai.add_argument("--theme", default="scary", choices=["scary", "dating", "crazy", "mystery", "motivational", "creepy", "interesting"])
    generate_ai.add_argument("--duration", type=int, default=60, choices=[30, 60, 90, 120])
    generate_ai.add_argument("--video-type", default="story", choices=["story", "commentary", "news"])
    generate_ai.set_defaults(func=command_generate_ai_video)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.func(args))
    except BrokenPipeError:
        LOGGER.warning("stdout pipe closed (BrokenPipeError)")
        return 1
    except TikTokAPIError as exc:
        LOGGER.exception("TikTok API error")
        try:
            print(f"ERROR: {exc}", flush=True)
        except BrokenPipeError:
            pass
        return 1
    except Exception as exc:
        LOGGER.exception("Unhandled backend error")
        try:
            print(f"ERROR: {exc}", flush=True)
        except BrokenPipeError:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
