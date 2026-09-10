# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""Tier-fire tests for the CN section-ID fallback chain.

Three tiers must each fire on targeted synthetic ``DocxSection`` inputs.
The assertion channel is
``CnPatentDocument.section_source_strategies["claims"]`` - the
walker-relevant strategy for Stage 2.

Stage 1.5 deleted the ``template_substyle`` tier, so this file
deliberately covers only three tiers: ``body_anchor``, ``claim_density``,
``page_header``. Adding a fourth case would regress the cleanup.
"""

from __future__ import annotations

from patentlint.parser.docx_loader import DocxSection
from patentlint.parser.sections_cn import extract_cn_sections_from_docx


def _section(header: str = "", paragraphs: list[str] | None = None,
             numpr: list[bool] | None = None) -> DocxSection:
    paragraphs = paragraphs or []
    numpr = numpr if numpr is not None else [False] * len(paragraphs)
    return DocxSection(header_text=header, paragraphs=paragraphs, numpr_flags=numpr)


class TestBodyAnchorTierFires:
    """Paragraphs carry standalone 五书 anchors (权利要求书, spec sub-sec
    headers) - Tier 1 must fire. Real CNIPA downloads take this path."""

    def test_body_anchor_fires_on_standalone_markers(self):
        sections = [
            _section(paragraphs=[
                "技术领域",
                "本发明涉及一种测试装置。",
                "权利要求书",
                "1. 一种装置，其特征在于，包括组件。",
                "2. 如权利要求1所述的装置，其特征在于，组件为金属。",
                "3. 如权利要求1所述的装置，其特征在于，组件为塑料。",
            ]),
        ]
        doc = extract_cn_sections_from_docx(sections)
        assert doc.section_source_strategies["claims"] == "body_anchor"
        assert doc.section_source_strategies["specification"] == "body_anchor"
        assert len(doc.claims) == 3


class TestClaimDensityTierFires:
    """No anchors at all - just a run of numbered claim paragraphs.
    Tier 2 must recover the claims span from pure density."""

    def test_claim_density_fires_on_anchor_stripped_input(self):
        sections = [
            _section(paragraphs=[
                "1. 一种装置，其特征在于，包括组件。",
                "2. 如权利要求1所述的装置，其特征在于，组件为金属。",
                "3. 如权利要求1所述的装置，其特征在于，组件为塑料。",
                "4. 如权利要求1所述的装置，其特征在于，组件为玻璃。",
            ]),
        ]
        doc = extract_cn_sections_from_docx(sections)
        assert doc.section_source_strategies["claims"] == "claim_density"
        assert len(doc.claims) == 4


class TestPageHeaderTierFires:
    """Word page-header text carries the 五书 title but body paragraphs
    contain no standalone anchors (五书模板 Word export pattern).
    Tier 3 must fall back to header-based mapping."""

    def test_page_header_fires_on_template_docx_pattern(self):
        sections = [
            _section(header="权利要求书", paragraphs=[
                "1. 一种装置，其特征在于，包括组件。",
                "2. 如权利要求1所述的装置，其特征在于，组件为金属。",
                "3. 如权利要求1所述的装置，其特征在于，组件为塑料。",
            ]),
            _section(header="说明书", paragraphs=[
                "本发明涉及一种测试装置。",
                "本发明的目的在于提供一种改进的装置。",
            ]),
        ]
        doc = extract_cn_sections_from_docx(sections)
        assert doc.section_source_strategies["claims"] == "page_header"
        assert doc.section_source_strategies["specification"] == "page_header"
        assert len(doc.claims) == 3


class TestLetterSpacedPageHeaders:
    """A drafter who letter-spaces the part titles by typing separators
    must still take the page-header tier.

    CNIPA templates justify the short part titles across the header line.
    Done with 分散对齐 the underlying text is unspaced and always parsed;
    typed by hand it arrives as separated characters, which matched none of
    the part patterns. The document then fell through to the
    publication-recovery tiers - claims via ``claim_density``, abstract via
    nothing - and ``requiredSections`` told the drafter that two parts their
    document plainly contains were missing.
    """

    def test_ascii_spaced_titles_take_the_page_header_tier(self):
        sections = [
            _section(header="摘  要", paragraphs=[
                "本发明公开一种第一装置，包括第一部件与第二部件。",
            ]),
            _section(header="权 利 要 求 书", paragraphs=[
                "1. 一种第一装置，其特征在于，包括第一部件。",
                "2. 如权利要求1所述的第一装置，其特征在于，还包括第二部件。",
                "3. 如权利要求1所述的第一装置，其特征在于，所述第一部件为金属。",
            ]),
            _section(header="说 明 书", paragraphs=[
                "本发明涉及一种第一装置。",
                "本发明的目的在于提供一种改进的第一装置。",
            ]),
        ]
        doc = extract_cn_sections_from_docx(sections)
        assert doc.section_source_strategies["claims"] == "page_header"
        assert doc.section_source_strategies["specification"] == "page_header"
        assert doc.section_source_strategies["abstract"] == "page_header"
        assert len(doc.claims) == 3
        assert doc.abstract_text.strip()

    def test_ideographic_spaced_titles_take_the_page_header_tier(self):
        """U+3000 is what a CJK IME produces, so it is the likelier form."""
        sections = [
            _section(header="\u3000摘\u3000要\u3000", paragraphs=[
                "本发明公开一种第二装置。",
            ]),
            _section(header="权\u3000利\u3000要\u3000求\u3000书", paragraphs=[
                "1. 一种第二装置，其特征在于，包括第三部件。",
                "2. 如权利要求1所述的第二装置，其特征在于，还包括第四部件。",
                "3. 如权利要求1所述的第二装置，其特征在于，所述第三部件为塑料。",
            ]),
        ]
        doc = extract_cn_sections_from_docx(sections)
        assert doc.section_source_strategies["claims"] == "page_header"
        assert doc.section_source_strategies["abstract"] == "page_header"
        assert len(doc.claims) == 3

    def test_spaced_abstract_drawing_still_beats_bare_abstract(self):
        """Removing the separators makes 摘要附图 contiguous, so the more
        specific part wins - the correct answer, and the one case where
        stripping changes an existing verdict."""
        from patentlint.parser.sections_cn import _identify_section

        assert _identify_section("摘要 附图") == "abstract_drawing"
        assert _identify_section("摘 要") == "abstract"


class TestNoTierFires:
    """No claims anywhere - all strategies remain ``none``."""

    def test_empty_sections(self):
        doc = extract_cn_sections_from_docx([_section(paragraphs=[])])
        assert doc.section_source_strategies["claims"] == "none"
        assert doc.section_source_strategies["specification"] == "none"
        assert doc.section_source_strategies["abstract"] == "none"
        assert doc.claims == []
