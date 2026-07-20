"""Failing-first test suite for models.py — SPEC.md section 5 (extraction
contract) and section 6 (response envelope). models.py must stay the only
pydantic-aware module here: comparators.py's dataclasses are adapted into
these schemas, not the other way around.
"""

import pytest
from pydantic import ValidationError

from comparators import (
    compare_alcohol_content,
    compare_brand_name,
    compare_class_type,
    compare_government_warning,
    compare_net_contents,
)
from models import (
    DiffOp,
    Evidence,
    ExtractionConfidence,
    ExtractionResult,
    FieldResult,
    GovernmentWarningExtraction,
    ImageQuality,
    ResponseEnvelope,
    worst_verdict,
)
from warning_text import BODY, PREFIX

STATUTORY_TEXT = f"{PREFIX} {BODY}"


def _warning_extraction(verbatim_text, present=True, bold=True, legibility="clear"):
    return {
        "present": present,
        "verbatim_text": verbatim_text,
        "prefix_appears_bold": bold,
        "legibility": legibility,
    }


# ---------------------------------------------------------------------------
# Section 5 — extraction contract
# ---------------------------------------------------------------------------


class TestGovernmentWarningExtraction:
    def test_valid_extraction_constructs(self):
        model = GovernmentWarningExtraction(
            present=True,
            verbatim_text=STATUTORY_TEXT,
            prefix_appears_bold=True,
            legibility="clear",
        )
        assert model.present is True
        assert model.legibility == "clear"

    def test_null_verbatim_text_and_bold_are_allowed(self):
        model = GovernmentWarningExtraction(
            present=False, verbatim_text=None, prefix_appears_bold=None, legibility="clear"
        )
        assert model.verbatim_text is None
        assert model.prefix_appears_bold is None

    def test_invalid_legibility_rejected(self):
        with pytest.raises(ValidationError):
            GovernmentWarningExtraction(
                present=True, verbatim_text=STATUTORY_TEXT, prefix_appears_bold=True,
                legibility="blurry",
            )


class TestExtractionConfidence:
    def test_valid_confidence_constructs(self):
        model = ExtractionConfidence(
            brand_name="high",
            class_type="high",
            alcohol_content="medium",
            net_contents="high",
            government_warning="low",
        )
        assert model.alcohol_content == "medium"

    def test_invalid_confidence_value_rejected(self):
        with pytest.raises(ValidationError):
            ExtractionConfidence(
                brand_name="certain",
                class_type="high",
                alcohol_content="high",
                net_contents="high",
                government_warning="high",
            )


class TestExtractionResult:
    def test_full_extraction_from_spec_example_constructs(self):
        model = ExtractionResult(
            brand_name="Old Tom Distillery",
            class_type="Kentucky Straight Bourbon Whiskey",
            alcohol_content="45% Alc./Vol.",
            net_contents="750 mL",
            government_warning=GovernmentWarningExtraction(
                present=True,
                verbatim_text=STATUTORY_TEXT,
                prefix_appears_bold=True,
                legibility="clear",
            ),
            extraction_confidence=ExtractionConfidence(
                brand_name="high",
                class_type="high",
                alcohol_content="high",
                net_contents="high",
                government_warning="high",
            ),
            image_quality_issues=[],
        )
        assert model.brand_name == "Old Tom Distillery"
        assert model.image_quality_issues == []

    def test_null_fields_never_guess_are_allowed(self):
        model = ExtractionResult(
            brand_name=None,
            class_type=None,
            alcohol_content=None,
            net_contents=None,
            government_warning=GovernmentWarningExtraction(
                present=False, verbatim_text=None, prefix_appears_bold=None, legibility="unreadable"
            ),
            extraction_confidence=ExtractionConfidence(
                brand_name="low", class_type="low", alcohol_content="low",
                net_contents="low", government_warning="low",
            ),
            image_quality_issues=["glare", "angle"],
        )
        assert model.brand_name is None
        assert model.image_quality_issues == ["glare", "angle"]

    def test_invalid_image_quality_issue_rejected(self):
        with pytest.raises(ValidationError):
            ExtractionResult(
                brand_name="X",
                class_type="Y",
                alcohol_content="45%",
                net_contents="750 mL",
                government_warning=GovernmentWarningExtraction(
                    present=True, verbatim_text=STATUTORY_TEXT, prefix_appears_bold=True,
                    legibility="clear",
                ),
                extraction_confidence=ExtractionConfidence(
                    brand_name="high", class_type="high", alcohol_content="high",
                    net_contents="high", government_warning="high",
                ),
                image_quality_issues=["smudge"],
            )


# ---------------------------------------------------------------------------
# Section 6 — diff op vocabulary (equal | replace | delete | insert)
# ---------------------------------------------------------------------------


class TestDiffOp:
    def test_equal_op_requires_text(self):
        from pydantic import TypeAdapter

        op = TypeAdapter(DiffOp).validate_python({"op": "equal", "text": "operate machinery"})
        assert op.op == "equal"
        assert op.text == "operate machinery"

    def test_replace_op_requires_expected_and_found(self):
        from pydantic import TypeAdapter

        op = TypeAdapter(DiffOp).validate_python(
            {"op": "replace", "expected": "drive", "found": "operate"}
        )
        assert op.expected == "drive"
        assert op.found == "operate"

    def test_delete_op_requires_expected_only(self):
        from pydantic import TypeAdapter

        op = TypeAdapter(DiffOp).validate_python({"op": "delete", "expected": "a car or"})
        assert op.expected == "a car or"

    def test_insert_op_requires_found_only(self):
        from pydantic import TypeAdapter

        op = TypeAdapter(DiffOp).validate_python({"op": "insert", "found": "serious"})
        assert op.found == "serious"

    def test_unknown_op_rejected(self):
        from pydantic import TypeAdapter

        with pytest.raises(ValidationError):
            TypeAdapter(DiffOp).validate_python({"op": "move", "text": "x"})

    def test_equal_op_missing_text_rejected(self):
        from pydantic import TypeAdapter

        with pytest.raises(ValidationError):
            TypeAdapter(DiffOp).validate_python({"op": "equal", "expected": "x"})


# ---------------------------------------------------------------------------
# Section 6 — Evidence + FieldResult
# ---------------------------------------------------------------------------


class TestEvidence:
    def test_brand_style_evidence(self):
        evidence = Evidence(application="Old Tom Distillery", extracted="Old Tom Distilery", similarity=0.94)
        assert evidence.expected is None
        assert evidence.diff is None

    def test_warning_style_evidence_with_diff(self):
        evidence = Evidence(
            expected=STATUTORY_TEXT,
            extracted="altered text",
            diff=[{"op": "equal", "text": "hello"}, {"op": "delete", "expected": "world"}],
        )
        assert len(evidence.diff) == 2
        assert evidence.diff[0].op == "equal"
        assert evidence.diff[1].op == "delete"


class TestFieldResult:
    def test_valid_field_result_constructs(self):
        result = FieldResult(
            field="brand_name",
            verdict="PASS",
            reason="Brand name matches application exactly.",
            evidence=Evidence(application="X", extracted="X", similarity=1.0),
        )
        assert result.verdict == "PASS"

    def test_invalid_verdict_rejected(self):
        with pytest.raises(ValidationError):
            FieldResult(
                field="brand_name",
                verdict="MAYBE",
                reason="...",
                evidence=Evidence(application="X", extracted="X", similarity=1.0),
            )

    def test_from_comparator_result_adapts_brand_name(self):
        comparator_result = compare_brand_name("Old Tom Distillery", "Old Tom Distilery")
        adapted = FieldResult.from_comparator_result(comparator_result)
        assert adapted.field == "brand_name"
        assert adapted.verdict == "FLAG"
        assert adapted.reason == comparator_result.reason
        assert adapted.evidence.application == "Old Tom Distillery"
        assert adapted.evidence.similarity == pytest.approx(comparator_result.evidence["similarity"])

    def test_from_comparator_result_adapts_government_warning_diff(self):
        altered = STATUTORY_TEXT.replace("drink alcoholic", "sip alcoholic")
        comparator_result = compare_government_warning(_warning_extraction(altered))
        adapted = FieldResult.from_comparator_result(comparator_result)
        assert adapted.verdict == "FAIL"
        assert adapted.evidence.diff is not None
        replace_ops = [op for op in adapted.evidence.diff if op.op == "replace"]
        assert len(replace_ops) == 1
        assert replace_ops[0].expected == "drink"
        assert replace_ops[0].found == "sip"


# ---------------------------------------------------------------------------
# Section 6 — ResponseEnvelope invariants
# ---------------------------------------------------------------------------


def _passing_fields():
    return [
        FieldResult.from_comparator_result(
            compare_brand_name("Old Tom Distillery", "Old Tom Distillery")
        ),
        FieldResult.from_comparator_result(
            compare_class_type("Kentucky Straight Bourbon Whiskey", "Kentucky Straight Bourbon Whiskey")
        ),
        FieldResult.from_comparator_result(
            compare_alcohol_content("45", "45% Alc./Vol. (90 Proof)")
        ),
        FieldResult.from_comparator_result(compare_net_contents("750 mL", "750 mL")),
        FieldResult.from_comparator_result(compare_government_warning(_warning_extraction(STATUTORY_TEXT))),
    ]


class TestWorstVerdict:
    def test_all_pass_is_pass(self):
        assert worst_verdict(["PASS", "PASS", "PASS"]) == "PASS"

    def test_flag_beats_pass(self):
        assert worst_verdict(["PASS", "FLAG", "PASS"]) == "FLAG"

    def test_fail_beats_flag_and_pass(self):
        assert worst_verdict(["PASS", "FLAG", "FAIL"]) == "FAIL"

    def test_needs_better_image_beats_everything(self):
        assert worst_verdict(["FAIL", "NEEDS BETTER IMAGE", "PASS"]) == "NEEDS BETTER IMAGE"


class TestResponseEnvelope:
    def test_all_pass_envelope_constructs(self):
        envelope = ResponseEnvelope(
            overall_verdict="PASS",
            processing_time_ms=3240,
            image_quality=ImageQuality(legibility="clear", issues=[]),
            fields=_passing_fields(),
        )
        assert envelope.overall_verdict == "PASS"
        assert len(envelope.fields) == 5

    def test_needs_better_image_requires_empty_fields(self):
        envelope = ResponseEnvelope(
            overall_verdict="NEEDS BETTER IMAGE",
            processing_time_ms=1800,
            image_quality=ImageQuality(legibility="partial", issues=["glare", "angle"]),
            fields=[],
        )
        assert envelope.fields == []

    def test_needs_better_image_with_fields_rejected(self):
        with pytest.raises(ValidationError):
            ResponseEnvelope(
                overall_verdict="NEEDS BETTER IMAGE",
                processing_time_ms=1800,
                image_quality=ImageQuality(legibility="partial", issues=["glare"]),
                fields=_passing_fields(),
            )

    def test_missing_a_field_rejected(self):
        with pytest.raises(ValidationError):
            ResponseEnvelope(
                overall_verdict="PASS",
                processing_time_ms=3240,
                image_quality=ImageQuality(legibility="clear", issues=[]),
                fields=_passing_fields()[:4],
            )

    def test_overall_verdict_must_equal_worst_field_verdict(self):
        fields = _passing_fields()
        with pytest.raises(ValidationError):
            ResponseEnvelope(
                overall_verdict="PASS",
                processing_time_ms=3240,
                image_quality=ImageQuality(legibility="clear", issues=[]),
                fields=fields[:-1]
                + [
                    FieldResult.from_comparator_result(
                        compare_government_warning(_warning_extraction(None, present=False))
                    )
                ],
            )

    def test_overall_verdict_reflects_worst_field_when_one_fails(self):
        fields = _passing_fields()[:-1] + [
            FieldResult.from_comparator_result(
                compare_government_warning(_warning_extraction(None, present=False))
            )
        ]
        envelope = ResponseEnvelope(
            overall_verdict="FAIL",
            processing_time_ms=3240,
            image_quality=ImageQuality(legibility="clear", issues=[]),
            fields=fields,
        )
        assert envelope.overall_verdict == "FAIL"

    def test_negative_processing_time_rejected(self):
        with pytest.raises(ValidationError):
            ResponseEnvelope(
                overall_verdict="PASS",
                processing_time_ms=-1,
                image_quality=ImageQuality(legibility="clear", issues=[]),
                fields=_passing_fields(),
            )


# ---------------------------------------------------------------------------
# Round-trip: comparators.py dataclass output -> pydantic model -> JSON must
# match the SPEC section 6 envelope shape exactly.
# ---------------------------------------------------------------------------


class TestRoundTripToWireJson:
    def test_brand_evidence_json_has_exactly_application_extracted_similarity(self):
        comparator_result = compare_brand_name("Old Tom Distillery", "Old Tom Distilery")
        wire = FieldResult.from_comparator_result(comparator_result).to_wire_dict()

        assert set(wire.keys()) == {"field", "verdict", "reason", "evidence"}
        assert set(wire["evidence"].keys()) == {"application", "extracted", "similarity"}
        assert wire["field"] == "brand_name"
        assert wire["verdict"] == "FLAG"
        assert wire["reason"] == comparator_result.reason

    def test_abv_evidence_json_has_exactly_application_extracted(self):
        comparator_result = compare_alcohol_content("45", "40% Alc./Vol.")
        wire = FieldResult.from_comparator_result(comparator_result).to_wire_dict()

        assert set(wire["evidence"].keys()) == {"application", "extracted"}
        assert wire["verdict"] == "FAIL"

    def test_government_warning_evidence_json_matches_spec_section_6_shape(self):
        # Mirrors the SPEC.md section 6 example: single word changed body.
        altered = STATUTORY_TEXT.replace("drink alcoholic", "sip alcoholic")
        comparator_result = compare_government_warning(_warning_extraction(altered))
        wire = FieldResult.from_comparator_result(comparator_result).to_wire_dict()

        assert wire["field"] == "government_warning"
        assert wire["verdict"] == "FAIL"
        evidence = wire["evidence"]
        assert set(evidence.keys()) == {"expected", "extracted", "diff"}
        assert evidence["expected"] == STATUTORY_TEXT
        assert evidence["extracted"] == altered

        diff = evidence["diff"]
        assert isinstance(diff, list)
        for op in diff:
            assert op["op"] in {"equal", "replace", "delete", "insert"}
            if op["op"] == "equal":
                assert set(op.keys()) == {"op", "text"}
            elif op["op"] == "replace":
                assert set(op.keys()) == {"op", "expected", "found"}
            elif op["op"] == "delete":
                assert set(op.keys()) == {"op", "expected"}
            elif op["op"] == "insert":
                assert set(op.keys()) == {"op", "found"}

        replace_entries = [op for op in diff if op["op"] == "replace"]
        assert replace_entries == [{"op": "replace", "expected": "drink", "found": "sip"}]

    def test_missing_warning_evidence_json_has_no_null_diff_key_when_present(self):
        # present=False path: diff is populated (a single delete op), not null.
        comparator_result = compare_government_warning(_warning_extraction(None, present=False))
        wire = FieldResult.from_comparator_result(comparator_result).to_wire_dict()

        assert wire["evidence"]["extracted"] is None
        assert wire["evidence"]["diff"] == [{"op": "delete", "expected": STATUTORY_TEXT}]

    def test_full_envelope_round_trip_matches_section_6_top_level_shape(self):
        fields = [FieldResult.from_comparator_result(r) for r in [
            compare_brand_name("Old Tom Distillery", "Old Tom Distillery"),
            compare_class_type("Kentucky Straight Bourbon Whiskey", "Kentucky Straight Bourbon Whiskey"),
            compare_alcohol_content("45", "45% Alc./Vol. (90 Proof)"),
            compare_net_contents("750 mL", "750 mL"),
            compare_government_warning(_warning_extraction(STATUTORY_TEXT)),
        ]]
        envelope = ResponseEnvelope(
            overall_verdict="PASS",
            processing_time_ms=3240,
            image_quality=ImageQuality(legibility="clear", issues=[]),
            fields=fields,
        )
        wire = envelope.to_wire_dict()

        assert set(wire.keys()) == {"overall_verdict", "processing_time_ms", "image_quality", "fields"}
        assert wire["overall_verdict"] == "PASS"
        assert wire["processing_time_ms"] == 3240
        assert wire["image_quality"] == {"legibility": "clear", "issues": []}
        assert len(wire["fields"]) == 5
        assert {f["field"] for f in wire["fields"]} == {
            "brand_name", "class_type", "alcohol_content", "net_contents", "government_warning",
        }
        for field_entry in wire["fields"]:
            assert set(field_entry.keys()) == {"field", "verdict", "reason", "evidence"}

    def test_wire_dict_is_json_serializable(self):
        import json

        comparator_result = compare_government_warning(_warning_extraction(STATUTORY_TEXT))
        wire = FieldResult.from_comparator_result(comparator_result).to_wire_dict()
        # round-trips cleanly through json.dumps/loads with no surprises
        assert json.loads(json.dumps(wire)) == wire
