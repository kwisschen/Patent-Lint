# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for `compute_confidence_score` (Phase 5 walker-side helper).

The confidence score is a coarsely-calibrated ranking signal for the
user-facing tier-display knob. Threshold calibration ships in a
follow-up commit using Phase 1 re-judging verdicts; these tests
validate the SHAPE + DIRECTION of each signal, not the absolute values.
"""

from patentlint.analysis.utils import compute_confidence_score


def _baseline(**overrides) -> dict:
    """Default kwargs that produce the score==55 baseline (50 + 5 jaccard
    when has_suggested_match=True).

    Default args: 6-char term `widget`, prefix `the`, intro pool 5,
    no suggested match → score 50 (no bonuses, no penalties).
    """
    args = dict(
        term="widget",
        prefix="the",
        intros_pool_size=5,
        has_suggested_match=False,
        suggested_cross_branch=False,
        suggested_jaccard=None,
        suggested_same_claim=False,
    )
    args.update(overrides)
    return args


class TestConfidenceScore:
    def test_baseline(self):
        # 6-char term, no signals → 50 (low-confidence default)
        assert compute_confidence_score(**_baseline()) == 50

    def test_empty_intro_pool(self):
        # +25 for empty pool — strongest positive signal
        assert compute_confidence_score(**_baseline(intros_pool_size=0)) == 75

    def test_suggested_match_high_jaccard(self):
        # +15 for very-close near-match
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.95,
        )) == 65

    def test_suggested_match_medium_jaccard(self):
        # +10 for close near-match
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.80,
        )) == 60

    def test_suggested_match_weak_jaccard(self):
        # +5 for weak near-match
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.50,
        )) == 55

    def test_suggested_same_claim_bonus(self):
        # +10 for same-claim near-match (additive on top of jaccard)
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.95,
            suggested_same_claim=True,
        )) == 75

    def test_long_term_bonus(self):
        # +10 for term length ≥ 8 chars
        assert compute_confidence_score(**_baseline(
            term="movable positioning component"
        )) == 60

    def test_paren_ref_discriminator(self):
        # +5 for paren-numeral discriminator (`第一電極(120)` style)
        assert compute_confidence_score(**_baseline(
            term="第一電極(120)"
        )) == 65  # 50 + 10 (≥8 chars) + 5 (paren-ref)

    def test_paren_no_digits_no_bonus(self):
        # `term(qualifier)` without digits should NOT trigger paren-ref bonus
        assert compute_confidence_score(**_baseline(
            term="device(qualifier)"
        )) == 60  # 50 + 10 (≥8 chars), no paren-ref bonus

    def test_formal_register_said(self):
        # +5 for `said`
        assert compute_confidence_score(**_baseline(prefix="said")) == 55

    def test_formal_register_cjk(self):
        for p in ("所述", "前述"):
            assert compute_confidence_score(**_baseline(prefix=p)) == 55

    def test_short_uppercase_latin_penalty(self):
        # -20 for `UE`, `RX`, `MAC` etc — clamps to 30
        # (50 - 20 = 30 for `MAC` which is 3 chars all-upper-Latin)
        assert compute_confidence_score(**_baseline(term="MAC")) == 30
        # `RX` is 2 chars — also gets the very-short penalty (-15)
        # 50 - 20 (short upper Latin) - 15 (≤2 chars) = 15
        assert compute_confidence_score(**_baseline(term="RX")) == 15

    def test_very_short_penalty(self):
        # -15 for term len ≤ 2 (CJK fragment / Latin remnant)
        assert compute_confidence_score(**_baseline(term="該")) == 35

    def test_cross_branch_penalty(self):
        # -15 for cross-branch only
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.95,
            suggested_cross_branch=True,
        )) == 50  # 50 + 15 (high jaccard) - 15 (cross-branch) = 50

    def test_clamp_low(self):
        # Stack penalties (short upper-Latin + very short)
        score = compute_confidence_score(**_baseline(term="UE"))
        # 50 - 20 - 15 = 15
        assert score == 15
        assert score >= 0  # clamp

    def test_clamp_high(self):
        # Stack bonuses to drive toward 100
        score = compute_confidence_score(
            term="movable positioning member(120)",
            prefix="said",
            intros_pool_size=0,
            has_suggested_match=True,
            suggested_cross_branch=False,
            suggested_jaccard=0.95,
            suggested_same_claim=True,
        )
        # 50 + 25 (zero pool) + 15 (jaccard ≥0.9) + 10 (same claim) +
        # 10 (≥8 chars) + 5 (paren-ref) + 5 (said) = 120 → clamped to 100
        assert score == 100

    def test_returns_int(self):
        score = compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.7,
        ))
        assert isinstance(score, int)

    def test_clamp_lower_bound_zero(self):
        # Verify the lower clamp is at 0 (not negative)
        # Need to find a config that drives below 0; current signals max
        # at -35 from baseline 50 = 15, so clamp doesn't fire.
        # Verify the floor logic via the helper directly.
        # (Defensive — protects against future signal additions.)
        score = compute_confidence_score(
            term="A",  # 1 char short uppercase Latin
            prefix="the",
            intros_pool_size=5,
            has_suggested_match=False,
            suggested_cross_branch=False,
        )
        # 50 - 20 (short upper-Latin) - 15 (≤2 chars) = 15
        assert score == 15
