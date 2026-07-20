# TTB Label Verification Prototype — Specification

Design principle: **the LLM extracts, code decides.** All compliance logic is
deterministic, unit-tested, and explainable. The model never renders a verdict.

---

## 1. Fields Verified

| Field | Match Type |
|---|---|
| Brand name | Normalized fuzzy (3-tier) |
| Class/type | Normalized fuzzy, loose (3-tier) |
| Alcohol content | Parsed numeric, exact |
| Net contents | Parsed numeric + unit, exact |
| Government warning | Two-part strict (see §4) |

## 2. Verdict Vocabulary

Per-field and overall verdicts: `PASS` / `FLAG` / `FAIL` / `NEEDS BETTER IMAGE`.

- Overall verdict = worst field verdict.
- Precedence: `NEEDS BETTER IMAGE` > `FAIL` > `FLAG` > `PASS`
  (if the label can't be read, no compliance verdict is rendered).
- Any field with `low` extraction confidence caps at `FLAG` regardless of
  match result.
- `FLAG` always routes to human judgment. The tool is decision support,
  never a decision-maker.

## 3. Field Comparison Rules

### Brand name
1. Exact match → PASS
2. Normalize both sides (uppercase, collapse whitespace, strip trailing
   punctuation, unify apostrophe variants ' vs ') → match → PASS with note
   "case/punctuation variance"
3. Levenshtein similarity ≥ 0.85 (normalized) → FLAG, show both strings
4. Below threshold → FAIL

### Class/type
1. Exact normalized match → PASS
2. Token-subset or similarity ≥ 0.70 → FLAG
3. Disjoint → FAIL
(Loose by design — legitimate variance is common; false FAILs destroy trust.)

### Alcohol content (ABV)
- Regex-extract percentage from both sides ("45% Alc./Vol.", "45% ABV",
  "ALC 45% BY VOL" all → 45.0). Compare floats.
- Format variance is legal; value variance is not. Tolerance = 0.0.
- If label shows proof, validate proof = 2 × ABV as internal consistency
  check; mismatch → FLAG (label internally inconsistent).
- Parse failure → FLAG, never FAIL.

### Net contents
- Parse quantity + unit ("750 mL" / "750ml" / "750 ML" → (750, ml)).
- Numeric compare, tolerance = 0.0.
- Unit conversion enabled (75 cL == 750 mL → PASS with note).

### Government warning — two-part strict rule (27 CFR Part 16)
1. `present == false` → FAIL
2. Normalize whitespace ONLY (collapse runs, strip line breaks — labels
   legally wrap text). Do NOT normalize case.
3. **Prefix**: case-sensitive compare, must be exactly `GOVERNMENT WARNING:`
4. **Body**: case-insensitive word-for-word compare against statutory text.
   Tokenize on whitespace, strip `.,;` from token edges. Any added/dropped/
   changed word → FAIL, with word-level diff in output. The (1) and (2)
   numerals are required tokens.
5. Body matches but internal casing deviates → FLAG
6. `prefix_appears_bold == false` → FLAG (advisory — visual judgment,
   human confirms)

## 4. Statutory Warning Constant

Stored as two parts (the structure IS the rule):

```
PREFIX = "GOVERNMENT WARNING:"

BODY = "(1) According to the Surgeon General, women should not drink
alcoholic beverages during pregnancy because of the risk of birth defects.
(2) Consumption of alcoholic beverages impairs your ability to drive a car
or operate machinery, and may cause health problems."
```

## 5. Extraction Prompt (vision API, temperature 0, single call)

```
You are extracting text from an alcohol beverage label image for TTB
compliance review. Extract EXACTLY what appears on the label,
character-for-character, preserving case, punctuation, and spacing.
Do not correct, normalize, or interpret.

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
- For government_warning.verbatim_text, transcribe every word exactly as
  printed, including capitalization.
- prefix_appears_bold: judge only whether "GOVERNMENT WARNING:" is visually
  bolder than surrounding text.
- Return JSON only, no commentary.
```

If `legibility` is `partial` or `unreadable` → short-circuit to
NEEDS BETTER IMAGE. No field verdicts rendered.

## 6. Response Envelope

```json
{
  "overall_verdict": "FAIL",
  "processing_time_ms": 3240,
  "image_quality": {"legibility": "clear", "issues": []},
  "fields": [
    {
      "field": "government_warning",
      "verdict": "FAIL",
      "reason": "Body text deviates from statutory warning: 1 word changed, 1 word missing",
      "evidence": {
        "expected": "...statutory text...",
        "extracted": "...label text...",
        "diff": [
          {"op": "equal",   "text": "impairs your ability to"},
          {"op": "replace", "expected": "drive", "found": "operate"},
          {"op": "delete",  "expected": "a car or"},
          {"op": "equal",   "text": "operate machinery"}
        ]
      }
    }
  ]
}
```

- Diff ops vocabulary: `equal | replace | delete | insert`
  (maps to difflib.SequenceMatcher opcodes).
- Runs of equal words collapsed into single chunks.
- Same envelope for every field; only the warning's evidence contains `diff`.
  Brand evidence: `{application, extracted, similarity}`.
- `reason` is always a plain-language human sentence.
- `processing_time_ms` in every response (proves the 5-second requirement).

## 7. Thresholds (thresholds.py — single source of tunables)

```python
BRAND_SIMILARITY_FLAG_FLOOR = 0.85
CLASS_TYPE_SIMILARITY_FLAG_FLOOR = 0.70
ABV_TOLERANCE = 0.0
NET_CONTENTS_TOLERANCE = 0.0
CONVERT_UNITS = True          # 75 cL == 750 mL -> PASS with note
VISION_TIMEOUT_SECONDS = 10
VISION_RETRIES = 1
BATCH_MAX_ROWS = 300
IMAGE_MAX_MB = 10
IMAGE_LONG_EDGE_PX = 1568
MODEL_NAME = "claude-haiku-4-5-20251001"
```

## 8. API Contract

- `POST /api/verify` — multipart: `image` file + form fields
  `brand_name, class_type, alcohol_content, net_contents, beverage_type`.
  Returns response envelope.
- `POST /api/verify-batch` — multipart: `csv` + multiple images.
  Returns `batch_id`; poll per-row status.
- `GET /api/batch/{id}` — row statuses + completed results.
- `GET /api/health` — `{status, model_name}`.

Timeout policy: 10s hard timeout on vision call, 1 retry on transient
failure, then clean "verification failed, try again" state. Never a
hanging spinner.

## 9. Batch Semantics

- CSV schema:
  `image_filename,brand_name,class_type,alcohol_content,net_contents,beverage_type`
- `alcohol_content` = bare number; `beverage_type` ∈
  `distilled_spirits | wine | beer`; filenames must exactly match uploads.
- Pre-flight validation rejects the whole batch with row-level errors —
  never fail mid-run.
- Sequential processing, visible per-row progress
  (pending → processing → done), cap 300 rows.
- Results table with verdict chips + CSV export.

## 10. Image Handling

- Accepted: JPEG/PNG (WebP optional). Max 10MB.
- Downscale long edge to ~1568px before API call.
- Unreadable/partial legibility → NEEDS BETTER IMAGE verdict with
  resubmission message (mirrors current agent practice).
- No image enhancement — bad photos are detected and routed, not corrected.

## 11. UI (single screen — the "Sarah's mother" test)

Upload zone + five-field form + "Verify Label" button → results panel,
color-coded field rows, image alongside. Batch behind a tab, not default.

Copy strings:
- Upload zone: "Drop label image here or tap to browse (JPEG/PNG, max 10MB)"
- PASS chip (green): "Matches application"
- FLAG chip (amber): "Needs your review"
- FAIL chip (red): "Does not match"
- NEEDS BETTER IMAGE: "We couldn't read this label clearly. Please request
  a clearer photo — straight-on, good lighting, no glare."
- Timeout: "Verification took too long. Please try again."
- Wrong file type: "That file isn't an image we support. Please upload a
  JPEG or PNG."
- Empty field: inline "Required", button disabled until complete.

Diff rendering: equal = plain; replace = red strikethrough → green
replacement; delete = red strikethrough; insert = green highlight.
Legend: "Red = on label but wrong / missing · Green = required text".

## 12. Test Matrix (test_labels/ — acceptance suite + demo script)

| ID | File | Scenario | Expected |
|---|---|---|---|
| T1 | clean_pass.png | Bourbon, all fields match, correct bold warning | PASS (all fields) |
| T2 | brand_case_variant.png | Label STONE'S THROW vs app Stone's Throw | PASS + variance note |
| T3 | warning_title_case.png | Prefix "Government Warning:" title case | FAIL (prefix case) |
| T4 | warning_word_swap.png | One word changed in warning body | FAIL + replace op in diff |
| T5 | warning_missing.png | No warning on label | FAIL (present: false) |
| T6 | abv_mismatch.png | App 45%, label 40% (80 Proof) | FAIL (45.0 vs 40.0) |
| T7 | bad_image_glare.png | Heavy glare/angle | NEEDS BETTER IMAGE |
| T8 | wine_no_abv.png | Wine, no ABV stated (legal) | PASS w/ "not stated — permitted" (or FLAG; document choice) |

Stretch: T9 net-contents unit variant (75 cL vs 750 mL), T10 batch CSV of T1–T6.

App data for T1: OLD TOM DISTILLERY / Kentucky Straight Bourbon Whiskey /
45 / 750 mL / distilled_spirits.

Demo order (tells the story accurate → nuanced → strict → honest → scalable):
T1 → T2 → T4 → T3 → T7 → batch.

## 13. Build Order

1. Scaffold, pydantic models, thresholds, warning constant (~20 min)
2. comparators.py + full test suite — all green, zero API calls (60–90 min)
3. extraction.py client + prompt (~30 min)
4. FastAPI endpoints end-to-end, test with T1 (~30 min)
5. Frontend single-screen flow + results + diff component (2–3 hrs)
6. Batch path (1–2 hrs) ← cut-line if time compresses
7. Generate T1–T8, run demo script, fix surprises (~1 hr)
8. Deploy (Railway), smoke test, finalize README (~45 min)

## 14. Repo Structure

```
ttb-label-verify/
├── README.md
├── SPEC.md
├── docs/adr/
├── backend/
│   ├── app.py              # FastAPI routes
│   ├── extraction.py       # vision API client (swappable)
│   ├── comparators.py      # five field comparators
│   ├── warning_text.py     # statutory constant (prefix + body)
│   ├── thresholds.py       # all tunable values
│   ├── models.py           # pydantic schemas
│   └── tests/test_comparators.py
├── frontend/               # Vite + React
└── test_labels/            # T1–T8 images + batch.csv
```

Comparator design: a FieldComparator interface (normalize, compare →
{verdict, reason, evidence}), one implementation per field, fully
unit-testable without API calls.
