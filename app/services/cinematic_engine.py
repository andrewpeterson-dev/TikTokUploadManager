from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

LOGGER = logging.getLogger("tiktok_manager.cinematic_engine")

# ---------------------------------------------------------------------------
# Theme colour-grading profiles (eq + colorbalance)
# ---------------------------------------------------------------------------

THEME_GRADES: Dict[str, Dict[str, str]] = {
    "scary": {
        "eq": "contrast=1.12:saturation=0.82:brightness=-0.02",
        "colorbalance": "bs=0.08:bm=0.04:bh=0.02:rs=-0.04:gs=-0.02",
    },
    "dating": {
        "eq": "contrast=1.04:saturation=1.12:brightness=0.03",
        "colorbalance": "rs=0.06:rm=0.03:gs=-0.02:bs=-0.04",
    },
    "crazy": {
        "eq": "contrast=1.14:saturation=1.18:brightness=0.01",
        "colorbalance": "rs=0.02:gs=0.01:bs=-0.02",
    },
    "mystery": {
        "eq": "contrast=1.08:saturation=0.88:brightness=-0.01",
        "colorbalance": "bs=0.06:gs=0.04:rs=-0.04:bm=0.03",
    },
    "motivational": {
        "eq": "contrast=1.06:saturation=1.08:brightness=0.04",
        "colorbalance": "rs=0.04:gs=0.02:bs=-0.06:rh=0.02",
    },
    "creepy": {
        "eq": "contrast=1.10:saturation=0.78:brightness=-0.03",
        "colorbalance": "gs=0.08:gm=0.04:rs=-0.04:bs=-0.02",
    },
    "interesting": {
        "eq": "contrast=1.06:saturation=1.04:brightness=0.01",
        "colorbalance": "bs=0.03:bm=0.02:rs=-0.01",
    },
}

EMPHASIS_WORDS = {
    "secret", "free", "fast", "mistake", "important", "truth", "must",
    "never", "best", "warning", "wait", "shocking", "crazy", "watch",
    "stop", "how", "why", "viral", "love", "hate", "fear", "angry",
    "excited", "insane", "wow", "epic", "unbelievable",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class CinematicConfig:
    theme: str = "interesting"
    color_grading: bool = True
    grain_strength: int = 6
    grain_temporal: bool = True
    vignette_angle: str = "PI/5"
    zoom_overscale: int = 32
    drift_amplitude_x: int = 16
    drift_amplitude_y: int = 10
    drift_freq_x: float = 0.15
    drift_freq_y: float = 0.20
    speed_factor: float = 1.0
    caption_font: str = "Futura"
    caption_font_size: int = 56
    accent_font_size: int = 60
    caption_outline: int = 4
    caption_shadow: int = 2
    caption_margin_bottom: int = 160
    caption_margin_sides: int = 80
    audio_loudnorm: bool = True
    audio_compressor: bool = True
    audio_reverb: bool = True
    crf: int = 20
    profile: str = "high"
    preset: str = "fast"
    fps: int = 30


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run(command: Sequence[str], *, context: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(list(command), capture_output=True, text=True)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "command failed").strip()
        raise RuntimeError(f"{context} failed: {message}")
    return result


def _probe_duration(video_path: Path) -> float:
    result = _run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        context="ffprobe duration",
    )
    try:
        return max(0.0, float((result.stdout or "0").strip()))
    except Exception:
        return 0.0


def _has_audio_stream(video_path: Path) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_type",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and "audio" in (result.stdout or "").lower()


def _escape_filter_path(path: Path) -> str:
    value = str(path)
    value = value.replace("\\", "\\\\")
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    value = value.replace(",", r"\,")
    return value


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[A-Za-z0-9']+", text.lower()) if t]


def _ass_ts(seconds: float) -> str:
    cs = int(max(0, round(seconds * 100)))
    hh = cs // 360000
    mm = (cs % 360000) // 6000
    ss = (cs % 6000) // 100
    cc = cs % 100
    return f"{hh}:{mm:02d}:{ss:02d}.{cc:02d}"


# ---------------------------------------------------------------------------
# Filter builders
# ---------------------------------------------------------------------------

def build_color_filters(config: CinematicConfig) -> str:
    if not config.color_grading:
        return ""
    grade = THEME_GRADES.get(config.theme.lower(), THEME_GRADES["interesting"])
    parts: List[str] = []
    if grade.get("eq"):
        parts.append(f"eq={grade['eq']}")
    if grade.get("colorbalance"):
        parts.append(f"colorbalance={grade['colorbalance']}")
    return ",".join(parts)


def build_grain_filter(config: CinematicConfig) -> str:
    if config.grain_strength <= 0:
        return ""
    flags = "t+u" if config.grain_temporal else "u"
    return f"noise=alls={config.grain_strength}:allf={flags}"


def build_vignette_filter(config: CinematicConfig) -> str:
    if not config.vignette_angle:
        return ""
    return f"vignette=angle={config.vignette_angle}"


def build_motion_filters(config: CinematicConfig) -> str:
    if config.zoom_overscale <= 0:
        return ""

    overscale_y = int(config.zoom_overscale * (1920 / 1080))
    if overscale_y % 2 != 0:
        overscale_y += 1

    w = 1080 + config.zoom_overscale
    if w % 2 != 0:
        w += 1
    h = 1920 + overscale_y

    center_x = (w - 1080) // 2
    center_y = (h - 1920) // 2

    ax = config.drift_amplitude_x
    ay = config.drift_amplitude_y
    fx = config.drift_freq_x
    fy = config.drift_freq_y

    scale = f"scale={w}:{h}:flags=lanczos"
    crop = (
        f"crop=1080:1920:"
        f"'{ax}*sin(t*{fx})+{center_x}':"
        f"'{ay}*cos(t*{fy})+{center_y}'"
    )
    return f"{scale},{crop}"


def build_audio_chain(config: CinematicConfig) -> str:
    parts: List[str] = []
    if config.audio_loudnorm:
        parts.append("loudnorm=I=-14:LRA=11:TP=-1.5")
    if config.audio_compressor:
        parts.append("acompressor=threshold=-20dB:ratio=2.2:attack=10:release=120")
    if config.audio_reverb:
        parts.append("aecho=0.8:0.25:35:0.025")
    return ",".join(parts)


# ---------------------------------------------------------------------------
# Premium caption builder (ASS)
# ---------------------------------------------------------------------------

def _chunk_words(text: str) -> List[List[str]]:
    words = text.split()
    chunks: List[List[str]] = []
    i = 0
    while i < len(words):
        size = 3 if (i // 3) % 2 == 0 else 2
        remaining = len(words) - i
        if remaining <= 2:
            size = remaining
        chunk = words[i : i + size]
        if chunk:
            chunks.append(chunk)
        i += size
    return chunks


def build_caption_ass(
    caption: str,
    duration_seconds: float,
    output_path: Path,
    config: CinematicConfig,
) -> Optional[Path]:
    text = _normalize_space(caption)
    if not text:
        return None

    tokens = _tokenize(text)
    if len(tokens) > 90 or len(text) > 420:
        return None

    chunks = _chunk_words(text)
    if not chunks:
        return None

    font = config.caption_font
    sz = config.caption_font_size
    accent_sz = config.accent_font_size
    outline = config.caption_outline
    shadow = config.caption_shadow
    mv = config.caption_margin_bottom
    mh = config.caption_margin_sides

    # &HAABBGGRR — cyan = R:00 G:FF B:FF → &H00FFFF00
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Caption,{font},{sz},&H00FFFFFF,&H00FFFFFF,&H00101010,&H64000000,"
        f"1,0,0,0,100,100,0,0,1,{outline},{shadow},2,{mh},{mh},{mv},1\n"
        f"Style: CaptionAccent,{font},{accent_sz},&H00FFFF00,&H00FFFFFF,&H00101010,&H64000000,"
        f"1,0,0,0,105,105,0,0,1,{outline},{shadow},2,{mh},{mh},{mv},1\n\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )

    min_slot = 0.35
    max_slot = 1.2
    slot = max(min_slot, min(max_slot, duration_seconds / max(1, len(chunks))))

    lines: List[str] = []
    current = 0.08

    for chunk in chunks:
        start = current
        end = min(duration_seconds, start + slot)
        current = end

        styled_words: List[str] = []
        for word in chunk:
            clean = word.lower().rstrip(".,!?;:'\"")
            if clean in EMPHASIS_WORDS:
                styled_words.append(
                    "{\\rCaptionAccent}{\\t(0,150,\\fscx110\\fscy110)}"
                    + word
                    + "{\\r}"
                )
            else:
                styled_words.append(word)

        text_payload = "{\\fad(60,60)}" + " ".join(styled_words)
        lines.append(
            f"Dialogue: 0,{_ass_ts(start)},{_ass_ts(end)},Caption,,0,0,0,,{text_payload}"
        )

        if current >= duration_seconds:
            break

    output_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Filter complex assembly
# ---------------------------------------------------------------------------

def build_filter_complex(
    config: CinematicConfig,
    *,
    has_audio: bool,
    ass_path: Optional[Path] = None,
) -> tuple[str, str, str]:
    """
    Assemble all filter modules into one filter_complex string.

    Returns ``(filter_complex, video_output_label, audio_output_label)``.
    """
    segments: List[str] = [
        # Background
        "[1:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=12:6[bg]",
        # Source blur for blend
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=30:15[srcblur]",
        # Blend
        "[bg][srcblur]blend=all_mode='overlay':all_opacity=0.35[base]",
        # Foreground scale
        "[0:v]scale='if(gt(iw,1080),1080,iw)':"
        "'if(gt(ih,1728),1728,ih)':force_original_aspect_ratio=decrease,"
        "setsar=1[fg]",
        # Overlay
        "[base][fg]overlay=(W-w)/2:(H-h)/2:shortest=1[comp]",
    ]

    # Post-compositing chain ------------------------------------------------
    post: List[str] = []

    # 1) Speed
    if abs(config.speed_factor - 1.0) > 0.001:
        post.append(f"setpts={1.0 / config.speed_factor:.6f}*PTS")

    # 2) Color grading
    color = build_color_filters(config)
    if color:
        post.append(color)

    # 3) Motion (overscale + animated crop)
    motion = build_motion_filters(config)
    if motion:
        post.append(motion)

    # 4) Vignette (on final-size frame)
    vignette = build_vignette_filter(config)
    if vignette:
        post.append(vignette)

    # 5) Film grain (on final-size frame)
    grain = build_grain_filter(config)
    if grain:
        post.append(grain)

    # 6) Subtitles (on top of everything)
    if ass_path:
        post.append(f"subtitles='{_escape_filter_path(ass_path)}'")

    if post:
        segments.append(f"[comp]{','.join(post)}[vout]")
        video_label = "[vout]"
    else:
        video_label = "[comp]"

    # Audio chain -----------------------------------------------------------
    audio_label = "0:a?"
    if has_audio:
        audio_parts: List[str] = []
        if abs(config.speed_factor - 1.0) > 0.001:
            audio_parts.append(f"atempo={config.speed_factor:.4f}")
        chain = build_audio_chain(config)
        if chain:
            audio_parts.append(chain)
        if audio_parts:
            segments.append(f"[0:a]{','.join(audio_parts)}[aout]")
            audio_label = "[aout]"

    return ";".join(segments), video_label, audio_label


# ---------------------------------------------------------------------------
# Auto-tune config from analysis data
# ---------------------------------------------------------------------------

def config_from_analysis(
    theme: str,
    script_profile: Dict[str, Any],
    frame_summary: Dict[str, Any],
) -> CinematicConfig:
    config = CinematicConfig(theme=theme)

    high_energy = bool(script_profile.get("high_energy"))
    mean_luma = float(frame_summary.get("mean_luma", 128))

    if high_energy:
        config.grain_strength = 4
        config.zoom_overscale = 40
        config.drift_amplitude_x = 20
        config.drift_amplitude_y = 14
        config.speed_factor = 1.02
    else:
        config.grain_strength = 8
        config.zoom_overscale = 28
        config.drift_amplitude_x = 12
        config.drift_amplitude_y = 8
        config.drift_freq_x = 0.10
        config.drift_freq_y = 0.14

    if mean_luma < 80:
        config.vignette_angle = "PI/4"

    return config


# ---------------------------------------------------------------------------
# Single-pass cinematic render
# ---------------------------------------------------------------------------

def cinematic_render(
    source_path: Path,
    output_path: Path,
    background_path: Path,
    caption: str,
    config: CinematicConfig,
) -> Path:
    """
    Render a cinematic short-form video in a single ffmpeg pass.

    Combines background compositing, theme colour grading, organic motion,
    film grain, vignette, premium captions, and broadcast audio processing
    into one ``filter_complex`` call — zero re-encoding degradation.
    """
    if not source_path.exists():
        raise RuntimeError(f"Source video not found: {source_path}")
    if not background_path.exists():
        raise RuntimeError(f"Background asset not found: {background_path}")

    duration = _probe_duration(source_path)
    if duration <= 0:
        raise RuntimeError("Source video has invalid duration.")

    has_audio = _has_audio_stream(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Caption ASS
    ass_path: Optional[Path] = None
    if caption and caption.strip():
        ass_path = build_caption_ass(
            caption,
            duration,
            Path(tempfile.gettempdir()) / f"cinematic_{output_path.stem}.ass",
            config,
        )

    # Assemble filter complex
    filter_complex, video_label, audio_label = build_filter_complex(
        config, has_audio=has_audio, ass_path=ass_path,
    )

    # ffmpeg command
    cmd: List[str] = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source_path),
    ]

    bg_is_image = background_path.suffix.lower() in IMAGE_EXTENSIONS
    if bg_is_image:
        cmd += ["-loop", "1", "-i", str(background_path)]
    else:
        cmd += ["-stream_loop", "-1", "-i", str(background_path)]

    cmd += [
        "-filter_complex", filter_complex,
        "-map", video_label,
        "-map", audio_label,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264",
        "-profile:v", config.profile,
        "-preset", config.preset,
        "-crf", str(config.crf),
        "-pix_fmt", "yuv420p",
        "-r", str(config.fps),
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-movflags", "+faststart",
        "-shortest",
        str(output_path),
    ]

    LOGGER.info(
        "Cinematic render: theme=%s grain=%s zoom=%s speed=%.3f",
        config.theme, config.grain_strength, config.zoom_overscale, config.speed_factor,
    )

    result = subprocess.run(cmd, capture_output=True, text=True)

    if ass_path and ass_path.exists():
        ass_path.unlink(missing_ok=True)

    if result.returncode != 0:
        message = (result.stderr or result.stdout or "ffmpeg error").strip()
        raise RuntimeError(f"Cinematic render failed: {message}")

    # Marker so shortform engine knows to skip re-processing
    output_path.with_suffix(".cinematic_done").write_text("1", encoding="utf-8")

    LOGGER.info("Cinematic render complete: %s", output_path)
    return output_path
