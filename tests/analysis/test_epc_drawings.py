# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""EPC G3 drawings check tests.

  - figuresSequential (Rule 46(2)(a) EPC)
  - singleFigureLabel (Guidelines F-V § 1.2 — REVIEW status)
  - priorArtLabeling  (Rule 46(2)(h) EPC)
  - figureCount       (informational)
"""

from __future__ import annotations

from patentlint.analysis.epc_drawings import (
    check_figure_count_epc,
    check_figures_sequential_epc,
    check_prior_art_labeling_epc,
    check_single_figure_label_epc,
    run_g3_drawings_checks,
)


EPC_DRAWINGS_CANONICAL = """A title here

BRIEF DESCRIPTION OF THE DRAWINGS

Fig. 1 shows a block diagram of the apparatus.
Fig. 2 shows a flow diagram of the method.
Fig. 3 shows an alternative arrangement.

DETAILED DESCRIPTION OF THE EMBODIMENTS

Referring to Fig. 1, the apparatus 10 includes a processor 12. Fig. 2
illustrates the flow. Fig. 3 shows the alternative.

CLAIMS

1. An apparatus.
"""


# --- Sequential ---------------------------------------------------------------


def test_figures_sequential_canonical_passes():
    results = check_figures_sequential_epc(EPC_DRAWINGS_CANONICAL)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_figures_sequential_gap_amends():
    text = """BRIEF DESCRIPTION OF THE DRAWINGS

Fig. 1 shows the apparatus.
Fig. 3 shows the alternative — gap at Fig. 2.

DETAILED DESCRIPTION OF THE EMBODIMENTS

Referring to Fig. 1 and Fig. 3.
"""
    results = check_figures_sequential_epc(text)
    assert len(results) == 1
    assert results[0].status == "amend"
    assert "2" in (results[0].details or "")


def test_figures_sequential_no_figures_passes():
    results = check_figures_sequential_epc("Just text without figures.")
    assert len(results) == 1
    assert results[0].status == "pass"


# --- Single figure label ------------------------------------------------------


def test_single_figure_label_multi_fig_pass():
    results = check_single_figure_label_epc(EPC_DRAWINGS_CANONICAL)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_single_figure_label_with_fig1_passes():
    text = "The apparatus is shown in Fig. 1, comprising a processor and memory."
    results = check_single_figure_label_epc(text)
    assert len(results) == 1
    assert results[0].status == "pass"


# --- Prior art labeling -------------------------------------------------------


def test_prior_art_labeling_canonical_passes():
    text = """A title

BRIEF DESCRIPTION OF THE DRAWINGS

Fig. 1 shows the new apparatus.
Fig. 2 shows a flow diagram of the method.

DETAILED DESCRIPTION OF THE EMBODIMENTS

Referring to Fig. 1, an apparatus.
"""
    results = check_prior_art_labeling_epc(text)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_prior_art_labeling_with_prior_art_verifies():
    text = """A title

BRIEF DESCRIPTION OF THE DRAWINGS

Fig. 1 shows the new apparatus.
Fig. 2 shows the prior art for comparison.

DETAILED DESCRIPTION OF THE EMBODIMENTS

Referring to Fig. 1.
"""
    results = check_prior_art_labeling_epc(text)
    assert len(results) == 1
    assert results[0].status == "verify"


# --- Figure count -------------------------------------------------------------


def test_figure_count_reports_three():
    results = check_figure_count_epc(EPC_DRAWINGS_CANONICAL)
    assert len(results) == 1
    assert results[0].status == "pass"
    assert results[0].diagnostics is not None
    assert results[0].diagnostics["figure_count"] == 3


# --- Aggregator ---------------------------------------------------------------


def test_g3_runner_emits_all_four_checks():
    results = run_g3_drawings_checks(EPC_DRAWINGS_CANONICAL)
    assert len(results) == 4
    for r in results:
        assert r.status == "pass", f"Expected pass but got {r.status}: {r.message}"
