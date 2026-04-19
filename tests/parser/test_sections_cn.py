# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for CN patent .docx section extraction."""

from __future__ import annotations

from patentlint.parser.docx_loader import DocxSection
from patentlint.parser.sections_cn import (
    _backfill_numpr_prefixes,
    _detect_paragraph_numbering,
    _extract_inid_title_abstract,
    _extract_title,
    _identify_section,
    _merge_publication_continuations,
    _presplit_mid_paragraph,
    _split_spec_subsections,
    detect_patent_document_cn,
    extract_cn_sections_from_docx,
)


# ---------------------------------------------------------------------------
# _identify_section
# ---------------------------------------------------------------------------


class TestIdentifySection:
    def test_identify_spec(self):
        assert _identify_section("说明书") == "specification"

    def test_identify_claims(self):
        assert _identify_section("权利要求书") == "claims"

    def test_identify_abstract(self):
        assert _identify_section("说明书摘要") == "abstract"

    def test_identify_abstract_short(self):
        assert _identify_section("摘要") == "abstract"

    def test_identify_abstract_drawing(self):
        assert _identify_section("摘要附图") == "abstract_drawing"

    def test_identify_drawings(self):
        assert _identify_section("说明书附图") == "drawings"

    def test_identify_empty(self):
        assert _identify_section("") is None

    def test_identify_unknown(self):
        assert _identify_section("其他文档") is None

    def test_spec_does_not_match_abstract(self):
        # "说明书摘要" must return "abstract", NOT "specification"
        assert _identify_section("说明书摘要") == "abstract"

    def test_spec_does_not_match_drawings(self):
        # "说明书附图" must return "drawings", NOT "specification"
        assert _identify_section("说明书附图") == "drawings"


# ---------------------------------------------------------------------------
# _split_spec_subsections
# ---------------------------------------------------------------------------


class TestSplitSpecSubsections:
    def test_split_all_sections(self):
        paragraphs = [
            "技术领域",
            "技术段落",
            "背景技术",
            "背景段落",
            "发明内容",
            "发明段落",
            "附图说明",
            "附图段落",
            "具体实施方式",
            "实施段落",
        ]
        result, section_order = _split_spec_subsections(paragraphs)
        assert result["technical_field"] == ["技术段落"]
        assert result["background"] == ["背景段落"]
        assert result["summary"] == ["发明段落"]
        assert result["drawings_description"] == ["附图段落"]
        assert result["detailed_description"] == ["实施段落"]
        assert section_order == [
            "technical_field",
            "background",
            "summary",
            "drawings_description",
            "detailed_description",
        ]

    def test_split_missing_section(self):
        paragraphs = [
            "技术领域",
            "技术段落",
            "发明内容",
            "发明段落",
        ]
        result, section_order = _split_spec_subsections(paragraphs)
        assert result["technical_field"] == ["技术段落"]
        assert result["background"] == []
        assert result["summary"] == ["发明段落"]
        assert section_order == ["technical_field", "summary"]

    def test_split_paragraphs_before_first_header(self):
        paragraphs = [
            "这是标题",
            "这也不属于任何节",
            "技术领域",
            "技术段落",
        ]
        result, section_order = _split_spec_subsections(paragraphs)
        assert result["technical_field"] == ["技术段落"]
        assert section_order == ["technical_field"]
        # Paragraphs before first header should not appear in any sub-section
        for paras in result.values():
            assert "这是标题" not in paras
            assert "这也不属于任何节" not in paras

    def test_split_fullwidth_spaces(self):
        paragraphs = ["\u3000技术领域\u3000", "段落"]
        result, section_order = _split_spec_subsections(paragraphs)
        assert result["technical_field"] == ["段落"]
        assert section_order == ["technical_field"]

    def test_section_order_non_canonical(self):
        # Headers encountered out of canonical order: 具体实施方式 before 发明内容
        # The parser preserves encounter order so check_section_ordering can flag.
        paragraphs = [
            "技术领域",
            "技术段落",
            "具体实施方式",
            "实施段落",
            "发明内容",
            "发明段落",
        ]
        result, section_order = _split_spec_subsections(paragraphs)
        assert result["technical_field"] == ["技术段落"]
        assert result["detailed_description"] == ["实施段落"]
        assert result["summary"] == ["发明段落"]
        assert section_order == [
            "technical_field",
            "detailed_description",
            "summary",
        ]

    def test_section_order_first_occurrence_only(self):
        # A reappearing header does not re-append to section_order.
        paragraphs = [
            "技术领域",
            "技术段落",
            "背景技术",
            "背景段落",
            "技术领域",
            "又一技术段落",
        ]
        _, section_order = _split_spec_subsections(paragraphs)
        assert section_order == ["technical_field", "background"]


# ---------------------------------------------------------------------------
# _detect_paragraph_numbering
# ---------------------------------------------------------------------------


class TestDetectParagraphNumbering:
    def test_no_numbering(self):
        has_num, nums = _detect_paragraph_numbering(["普通段落", "另一段"])
        assert has_num is False
        assert nums == []

    def test_has_numbering(self):
        has_num, nums = _detect_paragraph_numbering(
            ["[0001] 段落一", "[0002] 段落二"]
        )
        assert has_num is True
        assert nums == [1, 2]


# ---------------------------------------------------------------------------
# _extract_title
# ---------------------------------------------------------------------------


class TestExtractTitle:
    def test_title_before_sections(self):
        assert _extract_title(["一种测试装置", "技术领域", "段落"]) == "一种测试装置"

    def test_no_title(self):
        assert _extract_title(["技术领域", "段落"]) == ""


# ---------------------------------------------------------------------------
# _extract_inid_title_abstract (Phase 9 #70 — publication fallback)
# ---------------------------------------------------------------------------


class TestExtractInidTitleAbstract:
    def test_invention_title_and_abstract(self):
        paras = [
            "(19)国家知识产权局",
            "(12)发明专利",
            "(54)发明名称",
            "用于调整神经网络的方法和装置",
            "(57)摘要",
            "本申请提供了一种用于调整神经网络的方法和装置。",
            "权利要求书1/2页",
            "1. 一种方法。",
        ]
        sections = [DocxSection(header_text=None, paragraphs=paras)]
        title, abstract = _extract_inid_title_abstract(sections)
        assert title == "用于调整神经网络的方法和装置"
        assert abstract == ["本申请提供了一种用于调整神经网络的方法和装置。"]

    def test_utility_model_title(self):
        paras = [
            "(12)实用新型专利",
            "(54)实用新型名称",
            "折叠机构以及内折柔性屏设备",
            "(57)摘要",
            "本实用新型公开了一种折叠机构。",
            "权利要求书",
        ]
        sections = [DocxSection(header_text=None, paragraphs=paras)]
        title, abstract = _extract_inid_title_abstract(sections)
        assert title == "折叠机构以及内折柔性屏设备"
        assert abstract == ["本实用新型公开了一种折叠机构。"]

    def test_design_patent_title(self):
        paras = [
            "(54)外观设计名称",
            "手机外壳",
            "(57)摘要",
            "本外观设计。",
        ]
        sections = [DocxSection(header_text=None, paragraphs=paras)]
        title, _ = _extract_inid_title_abstract(sections)
        assert title == "手机外壳"

    def test_abstract_stops_at_claims_anchor(self):
        paras = [
            "(54)发明名称",
            "一种方法",
            "(57)摘要",
            "摘要第一段。",
            "摘要第二段。",
            "权\t利\t要\t求\t书\t1/3 页",
            "1. 后续不应纳入摘要。",
        ]
        sections = [DocxSection(header_text=None, paragraphs=paras)]
        _, abstract = _extract_inid_title_abstract(sections)
        assert abstract == ["摘要第一段。", "摘要第二段。"]

    def test_abstract_stops_at_next_inid_code(self):
        paras = [
            "(54)发明名称",
            "一种方法",
            "(57)摘要",
            "摘要内容。",
            "(71)申请人",
            "不应纳入摘要的申请人信息。",
        ]
        sections = [DocxSection(header_text=None, paragraphs=paras)]
        _, abstract = _extract_inid_title_abstract(sections)
        assert abstract == ["摘要内容。"]

    def test_drafter_file_returns_empty(self):
        """Drafter 五书模板 files have no INID cover — extraction returns empty."""
        paras = [
            "一种测试装置",
            "技术领域",
            "本发明涉及测试领域。",
        ]
        sections = [DocxSection(header_text=None, paragraphs=paras)]
        title, abstract = _extract_inid_title_abstract(sections)
        assert title == ""
        assert abstract == []

    def test_title_skips_blank_paragraphs(self):
        paras = [
            "(54)发明名称",
            "",
            "   ",
            "真实标题",
            "(57)摘要",
            "摘要。",
        ]
        sections = [DocxSection(header_text=None, paragraphs=paras)]
        title, _ = _extract_inid_title_abstract(sections)
        assert title == "真实标题"


# ---------------------------------------------------------------------------
# _merge_publication_continuations (Phase 9 #69 — PDF-column fragmentation)
# ---------------------------------------------------------------------------


class TestMergePublicationContinuations:
    def test_orphan_continuation_merges_into_preceding_numbered(self):
        paras = [
            "[0317]\t作为示例而非限定，在本申请实施例中，可穿戴设备也可以称为穿戴式智能设备，",
            "是应用穿戴式技术对日常穿戴进行智能化设计、开发出可以穿戴的设备的总称。",
            "[0318]\t下一段。",
        ]
        result = _merge_publication_continuations(paras)
        assert len(result) == 2
        assert result[0].startswith("[0317]")
        assert "是应用穿戴式技术" in result[0]
        assert result[1] == "[0318]\t下一段。"

    def test_multiple_continuations_merge_into_one(self):
        paras = [
            "[0100]\t第一行，",
            "第二行，",
            "第三行。",
            "[0101]\t新段。",
        ]
        result = _merge_publication_continuations(paras)
        assert len(result) == 2
        assert "第一行" in result[0]
        assert "第二行" in result[0]
        assert "第三行" in result[0]

    def test_subsection_header_breaks_merge(self):
        paras = [
            "[0010]\t背景段落，",
            "背景技术",
            "[0011]\t新章节段落。",
        ]
        result = _merge_publication_continuations(paras)
        assert len(result) == 3
        assert result[0] == "[0010]\t背景段落，"
        assert result[1] == "背景技术"
        assert result[2] == "[0011]\t新章节段落。"

    def test_drafter_file_no_numbering_passthrough(self):
        """Drafter 五书模板 files have no [NNNN] numbering — return unchanged."""
        paras = [
            "本发明涉及一种测试装置。",
            "所述装置包括处理器。",
            "所述处理器用于执行指令。",
        ]
        result = _merge_publication_continuations(paras)
        assert result == paras

    def test_leading_orphan_before_first_numbered(self):
        """Orphan paragraphs before the first [NNNN] preserved as-is."""
        paras = [
            "序言段落",
            "[0001]\t第一段。",
            "[0002]\t第二段。",
        ]
        result = _merge_publication_continuations(paras)
        assert result == paras


# ---------------------------------------------------------------------------
# extract_cn_sections_from_docx
# ---------------------------------------------------------------------------


class TestExtractCnSectionsFromDocx:
    def test_full_extraction(self):
        sections = [
            DocxSection(header_text="说明书摘要", paragraphs=["摘要文本内容。"]),
            DocxSection(header_text="摘要附图", paragraphs=[]),
            DocxSection(
                header_text="权利要求书",
                paragraphs=[
                    "1. 一种测试装置，其特征在于，包括第一组件。",
                    "2. 如权利要求1所述的测试装置，其特征在于，还包括第二组件。",
                ],
            ),
            DocxSection(
                header_text="说明书",
                paragraphs=[
                    "一种测试装置",
                    "技术领域",
                    "本发明涉及测试装置。",
                    "背景技术",
                    "现有技术存在问题。",
                    "发明内容",
                    "本发明提供解决方案。",
                    "附图说明",
                    "图1是结构示意图。",
                    "具体实施方式",
                    "如图1所示，包括组件。",
                ],
            ),
            DocxSection(header_text="说明书附图", paragraphs=[]),
        ]
        doc = extract_cn_sections_from_docx(sections)
        assert doc.title == "一种测试装置"
        assert len(doc.technical_field) == 1
        assert "测试装置" in doc.technical_field[0]
        assert len(doc.background) == 1
        assert len(doc.summary) == 1
        assert len(doc.drawings_description) == 1
        assert len(doc.detailed_description) == 1
        assert len(doc.claims) == 2
        assert doc.claims[0].independent is True
        assert doc.claims[1].dependencies == [1]
        assert doc.abstract_text == "摘要文本内容。"
        assert doc.input_format == "docx"
        assert doc.has_paragraph_numbering is False

    def test_no_spec_section(self):
        sections = [
            DocxSection(
                header_text="权利要求书",
                paragraphs=["1. 一种装置，其特征在于，包括组件。"],
            ),
            DocxSection(header_text="说明书摘要", paragraphs=["摘要内容。"]),
        ]
        doc = extract_cn_sections_from_docx(sections)
        assert doc.technical_field == []
        assert doc.title == ""
        assert len(doc.claims) == 1
        assert doc.claims[0].independent is True

    def test_figure_refs_extracted(self):
        sections = [
            DocxSection(
                header_text="说明书",
                paragraphs=[
                    "标题",
                    "附图说明",
                    "图1是第一视图。",
                    "图2是第二视图。",
                    "具体实施方式",
                    "如图1和图2所示，装置包括组件。",
                ],
            ),
        ]
        doc = extract_cn_sections_from_docx(sections)
        assert len(doc.figure_refs) > 0
        assert doc.figure_count >= 2


# ---------------------------------------------------------------------------
# detect_patent_document_cn
# ---------------------------------------------------------------------------


class TestDetectPatentDocumentCn:
    def test_true_with_spec_subsection_header(self):
        assert detect_patent_document_cn(["技术领域", "本发明涉及测试。"]) is True

    def test_true_with_background_header(self):
        assert detect_patent_document_cn(["背景技术", "现有方案存在问题。"]) is True

    def test_true_with_wushu_boundary_claims(self):
        assert detect_patent_document_cn(["权利要求书", "1. 一种装置。"]) is True

    def test_true_with_wushu_boundary_abstract(self):
        assert detect_patent_document_cn(["说明书摘要", "摘要内容。"]) is True

    def test_true_with_numbered_claims(self):
        paragraphs = [
            "1. 一种装置，其特征在于，包括组件。",
            "2. 如权利要求1所述的装置。",
            "3. 如权利要求2所述的装置。",
        ]
        assert detect_patent_document_cn(paragraphs) is True

    def test_true_with_fullwidth_period_claims(self):
        paragraphs = [
            "1．一种数据处理装置，其特征在于，包括处理器。",
            "2．如权利要求1所述的装置。",
            "3．如权利要求2所述的装置。",
        ]
        assert detect_patent_document_cn(paragraphs) is True

    def test_false_generic_document(self):
        paragraphs = [
            "会议纪要",
            "日期：2025年3月1日",
            "参会人员：张三、李四",
            "讨论事项：项目进展。",
        ]
        assert detect_patent_document_cn(paragraphs) is False

    def test_or_logic_single_signal(self):
        # Only sub-section header, no claims or boundary markers
        assert detect_patent_document_cn(["具体实施方式", "描述段落。"]) is True

    def test_fewer_than_three_claims_not_enough(self):
        paragraphs = ["1. 第一项。", "2. 第二项。"]
        assert detect_patent_document_cn(paragraphs) is False

    def test_phase_9_73_rejects_us_patent(self):
        """US English claims must not false-positive CN detector (Phase 9 #73)."""
        paragraphs = [
            "CLAIMS",
            "1. A method comprising step A.",
            "2. The method of claim 1, further comprising step B.",
            "3. The method of claim 1, wherein step A includes sub-step C.",
        ]
        assert detect_patent_document_cn(paragraphs) is False

    def test_phase_9_73_rejects_tw_patent(self):
        """TW 【】 bracket headers must reject the CN detector (Phase 9 #73)."""
        paragraphs = [
            "【中文發明名稱】",
            "一種蓋組件及帶蓋容器",
            "【技術領域】",
            "本發明涉及蓋組件的技術領域。",
            "1．一種蓋組件，包括蓋本體。",
            "2．如請求項1所述之蓋組件。",
            "3．如請求項2所述之蓋組件。",
        ]
        assert detect_patent_document_cn(paragraphs) is False


# ---------------------------------------------------------------------------
# _presplit_mid_paragraph — Phase 9 #59 fix
# ---------------------------------------------------------------------------


class TestPresplitMidParagraph:
    """Pre-split must recover mid-paragraph claim boundaries before the
    numPr backfill runs. Without this, the backfill counter drifts on
    sibling numPr claims that follow an embedded claim-start in a
    continuation paragraph (Phase 9 #59).
    """

    def test_passthrough_unaffected_paragraph(self):
        paras = ["1. 一种装置，包括组件A。"]
        flags = [False]
        out_paras, out_flags = _presplit_mid_paragraph(paras, flags)
        assert out_paras == paras
        assert out_flags == flags

    def test_passthrough_preserves_numpr_flag(self):
        paras = ["一种装置，包括组件A。"]
        flags = [True]
        out_paras, out_flags = _presplit_mid_paragraph(paras, flags)
        assert out_paras == paras
        assert out_flags == [True]

    def test_embedded_boundary_splits_continuation(self):
        # Continuation paragraph whose body embeds a new claim-start.
        # Matches CN113939805B c4 shape from the investigation.
        paras = [
            "所述处理器核还用于执行操作。 4 .根据权利要求1或2所述的硬件系统，其特征在于，"
        ]
        flags = [False]
        out_paras, out_flags = _presplit_mid_paragraph(paras, flags)
        assert len(out_paras) == 2
        assert out_paras[0] == "所述处理器核还用于执行操作。"
        assert out_paras[1].startswith("4 .根据权利要求")
        assert out_flags == [False, False]

    def test_numpr_flag_only_on_first_chunk(self):
        # numPr-flagged continuation paragraph (rare but possible) —
        # second chunk starts with a typed prefix and must NOT carry
        # the numPr flag or the backfill counter would double-advance.
        paras = [
            "所述处理器核还用于执行操作。 4 .根据权利要求1或2所述的硬件系统，其特征在于，"
        ]
        flags = [True]
        out_paras, out_flags = _presplit_mid_paragraph(paras, flags)
        assert len(out_paras) == 2
        assert out_flags == [True, False]

    def test_backfill_counter_resets_after_embedded_boundary(self):
        # Full scenario reproducing Phase 9 #59 CN113939805B c5/c6 drift.
        # Without pre-split, the backfill counter would drift and the
        # numPr paragraphs at indices 3+4 would emit as claim 4 / 5
        # instead of 5 / 6.
        paras = [
            "3. 如权利要求2所述的硬件系统，其特征在于，",
            "所述处理器核还用于执行操作。 4 .根据权利要求1或2所述的硬件系统，其特征在于，",
            # Next two are numPr-auto-numbered siblings (claims 5 and 6).
            "根据权利要求4所述的硬件系统，其特征在于，",
            "根据权利要求5所述的硬件系统，其特征在于，",
            # Typed resumption.
            "7. 如权利要求6所述的硬件系统。",
        ]
        flags = [False, False, True, True, False]
        split_paras, split_flags = _presplit_mid_paragraph(paras, flags)
        emitted = _backfill_numpr_prefixes(split_paras, split_flags)
        # Expect every claim-start paragraph to carry its correct N. prefix.
        prefixes = [p.split(".", 1)[0].strip() for p in emitted if "." in p]
        assert "3" in prefixes
        assert "4" in prefixes
        assert "5" in prefixes
        assert "6" in prefixes
        assert "7" in prefixes

    def test_no_split_without_content_char_lookahead(self):
        # A numeric token like "2.3" inside a claim body must not be
        # split. The regex requires a claim-start content char follows.
        paras = ["1 .一种方法，步骤S1中制备培养基；步骤S2中分离细胞。"]
        flags = [False]
        out_paras, out_flags = _presplit_mid_paragraph(paras, flags)
        assert out_paras == paras
        assert out_flags == flags

    def test_end_to_end_claim_ids_contiguous(self):
        # End-to-end: build a fake DocxSection, run through
        # extract_cn_sections_from_docx, confirm claim IDs are contiguous.
        claim_paras = [
            "1. 一种硬件系统，其特征在于，包括处理器核。",
            "2. 如权利要求1所述的硬件系统，其特征在于，",
            "3. 如权利要求2所述的硬件系统，其特征在于，",
            "所述处理器核还用于执行操作。 4 .根据权利要求1或2所述的硬件系统，其特征在于，",
            "根据权利要求4所述的硬件系统，其特征在于，",
            "根据权利要求5所述的硬件系统，其特征在于，",
            "7. 如权利要求6所述的硬件系统。",
        ]
        claim_flags = [False, False, False, False, True, True, False]
        section = DocxSection(
            header_text="",
            paragraphs=["权利要求书", *claim_paras],
            numpr_flags=[False, *claim_flags],
        )
        doc = extract_cn_sections_from_docx([section])
        ids = [c.id for c in doc.claims]
        assert ids == [1, 2, 3, 4, 5, 6, 7]
