"""Compatibility wrapper for short-form AI optimization entrypoints."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.shortform_ai_engine import (  # noqa: F401
    AESTHETIC_THRESHOLD,
    ENGAGEMENT_THRESHOLD,
    SHORTFORM_AI_ENABLED,
    API_KEY,
    optimize_shortform_video,
    optimize_shortform_video_async,
)

__all__ = [
    "API_KEY",
    "SHORTFORM_AI_ENABLED",
    "AESTHETIC_THRESHOLD",
    "ENGAGEMENT_THRESHOLD",
    "optimize_shortform_video",
    "optimize_shortform_video_async",
]
