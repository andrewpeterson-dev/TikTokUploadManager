from __future__ import annotations

from typing import Optional

from .style_profiles import StyleProfile


def _escape_filter_path(path: Optional[str]) -> str:
    if not path:
        return ""
    value = str(path)
    value = value.replace("\\", "\\\\")
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    value = value.replace(",", r"\,")
    return value


def build_color_filter(profile: StyleProfile) -> str:
    """
    Build a deterministic color grading chain from style profile.

    This intentionally keeps effects subtle to avoid over-processed social media
    content while still improving contrast/saturation consistency.
    """
    lut_path = _escape_filter_path(str(profile.lut_path)) if profile.lut_path else ""
    contrast = 1.05
    saturation = 1.02
    brightness = 0.0
    gamma = 1.0
    curve = "0/0 0.07/0.05 0.5/0.5 0.94/0.98 1/1"

    if profile.color_grade == "cinematic":
        contrast = 1.08
        saturation = 0.96
        brightness = -0.01
        gamma = 1.02
        curve = "0/0 0.06/0.02 0.5/0.5 0.88/0.92 1/1"
    elif profile.color_grade == "vibrant":
        contrast = 1.12
        saturation = 1.18
        brightness = 0.01
        gamma = 0.98
        curve = "0/0 0.04/0.03 0.5/0.53 0.9/0.9 1/1"
    elif profile.color_grade == "dark":
        contrast = 1.12
        saturation = 0.88
        brightness = -0.025
        gamma = 1.06
        curve = "0/0 0.05/0 0.5/0.46 0.9/0.84 1/1"
    elif profile.color_grade == "clean":
        contrast = 1.04
        saturation = 1.04
        brightness = 0.0
        gamma = 0.99
        curve = "0/0 0.08/0.06 0.5/0.5 0.93/0.97 1/1"

    filters = [
        f"eq=contrast={contrast:.3f}:saturation={saturation:.3f}:brightness={brightness:.3f}:gamma={gamma:.3f}",
        f"curves=all='{curve}'",
    ]

    if profile.color_grade in {"cinematic", "dark"}:
        filters.append("vignette=PI/4")
        if profile.color_grade == "cinematic":
            filters.append("noise=alls=2:allf=t+u")

    if profile.music_intensity >= 0.6:
        filters.append("eq=gamma=1.01")

    if profile.motion_intensity > 0.7:
        filters.append("noise=alls=1:allf=u")

    if lut_path:
        filters.insert(0, f"lut3d='{lut_path}'")

    return ",".join(filters)
