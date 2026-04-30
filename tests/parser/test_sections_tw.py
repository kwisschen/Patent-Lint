# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for TW section extraction from bracket-header .docx files."""

from __future__ import annotations

from pathlib import Path

import pytest

from patentlint.models import TwPatentType
from patentlint.parser.docx_loader import load_docx
from patentlint.parser.sections_tw import (
    _count_cjk_chars,
    _find_bracketless_section_headers,
    detect_patent_document_tw,
    extract_tw_sections,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tw"


def _load_fixture(name: str):
    """Load a .docx fixture and return TwPatentDocument."""
    loaded = load_docx(str(FIXTURES / name))
    paragraphs = [line for line in loaded.full_text.split("\n") if line.strip()]
    return extract_tw_sections(paragraphs)


class TestInventionComplete:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.doc = _load_fixture("invention_complete.docx")

    def test_patent_type(self):
        assert self.doc.patent_type == TwPatentType.INVENTION

    def test_title(self):
        assert self.doc.title == "半導體封裝結構及其製造方法"

    def test_technical_field(self):
        assert len(self.doc.technical_field) == 2
        assert "半導體封裝" in self.doc.technical_field[0]

    def test_prior_art(self):
        assert len(self.doc.prior_art) == 2

    def test_disclosure(self):
        assert len(self.doc.disclosure) == 2

    def test_drawings_description(self):
        assert len(self.doc.drawings_description) == 3

    def test_embodiment(self):
        assert len(self.doc.embodiment) == 3

    def test_symbol_table(self):
        assert len(self.doc.symbol_table) == 4
        numerals = [e.numeral for e in self.doc.symbol_table]
        assert "10" in numerals
        assert "100" in numerals

    def test_claims_count(self):
        assert len(self.doc.claims) == 6

    def test_independent_claims(self):
        indep = [c for c in self.doc.claims if c.independent]
        assert len(indep) == 2
        assert indep[0].id == 1
        assert indep[1].id == 5

    def test_dependent_claims(self):
        dep = [c for c in self.doc.claims if not c.independent]
        assert len(dep) == 4

    def test_abstract(self):
        assert "半導體封裝結構" in self.doc.abstract_text
        assert self.doc.abstract_char_count > 0

    def test_representative_drawing(self):
        assert self.doc.representative_drawing == "圖1"

    def test_representative_drawing_symbols(self):
        assert len(self.doc.representative_drawing_symbols) == 2
        assert self.doc.representative_drawing_symbols[0].numeral == "10"

    def test_figure_refs(self):
        # 圖1, 圖2, 圖3 from drawings desc + 圖1, 圖2 from embodiment
        # Now returns unique normalized IDs in first-appearance order
        assert set(self.doc.figure_refs) == {"1", "2", "3"}
        assert len(self.doc.figure_refs) == 3

    def test_paragraph_numbering(self):
        assert self.doc.has_paragraph_numbering is True
        assert len(self.doc.paragraph_numbers) == 12
        assert self.doc.paragraph_numbers[0] == "0001"
        assert self.doc.paragraph_numbers[-1] == "0012"


class TestUtilityModel:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.doc = _load_fixture("utility_model_complete.docx")

    def test_patent_type(self):
        assert self.doc.patent_type == TwPatentType.UTILITY_MODEL

    def test_title(self):
        assert self.doc.title == "散熱裝置"

    def test_disclosure_populated(self):
        """新型內容 maps to disclosure field."""
        assert len(self.doc.disclosure) >= 1

    def test_claims(self):
        assert len(self.doc.claims) == 2


class TestMissingSections:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.doc = _load_fixture("missing_sections.docx")

    def test_no_drawings_description(self):
        assert len(self.doc.drawings_description) == 0

    def test_no_symbol_table(self):
        assert len(self.doc.symbol_table) == 0

    def test_no_paragraph_numbering(self):
        assert self.doc.has_paragraph_numbering is False
        assert len(self.doc.paragraph_numbers) == 0

    def test_other_sections_populated(self):
        assert len(self.doc.technical_field) >= 1
        assert len(self.doc.prior_art) >= 1
        assert len(self.doc.disclosure) >= 1
        assert len(self.doc.embodiment) >= 1

    def test_representative_drawing_none(self):
        assert self.doc.representative_drawing is None


class TestCountCjkChars:
    def test_pure_cjk(self):
        assert _count_cjk_chars("本發明") == 3

    def test_mixed_with_punctuation(self):
        # Punctuation should not be counted
        assert _count_cjk_chars("本發明。") == 3

    def test_mixed_with_spaces(self):
        assert _count_cjk_chars("本 發 明") == 3

    def test_empty(self):
        assert _count_cjk_chars("") == 0

    def test_with_numbers(self):
        # ASCII digits are not CJK — only 元件 counted
        assert _count_cjk_chars("元件10") == 2


class TestExtractTwSectionsFromRawParagraphs:
    def test_empty_input(self):
        doc = extract_tw_sections([])
        assert doc.title == ""
        assert len(doc.claims) == 0

    def test_minimal_invention(self):
        doc = extract_tw_sections([
            "【發明名稱】",
            "測試裝置",
            "【申請專利範圍】",
            "1. 一種測試裝置。",
            "【摘要】",
            "本發明提供測試裝置。",
        ])
        assert doc.title == "測試裝置"
        assert len(doc.claims) == 1
        assert doc.patent_type == TwPatentType.INVENTION

    def test_utility_model_detection(self):
        doc = extract_tw_sections([
            "【新型名稱】",
            "散熱器",
        ])
        assert doc.patent_type == TwPatentType.UTILITY_MODEL

    def test_utility_model_content_header(self):
        """新型內容 also triggers utility model detection."""
        doc = extract_tw_sections([
            "【發明名稱】",
            "某裝置",
            "【新型內容】",
            "本新型提供某裝置。",
        ])
        assert doc.patent_type == TwPatentType.UTILITY_MODEL


class TestFindBracketlessSectionHeaders:
    """_find_bracketless_section_headers: detect canonical TIPO section
    names that appear without the required 【】 brackets."""

    def test_bracketed_name_not_flagged(self):
        """【先前技術】 is correctly bracketed → not flagged."""
        assert _find_bracketless_section_headers(["【先前技術】"]) == []

    def test_bare_section_name_flagged(self):
        """先前技術 alone on a line → flagged (user's reported case)."""
        assert _find_bracketless_section_headers(["先前技術"]) == ["先前技術"]

    def test_square_bracket_variant_flagged(self):
        assert _find_bracketless_section_headers(["[先前技術]"]) == ["[先前技術]"]

    def test_fullwidth_paren_variant_flagged(self):
        assert _find_bracketless_section_headers(["（先前技術）"]) == ["（先前技術）"]

    def test_halfwidth_paren_variant_flagged(self):
        assert _find_bracketless_section_headers(["(先前技術)"]) == ["(先前技術)"]

    def test_tortoise_bracket_variant_flagged(self):
        assert _find_bracketless_section_headers(["〔先前技術〕"]) == ["〔先前技術〕"]

    def test_missing_closing_bracket_flagged(self):
        """【先前技術 (opening only) → flagged."""
        assert _find_bracketless_section_headers(["【先前技術"]) == ["【先前技術"]

    def test_missing_opening_bracket_flagged(self):
        """先前技術】 (closing only) → flagged."""
        assert _find_bracketless_section_headers(["先前技術】"]) == ["先前技術】"]

    def test_correctly_bracketed_not_flagged(self):
        """【先前技術】 (well-formed) → not flagged."""
        assert _find_bracketless_section_headers(["【先前技術】"]) == []

    def test_correctly_bracketed_with_inline_not_flagged(self):
        """【先前技術】 本發明... (inline content after) → not flagged."""
        assert _find_bracketless_section_headers(
            ["【先前技術】 本發明涉及測試。"]
        ) == []

    def test_multiple_canonical_names_flagged_in_order(self):
        paragraphs = [
            "【技術領域】",
            "正常內容。",
            "先前技術",
            "更多內容。",
            "[發明內容]",
            "實施方式",
        ]
        result = _find_bracketless_section_headers(paragraphs)
        assert result == ["先前技術", "[發明內容]", "實施方式"]

    def test_non_canonical_bare_text_not_flagged(self):
        """A random bare line that isn't a canonical section name passes."""
        assert _find_bracketless_section_headers(["某段內容"]) == []

    def test_dedup_preserves_first_seen_order(self):
        paragraphs = ["先前技術", "技術領域", "先前技術"]
        assert _find_bracketless_section_headers(paragraphs) == ["先前技術", "技術領域"]

    def test_inline_usage_not_flagged(self):
        """A paragraph mentioning 先前技術 inline is not a header line."""
        assert _find_bracketless_section_headers(
            ["本發明涉及先前技術的改良。"]
        ) == []

    def test_populated_on_document(self):
        """extract_tw_sections sets bracketless_section_headers on the doc."""
        doc = extract_tw_sections([
            "【發明名稱】",
            "測試裝置",
            "【技術領域】",
            "本發明涉及測試。",
            "先前技術",  # ← missing brackets
            "已知先前技術。",
        ])
        assert doc.bracketless_section_headers == ["先前技術"]


class TestDetectPatentDocumentTw:
    def test_true_with_bracket_header(self):
        assert detect_patent_document_tw(["【技術領域】", "本發明涉及測試。"]) is True

    def test_true_with_claims_keyword(self):
        assert detect_patent_document_tw(["如請求項1所述之裝置。"]) is True

    def test_true_with_paragraph_numbers(self):
        paragraphs = [
            "【0001】第一段。",
            "【0002】第二段。",
            "【0003】第三段。",
        ]
        assert detect_patent_document_tw(paragraphs) is True

    def test_false_generic_document(self):
        paragraphs = [
            "會議紀錄",
            "日期：2025年3月1日",
            "出席人員：王先生、陳小姐",
            "討論事項：專案進度。",
        ]
        assert detect_patent_document_tw(paragraphs) is False

    def test_or_logic_single_signal(self):
        # Only bracket header, no claims or para numbers
        assert detect_patent_document_tw(["【先前技術】", "先前技術段落。"]) is True

    def test_fewer_than_three_para_nums_not_enough(self):
        paragraphs = ["【0001】第一段。", "【0002】第二段。"]
        assert detect_patent_document_tw(paragraphs) is False

    def test_phase_9_73_rejects_us_patent(self):
        """US English patent must not false-positive TW detector (Phase 9 #73)."""
        paragraphs = [
            "CLAIMS",
            "1. A method comprising step A.",
            "2. The method of claim 1, further comprising step B.",
            "3. The method of claim 1, wherein step A includes sub-step C.",
        ]
        assert detect_patent_document_tw(paragraphs) is False

    def test_phase_9_73_rejects_cn_patent(self):
        """CN simplified-Chinese publication must not false-positive TW detector (Phase 9 #73).

        CN uses 权利要求 (simplified 权) not 請求項 (traditional 請); uses [0001]
        ASCII brackets not 【0001】 fullwidth; uses body-anchor markers like
        权利要求书 plain-text, not 【】 headers.
        """
        paragraphs = [
            "用于调整神经网络的方法和装置",
            "[0001] 本申请涉及通信技术领域。",
            "[0002] 具体地，本申请涉及一种神经网络装置。",
            "[0003] 神经网络在无线通信中应用广泛。",
            "权利要求书",
            "1. 一种用于调整神经网络的方法。",
        ]
        assert detect_patent_document_tw(paragraphs) is False

    def test_phase_9_74_rejects_jp_patent(self):
        """JPO patent must not false-positive TW detector (Phase 9 #74).

        JPO shares the 【】 fullwidth bracket convention with TIPO but
        uses hiragana/katakana which TW patents never contain.
        """
        paragraphs = [
            "【特許請求の範囲】",
            "【請求項1】",
            "信号処理方法であって、第1の信号を受信するステップを含む方法。",
            "【発明の詳細な説明】",
            "本発明は信号処理に関するものである。",
        ]
        assert detect_patent_document_tw(paragraphs) is False

    def test_phase_9_74_rejects_ko_patent(self):
        """KIPO patent must not false-positive TW detector (Phase 9 #74).

        KIPO also uses 【】 brackets in some formats but writes in
        Hangul which TW patents never contain.
        """
        paragraphs = [
            "【청구항 1】",
            "장치에 있어서,",
            "처리기와,",
            "상기 처리기에 연결된 저장 매체를 포함하는 장치.",
            "【발명의 상세한 설명】",
            "본 발명은 신호 처리에 관한 것이다.",
        ]
        assert detect_patent_document_tw(paragraphs) is False

    def test_adr_150_accepts_tw_with_stray_middle_dot(self):
        """ADR-150 regression: a TW draft carrying a single script=Common
        middle dot (U+30FB) in 保溫・保冷-style typography must not be
        rejected as JP. Pre-fix, a single dot dropped likely_patent to
        False and triggered the non-patent banner on a clearly-TW file."""
        from patentlint.parser.sections_tw import classify_document_tw
        from patentlint.parser.detection import DetectionReason
        paragraphs = [
            "【發明摘要】",
            "【中文發明名稱】蓋組件及帶蓋容器",
            "【發明說明】",
            "1. 如請求項1所記載的蓋組件，具備保溫・保冷機能。",
            "【技術領域】",
            "本發明關於一種蓋組件及帶蓋容器。",
        ]
        is_patent, reason = classify_document_tw(paragraphs)
        assert is_patent is True
        assert reason == DetectionReason.PATENT_DETECTED

    def test_adr_150_reports_jp_reason_on_real_jp(self):
        """ADR-150: when a JP patent is uploaded to TW, the reason code
        should be CROSS_SCRIPT_JAPANESE so the banner copy can explain
        what was actually detected."""
        from patentlint.parser.sections_tw import classify_document_tw
        from patentlint.parser.detection import DetectionReason
        paragraphs = [
            "【特許請求の範囲】",
            "【請求項1】",
            "信号処理方法であって、第1の信号を受信するステップを含む方法。",
            "【発明の詳細な説明】",
            "本発明は信号処理に関するものである。",
        ]
        is_patent, reason = classify_document_tw(paragraphs)
        assert is_patent is False
        assert reason == DetectionReason.CROSS_SCRIPT_JAPANESE

    def test_adr_150_reports_ko_reason_on_real_ko(self):
        from patentlint.parser.sections_tw import classify_document_tw
        from patentlint.parser.detection import DetectionReason
        paragraphs = [
            "【청구항 1】",
            "장치에 있어서,",
            "본 발명은 신호 처리에 관한 것이다.",
        ]
        is_patent, reason = classify_document_tw(paragraphs)
        assert is_patent is False
        assert reason == DetectionReason.CROSS_SCRIPT_KOREAN

    def test_adr_150_content_missing_on_blank_doc(self):
        from patentlint.parser.sections_tw import classify_document_tw
        from patentlint.parser.detection import DetectionReason
        is_patent, reason = classify_document_tw(["Hello world.", "Nothing here."])
        assert is_patent is False
        assert reason == DetectionReason.CONTENT_MISSING


# NOTE: This test loads a real patent docx that is gitignored under
# tests/fixtures/tw/. The fixture is NEVER committed. Test skips cleanly
# when the fixture is absent (e.g. in CI). Primary regression coverage
# for the 110P000368 bug lives in the synthetic test in
# tests/analysis/test_tw_specification.py::TestFigureRefConsistency110P000368Regression
# which runs without any external fixture.
class TestFigureRefs110P000368Regression:
    """Real-world regression: 110P000368 docx has 10 figures, not 16.

    The old singleton regex extracted 100, 504, 510, 511, 701, 801 from
    compound nouns (地圖100, 縮圖511, etc.) in the 實施方式 section,
    inflating the figure count to 16. The shared TW_PARSER with
    blocklist guards correctly ignores these.
    """

    def test_figure_refs_110P000368_regression(self):
        from patentlint.parser.docx_loader import load_docx_tw

        fixture_path = FIXTURES / "110P000368US-JP,KR案派譯版-FV.DOCX"
        if not fixture_path.exists():
            pytest.skip(f"Fixture not found: {fixture_path}")

        loaded = load_docx_tw(str(fixture_path))
        paragraphs = [line for line in loaded.paragraphs if line.strip()]
        doc = extract_tw_sections(paragraphs)

        expected = {str(i) for i in range(1, 11)}
        false_positives = {"100", "504", "510", "511", "701", "801"}

        assert set(doc.figure_refs) == expected, (
            f"Expected {expected}, got {set(doc.figure_refs)}"
        )
        assert set(doc.figure_refs) & false_positives == set(), (
            f"False positives found: {set(doc.figure_refs) & false_positives}"
        )
        assert len(doc.figure_refs) == 10


class TestClaimBracketLabels:
    """Regression for issue #17: TIPO firm-variant claim labeling with
    【請求項N】 inline bracket headers.

    Without explicit support, the bracket-header regex in
    ``extract_tw_sections`` matches 【請求項N】 as an unknown section
    header, resets ``current_section`` to None, and drops claim text.
    Result: ``claims_header_seen=True`` but ``doc.claims=[]``, which
    trips the requiredSections.amend check with a misleading "missing
    申請專利範圍" message even though the section IS present.

    The fix recognizes 【請求項N】 while inside the claims section and
    transforms it to standard "N. <body>" form so parse_tw_claims
    handles it identically to the standard inline-numbered format.

    TIPO 專利法施行細則 §18 第3款 only requires Arabic-numeral sequential
    numbering — 【請求項N】 satisfies that, so the parser must accept it.
    """

    def test_claim_bracket_labels_with_inline_body(self):
        paragraphs = [
            "【中文發明名稱】範例發明",
            "【發明說明書】",
            "【技術領域】",
            "本發明係關於一種半導體裝置。",
            "【先前技術】",
            "現有技術中存在某種問題。",
            "【發明內容】",
            "本發明之目的在於解決上述問題。",
            "【實施方式】",
            "茲就本發明之實施方式說明如下。",
            "【申請專利範圍】",
            "【請求項1】 一種半導體裝置，包括A、B、C。",
            "【請求項2】 如請求項1所述之半導體裝置，其中A為矽。",
            "【請求項3】 如請求項1所述之半導體裝置，其中B為金屬。",
        ]
        doc = extract_tw_sections(paragraphs)
        assert doc.claims_header_seen is True
        assert len(doc.claims) == 3
        assert doc.claims[0].id == 1
        assert doc.claims[0].independent is True
        assert doc.claims[1].id == 2
        assert doc.claims[1].dependencies == [1]
        assert doc.claims[2].id == 3
        assert doc.claims[2].dependencies == [1]

    def test_claim_bracket_labels_with_continuation_paragraphs(self):
        """Continuation paragraphs (claim body wrapping across multiple
        paragraphs without a leading bracket label) accumulate into the
        preceding claim's text under the same claims section."""
        paragraphs = [
            "【申請專利範圍】",
            "【請求項1】 一種半導體裝置，包括A、B、C。",
            "前述A為一種特殊材料，",
            "前述B覆蓋於A之上。",
            "【請求項2】 如請求項1所述之半導體裝置，其中A為矽。",
        ]
        doc = extract_tw_sections(paragraphs)
        assert doc.claims_header_seen is True
        assert len(doc.claims) == 2
        assert "前述A為一種特殊材料" in doc.claims[0].text
        assert "前述B覆蓋於A之上" in doc.claims[0].text

    def test_claim_bracket_label_without_inline_body(self):
        """Drafter places 【請求項N】 on its own line, claim body on the
        next paragraph. Should still parse correctly."""
        paragraphs = [
            "【申請專利範圍】",
            "【請求項1】",
            "一種半導體裝置，包括A、B、C。",
            "【請求項2】",
            "如請求項1所述之半導體裝置，其中A為矽。",
        ]
        doc = extract_tw_sections(paragraphs)
        assert doc.claims_header_seen is True
        assert len(doc.claims) == 2
        assert doc.claims[0].id == 1
        assert doc.claims[1].id == 2
        assert doc.claims[1].dependencies == [1]

    def test_standard_inline_format_still_works(self):
        """Anti-corpus check: drafts using the standard `1.` / `1．`
        inline numbering (the path that's been working) must not
        regress."""
        paragraphs = [
            "【申請專利範圍】",
            "1. 一種半導體裝置，包括A、B、C。",
            "2. 如請求項1所述之半導體裝置，其中A為矽。",
        ]
        doc = extract_tw_sections(paragraphs)
        assert doc.claims_header_seen is True
        assert len(doc.claims) == 2
        assert doc.claims[1].dependencies == [1]
