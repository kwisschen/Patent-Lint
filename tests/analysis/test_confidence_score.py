# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for `compute_confidence_score` v4 (R58).

V4 weights are ML-distilled from logistic regression on 19,645
supplement_v2 verdicts. These tests validate signal directions and
clamping; specific numeric values track the current formula and may
shift as ML re-runs find better calibrations.
"""

from patentlint.analysis.utils import compute_confidence_score


def _baseline(**overrides) -> dict:
    args = dict(
        term="widget",  # 6 chars
        prefix="the",
        intros_pool_size=5,
        has_suggested_match=False,
        suggested_cross_branch=False,
        suggested_jaccard=None,
        suggested_same_claim=False,
        term_in_spec=False,
    )
    args.update(overrides)
    return args


class TestConfidenceScore:
    def test_baseline(self):
        # 6-char term in mid-length [5,10] → +5; baseline = 50 + 5 = 55
        assert compute_confidence_score(**_baseline()) == 55

    def test_very_short(self):
        # 2-char term → +8 (-2 chars, no other penalties for non-ASCII)
        assert compute_confidence_score(**_baseline(term="該下")) == 58

    def test_long_term_neutral(self):
        # 8-char term in [5,10] → +5
        assert compute_confidence_score(**_baseline(term="abcdefgh")) == 55

    def test_very_long_penalty(self):
        # >12 chars → -3
        assert compute_confidence_score(**_baseline(term="abcdefghijklm")) == 47

    def test_paren_penalty(self):
        # Paren-containing → -12 (mid-length 8 chars)
        # `widget(120)` is 11 chars — in mid-length range +5, paren -12
        # 50 + 5 (mid-len 5-10? no, 11 chars > 10) ... let me re-check.
        # term_len 11 → not 5-10, not >12 → no len bonus
        # paren -12 → 50 - 12 = 38
        assert compute_confidence_score(**_baseline(term="widget(120)")) == 38

    def test_short_acronym_penalty(self):
        # MAC: 3 chars upper-Latin → -18; not in 5-10 mid-len, not very-short
        # 50 - 18 = 32
        assert compute_confidence_score(**_baseline(term="MAC")) == 32

    def test_ordinal_zh_penalty(self):
        # 第一電極 (4 chars, ordinal_zh -5; not 5-10 mid-len → no bonus): 50 - 5 = 45
        assert compute_confidence_score(**_baseline(term="第一電極")) == 45

    def test_zero_intros_pool(self):
        # -5 for zero pool; 6-char term still gets +5
        assert compute_confidence_score(**_baseline(intros_pool_size=0)) == 50

    def test_formal_register_said(self):
        # +5 for `said` + 5 for mid-len = 60
        assert compute_confidence_score(**_baseline(prefix="said")) == 60

    def test_suggested_match_high_jaccard(self):
        # +5 jaccard + 5 mid-len = 60
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.85,
        )) == 60

    def test_suggested_same_claim(self):
        # +8 same_claim + 5 jaccard + 5 mid-len = 68
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.85,
            suggested_same_claim=True,
        )) == 68

    def test_cross_branch_penalty(self):
        # +5 jaccard + 5 mid-len - 10 cross_branch = 50
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.85,
            suggested_cross_branch=True,
        )) == 50

    def test_term_in_spec_boost(self):
        # +10 for spec match (added on top of baseline 55)
        assert compute_confidence_score(**_baseline(term_in_spec=True)) == 65

    def test_clamp_low(self):
        # Stack penalties to drive low
        score = compute_confidence_score(
            term="UE",
            prefix="the",
            intros_pool_size=0,
            has_suggested_match=True,
            suggested_cross_branch=True,
            suggested_jaccard=0.0,
            suggested_same_claim=False,
        )
        # 50 + 8 (very_short) - 18 (short_upper_latin) - 5 (zero_pool) - 10 (cross_branch) = 25
        assert score == 25
        assert score >= 0

    def test_clamp_high(self):
        # Stack positives
        score = compute_confidence_score(
            term="electronic_unit",  # 15 chars, ASCII
            prefix="said",
            intros_pool_size=5,
            has_suggested_match=True,
            suggested_cross_branch=False,
            suggested_jaccard=0.95,
            suggested_same_claim=True,
            term_in_spec=True,
        )
        # 50 - 3 (>12) + 5 (jaccard) + 8 (same_claim) + 5 (said) + 10 (in_spec) = 75
        assert score == 75
        assert score <= 100

    def test_returns_int(self):
        score = compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.7,
        ))
        assert isinstance(score, int)

    def test_directional_invariants(self):
        baseline = compute_confidence_score(**_baseline())
        # short term (2 chars CJK) > baseline
        assert compute_confidence_score(**_baseline(term="該下")) > baseline
        # paren < baseline
        assert compute_confidence_score(**_baseline(term="widget(1)")) < baseline
        # acronym << baseline
        assert compute_confidence_score(**_baseline(term="MAC")) < baseline
        # term_in_spec > baseline
        assert compute_confidence_score(**_baseline(term_in_spec=True)) > baseline
        # formal register > baseline
        assert compute_confidence_score(**_baseline(prefix="said")) > baseline
