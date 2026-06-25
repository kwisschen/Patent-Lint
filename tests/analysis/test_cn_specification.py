# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Tests for patentlint.analysis.cn_specification."""

from patentlint.analysis.cn_specification import (
    check_figure_reference_consistency,
    check_paragraph_ending,
    check_paragraph_numbering,
    check_patent_type_terminology,
    check_required_sections,
    check_section_ordering,
    check_spec_claim_reference,
    check_title,
)
from patentlint.models import Claim, CnPatentDocument


def _make_cn_doc(**overrides) -> CnPatentDocument:
    """Build a CnPatentDocument with reasonable defaults."""
    defaults = {
        "title": "一种数据处理装置",
        "technical_field": ["本发明涉及数据处理技术领域。"],
        "background": ["现有技术中存在数据处理效率低的问题。"],
        "summary": ["本发明提供一种数据处理装置，解决了上述问题。"],
        "drawings_description": ["图1为本发明实施例的结构示意图。"],
        "detailed_description": ["如图1所示，数据处理装置包括处理模块。"],
        "claims": [
            Claim(id=1, text="一种数据处理装置，包括处理模块。", independent=True),
        ],
        "abstract_text": "本发明提供一种数据处理装置。",
        "abstract_char_count": 12,
        # Default strategies: real anchors found for all three top-level
        # parts. Tests that simulate heading-removal override these.
        "section_source_strategies": {
            "claims": "body_anchor",
            "specification": "body_anchor",
            "abstract": "body_anchor",
        },
        "section_order": [
            "technical_field",
            "background",
            "summary",
            "drawings_description",
            "detailed_description",
        ],
        "input_format": "docx",
    }
    defaults.update(overrides)
    return CnPatentDocument(**defaults)


# ── Check 1: Required sections ───────────────────────────────────────────


class TestRequiredSections:
    def test_all_present_pass(self):
        doc = _make_cn_doc()
        results = check_required_sections(doc)
        assert len(results) == 1
        assert results[0].status == "pass"
        assert results[0].message_key == "check.cn.spec.requiredSections.pass"

    def test_missing_sections_amend(self):
        doc = _make_cn_doc(technical_field=[], summary=[""])
        results = check_required_sections(doc)
        assert results[0].status == "amend"
        assert "技术领域" in results[0].details_params["sections"]
        assert "发明内容" in results[0].details_params["sections"]

    def test_empty_strings_count_as_missing(self):
        doc = _make_cn_doc(background=["", "  "])
        results = check_required_sections(doc)
        assert results[0].status == "amend"
        assert "背景技术" in results[0].details_params["sections"]

    def test_missing_abstract(self):
        doc = _make_cn_doc(abstract_text="")
        results = check_required_sections(doc)
        assert results[0].status == "amend"
        assert "摘要" in results[0].details_params["sections"]

    def test_missing_abstract_whitespace_only(self):
        doc = _make_cn_doc(abstract_text="   \n  ")
        results = check_required_sections(doc)
        assert results[0].status == "amend"
        assert "摘要" in results[0].details_params["sections"]

    def test_missing_claims(self):
        doc = _make_cn_doc(claims=[])
        results = check_required_sections(doc)
        assert results[0].status == "amend"
        assert "权利要求书" in results[0].details_params["sections"]

    def test_reference_field(self):
        doc = _make_cn_doc(abstract_text="", section_source_strategies={"claims": "body_anchor", "specification": "body_anchor", "abstract": "none"})
        results = check_required_sections(doc)
        assert results[0].reference == "专利法 §26 第1款、专利法实施细则 §20"

    def test_claims_recovered_via_density_flags_missing_heading(self):
        """When the 权利要求书 anchor is missing and claims were
        recovered from a density-tier fallback, the heading-missing
        defect must surface even though doc.claims is non-empty."""
        doc = _make_cn_doc(section_source_strategies={
            "claims": "claim_density",
            "specification": "body_anchor",
            "abstract": "body_anchor",
        })
        results = check_required_sections(doc)
        assert results[0].status == "amend"
        assert "权利要求书" in results[0].details_params["sections"]

    def test_claims_strategy_none_flags_missing_heading(self):
        doc = _make_cn_doc(claims=[], section_source_strategies={
            "claims": "none",
            "specification": "body_anchor",
            "abstract": "body_anchor",
        })
        results = check_required_sections(doc)
        assert results[0].status == "amend"
        assert "权利要求书" in results[0].details_params["sections"]

    def test_abstract_via_inid_fallback_passes(self):
        """INID cover-page extraction populates abstract_text but leaves
        strategies["abstract"]="none". Treat as valid (publication
        format) — flagging would false-positive on legitimate uploads."""
        doc = _make_cn_doc(section_source_strategies={
            "claims": "body_anchor",
            "specification": "body_anchor",
            "abstract": "none",
        }, abstract_text="本发明提供一种装置。")
        results = check_required_sections(doc)
        assert results[0].status == "pass"

    def test_drawings_description_required_when_figures_referenced(self):
        doc = _make_cn_doc(drawings_description=[], figure_refs=["1", "2"])
        results = check_required_sections(doc)
        assert results[0].status == "amend"
        assert "附图说明" in results[0].details_params["sections"]

    def test_drawings_description_optional_when_no_figures(self):
        doc = _make_cn_doc(drawings_description=[], figure_refs=[])
        results = check_required_sections(doc)
        assert results[0].status == "pass"


# ── Check 2: Section ordering ────────────────────────────────────────────


class TestSectionOrdering:
    def test_correct_order_pass(self):
        doc = _make_cn_doc()
        results = check_section_ordering(doc)
        assert results[0].status == "pass"
        assert results[0].message_key == "check.cn.spec.sectionOrdering.pass"

    def test_wrong_order_amend(self):
        # 具体实施方式 encountered before 发明内容 — classic MPEP-ordered
        # spec reused for CNIPA filing without reordering.
        doc = _make_cn_doc(
            section_order=[
                "technical_field",
                "detailed_description",
                "background",
            ]
        )
        results = check_section_ordering(doc)
        assert results[0].status == "amend"
        assert results[0].message_key == "check.cn.spec.sectionOrdering.amend"
        assert results[0].reference == "专利法实施细则 §20"

    def test_empty_section_order_passes(self):
        # No headers found (degenerate input). Vacuously sorted.
        doc = _make_cn_doc(section_order=[])
        results = check_section_ordering(doc)
        assert results[0].status == "pass"

    def test_non_canonical_keys_ignored(self):
        # Unknown keys filtered out; remaining canonical indices still sorted.
        doc = _make_cn_doc(
            section_order=["claims", "technical_field", "abstract", "background"]
        )
        results = check_section_ordering(doc)
        assert results[0].status == "pass"

    def test_missing_middle_section_passes(self):
        # Skipping a canonical section (here: summary) is not an ordering
        # violation — required-sections check handles the absence.
        doc = _make_cn_doc(
            section_order=["technical_field", "background", "detailed_description"]
        )
        results = check_section_ordering(doc)
        assert results[0].status == "pass"


# ── Check 3: Paragraph numbering ─────────────────────────────────────────


class TestParagraphNumbering:
    def test_xml_sequential_pass(self):
        doc = _make_cn_doc(input_format="xml", paragraph_numbers=[1, 2, 3, 4, 5])
        results = check_paragraph_numbering(doc)
        assert results[0].status == "pass"

    def test_xml_gap_amend(self):
        doc = _make_cn_doc(input_format="xml", paragraph_numbers=[1, 2, 4, 5])
        results = check_paragraph_numbering(doc)
        assert results[0].status == "amend"
        assert results[0].message_key == "check.cn.spec.paragraphNumbering.amendXmlGap"
        assert results[0].details_params["prev"] == 2
        assert results[0].details_params["next"] == 4

    def test_xml_duplicate_amend(self):
        doc = _make_cn_doc(input_format="xml", paragraph_numbers=[1, 2, 2, 3])
        results = check_paragraph_numbering(doc)
        assert results[0].status == "amend"
        # Duplicate detection runs BEFORE gap detection, so [1, 2, 2, 3]
        # fires .amendXmlDuplicate (not .amendXmlGap).
        assert results[0].message_key == "check.cn.spec.paragraphNumbering.amendXmlDuplicate"
        assert results[0].details_params["paragraphs"] == [2]
        assert results[0].details_params["count"] == 1

    def test_xml_empty_pass(self):
        doc = _make_cn_doc(input_format="xml", paragraph_numbers=[])
        results = check_paragraph_numbering(doc)
        assert results[0].status == "pass"

    def test_docx_no_numbering_pass(self):
        doc = _make_cn_doc(input_format="docx", has_paragraph_numbering=False)
        results = check_paragraph_numbering(doc)
        assert results[0].status == "pass"

    def test_docx_has_numbering_amend(self):
        doc = _make_cn_doc(input_format="docx", has_paragraph_numbering=True)
        results = check_paragraph_numbering(doc)
        assert results[0].status == "amend"
        assert results[0].message_key == "check.cn.spec.paragraphNumbering.amendDocx"


# ── Check 4: Paragraph ending ────────────────────────────────────────────


class TestParagraphEnding:
    def test_all_valid_pass(self):
        doc = _make_cn_doc(
            technical_field=["本发明涉及数据处理。"],
            background=["现有技术存在问题！"],
            summary=["本发明解决了问题？"],
            detailed_description=["以下结合附图说明："],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "pass"

    def test_invalid_ending_verify(self):
        doc = _make_cn_doc(
            technical_field=["本发明涉及数据处理"],  # no ending punctuation
            background=["现有技术存在问题。"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "verify"
        assert results[0].details_params["count"] == 1
        assert results[0].details_params["paragraphs"] == [1]

    def test_multiple_bad_endings(self):
        doc = _make_cn_doc(
            technical_field=["没有标点"],
            background=["也没有标点"],
            summary=["正确的。"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "verify"
        assert results[0].details_params["count"] == 2
        assert results[0].details_params["paragraphs"] == [1, 2]

    def test_empty_paragraphs_skipped(self):
        doc = _make_cn_doc(
            technical_field=["", "  ", "正确的。"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "pass"

    def test_ascii_period_not_accepted(self):
        doc = _make_cn_doc(technical_field=["This ends with a period."])
        results = check_paragraph_ending(doc)
        assert results[0].status == "verify"

    def test_bracket_prefix_used_as_locator(self):
        # When the drafter has left manual [NNNN] prefixes in the file
        # (separately flagged by check_paragraph_numbering), report the
        # bracket number as the locator so the two checks don't contradict
        # each other: the drafter can still find the flagged paragraph by
        # the exact string they typed before stripping the prefixes.
        doc = _make_cn_doc(
            technical_field=["[0001]  本发明涉及数据处理"],
            background=[
                "[0002]  正确的。",
                "[0003]  也没有标点",
            ],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "verify"
        assert results[0].details_params["paragraphs"] == ["[0001]", "[0003]"]

    def test_bracket_prefix_falls_back_to_ordinal(self):
        # Unnumbered paragraphs still use the ordinal counter so XML input
        # and plain-text callers keep their existing locator.
        doc = _make_cn_doc(
            technical_field=["正确的。", "没有标点"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].details_params["paragraphs"] == [2]

    def test_continuation_paragraph_inherits_parent_bracket_number(self):
        """A non-empty paragraph following a [NNNN]-prefixed paragraph
        but lacking its own [NNNN] is a Word-line continuation of the
        parent. Inherit the parent's [NNNN] so the flagged label
        matches the number the drafter sees in Word."""
        doc = _make_cn_doc(
            technical_field=[],
            background=[
                "[0003]  正确的。",
                "也没有标点",  # continuation of [0003]
            ],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "verify"
        # The flagged continuation reports as [0003], not as ordinal 2.
        assert results[0].details_params["paragraphs"] == ["[0003]"]

    def test_strict_rejects_colon(self):
        # 技术领域 is strict — colon not accepted even though relaxed
        # sections allow it.
        doc = _make_cn_doc(
            technical_field=["本发明涉及数据处理："],
            background=["背景段落。"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "verify"
        assert results[0].details_params["count"] == 1

    def test_strict_rejects_semicolon(self):
        # 背景技术 is strict — semicolon not accepted.
        doc = _make_cn_doc(
            technical_field=["技术领域段落。"],
            background=["现有技术存在问题；"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "verify"
        assert results[0].details_params["count"] == 1

    def test_relaxed_accepts_colon(self):
        # 发明内容 is relaxed — colon accepted for step/list introductions.
        doc = _make_cn_doc(
            summary=["本发明包括以下步骤："],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "pass"

    def test_relaxed_accepts_semicolon(self):
        # 附图说明 is relaxed — semicolon accepted for enumeration items.
        doc = _make_cn_doc(
            drawings_description=["图1是本发明的流程图；"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "pass"

    def test_relaxed_accepts_list_cap_yiji(self):
        # 具体实施方式 is relaxed — ；以及 penultimate list item allowed.
        doc = _make_cn_doc(
            detailed_description=["包括第一步骤；第二步骤；以及"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "pass"

    def test_relaxed_accepts_list_cap_ji(self):
        doc = _make_cn_doc(
            summary=["提供第一组件；第二组件；及"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "pass"

    def test_figure_caption_only_skipped(self):
        # Bare figure captions below inserted images are not prose.
        doc = _make_cn_doc(
            drawings_description=[
                "图1是示意图。",
                "图1",
                "图4A",
                "图5C",
            ],
            detailed_description=["如图1所示，装置包括处理器。"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "pass"

    def test_figure_prose_still_checked(self):
        # A paragraph like "图1、图2及图3" is prose referring to figures,
        # not a standalone caption; must end with punctuation.
        doc = _make_cn_doc(
            drawings_description=["图1、图2及图3显示了本发明"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "verify"


# ── Check 5: Figure reference consistency ─────────────────────────────────


class TestFigureReferenceConsistency:
    def test_consistent_pass(self):
        doc = _make_cn_doc(
            drawings_description=["图1为结构示意图。", "图2为流程图。"],
            detailed_description=["如图1所示，装置包括模块。", "如图2所示，进行处理。"],
        )
        results = check_figure_reference_consistency(doc)
        assert results[0].status == "pass"

    def test_mismatch_amend(self):
        doc = _make_cn_doc(
            drawings_description=["图1为结构示意图。", "图3为侧视图。"],
            detailed_description=["如图1所示，装置包括模块。", "如图5所示，处理。"],
        )
        results = check_figure_reference_consistency(doc)
        assert results[0].status == "amend"
        payload = results[0].details_params["figure_ref_inconsistency"]
        assert 3 in payload["only_drawings"]
        assert 5 in payload["only_embodiment"]
        assert payload["jurisdiction"] == "cn"

    def test_both_empty_pass(self):
        doc = _make_cn_doc(drawings_description=[], detailed_description=[])
        results = check_figure_reference_consistency(doc)
        assert results[0].status == "pass"


# ── Check 6: Patent type terminology ──────────────────────────────────────


class TestPatentTypeTerminology:
    def test_consistent_pass(self):
        doc = _make_cn_doc(
            technical_field=["本发明涉及数据处理。"],
            summary=["本发明提供一种装置。"],
        )
        results = check_patent_type_terminology(doc)
        assert results[0].status == "pass"

    def test_mixed_verify(self):
        doc = _make_cn_doc(
            technical_field=["本发明涉及数据处理。"],
            summary=["本实用新型提供一种装置。"],
        )
        results = check_patent_type_terminology(doc)
        assert results[0].status == "verify"
        assert results[0].details_params["term"] == "本实用新型"

    def test_neither_term_pass(self):
        doc = _make_cn_doc(
            technical_field=["涉及数据处理技术领域。"],
            summary=["提供一种装置。"],
        )
        results = check_patent_type_terminology(doc)
        assert results[0].status == "pass"


# ── Check 7: Title ───────────────────────────────────────────────────────


class TestTitle:
    def test_good_title_pass(self):
        doc = _make_cn_doc(title="一种数据处理装置")
        results = check_title(doc)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_long_title_amend(self):
        # 26 CJK chars
        doc = _make_cn_doc(title="一种用于高速大容量数据存储及传输处理的智能化多功能集成电路控制装置")
        results = check_title(doc)
        amend = [r for r in results if r.status == "amend"]
        assert any(r.message_key == "check.cn.spec.title.amendLength" for r in amend)

    def test_trademark_amend(self):
        doc = _make_cn_doc(title="一种Apple®处理装置")
        results = check_title(doc)
        amend = [r for r in results if r.status == "amend"]
        assert any(r.message_key == "check.cn.spec.title.amendContent" for r in amend)

    def test_model_number_amend(self):
        doc = _make_cn_doc(title="一种AB-1234处理装置")
        results = check_title(doc)
        amend = [r for r in results if r.status == "amend"]
        assert any(r.message_key == "check.cn.spec.title.amendContent" for r in amend)

    def test_empty_title_amend(self):
        doc = _make_cn_doc(title="")
        results = check_title(doc)
        assert results[0].status == "amend"

    def test_both_length_and_content_fail(self):
        long_title = "一种用于高速大容量数据存储及传输处理的智能化多功能集成电路控制装置型号"
        doc = _make_cn_doc(title=long_title + "®")
        results = check_title(doc)
        amend_keys = {r.message_key for r in results if r.status == "amend"}
        assert "check.cn.spec.title.amendLength" in amend_keys
        assert "check.cn.spec.title.amendContent" in amend_keys


# ── Check 8: Spec claim reference ────────────────────────────────────────


class TestSpecClaimReference:
    def test_no_reference_pass(self):
        doc = _make_cn_doc()
        results = check_spec_claim_reference(doc)
        assert results[0].status == "pass"

    def test_claim_reference_amend(self):
        doc = _make_cn_doc(
            detailed_description=["如权利要求1所述的装置，其特征在于包括模块。"],
        )
        results = check_spec_claim_reference(doc)
        assert results[0].status == "amend"
        assert results[0].message_key == "check.cn.spec.claimReference.amend"
        assert "权利要求" in results[0].details_params["snippet"]
        assert results[0].details_params["count"] == 1
        assert results[0].details_params["paragraphs"] == [5]

    def test_claim_reference_with_spaces(self):
        doc = _make_cn_doc(
            detailed_description=["如权利要求 3 所述的方法。"],
        )
        results = check_spec_claim_reference(doc)
        assert results[0].status == "amend"


# ─────────────────────────────────────────────────────────────────────────
# R-refnum-2 — measurement-unit exclusion (issues #100/#101/#102)
# ─────────────────────────────────────────────────────────────────────────


class TestRefnumMeasurementExclusion:
    """The CJK refnum extractor must reject `\\d+\\s*<unit>` measurement
    patterns. Drafters write `平均粒徑可在10 μm至100 μm的範圍` (per #101
    TW report) — the digits are measurement values, not component
    reference numerals. Pre-fix the extractor captured `10` as a refnum
    paired with the clause-fragment `平均粒徑可在` as its "name."
    """

    def test_micro_meter_with_space_not_captured(self):
        """Greek small letter mu (U+03BC) — `10 μm` with whitespace."""
        from patentlint.analysis.cn_specification import (
            _cn_extract_numeral_name_pairs,
        )
        text = "平均粒徑可在10 μm至100 μm的範圍。"
        assert _cn_extract_numeral_name_pairs(text) == []

    def test_micro_meter_no_space_not_captured(self):
        """`10μm` (no whitespace) — same exclusion via \\s* lookahead."""
        from patentlint.analysis.cn_specification import (
            _cn_extract_numeral_name_pairs,
        )
        text = "粒徑為10μm的顆粒。"
        assert _cn_extract_numeral_name_pairs(text) == []

    def test_micro_sign_codepoint_also_excluded(self):
        """Micro sign U+00B5 (`µ`) — visually identical to U+03BC,
        sometimes used by drafters from copy/paste sources."""
        from patentlint.analysis.cn_specification import (
            _cn_extract_numeral_name_pairs,
        )
        text = "粒徑為10µm的顆粒。"  # U+00B5 micro sign
        assert _cn_extract_numeral_name_pairs(text) == []

    def test_other_si_units_with_letter_excluded(self):
        """`10 mm`, `100 nm`, `5 wt%` — pre-existing letter exclusion
        works once \\s* lookahead is added."""
        from patentlint.analysis.cn_specification import (
            _cn_extract_numeral_name_pairs,
        )
        for text in (
            "粒徑為10 mm的顆粒。",
            "厚度為100 nm的薄膜。",
            "含量為5 wt%。",
        ):
            assert _cn_extract_numeral_name_pairs(text) == [], text

    def test_real_refnum_still_captured(self):
        """Negative control — real component refnums (`齒輪10`) must
        still be captured. The fix narrowly targets measurement contexts."""
        from patentlint.analysis.cn_specification import (
            _cn_extract_numeral_name_pairs,
        )
        text = "所述齒輪10與所述軸件20連接。"
        pairs = _cn_extract_numeral_name_pairs(text)
        nums = [n for n, _ in pairs]
        assert "10" in nums and "20" in nums, pairs

    def test_quantifier_classifier_over_capture_collapses_213_244(self):
        """#213/#244: quantifier+classifier prefixes (兩個/多條/每條/至少一條)
        and 條+ref (條所述) bled into the captured numeralConsistency element
        name, producing phantom conflicts (條所述導通線路 vs 多條導通線路 for the
        same numeral). They must collapse to the bare head noun."""
        from patentlint.analysis.cn_specification import _cn_d1_head_noun
        for raw, want in {
            "兩個所述上側柱": "上側柱",
            "條所述導通線路": "導通線路",
            "多條導通線路": "導通線路",
            "條所述串接線路": "串接線路",
            "少一條串接線路": "串接線路",
            "至少一條串接線路": "串接線路",
        }.items():
            assert _cn_d1_head_noun(raw) == want, (raw, _cn_d1_head_noun(raw))
        # FN guards — bare 條-initial nouns keep their 條 (no ref prefix follows)
        for noun in ("條碼", "條紋", "條狀結構"):
            assert _cn_d1_head_noun(noun) == noun, noun

    def test_real_refnum_followed_by_measurement_unchanged(self):
        """`齒輪10之直徑為10 μm` — first `10` (refnum) captured, second
        `10` (measurement) excluded."""
        from patentlint.analysis.cn_specification import (
            _cn_extract_numeral_name_pairs,
        )
        text = "所述齒輪10之直徑為10 μm。"
        pairs = _cn_extract_numeral_name_pairs(text)
        # Exactly one capture: the refnum 10 paired with 齒輪
        assert len(pairs) == 1, pairs
        assert pairs[0] == ("10", "齒輪"), pairs


def test_cjk_measurement_tail_excluded_266():
    """#266: `10毫升` / `100 毫升` are measurement values, not refnums."""
    from patentlint.analysis.cn_specification import _cn_extract_numeral_name_pairs
    assert _cn_extract_numeral_name_pairs("每公斤體重 10毫升至12 毫升以內") == []
    assert _cn_extract_numeral_name_pairs("其定義為每100 毫升溶液") == []


def test_cjk_single_char_unit_does_not_drop_refnum_266():
    """FN guard: single-char units (升/克/度) are NOT in the tail set, so a
    real refnum followed by a verb/noun starting with that char is kept."""
    from patentlint.analysis.cn_specification import _cn_extract_numeral_name_pairs
    assert _cn_extract_numeral_name_pairs("按鈕10升起並轉動") == [("10", "按鈕")]
    assert _cn_extract_numeral_name_pairs("感測器20連接") == [("20", "感測器")]


def test_interior_conjunction_split_parity_242():
    """#242: `係亦可為與步驟S50` — the ordinal-keyed head-noun extractor
    must apply the same `<NP_A>與<NP_B>` conjunction split (#158) as the
    non-ordinal one. Result: `步驟` (then dropped as generic) → no phantom
    refnum for S50; and `散熱片與基板10` keeps the right element `基板`."""
    from patentlint.analysis.cn_specification import (
        _cn_extract_numeral_name_pairs,
        _cn_d1_head_noun_with_ordinal,
    )
    assert _cn_extract_numeral_name_pairs("中之閾值，係亦可為與步驟S50中之閾值相同") == []
    assert _cn_d1_head_noun_with_ordinal("係亦可為與步驟") == ""
    # #158 semantics preserved in the ordinal path
    assert _cn_extract_numeral_name_pairs("該散熱片與基板10連接") == [("10", "基板")]


class TestCnD1FnSafePrune:
    """FN-safe CJK extraction-noise prune (gold-validated 2026-06-25, CN+TW): a 1x
    ordinal variant or substring of the canonical is dropped; distinct nouns and
    repeated outliers are kept."""

    def test_prune_ordinal_variant_single_occurrence(self):
        from patentlint.analysis.cn_specification import _cn_prune_fn_safe_outliers
        # '第二|外殼' (1x) vs canonical '第一|外殼' — same base noun, drop
        assert _cn_prune_fn_safe_outliers(
            [{"name": "第二|外殼", "count": 1}], "第一|外殼") == []

    def test_prune_substring_fragment_single_occurrence(self):
        from patentlint.analysis.cn_specification import _cn_prune_fn_safe_outliers
        # '容槽' (1x) is a substring of '軸承容槽' — fragment, drop
        assert _cn_prune_fn_safe_outliers(
            [{"name": "|容槽", "count": 1}], "|軸承容槽") == []

    def test_prune_keeps_distinct_noun(self):
        from patentlint.analysis.cn_specification import _cn_prune_fn_safe_outliers
        outs = [{"name": "|電極", "count": 1}]  # distinct element vs 阵列 — KEEP
        assert _cn_prune_fn_safe_outliers(outs, "|阵列") == outs

    def test_prune_keeps_repeated_outlier(self):
        from patentlint.analysis.cn_specification import _cn_prune_fn_safe_outliers
        outs = [{"name": "第二|外殼", "count": 2}]  # 2x, not a bleed — KEEP
        assert _cn_prune_fn_safe_outliers(outs, "第一|外殼") == outs


class TestCnD1BioSymbolAndMutation:
    """Engine-3 R2 mirror (ADR-159): CJK D1 must not capture biology/clinical
    biomarker symbols or amino-acid mutation notation as Latin-prefix reference
    designators — they are never drawing elements. Real designators (R1/IC2/
    uppercase-suffix U1A, and 1-digit C2D) must still be captured. Covers CN
    AND TW (tw_specification reuses this extractor)."""

    def _nums(self, text):
        from patentlint.analysis.cn_specification import _cn_extract_numeral_name_pairs
        return {n for n, _ in _cn_extract_numeral_name_pairs(text)}

    def test_bio_and_mutation_symbols_not_captured(self):
        # CJK noun must precede the ref for the Latin pattern to fire.
        nums = self._nums(
            "抗體 CD3 與抗體 CD8 結合。受體 CLDN18 表現。"
            "突變 K417T 與突變 L858R。鏈路 V2X 通訊。"
        )
        for sym in ("CD3", "CD8", "CLDN18", "K417T", "L858R", "V2X"):
            assert sym not in nums, sym

    def test_real_designators_still_captured(self):
        nums = self._nums("電阻 R1 與電容 C2。晶片 IC2。節點 C2D 連接。")
        for sym in ("R1", "C2", "IC2", "C2D"):
            assert sym in nums, sym
