from __future__ import annotations

from .style_profiles import StyleProfile


def _clamp(value: float, lower: float, upper: float) -> float:
    return lower if value < lower else upper if value > upper else value


def build_motion_filter(profile: StyleProfile) -> str:
    """
    Build deterministic camera motion filters from style profile.

    - Low intensity: slow cinematic drift only.
    - High intensity: micro zoom + subtle directional drift + periodic punch-in.
    """
    intensity = _clamp(float(profile.motion_intensity), 0.0, 1.0)
    if intensity > 0.5:
        # Micro zoom with punch-in curve: 1.03..~1.08
        zoom_expr = f"1.03 + {0.05 * intensity:.4f}*(0.5+0.5*sin(t*0.45))"
        drift_x = 18 + 20 * intensity
        drift_y = 12 + 12 * intensity
        freq_x = 0.06
        freq_y = 0.045
    else:
        # Cinematic drift only.
        zoom_expr = f"{1.0 + 0.015 * (intensity + 0.25):.4f}"
        drift_x = max(3.0, 6.0 * (1.0 + intensity))
        drift_y = max(2.0, 4.0 * (1.0 + intensity))
        freq_x = 0.02
        freq_y = 0.017

    # Keep crop movement bounded to avoid edge artifacts.
    x_expr = f"max(0,min(iw-1080,(iw-1080)/2 + {drift_x:.3f}*sin(t*{freq_x:.3f} + 0.12))"
    y_expr = f"max(0,min(ih-1920,(ih-1920)/2 + {drift_y:.3f}*cos(t*{freq_y:.3f} + 0.03))"

    # Punch-in every few seconds by increasing zoom slightly without randomness.
    punch = "1+0.02*(0.5+0.5*sin(t*0.9))"
    punch_expr = f"({zoom_expr})*{punch}"

    filter_chain = [
        f"scale='iw*{punch_expr}':'ih*{punch_expr}'",
        f"crop=1080:1920:{x_expr}:{y_expr}",
    ]

    return ",".join(filter_chain)
