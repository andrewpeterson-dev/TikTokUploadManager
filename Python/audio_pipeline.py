#!/usr/bin/env python3
"""
Audio pipeline with background music, ducking, and normalization.
"""

import numpy as np
from moviepy.editor import AudioFileClip, CompositeAudioClip, concatenate_audioclips
from pathlib import Path
from typing import Optional


class AudioPipeline:
    """Professional audio mixing and normalization."""

    def __init__(
        self,
        target_lufs: float = -14.0,  # ENHANCED: TikTok optimal (-14 LUFS)
        duck_amount_db: float = -18.0,  # ENHANCED: More aggressive ducking
        music_fade_duration: float = 1.2,  # ENHANCED: Smoother fades
    ):
        """
        Initialize PREMIUM audio pipeline.

        Args:
            target_lufs: Target loudness in LUFS (TikTok optimal: -14 LUFS)
            duck_amount_db: How much to reduce music during speech (-15 to -25)
            music_fade_duration: Fade in/out duration in seconds
        """
        self.target_lufs = target_lufs
        self.duck_amount_db = duck_amount_db
        self.music_fade_duration = music_fade_duration

    def normalize_audio(
        self, audio: AudioFileClip, target_db: float = -3.0
    ) -> AudioFileClip:
        """
        Normalize audio to target dB level.

        Args:
            audio: Input audio clip
            target_db: Target peak level in dB

        Returns:
            Normalized audio clip
        """
        try:
            # Get audio array
            audio_array = audio.to_soundarray()

            # Calculate current peak level
            current_peak = np.max(np.abs(audio_array))
            if current_peak == 0:
                return audio

            # Calculate required gain
            target_amplitude = 10 ** (target_db / 20.0)
            gain = target_amplitude / current_peak

            # Apply gain (with safety limit)
            gain = min(gain, 3.0)  # Max 3x amplification

            return audio.volumex(gain)

        except Exception as e:
            print(f"⚠️ Audio normalization failed: {e}")
            return audio

    def apply_lufs_normalization(
        self, audio: AudioFileClip, target_lufs: float = None
    ) -> AudioFileClip:
        """
        Normalize audio to target LUFS (perceived loudness).

        Note: This is a simplified approximation. For true LUFS,
        would need pyloudnorm library.

        Args:
            audio: Input audio clip
            target_lufs: Target LUFS level

        Returns:
            Normalized audio clip
        """
        if target_lufs is None:
            target_lufs = self.target_lufs

        # Approximate LUFS with RMS-based normalization
        # LUFS roughly corresponds to -23 LUFS = 0 dBFS RMS
        target_db = target_lufs + 23.0  # Convert LUFS to approximate dB

        return self.normalize_audio(audio, target_db)

    def create_ducked_music(
        self,
        music: AudioFileClip,
        narration: AudioFileClip,
        duck_amount_db: float = None,
    ) -> AudioFileClip:
        """
        Apply auto-ducking: reduce music volume when narration plays.

        Args:
            music: Background music clip
            narration: Narration audio clip
            duck_amount_db: Reduction in dB (negative value)

        Returns:
            Music clip with ducking applied
        """
        if duck_amount_db is None:
            duck_amount_db = self.duck_amount_db

        try:
            # Calculate ducking multiplier
            duck_multiplier = 10 ** (duck_amount_db / 20.0)

            # Detect where narration is playing
            # Simple approach: duck entire duration where narration exists
            def volume_at_time(t):
                """Calculate volume multiplier at time t."""
                # If narration is playing at this time, duck
                if 0 <= t < narration.duration:
                    # Check if narration has audio at this time
                    try:
                        narration_frame = narration.get_frame(t)
                        if np.max(np.abs(narration_frame)) > 0.001:
                            return duck_multiplier
                    except:
                        pass
                return 1.0

            # Apply volume envelope
            ducked = music.fl(lambda gf, t: gf(t) * volume_at_time(t), apply_to=['audio'])
            return ducked

        except Exception as e:
            print(f"⚠️ Audio ducking failed: {e}")
            # Fallback: just reduce music volume globally
            return music.volumex(duck_multiplier)

    def add_fades(
        self,
        audio: AudioFileClip,
        fade_in: float = None,
        fade_out: float = None,
    ) -> AudioFileClip:
        """
        Add fade in/out to audio.

        Args:
            audio: Input audio clip
            fade_in: Fade in duration (uses music_fade_duration if None)
            fade_out: Fade out duration (uses music_fade_duration if None)

        Returns:
            Audio with fades applied
        """
        if fade_in is None:
            fade_in = self.music_fade_duration
        if fade_out is None:
            fade_out = self.music_fade_duration

        try:
            faded = audio.audio_fadeout(fade_out)
            faded = faded.audio_fadein(fade_in)
            return faded
        except Exception as e:
            print(f"⚠️ Fade application failed: {e}")
            return audio

    def loop_music(
        self, music_path: str, target_duration: float
    ) -> Optional[AudioFileClip]:
        """
        Loop background music to match target duration.

        Args:
            music_path: Path to music file
            target_duration: Desired total duration

        Returns:
            Looped music clip, or None if failed
        """
        try:
            music = AudioFileClip(music_path)

            if music.duration >= target_duration:
                # Trim to exact duration
                return music.subclip(0, target_duration)
            else:
                # Loop to fill duration
                n_loops = int(target_duration / music.duration) + 1
                looped = concatenate_audioclips([music] * n_loops)
                return looped.subclip(0, target_duration)

        except Exception as e:
            print(f"⚠️ Music looping failed: {e}")
            return None

    def add_background_music(
        self,
        narration: AudioFileClip,
        music_path: str,
        music_volume: float = 0.15,
    ) -> Optional[AudioFileClip]:
        """
        Add background music with auto-ducking to narration.

        Args:
            narration: Main narration audio
            music_path: Path to background music file
            music_volume: Base music volume (0.0-1.0)

        Returns:
            Mixed audio with narration + ducked music
        """
        try:
            print(f"🎵 Loading background music: {music_path}")

            # Loop music to match narration duration
            music = self.loop_music(music_path, narration.duration)
            if not music:
                return narration

            # Reduce music to base volume
            music = music.volumex(music_volume)

            # Add fades
            music = self.add_fades(music)

            # Apply ducking
            print(f"🎚️ Applying auto-ducking ({self.duck_amount_db} dB)...")
            ducked_music = self.create_ducked_music(music, narration)

            # Normalize narration
            print("🔊 Normalizing narration...")
            narration = self.normalize_audio(narration, target_db=-3.0)

            # Composite audio
            print("🎧 Mixing audio tracks...")
            mixed = CompositeAudioClip([narration, ducked_music])

            # Final normalization
            mixed = self.apply_lufs_normalization(mixed)

            print("✅ Background music added successfully")
            return mixed

        except Exception as e:
            print(f"⚠️ Background music addition failed: {e}")
            import traceback
            traceback.print_exc()
            return narration

    def get_music_file(self, theme: str = "scary") -> Optional[str]:
        """
        Get appropriate background music file for theme.

        Args:
            theme: Content theme

        Returns:
            Path to music file, or None if not found
        """
        # TODO: Add actual music files to project
        # For now, return None to skip music
        music_dir = Path("music")
        if not music_dir.exists():
            return None

        # Theme-specific music mapping
        music_map = {
            "scary": "dark_ambient.mp3",
            "dating": "soft_piano.mp3",
            "crazy": "energetic_beat.mp3",
            "mystery": "suspense_strings.mp3",
            "motivational": "uplifting_synth.mp3",
            "creepy": "eerie_soundscape.mp3",
            "interesting": "curious_melody.mp3",
        }

        music_file = music_dir / music_map.get(theme, "ambient.mp3")
        if music_file.exists():
            return str(music_file)

        # Fallback: any music file in directory
        music_files = list(music_dir.glob("*.mp3"))
        if music_files:
            return str(music_files[0])

        return None


# Preset configurations
AUDIO_PRESETS = {
    "standard": {
        "target_lufs": -30.0,
        "duck_amount_db": -20.0,
        "music_fade_duration": 0.8,
    },
    "aggressive_duck": {
        "target_lufs": -30.0,
        "duck_amount_db": -24.0,
        "music_fade_duration": 0.5,
    },
    "subtle_duck": {
        "target_lufs": -30.0,
        "duck_amount_db": -15.0,
        "music_fade_duration": 1.0,
    },
    "no_music": {
        "target_lufs": -30.0,
        "duck_amount_db": 0.0,
        "music_fade_duration": 0.0,
    },
}


def get_audio_pipeline(preset: str = "standard") -> AudioPipeline:
    """
    Get an AudioPipeline with preset configuration.

    Args:
        preset: "standard", "aggressive_duck", "subtle_duck", or "no_music"

    Returns:
        Configured AudioPipeline instance
    """
    config = AUDIO_PRESETS.get(preset, AUDIO_PRESETS["standard"])
    return AudioPipeline(**config)


if __name__ == "__main__":
    # Demo usage
    print("Audio Pipeline - Available Presets:")
    for name, config in AUDIO_PRESETS.items():
        print(f"\n{name.upper()}:")
        for key, value in config.items():
            print(f"  {key}: {value}")
