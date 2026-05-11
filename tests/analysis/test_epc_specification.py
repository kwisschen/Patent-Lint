# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""EPC G1 spec-structure check tests.

Synthetic fixtures cover the five G1 checks:
  - requiredSections  (Art. 78(1) + Rule 41 + Rule 42(1) EPC)
  - sectionOrdering   (Rule 42(1) EPC)
  - paragraphNumbering (EPO Guidelines F-II § 4.5 — advisory)
  - paragraphEnding   (drafting hygiene — REVIEW)
  - titleRequired     (Rule 41(2)(b) EPC)
"""

from __future__ import annotations

from patentlint.analysis.epc_specification import (
    check_claim_reference_in_spec_epc,
    check_figure_ref_consistency_epc,
    check_numeral_consistency_epc,
    check_paragraph_ending_epc,
    check_paragraph_numbering_epc,
    check_required_sections_epc,
    check_section_ordering_epc,
    check_title_required_epc,
    run_g1_spec_structure_checks,
    run_g2_spec_content_checks,
)

# A canonical-shaped EPC English draft with all Rule 42(1) sub-sections in
# order plus required Title / Claims / Abstract sections.
EPC_DRAFT_CANONICAL = """A signal-processing apparatus for adaptive filtering

TECHNICAL FIELD

The present invention relates to signal-processing apparatuses,
particularly those used for adaptive filtering.

BACKGROUND ART

Adaptive filters are well known in the art. Prior art systems suffer
from convergence delays.

SUMMARY OF THE INVENTION

The invention provides an adaptive filter that converges faster than
prior art systems.

BRIEF DESCRIPTION OF THE DRAWINGS

Fig. 1 shows a block diagram of an apparatus according to the invention.
Fig. 2 shows a flow diagram of a method according to the invention.

DETAILED DESCRIPTION OF THE EMBODIMENTS

Referring to Fig. 1, an adaptive filter 10 includes a processor 12 and
a memory 14 coupled to the processor 12. Fig. 2 illustrates the same
arrangement with the processor 12 and memory 14 in a method-flow view.

CLAIMS

1. An adaptive filter comprising a processor and a memory, characterised
   in that the memory stores convergence parameters.

2. The adaptive filter of claim 1, wherein the processor is configured
   to update the convergence parameters dynamically.

ABSTRACT

An adaptive filter with faster convergence.
"""


def test_title_present_passes():
    results = check_title_required_epc(EPC_DRAFT_CANONICAL)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_title_missing_amends():
    # A draft that starts directly with a section header has no title text
    text_no_title = "TECHNICAL FIELD\n\nThe invention relates to ...\n"
    results = check_title_required_epc(text_no_title)
    assert len(results) == 1
    assert results[0].status == "amend"
    assert "Rule 41(2)(b) EPC" in (results[0].reference or "")


def test_required_sections_all_present_passes():
    results = check_required_sections_epc(EPC_DRAFT_CANONICAL)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_required_sections_missing_claims_amends():
    text = EPC_DRAFT_CANONICAL.replace("CLAIMS\n", "REMOVED\n")
    results = check_required_sections_epc(text)
    assert len(results) == 1
    assert results[0].status == "amend"
    assert "Claims" in (results[0].details or "")


def test_required_sections_missing_abstract_amends():
    text = EPC_DRAFT_CANONICAL.replace("ABSTRACT\n", "REMOVED\n")
    results = check_required_sections_epc(text)
    assert len(results) == 1
    assert results[0].status == "amend"
    assert "Abstract" in (results[0].details or "")


def test_section_ordering_canonical_passes():
    results = check_section_ordering_epc(EPC_DRAFT_CANONICAL)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_section_ordering_out_of_order_amends():
    # Swap BACKGROUND and TECHNICAL FIELD positions
    text = """Title here

BACKGROUND ART

Prior art content.

TECHNICAL FIELD

Field content.

SUMMARY OF THE INVENTION

Summary content.

CLAIMS

1. A device.
"""
    results = check_section_ordering_epc(text)
    assert len(results) == 1
    assert results[0].status == "amend"


def test_paragraph_numbering_absent_passes():
    """No EPC mandate to number paragraphs; absence is fine."""
    results = check_paragraph_numbering_epc(EPC_DRAFT_CANONICAL)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_paragraph_numbering_sequential_passes():
    text = """Title

TECHNICAL FIELD

[0001] First paragraph.

[0002] Second paragraph.

[0003] Third paragraph.
"""
    results = check_paragraph_numbering_epc(text)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_paragraph_numbering_non_sequential_verifies():
    text = """Title

TECHNICAL FIELD

[0001] First paragraph.

[0003] Third paragraph — gap at 0002.

[0004] Fourth paragraph.
"""
    results = check_paragraph_numbering_epc(text)
    assert len(results) == 1
    assert results[0].status == "verify"


def test_paragraph_ending_good_passes():
    results = check_paragraph_ending_epc(EPC_DRAFT_CANONICAL)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_paragraph_ending_missing_punctuation_verifies():
    text = """Title here

TECHNICAL FIELD

This paragraph is missing a final period

This one has a period.

This one is also missing
"""
    results = check_paragraph_ending_epc(text)
    assert len(results) == 1
    assert results[0].status == "verify"


def test_g1_runner_emits_all_five_checks():
    results = run_g1_spec_structure_checks(EPC_DRAFT_CANONICAL)
    assert len(results) == 5
    # All G1 checks pass on the canonical draft
    for r in results:
        assert r.status == "pass", f"Expected pass but got {r.status}: {r.message}"


# ---------------------------------------------------------------------------
# G2 (content) — figure-ref consistency, numeral consistency, claim-in-spec
# ---------------------------------------------------------------------------


def test_figure_ref_consistency_canonical_passes():
    results = check_figure_ref_consistency_epc(EPC_DRAFT_CANONICAL)
    assert len(results) >= 1
    assert all(r.status == "pass" for r in results)


def test_figure_ref_consistency_orphaned_in_brief_amends():
    """A figure declared in the brief description but never used in the
    detailed description is flagged."""
    text = EPC_DRAFT_CANONICAL.replace(
        "Fig. 1 shows a block diagram of an apparatus according to the invention.\n"
        "Fig. 2 shows a flow diagram of a method according to the invention.",
        "Fig. 1 shows a block diagram of an apparatus according to the invention.\n"
        "Fig. 2 shows a flow diagram of a method according to the invention.\n"
        "Fig. 3 shows a third diagram never described in detail.",
    )
    results = check_figure_ref_consistency_epc(text)
    statuses = {r.status for r in results}
    assert "amend" in statuses or "verify" in statuses


def test_numeral_consistency_canonical_passes():
    results = check_numeral_consistency_epc(EPC_DRAFT_CANONICAL)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_numeral_consistency_conflict_amends():
    """Same numeral (10) attached to two disjoint element names — when one
    name appears repeatedly (canonical_count >= 2) and the other appears
    once — is a real drafting error and should amend. The US D1 detector
    requires the canonical name to have at least 2 occurrences before
    treating any other name on the same numeral as a conflict."""
    text = """Title here

TECHNICAL FIELD

The invention relates to filters.

BACKGROUND ART

Prior art filters had problems.

SUMMARY OF THE INVENTION

This invention improves filters.

DETAILED DESCRIPTION OF THE EMBODIMENTS

The adaptive filter 10 has a processor.
The filter 10 receives signals from an antenna.
The filter 10 outputs processed signals.
The aircraft 10 has a wing.

CLAIMS

1. A filter.

ABSTRACT

A filter.
"""
    results = check_numeral_consistency_epc(text)
    assert len(results) >= 1
    # At least one finding should flag the conflict
    assert any(r.status == "amend" for r in results)


def test_claim_reference_in_spec_canonical_passes():
    results = check_claim_reference_in_spec_epc(EPC_DRAFT_CANONICAL)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_claim_reference_in_spec_as_claimed_in_amends():
    text = EPC_DRAFT_CANONICAL.replace(
        "Referring to Fig. 1, an adaptive filter 10 includes a processor 12 and",
        "Referring to Fig. 1, an adaptive filter as claimed in claim 1 includes a processor 12 and",
    )
    results = check_claim_reference_in_spec_epc(text)
    assert len(results) == 1
    assert results[0].status == "amend"
    assert "Guidelines F-IV § 4.3" in (results[0].reference or "")


def test_claim_reference_in_spec_according_to_claim_amends():
    text = EPC_DRAFT_CANONICAL.replace(
        "Referring to Fig. 1, an adaptive filter 10 includes a processor 12 and",
        "Referring to Fig. 1, the apparatus according to claim 1 includes a processor 12 and",
    )
    results = check_claim_reference_in_spec_epc(text)
    assert len(results) == 1
    assert results[0].status == "amend"


def test_g2_runner_emits_all_three_checks():
    results = run_g2_spec_content_checks(EPC_DRAFT_CANONICAL)
    assert len(results) == 3
    # All G2 checks pass on the canonical draft
    for r in results:
        assert r.status == "pass", f"Expected pass but got {r.status}: {r.message}"
