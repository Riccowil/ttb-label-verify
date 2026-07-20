"""Failing-first test suite for app.py — SPEC.md section 8 (API contract),
section 9 (batch semantics), section 10 (image handling). VisionExtractor
is swapped for a fake via FastAPI dependency overrides: zero live API
calls anywhere in this suite.
"""

import csv
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from extraction import ExtractionError
from models import ExtractionConfidence, ExtractionResult, GovernmentWarningExtraction
from thresholds import BATCH_MAX_ROWS, IMAGE_MAX_MB, MODEL_NAME
from warning_text import BODY, PREFIX

STATUTORY_TEXT = f"{PREFIX} {BODY}"


def _make_image_bytes(width=800, height=600, fmt="JPEG"):
    image = Image.new("RGB", (width, height), color=(120, 40, 40))
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def _clear_extraction(
    brand_name="Old Tom Distillery",
    class_type="Kentucky Straight Bourbon Whiskey",
    alcohol_content="45% Alc./Vol.",
    net_contents="750 mL",
    warning_text=STATUTORY_TEXT,
    legibility="clear",
) -> ExtractionResult:
    return ExtractionResult(
        brand_name=brand_name,
        class_type=class_type,
        alcohol_content=alcohol_content,
        net_contents=net_contents,
        government_warning=GovernmentWarningExtraction(
            present=warning_text is not None,
            verbatim_text=warning_text,
            prefix_appears_bold=True,
            legibility=legibility,
        ),
        extraction_confidence=ExtractionConfidence(
            brand_name="high", class_type="high", alcohol_content="high",
            net_contents="high", government_warning="high",
        ),
        image_quality_issues=[],
    )


_APPLICATION_FORM = {
    "brand_name": "Old Tom Distillery",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45",
    "net_contents": "750 mL",
    "beverage_type": "distilled_spirits",
}


class FakeExtractor:
    """Duck-types VisionExtractor.extract without touching the network."""

    def __init__(self, result=None, error=None, per_call=None):
        self.result = result
        self.error = error
        self.per_call = per_call or {}
        self.calls = []

    def extract(self, image_bytes, media_type="image/jpeg"):
        self.calls.append((image_bytes, media_type))
        key = len(self.calls) - 1
        if key in self.per_call:
            behavior = self.per_call[key]
            if isinstance(behavior, Exception):
                raise behavior
            return behavior
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def client_factory():
    """Returns a (client, fake_extractor) pair with the extractor dependency
    overridden — no real Anthropic client is ever constructed."""

    def _make(result=None, error=None, per_call=None):
        import app as app_module

        fake = FakeExtractor(result=result, error=error, per_call=per_call)
        app_module.app.dependency_overrides[app_module.get_extractor] = lambda: fake
        client = TestClient(app_module.app)
        return client, fake

    yield _make

    import app as app_module

    app_module.app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_returns_status_and_model_name(self, client_factory):
        client, _ = client_factory(result=_clear_extraction())
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "model_name": MODEL_NAME}


# ---------------------------------------------------------------------------
# POST /api/verify — happy path
# ---------------------------------------------------------------------------


class TestVerifyHappyPath:
    def test_all_pass_returns_envelope_shape(self, client_factory):
        client, fake = client_factory(result=_clear_extraction())
        response = client.post(
            "/api/verify",
            files={"image": ("label.jpg", _make_image_bytes(), "image/jpeg")},
            data=_APPLICATION_FORM,
        )
        assert response.status_code == 200
        body = response.json()

        assert set(body.keys()) == {"overall_verdict", "processing_time_ms", "image_quality", "fields"}
        assert body["overall_verdict"] == "PASS"
        assert isinstance(body["processing_time_ms"], int)
        assert body["processing_time_ms"] >= 0
        assert body["image_quality"] == {"legibility": "clear", "issues": []}
        assert len(body["fields"]) == 5
        assert {f["field"] for f in body["fields"]} == {
            "brand_name", "class_type", "alcohol_content", "net_contents", "government_warning",
        }
        for field_entry in body["fields"]:
            assert set(field_entry.keys()) == {"field", "verdict", "reason", "evidence"}

        assert fake.calls[0][1] == "image/jpeg"

    def test_mismatched_fields_produce_worse_overall_verdict(self, client_factory):
        client, _ = client_factory(result=_clear_extraction(brand_name="Totally Different Name"))
        response = client.post(
            "/api/verify",
            files={"image": ("label.jpg", _make_image_bytes(), "image/jpeg")},
            data=_APPLICATION_FORM,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["overall_verdict"] == "FAIL"
        brand_field = next(f for f in body["fields"] if f["field"] == "brand_name")
        assert brand_field["verdict"] == "FAIL"

    def test_png_upload_is_accepted(self, client_factory):
        client, _ = client_factory(result=_clear_extraction())
        response = client.post(
            "/api/verify",
            files={"image": ("label.png", _make_image_bytes(fmt="PNG"), "image/png")},
            data=_APPLICATION_FORM,
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/verify — NEEDS BETTER IMAGE short-circuit
# ---------------------------------------------------------------------------


class TestVerifyShortCircuit:
    def test_partial_legibility_short_circuits(self, client_factory):
        client, _ = client_factory(result=_clear_extraction(legibility="partial"))
        response = client.post(
            "/api/verify",
            files={"image": ("label.jpg", _make_image_bytes(), "image/jpeg")},
            data=_APPLICATION_FORM,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["overall_verdict"] == "NEEDS BETTER IMAGE"
        assert body["fields"] == []

    def test_unreadable_legibility_short_circuits(self, client_factory):
        client, _ = client_factory(result=_clear_extraction(legibility="unreadable"))
        response = client.post(
            "/api/verify",
            files={"image": ("label.jpg", _make_image_bytes(), "image/jpeg")},
            data=_APPLICATION_FORM,
        )
        body = response.json()
        assert body["overall_verdict"] == "NEEDS BETTER IMAGE"
        assert body["fields"] == []


# ---------------------------------------------------------------------------
# POST /api/verify — upload validation (SPEC section 10)
# ---------------------------------------------------------------------------


class TestVerifyUploadValidation:
    def test_oversized_image_rejected(self, client_factory):
        client, fake = client_factory(result=_clear_extraction())
        oversized = b"\xff" * (IMAGE_MAX_MB * 1024 * 1024 + 1)
        response = client.post(
            "/api/verify",
            files={"image": ("label.jpg", oversized, "image/jpeg")},
            data=_APPLICATION_FORM,
        )
        assert response.status_code == 400
        assert str(IMAGE_MAX_MB) in response.json()["detail"]
        assert fake.calls == []

    def test_wrong_file_type_rejected(self, client_factory):
        client, fake = client_factory(result=_clear_extraction())
        response = client.post(
            "/api/verify",
            files={"image": ("label.pdf", b"%PDF-1.4 not an image", "application/pdf")},
            data=_APPLICATION_FORM,
        )
        assert response.status_code == 400
        assert response.json()["detail"] == (
            "That file isn't an image we support. Please upload a JPEG or PNG."
        )
        assert fake.calls == []

    def test_declared_type_lying_about_garbage_bytes_rejected(self, client_factory):
        # content-type header says image/jpeg but the bytes aren't a real image
        client, fake = client_factory(result=_clear_extraction())
        response = client.post(
            "/api/verify",
            files={"image": ("label.jpg", b"this is not actually a jpeg", "image/jpeg")},
            data=_APPLICATION_FORM,
        )
        assert response.status_code == 400
        assert fake.calls == []


# ---------------------------------------------------------------------------
# POST /api/verify — extraction failure (SPEC section 8 timeout policy)
# ---------------------------------------------------------------------------


class TestVerifyExtractionFailure:
    def test_extraction_error_returns_clean_failure_state(self, client_factory):
        client, _ = client_factory(error=ExtractionError("vision call timed out"))
        response = client.post(
            "/api/verify",
            files={"image": ("label.jpg", _make_image_bytes(), "image/jpeg")},
            data=_APPLICATION_FORM,
        )
        assert response.status_code == 504
        assert response.json()["detail"] == "Verification took too long. Please try again."


# ---------------------------------------------------------------------------
# POST /api/verify-batch — pre-flight validation (SPEC section 9)
# ---------------------------------------------------------------------------


def _csv_bytes(rows, header=None):
    header = header or [
        "image_filename", "brand_name", "class_type", "alcohol_content",
        "net_contents", "beverage_type",
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _valid_batch_rows(n=2):
    return [
        [f"label{i}.jpg", "Old Tom Distillery", "Kentucky Straight Bourbon Whiskey", "45", "750 mL", "distilled_spirits"]
        for i in range(1, n + 1)
    ]


class TestBatchPreflightValidation:
    def test_invalid_beverage_type_rejects_whole_batch(self, client_factory):
        client, fake = client_factory(result=_clear_extraction())
        rows = _valid_batch_rows(1)
        rows[0][5] = "whiskey"  # not one of distilled_spirits | wine | beer
        response = client.post(
            "/api/verify-batch",
            files=[
                ("csv", ("batch.csv", _csv_bytes(rows), "text/csv")),
                ("images", ("label1.jpg", _make_image_bytes(), "image/jpeg")),
            ],
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert len(detail["row_errors"]) == 1
        assert detail["row_errors"][0]["row"] == 1
        assert fake.calls == []

    def test_non_numeric_alcohol_content_rejects_whole_batch(self, client_factory):
        client, _ = client_factory(result=_clear_extraction())
        rows = _valid_batch_rows(1)
        rows[0][3] = "forty-five"
        response = client.post(
            "/api/verify-batch",
            files=[
                ("csv", ("batch.csv", _csv_bytes(rows), "text/csv")),
                ("images", ("label1.jpg", _make_image_bytes(), "image/jpeg")),
            ],
        )
        assert response.status_code == 400
        assert response.json()["detail"]["row_errors"]

    def test_filename_not_matching_any_upload_rejects_batch(self, client_factory):
        client, _ = client_factory(result=_clear_extraction())
        rows = _valid_batch_rows(1)
        response = client.post(
            "/api/verify-batch",
            files=[
                ("csv", ("batch.csv", _csv_bytes(rows), "text/csv")),
                ("images", ("some_other_file.jpg", _make_image_bytes(), "image/jpeg")),
            ],
        )
        assert response.status_code == 400
        assert response.json()["detail"]["row_errors"]

    def test_batch_over_row_cap_rejected(self, client_factory):
        client, _ = client_factory(result=_clear_extraction())
        rows = _valid_batch_rows(BATCH_MAX_ROWS + 1)
        images = [
            ("images", (f"label{i}.jpg", _make_image_bytes(), "image/jpeg"))
            for i in range(1, BATCH_MAX_ROWS + 2)
        ]
        response = client.post(
            "/api/verify-batch",
            files=[("csv", ("batch.csv", _csv_bytes(rows), "text/csv"))] + images,
        )
        assert response.status_code == 400
        assert str(BATCH_MAX_ROWS) in json.dumps(response.json())

    def test_wrong_csv_header_rejected(self, client_factory):
        client, _ = client_factory(result=_clear_extraction())
        rows = [["label1.jpg", "X", "Y", "45", "750 mL", "distilled_spirits"]]
        bad_header = ["filename", "brand", "class_type", "alcohol_content", "net_contents", "beverage_type"]
        response = client.post(
            "/api/verify-batch",
            files=[
                ("csv", ("batch.csv", _csv_bytes(rows, header=bad_header), "text/csv")),
                ("images", ("label1.jpg", _make_image_bytes(), "image/jpeg")),
            ],
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/verify-batch + GET /api/batch/{id} — happy path (SPEC section 9)
# ---------------------------------------------------------------------------


class TestBatchHappyPath:
    def test_batch_processes_sequentially_and_reports_done(self, client_factory):
        client, fake = client_factory(result=_clear_extraction())
        rows = _valid_batch_rows(2)
        response = client.post(
            "/api/verify-batch",
            files=[
                ("csv", ("batch.csv", _csv_bytes(rows), "text/csv")),
                ("images", ("label1.jpg", _make_image_bytes(), "image/jpeg")),
                ("images", ("label2.jpg", _make_image_bytes(), "image/jpeg")),
            ],
        )
        assert response.status_code == 202
        assert response.json()["row_count"] == 2
        assert response.json()["unreferenced_images"] == []
        batch_id = response.json()["batch_id"]

        status_response = client.get(f"/api/batch/{batch_id}")
        assert status_response.status_code == 200
        body = status_response.json()
        assert body["batch_id"] == batch_id
        assert body["status"] == "done"
        assert len(body["rows"]) == 2
        for row in body["rows"]:
            assert row["status"] == "done"
            assert row["result"]["overall_verdict"] == "PASS"
            assert row["error"] is None

        assert len(fake.calls) == 2

    def test_unreferenced_uploaded_images_are_reported_but_do_not_block(self, client_factory):
        # Dogfooding finding: uploading more images than the CSV references
        # (e.g. leftover files from a wider selection) must not error or
        # block the run — the CSV is the source of truth — but it also
        # shouldn't be silently swallowed. The extras come back as a notice
        # alongside the normal batch_id/row_count response.
        client, fake = client_factory(result=_clear_extraction())
        rows = _valid_batch_rows(2)  # references label1.jpg, label2.jpg
        response = client.post(
            "/api/verify-batch",
            files=[
                ("csv", ("batch.csv", _csv_bytes(rows), "text/csv")),
                ("images", ("label1.jpg", _make_image_bytes(), "image/jpeg")),
                ("images", ("label2.jpg", _make_image_bytes(), "image/jpeg")),
                ("images", ("t7_bad_image_glare.png", _make_image_bytes(), "image/jpeg")),
                ("images", ("t8_wine_no_abv.png", _make_image_bytes(), "image/jpeg")),
            ],
        )
        assert response.status_code == 202
        body = response.json()
        assert body["row_count"] == 2
        assert body["unreferenced_images"] == ["t7_bad_image_glare.png", "t8_wine_no_abv.png"]

        # the run itself proceeds normally for the referenced rows only
        status_response = client.get(f"/api/batch/{body['batch_id']}")
        status_body = status_response.json()
        assert len(status_body["rows"]) == 2
        assert status_body["status"] == "done"
        assert len(fake.calls) == 2

    def test_one_row_extraction_failure_does_not_abort_other_rows(self, client_factory):
        client, fake = client_factory(
            per_call={0: ExtractionError("boom"), 1: _clear_extraction()}
        )
        rows = _valid_batch_rows(2)
        response = client.post(
            "/api/verify-batch",
            files=[
                ("csv", ("batch.csv", _csv_bytes(rows), "text/csv")),
                ("images", ("label1.jpg", _make_image_bytes(), "image/jpeg")),
                ("images", ("label2.jpg", _make_image_bytes(), "image/jpeg")),
            ],
        )
        batch_id = response.json()["batch_id"]
        body = client.get(f"/api/batch/{batch_id}").json()

        statuses = {row["filename"]: row["status"] for row in body["rows"]}
        assert statuses["label1.jpg"] == "failed"
        assert statuses["label2.jpg"] == "done"
        assert len(fake.calls) == 2

    def test_unknown_batch_id_returns_404(self, client_factory):
        client, _ = client_factory(result=_clear_extraction())
        response = client.get("/api/batch/does-not-exist")
        assert response.status_code == 404
