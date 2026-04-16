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
    # ref len 3, dym len 4 → ratio < 2 AND suffix <2 CJK → accept.
    # (Note: prior test used "控制器裝置" with 2-CJK suffix 裝置; that now
    # falls under F5 modifier-expansion rejection. Use a 1-CJK suffix to
    # verify length-ratio filter alone doesn't trigger.)
    assert _dym_quality_reject_tw("控制器", "控制器X") is False


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
    # ref ⊂ DYM, no stop-particle AND <2 CJK in non-overlap → accept
    # (短suffix 1-char expansion). Used when DYM is a clean
    # ref+suffix form like 控制 → 控制器.
    assert _dym_quality_reject_tw("控制", "控制器") is False


# --- Filter 5 (F5): modifier-expanded superset ----------------------------

def test_modifier_prefix_2cjk_rejected_F5() -> None:
    # DYM = 圖形 + ref (2-CJK modifier prefix) → F5 reject. Generalized
    # case: 圖形使用者介面 should not DYM-suggest itself for 使用者介面 ref
    # since the drafter already wrote the right base noun.
    assert _dym_quality_reject_tw("使用者介面", "圖形使用者介面") is True


def test_modifier_suffix_2cjk_rejected_F5() -> None:
    # DYM = ref + 裝置 (2-CJK modifier suffix) → F5 reject.
    assert _dym_quality_reject_tw("控制器", "控制器裝置") is True


def test_modifier_suffix_1cjk_accepted_F5() -> None:
    # DYM = ref + 1 CJK (short suffix, not modifier-expanded) → accept.
    # Boundary case: 1-char expansions are usually inflection/particle,
    # not modifier, so F5 doesn't trigger.
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


# --- Morphological-prefix fallback (F5) -----------------------------------

def test_morphological_prefix_fallback_basic() -> None:
    from patentlint.analysis.tw_claims import _morphological_prefix_fallback_tw
    intros = {
        "使用者裝置": (1, 0),
        "位置資訊": (1, 0),
        "主題標籤": (1, 0),
    }
    result = _morphological_prefix_fallback_tw("使用者介面", intros)
    assert result is not None
    assert result["term"] == "使用者裝置"
    assert result["claim_id"] == 1


def test_morphological_prefix_fallback_longest_wins() -> None:
    from patentlint.analysis.tw_claims import _morphological_prefix_fallback_tw
    # Two candidates share prefix; longer prefix wins.
    intros = {
        "第二控制訊號": (4, 0),
        "第二通訊模組": (4, 0),
        "第二無線通訊裝置": (4, 0),
    }
    result = _morphological_prefix_fallback_tw("第二無線通訊模組", intros)
    assert result is not None
    # 第二無線通訊裝置 shares "第二無線通訊" = 5 CJK prefix with ref
    # 第二通訊模組 shares "第二" = 2 CJK prefix
    # Longer prefix wins.
    assert result["term"] == "第二無線通訊裝置"


def test_morphological_prefix_fallback_no_match() -> None:
    from patentlint.analysis.tw_claims import _morphological_prefix_fallback_tw
    # No intro shares ≥2 CJK prefix with ref → None
    intros = {
        "控制器": (1, 0),
        "感測器": (1, 0),
    }
    result = _morphological_prefix_fallback_tw("使用者介面", intros)
    assert result is None


def test_morphological_prefix_fallback_ancestor_proximity_tiebreak() -> None:
    from patentlint.analysis.tw_claims import _morphological_prefix_fallback_tw
    # Equal prefix length → nearer ancestor (smaller depth) wins
    intros = {
        "使用者A": (1, 2),  # farther ancestor
        "使用者B": (3, 0),  # current-ish claim
    }
    result = _morphological_prefix_fallback_tw("使用者X", intros)
    assert result is not None
    assert result["claim_id"] == 3  # nearer ancestor
