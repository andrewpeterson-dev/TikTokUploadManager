#!/usr/bin/env python3
"""CLI bridge for SwiftUI frontend to production backend services."""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def human_size(num_bytes: int) -> str:
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


def log(message: str) -> None:
    print(message, flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TikTok clip generation CLI bridge")
    parser.add_argument("--url", required=True, help="Video URL or local file path")
    parser.add_argument("--duration", type=int, default=30, help="Clip duration in seconds")
    parser.add_argument("--max_clips", type=int, default=2, help="Maximum clips to generate")
    parser.add_argument("--captions", default="true", help="Enable captions (true/false)")
    parser.add_argument("--music", default="true", help="Enable music (true/false)")
    parser.add_argument("--effects", default="true", help="Enable effects (true/false)")
    parser.add_argument(
        "--clip_format",
        default="background_layer",
        choices=["straight_highlight", "background_layer", "commentary_layer"],
        help="Clipping format profile",
    )
    parser.add_argument(
        "--content_theme",
        default="story",
        choices=["podcast", "gaming", "story", "motivation", "drama"],
        help="Theme profile for styling and pacing",
    )
    parser.add_argument(
        "--variation_mode",
        default="varied",
        choices=["stable", "varied", "wild"],
        help="How much variation to introduce in generated clips",
    )
    parser.add_argument("--run_seed", default="", help="Optional run seed for clip variation")

    parser.add_argument("--use_smart_backgrounds", default="false")
    parser.add_argument("--background_theme", default="scary")
    parser.add_argument("--account_username", default="")
    parser.add_argument("--auto_track", default="false")
    parser.add_argument("--shortform_ai", default="true", help="Enable shortform AI optimization (true/false)")
    parser.add_argument("--aesthetic_threshold", type=int, default=75, help="Shortform aesthetic threshold")
    parser.add_argument("--engagement_threshold", type=int, default=70, help="Shortform engagement threshold")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    shortform_ai_enabled = parse_bool(args.shortform_ai)
    os.environ["SHORTFORM_AI_ENABLED"] = "true" if shortform_ai_enabled else "false"
    os.environ["AESTHETIC_THRESHOLD"] = str(args.aesthetic_threshold)
    os.environ["ENGAGEMENT_THRESHOLD"] = str(args.engagement_threshold)

    from app.main import configure_logging
    from app.services.storage import AppStorage
    from app.services.video_engine import VideoEngine

    configure_logging()

    _ = parse_bool(args.captions)
    _ = parse_bool(args.music)
    _ = parse_bool(args.effects)
    use_smart_backgrounds = parse_bool(args.use_smart_backgrounds)
    auto_track = parse_bool(args.auto_track)

    storage = AppStorage(PROJECT_ROOT / "app")
    engine = VideoEngine(storage)

    log("Step 0/6: Starting clip generation...")
    log(
        "CONFIG: "
        f"format={args.clip_format} "
        f"theme={args.content_theme} "
        f"variation={args.variation_mode} "
        f"shortform_ai={shortform_ai_enabled} "
        f"thresholds={args.aesthetic_threshold}/{args.engagement_threshold}"
    )

    if use_smart_backgrounds:
        log(f"Smart backgrounds enabled (theme={args.background_theme})")

    try:
        clips = engine.generate_clips(
            source_reference=args.url,
            clip_duration=args.duration,
            max_clips=args.max_clips,
            content_theme=args.content_theme,
            progress_callback=log,
        )

        if not clips:
            log("ERROR: No clips generated")
            return 2

        for clip in clips:
            video_id = storage.create_or_update_video(
                filename=clip.filename,
                source_path=clip.path,
                export_path=clip.path,
                status="ready",
            )
            storage.enqueue_upload(video_id) if auto_track and args.account_username else None

            payload = {
                "videoId": video_id,
                "fileName": clip.filename,
                "duration": clip.duration,
                "size": human_size(clip.size_bytes),
                "path": clip.path,
                "status": "ready",
            }

            log(f"CLIP_GENERATED: {clip.filename}")
            log("CLIP_JSON: " + json.dumps(payload))

            if auto_track and args.account_username:
                log(f"Queued clip for upload tracking to @{args.account_username}")

        log(f"DONE: Generated {len(clips)} clips")
        return 0

    except KeyboardInterrupt:
        log("ERROR: Interrupted")
        return 130
    except Exception as exc:
        log(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
