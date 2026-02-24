from __future__ import annotations

import json
import logging
import math
import random
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

try:
    from .shortform_ai_engine import SHORTFORM_AI_ENABLED, optimize_shortform_video
except Exception:  # pragma: no cover - fallback keeps pipeline safe if module import fails
    SHORTFORM_AI_ENABLED = False

    def optimize_shortform_video(video_path: str, transcript: str) -> str:
        return video_path

from .storage import AppStorage

LOGGER = logging.getLogger("tiktok_manager.video_engine")

try:
    import yt_dlp  # type: ignore

    YTDLP_AVAILABLE = True
except Exception:
    yt_dlp = None
    YTDLP_AVAILABLE = False

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SUPPORTED_BACKGROUND_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS


@dataclass
class GeneratedClip:
    filename: str
    path: str
    duration: int
    size_bytes: int


class VideoEngine:
    """High-quality vertical video rendering engine for TikTok publishing."""

    def __init__(self, storage: AppStorage):
        self.storage = storage
        self.temp_dir = self.storage.app_root / "media" / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _run_ffmpeg(self, args: List[str], *, error_context: str) -> None:
        command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "ffmpeg error").strip()
            LOGGER.error("%s failed: %s", error_context, message)
            raise RuntimeError(f"{error_context} failed: {message}")

    def _run_ffprobe(self, args: List[str]) -> Dict[str, object]:
        command = ["ffprobe", "-v", "error"] + args
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "ffprobe error").strip()
            raise RuntimeError(f"ffprobe failed: {message}")
        return json.loads(result.stdout or "{}")

    def _probe_video(self, video_path: Path) -> Dict[str, float]:
        payload = self._run_ffprobe(
            [
                "-show_entries",
                "stream=width,height,codec_type",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(video_path),
            ]
        )
        duration = float((payload.get("format") or {}).get("duration") or 0.0)
        width = 0.0
        height = 0.0
        has_audio = False
        for stream in payload.get("streams", []):
            if not isinstance(stream, dict):
                continue
            if stream.get("codec_type") == "video":
                width = float(stream.get("width") or 0)
                height = float(stream.get("height") or 0)
            if stream.get("codec_type") == "audio":
                has_audio = True

        if width <= 0 or height <= 0:
            raise RuntimeError(f"Unable to read video dimensions for {video_path}")

        return {
            "duration": max(duration, 0.0),
            "width": width,
            "height": height,
            "has_audio": 1.0 if has_audio else 0.0,
        }

    def _is_url(self, value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _download_video(self, source_url: str) -> Path:
        if not YTDLP_AVAILABLE:
            raise RuntimeError("yt-dlp is required for URL downloads. Install yt-dlp Python package.")

        timestamp = int(time.time())
        output_template = str(self.storage.videos_dir / f"source_{timestamp}_%(id)s.%(ext)s")
        options = {
            "format": "bv*+ba/b",
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
        }

        with yt_dlp.YoutubeDL(options) as downloader:  # type: ignore[union-attr]
            info = downloader.extract_info(source_url, download=True)
            output_path = Path(downloader.prepare_filename(info))

        if output_path.suffix.lower() != ".mp4":
            mp4_candidate = output_path.with_suffix(".mp4")
            if mp4_candidate.exists():
                output_path = mp4_candidate

        if not output_path.exists():
            raise RuntimeError("Downloaded source video was not found on disk.")

        return output_path

    def resolve_source(self, source: str) -> Path:
        source = source.strip()
        if not source:
            raise RuntimeError("Source video path or URL is required.")

        source_path = Path(source)
        if source_path.exists() and source_path.is_file():
            return source_path.resolve()

        if self._is_url(source):
            return self._download_video(source)

        raise RuntimeError(f"Source is not a readable local file or valid URL: {source}")

    def _pick_background_asset(self) -> Path:
        candidates = [
            path
            for path in self.storage.backgrounds_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_BACKGROUND_EXTENSIONS
        ]
        if not candidates:
            raise RuntimeError(
                f"No background assets found in {self.storage.backgrounds_dir}. "
                "Add gameplay/background media before rendering."
            )
        return random.choice(candidates)

    def _format_ass_timestamp(self, seconds: float) -> str:
        total_centiseconds = max(0, int(round(seconds * 100)))
        hours = total_centiseconds // 360000
        minutes = (total_centiseconds % 360000) // 6000
        secs = (total_centiseconds % 6000) // 100
        centis = total_centiseconds % 100
        return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"

    def _sanitize_caption_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        text = text.replace("{", "\\{").replace("}", "\\}")
        return text

    def _select_font_size(self, text_len: int) -> int:
        if text_len <= 90:
            return 62
        if text_len <= 150:
            return 54
        if text_len <= 220:
            return 48
        return 42

    def _wrap_caption_lines(self, text: str, max_chars_per_line: int) -> List[str]:
        words = text.split()
        lines: List[str] = []
        current: List[str] = []
        length = 0

        for word in words:
            token_len = len(word) if not current else len(word) + 1
            if length + token_len <= max_chars_per_line:
                current.append(word)
                length += token_len
            else:
                lines.append(" ".join(current))
                current = [word]
                length = len(word)

        if current:
            lines.append(" ".join(current))

        if len(lines) <= 3:
            return lines

        merged = lines[:2]
        trailing = " ".join(lines[2:])
        max_final = max_chars_per_line * 2
        if len(trailing) > max_final:
            trailing = trailing[: max_final - 3].rstrip() + "..."
        merged.append(trailing)
        return merged[:3]

    def _build_caption_ass_file(self, caption: str, duration_seconds: float, target_path: Path) -> Path:
        clean_text = self._sanitize_caption_text(caption)
        if not clean_text:
            raise RuntimeError("Caption text is empty.")

        font_size = self._select_font_size(len(clean_text))
        max_chars = 32 if font_size >= 56 else 36 if font_size >= 48 else 40
        lines = self._wrap_caption_lines(clean_text, max_chars)

        # Enforce 20% vertical max (384px) by reducing font size if needed.
        line_height = font_size * 1.28
        while len(lines) * line_height > 384 and font_size > 28:
            font_size -= 2
            line_height = font_size * 1.28

        line_payload = "\\N".join(lines[:3])
        ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Caption,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H64000000,1,0,0,0,100,100,0,0,1,3,2,2,80,80,154,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
Dialogue: 0,0:00:00.00,{self._format_ass_timestamp(duration_seconds)},Caption,,0,0,0,,{line_payload}
"""
        target_path.write_text(ass, encoding="utf-8")
        return target_path

    def _escape_filter_path(self, path: Path) -> str:
        escaped = str(path)
        escaped = escaped.replace("\\", "\\\\")
        escaped = escaped.replace(":", r"\:")
        escaped = escaped.replace("'", r"\'")
        escaped = escaped.replace(",", r"\,")
        return escaped

    def render_vertical(
        self,
        *,
        source_path: Path,
        output_path: Path,
        caption: Optional[str] = None,
        background_path: Optional[Path] = None,
    ) -> Path:
        if not source_path.exists():
            raise RuntimeError(f"Source video not found: {source_path}")

        bg_asset = background_path or self._pick_background_asset()
        if not bg_asset.exists():
            raise RuntimeError(f"Background asset not found: {bg_asset}")

        source_meta = self._probe_video(source_path)
        duration = float(source_meta["duration"])
        if duration <= 0:
            raise RuntimeError("Source video has invalid duration.")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        filter_segments: List[str] = [
            "[1:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=12:6[bg]",
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:15[srcblur]",
            "[bg][srcblur]blend=all_mode='overlay':all_opacity=0.35[base]",
            "[0:v]scale='if(gt(iw,1080),1080,iw)':'if(gt(ih,1728),1728,ih)':force_original_aspect_ratio=decrease,setsar=1[fg]",
            "[base][fg]overlay=(W-w)/2:(H-h)/2:shortest=1[vtmp]",
        ]

        ass_file: Optional[Path] = None
        if caption and caption.strip():
            ass_file = self._build_caption_ass_file(
                caption=caption,
                duration_seconds=duration,
                target_path=self.temp_dir / f"{output_path.stem}.ass",
            )
            filter_segments.append(
                f"[vtmp]subtitles='{self._escape_filter_path(ass_file)}'[vout]"
            )
            output_label = "[vout]"
        else:
            output_label = "[vtmp]"

        filter_complex = ";".join(filter_segments)
        cmd: List[str] = ["-i", str(source_path)]
        if bg_asset.suffix.lower() in IMAGE_EXTENSIONS:
            cmd += ["-loop", "1", "-i", str(bg_asset)]
        else:
            cmd += ["-stream_loop", "-1", "-i", str(bg_asset)]

        cmd += [
            "-filter_complex",
            filter_complex,
            "-map",
            output_label,
            "-map",
            "0:a?",
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ]

        self._run_ffmpeg(cmd, error_context="Vertical render")

        if ass_file and ass_file.exists():
            ass_file.unlink(missing_ok=True)

        if not SHORTFORM_AI_ENABLED:
            return output_path

        # Short-form optimizer is fail-safe by design; on failure it returns the original path.
        transcript = caption or ""
        enhanced_path = Path(optimize_shortform_video(str(output_path), transcript)).resolve()
        if enhanced_path.exists():
            return enhanced_path
        return output_path

    def _extract_segment(self, *, source_path: Path, start_time: float, duration: int, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._run_ffmpeg(
            [
                "-ss",
                f"{max(0.0, start_time):.3f}",
                "-i",
                str(source_path),
                "-t",
                str(max(1, duration)),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-movflags",
                "+faststart",
                str(output_path),
            ],
            error_context="Segment extraction",
        )
        return output_path

    def _segment_start_times(self, *, duration_seconds: float, clip_duration: int, max_clips: int) -> List[float]:
        if duration_seconds <= clip_duration or max_clips <= 1:
            return [0.0]

        usable = max(0.0, duration_seconds - clip_duration)
        if usable <= 0:
            return [0.0]

        count = min(max_clips, max(1, int(duration_seconds // max(5, clip_duration // 2))))
        if count <= 1:
            return [0.0]

        step = usable / float(count - 1)
        starts = [round(step * idx, 3) for idx in range(count)]
        return starts[:max_clips]

    def generate_clips(
        self,
        *,
        source_reference: str,
        clip_duration: int,
        max_clips: int,
        content_theme: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[GeneratedClip]:
        clip_duration = max(5, int(clip_duration))
        max_clips = max(1, int(max_clips))

        if progress_callback:
            progress_callback("Step 1/6: Resolving source video...")
        source_path = self.resolve_source(source_reference)

        if progress_callback:
            progress_callback("Step 2/6: Probing source media...")
        meta = self._probe_video(source_path)
        duration_seconds = float(meta["duration"])
        if duration_seconds <= 0:
            raise RuntimeError("Source duration is invalid.")

        starts = self._segment_start_times(
            duration_seconds=duration_seconds,
            clip_duration=clip_duration,
            max_clips=max_clips,
        )

        generated: List[GeneratedClip] = []
        for index, start_time in enumerate(starts, start=1):
            if progress_callback:
                progress_callback(f"Step 3/6: Extracting clip {index}/{len(starts)}...")

            clip_stem = f"clip_{int(time.time())}_{index}_{source_path.stem[:24]}"
            segment_path = self.temp_dir / f"{clip_stem}_segment.mp4"
            self._extract_segment(
                source_path=source_path,
                start_time=start_time,
                duration=clip_duration,
                output_path=segment_path,
            )

            if progress_callback:
                progress_callback(f"Step 4/6: Rendering clip {index}/{len(starts)} to 9:16...")

            rendered_path = self.storage.videos_dir / f"{clip_stem}.mp4"
            final_rendered_path = self.render_vertical(
                source_path=segment_path,
                output_path=rendered_path,
                caption=None,
            )

            segment_path.unlink(missing_ok=True)

            generated.append(
                GeneratedClip(
                    filename=final_rendered_path.name,
                    path=str(final_rendered_path),
                    duration=int(min(clip_duration, max(1, math.ceil(duration_seconds - start_time)))),
                    size_bytes=int(final_rendered_path.stat().st_size),
                )
            )

        if progress_callback:
            progress_callback("Step 5/6: Finalizing metadata...")
            progress_callback("Step 6/6: Clip generation complete.")

        return generated

    def render_for_posting(
        self,
        *,
        source_path: Path,
        caption: str,
        output_filename: Optional[str] = None,
    ) -> Path:
        stem = source_path.stem
        filename = output_filename or f"{stem}_post.mp4"
        output_path = self.storage.exports_dir / filename
        return self.render_vertical(source_path=source_path, output_path=output_path, caption=caption)
