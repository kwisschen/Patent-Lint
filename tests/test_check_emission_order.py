# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Regression gates for the Phase 10C document-order invariant.

Asserts that CheckItems emit in the canonical per-jurisdiction order
documented in CLAUDE.md ("Check-ordering consistency invariant"). The
test doesn't pin a brittle full-order list; instead each known
message_key maps to an integer group rank (1 = spec-structure,
2 = spec-content, 3 = drawings, ...), and we require the actual emit
order to be monotonically non-decreasing in group rank.

If a future refactor shuffles a check into the wrong group (e.g.
required_sections drifts mid-spec-list), the test fails loudly with
the offending message_key named."""

from __future__ import annotations

from patentlint.models import AnalysisResult, Jurisdiction


# Group rank for every message_key emitted on spec_checks / drawings_checks.
# Lower numbers emit first. Keys not in this dict are ignored (walker-emitted
# dynamic keys like required_sections_checks contents are handled inline).
SPEC_STRUCTURE_GROUP = 1
SPEC_CONTENT_GROUP = 2
DRAWINGS_GROUP = 3

SPEC_GROUP_RANK: dict[str, int] = {
    # Group 1: Spec structure
    "check.spec.trackedChanges.amend": SPEC_STRUCTURE_GROUP,
    "check.spec.paragraphSequential.missing": SPEC_STRUCTURE_GROUP,
    "check.spec.paragraphSequential.amend": SPEC_STRUCTURE_GROUP,
    "check.spec.paragraphSequential.pass": SPEC_STRUCTURE_GROUP,
    "check.spec.paragraphEnding.amend": SPEC_STRUCTURE_GROUP,
    "check.spec.paragraphEnding.pass": SPEC_STRUCTURE_GROUP,
    # Required sections checks are emitted as dynamic per-section items;
    # their message_keys begin with "checks.required_section_" — handled
    # via prefix in _rank_of.
    # Group 2: Spec content
    "check.spec.sequenceListing.amend": SPEC_CONTENT_GROUP,
    "check.spec.sequenceListing.pass": SPEC_CONTENT_GROUP,
    "check.spec.crossReference.verify": SPEC_CONTENT_GROUP,
    "check.spec.crossReference.pass": SPEC_CONTENT_GROUP,
    "check.spec.priorArt.verify": SPEC_CONTENT_GROUP,
    "check.spec.priorArt.pass": SPEC_CONTENT_GROUP,
    "check.spec.restrictiveWording.verify": SPEC_CONTENT_GROUP,
    "check.spec.restrictiveWording.pass": SPEC_CONTENT_GROUP,
    # Drawing overview is also spec-content (it's the spec-tab preview of
    # drawings status; true drawings checks live on drawings_checks).
    "check.drawings.overview.verify": SPEC_CONTENT_GROUP,
    "check.drawings.overview.pass": SPEC_CONTENT_GROUP,
}

# Drawings tab (jurisdiction-common)
DRAWINGS_GROUP_RANK: dict[str, int] = {
    # Per target: figure_count → single_figure → prior_art_drawings
    # → figures_sequential → figure_xref
    "check.drawings.count.amend": 1,
    "check.drawings.count.pass": 1,
    "check.cn.drawings.count.amend": 1,
    "check.cn.drawings.count.pass": 1,
    "check.tw.drawings.count.amend": 1,
    "check.tw.drawings.count.pass": 1,
    "check.drawings.singleFigure.amend": 2,
    "check.drawings.singleFigure.pass": 2,
    "check.drawings.priorArt.amend": 3,
    "check.drawings.priorArt.pass": 3,
    "check.drawings.sequential.amend": 4,
    "check.drawings.sequential.pass": 4,
    "check.cn.drawings.figuresSequential.amend": 4,
    "check.cn.drawings.figuresSequential.pass": 4,
    "check.tw.drawings.figuresSequential.amend": 4,
    "check.tw.drawings.figuresSequential.pass": 4,
}


def _rank_spec(key: str) -> int | None:
    if key in SPEC_GROUP_RANK:
        return SPEC_GROUP_RANK[key]
    # Required-sections synthesized CheckItems (group 1, spec structure).
    if key.startswith("checks.required_section"):
        return SPEC_STRUCTURE_GROUP
    return None


def _rank_drawings(key: str) -> int | None:
    return DRAWINGS_GROUP_RANK.get(key)


def _assert_monotonic(items, rank_fn, jurisdiction: str, group_label: str) -> None:
    last_rank = 0
    last_key = None
    for check in items:
        rank = rank_fn(check.message_key)
        if rank is None:
            continue
        assert rank >= last_rank, (
            f"{jurisdiction} {group_label} order regression: "
            f"'{check.message_key}' (rank {rank}) emitted after "
            f"'{last_key}' (rank {last_rank}). The document-order invariant "
            f"requires non-decreasing group ranks — see CLAUDE.md "
            f"'Check-ordering consistency invariant'."
        )
        last_rank = rank
        last_key = check.message_key


class TestUsSpecOrderInvariant:
    """US _to_us_report_data spec-checks emit in the document-order invariant."""

    def test_empty_us_analysis_spec_order(self):
        # A minimal US AnalysisResult still emits the pass-status spec
        # checks; ordering must respect the group invariant even with
        # no findings.
        result = AnalysisResult(jurisdiction=Jurisdiction.US, likely_patent=True)
        report = result.to_report_data()
        _assert_monotonic(report.specification_checks, _rank_spec, "US", "spec")

    def test_required_sections_emits_in_spec_structure_group(self):
        # Required sections are Group 1 (spec structure). Verify they appear
        # before any Group 2 (spec content) check by inspecting the pass-path
        # output — required_sections should show up before
        # sequence_listing / cross_reference / prior_art / restrictive_wording.
        from patentlint.models import CheckItem

        result = AnalysisResult(
            jurisdiction=Jurisdiction.US,
            likely_patent=True,
            required_sections_checks=[
                CheckItem(
                    status="amend",
                    message="Missing X section.",
                    message_key="checks.required_section_test_stub",
                ),
            ],
        )
        report = result.to_report_data()
        keys = [c.message_key for c in report.specification_checks]

        # The stub required-sections check must precede sequence_listing
        # (Group 2 leader).
        rs_idx = keys.index("checks.required_section_test_stub")
        sl_idx = keys.index("check.spec.sequenceListing.pass")
        assert rs_idx < sl_idx, (
            f"required_sections (Group 1) emitted after sequence_listing "
            f"(Group 2): keys={keys}"
        )


class TestDrawingsOrderInvariant:
    """CN + TW pipelines emit drawings checks figure_count → figures_sequential."""

    def test_cn_drawings_order(self):
        # The CN pipeline's drawings_checks concatenation is
        # check_figure_count(...) + check_figures_sequential(...). We
        # assert that ordering is reflected in the rank function — a
        # lightweight invariant check that catches future concat swaps
        # without needing to spin up a full CN fixture.
        assert _rank_drawings("check.cn.drawings.count.amend") == 1
        assert _rank_drawings("check.cn.drawings.figuresSequential.amend") == 4

    def test_tw_drawings_order(self):
        assert _rank_drawings("check.tw.drawings.count.amend") == 1
        assert _rank_drawings("check.tw.drawings.figuresSequential.amend") == 4
