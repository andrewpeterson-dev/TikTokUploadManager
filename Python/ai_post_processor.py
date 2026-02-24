"""Compatibility wrapper for AI post-processing entrypoints."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.ai_post_processor import (  # noqa: F401
    AI_ENHANCEMENT,
    AESTHETIC_THRESHOLD,
    API_KEY,
    enhance_video,
    enhance_video_async,
)

__all__ = [
    "API_KEY",
    "AI_ENHANCEMENT",
    "AESTHETIC_THRESHOLD",
    "enhance_video",
    "enhance_video_async",
]
