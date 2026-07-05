# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Tests for patentlint.analysis.drawings."""

from patentlint.analysis.drawings import (
    get_figure_count,
    are_figures_sequential,
    compute_missing_figure_numbers,
    compute_suffix_violations,
    is_single_figure,
    uses_wrong_label_for_single_figure,
    contains_prior_art_references,
    contains_prior_art_references_cn,
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


class TestComputeSuffixViolations:
    """Issue #112: when a draft fires figuresSequential.amend because of
    sub-figure suffix ordering (FIG. 1A → FIG. 1C without 1B) instead of
    a parent-integer gap, missing_numbers is empty. This helper surfaces
    the suffix-side violations so the diagnostic payload can self-explain."""

    def test_no_violations_when_sequential(self):
        assert compute_suffix_violations(
            "FIG. 1A is a view.\nFIG. 1B is another view.\nFIG. 2 is overview."
        ) == []

    def test_no_violations_when_no_figures(self):
        assert compute_suffix_violations("No figures.") == []

    def test_gap_in_suffix(self):
        result = compute_suffix_violations(
            "FIG. 1A is a view.\nFIG. 1C is a third view."
        )
        assert result == [{
            "parent": 1, "kind": "gap",
            "after": "A", "expected": "B", "got": "C",
        }]

    def test_out_of_order_suffix(self):
        result = compute_suffix_violations(
            "FIG. 1B is a view.\nFIG. 1A is another view."
        )
        assert result == [{
            "parent": 1, "kind": "out_of_order",
            "after": "B", "got": "A",
        }]

    def test_missing_suffix_on_one_side(self):
        # The extractor synthesizes a space-suffix for bare FIG. N when
        # followed by another same-parent suffix-bearing ref. Verify the
        # helper flags the missing-letter side.
        result = compute_suffix_violations(
            "FIG. 1A is a view.\nFIG. 1 is the whole assembly."
        )
        assert len(result) == 1
        assert result[0]["parent"] == 1
        assert result[0]["kind"] == "missing_suffix"

    def test_multiple_violations_surfaced(self):
        result = compute_suffix_violations(
            "FIG. 1A is a view.\nFIG. 1D is another.\nFIG. 2A.\nFIG. 2C."
        )
        # Both parent=1 (A→D gap) and parent=2 (A→C gap) should fire.
        assert len(result) == 2
        kinds = {(v["parent"], v["kind"]) for v in result}
        assert (1, "gap") in kinds and (2, "gap") in kinds


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


class TestPriorArtCn:
    def test_xianyou_jishu_labeled(self):
        assert contains_prior_art_references_cn("图1示出现有技术的小部件。") is True

    def test_yizhi_jishu_labeled(self):
        assert contains_prior_art_references_cn("图1示出已知技术的系统。") is True

    def test_beijing_jishu_labeled(self):
        assert contains_prior_art_references_cn("图1为背景技术示意图。") is True

    def test_reverse_order(self):
        assert contains_prior_art_references_cn("现有技术如图1所示。") is True

    def test_clean_embodiment(self):
        assert contains_prior_art_references_cn("图1为本发明一实施例的装置示意图。") is False

    def test_boilerplate_preamble_not_flagged(self):
        # The common 附图说明 intro mentions 现有技术 conceptually but
        # doesn't label a specific figure. Must NOT fire (BOE fixture bug).
        boilerplate = (
            "为了更清楚地说明本发明实施例或现有技术中的技术方案，"
            "下面将对实施例或现有技术描述中所需要使用的附图作简单地介绍"
        )
        assert contains_prior_art_references_cn(boilerplate) is False

    def test_no_figure_reference_not_flagged(self):
        assert contains_prior_art_references_cn("本发明克服了现有技术的缺点。") is False


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

    def test_bare_parent_covered_by_lettered_subfigures(self):
        # Report #345: both sections describe FIG. 7A/7B/7C + 8A/8B/8C; the
        # detailed description ALSO uses a collective bare "FIG. 7" / "FIG. 8".
        # The bare parent must not be flagged as orphaned when its lettered
        # subfigures are described on the other side (37 CFR 1.84(u)(2)).
        brief = (
            "FIG. 7A shows.\nFIG. 7B shows.\nFIG. 7C shows.\n"
            "FIG. 8A shows.\nFIG. 8B shows.\nFIG. 8C shows."
        )
        detailed = (
            "FIG. 7A. FIG. 7B. FIG. 7C. FIG. 8A. FIG. 8B. FIG. 8C. "
            "Collectively, FIG. 7 and FIG. 8 illustrate the assembly."
        )
        results = check_figure_cross_references(brief, detailed)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_lettered_subfigure_covered_by_bare_parent(self):
        # Reverse direction: brief uses lettered 3A/3B, detailed uses bare FIG. 3.
        brief = "FIG. 3A shows X.\nFIG. 3B shows Y."
        detailed = "As shown in FIG. 3, the assembly operates."
        results = check_figure_cross_references(brief, detailed)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_sibling_subfigure_only_still_flags(self):
        # FN-guard: subfigure-vs-subfigure mismatch with NO bare parent bridge
        # is a genuine inconsistency and must still surface.
        brief = "FIG. 4A shows X."
        detailed = "As shown in FIG. 4B, the widget."
        results = check_figure_cross_references(brief, detailed)
        keys = {r.message_key for r in results}
        assert "checks.figure_xref_orphaned_brief" in keys
        assert "checks.figure_xref_orphaned_detailed" in keys
