"""Tests for patentlint.analysis.drawings."""

from patentlint.analysis.drawings import (
    get_figure_count,
    are_figures_sequential,
    is_single_figure,
    uses_wrong_label_for_single_figure,
    contains_prior_art_references,
    count_figure_range,
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
