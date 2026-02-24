"""
AI Video Generator Service
Generates AI-powered videos with stories, commentary, or news
"""

import sys
import os
import logging
from pathlib import Path
from typing import Optional, Callable, Literal
from datetime import datetime

# Add clip-empire to path for imports
CLIP_EMPIRE_DIR = Path.home() / "clip-empire"
if str(CLIP_EMPIRE_DIR) not in sys.path:
    sys.path.insert(0, str(CLIP_EMPIRE_DIR))
    sys.path.insert(0, str(CLIP_EMPIRE_DIR / "src"))

# Load environment variables from clip-empire .env file
env_file = CLIP_EMPIRE_DIR / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

try:
    from content_generator import ContentGenerator
    from viral_video_editor import ViralVideoEditor
    from background_manager import BackgroundManager
except ImportError as e:
    print(f"Warning: Could not import clip-empire modules: {e}")
    ContentGenerator = None
    ViralVideoEditor = None
    BackgroundManager = None


VideoType = Literal["story", "commentary", "news"]
LOGGER = logging.getLogger("tiktok_manager.ai_video_generator")


class AIVideoGenerator:
    """Generate AI-powered TikTok videos"""

    def __init__(self, output_dir: Optional[Path] = None):
        if output_dir is None:
            output_dir = Path.home() / "TikTok_Videos"

        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dependencies_available = (
            ContentGenerator is not None and ViralVideoEditor is not None and BackgroundManager is not None
        )
        self.last_caption: str = ""
        self.last_transcript: str = ""
        self.last_audio_path: Optional[str] = None

        if not self.dependencies_available:
            LOGGER.warning(
                "clip-empire dependencies unavailable; AI generator will defer to backend fallback renderer."
            )

    def generate_video(
        self,
        theme: str = "scary",
        duration: int = 60,
        video_type: VideoType = "story",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """
        Generate an AI video with the specified parameters.

        Args:
            theme: Video theme (scary, dating, crazy, mystery, motivational, creepy, interesting)
            duration: Video duration in seconds (30, 60, 90, or 120)
            video_type: Type of video content (story, commentary, news)
            progress_callback: Optional callback for progress updates

        Returns:
            Path to the generated video file, or None if generation failed
        """
        self.last_caption = ""
        self.last_transcript = ""
        self.last_audio_path = None

        if not self.dependencies_available:
            if progress_callback:
                progress_callback("⚠️ AI generator dependencies unavailable. Using backend fallback renderer.")
            return None

        try:
            def log(message: str):
                try:
                    if progress_callback:
                        progress_callback(message)
                    else:
                        print(message)
                except BrokenPipeError:
                    pass

            log(f"🎬 Starting AI video generation...")
            log(f"   Theme: {theme}")
            log(f"   Duration: {duration}s")
            log(f"   Type: {video_type}")

            # Create organized folder structure
            today_folder = self.output_dir / datetime.now().strftime("%Y-%m-%d")
            today_folder.mkdir(parents=True, exist_ok=True)

            # Generate content based on video type
            log(f"📝 Generating AI {video_type} content...")
            generator = ContentGenerator()

            # Customize content generation based on type
            if video_type == "commentary":
                # For commentary, we might want different prompting
                # This could be extended later with specific commentary logic
                package = generator.create_content_package(theme, target_duration=duration)
            elif video_type == "news":
                # For news, we might want different style/tone
                # This could be extended later with specific news logic
                package = generator.create_content_package(theme, target_duration=duration)
            else:  # story (default)
                package = generator.create_content_package(theme, target_duration=duration)

            self.last_caption = str(package.get("caption") or "").strip()
            self.last_transcript = str(
                package.get("script")
                or package.get("story")
                or package.get("text")
                or self.last_caption
            ).strip()
            self.last_audio_path = str(package.get("audio_path") or "").strip() or None

            if not package.get("audio_path"):
                raise RuntimeError("Voiceover generation failed, cannot render video")

            log("✅ Content generated successfully")

            # Save caption to file for easy access
            caption_file = CLIP_EMPIRE_DIR / "generated_content" / "latest_caption.txt"
            caption_file.parent.mkdir(parents=True, exist_ok=True)
            caption_file.write_text(package['caption'])
            log(f"💬 Caption saved: {caption_file}")

            # Get a random unique background
            log("🎨 Selecting background video...")
            bg_manager = BackgroundManager()
            min_background_duration = max(30, min(int(duration), 60))
            background_video_path = bg_manager.get_background_for_theme(
                theme,
                min_duration=min_background_duration,
            )

            if not background_video_path or not Path(background_video_path).exists():
                log("📥 No backgrounds available, downloading...")
                bg_manager.download_all_backgrounds()
                background_video_path = bg_manager.get_background_for_theme(
                    theme,
                    min_duration=min_background_duration,
                )

                if not background_video_path:
                    raise FileNotFoundError("Failed to get background video")

            log(f"✅ Using background: {Path(background_video_path).name}")

            # Create video with organized naming: YYYY-MM-DD_HH-MM-SS.mp4
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_name = f"TikTok_AI_{video_type}_{timestamp}"
            output_path = today_folder / f"{output_name}.mp4"

            # Create video with captions
            log("🎬 Creating video with captions...")
            editor = ViralVideoEditor(output_dir=str(today_folder))
            video_path = editor.create_viral_video(
                audio_path=package['audio_path'],
                background_video=background_video_path,
                output_name=output_name,
                theme=theme,
                add_captions=True,
            )

            if not video_path or not Path(video_path).exists():
                raise RuntimeError("Video render failed")

            log(f"✅ Video created: {video_path}")
            log(f"📂 Location: {today_folder}")

            return video_path

        except Exception as e:
            LOGGER.exception("AI video generation failed: %s", e)
            try:
                if progress_callback:
                    progress_callback(f"Primary generator error: {e}")
                else:
                    print(f"Primary generator error: {e}")
            except BrokenPipeError:
                pass
            return None

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
        return ["story", "commentary", "news"]


if __name__ == "__main__":
    # Test the generator
    generator = AIVideoGenerator()
    video_path = generator.generate_video(
        theme="scary",
        duration=60,
        video_type="story",
    )
    if video_path:
        print(f"\n✅ Success! Video saved to: {video_path}")
    else:
        print("\n❌ Video generation failed")
