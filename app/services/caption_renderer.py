from __future__ import annotations

import re
from pathlib import Path
from typing import List, Sequence, Tuple

from .style_profiles import CaptionStyle, StyleProfile


EMPHASIS_WORDS = {
    "secret",
    "free",
    "fast",
    "mistake",
    "important",
    "truth",
    "never",
    "best",
    "watch",
    "shocking",
    "crazy",
    "stop",
    "how",
    "why",
}

STYLE_BY_PROFILE = {
    "minimal": {
        "font": "Arial",
        "size": 46,
        "accent_size": 50,
        "outline": 3,
        "shadow": 2,
        "margin_v": 180,
        "accent_colors": ("&H00FFFFFF&", "&H0010A0FF&", "&H00FFA500&"),
        "duration_scale": 1.12,
    },
    "dynamic": {
        "font": "Arial",
        "size": 50,
        "accent_size": 56,
        "outline": 3,
        "shadow": 2,
        "margin_v": 170,
        "accent_colors": ("&H00FFFFFF&", "&H0000FFFF&", "&H00FFD700&"),
        "duration_scale": 1.0,
    },
    "bold": {
        "font": "Arial",
        "size": 52,
        "accent_size": 58,
        "outline": 4,
        "shadow": 3,
        "margin_v": 150,
        "accent_colors": ("&H00FFFFFF&", "&H0000FFFF&", "&H00FF4E42&"),
        "duration_scale": 0.95,
    },
}


def _normalize_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    return normalized


def _tokenize(text: str) -> List[str]:
    normalized_text = re.findall(r"[A-Za-z0-9']+", text.lower())
    return [token for token in normalized_text if token]


def chunk_transcript_for_subtitle(transcript: str, *, min_words: int = 2, max_words: int = 4) -> List[str]:
    words = _tokenize(_normalize_text(transcript))
    chunks: List[str] = []

    if not words:
        return chunks

    i = 0
    while i < len(words):
        remaining = len(words) - i
        if remaining <= max_words:
            size = max(min_words, remaining)
        elif i % 2 == 0:
            size = max_words
        else:
            size = 3 if remaining > 3 else max_words
        chunk = words[i : i + size]
        chunks.append(" ".join(chunk))
        i += size

    return chunks


def _format_timestamp(seconds: float) -> str:
    centiseconds = int(max(0, round(float(seconds) * 100)))
    h = centiseconds // 360000
    m = (centiseconds % 360000) // 6000
    s = (centiseconds % 6000) // 100
    cs = centiseconds % 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _styled_word(word: str) -> str:
    token = re.sub(r"[^\w']+", "", word.lower())
    if token in EMPHASIS_WORDS:
        return f"{{\\c&H00FFFF00&}}{word}{{\\r}}"
    return word


def build_caption_ass(
    transcript: str,
    duration_seconds: float,
    output_path: Path,
    profile: StyleProfile,
    style: CaptionStyle = "minimal",
) -> Path:
    text = _normalize_text(transcript)
    if not text:
        raise ValueError("Caption text is empty.")

    style_cfg = STYLE_BY_PROFILE.get(style, STYLE_BY_PROFILE["minimal"])
    chunks = chunk_transcript_for_subtitle(text, min_words=2, max_words=4)
    if not chunks:
        raise ValueError("No caption chunks generated.")

    font = style_cfg["font"]
    base_size = int(style_cfg["size"])
    accent_size = int(style_cfg["accent_size"])
    outline = int(style_cfg["outline"])
    shadow = int(style_cfg["shadow"])
    margin_v = int(style_cfg["margin_v"])
    primary, accent, accent2 = style_cfg["accent_colors"]
    duration_scale = float(style_cfg["duration_scale"])

    slot = max(0.30, min(1.15, (max(duration_seconds, 0.2) / max(1, len(chunks))) * duration_scale))
    lines: List[str] = []

    cursor = 0.08
    color_cycle = [primary, accent, accent2]
    for idx, chunk in enumerate(chunks[:8]):
        start = cursor
        end = min(max(duration_seconds, 0.3), cursor + slot)
        cursor = end

        words = chunk.split()
        colored = " ".join(_styled_word(word) for word in words)
        color = color_cycle[idx % len(color_cycle)]
        line = (
            f"{{\\c{color}}}"
            f"{{\\fs{accent_size}}}{{\\rCaption{idx % 2}}}{colored}"
        )
        lines.append(
            "Dialogue: 0,"
            f"{_format_timestamp(start)},{_format_timestamp(end)},Caption,,0,0,{margin_v},,"
            + "{\\an2}{\\fad(80,120)}"
            + f"{{\\fscx100\\fscy100\\blur2\\bord{outline}\\shad{shadow}\\fn{font}\\fs{base_size}}}{line}"
        )

        if cursor >= duration_seconds:
            break

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
        "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Caption,Arial,{base_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H64000000,1,0,0,0,100,100,0,0,1,{outline},{shadow},2,80,80,{margin_v},1\n"
        f"Style: Caption1,{font},{accent_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H64000000,1,0,0,0,100,100,0,0,1,{outline},{shadow},2,80,80,{margin_v},1\n"
        f"Style: Caption0,{font},{base_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H64000000,1,0,0,0,100,100,0,0,1,{outline},{shadow},2,80,80,{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )

    output_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return output_path
