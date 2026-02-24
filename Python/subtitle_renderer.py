#!/usr/bin/env python3
"""
Modern TikTok/Reels-style subtitle renderer.
Clean, minimal, word-by-word progressive reveal with soft shadows.
"""

from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.editor import ImageClip, CompositeVideoClip


class SubtitleRenderer:
    """Modern subtitle renderer with TikTok/Instagram Reels aesthetic."""

    def __init__(
        self,
        video_size: Tuple[int, int] = (1080, 1920),
        font_size: int = 26,  # ENHANCED: Slightly larger for better readability
        position_y_ratio: float = 0.82,  # ENHANCED: Better positioning
        shadow_blur: int = 4,  # ENHANCED: More pronounced shadow
        shadow_opacity: float = 0.35,  # ENHANCED: Stronger shadow for contrast
        words_per_phrase: int = 2,
        max_lines: int = 2,
        fade_duration: float = 0.06,  # ENHANCED: Smoother transitions
        use_blur_box: bool = True,  # ENHANCED: Enable blur box by default
    ):
        """
        Initialize subtitle renderer.

        Args:
            video_size: (width, height) - typically (1080, 1920) for 9:16
            font_size: Base font size in pixels (24-32 recommended)
            position_y_ratio: Vertical position (0.75-0.85 for lower third)
            shadow_blur: Gaussian blur radius for text shadow
            shadow_opacity: Shadow opacity (0.0-1.0)
            words_per_phrase: How many words to show at once
            max_lines: Maximum lines of text simultaneously
            fade_duration: Crossfade duration in seconds
            use_blur_box: Add semi-transparent blur box behind text
        """
        self.width, self.height = video_size
        self.font_size = font_size
        self.position_y = int(self.height * position_y_ratio)
        self.shadow_blur = shadow_blur
        self.shadow_opacity = shadow_opacity
        self.words_per_phrase = words_per_phrase
        self.max_lines = max_lines
        self.fade_duration = fade_duration
        self.use_blur_box = use_blur_box

        # Safe margins
        self.margin_x = 40
        self.margin_y = 40

        # Load font
        self.font = self._load_modern_font(self.font_size)

    def _load_modern_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Load a clean, modern sans-serif font."""
        font_candidates = [
            # Inter (if installed)
            "/System/Library/Fonts/Supplemental/Inter.ttc",
            # SF Pro Display (macOS system font)
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/SF-Pro-Display-Medium.otf",
            "/System/Library/Fonts/SF-Pro-Display-Semibold.otf",
            # Helvetica Neue
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
            # Arial as fallback
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]

        for font_path in font_candidates:
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue

        # Ultimate fallback
        return ImageFont.load_default()

    def _create_text_shadow(
        self, text: str, font: ImageFont.FreeTypeFont, blur_radius: int = 3
    ) -> Image.Image:
        """Create a soft blurred shadow for text."""
        # Create shadow layer (same size as main canvas)
        shadow_img = Image.new("RGBA", (self.width, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(shadow_img)

        # Draw black text for shadow
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Center the shadow
        x = (self.width - text_width) // 2
        y = (200 - text_height) // 2 + 2  # Slight downward offset

        draw.text((x, y), text, font=font, fill=(0, 0, 0, int(255 * self.shadow_opacity)))

        # Apply Gaussian blur
        shadow = shadow_img.filter(ImageFilter.GaussianBlur(blur_radius))

        return shadow

    def _create_subtitle_image(self, text: str) -> np.ndarray:
        """
        Create a single subtitle frame with modern styling.

        Returns RGBA numpy array.
        """
        # Create transparent canvas
        img = Image.new("RGBA", (self.width, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Get text dimensions
        bbox = draw.textbbox((0, 0), text, font=self.font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Ensure text fits within margins
        if text_width > self.width - (self.margin_x * 2):
            # Text too wide - need to wrap or shrink
            # For now, shrink font temporarily
            temp_font_size = self.font_size
            temp_font = self.font
            while text_width > self.width - (self.margin_x * 2) and temp_font_size > 18:
                temp_font_size -= 1
                temp_font = self._load_modern_font(temp_font_size)
                bbox = draw.textbbox((0, 0), text, font=temp_font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            self.font = temp_font

        # Center text horizontally
        x = (self.width - text_width) // 2
        y = (200 - text_height) // 2

        # Optional: Add semi-transparent blur box behind text
        if self.use_blur_box:
            pad_x = 20
            pad_y = 8
            box = [
                x - pad_x,
                y - pad_y,
                x + text_width + pad_x,
                y + text_height + pad_y,
            ]
            draw.rounded_rectangle(box, radius=8, fill=(0, 0, 0, int(255 * 0.6)))

        # Create shadow layer
        shadow = self._create_text_shadow(text, self.font, self.shadow_blur)

        # Composite shadow onto main image
        img = Image.alpha_composite(img, shadow)

        # Draw main text (pure white, no stroke)
        draw = ImageDraw.Draw(img)
        draw.text((x, y), text, font=self.font, fill=(255, 255, 255, 255))

        return np.array(img)

    def render_phrase(
        self, words: List[str], start: float, end: float
    ) -> Optional[ImageClip]:
        """
        Render a phrase (1-3 words) as a subtitle clip.

        Args:
            words: List of words to display together
            start: Start time in seconds
            end: End time in seconds

        Returns:
            ImageClip with subtitle, or None if invalid
        """
        if not words or start >= end:
            return None

        phrase_text = " ".join(words)
        duration = end - start

        try:
            # Create subtitle image
            subtitle_img = self._create_subtitle_image(phrase_text)

            # Create clip
            clip = (
                ImageClip(subtitle_img)
                .set_position(("center", self.position_y))
                .set_start(start)
                .set_duration(duration)
                .crossfadein(self.fade_duration)
                .crossfadeout(self.fade_duration)
            )

            return clip
        except Exception as e:
            print(f"⚠️ Failed to render phrase '{phrase_text}': {e}")
            return None

    def add_subtitles_to_video(
        self, video, captions: List[dict]
    ) -> CompositeVideoClip:
        """
        Add word-by-word or phrase-based subtitles to video.

        Args:
            video: VideoClip to add subtitles to
            captions: List of dicts with keys: 'word', 'start', 'end'

        Returns:
            CompositeVideoClip with subtitles overlaid
        """
        if not captions:
            return video

        # Group words into phrases
        phrases = self._group_into_phrases(captions)

        print(f"📝 Rendering {len(phrases)} subtitle phrases...")

        # Render each phrase
        subtitle_clips = []
        for i, phrase_data in enumerate(phrases):
            words = phrase_data["words"]
            start = phrase_data["start"]
            end = phrase_data["end"]

            clip = self.render_phrase(words, start, end)
            if clip:
                subtitle_clips.append(clip)

            if (i + 1) % 10 == 0:
                print(f"  ✓ Rendered {i + 1}/{len(phrases)} phrases")

        print(f"✅ Rendered {len(subtitle_clips)} subtitle clips")

        if subtitle_clips:
            return CompositeVideoClip([video] + subtitle_clips)
        return video

    def _group_into_phrases(self, captions: List[dict]) -> List[dict]:
        """
        Group word captions into phrases based on words_per_phrase setting.

        Args:
            captions: List of word-level caption dicts

        Returns:
            List of phrase dicts with keys: 'words', 'start', 'end'
        """
        phrases = []
        current_words = []
        current_start = None

        for caption in captions:
            word = caption.get("word", "").strip()
            if not word:
                continue

            if not current_words:
                current_start = caption["start"]

            current_words.append(word)

            # Break phrase on:
            # 1. Reached words_per_phrase limit
            # 2. Punctuation ending (period, exclamation, question)
            # 3. Comma/semicolon for natural pause
            should_break = (
                len(current_words) >= self.words_per_phrase
                or word.endswith((".", "!", "?"))
                or (len(current_words) >= 2 and word.endswith((",", ";")))
            )

            if should_break:
                phrases.append(
                    {
                        "words": current_words,
                        "start": current_start,
                        "end": caption["end"],
                    }
                )
                current_words = []
                current_start = None

        # Add remaining words
        if current_words:
            phrases.append(
                {
                    "words": current_words,
                    "start": current_start,
                    "end": captions[-1]["end"],
                }
            )

        return phrases


# Example usage
if __name__ == "__main__":
    # Demo subtitle rendering
    renderer = SubtitleRenderer(
        video_size=(1080, 1920),
        font_size=28,
        position_y_ratio=0.80,
        shadow_blur=3,
        shadow_opacity=0.25,
        words_per_phrase=2,
        use_blur_box=False,
    )

    # Create sample subtitle image
    sample_text = "This is a test subtitle"
    img = renderer._create_subtitle_image(sample_text)

    # Save as PNG for visual verification
    from PIL import Image as PILImage

    output = PILImage.fromarray(img)
    output.save("/tmp/subtitle_sample.png")
    print("✅ Sample subtitle saved to /tmp/subtitle_sample.png")
