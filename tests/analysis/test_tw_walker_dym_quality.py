# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Phase B3 — R21-analog DYM quality-reject filter for the TW walker.

Covers the three filters in ``_dym_quality_reject_tw``:
    1. length-ratio (DYM > 2× ref)
    2. leading-particle (DYM starts with a prep/particle/ref-prefix)
    3. substring-wrap (ref ⊂ DYM with stop-particle wrap)

Plus interaction with the existing self-suggest filter and the null
case (no DYM suggestion to reject).
"""

from __future__ import annotations

from patentlint.analysis.tw_claims import _dym_quality_reject_tw


# --- Filter 1: length ratio ------------------------------------------------

def test_length_ratio_rejects_disproportionate_expansion() -> None:
    # ref len 3, dym len 7 → ratio > 2 → reject
    assert _dym_quality_reject_tw("控制器", "測量到的溫度感測值") is True


def test_length_ratio_accepts_modest_expansion() -> None:
    # ref len 3, dym len 5 → ratio < 2 → accept (subject to other filters)
    assert _dym_quality_reject_tw("控制器", "控制器裝置") is False


# --- Filter 2: leading particle ------------------------------------------

def test_leading_particle_對_rejected() -> None:
    # DYM starts with 對 (preposition) → reject
    assert _dym_quality_reject_tw("控制器", "對控制器") is True


def test_leading_particle_基於_rejected() -> None:
    # DYM starts with multi-char preposition 基於 → reject
    assert _dym_quality_reject_tw("控制器", "基於控制器") is True


def test_leading_particle_該_rejected_TW_specific() -> None:
    # TW reference prefix 該 as DYM head → walker noise, reject
    assert _dym_quality_reject_tw("控制器", "該控制器") is True


def test_leading_particle_該等_rejected_TW_plural() -> None:
    # TW plural-reference prefix 該等 as DYM head → reject
    assert _dym_quality_reject_tw("控制器", "該等控制器") is True


def test_leading_particle_所述_rejected() -> None:
    # Classic TW ref prefix 所述 as DYM head → reject
    assert _dym_quality_reject_tw("控制器", "所述控制器") is True


# --- Filter 3: substring wrap w/ stop-particle --------------------------

def test_substring_wrap_with_的_stop_particle_rejected() -> None:
    # ref ⊂ DYM, trailing 的 → "控制器的輸出" contains 控制器 + 的 noise
    assert _dym_quality_reject_tw("控制器", "控制器的輸出") is True


def test_substring_wrap_with_之_classical_possessive_rejected() -> None:
    # TW-specific: classical 之 possessive also wraps walker noise
    assert _dym_quality_reject_tw("控制器", "控制器之輸出") is True


def test_substring_wrap_without_stop_particle_accepted() -> None:
    # ref ⊂ DYM, but no stop-particle in wrap → accept (genuine match)
    assert _dym_quality_reject_tw("控制", "控制器") is False


# --- Interaction: ordinary acceptance -----------------------------------

def test_clean_unrelated_dym_accepted() -> None:
    # Different NPs, similar length, no substring relation → accept
    assert _dym_quality_reject_tw("感測器", "控制器") is False


def test_byte_identical_self_suggest_handled_upstream() -> None:
    # Self-suggest filter runs before this gate; test the length-ratio
    # branch on the edge case where ref == dym: trivially equal, so
    # len(dym) > 2*len(ref) is False and substring_wrap is False (not
    # strict substring). Should pass through as accept.
    assert _dym_quality_reject_tw("控制器", "控制器") is False


# --- Regression: CN-style particles in Traditional form ----------------

def test_能夠由_traditional_rejected() -> None:
    # CN R21 had 能够由; TW port uses Traditional 能夠由
    assert _dym_quality_reject_tw("控制器", "能夠由控制器") is True


def test_響應於_traditional_rejected() -> None:
    # CN R21 had 响应于; TW port uses Traditional 響應於
    assert _dym_quality_reject_tw("控制器", "響應於控制器") is True
