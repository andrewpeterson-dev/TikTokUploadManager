from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, Iterable, Literal, Optional


EnergyLevel = Literal["low", "medium", "high"]
ColorGrade = Literal["cinematic", "vibrant", "dark", "clean"]
CaptionStyle = Literal["minimal", "dynamic", "bold"]
BackgroundType = Literal["gta", "subway", "cinematic", "blur", "none"]
VideoType = Literal[
    "story",
    "commentary",
    "news",
    "podcast",
    "story_narration",
    "motivational",
    "satisfying",
    "educational",
    "trend",
]


@dataclass(frozen=True)
class StyleProfile:
    """Profile used by the style intelligence pipeline."""

    energy_level: EnergyLevel
    color_grade: ColorGrade
    caption_style: CaptionStyle
    motion_intensity: float
    music_intensity: float
    background_type: BackgroundType
    lut_path: Optional[Path] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "motion_intensity", max(0.0, min(1.0, float(self.motion_intensity))))
        object.__setattr__(self, "music_intensity", max(0.0, min(1.0, float(self.music_intensity))))
        if self.lut_path is not None and not str(self.lut_path).strip():
            object.__setattr__(self, "lut_path", None)


_STYLE_LIBRARY: Dict[str, StyleProfile] = {
    # Existing app-facing types
    "story": StyleProfile(
        energy_level="low",
        color_grade="clean",
        caption_style="minimal",
        motion_intensity=0.22,
        music_intensity=0.30,
        background_type="none",
    ),
    "commentary": StyleProfile(
        energy_level="medium",
        color_grade="cinematic",
        caption_style="minimal",
        motion_intensity=0.35,
        music_intensity=0.28,
        background_type="cinematic",
    ),
    "news": StyleProfile(
        energy_level="high",
        color_grade="vibrant",
        caption_style="dynamic",
        motion_intensity=0.68,
        music_intensity=0.62,
        background_type="subway",
    ),

    # Requested professional profile set
    "podcast": StyleProfile(
        energy_level="low",
        color_grade="clean",
        caption_style="minimal",
        motion_intensity=0.24,
        music_intensity=0.18,
        background_type="blur",
    ),
    "story_narration": StyleProfile(
        energy_level="low",
        color_grade="cinematic",
        caption_style="minimal",
        motion_intensity=0.28,
        music_intensity=0.22,
        background_type="cinematic",
    ),
    "motivational": StyleProfile(
        energy_level="high",
        color_grade="vibrant",
        caption_style="bold",
        motion_intensity=0.84,
        music_intensity=0.82,
        background_type="gta",
    ),
    "satisfying": StyleProfile(
        energy_level="medium",
        color_grade="clean",
        caption_style="minimal",
        motion_intensity=0.30,
        music_intensity=0.25,
        background_type="blur",
    ),
    "educational": StyleProfile(
        energy_level="medium",
        color_grade="clean",
        caption_style="dynamic",
        motion_intensity=0.42,
        music_intensity=0.30,
        background_type="cinematic",
    ),
    "trend": StyleProfile(
        energy_level="high",
        color_grade="vibrant",
        caption_style="bold",
        motion_intensity=0.90,
        music_intensity=0.88,
        background_type="gta",
    ),
}

_TYPE_ALIASES = {
    "story_narrative": "story_narration",
    "storytelling": "story_narration",
    "short_story": "story_narration",
    "background": "satisfying",
    "backgrounds": "satisfying",
    "high_energy_trend": "trend",
    "trend_clip": "trend",
    "trending": "trend",
    "podcasts": "podcast",
}

_THEME_HINTS: Dict[str, str] = {
    "motivational": "motivational",
    "inspiration": "motivational",
    "motivation": "motivational",
    "story": "story_narration",
    "narration": "story_narration",
    "podcast": "podcast",
    "education": "educational",
    "educational": "educational",
    "satisfying": "satisfying",
    "trend": "trend",
    "trending": "trend",
}


def _normalize_video_type(video_type: str) -> str:
    value = (video_type or "").strip().lower().replace(" ", "_")
    return _TYPE_ALIASES.get(value, value or "story")


def _best_match_from_theme(theme: str) -> Optional[str]:
    normalized = (theme or "").strip().lower()
    for hint, mapped in _THEME_HINTS.items():
        if hint in normalized:
            return mapped
    return None


def get_style_profile(video_type: str, theme: str = "") -> StyleProfile:
    """Return a style profile for the requested video type/theme."""
    resolved = _normalize_video_type(video_type)
    theme_profile = _best_match_from_theme(theme)

    if theme_profile and theme_profile in _STYLE_LIBRARY:
        if theme_profile != resolved and resolved in {"story", "commentary", "news"}:
            resolved = theme_profile

    profile = _STYLE_LIBRARY.get(theme_profile or resolved)
    if profile is None:
        profile = _STYLE_LIBRARY.get(resolved, _STYLE_LIBRARY["story"])
    return replace(profile)


def get_available_video_types() -> list[str]:
    return list(_STYLE_LIBRARY.keys())


def get_lut_path(profile: StyleProfile) -> Optional[Path]:
    if profile.lut_path and profile.lut_path.exists():
        return profile.lut_path
    return None


def allowed_video_types() -> Iterable[str]:
    return sorted(set(_STYLE_LIBRARY.keys()))
