# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
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
        assert results[0].reference == "专利法 §26 第1款、专利法实施细则 §17"

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
        assert results[0].reference == "专利法实施细则 §17"

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

    def test_invalid_ending_amend(self):
        doc = _make_cn_doc(
            technical_field=["本发明涉及数据处理"],  # no ending punctuation
            background=["现有技术存在问题。"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "amend"
        assert results[0].details_params["count"] == 1
        assert results[0].details_params["paragraphs"] == [1]

    def test_multiple_bad_endings(self):
        doc = _make_cn_doc(
            technical_field=["没有标点"],
            background=["也没有标点"],
            summary=["正确的。"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "amend"
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
        assert results[0].status == "amend"

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
        assert results[0].status == "amend"
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
        assert results[0].status == "amend"
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
        assert results[0].status == "amend"
        assert results[0].details_params["count"] == 1

    def test_strict_rejects_semicolon(self):
        # 背景技术 is strict — semicolon not accepted.
        doc = _make_cn_doc(
            technical_field=["技术领域段落。"],
            background=["现有技术存在问题；"],
        )
        results = check_paragraph_ending(doc)
        assert results[0].status == "amend"
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
        assert results[0].status == "amend"


# ── Check 5: Figure reference consistency ─────────────────────────────────


class TestFigureReferenceConsistency:
    def test_consistent_pass(self):
        doc = _make_cn_doc(
            drawings_description=["图1为结构示意图。", "图2为流程图。"],
            detailed_description=["如图1所示，装置包括模块。", "如图2所示，进行处理。"],
        )
        results = check_figure_reference_consistency(doc)
        assert results[0].status == "pass"

    def test_mismatch_verify(self):
        doc = _make_cn_doc(
            drawings_description=["图1为结构示意图。", "图3为侧视图。"],
            detailed_description=["如图1所示，装置包括模块。", "如图5所示，处理。"],
        )
        results = check_figure_reference_consistency(doc)
        assert results[0].status == "verify"
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
