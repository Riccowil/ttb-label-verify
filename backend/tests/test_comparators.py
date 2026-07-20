"""Failing-first test suite for comparators.py — SPEC.md section 3 (comparison
rules) and section 12 (test matrix T1-T9). Zero API calls: every case is a
plain string/dict fixture standing in for extracted vs. application data.
"""

import pytest

from comparators import (
    PASS,
    FLAG,
    FAIL,
    compare_brand_name,
    compare_class_type,
    compare_alcohol_content,
    compare_net_contents,
    compare_government_warning,
)
from warning_text import PREFIX, BODY


# ---------------------------------------------------------------------------
# Brand name — SPEC section 3 "Brand name"
# ---------------------------------------------------------------------------

class TestBrandName:
    def test_exact_match_passes(self):
        result = compare_brand_name("Old Tom Distillery", "Old Tom Distillery")
        assert result.verdict == PASS

    def test_case_variance_passes_with_note(self):
        # T2: label STONE'S THROW vs app Stone's Throw
        result = compare_brand_name("Stone's Throw", "STONE'S THROW")
        assert result.verdict == PASS
        assert "case/punctuation variance" in result.reason

    def test_trailing_punctuation_variance_passes_with_note(self):
        result = compare_brand_name("Old Tom Distillery", "Old Tom Distillery.")
        assert result.verdict == PASS
        assert "case/punctuation variance" in result.reason

    def test_apostrophe_variant_unified(self):
        result = compare_brand_name("Stone’s Throw", "Stone's Throw")
        assert result.verdict == PASS

    def test_whitespace_collapse_passes_with_note(self):
        result = compare_brand_name("Old Tom Distillery", "Old   Tom  Distillery")
        assert result.verdict == PASS

    def test_high_similarity_flags(self):
        # "Old Tom Distillery" vs "Old Tom Distilery" (missing one letter)
        result = compare_brand_name("Old Tom Distillery", "Old Tom Distilery")
        assert result.verdict == FLAG

    def test_low_similarity_fails(self):
        result = compare_brand_name("Old Tom Distillery", "Completely Different Brand")
        assert result.verdict == FAIL

    def test_evidence_shape(self):
        result = compare_brand_name("Old Tom Distillery", "Old Tom Distilery")
        assert result.field == "brand_name"
        assert set(result.evidence.keys()) == {"application", "extracted", "similarity"}
        assert result.evidence["application"] == "Old Tom Distillery"
        assert result.evidence["extracted"] == "Old Tom Distilery"
        assert 0.0 <= result.evidence["similarity"] <= 1.0

    def test_missing_from_label_fails(self):
        result = compare_brand_name("Old Tom Distillery", None)
        assert result.verdict == FAIL


# ---------------------------------------------------------------------------
# Class/type — SPEC section 3 "Class/type"
# ---------------------------------------------------------------------------

class TestClassType:
    def test_exact_normalized_match_passes(self):
        result = compare_class_type(
            "Kentucky Straight Bourbon Whiskey", "KENTUCKY STRAIGHT BOURBON WHISKEY"
        )
        assert result.verdict == PASS

    def test_token_subset_flags(self):
        result = compare_class_type("Kentucky Straight Bourbon Whiskey", "Bourbon Whiskey")
        assert result.verdict == FLAG

    def test_moderate_similarity_flags(self):
        result = compare_class_type("Bourbon Whiskey", "Bourbon Whisky")
        assert result.verdict == FLAG

    def test_disjoint_fails(self):
        result = compare_class_type("Kentucky Straight Bourbon Whiskey", "Vodka")
        assert result.verdict == FAIL

    def test_missing_from_label_fails(self):
        result = compare_class_type("Kentucky Straight Bourbon Whiskey", None)
        assert result.verdict == FAIL

    def test_field_name(self):
        result = compare_class_type("Bourbon", "Bourbon")
        assert result.field == "class_type"


# ---------------------------------------------------------------------------
# Alcohol content — SPEC section 3 "Alcohol content (ABV)"
# ---------------------------------------------------------------------------

class TestAlcoholContent:
    @pytest.mark.parametrize(
        "label_text",
        ["45% Alc./Vol.", "45% ABV", "ALC 45% BY VOL", "45%"],
    )
    def test_format_variants_all_parse_to_same_value_and_pass(self, label_text):
        result = compare_alcohol_content("45", label_text)
        assert result.verdict == PASS

    def test_value_mismatch_fails(self):
        # T6: app 45%, label 40% (80 Proof)
        result = compare_alcohol_content("45", "40% Alc./Vol. (80 Proof)")
        assert result.verdict == FAIL
        assert "45" in result.reason and "40" in result.reason

    def test_proof_inconsistent_with_stated_percentage_flags(self):
        # 45% should be 90 proof; label says 89 proof — internally inconsistent
        result = compare_alcohol_content("45", "45% Alc./Vol. (89 Proof)")
        assert result.verdict == FLAG

    def test_proof_consistent_with_stated_percentage_passes(self):
        result = compare_alcohol_content("45", "45% Alc./Vol. (90 Proof)")
        assert result.verdict == PASS

    def test_unparseable_label_text_flags_never_fails(self):
        result = compare_alcohol_content("45", "see back label")
        assert result.verdict == FLAG

    def test_wine_with_no_abv_stated_passes_with_note(self):
        # T8: wine, no ABV stated (legal) — documented choice: PASS w/ note
        result = compare_alcohol_content("11", None, beverage_type="wine")
        assert result.verdict == PASS
        assert "not stated" in result.reason.lower()

    def test_non_wine_with_no_abv_stated_flags(self):
        result = compare_alcohol_content("45", None, beverage_type="distilled_spirits")
        assert result.verdict == FLAG

    def test_field_name(self):
        result = compare_alcohol_content("45", "45%")
        assert result.field == "alcohol_content"


# ---------------------------------------------------------------------------
# Net contents — SPEC section 3 "Net contents"
# ---------------------------------------------------------------------------

class TestNetContents:
    def test_exact_match_passes(self):
        result = compare_net_contents("750 mL", "750 mL")
        assert result.verdict == PASS

    @pytest.mark.parametrize("label_text", ["750ml", "750 ML", "750  mL"])
    def test_format_variants_pass(self, label_text):
        result = compare_net_contents("750 mL", label_text)
        assert result.verdict == PASS

    def test_unit_conversion_passes_with_note(self):
        # T9 (stretch): 75 cL == 750 mL
        result = compare_net_contents("750 mL", "75 cL")
        assert result.verdict == PASS
        assert "unit conversion" in result.reason.lower() or "converted" in result.reason.lower()

    def test_value_mismatch_fails(self):
        result = compare_net_contents("750 mL", "700 mL")
        assert result.verdict == FAIL

    def test_unparseable_label_text_flags(self):
        result = compare_net_contents("750 mL", "a big bottle")
        assert result.verdict == FLAG

    def test_field_name(self):
        result = compare_net_contents("750 mL", "750 mL")
        assert result.field == "net_contents"


# ---------------------------------------------------------------------------
# Government warning — SPEC section 3 "Government warning — two-part strict"
# ---------------------------------------------------------------------------

def _extraction(verbatim_text, present=True, bold=True, legibility="clear"):
    return {
        "present": present,
        "verbatim_text": verbatim_text,
        "prefix_appears_bold": bold,
        "legibility": legibility,
    }


STATUTORY_TEXT = f"{PREFIX} {BODY}"


class TestGovernmentWarning:
    def test_exact_statutory_text_passes(self):
        # T1: correct bold warning
        result = compare_government_warning(_extraction(STATUTORY_TEXT))
        assert result.verdict == PASS

    def test_missing_warning_fails(self):
        # T5: no warning on label
        result = compare_government_warning(_extraction(None, present=False))
        assert result.verdict == FAIL
        assert result.evidence["extracted"] is None

    def test_wrapped_whitespace_normalized_and_passes(self):
        wrapped = STATUTORY_TEXT.replace(" ", "\n")
        result = compare_government_warning(_extraction(wrapped))
        assert result.verdict == PASS

    def test_title_case_prefix_fails(self):
        # T3: prefix "Government Warning:" title case
        bad_prefix_text = STATUTORY_TEXT.replace(PREFIX, "Government Warning:")
        result = compare_government_warning(_extraction(bad_prefix_text))
        assert result.verdict == FAIL
        assert "prefix" in result.reason.lower()

    def test_single_word_replaced_in_body_fails_with_replace_op(self):
        # T4: one word changed in warning body
        altered = STATUTORY_TEXT.replace("drink alcoholic", "sip alcoholic")
        result = compare_government_warning(_extraction(altered))
        assert result.verdict == FAIL
        diff = result.evidence["diff"]
        replace_ops = [op for op in diff if op["op"] == "replace"]
        assert len(replace_ops) == 1
        assert replace_ops[0]["expected"] == "drink"
        assert replace_ops[0]["found"] == "sip"

    def test_missing_word_in_body_fails_with_delete_op(self):
        altered = STATUTORY_TEXT.replace("(2) Consumption", "Consumption")
        result = compare_government_warning(_extraction(altered))
        assert result.verdict == FAIL
        diff = result.evidence["diff"]
        delete_ops = [op for op in diff if op["op"] == "delete"]
        assert any("(2)" in op["expected"] for op in delete_ops)

    def test_added_word_in_body_fails_with_insert_op(self):
        altered = STATUTORY_TEXT.replace("health problems", "serious health problems")
        result = compare_government_warning(_extraction(altered))
        assert result.verdict == FAIL
        diff = result.evidence["diff"]
        insert_ops = [op for op in diff if op["op"] == "insert"]
        assert any(op["found"] == "serious" for op in insert_ops)

    def test_equal_runs_are_collapsed_not_per_word(self):
        altered = STATUTORY_TEXT.replace("drink alcoholic", "sip alcoholic")
        result = compare_government_warning(_extraction(altered))
        diff = result.evidence["diff"]
        equal_ops = [op for op in diff if op["op"] == "equal"]
        # a single word-level substitution should leave two large equal runs,
        # not one equal op per surrounding word
        assert len(equal_ops) == 2

    def test_body_correct_but_internal_casing_deviates_flags(self):
        lowered = STATUTORY_TEXT.replace(
            "According to the Surgeon General", "according to the surgeon general"
        )
        result = compare_government_warning(_extraction(lowered))
        assert result.verdict == FLAG

    def test_prefix_not_bold_flags(self):
        result = compare_government_warning(_extraction(STATUTORY_TEXT, bold=False))
        assert result.verdict == FLAG

    def test_field_name(self):
        result = compare_government_warning(_extraction(STATUTORY_TEXT))
        assert result.field == "government_warning"


# ---------------------------------------------------------------------------
# Low-confidence cap — SPEC section 2
# "Any field with low extraction confidence caps at FLAG regardless of
# match result."
# ---------------------------------------------------------------------------

class TestLowConfidenceCap:
    def test_low_confidence_caps_a_pass_to_flag(self):
        result = compare_brand_name("Old Tom Distillery", "Old Tom Distillery", confidence="low")
        assert result.verdict == FLAG

    def test_low_confidence_caps_a_fail_to_flag(self):
        result = compare_brand_name("Old Tom Distillery", "Nothing Alike", confidence="low")
        assert result.verdict == FLAG

    def test_high_confidence_does_not_cap(self):
        result = compare_brand_name("Old Tom Distillery", "Nothing Alike", confidence="high")
        assert result.verdict == FAIL

    def test_medium_confidence_does_not_cap(self):
        result = compare_brand_name("Old Tom Distillery", "Old Tom Distillery", confidence="medium")
        assert result.verdict == PASS

    def test_low_confidence_applies_to_government_warning(self):
        result = compare_government_warning(_extraction(None, present=False), confidence="low")
        assert result.verdict == FLAG
