"""Failing-first test suite for extraction.py — SPEC.md section 5 (prompt)
and section 7/8 (thresholds, retry/timeout policy). No live API calls: the
vision call is exercised through a mocked Anthropic client so retry and
error-handling behavior is verified without a network round trip.
"""

import base64
import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from anthropic import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
)
from PIL import Image

from extraction import (
    EXTRACTION_PROMPT,
    ExtractionError,
    VisionExtractor,
    downscale_image,
    needs_better_image,
    parse_extraction_response,
)
from models import ExtractionResult
from thresholds import IMAGE_LONG_EDGE_PX, MODEL_NAME, VISION_RETRIES, VISION_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# Prompt — SPEC section 5, must be verbatim
# ---------------------------------------------------------------------------


class TestExtractionPrompt:
    def test_contains_extraction_instruction_verbatim(self):
        assert (
            "Extract EXACTLY what appears on the label, character-for-character, "
            "preserving case, punctuation, and spacing."
            in EXTRACTION_PROMPT
        )

    def test_contains_do_not_correct_instruction(self):
        assert "Do not correct, normalize, or interpret." in EXTRACTION_PROMPT

    def test_contains_json_schema_keys(self):
        for key in (
            '"brand_name"', '"class_type"', '"alcohol_content"', '"net_contents"',
            '"government_warning"', '"present"', '"verbatim_text"',
            '"prefix_appears_bold"', '"legibility"', '"extraction_confidence"',
            '"image_quality_issues"',
        ):
            assert key in EXTRACTION_PROMPT

    def test_contains_never_guess_rule(self):
        assert "If a field is not visible or not present, use null. Never guess." in EXTRACTION_PROMPT

    def test_contains_bold_judgment_rule(self):
        assert (
            'prefix_appears_bold: judge only whether "GOVERNMENT WARNING:" is visually '
            "bolder than surrounding text." in EXTRACTION_PROMPT
        )

    def test_contains_json_only_rule(self):
        assert "Return JSON only, no commentary." in EXTRACTION_PROMPT


# ---------------------------------------------------------------------------
# downscale_image — SPEC section 10 / thresholds.IMAGE_LONG_EDGE_PX
# ---------------------------------------------------------------------------


def _make_image_bytes(width, height, fmt="JPEG"):
    image = Image.new("RGB", (width, height), color=(120, 40, 40))
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


class TestDownscaleImage:
    def test_image_below_threshold_is_unchanged(self):
        original = _make_image_bytes(800, 600)
        result = downscale_image(original)
        with Image.open(io.BytesIO(result)) as img:
            assert img.size == (800, 600)

    def test_landscape_image_above_threshold_is_downscaled_preserving_aspect_ratio(self):
        original = _make_image_bytes(3136, 2000)  # long edge = 2x threshold
        result = downscale_image(original)
        with Image.open(io.BytesIO(result)) as img:
            width, height = img.size
            assert max(width, height) == IMAGE_LONG_EDGE_PX
            assert width / height == pytest.approx(3136 / 2000, rel=0.01)

    def test_portrait_image_above_threshold_is_downscaled_on_height(self):
        original = _make_image_bytes(2000, 3136)
        result = downscale_image(original)
        with Image.open(io.BytesIO(result)) as img:
            width, height = img.size
            assert max(width, height) == IMAGE_LONG_EDGE_PX
            assert height == IMAGE_LONG_EDGE_PX

    def test_custom_long_edge_px_is_honored(self):
        original = _make_image_bytes(2000, 1000)
        result = downscale_image(original, long_edge_px=500)
        with Image.open(io.BytesIO(result)) as img:
            assert max(img.size) == 500

    def test_result_is_valid_image_bytes(self):
        original = _make_image_bytes(3136, 2000)
        result = downscale_image(original)
        # re-opening and loading should not raise
        with Image.open(io.BytesIO(result)) as img:
            img.load()


# ---------------------------------------------------------------------------
# parse_extraction_response — defensive markdown-fence stripping + validation
# ---------------------------------------------------------------------------


def _valid_extraction_json():
    return {
        "brand_name": "Old Tom Distillery",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol.",
        "net_contents": "750 mL",
        "government_warning": {
            "present": True,
            "verbatim_text": "GOVERNMENT WARNING: (1) According to the Surgeon General...",
            "prefix_appears_bold": True,
            "legibility": "clear",
        },
        "extraction_confidence": {
            "brand_name": "high",
            "class_type": "high",
            "alcohol_content": "high",
            "net_contents": "high",
            "government_warning": "high",
        },
        "image_quality_issues": [],
    }


class TestParseExtractionResponse:
    def test_plain_json_parses(self):
        raw = json.dumps(_valid_extraction_json())
        result = parse_extraction_response(raw)
        assert isinstance(result, ExtractionResult)
        assert result.brand_name == "Old Tom Distillery"

    def test_json_fenced_with_language_tag_parses(self):
        raw = "```json\n" + json.dumps(_valid_extraction_json()) + "\n```"
        result = parse_extraction_response(raw)
        assert result.brand_name == "Old Tom Distillery"

    def test_json_fenced_without_language_tag_parses(self):
        raw = "```\n" + json.dumps(_valid_extraction_json()) + "\n```"
        result = parse_extraction_response(raw)
        assert result.class_type == "Kentucky Straight Bourbon Whiskey"

    def test_json_with_surrounding_whitespace_parses(self):
        raw = "\n\n  " + json.dumps(_valid_extraction_json()) + "  \n\n"
        result = parse_extraction_response(raw)
        assert result.net_contents == "750 mL"

    def test_full_nested_shape_parses_correctly(self):
        raw = json.dumps(_valid_extraction_json())
        result = parse_extraction_response(raw)
        assert result.government_warning.present is True
        assert result.government_warning.legibility == "clear"
        assert result.extraction_confidence.government_warning == "high"
        assert result.image_quality_issues == []

    def test_malformed_json_raises_extraction_error(self):
        with pytest.raises(ExtractionError):
            parse_extraction_response("{not valid json")

    def test_valid_json_failing_schema_raises_extraction_error(self):
        broken = _valid_extraction_json()
        del broken["government_warning"]
        with pytest.raises(ExtractionError):
            parse_extraction_response(json.dumps(broken))

    def test_null_fields_pass_through(self):
        data = _valid_extraction_json()
        data["brand_name"] = None
        data["government_warning"]["verbatim_text"] = None
        data["government_warning"]["present"] = False
        result = parse_extraction_response(json.dumps(data))
        assert result.brand_name is None
        assert result.government_warning.present is False


# ---------------------------------------------------------------------------
# needs_better_image — SPEC section 5 short-circuit rule
# ---------------------------------------------------------------------------


class TestNeedsBetterImage:
    def test_clear_legibility_does_not_need_better_image(self):
        result = parse_extraction_response(json.dumps(_valid_extraction_json()))
        assert needs_better_image(result) is False

    def test_partial_legibility_needs_better_image(self):
        data = _valid_extraction_json()
        data["government_warning"]["legibility"] = "partial"
        result = parse_extraction_response(json.dumps(data))
        assert needs_better_image(result) is True

    def test_unreadable_legibility_needs_better_image(self):
        data = _valid_extraction_json()
        data["government_warning"]["legibility"] = "unreadable"
        result = parse_extraction_response(json.dumps(data))
        assert needs_better_image(result) is True


# ---------------------------------------------------------------------------
# VisionExtractor — single interface (ADR-002), retry policy (SPEC section 8)
# ---------------------------------------------------------------------------


def _fake_request():
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _fake_httpx_response(status_code):
    return httpx.Response(status_code, request=_fake_request())


def _fake_anthropic_response(text):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class TestVisionExtractorConstruction:
    def test_missing_api_key_raises_extraction_error(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ExtractionError):
            VisionExtractor()

    def test_explicit_api_key_does_not_require_env_var(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        VisionExtractor(api_key="sk-test-key")  # should not raise

    def test_injected_client_bypasses_api_key_requirement(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        VisionExtractor(client=MagicMock())  # should not raise


class TestVisionExtractorExtract:
    def _extractor(self, client):
        return VisionExtractor(api_key="sk-test-key", client=client)

    def test_happy_path_returns_extraction_result_and_calls_once(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_anthropic_response(
            json.dumps(_valid_extraction_json())
        )
        extractor = self._extractor(client)

        result = extractor.extract(_make_image_bytes(800, 600), media_type="image/jpeg")

        assert isinstance(result, ExtractionResult)
        assert result.brand_name == "Old Tom Distillery"
        assert client.messages.create.call_count == 1

    def test_request_uses_model_temperature_and_timeout_from_thresholds(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_anthropic_response(
            json.dumps(_valid_extraction_json())
        )
        extractor = self._extractor(client)

        extractor.extract(_make_image_bytes(800, 600))

        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["model"] == MODEL_NAME
        assert kwargs["temperature"] == 0
        assert kwargs["timeout"] == VISION_TIMEOUT_SECONDS

    def test_oversized_image_is_downscaled_before_being_sent(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_anthropic_response(
            json.dumps(_valid_extraction_json())
        )
        extractor = self._extractor(client)

        extractor.extract(_make_image_bytes(3136, 2000))

        kwargs = client.messages.create.call_args.kwargs
        image_block = next(
            block for block in kwargs["messages"][0]["content"] if block["type"] == "image"
        )
        sent_bytes = base64.standard_b64decode(image_block["source"]["data"])
        with Image.open(io.BytesIO(sent_bytes)) as img:
            assert max(img.size) == IMAGE_LONG_EDGE_PX

    def test_transient_failure_then_success_retries_once(self):
        client = MagicMock()
        client.messages.create.side_effect = [
            APITimeoutError(request=_fake_request()),
            _fake_anthropic_response(json.dumps(_valid_extraction_json())),
        ]
        extractor = self._extractor(client)

        result = extractor.extract(_make_image_bytes(800, 600))

        assert result.brand_name == "Old Tom Distillery"
        assert client.messages.create.call_count == 2

    def test_persistent_transient_failure_exhausts_retries_and_raises(self):
        client = MagicMock()
        client.messages.create.side_effect = APIConnectionError(request=_fake_request())
        extractor = self._extractor(client)

        with pytest.raises(ExtractionError):
            extractor.extract(_make_image_bytes(800, 600))

        assert client.messages.create.call_count == VISION_RETRIES + 1

    def test_persistent_server_error_exhausts_retries_and_raises(self):
        client = MagicMock()
        client.messages.create.side_effect = InternalServerError(
            "server error", response=_fake_httpx_response(500), body=None
        )
        extractor = self._extractor(client)

        with pytest.raises(ExtractionError):
            extractor.extract(_make_image_bytes(800, 600))

        assert client.messages.create.call_count == VISION_RETRIES + 1

    def test_non_retryable_error_propagates_immediately_without_retrying(self):
        client = MagicMock()
        client.messages.create.side_effect = AuthenticationError(
            "invalid api key", response=_fake_httpx_response(401), body=None
        )
        extractor = self._extractor(client)

        with pytest.raises(ExtractionError):
            extractor.extract(_make_image_bytes(800, 600))

        assert client.messages.create.call_count == 1

    def test_garbled_response_is_retried_once_then_raises(self):
        client = MagicMock()
        client.messages.create.side_effect = [
            _fake_anthropic_response("not json at all"),
            _fake_anthropic_response("still not json"),
        ]
        extractor = self._extractor(client)

        with pytest.raises(ExtractionError):
            extractor.extract(_make_image_bytes(800, 600))

        assert client.messages.create.call_count == VISION_RETRIES + 1
