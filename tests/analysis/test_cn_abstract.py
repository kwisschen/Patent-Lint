# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.analysis.cn_abstract."""

from patentlint.analysis.cn_abstract import (
    check_abstract_char_count,
    check_abstract_title_match,
    check_commercial_language,
    check_figure_count,
    check_figures_sequential,
)
from patentlint.models import CnPatentDocument


def _cn_doc(**overrides) -> CnPatentDocument:
    defaults = {
        "title": "一种数据处理装置",
        "abstract_text": "本发明公开了一种数据处理装置，用于高效处理数据。",
        "abstract_char_count": 22,
        "figure_count": 3,
    }
    defaults.update(overrides)
    return CnPatentDocument(**defaults)


# ── Check 21: Abstract char count ─────────────────────────────────────────


class TestAbstractCharCount:
    def test_within_limit_pass(self):
        doc = _cn_doc(abstract_char_count=200)
        results = check_abstract_char_count(doc)
        assert results[0].status == "pass"
        assert results[0].details_params["count"] == "200"

    def test_over_limit_amend(self):
        doc = _cn_doc(abstract_char_count=350)
        results = check_abstract_char_count(doc)
        assert results[0].status == "amend"
        assert results[0].details_params["count"] == "350"

    def test_exactly_300_pass(self):
        doc = _cn_doc(abstract_char_count=300)
        results = check_abstract_char_count(doc)
        assert results[0].status == "pass"

    def test_zero_pass(self):
        doc = _cn_doc(abstract_char_count=0)
        results = check_abstract_char_count(doc)
        assert results[0].status == "pass"
        assert results[0].details_params["count"] == "0"


# ── Check 22: Abstract title match ────────────────────────────────────────


class TestAbstractTitleMatch:
    def test_title_in_abstract_pass(self):
        doc = _cn_doc(
            title="数据处理装置",
            abstract_text="本发明公开了一种数据处理装置，用于高效处理。",
        )
        results = check_abstract_title_match(doc)
        assert results[0].status == "pass"

    def test_title_not_in_abstract_verify(self):
        doc = _cn_doc(
            title="信号处理系统",
            abstract_text="本发明公开了一种数据处理装置。",
        )
        results = check_abstract_title_match(doc)
        assert results[0].status == "verify"

    def test_empty_abstract_verify(self):
        doc = _cn_doc(abstract_text="")
        results = check_abstract_title_match(doc)
        assert results[0].status == "verify"

    def test_empty_title_verify(self):
        doc = _cn_doc(title="", abstract_text="本发明公开了一种装置。")
        results = check_abstract_title_match(doc)
        assert results[0].status == "verify"

    def test_compound_title_ji_both_halves_pass_compound(self):
        doc = _cn_doc(
            title="盖组件及带盖容器",
            abstract_text="本发明公开了一种盖组件，适用于带盖容器的密封结构。",
        )
        results = check_abstract_title_match(doc)
        assert results[0].status == "pass"
        assert results[0].message_key == "check.cn.abstract.titleMatch.passCompound"
        assert results[0].details_params == {"halves": "盖组件、带盖容器"}

    def test_compound_title_he_both_halves_pass_compound(self):
        doc = _cn_doc(
            title="感测元件和控制电路",
            abstract_text="本发明公开了一种感测元件及与其耦接的控制电路。",
        )
        results = check_abstract_title_match(doc)
        assert results[0].status == "pass"
        assert results[0].message_key == "check.cn.abstract.titleMatch.passCompound"

    def test_compound_title_yu_both_halves_pass_compound(self):
        """CN uses simplified 与 (not Traditional 與)."""
        doc = _cn_doc(
            title="发光二极管与驱动电路",
            abstract_text="本发明公开了一种发光二极管及驱动电路。",
        )
        results = check_abstract_title_match(doc)
        assert results[0].status == "pass"
        assert results[0].message_key == "check.cn.abstract.titleMatch.passCompound"

    def test_compound_title_yiji_preferred_over_ji(self):
        doc = _cn_doc(
            title="存储模块以及存取装置",
            abstract_text="本发明公开了存储模块及存取装置。",
        )
        results = check_abstract_title_match(doc)
        assert results[0].status == "pass"
        assert results[0].details_params == {"halves": "存储模块、存取装置"}

    def test_compound_title_one_half_missing_verify(self):
        doc = _cn_doc(
            title="盖组件及带盖容器",
            abstract_text="本发明公开了一种盖组件。",
        )
        results = check_abstract_title_match(doc)
        assert results[0].status == "verify"

    def test_compound_title_single_char_half_verify(self):
        doc = _cn_doc(
            title="A及盖组件",
            abstract_text="本发明公开了A与盖组件。",
        )
        results = check_abstract_title_match(doc)
        assert results[0].status == "verify"


# ── Check 23: Commercial language ─────────────────────────────────────────


class TestCommercialLanguage:
    def test_no_commercial_pass(self):
        doc = _cn_doc(abstract_text="本发明公开了一种数据处理装置。")
        results = check_commercial_language(doc)
        assert results[0].status == "pass"

    def test_commercial_term_amend(self):
        doc = _cn_doc(abstract_text="本发明提供了最优的数据处理方案。")
        results = check_commercial_language(doc)
        assert results[0].status == "amend"
        assert "最优" in results[0].details_params["terms"]

    def test_multiple_terms_amend(self):
        doc = _cn_doc(abstract_text="本发明是国内首创的最佳方案，填补空白。")
        results = check_commercial_language(doc)
        assert results[0].status == "amend"
        terms = results[0].details_params["terms"]
        assert "最佳" in terms
        assert "国内首创" in terms
        assert "填补空白" in terms

    def test_empty_abstract_pass(self):
        doc = _cn_doc(abstract_text="")
        results = check_commercial_language(doc)
        assert results[0].status == "pass"


# ── Check 24: Figure count ────────────────────────────────────────────────


class TestFigureCount:
    def test_with_figures_pass(self):
        doc = _cn_doc(figure_count=5)
        results = check_figure_count(doc)
        assert results[0].status == "pass"
        assert results[0].details_params["count"] == "5"

    def test_zero_figures_pass(self):
        doc = _cn_doc(figure_count=0)
        results = check_figure_count(doc)
        assert results[0].status == "pass"
        assert results[0].details_params["count"] == "0"


# ── Check 25: Figures sequential ──────────────────────────────────────────


class TestFiguresSequential:
    def test_contiguous_passes(self):
        doc = _cn_doc(figure_refs=["图1", "图2", "图3"])
        results = check_figures_sequential(doc)
        assert results[0].status == "pass"
        assert results[0].details_params == {"found_max": "3"}

    def test_subfigure_suffixes_collapse(self):
        doc = _cn_doc(figure_refs=["图1", "图1a", "图1b", "图2", "图2A"])
        results = check_figures_sequential(doc)
        assert results[0].status == "pass"

    def test_fuzhu_prefix_accepted(self):
        # 附图 prefix occurs in some drafting styles
        doc = _cn_doc(figure_refs=["附图1", "附图2", "附图3"])
        results = check_figures_sequential(doc)
        assert results[0].status == "pass"

    def test_gap_amends(self):
        doc = _cn_doc(figure_refs=["图1", "图2", "图4"])
        results = check_figures_sequential(doc)
        assert results[0].status == "amend"
        assert results[0].details_params["figure_list"] == [3]
        assert results[0].details_params["found_max"] == "4"

    def test_missing_one_amends(self):
        doc = _cn_doc(figure_refs=["图2", "图3"])
        results = check_figures_sequential(doc)
        assert results[0].status == "amend"
        assert results[0].details_params["figure_list"] == [1]

    def test_no_figures_passes(self):
        doc = _cn_doc(figure_refs=[])
        results = check_figures_sequential(doc)
        assert results[0].status == "pass"
        assert results[0].message_key == "check.cn.drawings.figuresSequential.pass"

    def test_reference(self):
        doc = _cn_doc(figure_refs=["图1", "图3"])
        results = check_figures_sequential(doc)
        assert results[0].reference == "审查指南"
