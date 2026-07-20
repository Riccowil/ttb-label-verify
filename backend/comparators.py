"""Five field comparators. The LLM extracts, code decides — every function
here is deterministic and fully testable without a network call. See
SPEC.md section 3 for the comparison rules and section 7 (thresholds.py)
for tunables.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from thresholds import (
    ABV_TOLERANCE,
    BRAND_SIMILARITY_FLAG_FLOOR,
    CLASS_TYPE_SIMILARITY_FLAG_FLOOR,
    CONVERT_UNITS,
    NET_CONTENTS_TOLERANCE,
)
from warning_text import BODY, PREFIX

PASS = "PASS"
FLAG = "FLAG"
FAIL = "FAIL"

_EXPECTED_WARNING_TEXT = f"{PREFIX} {BODY}"


@dataclass
class FieldResult:
    field: str
    verdict: str
    reason: str
    evidence: dict


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _normalize_text(value: str) -> str:
    text = value.upper().replace("’", "'").replace("‘", "'")
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(".,;:!?")


def _levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current_row = [i]
        for j, char_b in enumerate(b, start=1):
            current_row.append(
                min(
                    current_row[j - 1] + 1,  # insertion
                    previous_row[j] + 1,  # deletion
                    previous_row[j - 1] + (char_a != char_b),  # substitution
                )
            )
        previous_row = current_row
    return previous_row[-1]


def _levenshtein_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return 1.0 - (_levenshtein_distance(a, b) / max(len(a), len(b)))


def _apply_confidence_cap(result: FieldResult, confidence: str) -> FieldResult:
    """SPEC section 2: low extraction confidence caps the verdict at FLAG
    regardless of what the comparison itself found — we don't confidently
    PASS or FAIL a field the model itself wasn't sure it read correctly."""
    if confidence != "low" or result.verdict == FLAG:
        return result
    return FieldResult(
        field=result.field,
        verdict=FLAG,
        reason=f"Low extraction confidence — {result.reason}",
        evidence=result.evidence,
    )


# ---------------------------------------------------------------------------
# Brand name — SPEC section 3 "Brand name"
# ---------------------------------------------------------------------------


def compare_brand_name(
    application_value: str, extracted_value: Optional[str], confidence: str = "high"
) -> FieldResult:
    return _apply_confidence_cap(
        _compare_brand_name(application_value, extracted_value), confidence
    )


def _compare_brand_name(application_value: str, extracted_value: Optional[str]) -> FieldResult:
    field_name = "brand_name"

    if extracted_value is None:
        return FieldResult(
            field=field_name,
            verdict=FAIL,
            reason="Brand name not found on label.",
            evidence={"application": application_value, "extracted": None, "similarity": 0.0},
        )

    if application_value == extracted_value:
        return FieldResult(
            field=field_name,
            verdict=PASS,
            reason="Brand name matches application exactly.",
            evidence={"application": application_value, "extracted": extracted_value, "similarity": 1.0},
        )

    normalized_app = _normalize_text(application_value)
    normalized_ext = _normalize_text(extracted_value)

    if normalized_app == normalized_ext:
        return FieldResult(
            field=field_name,
            verdict=PASS,
            reason="Brand name matches application (case/punctuation variance).",
            evidence={"application": application_value, "extracted": extracted_value, "similarity": 1.0},
        )

    similarity = _levenshtein_similarity(normalized_app, normalized_ext)
    evidence = {"application": application_value, "extracted": extracted_value, "similarity": similarity}

    if similarity >= BRAND_SIMILARITY_FLAG_FLOOR:
        return FieldResult(
            field=field_name,
            verdict=FLAG,
            reason=f"Brand name is similar but not identical to application (similarity {similarity:.2f}).",
            evidence=evidence,
        )

    return FieldResult(
        field=field_name,
        verdict=FAIL,
        reason=f"Brand name does not match application (similarity {similarity:.2f}).",
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Class/type — SPEC section 3 "Class/type"
# ---------------------------------------------------------------------------


def compare_class_type(
    application_value: str, extracted_value: Optional[str], confidence: str = "high"
) -> FieldResult:
    return _apply_confidence_cap(
        _compare_class_type(application_value, extracted_value), confidence
    )


def _compare_class_type(application_value: str, extracted_value: Optional[str]) -> FieldResult:
    field_name = "class_type"

    if extracted_value is None:
        return FieldResult(
            field=field_name,
            verdict=FAIL,
            reason="Class/type not found on label.",
            evidence={"application": application_value, "extracted": None, "similarity": 0.0},
        )

    normalized_app = _normalize_text(application_value)
    normalized_ext = _normalize_text(extracted_value)
    evidence_base = {"application": application_value, "extracted": extracted_value}

    if normalized_app == normalized_ext:
        return FieldResult(
            field=field_name,
            verdict=PASS,
            reason="Class/type matches application.",
            evidence={**evidence_base, "similarity": 1.0},
        )

    tokens_app = set(normalized_app.split())
    tokens_ext = set(normalized_ext.split())
    token_subset = bool(tokens_app) and bool(tokens_ext) and (
        tokens_app <= tokens_ext or tokens_ext <= tokens_app
    )
    similarity = _levenshtein_similarity(normalized_app, normalized_ext)
    evidence = {**evidence_base, "similarity": similarity}

    if token_subset or similarity >= CLASS_TYPE_SIMILARITY_FLAG_FLOOR:
        return FieldResult(
            field=field_name,
            verdict=FLAG,
            reason=f"Class/type differs from application but overlaps significantly (similarity {similarity:.2f}).",
            evidence=evidence,
        )

    return FieldResult(
        field=field_name,
        verdict=FAIL,
        reason=f"Class/type does not match application (similarity {similarity:.2f}).",
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Alcohol content — SPEC section 3 "Alcohol content (ABV)"
# ---------------------------------------------------------------------------

_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_BARE_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*$")
_PROOF_RE = re.compile(r"(\d+(?:\.\d+)?)\s*proof", re.IGNORECASE)


def _parse_abv_percentage(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    match = _PERCENT_RE.search(text)
    if match:
        return float(match.group(1))
    match = _BARE_NUMBER_RE.match(text)
    if match:
        return float(match.group(1))
    return None


def _parse_proof(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    match = _PROOF_RE.search(text)
    return float(match.group(1)) if match else None


def compare_alcohol_content(
    application_value: str,
    extracted_value: Optional[str],
    beverage_type: Optional[str] = None,
    confidence: str = "high",
) -> FieldResult:
    return _apply_confidence_cap(
        _compare_alcohol_content(application_value, extracted_value, beverage_type), confidence
    )


def _compare_alcohol_content(
    application_value: str, extracted_value: Optional[str], beverage_type: Optional[str]
) -> FieldResult:
    field_name = "alcohol_content"
    evidence = {"application": application_value, "extracted": extracted_value}

    if extracted_value is None:
        # Wine is legally permitted to omit ABV on the label — TTB does not
        # require it below a strength threshold. Other beverage types must
        # state it, so a null there is a review flag, not an auto-pass.
        if beverage_type == "wine":
            return FieldResult(
                field=field_name,
                verdict=PASS,
                reason="Alcohol content not stated on label — permitted for wine under TTB regulations.",
                evidence=evidence,
            )
        return FieldResult(
            field=field_name,
            verdict=FLAG,
            reason="Alcohol content not stated on label.",
            evidence=evidence,
        )

    app_abv = _parse_abv_percentage(application_value)
    ext_abv = _parse_abv_percentage(extracted_value)

    if app_abv is None or ext_abv is None:
        return FieldResult(
            field=field_name,
            verdict=FLAG,
            reason="Could not parse alcohol content for comparison.",
            evidence=evidence,
        )

    if abs(app_abv - ext_abv) > ABV_TOLERANCE:
        return FieldResult(
            field=field_name,
            verdict=FAIL,
            reason=f"Alcohol content mismatch: application states {app_abv}%, label states {ext_abv}%.",
            evidence=evidence,
        )

    ext_proof = _parse_proof(extracted_value)
    if ext_proof is not None and abs(ext_proof - 2 * ext_abv) > 0.01:
        return FieldResult(
            field=field_name,
            verdict=FLAG,
            reason=(
                f"Label is internally inconsistent: {ext_abv}% ABV implies {2 * ext_abv} proof, "
                f"label states {ext_proof} proof."
            ),
            evidence=evidence,
        )

    return FieldResult(
        field=field_name,
        verdict=PASS,
        reason="Alcohol content matches application.",
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Net contents — SPEC section 3 "Net contents"
# ---------------------------------------------------------------------------

_NET_CONTENTS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mL|cL|L)\b", re.IGNORECASE)
_UNIT_TO_ML = {"ml": 1.0, "cl": 10.0, "l": 1000.0}


def _parse_net_contents(text: Optional[str]):
    if text is None:
        return None
    match = _NET_CONTENTS_RE.search(text)
    if not match:
        return None
    return float(match.group(1)), match.group(2).lower()


def compare_net_contents(
    application_value: str, extracted_value: Optional[str], confidence: str = "high"
) -> FieldResult:
    return _apply_confidence_cap(
        _compare_net_contents(application_value, extracted_value), confidence
    )


def _compare_net_contents(application_value: str, extracted_value: Optional[str]) -> FieldResult:
    field_name = "net_contents"
    evidence = {"application": application_value, "extracted": extracted_value}

    app_parsed = _parse_net_contents(application_value)
    ext_parsed = _parse_net_contents(extracted_value)

    if app_parsed is None or ext_parsed is None:
        return FieldResult(
            field=field_name,
            verdict=FLAG,
            reason="Could not parse net contents for comparison.",
            evidence=evidence,
        )

    app_qty, app_unit = app_parsed
    ext_qty, ext_unit = ext_parsed

    if not CONVERT_UNITS and app_unit != ext_unit:
        return FieldResult(
            field=field_name,
            verdict=FLAG,
            reason="Net contents units differ and unit conversion is disabled.",
            evidence=evidence,
        )

    app_ml = app_qty * _UNIT_TO_ML[app_unit]
    ext_ml = ext_qty * _UNIT_TO_ML[ext_unit]

    if abs(app_ml - ext_ml) > NET_CONTENTS_TOLERANCE:
        return FieldResult(
            field=field_name,
            verdict=FAIL,
            reason=f"Net contents mismatch: application states {app_qty} {app_unit}, label states {ext_qty} {ext_unit}.",
            evidence=evidence,
        )

    if app_unit != ext_unit:
        return FieldResult(
            field=field_name,
            verdict=PASS,
            reason=f"Net contents match after unit conversion ({app_qty} {app_unit} = {ext_qty} {ext_unit}).",
            evidence=evidence,
        )

    return FieldResult(
        field=field_name,
        verdict=PASS,
        reason="Net contents match application.",
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Government warning — SPEC section 3 "two-part strict rule" (27 CFR Part 16)
# ---------------------------------------------------------------------------


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _tokenize(text: str):
    return [tok.strip(".,;") for tok in text.split() if tok.strip(".,;")]


def compare_government_warning(extracted: dict, confidence: str = "high") -> FieldResult:
    return _apply_confidence_cap(_compare_government_warning(extracted), confidence)


def _compare_government_warning(extracted: dict) -> FieldResult:
    field_name = "government_warning"
    present = extracted.get("present", False)
    verbatim_text = extracted.get("verbatim_text")

    if not present or not verbatim_text:
        return FieldResult(
            field=field_name,
            verdict=FAIL,
            reason="Government warning is missing from the label.",
            evidence={
                "expected": _EXPECTED_WARNING_TEXT,
                "extracted": None,
                "diff": [{"op": "delete", "expected": _EXPECTED_WARNING_TEXT}],
            },
        )

    normalized_text = _collapse_whitespace(verbatim_text)

    if not normalized_text.startswith(PREFIX):
        found_prefix = normalized_text[: len(PREFIX)]
        return FieldResult(
            field=field_name,
            verdict=FAIL,
            reason=(
                f"Government warning prefix must read exactly '{PREFIX}' (case-sensitive); "
                f"found '{found_prefix}'."
            ),
            evidence={"expected": PREFIX, "extracted": found_prefix, "diff": None},
        )

    body_text = normalized_text[len(PREFIX) :].strip()

    expected_tokens = _tokenize(BODY)
    found_tokens = _tokenize(body_text)
    expected_casefold = [tok.casefold() for tok in expected_tokens]
    found_casefold = [tok.casefold() for tok in found_tokens]

    opcodes = SequenceMatcher(None, expected_casefold, found_casefold).get_opcodes()

    diff = []
    changed = {"replace": 0, "delete": 0, "insert": 0}
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            diff.append({"op": "equal", "text": " ".join(found_tokens[j1:j2])})
        elif tag == "replace":
            diff.append(
                {
                    "op": "replace",
                    "expected": " ".join(expected_tokens[i1:i2]),
                    "found": " ".join(found_tokens[j1:j2]),
                }
            )
            changed["replace"] += i2 - i1
        elif tag == "delete":
            diff.append({"op": "delete", "expected": " ".join(expected_tokens[i1:i2])})
            changed["delete"] += i2 - i1
        elif tag == "insert":
            diff.append({"op": "insert", "found": " ".join(found_tokens[j1:j2])})
            changed["insert"] += j2 - j1

    evidence = {"expected": _EXPECTED_WARNING_TEXT, "extracted": verbatim_text, "diff": diff}

    if any(tag != "equal" for tag, *_ in opcodes):
        parts = []
        if changed["replace"]:
            parts.append(f"{changed['replace']} word(s) changed")
        if changed["delete"]:
            parts.append(f"{changed['delete']} word(s) missing")
        if changed["insert"]:
            parts.append(f"{changed['insert']} word(s) added")
        return FieldResult(
            field=field_name,
            verdict=FAIL,
            reason="Body text deviates from statutory warning: " + ", ".join(parts) + ".",
            evidence=evidence,
        )

    if found_tokens != expected_tokens:
        return FieldResult(
            field=field_name,
            verdict=FLAG,
            reason="Government warning body matches statutory text but casing deviates.",
            evidence=evidence,
        )

    if extracted.get("prefix_appears_bold") is False:
        return FieldResult(
            field=field_name,
            verdict=FLAG,
            reason="Government warning prefix does not appear bold.",
            evidence=evidence,
        )

    return FieldResult(
        field=field_name,
        verdict=PASS,
        reason="Government warning matches statutory text exactly.",
        evidence=evidence,
    )
