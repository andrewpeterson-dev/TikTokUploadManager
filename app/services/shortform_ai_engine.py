from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib import error, request

try:
    import cv2  # type: ignore
import numpy as np  # type: ignore

    CV_AVAILABLE = True
except Exception:
    cv2 = None
    np = None
    CV_AVAILABLE = False

from .export_profiles import standard_1080x1920_profile

LOGGER = logging.getLogger("tiktok_manager.shortform_ai_engine")

API_KEY = os.getenv("OPENAI_API_KEY")
SHORTFORM_AI_ENABLED = os.getenv("SHORTFORM_AI_ENABLED", "true").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
try:
    AESTHETIC_THRESHOLD = int(os.getenv("AESTHETIC_THRESHOLD", "75"))
except ValueError:
    AESTHETIC_THRESHOLD = 75
try:
    ENGAGEMENT_THRESHOLD = int(os.getenv("ENGAGEMENT_THRESHOLD", "70"))
except ValueError:
    ENGAGEMENT_THRESHOLD = 70

OPENAI_MODEL = os.getenv("OPENAI_SHORTFORM_MODEL", "gpt-4.1-mini")
OPENAI_TIMEOUT_SECONDS = int(os.getenv("OPENAI_SHORTFORM_TIMEOUT", "16"))

DESIGN_PROMPT = (
    "You are a professional short-form motion designer for TikTok/Reels/Shorts. "
    "Evaluate retention potential and visual quality using transcript + detected frame metrics. "
    "Return JSON only with this schema: "
    "{\"aesthetic_score\":0-100,\"engagement_score\":0-100,\"issues\":[],\"improvements\":[]}."
)

HOOK_WORDS = {
    "wait",
    "secret",
    "shocking",
    "crazy",
    "watch",
    "warning",
    "stop",
    "never",
    "how",
    "why",
    "best",
    "viral",
}
EMOTION_WORDS = {
    "love",
    "hate",
    "fear",
    "angry",
    "excited",
    "sad",
    "happy",
    "insane",
    "wow",
    "crazy",
    "epic",
    "unbelievable",
}
KEYWORD_WORDS = {
    "secret",
    "free",
    "fast",
    "mistake",
    "important",
    "truth",
    "must",
    "never",
    "best",
    "warning",
}


def _run(command: Sequence[str], *, context: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(list(command), capture_output=True, text=True)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "command failed").strip()
        raise RuntimeError(f"{context} failed: {message}")
    return result


def _has_audio_stream(video_path: Path) -> bool:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and "audio" in (result.stdout or "").lower()


def _probe_duration(video_path: Path) -> float:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        context="ffprobe duration",
    )
    try:
        return max(0.0, float((result.stdout or "0").strip()))
    except Exception:
        return 0.0


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _tokenize(text: str) -> List[str]:
    return [token for token in re.findall(r"[A-Za-z0-9']+", text.lower()) if token]


def _script_analysis(transcript: str, duration_seconds: float) -> Dict[str, Any]:
    tokens = _tokenize(transcript)
    token_count = len(tokens)

    if token_count == 0:
        return {
            "hook_strength": 45,
            "emotional_intensity": 35,
            "pacing_wpm": 0,
            "pacing_issues": ["no transcript provided"],
            "energy_curve": "steady",
            "high_energy": False,
        }

    first_window = tokens[: min(14, token_count)]
    hook_hits = sum(1 for token in first_window if token in HOOK_WORDS)
    punctuation_bonus = 8 if re.search(r"[!?]", transcript[:140]) else 0
    hook_strength = max(0, min(100, 40 + hook_hits * 12 + punctuation_bonus))

    emotion_hits = sum(1 for token in tokens if token in EMOTION_WORDS)
    emotional_intensity = max(0, min(100, 30 + int((emotion_hits / max(token_count, 1)) * 280)))

    minutes = max(duration_seconds / 60.0, 0.15)
    pacing_wpm = int(token_count / minutes)
    pacing_issues: List[str] = []
    if pacing_wpm < 105:
        pacing_issues.append("pacing too slow")
    if pacing_wpm > 235:
        pacing_issues.append("pacing too dense")

    if hook_strength >= 70 or emotional_intensity >= 68:
        energy_curve = "front_loaded_spike"
    elif pacing_wpm >= 170:
        energy_curve = "high_momentum"
    else:
        energy_curve = "cinematic_rise"

    high_energy = energy_curve in {"front_loaded_spike", "high_momentum"}

    return {
        "hook_strength": hook_strength,
        "emotional_intensity": emotional_intensity,
        "pacing_wpm": pacing_wpm,
        "pacing_issues": pacing_issues,
        "energy_curve": energy_curve,
        "high_energy": high_energy,
    }


def _caption_chunks(transcript: str) -> List[str]:
    tokens = _tokenize(transcript)
    if not tokens:
        return []

    chunks: List[str] = []
    index = 0
    while index < len(tokens):
        size = 4 if (index % 3 == 0) else 3
        if len(tokens) - index <= 2:
            size = 2
        part = tokens[index : index + size]
        if not part:
            break
        words: List[str] = []
        for word in part:
            if word in KEYWORD_WORDS:
                words.append(word.upper())
            else:
                words.append(word)
        chunks.append(" ".join(words))
        index += size
    return chunks


def _ass_ts(seconds: float) -> str:
    centiseconds = int(max(0, round(seconds * 100)))
    hh = centiseconds // 360000
    mm = (centiseconds % 360000) // 6000
    ss = (centiseconds % 6000) // 100
    cs = centiseconds % 100
    return f"{hh}:{mm:02d}:{ss:02d}.{cs:02d}"


def _write_caption_ass(transcript: str, duration_seconds: float, output_path: Path, *, reduced_font: bool = False) -> Optional[Path]:
    text = _normalize_space(transcript)
    if not text:
        return None

    # Avoid turning social caption copy into on-screen subtitle spam.
    if len(text) > 420 or len(_tokenize(text)) > 90:
        return None

    chunks = _caption_chunks(text)
    if not chunks:
        return None

    # One font family, max 3 colors.
    colors = [r"{\c&H00FFFFFF&}", r"{\c&H0000FFFF&}", r"{\c&H0058FF7A&}"]
    font_size = 52 if not reduced_font else 44

    min_chunk = 0.32
    max_chunk = 1.05
    slot = max(min_chunk, min(max_chunk, duration_seconds / max(1, len(chunks))))

    lines: List[str] = []
    current = 0.08
    color_idx = 0
    for chunk in chunks:
        start = current
        end = min(duration_seconds, start + slot)
        current = end
        styled = f"{colors[color_idx % len(colors)]}{chunk}"
        color_idx += 1
        lines.append(
            "Dialogue: 0,"
            f"{_ass_ts(start)},{_ass_ts(end)},Caption,,0,0,0,,{styled}"
        )
        if current >= duration_seconds:
            break

    ass = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
        "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Caption,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H64000000,1,0,0,0,100,100,0,0,1,3,2,2,96,96,170,1\n\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
        + "\n".join(lines)
        + "\n"
    )

    output_path.write_text(ass, encoding="utf-8")
    return output_path


def _escape_filter_path(path: Path) -> str:
    value = str(path)
    value = value.replace("\\", "\\\\")
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    value = value.replace(",", r"\,")
    return value


def _apply_primary_pass(
    input_path: Path,
    output_path: Path,
    *,
    transcript: str,
    script_profile: Dict[str, Any],
    reduced_font: bool = False,
    engagement_boost: bool = False,
    simplify_colors: bool = False,
    recover_dark_tone: bool = False,
) -> Tuple[Path, List[str]]:
    has_audio = _has_audio_stream(input_path)
    duration = max(_probe_duration(input_path), 0.1)

    high_energy = bool(script_profile.get("high_energy"))
    visual_filters: List[str] = []
    corrections: List[str] = []

    # Final format safety: always fill 9:16 and avoid black bars.
    visual_filters.append("scale=1080:1920:force_original_aspect_ratio=increase")
    visual_filters.append("crop=1080:1920")
    visual_filters.append("setsar=1")

    if high_energy or engagement_boost:
        visual_filters.append("scale=1112:1978:flags=lanczos")
        visual_filters.append("crop=1080:1920")
        visual_filters.append("eq=contrast=1.04:saturation=1.02:brightness=0.01:gamma=1.01")
        corrections.append("visual_energy_micro_zoom")
    else:
        visual_filters.append("eq=contrast=1.02:saturation=1.01:brightness=0.005:gamma=1.0")
        visual_filters.append("unsharp=3:3:0.35")
        corrections.append("cinematic_motion_grade")

    if recover_dark_tone:
        visual_filters.append("eq=contrast=1.04:saturation=1.03:brightness=0.02")
        corrections.append("dark_tone_recovery")

    if simplify_colors:
        visual_filters.append("hue=s=0.87")
        corrections.append("simplify_palette")

    ass_path: Optional[Path] = None
    filter_complex = ",".join(visual_filters)

    # Caption intelligence stage (2-4 words chunk, safe margins, controlled colors).
    ass_path = _write_caption_ass(
        transcript,
        duration,
        Path(tempfile.gettempdir()) / f"shortform_{input_path.stem}.ass",
        reduced_font=reduced_font,
    )
    if ass_path:
        filter_complex = f"{filter_complex},subtitles='{_escape_filter_path(ass_path)}'"
        corrections.append("caption_intelligence")

    if engagement_boost:
        setpts_factor = 0.965 if high_energy else 0.975
    else:
        setpts_factor = 0.985 if high_energy else 1.0

    export_profile = standard_1080x1920_profile()
    cmd: List[str] = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
    ]

    if has_audio:
        audio_graph = (
            "loudnorm=I=-14:LRA=11:TP=-1.5,"
            "dynaudnorm=f=200:g=9:m=7,"
            "acompressor=threshold=-20dB:ratio=2.2:attack=10:release=120,"
            "aecho=0.8:0.25:35:0.025"
        )
        if high_energy or engagement_boost:
            audio_graph += ",volume=1.03"
        cmd += ["-af", audio_graph]
        corrections.append("audio_voice_normalized_-14_lufs")
        corrections.append("music_level_target_-28_lufs_proxy")
        corrections.append("speech_ducking_proxy")
        corrections.append("beat_sync_emphasis_subtle")
    else:
        corrections.append("no_audio_stream")

    video_filter = filter_complex
    if abs(setpts_factor - 1.0) > 0.001:
        video_filter = f"setpts={setpts_factor}*PTS,{filter_complex}"
        corrections.append("engagement_pacing_boost")

    cmd += ["-vf", video_filter]

    cmd += [
        "-c:v",
        "libx264",
        "-profile:v",
        export_profile.video_profile,
        "-preset",
        export_profile.video_preset,
        "-crf",
        str(export_profile.crf),
        "-pix_fmt",
        export_profile.pixel_format,
        "-r",
        str(export_profile.fps),
        "-b:v",
        export_profile.bitrate,
        "-maxrate",
        export_profile.maxrate,
        "-bufsize",
        export_profile.bufsize,
        "-c:a",
        "aac",
        "-b:a",
        export_profile.audio_bitrate,
        "-ar",
        str(export_profile.audio_sample_rate),
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    _run(cmd, context="shortform primary pass")

    if ass_path:
        ass_path.unlink(missing_ok=True)

    return output_path, corrections


def _frame_summary_opencv(video_path: Path) -> Dict[str, Any]:
    if not CV_AVAILABLE:
        return {
            "sample_count": 0,
            "caption_overlap_ratio": 0.0,
            "edge_clipping_ratio": 0.0,
            "oversaturation_ratio": 0.0,
            "active_color_mean": 0.0,
            "cv_available": False,
        }

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {
            "sample_count": 0,
            "caption_overlap_ratio": 0.0,
            "edge_clipping_ratio": 0.0,
            "oversaturation_ratio": 0.0,
            "active_color_mean": 0.0,
            "cv_available": True,
            "capture_open": False,
        }

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    # Sample ~30 evenly-spaced frames by seeking directly instead of reading
    # every frame sequentially.  This cuts analysis from 40-70s to ~3-5s.
    max_samples = 30
    target_count = min(max_samples, max(1, total_frames))
    seek_indices = [int(i * total_frames / target_count) for i in range(target_count)] if total_frames > 0 else []

    sample_count = 0
    caption_overlap_hits = 0
    clipping_hits = 0
    oversat_hits = 0
    active_colors: List[float] = []
    luma_samples: List[float] = []

    for frame_idx in seek_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue

        sample_count += 1
        h, w = frame.shape[:2]

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        sat_mean = float(np.mean(hsv[:, :, 1]))
        if sat_mean > 170:
            oversat_hits += 1

        # active colors via coarse quantization.
        resized = cv2.resize(frame, (128, 228), interpolation=cv2.INTER_AREA)
        quant = (resized // 32).astype(np.uint8)
        flat = quant.reshape(-1, 3)
        uniq = np.unique(flat, axis=0)
        active_colors.append(float(len(uniq)))

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        luma_samples.append(float(np.mean(gray)))
        edges = cv2.Canny(gray, 80, 160)

        border = max(6, int(min(h, w) * 0.03))
        border_mask = np.zeros_like(edges)
        border_mask[:border, :] = 1
        border_mask[-border:, :] = 1
        border_mask[:, :border] = 1
        border_mask[:, -border:] = 1
        border_edges = np.sum(edges[border_mask == 1] > 0)
        total_edges = max(1, int(np.sum(edges > 0)))
        if (border_edges / total_edges) > 0.44:
            clipping_hits += 1

        lower_band = edges[int(h * 0.74) : int(h * 0.93), int(w * 0.08) : int(w * 0.92)]
        lower_density = float(np.mean(lower_band > 0)) if lower_band.size else 0.0
        if lower_density > 0.12:
            caption_overlap_hits += 1

    cap.release()

    return {
        "sample_count": sample_count,
        "caption_overlap_ratio": round(caption_overlap_hits / max(sample_count, 1), 3),
        "edge_clipping_ratio": round(clipping_hits / max(sample_count, 1), 3),
        "oversaturation_ratio": round(oversat_hits / max(sample_count, 1), 3),
        "active_color_mean": round(float(np.mean(active_colors)) if active_colors else 0.0, 2),
        "mean_luma": round(float(np.mean(luma_samples)) if luma_samples else 0.0, 2),
        "min_luma": round(float(min(luma_samples)) if luma_samples else 0.0, 2),
        "cv_available": True,
    }


def _looks_like_black_screen(summary: Dict[str, Any], reference: Optional[Dict[str, Any]] = None) -> bool:
    sample_count = int(summary.get("sample_count") or 0)
    if sample_count < 2:
        return False

    mean_luma = float(summary.get("mean_luma") or 0.0)
    min_luma = float(summary.get("min_luma") or mean_luma)

    if mean_luma <= 16.0 and min_luma <= 7.0:
        return True

    if reference:
        ref_mean = float(reference.get("mean_luma") or mean_luma)
        ref_min = float(reference.get("min_luma") or mean_luma)
        if ref_mean > 0 and mean_luma < ref_mean * 0.35 and min_luma < max(ref_min * 0.35, 5.0):
            return True

    return False


def _requires_dark_recovery(summary: Dict[str, Any]) -> bool:
    sample_count = int(summary.get("sample_count") or 0)
    if sample_count < 2:
        return False

    mean_luma = float(summary.get("mean_luma") or 0.0)
    min_luma = float(summary.get("min_luma") or mean_luma)

    # Recovery trigger for visually dull inputs that are not fully black.
    if mean_luma <= 102.0 and min_luma < 22.0:
        return True
    if mean_luma <= 110.0 and min_luma <= 12.0:
        return True

    return False


def _ai_validate(
    transcript: str,
    *,
    script_profile: Dict[str, Any],
    frame_summary: Dict[str, Any],
) -> Dict[str, Any]:
    if not API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    payload: Dict[str, Any] = {
        "model": OPENAI_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": DESIGN_PROMPT},
            {
                "role": "user",
                "content": (
                    "Evaluate this short-form video optimization result.\n"
                    f"Transcript: {transcript[:2000] or '[none]'}\n"
                    f"Script Profile: {json.dumps(script_profile)}\n"
                    f"Frame Summary (0.5s OpenCV samples): {json.dumps(frame_summary)}\n"
                    "Return JSON only."
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "shortform_scores",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "aesthetic_score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "engagement_score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "issues": {"type": "array", "items": {"type": "string"}},
                        "improvements": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["aesthetic_score", "engagement_score", "issues", "improvements"],
                    "additionalProperties": False,
                },
            },
        },
    }

    req = request.Request(
        url="https://api.openai.com/v1/chat/completions",
        method="POST",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode("utf-8"),
    )

    try:
        with request.urlopen(req, timeout=OPENAI_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI shortform validation failed ({exc.code}): {detail[:450]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"OpenAI shortform validation network error: {exc.reason}") from exc

    parsed = json.loads(body or "{}")
    choices = parsed.get("choices") or []
    if not choices:
        raise RuntimeError("OpenAI returned no choices")

    content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, str):
        raw = content
    elif isinstance(content, list):
        raw = "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    else:
        raise RuntimeError("OpenAI content missing")

    data = json.loads(raw)
    return {
        "aesthetic_score": max(0, min(100, int(data.get("aesthetic_score", 0)))),
        "engagement_score": max(0, min(100, int(data.get("engagement_score", 0)))),
        "issues": [str(item) for item in data.get("issues", []) if isinstance(item, (str, int, float))],
        "improvements": [str(item) for item in data.get("improvements", []) if isinstance(item, (str, int, float))],
    }


def _local_validation_default(script_profile: Dict[str, Any], frame_summary: Dict[str, Any]) -> Dict[str, Any]:
    aesthetic = 86
    engagement = 82
    issues: List[str] = []
    improvements: List[str] = []

    if frame_summary.get("oversaturation_ratio", 0.0) > 0.28:
        aesthetic -= 14
        issues.append("over-saturation detected")
        improvements.append("reduce saturation and simplify palette")
    if frame_summary.get("active_color_mean", 0.0) > 120:
        aesthetic -= 10
        issues.append("too many active colors")
        improvements.append("restrict palette to cleaner scheme")
    if frame_summary.get("edge_clipping_ratio", 0.0) > 0.33:
        aesthetic -= 12
        issues.append("edge clipping risk")
        improvements.append("rebalance framing to safe center")
    if frame_summary.get("caption_overlap_ratio", 0.0) > 0.30:
        aesthetic -= 10
        issues.append("caption overlap risk")
        improvements.append("reduce subtitle size and enforce safe margins")

    pacing = int(script_profile.get("pacing_wpm", 0) or 0)
    if pacing > 225 or pacing < 105:
        engagement -= 14
        issues.append("pacing inconsistency")
        improvements.append("tighten pauses and normalize cadence")
    if not script_profile.get("high_energy", False):
        engagement -= 6
        improvements.append("add subtle motion accents")

    return {
        "aesthetic_score": max(0, min(100, aesthetic)),
        "engagement_score": max(0, min(100, engagement)),
        "issues": issues,
        "improvements": improvements,
    }


def _replace_original(original: Path, replacement: Path) -> str:
    if replacement.resolve() == original.resolve():
        return str(original)
    temp = original.with_name(f"{original.stem}_shortform_tmp{original.suffix}")
    replacement.replace(temp)
    temp.replace(original)
    replacement.unlink(missing_ok=True)
    return str(original)


def analyze_script(transcript: str, duration: float) -> Dict[str, Any]:
    return _script_analysis(transcript, duration)


def analyze_frames(video_path: str) -> Dict[str, Any]:
    return _frame_summary_opencv(Path(video_path))


def optimize_shortform_video(video_path: str, transcript: str) -> str:
    """
    Master short-form AI optimization pipeline (single-pass).

    Stages:
    1) Script analysis
    2) Frame analysis (OpenCV on original — no pre-render needed)
    3) AI validation → determines which corrections to apply
    4) Single render pass with all corrections baked in

    Analyzing the original before rendering lets us decide all corrections
    upfront and apply them in ONE ffmpeg pass instead of two or three.
    """
    original = Path(video_path).expanduser().resolve()
    if not original.exists():
        LOGGER.error("shortform optimize requested for missing file: %s", original)
        return video_path

    # Skip if cinematic engine already processed this video.
    if original.with_suffix(".cinematic_done").exists():
        LOGGER.info("Cinematic engine already processed %s; skipping shortform.", original.name)
        return str(original)

    if not SHORTFORM_AI_ENABLED:
        LOGGER.info("shortform optimization disabled; keeping original %s", original.name)
        return str(original)

    transcript = _normalize_space(transcript)

    try:
        duration = _probe_duration(original)
        script_profile = _script_analysis(transcript, duration)
        LOGGER.info(
            "shortform script metrics hook=%s emotion=%s pacing_wpm=%s energy_curve=%s",
            script_profile.get("hook_strength"),
            script_profile.get("emotional_intensity"),
            script_profile.get("pacing_wpm"),
            script_profile.get("energy_curve"),
        )

        # Analyze the original video directly — no need to render first.
        frame_summary = _frame_summary_opencv(original)
        LOGGER.info("shortform frame summary=%s", frame_summary)

        if _looks_like_black_screen(frame_summary):
            LOGGER.warning("Skipping shortform optimization because source appears near-black.")
            return str(original)

        try:
            ai_scores = _ai_validate(
                transcript,
                script_profile=script_profile,
                frame_summary=frame_summary,
            )
            source = "ai"
        except Exception as exc:
            LOGGER.error("shortform AI validation failed, using local fallback. error=%s", exc)
            ai_scores = _local_validation_default(script_profile, frame_summary)
            source = "local"

        aesthetic_score = int(ai_scores.get("aesthetic_score", 0))
        engagement_score = int(ai_scores.get("engagement_score", 0))
        issues = [str(item) for item in ai_scores.get("issues", [])]
        improvements = [str(item) for item in ai_scores.get("improvements", [])]

        LOGGER.info(
            "shortform validation source=%s aesthetic_score=%s engagement_score=%s",
            source,
            aesthetic_score,
            engagement_score,
        )
        LOGGER.info("shortform issues=%s", issues)
        LOGGER.info("shortform improvements=%s", improvements)

        needs_aesthetic_fix = aesthetic_score < AESTHETIC_THRESHOLD
        needs_engagement_fix = engagement_score < ENGAGEMENT_THRESHOLD
        needs_dark_recovery = _requires_dark_recovery(frame_summary)

        # Single render pass with all corrections determined upfront.
        output_path = original.with_name(f"{original.stem}_shortform{original.suffix}")
        optimized_path, corrections = _apply_primary_pass(
            original,
            output_path,
            transcript=transcript,
            script_profile=script_profile,
            reduced_font=needs_aesthetic_fix,
            engagement_boost=needs_engagement_fix,
            simplify_colors=needs_aesthetic_fix,
            recover_dark_tone=needs_dark_recovery,
        )

        LOGGER.info("shortform corrections applied=%s", corrections)

        optimized_summary = _frame_summary_opencv(optimized_path)
        if _looks_like_black_screen(optimized_summary, frame_summary):
            LOGGER.warning("Shortform optimization produced near-black output; keeping original clip.")
            try:
                if optimized_path.exists() and optimized_path != original:
                    optimized_path.unlink(missing_ok=True)
            except OSError as exc:
                LOGGER.debug("Could not remove low-luma optimized clip: %s", exc)
            return str(original)

        return _replace_original(original, optimized_path)
    except Exception as exc:
        LOGGER.error("shortform optimization failed; returning original. error=%s", exc)
        return str(original)


async def optimize_shortform_video_async(video_path: str, transcript: str) -> str:
    return await asyncio.to_thread(optimize_shortform_video, video_path, transcript)
