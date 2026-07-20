"""FastAPI endpoints — SPEC.md section 8 (API contract), section 9 (batch
semantics), section 10 (image handling).

Pipeline: validate upload -> VisionExtractor.extract -> needs_better_image
short-circuit -> comparators -> ResponseEnvelope. /api/verify and the batch
row processor share the same pipeline (_run_verification) so there is
exactly one place that wiring can drift.
"""

import csv
import io
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
from starlette.concurrency import run_in_threadpool

from comparators import (
    compare_alcohol_content,
    compare_brand_name,
    compare_class_type,
    compare_government_warning,
    compare_net_contents,
)
from extraction import ExtractionError, VisionExtractor, needs_better_image
from models import FieldResult, ImageQuality, ResponseEnvelope, worst_verdict
from thresholds import BATCH_MAX_ROWS, IMAGE_MAX_MB, MODEL_NAME

app = FastAPI(title="TTB Label Verification")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_extractor() -> VisionExtractor:
    # Constructed lazily, once per process, on first real request that needs
    # it — never at import time, so `import app` doesn't require
    # ANTHROPIC_API_KEY to be set (tests override this dependency entirely).
    if not hasattr(get_extractor, "_instance"):
        get_extractor._instance = VisionExtractor()
    return get_extractor._instance


@app.get("/api/health")
def health():
    return {"status": "ok", "model_name": MODEL_NAME}


# ---------------------------------------------------------------------------
# Shared application-data shape and verification pipeline
# ---------------------------------------------------------------------------


@dataclass
class ApplicationData:
    brand_name: str
    class_type: str
    alcohol_content: str
    net_contents: str
    beverage_type: str


async def _run_verification(
    extractor: VisionExtractor, image_bytes: bytes, media_type: str, application: ApplicationData
) -> dict:
    start = time.monotonic()
    extraction = await run_in_threadpool(extractor.extract, image_bytes, media_type)

    image_quality = ImageQuality(
        legibility=extraction.government_warning.legibility,
        issues=extraction.image_quality_issues,
    )

    if needs_better_image(extraction):
        envelope = ResponseEnvelope(
            overall_verdict="NEEDS BETTER IMAGE",
            processing_time_ms=int((time.monotonic() - start) * 1000),
            image_quality=image_quality,
            fields=[],
        )
        return envelope.to_wire_dict()

    confidence = extraction.extraction_confidence
    field_results = [
        FieldResult.from_comparator_result(
            compare_brand_name(application.brand_name, extraction.brand_name, confidence=confidence.brand_name)
        ),
        FieldResult.from_comparator_result(
            compare_class_type(application.class_type, extraction.class_type, confidence=confidence.class_type)
        ),
        FieldResult.from_comparator_result(
            compare_alcohol_content(
                application.alcohol_content,
                extraction.alcohol_content,
                beverage_type=application.beverage_type,
                confidence=confidence.alcohol_content,
            )
        ),
        FieldResult.from_comparator_result(
            compare_net_contents(
                application.net_contents, extraction.net_contents, confidence=confidence.net_contents
            )
        ),
        FieldResult.from_comparator_result(
            compare_government_warning(
                extraction.government_warning.model_dump(), confidence=confidence.government_warning
            )
        ),
    ]

    envelope = ResponseEnvelope(
        overall_verdict=worst_verdict([f.verdict for f in field_results]),
        processing_time_ms=int((time.monotonic() - start) * 1000),
        image_quality=image_quality,
        fields=field_results,
    )
    return envelope.to_wire_dict()


# ---------------------------------------------------------------------------
# Image upload validation — SPEC section 10
# ---------------------------------------------------------------------------

_ALLOWED_IMAGE_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def _detect_image_format(data: bytes) -> Optional[str]:
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            return img.format
    except Exception:
        return None


def _validate_image_upload(data: bytes) -> str:
    """Returns the media type on success; raises HTTPException otherwise.
    Format is verified by decoding the bytes, not by trusting the
    client-declared content-type header."""
    if len(data) > IMAGE_MAX_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"Image exceeds the {IMAGE_MAX_MB}MB limit. Please upload a smaller file.",
        )
    image_format = _detect_image_format(data)
    if image_format not in _ALLOWED_IMAGE_FORMATS:
        raise HTTPException(
            status_code=400,
            detail="That file isn't an image we support. Please upload a JPEG or PNG.",
        )
    return _ALLOWED_IMAGE_FORMATS[image_format]


# ---------------------------------------------------------------------------
# POST /api/verify
# ---------------------------------------------------------------------------


@app.post("/api/verify")
async def verify(
    image: UploadFile = File(...),
    brand_name: str = Form(...),
    class_type: str = Form(...),
    alcohol_content: str = Form(...),
    net_contents: str = Form(...),
    beverage_type: str = Form(...),
    extractor: VisionExtractor = Depends(get_extractor),
):
    image_bytes = await image.read()
    media_type = _validate_image_upload(image_bytes)

    application = ApplicationData(
        brand_name=brand_name,
        class_type=class_type,
        alcohol_content=alcohol_content,
        net_contents=net_contents,
        beverage_type=beverage_type,
    )

    try:
        return await _run_verification(extractor, image_bytes, media_type, application)
    except ExtractionError:
        # SPEC section 8: 10s timeout, 1 retry, then a clean failure state —
        # never a hanging spinner.
        raise HTTPException(status_code=504, detail="Verification took too long. Please try again.")


# ---------------------------------------------------------------------------
# Batch — SPEC section 9
# ---------------------------------------------------------------------------

_EXPECTED_CSV_COLUMNS = [
    "image_filename", "brand_name", "class_type", "alcohol_content", "net_contents", "beverage_type",
]
_BEVERAGE_TYPES = {"distilled_spirits", "wine", "beer"}
_BARE_NUMBER_RE = re.compile(r"^\d+(\.\d+)?$")


@dataclass
class BatchRow:
    row_number: int
    filename: str
    application: ApplicationData
    status: str = "pending"  # pending | processing | done | failed
    result: Optional[dict] = None
    error: Optional[str] = None


@dataclass
class Batch:
    batch_id: str
    rows: List[BatchRow]


_BATCHES: dict = {}


def _batch_error(message: str, errors=None, row_errors=None) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"message": message, "errors": errors or [], "row_errors": row_errors or []},
    )


def _validate_batch_row(row: dict, uploaded_filenames: set) -> List[str]:
    errors = []
    filename = (row.get("image_filename") or "").strip()
    if not filename:
        errors.append("image_filename is required.")
    elif filename not in uploaded_filenames:
        errors.append(f"image_filename '{filename}' does not match any uploaded file.")

    for field in ("brand_name", "class_type", "net_contents"):
        if not (row.get(field) or "").strip():
            errors.append(f"{field} is required.")

    alcohol_content = (row.get("alcohol_content") or "").strip()
    if not alcohol_content:
        errors.append("alcohol_content is required.")
    elif not _BARE_NUMBER_RE.match(alcohol_content):
        errors.append("alcohol_content must be a bare number (e.g. 45), not label-style text.")

    beverage_type = (row.get("beverage_type") or "").strip()
    if beverage_type not in _BEVERAGE_TYPES:
        errors.append(f"beverage_type must be one of: {', '.join(sorted(_BEVERAGE_TYPES))}.")

    return errors


async def _preflight_validate_batch(csv_bytes: bytes, images: List[UploadFile]):
    """Rejects the whole batch on any problem, with row-level detail where
    possible — SPEC section 9: 'never fail mid-run.' Returns (rows,
    image_payloads) on success."""
    try:
        csv_text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _batch_error("CSV file is not valid UTF-8 text.", errors=["CSV file is not valid UTF-8 text."])

    reader = csv.DictReader(io.StringIO(csv_text))
    if list(reader.fieldnames or []) != _EXPECTED_CSV_COLUMNS:
        raise _batch_error(
            "CSV header is invalid.",
            errors=[f"CSV header must be exactly: {','.join(_EXPECTED_CSV_COLUMNS)}."],
        )

    rows = list(reader)
    if not rows:
        raise _batch_error("CSV has no data rows.", errors=["CSV has no data rows."])
    if len(rows) > BATCH_MAX_ROWS:
        raise _batch_error(
            "Batch exceeds the row limit.",
            errors=[f"Batch exceeds the {BATCH_MAX_ROWS}-row limit (found {len(rows)} rows)."],
        )

    image_payloads = {}
    image_errors = []
    for upload in images:
        data = await upload.read()
        try:
            media_type = _validate_image_upload(data)
        except HTTPException as exc:
            image_errors.append(f"{upload.filename}: {exc.detail}")
            continue
        image_payloads[upload.filename] = (data, media_type)

    if image_errors:
        raise _batch_error("One or more uploaded images are invalid.", errors=image_errors)

    row_errors = []
    for i, row in enumerate(rows, start=1):
        problems = _validate_batch_row(row, set(image_payloads.keys()))
        if problems:
            row_errors.append({"row": i, "filename": row.get("image_filename"), "errors": problems})

    if row_errors:
        raise _batch_error("Batch validation failed.", row_errors=row_errors)

    return rows, image_payloads


async def _process_batch(batch_id: str, image_payloads: dict, extractor: VisionExtractor) -> None:
    batch = _BATCHES.get(batch_id)
    if batch is None:
        return
    for row in batch.rows:
        row.status = "processing"
        data, media_type = image_payloads[row.filename]
        try:
            row.result = await _run_verification(extractor, data, media_type, row.application)
            row.status = "done"
        except ExtractionError:
            row.error = "Verification took too long. Please try again."
            row.status = "failed"


@app.post("/api/verify-batch", status_code=202)
async def verify_batch(
    background_tasks: BackgroundTasks,
    csv: UploadFile = File(...),
    images: List[UploadFile] = File(...),
    extractor: VisionExtractor = Depends(get_extractor),
):
    csv_bytes = await csv.read()
    rows, image_payloads = await _preflight_validate_batch(csv_bytes, images)

    batch_id = str(uuid.uuid4())
    batch_rows = [
        BatchRow(
            row_number=i,
            filename=row["image_filename"],
            application=ApplicationData(
                brand_name=row["brand_name"],
                class_type=row["class_type"],
                alcohol_content=row["alcohol_content"],
                net_contents=row["net_contents"],
                beverage_type=row["beverage_type"],
            ),
        )
        for i, row in enumerate(rows, start=1)
    ]
    _BATCHES[batch_id] = Batch(batch_id=batch_id, rows=batch_rows)

    background_tasks.add_task(_process_batch, batch_id, image_payloads, extractor)

    return {"batch_id": batch_id, "row_count": len(batch_rows)}


@app.get("/api/batch/{batch_id}")
def get_batch(batch_id: str):
    batch = _BATCHES.get(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found.")

    rows = [
        {
            "row": row.row_number,
            "filename": row.filename,
            "status": row.status,
            "result": row.result,
            "error": row.error,
        }
        for row in batch.rows
    ]
    status = "done" if all(row.status in ("done", "failed") for row in batch.rows) else "processing"
    return {"batch_id": batch.batch_id, "status": status, "rows": rows}


# ---------------------------------------------------------------------------
# Static frontend — ADR-005: one Railway service serves both. Mounted last
# so it never shadows the /api/* routes above; absent in local backend-only
# dev (no frontend build alongside app.py) this is simply skipped.
# ---------------------------------------------------------------------------

_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
