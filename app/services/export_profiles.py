from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class ExportProfile:
    """Single-pass FFmpeg profile for short-form output."""

    width: int = 1080
    height: int = 1920
    fps: int = 60
    video_codec: str = "libx264"
    video_profile: str = "high"
    video_preset: str = "medium"
    crf: int = 19
    pixel_format: str = "yuv420p"
    bitrate: str = "8M"
    maxrate: str = "10M"
    bufsize: str = "16M"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_sample_rate: int = 48000
    force_aspect: bool = True
    use_b_frames: bool = False

    def ffmpeg_video_args(self) -> List[str]:
        return [
            "-c:v",
            self.video_codec,
            "-profile:v",
            self.video_profile,
            "-pix_fmt",
            self.pixel_format,
            "-preset",
            self.video_preset,
            "-crf",
            str(self.crf),
            "-r",
            str(self.fps),
            "-b:v",
            self.bitrate,
            "-maxrate",
            self.maxrate,
            "-bufsize",
            self.bufsize,
            "-movflags",
            "+faststart",
        ]

    def ffmpeg_audio_args(self) -> List[str]:
        return [
            "-c:a",
            self.audio_codec,
            "-b:a",
            self.audio_bitrate,
            "-ar",
            str(self.audio_sample_rate),
        ]


def standard_1080x1920_profile() -> ExportProfile:
    return ExportProfile()
