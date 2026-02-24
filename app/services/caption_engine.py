from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CaptionContext:
    filename: str
    content_theme: str
    clip_format: str
    source_hint: Optional[str] = None


class CaptionEngine:
    """GPT-backed caption generation with strict TikTok formatting rules."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 45,
    ):
        self.api_key = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        self.model = (model or os.getenv("OPENAI_CAPTION_MODEL") or "gpt-4.1-mini").strip()
        self.timeout_seconds = timeout_seconds

    def _call_openai(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required to generate captions.")

        payload = {
            "model": self.model,
            "temperature": 0.7,
            "max_output_tokens": 220,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You write high-performing TikTok captions. "
                                "Return one caption only with hook + concise value description + 5-10 hashtags."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                },
            ],
        }

        request = urllib.request.Request(
            url="https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Caption generation request failed ({exc.code}): {body[:400]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Caption generation network error: {exc.reason}") from exc

        payload = json.loads(raw or "{}")
        if isinstance(payload.get("output_text"), str) and payload.get("output_text"):
            return str(payload["output_text"]).strip()

        output = payload.get("output") or []
        chunks: List[str] = []
        for item in output:
            for content in item.get("content", []) if isinstance(item, dict) else []:
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    chunks.append(str(content["text"]))
        if chunks:
            return "\n".join(chunks).strip()

        raise RuntimeError("Caption generation returned an empty response.")

    def generate_caption(self, context: CaptionContext) -> str:
        prompt = (
            "Create a TikTok caption using these rules:\n"
            "- 150 to 300 characters total\n"
            "- First line: strong hook\n"
            "- Then 1-3 short sentences with concrete value\n"
            "- End with 5-10 optimized hashtags relevant to context\n"
            "- Avoid generic filler and spam hashtags\n"
            "- Keep spacing clean and natural\n\n"
            f"Context:\n"
            f"filename={context.filename}\n"
            f"content_theme={context.content_theme}\n"
            f"clip_format={context.clip_format}\n"
            f"source_hint={context.source_hint or 'none'}"
        )

        raw_caption = self._call_openai(prompt)
        return self._normalize_caption(raw_caption, context)

    def _normalize_caption(self, caption: str, context: CaptionContext) -> str:
        text = re.sub(r"\s+", " ", caption.replace("\r", " ").replace("\n", " \n ")).strip()
        text = re.sub(r"\s*\n\s*", "\n", text)

        hashtags = re.findall(r"#[A-Za-z0-9_]+", text)
        unique_hashtags = []
        for tag in hashtags:
            normalized = tag.lower()
            if normalized not in {h.lower() for h in unique_hashtags}:
                unique_hashtags.append(tag)

        if len(unique_hashtags) < 5:
            defaults = self._default_hashtags(context)
            for tag in defaults:
                if tag.lower() not in {h.lower() for h in unique_hashtags}:
                    unique_hashtags.append(tag)
                if len(unique_hashtags) >= 5:
                    break

        unique_hashtags = unique_hashtags[:10]

        # Strip original hashtags and rebuild the tag section.
        body = re.sub(r"(?:\s|^)(#[A-Za-z0-9_]+)", "", text).strip()
        body = re.sub(r"\s+", " ", body)
        hashtag_section = " ".join(unique_hashtags)

        rebuilt = f"{body}\n\n{hashtag_section}".strip()
        rebuilt = re.sub(r"\s+", " ", rebuilt.replace("\r", " ")).strip()

        if len(rebuilt) > 300:
            overflow = len(rebuilt) - 300
            trimmed_body = body[:-overflow].rstrip(" .,!;:-") if overflow < len(body) else body[:120]
            rebuilt = f"{trimmed_body}\n\n{hashtag_section}".strip()

        if len(rebuilt) < 150:
            extension = self._extension_sentence(context)
            rebuilt = f"{body} {extension}\n\n{hashtag_section}".strip()
            rebuilt = re.sub(r"\s+", " ", rebuilt)

        if len(rebuilt) > 300:
            rebuilt = rebuilt[:297].rstrip() + "..."

        return rebuilt

    def _default_hashtags(self, context: CaptionContext) -> List[str]:
        theme_tag = re.sub(r"[^a-z0-9]", "", context.content_theme.lower()) or "story"
        format_tag = re.sub(r"[^a-z0-9]", "", context.clip_format.lower()) or "clip"
        return [
            f"#{theme_tag}",
            f"#{format_tag}",
            "#storytelling",
            "#creator",
            "#contentstrategy",
            "#videomarketing",
            "#audiencegrowth",
        ]

    def _extension_sentence(self, context: CaptionContext) -> str:
        theme = context.content_theme.lower()
        if theme == "gaming":
            return "Timing and pacing are tuned so viewers stay through the payoff."
        if theme == "motivation":
            return "Use this as a repeatable framework, not just a one-time idea."
        if theme == "podcast":
            return "The clip is optimized for quick retention and clean takeaway value."
        return "This edit is structured to deliver a clear payoff fast and keep watch time high."
