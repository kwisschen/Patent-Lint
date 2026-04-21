# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.analysis.drawings."""

from patentlint.analysis.drawings import (
    get_figure_count,
    are_figures_sequential,
    compute_missing_figure_numbers,
    is_single_figure,
    uses_wrong_label_for_single_figure,
    contains_prior_art_references,
    count_figure_range,
    check_figure_cross_references,
)


class TestFigureCount:
    def test_simple(self):
        assert get_figure_count("FIG. 1 shows a widget.\nFIG. 2 shows a gadget.\nFIG. 3 shows a thing.") == 3

    def test_range(self):
        assert get_figure_count("FIGS. 1 to 3 show various views.") == 3

    def test_alpha_suffix(self):
        assert get_figure_count("FIGS. 2(a) to 2(c) show different angles.") == 3

    def test_none(self):
        assert get_figure_count("No figures here.") == 0

    def test_spelled_out(self):
        assert get_figure_count("Figure 1 shows a widget.\nFigure 2 shows a gadget.") == 2


class TestFiguresSequential:
    def test_sequential(self):
        assert are_figures_sequential("FIG. 1 shows a widget.\nFIG. 2 shows a gadget.\nFIG. 3 shows a thing.") is True

    def test_gap(self):
        assert are_figures_sequential("FIG. 1 shows a widget.\nFIG. 3 shows a thing.") is False

    def test_alpha(self):
        assert are_figures_sequential("FIG. 1A is a front view.\nFIG. 1B is a side view.\nFIG. 2 is an overview.") is True

    def test_empty(self):
        assert are_figures_sequential("No figures.") is True


class TestComputeMissingFigureNumbers:
    def test_empty(self):
        assert compute_missing_figure_numbers("No figures.") == []

    def test_sequential(self):
        assert compute_missing_figure_numbers(
            "FIG. 1 shows a widget.\nFIG. 2 shows a gadget.\nFIG. 3 shows a thing."
        ) == []

    def test_single_gap(self):
        assert compute_missing_figure_numbers(
            "FIG. 1 shows a widget.\nFIG. 3 shows a thing."
        ) == [2]

    def test_multiple_gaps(self):
        assert compute_missing_figure_numbers(
            "FIG. 1 shows X.\nFIG. 3 shows Y.\nFIG. 5 shows Z."
        ) == [2, 4]

    def test_missing_first(self):
        assert compute_missing_figure_numbers("FIG. 2 shows X.") == [1]

    def test_subfigure_suffix_collapses_to_parent(self):
        assert compute_missing_figure_numbers(
            "FIG. 1A is a view.\nFIG. 1B is another view.\nFIG. 3 is a different one."
        ) == [2]


class TestSingleFigure:
    def test_true(self):
        assert is_single_figure("FIG. 1 shows the device.") is True

    def test_false(self):
        assert is_single_figure("FIG. 1 shows X.\nFIG. 2 shows Y.") is False

    def test_wrong_label(self):
        assert uses_wrong_label_for_single_figure("FIG. 1 shows the device.") is True


class TestPriorArt:
    def test_detected(self):
        assert contains_prior_art_references("FIG. 1 shows a prior art widget.") is True

    def test_conventional(self):
        assert contains_prior_art_references("FIG. 1 shows a conventional system.") is True

    def test_clean(self):
        assert contains_prior_art_references("FIG. 1 shows the device.") is False


class TestFigureRange:
    def test_numeric(self):
        assert count_figure_range("1", "5", "", "") == 5

    def test_alpha(self):
        assert count_figure_range("2", "2", "A", "D") == 4


class TestFigureCrossReferences:
    def test_all_consistent(self):
        brief = "FIG. 1 shows X.\nFIG. 2 shows Y.\nFIG. 3 shows Z.\nFIG. 4 shows W.\nFIG. 5 shows V."
        detailed = "As shown in FIG. 1, the widget. FIG. 2 illustrates. FIG. 3 depicts. FIG. 4 shows. FIG. 5 details."
        results = check_figure_cross_references(brief, detailed)
        assert len(results) == 1
        assert results[0].status == "pass"
        assert results[0].message_key == "checks.figure_xref_pass"

    def test_brief_has_extra(self):
        brief = "FIG. 1 shows X.\nFIG. 2 shows Y.\nFIG. 3 shows Z.\nFIG. 4 shows W.\nFIG. 5 shows V."
        detailed = "FIG. 1 shows X. FIG. 2 shows Y. FIG. 3 shows Z."
        results = check_figure_cross_references(brief, detailed)
        orphaned = [r for r in results if r.message_key == "checks.figure_xref_orphaned_brief"]
        assert len(orphaned) == 1
        assert "4" in orphaned[0].details
        assert "5" in orphaned[0].details

    def test_detailed_has_extra(self):
        brief = "FIG. 1 shows X.\nFIG. 2 shows Y.\nFIG. 3 shows Z.\nFIG. 4 shows W.\nFIG. 5 shows V."
        detailed = "FIG. 1 shows X. FIG. 2 shows Y. FIG. 3 shows Z. FIG. 4 shows W. FIG. 5 shows V. FIG. 6 shows U. FIG. 7 shows T. FIG. 8 shows S."
        results = check_figure_cross_references(brief, detailed)
        orphaned = [r for r in results if r.message_key == "checks.figure_xref_orphaned_detailed"]
        assert len(orphaned) == 1
        assert "6" in orphaned[0].details
        assert "7" in orphaned[0].details
        assert "8" in orphaned[0].details

    def test_both_directions_mismatch(self):
        brief = "FIG. 1 shows X.\nFIG. 2 shows Y."
        detailed = "FIG. 1 shows X. FIG. 3 shows Z."
        results = check_figure_cross_references(brief, detailed)
        assert len(results) == 2
        keys = {r.message_key for r in results}
        assert "checks.figure_xref_orphaned_brief" in keys
        assert "checks.figure_xref_orphaned_detailed" in keys

    def test_letter_suffixes(self):
        brief = "FIG. 2A shows X.\nFIG. 2B shows Y."
        detailed = "As shown in FIG. 2A and FIG. 2B."
        results = check_figure_cross_references(brief, detailed)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_range_notation(self):
        brief = "FIGS. 3-5 show various views."
        detailed = "FIG. 3 shows X. FIG. 4 shows Y. FIG. 5 shows Z."
        results = check_figure_cross_references(brief, detailed)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_and_notation(self):
        brief = "FIGS. 1 and 2 show the device."
        detailed = "FIG. 1 shows X. FIG. 2 shows Y."
        results = check_figure_cross_references(brief, detailed)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_both_empty(self):
        results = check_figure_cross_references("", "")
        assert results == []

    def test_one_empty_one_has_refs(self):
        brief = ""
        detailed = "FIG. 1 shows X. FIG. 2 shows Y."
        results = check_figure_cross_references(brief, detailed)
        orphaned = [r for r in results if r.message_key == "checks.figure_xref_orphaned_detailed"]
        assert len(orphaned) == 1
        assert "1" in orphaned[0].details
        assert "2" in orphaned[0].details

    def test_range_vs_individual_partial(self):
        brief = "FIGS. 5-7 show the cooling assembly."
        detailed = "As shown in FIG. 5, the housing includes... Referring to FIG. 6, the inlet valve..."
        results = check_figure_cross_references(brief, detailed)
        orphaned = [r for r in results if r.message_key == "checks.figure_xref_orphaned_brief"]
        assert len(orphaned) == 1
        assert "7" in orphaned[0].details
        assert "5" not in orphaned[0].details
        assert "6" not in orphaned[0].details
