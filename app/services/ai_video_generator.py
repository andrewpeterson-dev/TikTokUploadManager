from __future__ import annotations

import logging
import os
import subprocess
import sys
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .audio_engine import build_audio_filter
from .caption_renderer import build_caption_ass
from .color_engine import build_color_filter
from .export_profiles import standard_1080x1920_profile
from .motion_engine import build_motion_filter
from .quality_validator import QualityReport, validate_render
from .style_profiles import (
    StyleProfile,
    VideoType,
    get_available_video_types,
    get_style_profile,
)

# Add clip-empire to path for imports.
CLIP_EMPIRE_DIR = Path.home() / "clip-empire"
if str(CLIP_EMPIRE_DIR) not in sys.path:
    sys.path.insert(0, str(CLIP_EMPIRE_DIR))
    sys.path.insert(0, str(CLIP_EMPIRE_DIR / "src"))

# Load environment variables from clip-empire .env file
env_file = CLIP_EMPIRE_DIR / ".env"
if env_file.exists():
    with env_file.open() as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value

try:
    from content_generator import ContentGenerator
    from viral_video_editor import ViralVideoEditor
    from background_manager import BackgroundManager
except ImportError as exc:
    print(f"Warning: Could not import clip-empire modules: {exc}")
    ContentGenerator = None
    ViralVideoEditor = None
    BackgroundManager = None

LOGGER = logging.getLogger("tiktok_manager.ai_video_generator")


class AIVideoGenerator:
    """Generate AI-powered TikTok videos through a style-intelligence pipeline."""

    def __init__(self, output_dir: Optional[Path] = None):
        if output_dir is None:
            output_dir = Path.home() / "TikTok_Videos"

        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = self.output_dir / "tmp_style"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.dependencies_available = (
            ContentGenerator is not None and ViralVideoEditor is not None and BackgroundManager is not None
        )
        self.last_caption = ""
        self.last_transcript = ""
        self.last_audio_path = None

        if not self.dependencies_available:
            LOGGER.warning("clip-empire dependencies unavailable; AI generator will defer to backend fallback renderer.")

    @staticmethod
    def _format_seconds(value: float) -> str:
        return f"{max(0.0, float(value)):.3f}"

    @staticmethod
    def _escape_filter_path(value: str) -> str:
        escaped = str(value)
        escaped = escaped.replace("\\", "\\\\")
        escaped = escaped.replace(":", r"\:")
        escaped = escaped.replace("'", r"\'")
        escaped = escaped.replace(",", r"\,")
        return escaped

    @staticmethod
    def _run_ffmpeg(args: list[str], *, context: str) -> None:
        command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "ffmpeg error").strip()
            raise RuntimeError(f"{context} failed: {message}")

    @staticmethod
    def _run_ffprobe(args: list[str]) -> str:
        result = subprocess.run(["ffprobe", "-v", "error"] + args, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("ffprobe failed")
        return result.stdout or ""

    @classmethod
    def _probe_duration(cls, path: Path) -> float:
        output = cls._run_ffprobe(
            ["-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
        )
        try:
            return max(0.0, float(output.strip()))
        except ValueError:
            return 0.0

    @classmethod
    def _probe_has_audio(cls, path: Path) -> bool:
        try:
            info = json.loads(
                cls._run_ffprobe(
                    [
                        "-show_entries",
                        "stream=codec_type",
                        "-of",
                        "json",
                        str(path),
                    ]
                )
            )
        except Exception:
            return False
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "audio":
                return True
        return False

    @staticmethod
    def _normalize_theme(theme: str) -> str:
        return (theme or "").strip().lower() or "scary"

    @staticmethod
    def _map_theme_for_background(theme: str, profile: StyleProfile) -> str:
        if profile.background_type == "gta":
            return "crazy"
        if profile.background_type == "subway":
            return "scary"
        if profile.background_type == "cinematic":
            return "interesting"
        if profile.background_type == "blur":
            return "creepy"
        if profile.background_type == "none":
            return AIVideoGenerator._normalize_theme(theme)
        return AIVideoGenerator._normalize_theme(theme)

    def generate_base_video(
        self,
        theme: str = "scary",
        duration: int = 60,
        video_type: VideoType = "story",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[tuple[Path, StyleProfile, str]]:
        """
        Generate the first-pass raw viral video.

        Returns (video_path, style_profile, transcript).
        """
        self.last_caption = ""
        self.last_transcript = ""
        self.last_audio_path = None

        if not self.dependencies_available:
            if progress_callback:
                progress_callback("⚠️ AI generator dependencies unavailable. Using backend fallback renderer.")
            return None

        def log(message: str) -> None:
            try:
                if progress_callback:
                    progress_callback(message)
                else:
                    print(message)
            except BrokenPipeError:
                pass

        try:
            log("🎬 Starting AI video generation...")
            log(f"   Theme: {theme}")
            log(f"   Duration: {duration}s")
            log(f"   Type: {video_type}")

            profile = get_style_profile(video_type, theme=theme)
            log(f"   Style profile energy={profile.energy_level} color={profile.color_grade} motion={profile.motion_intensity:.2f}")

            # Organize output folder.
            today_folder = self.output_dir / datetime.now().strftime("%Y-%m-%d")
            today_folder.mkdir(parents=True, exist_ok=True)

            log(f"📝 Generating AI {video_type} content...")
            generator = ContentGenerator()

            # Prompting branch kept intentionally aligned with existing behavior for compatibility.
            if video_type in {"commentary", "story"}:
                package = generator.create_content_package(theme, target_duration=duration)
            elif video_type == "news":
                package = generator.create_content_package(theme, target_duration=duration)
            else:
                package = generator.create_content_package(theme, target_duration=duration)

            self.last_caption = str(package.get("caption") or "").strip()
            self.last_transcript = (
                str(package.get("script") or package.get("story") or package.get("text") or self.last_caption).strip()
            )
            self.last_audio_path = str(package.get("audio_path") or "").strip() or None

            if not self.last_audio_path:
                raise RuntimeError("Voiceover generation failed, cannot render video")

            log("✅ Content generated successfully")

            caption_file = CLIP_EMPIRE_DIR / "generated_content" / "latest_caption.txt"
            caption_file.parent.mkdir(parents=True, exist_ok=True)
            caption_file.write_text(self.last_caption)
            log(f"💬 Caption saved: {caption_file}")

            log("🎨 Selecting background video...")
            bg_manager = BackgroundManager()
            mapped_theme = self._map_theme_for_background(theme, profile)
            min_background_duration = max(30, min(int(duration), 60))
            background_video_path = bg_manager.get_background_for_theme(mapped_theme, min_duration=min_background_duration)

            if not background_video_path or not Path(background_video_path).exists():
                log("📥 No backgrounds available, downloading...")
                bg_manager.download_all_backgrounds()
                background_video_path = bg_manager.get_background_for_theme(
                    mapped_theme,
                    min_duration=min_background_duration,
                )
                if not background_video_path:
                    raise RuntimeError("Failed to get background video")

            log(f"✅ Using background: {Path(background_video_path).name}")

            output_name = f"TikTok_AI_{video_type}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
            editor = ViralVideoEditor(output_dir=str(today_folder))
            log("🎬 Creating base video...")
            video_path = editor.create_viral_video(
                audio_path=self.last_audio_path,
                background_video=background_video_path,
                output_name=output_name,
                theme=mapped_theme,
                add_captions=False,
            )
            if not video_path or not Path(video_path).exists():
                raise RuntimeError("Video render failed")

            log(f"✅ Base video created: {video_path}")
            return Path(video_path), profile, self.last_transcript

        except Exception as exc:
            LOGGER.exception("AI video base generation failed: %s", exc)
            if progress_callback:
                try:
                    progress_callback(f"Primary generator error: {exc}")
                except BrokenPipeError:
                    pass
            return None

    def apply_style_profile(self, profile: StyleProfile) -> StyleProfile:
        """Single stage hook for future style-profile expansion."""
        return profile

    def apply_motion_engine(self, profile: StyleProfile) -> str:
        return build_motion_filter(profile)

    def apply_color_engine(self, profile: StyleProfile) -> str:
        return build_color_filter(profile)

    def apply_caption_engine(
        self,
        transcript: str,
        duration_seconds: float,
        output_path: Path,
        profile: StyleProfile,
    ) -> Optional[Path]:
        if not transcript.strip():
            return None
        return build_caption_ass(
            transcript=transcript,
            duration_seconds=duration_seconds,
            output_path=output_path,
            profile=profile,
            style=profile.caption_style,
        )

    def apply_audio_engine(self, profile: StyleProfile) -> str:
        return build_audio_filter(profile)

    def validate_quality(self, video_path: Path, transcript: str) -> QualityReport:
        return validate_render(video_path, transcript=transcript or "")

    def apply_quality_profile(self, profile: StyleProfile, report: QualityReport) -> StyleProfile:
        if not report.corrections:
            return profile

        profile = replace(
            profile,
            caption_style="minimal",
            color_grade="clean",
            music_intensity=min(0.85, float(profile.music_intensity)),
        )

        if any(issue == "clipping_or_black_screen" for issue in report.issues):
            profile = replace(profile, motion_intensity=0.0, color_grade="clean")

        if report.corrections.get("motion_intensity") is not None:
            profile = replace(profile, motion_intensity=0.22)
        if report.corrections.get("music_intensity") is not None:
            profile = replace(profile, music_intensity=0.3)
        return profile

    def _build_styled_video(
        self,
        *,
        base_video_path: Path,
        transcript: str,
        profile: StyleProfile,
        output_path: Path,
        max_attempts: int = 2,
        attempt: int = 0,
    ) -> Path:
        if attempt >= max_attempts:
            return base_video_path

        duration = self._probe_duration(base_video_path)
        if duration <= 0:
            raise RuntimeError("Invalid base duration.")

        # Style profile pipeline stages (kept explicit for modular architecture).
        profile = self.apply_style_profile(profile)
        motion_filter = self.apply_motion_engine(profile)
        color_filter = self.apply_color_engine(profile)
        caption_ass = self.apply_caption_engine(
            transcript=transcript,
            duration_seconds=duration,
            output_path=self.temp_dir / f"{output_path.stem}_subs.ass",
            profile=profile,
        )
        audio_filter = self.apply_audio_engine(profile)

        video_parts = [
            "scale=1080:1920:force_original_aspect_ratio=increase",
            "crop=1080:1920",
            "setsar=1",
            motion_filter,
            color_filter,
        ]
        if caption_ass and caption_ass.exists():
            video_parts.append(f"subtitles='{self._escape_filter_path(str(caption_ass))}'")
        video_filter = "[0:v]" + ",".join(video_parts) + "[vout]"

        has_audio = self._probe_has_audio(base_video_path)
        if has_audio:
            audio_filter_chain = f"[0:a]{audio_filter}[aout]"
            filter_complex = f"{video_filter};{audio_filter_chain}"
        else:
            filter_complex = video_filter

        export_profile = standard_1080x1920_profile()

        args: list[str]
        if has_audio:
            args = [
                "-i",
                str(base_video_path),
                "-filter_complex",
                filter_complex,
                "-map",
                "[vout]",
                "-map",
                "[aout]",
                "-t",
                self._format_seconds(duration),
                *export_profile.ffmpeg_video_args(),
                *export_profile.ffmpeg_audio_args(),
                "-shortest",
                str(output_path),
            ]
        else:
            args = [
                "-i",
                str(base_video_path),
                "-filter_complex",
                filter_complex,
                "-map",
                "[vout]",
                "-an",
                "-t",
                self._format_seconds(duration),
                *export_profile.ffmpeg_video_args(),
                "-shortest",
                str(output_path),
            ]

        self._run_ffmpeg(args, context=f"Styled AI render attempt {attempt + 1}")

        if caption_ass and caption_ass.exists():
            caption_ass.unlink(missing_ok=True)

        report = self.validate_quality(output_path, transcript)
        if report.ok:
            return output_path

        corrected = self.apply_quality_profile(profile, report)
        if corrected == profile:
            if "clipping_or_black_screen" in report.issues:
                return base_video_path
            return output_path

        retry_name = output_path.with_name(f"{output_path.stem}_retry_{attempt + 1}.mp4")
        return self._build_styled_video(
            base_video_path=base_video_path,
            transcript=transcript,
            profile=corrected,
            output_path=retry_name,
            max_attempts=max_attempts,
            attempt=attempt + 1,
        )

    def generate_video(
        self,
        theme: str = "scary",
        duration: int = 60,
        video_type: VideoType = "story",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """
        Generate an AI video with the requested type using the full style engine.
        """
        if not self.dependencies_available:
            return None

        base_result = self.generate_base_video(
            theme=theme,
            duration=duration,
            video_type=video_type,
            progress_callback=progress_callback,
        )
        if not base_result:
            return None

        base_video_path, profile, transcript = base_result

        if not transcript:
            transcript = self.last_caption

        styled_name = (
            f"TikTok_AI_{video_type}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_styled.mp4"
        )
        output_path = self.output_dir / datetime.now().strftime("%Y-%m-%d") / styled_name
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if progress_callback:
                progress_callback(
                    f"🎛️ Applying style profile ({profile.color_grade}/{profile.caption_style})"
                )
            return str(self._build_styled_video(
                base_video_path=base_video_path,
                transcript=transcript,
                profile=profile,
                output_path=output_path,
            ))
        except Exception:
            LOGGER.exception("AI style pipeline failed; returning base render.")
            return str(base_video_path)

    def get_available_themes(self) -> list[str]:
        """Get list of available video themes"""
        return [
            "scary",
            "dating",
            "crazy",
            "mystery",
            "motivational",
            "creepy",
            "interesting",
        ]

    def get_available_durations(self) -> list[int]:
        """Get list of available video durations"""
        return [30, 60, 90, 120]

    def get_available_video_types(self) -> list[VideoType]:
        """Get list of available video types"""
        return get_available_video_types()  # type: ignore[return-value]


if __name__ == "__main__":
    generator = AIVideoGenerator()
    video_path = generator.generate_video(theme="scary", duration=60, video_type="story")
    if video_path:
        print(f"\n✅ Success! Video saved to: {video_path}")
    else:
        print("\n❌ Video generation failed")
