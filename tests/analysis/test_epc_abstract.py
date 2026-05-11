# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""EPC G7 abstract check tests.

Word count (Rule 47(2) + Guidelines F-II § 2.3: 50-150 word range) and
structure (single paragraph, no commercial language, no implied phrases,
no merit / self-referential language).
"""

from __future__ import annotations

from patentlint.analysis.epc_abstract import (
    check_abstract_structure_epc,
    check_abstract_word_count_epc,
    run_g7_abstract_checks,
)


# Canonical-shape EPC abstract: ~100 words, single paragraph, no banned
# phrases. Word count comfortably inside the 50-150 range.
EPC_ABSTRACT_CANONICAL = (
    "A signal-processing apparatus for adaptive filtering includes a "
    "processor and a memory storing convergence parameters. The processor "
    "executes an iterative update rule on the convergence parameters in "
    "response to a first input signal received at a first time and a "
    "second input signal received at a later time. A communication "
    "interface coupled to the processor transmits a filtered output "
    "signal to a remote device. The apparatus reduces filter-coefficient "
    "settling time relative to fixed-step adaptive filters by adjusting "
    "the iterative update rule based on a measured signal-to-noise ratio "
    "estimated from received input."
)


# --- Word count ---------------------------------------------------------------


def test_word_count_canonical_passes():
    results = check_abstract_word_count_epc(EPC_ABSTRACT_CANONICAL)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_word_count_empty_amends():
    results = check_abstract_word_count_epc("")
    assert len(results) == 1
    assert results[0].status == "amend"


def test_word_count_over_max_amends():
    long_abstract = " ".join(["word"] * 160)
    results = check_abstract_word_count_epc(long_abstract)
    assert len(results) == 1
    assert results[0].status == "amend"
    assert "150" in results[0].message


def test_word_count_under_min_verifies():
    short_abstract = "A widget."
    results = check_abstract_word_count_epc(short_abstract)
    assert len(results) == 1
    assert results[0].status == "verify"
    assert "50" in results[0].message


# --- Structure ----------------------------------------------------------------


def test_structure_canonical_passes():
    results = check_abstract_structure_epc(EPC_ABSTRACT_CANONICAL)
    assert len(results) == 1
    assert results[0].status == "pass"


def test_structure_multiple_paragraphs_amends():
    text = "First paragraph here.\n\nSecond paragraph with separate content."
    results = check_abstract_structure_epc(text)
    assert len(results) == 1
    assert results[0].status == "amend"
    assert "paragraph" in results[0].message.lower()


def test_structure_implied_phrase_amends():
    text = "A method is provided for processing signals using an adaptive filter."
    results = check_abstract_structure_epc(text)
    assert len(results) == 1
    assert results[0].status == "amend"
    assert "is provided" in (results[0].details or "")


def test_structure_legal_phraseology_amends():
    text = "An apparatus comprising means for filtering, wherein said means filters signals."
    results = check_abstract_structure_epc(text)
    assert len(results) == 1
    assert results[0].status == "amend"


def test_structure_merit_language_amends():
    text = "The present invention provides a novel and advantageous filter design."
    results = check_abstract_structure_epc(text)
    assert len(results) == 1
    assert results[0].status == "amend"


# --- Aggregator ---------------------------------------------------------------


def test_g7_runner_emits_both_checks():
    results = run_g7_abstract_checks(EPC_ABSTRACT_CANONICAL)
    assert len(results) == 2
    for r in results:
        assert r.status == "pass", f"Expected pass but got {r.status}: {r.message}"
