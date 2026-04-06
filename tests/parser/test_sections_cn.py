# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for CN patent .docx section extraction."""

from __future__ import annotations

from patentlint.parser.docx_loader import DocxSection
from patentlint.parser.sections_cn import (
    _detect_paragraph_numbering,
    _extract_title,
    _identify_section,
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
        result = _split_spec_subsections(paragraphs)
        assert result["technical_field"] == ["技术段落"]
        assert result["background"] == ["背景段落"]
        assert result["summary"] == ["发明段落"]
        assert result["drawings_description"] == ["附图段落"]
        assert result["detailed_description"] == ["实施段落"]

    def test_split_missing_section(self):
        paragraphs = [
            "技术领域",
            "技术段落",
            "发明内容",
            "发明段落",
        ]
        result = _split_spec_subsections(paragraphs)
        assert result["technical_field"] == ["技术段落"]
        assert result["background"] == []
        assert result["summary"] == ["发明段落"]

    def test_split_paragraphs_before_first_header(self):
        paragraphs = [
            "这是标题",
            "这也不属于任何节",
            "技术领域",
            "技术段落",
        ]
        result = _split_spec_subsections(paragraphs)
        assert result["technical_field"] == ["技术段落"]
        # Paragraphs before first header should not appear in any sub-section
        for paras in result.values():
            assert "这是标题" not in paras
            assert "这也不属于任何节" not in paras

    def test_split_fullwidth_spaces(self):
        paragraphs = ["\u3000技术领域\u3000", "段落"]
        result = _split_spec_subsections(paragraphs)
        assert result["technical_field"] == ["段落"]


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
            "1．一种装置。",
            "2．如权利要求1所述。",
            "3．如权利要求2所述。",
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
