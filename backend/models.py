"""Pydantic schemas for the vision extraction contract (SPEC.md section 5)
and the API response envelope (SPEC.md section 6).

This module is the only pydantic-aware boundary in the backend.
comparators.py stays pure — plain dataclasses, zero API calls, zero
serialization concerns. FieldResult.from_comparator_result() is the seam
where a comparator's dataclass output becomes the validated wire shape;
it duck-types on (field, verdict, reason, evidence) rather than importing
comparators.py, so the dependency only ever points one way.
"""

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Section 5 — extraction contract (raw vision API output)
# ---------------------------------------------------------------------------

Confidence = Literal["high", "medium", "low"]
Legibility = Literal["clear", "partial", "unreadable"]
ImageQualityIssue = Literal["glare", "angle", "blur", "cropped"]


class GovernmentWarningExtraction(BaseModel):
    present: bool
    verbatim_text: Optional[str] = None
    prefix_appears_bold: Optional[bool] = None
    legibility: Legibility


class ExtractionConfidence(BaseModel):
    brand_name: Confidence
    class_type: Confidence
    alcohol_content: Confidence
    net_contents: Confidence
    government_warning: Confidence


class ExtractionResult(BaseModel):
    brand_name: Optional[str] = None
    class_type: Optional[str] = None
    alcohol_content: Optional[str] = None
    net_contents: Optional[str] = None
    government_warning: GovernmentWarningExtraction
    extraction_confidence: ExtractionConfidence
    image_quality_issues: List[ImageQualityIssue] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Section 6 — response envelope
# ---------------------------------------------------------------------------

FieldVerdict = Literal["PASS", "FLAG", "FAIL"]
OverallVerdict = Literal["PASS", "FLAG", "FAIL", "NEEDS BETTER IMAGE"]

_FIELD_NAMES = frozenset(
    {"brand_name", "class_type", "alcohol_content", "net_contents", "government_warning"}
)

# SPEC.md section 2: "Precedence: NEEDS BETTER IMAGE > FAIL > FLAG > PASS."
_VERDICT_PRECEDENCE = {"PASS": 0, "FLAG": 1, "FAIL": 2, "NEEDS BETTER IMAGE": 3}


def worst_verdict(verdicts: List[str]) -> str:
    """SPEC.md section 2: 'Overall verdict = worst field verdict.' Shared by
    the ResponseEnvelope invariant below and by app.py, which has to compute
    overall_verdict before it can construct the envelope in the first place."""
    return max(verdicts, key=lambda v: _VERDICT_PRECEDENCE[v])


class EqualOp(BaseModel):
    op: Literal["equal"]
    text: str


class ReplaceOp(BaseModel):
    op: Literal["replace"]
    expected: str
    found: str


class DeleteOp(BaseModel):
    op: Literal["delete"]
    expected: str


class InsertOp(BaseModel):
    op: Literal["insert"]
    found: str


DiffOp = Annotated[Union[EqualOp, ReplaceOp, DeleteOp, InsertOp], Field(discriminator="op")]


class Evidence(BaseModel):
    """One shape for every field (SPEC section 6): which keys are populated
    depends on which field produced it. Brand/class -> application,
    extracted, similarity. ABV/net contents -> application, extracted.
    Government warning -> expected, extracted, diff."""

    application: Optional[str] = None
    extracted: Optional[str] = None
    similarity: Optional[float] = None
    expected: Optional[str] = None
    diff: Optional[List[DiffOp]] = None


class FieldResult(BaseModel):
    field: str
    verdict: FieldVerdict
    reason: str
    evidence: Evidence

    @classmethod
    def from_comparator_result(cls, result) -> "FieldResult":
        return cls(
            field=result.field,
            verdict=result.verdict,
            reason=result.reason,
            evidence=Evidence(**result.evidence),
        )

    def to_wire_dict(self) -> dict:
        # exclude_unset (not exclude_none): a field-type's evidence keys are
        # exactly whichever ones the comparator populated, and some of those
        # (e.g. "extracted" when nothing was found on the label) are
        # legitimately null rather than absent. comparators.py always sets
        # every key that applies to a field's evidence shape, so "unset"
        # reliably means "not part of this field type's shape."
        data = self.model_dump(mode="json")
        data["evidence"] = self.evidence.model_dump(mode="json", exclude_unset=True)
        return data


class ImageQuality(BaseModel):
    legibility: Legibility
    issues: List[ImageQualityIssue] = Field(default_factory=list)


class ResponseEnvelope(BaseModel):
    overall_verdict: OverallVerdict
    processing_time_ms: int = Field(ge=0)
    image_quality: ImageQuality
    fields: List[FieldResult]

    @model_validator(mode="after")
    def _check_field_invariants(self) -> "ResponseEnvelope":
        if self.overall_verdict == "NEEDS BETTER IMAGE":
            if self.fields:
                raise ValueError("NEEDS BETTER IMAGE responses must not render field verdicts.")
            return self

        field_names = [f.field for f in self.fields]
        if len(field_names) != len(_FIELD_NAMES) or set(field_names) != _FIELD_NAMES:
            raise ValueError(
                f"Expected exactly the five compared fields {sorted(_FIELD_NAMES)}, got {field_names}."
            )

        worst = worst_verdict([f.verdict for f in self.fields])
        if self.overall_verdict != worst:
            raise ValueError(
                f"overall_verdict must equal the worst field verdict ({worst}), "
                f"got {self.overall_verdict}."
            )
        return self

    def to_wire_dict(self) -> dict:
        data = self.model_dump(mode="json")
        data["fields"] = [field.to_wire_dict() for field in self.fields]
        return data
