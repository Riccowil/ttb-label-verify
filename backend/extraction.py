"""Vision extraction client — SPEC.md section 5 (prompt, single call,
temperature 0) and sections 7/8 (thresholds, retry/timeout policy).

ADR-002: hosted vision API for the prototype, provider kept behind this
one module. Model/provider is config (thresholds.MODEL_NAME), not code —
swapping providers means editing VisionExtractor, not its callers.
"""

import base64
import io
import json
import os
import re
from typing import Optional

from anthropic import (
    Anthropic,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)
from PIL import Image
from pydantic import ValidationError

from models import ExtractionResult
from thresholds import IMAGE_LONG_EDGE_PX, MODEL_NAME, VISION_RETRIES, VISION_TIMEOUT_SECONDS

EXTRACTION_PROMPT = """You are extracting text from an alcohol beverage label image for TTB compliance review. Extract EXACTLY what appears on the label, character-for-character, preserving case, punctuation, and spacing. Do not correct, normalize, or interpret.

Return only this JSON:

{
  "brand_name": "verbatim text or null",
  "class_type": "verbatim text or null",
  "alcohol_content": "verbatim text or null",
  "net_contents": "verbatim text or null",
  "government_warning": {
    "present": true/false,
    "verbatim_text": "exact text including the GOVERNMENT WARNING: prefix, or null",
    "prefix_appears_bold": true/false/null,
    "legibility": "clear" | "partial" | "unreadable"
  },
  "extraction_confidence": {
    "brand_name": "high" | "medium" | "low",
    "class_type": "high" | "medium" | "low",
    "alcohol_content": "high" | "medium" | "low",
    "net_contents": "high" | "medium" | "low",
    "government_warning": "high" | "medium" | "low"
  },
  "image_quality_issues": ["glare", "angle", "blur", "cropped"] or []
}

Rules:
- If a field is not visible or not present, use null. Never guess.
- For government_warning.verbatim_text, transcribe every word exactly as printed, including capitalization.
- prefix_appears_bold: judge only whether "GOVERNMENT WARNING:" is visually bolder than surrounding text.
- Return JSON only, no commentary."""

_MAX_RESPONSE_TOKENS = 1024
_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)

# SPEC section 8: "1 retry on transient failure, then clean ... state."
# Connection/timeout/server-load errors are worth a retry; a garbled (but
# successfully returned) response is treated the same way since a retry is
# cheap and temperature 0 rarely reproduces the same noise twice. Anything
# else (bad request, auth failure, etc.) will not be fixed by retrying, so
# it propagates on the first attempt instead of burning the retry budget.
_RETRYABLE_API_EXCEPTIONS = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)


class ExtractionError(Exception):
    """Raised for any extraction-pipeline failure: network, parsing, or
    schema validation. Callers only need to catch this one type."""


def downscale_image(image_bytes: bytes, long_edge_px: int = IMAGE_LONG_EDGE_PX) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as img:
        width, height = img.size
        long_edge = max(width, height)
        if long_edge <= long_edge_px:
            return image_bytes

        scale = long_edge_px / long_edge
        new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        resized = img.resize(new_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        resized.save(buffer, format=img.format or "JPEG")
        return buffer.getvalue()


def _strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    return match.group(1).strip() if match else stripped


def _normalize_missing_warning_legibility(data: dict) -> dict:
    """Observed live: when government_warning.present is false, the model
    sometimes returns legibility: null instead of an enum value — there's
    no warning text left to judge legibility of. Every other field still
    extracts normally in that case, so null here means "not applicable,"
    not "unreadable." Defaulting to "clear" lets the missing warning reach
    the comparator as the compliance FAIL it actually is, instead of
    crashing schema validation or being mistaken for a bad photo."""
    warning = data.get("government_warning")
    if isinstance(warning, dict) and warning.get("legibility") is None:
        warning["legibility"] = "clear"
    return data


def parse_extraction_response(raw_text: str) -> ExtractionResult:
    cleaned = _strip_markdown_fences(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"Vision API returned non-JSON response: {exc}") from exc

    data = _normalize_missing_warning_legibility(data)

    try:
        return ExtractionResult.model_validate(data)
    except ValidationError as exc:
        raise ExtractionError(f"Vision API response failed schema validation: {exc}") from exc


def needs_better_image(extraction: ExtractionResult) -> bool:
    """SPEC section 5: partial/unreadable legibility short-circuits to
    NEEDS BETTER IMAGE with no field verdicts rendered. Callers check this
    before handing the extraction to the comparators."""
    return extraction.government_warning.legibility in ("partial", "unreadable")


class VisionExtractor:
    def __init__(self, api_key: Optional[str] = None, client: Optional[Anthropic] = None):
        if client is not None:
            self._client = client
            return

        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise ExtractionError(
                "ANTHROPIC_API_KEY is not set and no api_key was provided."
            )
        self._client = Anthropic(api_key=resolved_key)

    def extract(self, image_bytes: bytes, media_type: str = "image/jpeg") -> ExtractionResult:
        encoded = base64.standard_b64encode(downscale_image(image_bytes)).decode("utf-8")
        message_content = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": encoded},
            },
            {"type": "text", "text": EXTRACTION_PROMPT},
        ]

        last_error: Optional[Exception] = None
        for _ in range(VISION_RETRIES + 1):
            try:
                response = self._client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=_MAX_RESPONSE_TOKENS,
                    temperature=0,
                    timeout=VISION_TIMEOUT_SECONDS,
                    messages=[{"role": "user", "content": message_content}],
                )
                raw_text = "".join(
                    block.text for block in response.content if block.type == "text"
                )
                return parse_extraction_response(raw_text)
            except _RETRYABLE_API_EXCEPTIONS as exc:
                last_error = exc
            except ExtractionError as exc:
                last_error = exc
            except Exception as exc:
                raise ExtractionError(f"Vision extraction failed: {exc}") from exc

        raise ExtractionError(
            f"Vision extraction failed after {VISION_RETRIES + 1} attempt(s): {last_error}"
        ) from last_error
