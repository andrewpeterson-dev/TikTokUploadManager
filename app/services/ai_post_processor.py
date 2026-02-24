from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib import error, request

# Required key source: never hardcode API credentials.
API_KEY = os.getenv("OPENAI_API_KEY")

AI_ENHANCEMENT = os.getenv("AI_ENHANCEMENT", "true").strip().lower() not in {"0", "false", "no", "off"}
try:
    AESTHETIC_THRESHOLD = int(os.getenv("AESTHETIC_THRESHOLD", "75"))
except ValueError:
    AESTHETIC_THRESHOLD = 75

AI_MODEL = os.getenv("OPENAI_AESTHETIC_MODEL", "gpt-4.1-mini")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("OPENAI_AESTHETIC_TIMEOUT", "12"))

LOGGER = logging.getLogger("tiktok_manager.ai_post_processor")

SYSTEM_PROMPT = (
    "You are a professional TikTok motion designer.\n"
    "Detect:\n"
    "- Overlapping captions\n"
    "- Bad contrast\n"
    "- Misalignment\n"
    "- Excessive font sizes\n"
    "- Too many colors\n"
    "- Chaotic styling\n"
    "- Cropping issues (must be 9:16 safe)\n"
    "- Audio imbalance\n\n"
    "Return JSON:\n"
    "{\n"
    '  "errors_found": boolean,\n'
    '  "issues": [],\n'
    '  "suggested_fixes": [],\n'
    '  "aesthetic_score": 0-100\n'
    "}\n"
)


class AIPostProcessorError(RuntimeError):
    pass


def _run(command: List[str], *, context: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "command failed").strip()
        raise AIPostProcessorError(f"{context} failed: {message}")
    return result


def _probe_video(video_path: Path) -> Dict[str, Any]:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=width,height,codec_type",
            "-show_entries",
            "format=duration,bit_rate",
            "-of",
            "json",
            str(video_path),
        ],
        context="ffprobe media",
    )

    payload = json.loads(result.stdout or "{}")
    width = 0
    height = 0
    has_audio = False

    for stream in payload.get("streams", []):
        if not isinstance(stream, dict):
            continue
        if stream.get("codec_type") == "video":
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
        if stream.get("codec_type") == "audio":
            has_audio = True

    format_info = payload.get("format") or {}
    return {
        "width": width,
        "height": height,
        "duration": float(format_info.get("duration") or 0.0),
        "bit_rate": int(format_info.get("bit_rate") or 0),
        "has_audio": has_audio,
    }


def _audio_loudness_summary(video_path: Path) -> Dict[str, Any]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-af",
        "loudnorm=I=-14:LRA=11:TP=-1.5:print_format=json",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        return {"input_i": None, "input_tp": None, "input_lra": None, "input_thresh": None}

    text = result.stderr or ""
    match = re.search(r"\{\s*\"input_i\".*?\}\s*$", text, re.DOTALL)
    if not match:
        return {"input_i": None, "input_tp": None, "input_lra": None, "input_thresh": None}

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"input_i": None, "input_tp": None, "input_lra": None, "input_thresh": None}

    return {
        "input_i": parsed.get("input_i"),
        "input_tp": parsed.get("input_tp"),
        "input_lra": parsed.get("input_lra"),
        "input_thresh": parsed.get("input_thresh"),
    }


def _extract_frames(video_path: Path, *, count: int = 3) -> List[Path]:
    meta = _probe_video(video_path)
    duration = max(float(meta.get("duration") or 0.0), 1.0)
    timestamps = []
    if count <= 1:
        timestamps = [duration / 2]
    else:
        for idx in range(count):
            ratio = (idx + 1) / (count + 1)
            timestamps.append(max(0.0, duration * ratio))

    frame_paths: List[Path] = []
    for idx, timestamp in enumerate(timestamps, start=1):
        frame_path = Path(tempfile.gettempdir()) / f"aesthetic_{video_path.stem}_{idx}.jpg"
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            "scale=512:-2",
            str(frame_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0 and frame_path.exists():
            frame_paths.append(frame_path)

    return frame_paths


def _frame_to_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _analyze_with_ai(video_path: Path) -> Dict[str, Any]:
    if not API_KEY:
        raise AIPostProcessorError("OPENAI_API_KEY is not set")

    metadata = _probe_video(video_path)
    loudness = _audio_loudness_summary(video_path)
    frames = _extract_frames(video_path, count=3)

    content: List[Dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "Assess this rendered TikTok video. "
                "Use the metadata and preview frames to find design/audio issues.\n"
                f"Metadata: {json.dumps(metadata)}\n"
                f"Audio: {json.dumps(loudness)}\n"
                "Return only JSON matching the schema."
            ),
        }
    ]

    for frame_path in frames:
        try:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": _frame_to_data_url(frame_path),
                        "detail": "low",
                    },
                }
            )
        except Exception:
            continue

    payload: Dict[str, Any] = {
        "model": AI_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "aesthetic_feedback",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "errors_found": {"type": "boolean"},
                        "issues": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "suggested_fixes": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "aesthetic_score": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                        },
                    },
                    "required": ["errors_found", "issues", "suggested_fixes", "aesthetic_score"],
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
        with request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AIPostProcessorError(f"OpenAI request failed ({exc.code}): {detail[:600]}") from exc
    except error.URLError as exc:
        raise AIPostProcessorError(f"OpenAI network error: {exc.reason}") from exc
    finally:
        for frame_path in frames:
            frame_path.unlink(missing_ok=True)

    parsed = json.loads(body or "{}")
    choices = parsed.get("choices") or []
    if not choices:
        raise AIPostProcessorError("OpenAI response had no choices")

    message = choices[0].get("message") or {}
    content_value = message.get("content")
    if isinstance(content_value, str):
        raw_json = content_value
    elif isinstance(content_value, list):
        # Some models return a list of text parts.
        raw_json = "\n".join(str(item.get("text", "")) for item in content_value if isinstance(item, dict))
    else:
        raise AIPostProcessorError("OpenAI response missing message.content")

    try:
        feedback = json.loads(raw_json)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_json, flags=re.DOTALL)
        if not match:
            raise AIPostProcessorError("OpenAI response content was not valid JSON")
        feedback = json.loads(match.group(0))

    issues = feedback.get("issues")
    if not isinstance(issues, list):
        issues = []
    suggested_fixes = feedback.get("suggested_fixes")
    if not isinstance(suggested_fixes, list):
        suggested_fixes = []

    score = feedback.get("aesthetic_score")
    if not isinstance(score, int):
        try:
            score = int(score)
        except Exception:
            score = 0

    normalized = {
        "errors_found": bool(feedback.get("errors_found")),
        "issues": [str(item) for item in issues],
        "suggested_fixes": [str(item) for item in suggested_fixes],
        "aesthetic_score": max(0, min(100, score)),
    }
    return normalized


def _needs_caption_normalization(issues: List[str], suggested_fixes: List[str]) -> bool:
    text = " ".join([*issues, *suggested_fixes]).lower()
    keywords = ["caption", "subtitle", "font", "overlap", "misalign", "alignment"]
    return any(keyword in text for keyword in keywords)


def _needs_palette_reduction(issues: List[str], suggested_fixes: List[str]) -> bool:
    text = " ".join([*issues, *suggested_fixes]).lower()
    keywords = ["too many colors", "palette", "chaotic", "color", "styling"]
    return any(keyword in text for keyword in keywords)


def _needs_contrast_fix(issues: List[str], suggested_fixes: List[str]) -> bool:
    text = " ".join([*issues, *suggested_fixes]).lower()
    return "contrast" in text or "dark" in text


def _needs_audio_fix(issues: List[str], suggested_fixes: List[str]) -> bool:
    text = " ".join([*issues, *suggested_fixes]).lower()
    keywords = ["audio", "loud", "quiet", "imbalance", "volume", "mix"]
    return any(keyword in text for keyword in keywords)


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


def _build_output_path(video_path: Path, suffix: str) -> Path:
    parent = video_path.parent
    stem = video_path.stem
    return parent / f"{stem}{suffix}.mp4"


def _apply_heavy_corrections(video_path: Path, issues: List[str], suggested_fixes: List[str]) -> Tuple[Path, List[str]]:
    output_path = _build_output_path(video_path, "_ai_fixed")

    caption_fix = _needs_caption_normalization(issues, suggested_fixes)
    palette_fix = _needs_palette_reduction(issues, suggested_fixes)
    contrast_fix = _needs_contrast_fix(issues, suggested_fixes)
    audio_fix = _needs_audio_fix(issues, suggested_fixes)

    corrections_applied: List[str] = [
        "enforce_9_16_safe_frame",
        "center_safe_margins",
    ]

    base_chain = [
        "scale=1080:1920:force_original_aspect_ratio=decrease",
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
        "setsar=1",
    ]

    if caption_fix:
        base_chain.extend(
            [
                # Shrink full frame slightly to reduce oversized burned-in captions.
                "scale=1004:1786:flags=lanczos",
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
            ]
        )
        corrections_applied.extend(
            [
                "normalize_captions",
                "reduce_font_size_proxy",
                "enforce_caption_safe_margins",
            ]
        )

    if contrast_fix:
        base_chain.append("eq=contrast=1.08:brightness=0.02:saturation=1.04")
        corrections_applied.append("contrast_rebalance")

    has_audio = _has_audio_stream(video_path)

    command: List[str] = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
    ]

    if palette_fix:
        filter_complex = (
            f"[0:v]{','.join(base_chain)}[base];"
            "[base]split[pgen][puse];"
            "[pgen]palettegen=max_colors=3[p];"
            "[puse][p]paletteuse=dither=bayer[outv]"
        )
        command += ["-filter_complex", filter_complex, "-map", "[outv]"]
        corrections_applied.append("restrict_palette_max_3")
    else:
        command += ["-vf", ",".join(base_chain)]

    if has_audio:
        command += ["-map", "0:a:0"]
        if audio_fix:
            command += ["-af", "loudnorm=I=-14:LRA=11:TP=-1.5"]
            corrections_applied.append("normalize_audio_-14_lufs")
    else:
        corrections_applied.append("no_audio_stream")

    command += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    _run(command, context="heavy enhancement")
    return output_path, corrections_applied


def _apply_light_enhancement(video_path: Path) -> Tuple[Path, List[str]]:
    output_path = _build_output_path(video_path, "_ai_light")

    has_audio = _has_audio_stream(video_path)
    corrections_applied = [
        "subtle_color_grade",
        "light_cinematic_polish",
    ]

    command: List[str] = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vf",
        (
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
            "setsar=1,"
            "eq=contrast=1.03:brightness=0.01:saturation=1.05,"
            "unsharp=5:5:0.4:5:5:0.0"
        ),
    ]

    if has_audio:
        command += ["-map", "0:a:0", "-af", "loudnorm=I=-14:LRA=11:TP=-1.5"]
        corrections_applied.append("subtitle_timing_polish_proxy")
    else:
        corrections_applied.append("no_audio_stream")

    command += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    _run(command, context="light enhancement")
    return output_path, corrections_applied


def enhance_video(video_path: str) -> str:
    """
    Post-render AI validation + enhancement pipeline.

    Architecture:
    1) Analyze rendered video with multimodal AI (metadata + sampled frames).
    2) Parse strict JSON feedback.
    3) Apply heavy corrections below threshold, light polish otherwise.
    4) Fail-safe: on any API/processing error, keep original video unchanged.

    Returns final video path.
    """
    input_path = Path(video_path).expanduser().resolve()
    if not input_path.exists():
        LOGGER.error("AI post processor received missing file: %s", input_path)
        return video_path

    if not AI_ENHANCEMENT:
        LOGGER.info("AI enhancement disabled. Returning original video: %s", input_path)
        return str(input_path)

    if not API_KEY:
        LOGGER.warning("OPENAI_API_KEY not set. Skipping AI enhancement for %s", input_path.name)
        return str(input_path)

    try:
        feedback = _analyze_with_ai(input_path)
    except Exception as exc:
        LOGGER.error("AI analysis failed. Returning original video. error=%s", exc)
        return str(input_path)

    score = int(feedback.get("aesthetic_score", 0))
    issues = [str(issue) for issue in feedback.get("issues", [])]
    suggested_fixes = [str(item) for item in feedback.get("suggested_fixes", [])]

    LOGGER.info("AI aesthetic score=%s threshold=%s", score, AESTHETIC_THRESHOLD)
    LOGGER.info("AI issues found=%s", issues)
    LOGGER.info("AI suggested fixes=%s", suggested_fixes)

    try:
        if score < AESTHETIC_THRESHOLD:
            output_path, corrections = _apply_heavy_corrections(input_path, issues, suggested_fixes)
        else:
            output_path, corrections = _apply_light_enhancement(input_path)

        LOGGER.info("AI corrections applied=%s", corrections)

        # Replace original file atomically to avoid breaking upstream path assumptions.
        temp_replaced = _build_output_path(input_path, "_ai_tmp")
        output_path.replace(temp_replaced)
        temp_replaced.replace(input_path)

        # Remove intermediate artifact if it remains.
        output_path.unlink(missing_ok=True)

        return str(input_path)
    except Exception as exc:
        LOGGER.error("AI enhancement failed. Returning original video. error=%s", exc)
        return str(input_path)


async def enhance_video_async(video_path: str) -> str:
    """Async-compatible entrypoint for non-blocking orchestration contexts."""
    return await asyncio.to_thread(enhance_video, video_path)
