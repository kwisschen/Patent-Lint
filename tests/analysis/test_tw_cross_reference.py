# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for TW cross-reference and drawings checks (#31-33)."""

from __future__ import annotations

from patentlint.analysis.tw_cross_reference import (
    check_bracket_format,
    check_figure_count,
    check_figures_sequential,
    check_symbol_vs_rep_drawing,
)
from patentlint.models import SymbolEntry, TwPatentDocument


class TestCheckSymbolVsRepDrawing:
    """Check #31: Representative drawing symbols vs symbol table consistency."""

    def test_all_match_pass(self):
        doc = TwPatentDocument(
            representative_drawing_symbols=[
                SymbolEntry(numeral="10", name="框架"),
                SymbolEntry(numeral="20", name="底座"),
            ],
            symbol_table=[
                SymbolEntry(numeral="10", name="框架"),
                SymbolEntry(numeral="20", name="底座"),
                SymbolEntry(numeral="30", name="蓋板"),
            ],
        )
        result = check_symbol_vs_rep_drawing(doc)
        assert result[0].status == "pass"

    def test_numeral_not_in_symbol_table_verify(self):
        doc = TwPatentDocument(
            representative_drawing_symbols=[
                SymbolEntry(numeral="99", name="未知元件"),
            ],
            symbol_table=[
                SymbolEntry(numeral="10", name="框架"),
            ],
        )
        result = check_symbol_vs_rep_drawing(doc)
        assert result[0].status == "verify"
        mismatches = result[0].details_params["symbol_mismatch_triples"]["mismatches"]
        assert any(m["numeral"] == "99" for m in mismatches)

    def test_name_mismatch_verify(self):
        doc = TwPatentDocument(
            representative_drawing_symbols=[
                SymbolEntry(numeral="10", name="基座"),
            ],
            symbol_table=[
                SymbolEntry(numeral="10", name="框架"),
            ],
        )
        result = check_symbol_vs_rep_drawing(doc)
        assert result[0].status == "verify"
        mismatches = result[0].details_params["symbol_mismatch_triples"]["mismatches"]
        m = mismatches[0]
        assert m["rep_name"] == "基座"
        assert m["table_name"] == "框架"

    def test_empty_rep_drawing_symbols_suppressed(self):
        doc = TwPatentDocument(
            representative_drawing_symbols=[],
            symbol_table=[SymbolEntry(numeral="10", name="框架")],
        )
        result = check_symbol_vs_rep_drawing(doc)
        assert result == []

    def test_empty_symbol_table_verify(self):
        doc = TwPatentDocument(
            representative_drawing_symbols=[
                SymbolEntry(numeral="10", name="框架"),
            ],
            symbol_table=[],
        )
        result = check_symbol_vs_rep_drawing(doc)
        assert result[0].status == "verify"

    def test_multiple_mismatches(self):
        doc = TwPatentDocument(
            representative_drawing_symbols=[
                SymbolEntry(numeral="10", name="A"),
                SymbolEntry(numeral="20", name="B"),
                SymbolEntry(numeral="99", name="C"),
            ],
            symbol_table=[
                SymbolEntry(numeral="10", name="X"),
                SymbolEntry(numeral="20", name="B"),
            ],
        )
        result = check_symbol_vs_rep_drawing(doc)
        assert result[0].status == "verify"

    def test_reference(self):
        doc = TwPatentDocument(
            representative_drawing_symbols=[SymbolEntry(numeral="10", name="框架")],
            symbol_table=[SymbolEntry(numeral="10", name="框架")],
        )
        result = check_symbol_vs_rep_drawing(doc)
        assert result[0].reference == "專利審查基準"


class TestCheckBracketFormat:
    """Check #32: Section header bracket format — 專利法施行細則 §17."""

    def test_empty_list_passes(self):
        """No bracketless headers → PASS."""
        doc = TwPatentDocument(bracketless_section_headers=[])
        result = check_bracket_format(doc)
        assert result[0].status == "pass"
        assert result[0].message_key == "check.tw.crossRef.bracketFormat.pass"

    def test_bare_canonical_name_flagged(self):
        """Bare 先前技術 (no brackets) → VERIFY with header in details."""
        doc = TwPatentDocument(bracketless_section_headers=["先前技術"])
        result = check_bracket_format(doc)
        assert result[0].status == "verify"
        assert result[0].message_key == "check.tw.crossRef.bracketFormat.verify"
        assert result[0].details_params["headers"] == "先前技術"

    def test_variant_bracket_flagged(self):
        """[先前技術] → VERIFY; whole variant-bracketed string passes through."""
        doc = TwPatentDocument(bracketless_section_headers=["[先前技術]"])
        result = check_bracket_format(doc)
        assert result[0].status == "verify"
        assert result[0].details_params["headers"] == "[先前技術]"

    def test_multiple_headers_joined(self):
        doc = TwPatentDocument(
            bracketless_section_headers=["先前技術", "技術領域", "[實施方式]"]
        )
        result = check_bracket_format(doc)
        assert result[0].status == "verify"
        assert result[0].details_params["headers"] == "先前技術, 技術領域, [實施方式]"

    def test_truncation_at_ten(self):
        """Payload capped at 10 entries to avoid unbounded detail growth."""
        headers = [f"header{i}" for i in range(15)]
        doc = TwPatentDocument(bracketless_section_headers=headers)
        result = check_bracket_format(doc)
        rendered = result[0].details_params["headers"]
        assert rendered.count(",") == 9  # 10 entries = 9 separators

    def test_reference(self):
        doc = TwPatentDocument()
        result = check_bracket_format(doc)
        assert result[0].reference == "專利法施行細則 §17"

    def test_flagged_phrases_items_surfaced(self):
        """Malformed header tokens surface as FlaggedTermList chips so the
        user sees WHICH headers failed the 【】 bracket format — no
        hardcoded example list in the template."""
        doc = TwPatentDocument(
            bracketless_section_headers=["先前技術", "[實施方式]", "(發明內容)"]
        )
        result = check_bracket_format(doc)
        items = result[0].details_params.get("flagged_phrases", {}).get("items", [])
        tokens = [i["token"] for i in items]
        assert "先前技術" in tokens
        assert "[實施方式]" in tokens
        assert "(發明內容)" in tokens
        for item in items:
            assert item["kind"] == "header"


class TestCheckFigureCount:
    """Check #33 (Internal †): Figure count."""

    def test_figures_exist(self):
        doc = TwPatentDocument(figure_refs=["1", "2", "3"])
        result = check_figure_count(doc)
        assert result[0].status == "pass"
        assert result[0].details_params == {"count": "3"}

    def test_no_figures(self):
        doc = TwPatentDocument(figure_refs=[])
        result = check_figure_count(doc)
        assert result[0].status == "pass"
        assert result[0].details_params == {"count": "0"}

    def test_unique_ids_counted_directly(self):
        doc = TwPatentDocument(figure_refs=["1", "2"])
        result = check_figure_count(doc)
        assert result[0].details_params == {"count": "2"}

    def test_message_key(self):
        doc = TwPatentDocument(figure_refs=["1"])
        result = check_figure_count(doc)
        assert result[0].message_key == "check.tw.drawings.figureCount.pass"

    def test_reference(self):
        doc = TwPatentDocument(figure_refs=[])
        result = check_figure_count(doc)
        assert result[0].reference == "專利審查基準"


class TestCheckFiguresSequential:
    """Check #34: Figures sequential numbering."""

    def test_contiguous_passes(self):
        doc = TwPatentDocument(figure_refs=["1", "2", "3", "4"])
        result = check_figures_sequential(doc)
        assert result[0].status == "pass"
        assert result[0].details_params == {"found_max": "4"}

    def test_subfigure_suffixes_collapse(self):
        doc = TwPatentDocument(figure_refs=["1", "1A", "1B", "2", "2A"])
        result = check_figures_sequential(doc)
        assert result[0].status == "pass"

    def test_gap_amends(self):
        doc = TwPatentDocument(figure_refs=["1", "2", "4", "5"])
        result = check_figures_sequential(doc)
        assert result[0].status == "amend"
        assert result[0].details_params["figure_list"] == [3]
        assert result[0].details_params["found_max"] == "5"

    def test_missing_fig_one_amends(self):
        doc = TwPatentDocument(figure_refs=["2", "3"])
        result = check_figures_sequential(doc)
        assert result[0].status == "amend"
        assert result[0].details_params["figure_list"] == [1]

    def test_multiple_gaps(self):
        doc = TwPatentDocument(figure_refs=["1", "3", "5"])
        result = check_figures_sequential(doc)
        assert result[0].status == "amend"
        assert result[0].details_params["figure_list"] == [2, 4]

    def test_no_figures_passes(self):
        doc = TwPatentDocument(figure_refs=[])
        result = check_figures_sequential(doc)
        assert result[0].status == "pass"
        assert result[0].message_key == "check.tw.drawings.figuresSequential.passNone"

    def test_single_figure_passes(self):
        doc = TwPatentDocument(figure_refs=["1"])
        result = check_figures_sequential(doc)
        assert result[0].status == "pass"

    def test_reference(self):
        doc = TwPatentDocument(figure_refs=["1", "3"])
        result = check_figures_sequential(doc)
        assert result[0].reference == "專利審查基準"
