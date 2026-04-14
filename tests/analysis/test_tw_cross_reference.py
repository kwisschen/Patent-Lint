# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for TW cross-reference and drawings checks (#31-33)."""

from __future__ import annotations

from patentlint.analysis.tw_cross_reference import (
    check_bracket_format,
    check_figure_count,
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
    """Check #32: Section header bracket format."""

    def test_always_pass_for_now(self):
        """Until raw header data is available, always PASS."""
        doc = TwPatentDocument()
        result = check_bracket_format(doc)
        assert result[0].status == "pass"
        assert result[0].message_key == "check.tw.crossRef.bracketFormat.pass"

    def test_reference(self):
        doc = TwPatentDocument()
        result = check_bracket_format(doc)
        assert result[0].reference == "專利法施行細則 §17"


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
