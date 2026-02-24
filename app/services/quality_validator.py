from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from .caption_renderer import chunk_transcript_for_subtitle


@dataclass
class QualityReport:
    ok: bool
    issues: List[str] = field(default_factory=list)
    corrections: Dict[str, float] = field(default_factory=dict)


def _run(args: List[str], *, context: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "command failed").strip()
        raise RuntimeError(f"{context} failed: {message}")
    return result


def _probe(video_path: Path) -> Dict[str, object]:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=width,height,codec_type",
            "-show_entries",
            "format=duration,bit_rate",
            "-of",
            "json",
            str(video_path),
        ],
        context="ffprobe metadata",
    )
    return json.loads(result.stdout or "{}")


def _detect_black_content(video_path: Path) -> bool:
    # Quick clipped-frame check: treat any sustained near-black region as potential issue.
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-vf",
            "blackdetect=d=0.35:pix_th=0.02",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    log = (result.stderr or "").replace("\n", " ")
    matches = re.findall(
        r"black_duration:([0-9]*\.?[0-9]+)",
        log,
    )
    if not matches:
        return False
    max_black = max(float(item) for item in matches)
    return max_black >= 0.6


def validate_render(video_path: Path, transcript: str = "", *, min_width: int = 1080, min_height: int = 1920) -> QualityReport:
    if not video_path.exists():
        return QualityReport(False, ["missing_file"], {})

    payload = _probe(video_path)
    format_info = payload.get("format") or {}
    width = 0
    height = 0
    has_audio = False
    for stream in payload.get("streams", []) or []:
        if not isinstance(stream, dict):
            continue
        if stream.get("codec_type") == "video":
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
        if stream.get("codec_type") == "audio":
            has_audio = True

    duration = float(format_info.get("duration") or 0.0)
    bitrate = int(format_info.get("bit_rate") or 0)

    issues: List[str] = []
    corrections: Dict[str, float] = {}

    if not width or not height:
        issues.append("missing_video_stream")
    else:
        if width != min_width or height != min_height:
            issues.append(f"resolution_not_standard_{width}x{height}")
            corrections["crf"] = 20

    ratio = (float(width) / float(height)) if width and height else 0.0
    if ratio and abs(ratio - (9.0 / 16.0)) > 0.005:
        issues.append(f"aspect_ratio_off_{ratio:.4f}")
        corrections["max_bitrate"] = 9500000

    if not has_audio:
        issues.append("missing_audio")

    if not duration or duration < 1.0:
        issues.append("invalid_duration")

    if bitrate and bitrate < 2_500_000:
        issues.append(f"bitrate_too_low_{bitrate}")
        corrections["bitrate"] = 7_000_000

    chunks = chunk_transcript_for_subtitle(transcript or "")
    if any(len(chunk.split()) > 4 for chunk in chunks):
        issues.append("caption_chunks_too_long")
        corrections["caption_style"] = 0

    if transcript and not chunks:
        issues.append("caption_parse_failure")
        corrections["caption_style"] = 0

    if _detect_black_content(video_path):
        issues.append("clipping_or_black_screen")
        corrections["motion_intensity"] = min(0.5, 0.25)

    return QualityReport(ok=(len(issues) == 0), issues=issues, corrections=corrections)
