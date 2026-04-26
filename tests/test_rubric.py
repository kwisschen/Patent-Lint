# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.rubric — the deterministic scoring rubric."""

from __future__ import annotations


from patentlint.models import (
    CheckItem,
    CompletenessGap,
    Jurisdiction,
    RubricSection,
)
from patentlint.rubric import (
    ADVISORY_REVIEW_KEYS,
    FIX_DEDUCTION,
    REVIEW_DEDUCTION,
    RUBRIC_VERSION,
    SECTION_WEIGHTS,
    compute_rubric_grade,
    compute_section_score,
    detect_completeness_gap,
    detect_has_drawings,
    flatten_checks_from_lists,
    gate_cap_for_fix_count,
    letter_for_score,
    section_for_check,
    section_for_message_key,
)


def _check(status: str, message_key: str) -> CheckItem:
    return CheckItem(status=status, message=message_key, message_key=message_key)


# ── Pure helpers ─────────────────────────────────────────────────────────


class TestPureHelpers:
    def test_section_score_clean(self):
        assert compute_section_score(0, 0) == 100

    def test_section_score_one_fix(self):
        assert compute_section_score(1, 0) == 100 - FIX_DEDUCTION

    def test_section_score_one_review(self):
        assert compute_section_score(0, 1) == 100 - REVIEW_DEDUCTION

    def test_section_score_floors_at_zero(self):
        # 10 FIX would deduct 150 — must floor.
        assert compute_section_score(10, 0) == 0

    def test_letter_thresholds(self):
        # Standard US university 12-tier scale (Harvard / Yale / MIT-style;
        # no A+). A spans 93-100; everything else split into +/-/middle.
        assert letter_for_score(100) == "A"
        assert letter_for_score(97) == "A"
        assert letter_for_score(93) == "A"
        assert letter_for_score(92) == "A-"
        assert letter_for_score(90) == "A-"
        assert letter_for_score(89) == "B+"
        assert letter_for_score(87) == "B+"
        assert letter_for_score(86) == "B"
        assert letter_for_score(83) == "B"
        assert letter_for_score(82) == "B-"
        assert letter_for_score(80) == "B-"
        assert letter_for_score(79) == "C+"
        assert letter_for_score(77) == "C+"
        assert letter_for_score(76) == "C"
        assert letter_for_score(73) == "C"
        assert letter_for_score(72) == "C-"
        assert letter_for_score(70) == "C-"
        assert letter_for_score(69) == "D+"
        assert letter_for_score(67) == "D+"
        assert letter_for_score(66) == "D"
        assert letter_for_score(63) == "D"
        assert letter_for_score(62) == "D-"
        assert letter_for_score(60) == "D-"
        assert letter_for_score(59) == "F"
        assert letter_for_score(0) == "F"

    def test_gate_no_fix(self):
        cap, reason = gate_cap_for_fix_count(0)
        assert cap == 100
        assert reason is None

    def test_gate_one_fix_caps_a_minus(self):
        # Standard US 13-tier mapping: numeric cap 92 = A- (90-92).
        cap, reason = gate_cap_for_fix_count(1)
        assert cap == 92
        assert "A-" in reason

    def test_gate_progressive_caps(self):
        # 2: B (87), 3: B- (82), 4: C+ (77), 5: C (72), 6: D (67), 7+: F (59)
        for fix_n, expected_max in [(2, 87), (3, 82), (4, 77), (5, 72), (6, 67), (7, 59), (10, 59)]:
            cap, _ = gate_cap_for_fix_count(fix_n)
            assert cap == expected_max, f"fix_count={fix_n} should cap at {expected_max}"

    def test_section_weights_sum_to_100(self):
        assert sum(SECTION_WEIGHTS.values()) == 100


# ── Section mapping ──────────────────────────────────────────────────────


class TestSectionMapping:
    def test_antecedent_basis_routes_to_dedicated_section(self):
        assert section_for_message_key("check.claims.antecedentBasis.verify") == \
            RubricSection.ANTECEDENT_SPEC_SUPPORT
        assert section_for_message_key("check.cn.claims.antecedentBasis.verify") == \
            RubricSection.ANTECEDENT_SPEC_SUPPORT
        assert section_for_message_key("check.tw.claims.antecedentBasis.pass") == \
            RubricSection.ANTECEDENT_SPEC_SUPPORT

    def test_spec_support_routes_to_dedicated_section(self):
        assert section_for_message_key("checks.spec_support_unsupported_terms") == \
            RubricSection.ANTECEDENT_SPEC_SUPPORT
        assert section_for_message_key("check.cn.claims.specSupport.verify") == \
            RubricSection.ANTECEDENT_SPEC_SUPPORT
        assert section_for_message_key("check.tw.claims.specSupport.pass") == \
            RubricSection.ANTECEDENT_SPEC_SUPPORT

    def test_figure_ref_consistency_routes_to_drawings(self):
        # Spec-bucket checks that are conceptually drawings → DRAWINGS rubric.
        assert section_for_message_key("check.cn.spec.figureRefConsistency.verify") == \
            RubricSection.DRAWINGS
        assert section_for_message_key("check.tw.spec.figureRefConsistency.pass") == \
            RubricSection.DRAWINGS

    def test_tw_symbol_table_routes_to_drawings(self):
        assert section_for_message_key("check.tw.spec.symbolTablePresence.amend") == \
            RubricSection.DRAWINGS
        assert section_for_message_key("check.tw.crossRef.symbolVsRepDrawing.pass") == \
            RubricSection.DRAWINGS
        assert section_for_message_key("check.tw.claims.symbolTableConsistency.pass") == \
            RubricSection.DRAWINGS

    def test_spec_default_routes_to_specification(self):
        assert section_for_message_key("check.spec.paragraphSequential.amend") == \
            RubricSection.SPECIFICATION
        assert section_for_message_key("check.cn.spec.requiredSections.pass") == \
            RubricSection.SPECIFICATION

    def test_drawings_bucket_routes_to_drawings(self):
        assert section_for_message_key("check.drawings.singleFigure.amend") == \
            RubricSection.DRAWINGS
        assert section_for_message_key("check.tw.drawings.figuresSequential.pass") == \
            RubricSection.DRAWINGS

    def test_claims_bucket_routes_to_claims(self):
        assert section_for_message_key("check.claims.sequential.amend") == \
            RubricSection.CLAIMS
        assert section_for_message_key("check.cn.claims.markushOpenTransition.amend") == \
            RubricSection.CLAIMS

    def test_abstract_bucket_routes_to_abstract(self):
        assert section_for_message_key("check.abstract.wordCount.amend") == \
            RubricSection.ABSTRACT
        assert section_for_message_key("check.cn.abstract.charCount.amend") == \
            RubricSection.ABSTRACT


# ── compute_rubric_grade ─────────────────────────────────────────────────


class TestComputeRubricGrade:
    def test_all_pass_scores_a(self):
        checks = [_check("pass", "check.spec.paragraphSequential.pass")]
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=checks,
            has_drawings=True,
        )
        assert grade.score == 100
        assert grade.letter == "A"
        assert grade.cap_reason is None
        assert grade.is_complete

    def test_one_fix_caps_at_a_minus(self):
        checks = [_check("amend", "check.cn.spec.requiredSections.amend")]
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.CN,
            all_checks=checks,
            has_drawings=True,
        )
        # Spec section: 100 - 15 = 85; weighted = 85 * 0.20 = 17 contribution.
        # Other sections: 100 each. Total weighted ≈ 97. Gate caps at 92 (A-).
        assert grade.score == 92
        assert grade.letter == "A-"
        assert "A-" in grade.cap_reason

    def test_three_fix_caps_at_b_minus(self):
        # Spread the 3 FIXes across different sections so the gate (cap 82)
        # is the binding constraint, not section-level deductions.
        checks = [
            _check("amend", "check.spec.paragraphSequential.amend"),
            _check("amend", "check.cn.claims.selfDependent.amend"),
            _check("amend", "check.cn.abstract.charCount.amend"),
        ]
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.CN,
            all_checks=checks,
            has_drawings=True,
        )
        # Gate cap for 3 FIX is 82 (B- in standard US scale: 80-82).
        assert grade.score == 82
        assert grade.letter == "B-"

    def test_review_only_polishes_a_minus(self):
        # 5 REVIEW × 3pts = 15pts deducted across various sections; clean of FIX.
        # Effect on weighted overall is small (claims-section 5 reviews = -15
        # at section level, weighted at 0.45 → -6.75 to overall).
        checks = [
            _check("verify", "check.claims.antecedentBasis.verify"),
            _check("verify", "check.claims.antecedentBasis.verify"),
            _check("verify", "check.claims.antecedentBasis.verify"),
            _check("verify", "check.claims.antecedentBasis.verify"),
            _check("verify", "check.claims.antecedentBasis.verify"),
        ]
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=checks,
            has_drawings=True,
        )
        # 5 × 3 = 15 deducted from antecedent section → 85; weighted at 0.15 → -2.25.
        # Overall ≈ 97.75 → 97 → A (93-100 with no A+). No gate.
        assert grade.letter in ("A", "A-")
        assert grade.cap_reason is None

    def test_no_drawings_drawings_section_na(self):
        checks = [_check("pass", "check.cn.spec.requiredSections.pass")]
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.CN,
            all_checks=checks,
            has_drawings=False,
        )
        # Drawings section should be N/A.
        drawings_sg = next(sg for sg in grade.section_grades if sg.section == RubricSection.DRAWINGS)
        assert not drawings_sg.applicable
        assert drawings_sg.effective_weight == 0.0

    def test_no_drawings_redistributes_weight(self):
        checks = [_check("pass", "check.cn.spec.requiredSections.pass")]
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.CN,
            all_checks=checks,
            has_drawings=False,
        )
        # Total effective weight across applicable sections must sum to ~100.
        total = sum(sg.effective_weight for sg in grade.section_grades if sg.applicable)
        assert abs(total - 100.0) < 0.5  # allow rounding slack

    def test_completeness_gap_yields_no_grade(self):
        gap = CompletenessGap(missing_sections=["claims", "abstract"])
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=[],
            has_drawings=True,
            completeness_gap=gap,
        )
        assert grade.completeness_gap is not None
        assert grade.completeness_gap.missing_sections == ["claims", "abstract"]
        assert grade.letter == "—"
        assert not grade.is_complete

    def test_section_grades_include_all_5(self):
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.TW,
            all_checks=[],
            has_drawings=True,
        )
        sections = {sg.section for sg in grade.section_grades}
        assert sections == set(RubricSection)

    def test_rubric_version_set(self):
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=[],
            has_drawings=False,
        )
        assert grade.rubric_version == RUBRIC_VERSION

    def test_gate_only_surfaced_when_actually_capped(self):
        # 1 FIX in claims: section drops to 85, weighted contribution
        # ~93 un-capped. Gate caps at 92 (B+) — actually binding, so
        # cap_reason should surface.
        checks = [_check("amend", "check.claims.selfDependent.amend")]
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=checks,
            has_drawings=True,
        )
        assert grade.cap_reason is not None
        assert grade.score == 92


# ── Impact list ──────────────────────────────────────────────────────────


class TestImpactList:
    def test_empty_when_all_pass(self):
        checks = [_check("pass", "check.claims.sequential.pass")]
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=checks,
            has_drawings=True,
        )
        assert grade.impact_list == []

    def test_top_3_only(self):
        checks = [_check("amend", "check.claims.sequential.amend") for _ in range(10)]
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=checks,
            has_drawings=True,
        )
        assert len(grade.impact_list) <= 3

    def test_fix_ranks_above_review(self):
        # Both in claims section: FIX delta should beat REVIEW delta.
        checks = [
            _check("verify", "check.claims.antecedentBasis.verify"),
            _check("amend", "check.claims.selfDependent.amend"),
        ]
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=checks,
            has_drawings=True,
        )
        assert grade.impact_list[0].status == "amend"

    def test_excludes_pass_items(self):
        checks = [
            _check("pass", "check.claims.sequential.pass"),
            _check("amend", "check.claims.selfDependent.amend"),
        ]
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=checks,
            has_drawings=True,
        )
        assert all(item.status in ("amend", "verify") for item in grade.impact_list)

    def test_excludes_findings_in_inapplicable_sections(self):
        # A drawings-section finding when has_drawings=False should not
        # appear in the impact list (drawings is N/A so resolving it
        # doesn't move the grade).
        checks = [_check("amend", "check.drawings.sequential.amend")]
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=checks,
            has_drawings=False,
        )
        assert grade.impact_list == []


# ── requiredSections.amend → Drawings routing ───────────────────────────


class TestRequiredSectionsRouting:
    """When a requiredSections FIX names ONLY drawings-related sections
    (BDoD or 符號說明), route the FIX to the Drawings rubric section so
    the section pills tell the truth (Drawings score drops; Spec score
    stays clean). Mixed-missing cases stay in SPEC."""

    def _check_with_sections(self, message_key, sections_str):
        return CheckItem(
            status="amend",
            message="Missing required sections",
            message_key=message_key,
            details_params={"sections": sections_str},
        )

    def test_tw_bdod_only_routes_to_drawings(self):
        c = self._check_with_sections("check.tw.spec.requiredSections.amend", "圖式簡單說明")
        assert section_for_check(c) == RubricSection.DRAWINGS

    def test_tw_symbol_table_only_routes_to_drawings(self):
        c = self._check_with_sections("check.tw.spec.requiredSections.amend", "符號說明")
        assert section_for_check(c) == RubricSection.DRAWINGS

    def test_tw_bdod_plus_symbol_table_routes_to_drawings(self):
        c = self._check_with_sections("check.tw.spec.requiredSections.amend", "圖式簡單說明, 符號說明")
        assert section_for_check(c) == RubricSection.DRAWINGS

    def test_tw_mixed_missing_stays_in_spec(self):
        # BDoD + 技術領域 missing → mixed; routing to Drawings would lose
        # the non-drawings signal. Keep on SPEC.
        c = self._check_with_sections("check.tw.spec.requiredSections.amend", "圖式簡單說明, 技術領域")
        assert section_for_check(c) == RubricSection.SPECIFICATION

    def test_tw_non_drawings_only_stays_in_spec(self):
        c = self._check_with_sections("check.tw.spec.requiredSections.amend", "技術領域, 先前技術")
        assert section_for_check(c) == RubricSection.SPECIFICATION

    def test_cn_bdod_only_routes_to_drawings(self):
        c = self._check_with_sections("check.cn.spec.requiredSections.amend", "附图说明")
        assert section_for_check(c) == RubricSection.DRAWINGS

    def test_us_bdod_only_routes_to_drawings(self):
        c = self._check_with_sections("checks.required_sections_missing", "Brief Description of the Drawings")
        assert section_for_check(c) == RubricSection.DRAWINGS

    def test_non_required_sections_check_unaffected(self):
        # A non-requiredSections check with details_params still routes
        # by the normal key-based path.
        c = CheckItem(
            status="amend",
            message="x",
            message_key="check.tw.spec.paragraphNumbering.amendFormat",
            details_params={"sections": "圖式簡單說明"},  # irrelevant for this key
        )
        assert section_for_check(c) == RubricSection.SPECIFICATION

    def test_no_details_params_falls_back_to_spec(self):
        c = CheckItem(
            status="amend",
            message="x",
            message_key="check.tw.spec.requiredSections.amend",
        )
        assert section_for_check(c) == RubricSection.SPECIFICATION

    def test_routing_affects_section_grade(self):
        # End-to-end: a TW draft that has drawings (figures detected),
        # a missing 圖式簡單說明 should drop the Drawings score, NOT Spec.
        check = self._check_with_sections("check.tw.spec.requiredSections.amend", "圖式簡單說明")
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.TW,
            all_checks=[check],
            has_drawings=True,
        )
        spec = next(sg for sg in grade.section_grades if sg.section == RubricSection.SPECIFICATION)
        drawings = next(sg for sg in grade.section_grades if sg.section == RubricSection.DRAWINGS)
        assert spec.fix_count == 0
        assert spec.score == 100
        assert drawings.fix_count == 1
        assert drawings.score == 85  # 100 - 15


# ── Advisory REVIEW exclusion ────────────────────────────────────────────


class TestAdvisoryReviews:
    """Advisory REVIEW items are informational (cross-reference / prior-art
    citation / indigenous-term presence). They surface in the triage panel
    but must NOT deduct from the rubric grade — drafters who legitimately
    cite cross-references shouldn't see the grade drop."""

    def test_advisory_keys_set_nonempty(self):
        # Sanity check: the set should be populated; if someone clears
        # it, this test fires.
        assert len(ADVISORY_REVIEW_KEYS) >= 5
        # Spot-check a few specific keys
        assert "check.spec.crossReference.verify" in ADVISORY_REVIEW_KEYS
        assert "check.spec.priorArt.verify" in ADVISORY_REVIEW_KEYS
        assert "check.tw.spec.indigenousTerms.verify" in ADVISORY_REVIEW_KEYS

    def test_advisory_review_does_not_deduct(self):
        # An advisory REVIEW item should not affect the grade.
        clean_grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=[],
            has_drawings=True,
        )
        with_advisory = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=[_check("verify", "check.spec.crossReference.verify")],
            has_drawings=True,
        )
        assert with_advisory.score == clean_grade.score
        assert with_advisory.letter == clean_grade.letter

    def test_non_advisory_review_still_deducts(self):
        # A non-advisory REVIEW (antecedent walker, restrictive wording, etc.)
        # should still deduct. Using 5 reviews in claims (45% weight) so the
        # deduction is large enough to survive rounding: 5 × 3 = 15pts at
        # section level, weighted at 0.45 → -6.75 → final score ~93.
        clean_grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=[],
            has_drawings=True,
        )
        with_reviews = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=[_check("verify", "check.claims.restrictiveAbsolutes.verify") for _ in range(5)],
            has_drawings=True,
        )
        assert with_reviews.score < clean_grade.score

    def test_advisory_review_excluded_from_impact_list(self):
        checks = [
            _check("verify", "check.spec.crossReference.verify"),
            _check("verify", "check.spec.priorArt.verify"),
            _check("verify", "check.claims.antecedentBasis.verify"),  # non-advisory
        ]
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=checks,
            has_drawings=True,
        )
        # Only the antecedent item should land in the impact list — the two
        # advisory items are filtered out.
        keys_in_impact = {item.message_key for item in grade.impact_list}
        assert "check.claims.antecedentBasis.verify" in keys_in_impact
        assert "check.spec.crossReference.verify" not in keys_in_impact
        assert "check.spec.priorArt.verify" not in keys_in_impact

    def test_small_deduction_visibly_drops_below_100(self):
        # Regression for the rounding bug: 1 REVIEW in a low-weight section
        # produced a fractional overall deduction (~0.5pts) that rounded
        # back up to 100, hiding the deduction in the hero. With floor
        # semantics any non-zero deduction must visibly drop the score
        # below 100.
        clean = compute_rubric_grade(
            jurisdiction=Jurisdiction.TW,
            all_checks=[],
            has_drawings=False,  # mirror the user's BDoD-removed fixture
        )
        with_review = compute_rubric_grade(
            jurisdiction=Jurisdiction.TW,
            all_checks=[_check("verify", "check.tw.claims.antecedentBasis.verify")],
            has_drawings=False,
        )
        assert clean.score == 100
        assert with_review.score < 100, "any non-advisory REVIEW must visibly drop the score below 100"

    def test_advisory_still_appears_in_section_pass_count(self):
        # Advisory items bucket as PASS for grading purposes.
        grade = compute_rubric_grade(
            jurisdiction=Jurisdiction.US,
            all_checks=[
                _check("verify", "check.spec.crossReference.verify"),
                _check("verify", "check.spec.priorArt.verify"),
            ],
            has_drawings=True,
        )
        spec = next(sg for sg in grade.section_grades if sg.section == RubricSection.SPECIFICATION)
        # Both advisory verifies counted as pass (for grading), not as review.
        assert spec.review_count == 0
        assert spec.pass_count == 2


# ── Detection helpers ────────────────────────────────────────────────────


class TestDetectHasDrawings:
    def test_figure_count_signals_drawings(self):
        assert detect_has_drawings(figures_count=3) is True

    def test_figure_refs_signal_drawings(self):
        assert detect_has_drawings(figures_count=0, figure_refs=["1", "2"]) is True

    def test_no_signal_means_no_drawings(self):
        assert detect_has_drawings(figures_count=0, figure_refs=None) is False
        assert detect_has_drawings(figures_count=0, figure_refs=[]) is False


class TestDetectCompletenessGap:
    def test_complete_doc_no_gap(self):
        gap = detect_completeness_gap(
            title="A Useful Invention",
            has_claims=True,
            has_spec_body=True,
            has_abstract=True,
        )
        assert gap is None

    def test_missing_title_triggers_gap(self):
        gap = detect_completeness_gap(
            title="",
            has_claims=True,
            has_spec_body=True,
            has_abstract=True,
        )
        assert gap is not None
        assert "title" in gap.missing_sections

    def test_whitespace_title_triggers_gap(self):
        gap = detect_completeness_gap(
            title="   ",
            has_claims=True,
            has_spec_body=True,
            has_abstract=True,
        )
        assert gap is not None
        assert "title" in gap.missing_sections

    def test_multiple_missing_listed(self):
        gap = detect_completeness_gap(
            title="",
            has_claims=False,
            has_spec_body=True,
            has_abstract=False,
        )
        assert gap is not None
        assert set(gap.missing_sections) == {"title", "claims", "abstract"}


# ── flatten_checks_from_lists ────────────────────────────────────────────


class TestFlatten:
    def test_flattens_multiple_lists(self):
        a = [_check("pass", "check.spec.paragraphSequential.pass")]
        b = [_check("amend", "check.claims.selfDependent.amend")]
        c: list = []
        flat = flatten_checks_from_lists(a, b, c)
        assert len(flat) == 2

    def test_empty_lists_yield_empty(self):
        assert flatten_checks_from_lists() == []
        assert flatten_checks_from_lists([], [], []) == []
