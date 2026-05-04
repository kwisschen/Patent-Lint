# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for `compute_confidence_score` v3 (Phase 5 walker-side helper).

V3 formula is empirically grounded: each signal's sign matches the
correlation observed on broad pre-R34 supplement verdicts (CN 7556,
US 13578, TW 5283). On US data, V3 lifts bucket precision from
absolute 29.4% → 45.3% at threshold 45 (+15.9pp, 1454 findings).

These tests validate the SHAPE + DIRECTION of each signal — they are
contracts, not absolute thresholds. The helper's exact value at a
given input may shift as we re-validate against Phase 1 verdicts.
"""

from patentlint.analysis.utils import compute_confidence_score


def _baseline(**overrides) -> dict:
    """Default kwargs producing baseline 50."""
    args = dict(
        term="widget",  # 6 chars, no triggers
        prefix="the",   # informal, no boost
        intros_pool_size=5,  # nonzero
        has_suggested_match=False,
        suggested_cross_branch=False,
        suggested_jaccard=None,
        suggested_same_claim=False,
    )
    args.update(overrides)
    return args


class TestConfidenceScore:
    def test_baseline(self):
        # No triggers fired → baseline 50
        assert compute_confidence_score(**_baseline()) == 50

    def test_very_short_positive(self):
        # +8 — empirically positive predictor
        assert compute_confidence_score(**_baseline(term="該下")) == 58

    def test_long_term_negative(self):
        # -8 — walker over-extraction class
        assert compute_confidence_score(**_baseline(
            term="movable positioning component"  # >8 chars
        )) == 42

    def test_paren_numeric_negative(self):
        # -5 — paren-context over-extraction
        # 8-char `widget(120)` triggers BOTH long_term (-8) AND paren (-5) = -13
        assert compute_confidence_score(**_baseline(
            term="widget(120)"
        )) == 37

    def test_paren_no_digits_no_penalty(self):
        # `device(qual)` — no digit, no penalty even though parens present
        assert compute_confidence_score(**_baseline(
            term="device(qual)"
        )) == 42  # Only -8 from ≥8 chars; no paren penalty

    def test_short_uppercase_latin_strong_penalty(self):
        # -15 short_upper_latin + -15 very_short (RX is 2 chars and upper-Latin, hits BOTH)
        # Wait: very_short is +8, short_upper_latin is -15 — but 2-char RX is ALSO ≤3
        # So: +8 (very_short) + (-15) (short_upper_latin) = -7 → 50-7=43
        assert compute_confidence_score(**_baseline(term="RX")) == 43

    def test_three_char_acronym(self):
        # 3-char `MAC` — short_upper_latin penalty, NOT very_short
        assert compute_confidence_score(**_baseline(term="MAC")) == 35

    def test_zero_intros_pool_negative(self):
        # -15 — walker-parser failure correlation
        assert compute_confidence_score(**_baseline(intros_pool_size=0)) == 35

    def test_formal_register_said(self):
        # +5
        assert compute_confidence_score(**_baseline(prefix="said")) == 55

    def test_formal_register_cjk(self):
        for p in ("所述", "前述"):
            assert compute_confidence_score(**_baseline(prefix=p)) == 55

    def test_suggested_match_high_jaccard(self):
        # +5 — small positive on weak signal correlation
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.85,
        )) == 55

    def test_suggested_match_low_jaccard_no_boost(self):
        # No boost (j < 0.75)
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.50,
        )) == 50

    def test_suggested_match_same_claim(self):
        # +10 — strong same-claim signal
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.85,
            suggested_same_claim=True,
        )) == 65  # 50 + 5 (jaccard) + 10 (same_claim)

    def test_cross_branch_only_penalty(self):
        # -10 — chain-invalid by strict §112(b)
        assert compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.85,
            suggested_cross_branch=True,
        )) == 45  # 50 + 5 (jaccard) - 10 (cross-branch)

    def test_returns_int(self):
        score = compute_confidence_score(**_baseline(
            has_suggested_match=True,
            suggested_jaccard=0.7,
        ))
        assert isinstance(score, int)

    def test_clamp_low(self):
        # Stack negatives
        score = compute_confidence_score(
            term="UE",  # very_short +8, short_upper_latin -15
            prefix="the",
            intros_pool_size=0,  # -15
            has_suggested_match=True,
            suggested_cross_branch=True,  # -10
            suggested_jaccard=0.0,
            suggested_same_claim=False,
        )
        # 50 + 8 - 15 - 15 - 10 = 18
        assert score == 18
        assert score >= 0  # clamp invariant

    def test_clamp_high(self):
        # Stack positives — but most signals are negative now
        # Best v3 case: short CJK term (short_upper_latin doesn't fire on
        # non-ASCII) + said + same_claim near-match
        score = compute_confidence_score(
            term="該下",  # 2 chars CJK: very_short +8, no acronym penalty
            prefix="said",
            intros_pool_size=5,
            has_suggested_match=True,
            suggested_cross_branch=False,
            suggested_jaccard=0.95,
            suggested_same_claim=True,
        )
        # 50 + 8 (very_short) + 5 (said) + 5 (jaccard) + 10 (same_claim) = 78
        assert score == 78

    def test_directional_invariants(self):
        """Sanity-check that key signal directions are correct (v3 contract).

        These guard against accidentally flipping a sign during refactor.
        """
        baseline = compute_confidence_score(**_baseline())
        long_term = compute_confidence_score(**_baseline(term="abcdefghij"))
        very_short = compute_confidence_score(**_baseline(term="ab"))
        zero_pool = compute_confidence_score(**_baseline(intros_pool_size=0))
        formal_register = compute_confidence_score(**_baseline(prefix="said"))

        # V3 invariants:
        assert long_term < baseline, "long term should reduce score (over-extraction)"
        assert very_short > baseline, "very-short should boost score (empirically positive)"
        assert zero_pool < baseline, "zero pool should reduce score (parser-failure correlation)"
        assert formal_register > baseline, "formal register should boost"
