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
    """Default kwargs that produce the score==80 baseline."""
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
        # `the widget` with intros pool, no suggested match — 80
        assert compute_confidence_score(**_baseline()) == 80

    def test_formal_register_said(self):
        # +5 for `said`
        assert compute_confidence_score(**_baseline(prefix="said")) == 85

    def test_formal_register_cjk(self):
        for p in ("所述", "前述"):
            assert compute_confidence_score(**_baseline(prefix=p)) == 85

    def test_empty_intro_pool(self):
        # +5 for empty pool — no intros at all means almost certainly defect
        assert compute_confidence_score(**_baseline(intros_pool_size=0)) == 85

    def test_short_uppercase_latin_penalty(self):
        # -10 for `UE`, `RX`, `MAC` etc — high baseline FP
        assert compute_confidence_score(**_baseline(term="UE")) == 70
        assert compute_confidence_score(**_baseline(term="RX")) == 70
        assert compute_confidence_score(**_baseline(term="MAC")) == 70

    def test_short_lowercase_no_penalty(self):
        # `the` is short but lowercase — no acronym penalty
        # Using normal term that is 3 chars lowercase
        assert compute_confidence_score(**_baseline(term="abc")) == 80

    def test_suggested_match_jaccard_high(self):
        # +5 × 1.0 = +5
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=1.0,
        )) == 85

    def test_suggested_match_jaccard_partial(self):
        # +5 × 0.6 = +3
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.6,
        )) == 83

    def test_suggested_same_claim_bonus(self):
        # Near-match in same claim is high signal
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=1.0,
            suggested_same_claim=True,
        )) == 90

    def test_cross_branch_only_penalty(self):
        # -10 for cross-branch-only candidate (informational, not chain-valid)
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=1.0,
            suggested_cross_branch=True,
        )) == 75  # 80 + 5 - 10

    def test_clamp_low(self):
        # Stack penalties to drive below 0
        score = compute_confidence_score(
            term="UE",
            prefix="the",
            intros_pool_size=5,
            has_suggested_match=True,
            suggested_cross_branch=True,
            suggested_jaccard=0.0,
            suggested_same_claim=False,
        )
        # 80 - 10 (acronym) + 0 (jaccard) - 10 (cross-branch) = 60
        assert score == 60
        # Verify clamp doesn't go negative (no input can drive that low yet,
        # but clamp must still be in place for future signal additions)

    def test_clamp_high(self):
        # Stack boosts toward 100
        score = compute_confidence_score(
            term="widget",
            prefix="said",
            intros_pool_size=0,
            has_suggested_match=True,
            suggested_cross_branch=False,
            suggested_jaccard=1.0,
            suggested_same_claim=True,
        )
        # 80 + 5 (said) + 5 (empty pool) + 5 (jaccard) + 5 (same claim) = 100
        assert score == 100

    def test_returns_int(self):
        score = compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.7,
        ))
        assert isinstance(score, int)
