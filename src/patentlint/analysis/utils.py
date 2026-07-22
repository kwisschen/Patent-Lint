# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Shared analysis utilities.

Extracted from analysis/claims.py for reuse across multiple checks.
"""

from __future__ import annotations

import re
from typing import Any


# ADR-145 diagnostic fingerprint helper. Every amend/verify CheckItem
# emission carries a diagnostics dict so error-report emails contain a
# consistent structural-metadata block across every check — no silent
# "this one has a fingerprint, that one doesn't" UX. The helper drops
# None values so call-sites can pass every candidate key unconditionally
# without littering the output.
#
# VALID diagnostic keys (structural only, no claim content):
#   - counts / lengths: flagged_count, total_count, *_charlen
#   - Unicode codepoints from closed-set chars: *_codepoint (e.g.
#     sample_last_char_codepoint for paragraph-ending checks)
#   - closed-set enum strings: *_code, *_path (e.g. reason_code:
#     "length" / "content" / "missing")
#   - booleans: has_*, is_*, *_matched
# INVALID: raw noun/verb content, claim text, user-typed strings.
def _dx(**kwargs: Any) -> dict[str, Any]:
    """Build a structural-diagnostic fingerprint dict, dropping None values."""
    return {k: v for k, v in kwargs.items() if v is not None}


def numeral_context_excerpt(
    spec_text: str,
    numeral: str,
    name_clean: str | None = None,
    before: int = 12,
    after: int = 12,
) -> str | None:
    """Return a short context excerpt around the first occurrence of
    ``numeral`` in ``spec_text``.

    Format: ``"…<before-chars> <numeral> <after-chars>…"``. When
    ``name_clean`` is provided, prefer occurrences where the name
    appears within ±30 chars of the numeral so the excerpt actually
    illustrates the conflict pair (avoids returning a year-like or
    unrelated occurrence).

    Returns None when no qualifying occurrence is found. Excerpt size
    is bounded (12 chars before + 12 chars after by default) to stay
    within the "structural fingerprint" privacy boundary — same
    convention as `context_after` in `_ref_numeral_finding_diag` and
    other walker diagnostics. Newlines are collapsed so the excerpt
    fits on one report-payload line.

    Used by `numeralConsistency` (TW/CN/US) to enrich the diagnostic
    with an actual snippet of where the conflict occurred (R67
    2026-05-08 — anonymous reports were emitting bare digits with
    no surrounding context, useless for triage).
    """
    if not spec_text or not numeral:
        return None
    pat = re.compile(r"(?<!\d)" + re.escape(numeral) + r"(?!\d)")
    matches = list(pat.finditer(spec_text))
    if not matches:
        return None
    chosen = matches[0]
    if name_clean:
        needle = name_clean.lower()
        for m in matches:
            ctx = spec_text[max(0, m.start() - 30): m.end() + 30].lower()
            if needle in ctx:
                chosen = m
                break
    start = max(0, chosen.start() - before)
    end = min(len(spec_text), chosen.end() + after)
    snippet = spec_text[start:end].replace("\n", " ").replace("\t", " ").strip()
    snippet = re.sub(r"\s{2,}", " ", snippet)
    return f"…{snippet}…"


def annotate_term_in_spec(
    findings: list[dict],
    spec_text: str,
) -> None:
    """Annotate each walker finding with `term_in_spec` + adjust confidence.

    R57 (2026-05-05): cross-validate antecedent walker findings against
    the document's specification body. When a flagged term ALSO appears
    in the description (technical field + background + summary +
    drawings description + detailed description / embodiment), the
    drafter likely DID introduce the concept somewhere — even if the
    claim-chain walker can't resolve the back-reference. The spec match
    boosts confidence that the finding is a STYLISTIC issue (term
    introduced in spec but referenced in claims without parallel intro)
    vs. a pure walker FP (over-capture or fragment).

    Mutates findings list in place. Adds `term_in_spec: bool` and
    boosts `confidence_score` by +10 when match. Empty spec text leaves
    the field False; no score change.
    """
    # R57c (2026-05-05): annotated term_in_spec but did NOT mutate
    # confidence_score — abstract proxy on supplement_v2 showed term_in_abs
    # was a slight negative signal for legit (in 13.4% / out 18.7%).
    #
    # R61c (2026-05-05 evening): Path 1 corpus measurement using FULL
    # spec body (Google Patents description fetch) on n=9382 judged TW
    # supplement_v2 findings showed the inverse direction:
    #
    #   term_in_spec=True:   13.2% legit (n=9118 TP+FP)
    #   term_in_spec=False:   0.8% legit (n=264 TP+FP)
    #   baseline:            12.8% legit
    #
    # Absence is the strong walker_fp signal (~−12pp from baseline).
    # Wire as a −15 confidence penalty when the term is missing from
    # spec body — pushes walker over-captures out of the high-conf
    # bucket. Magnitude calibrated so the floor lands these findings
    # well below typical thresholds (~50 baseline → ~35 with penalty).
    #
    # Why this differs from the R57 abstract result: abstract is a
    # tiny ~150-char excerpt; full spec body is 10-50K chars and
    # captures actual element introductions the drafter wrote.
    # Walker over-captures aren't in spec; legit defects are.
    if not spec_text:
        for f in findings:
            f["term_in_spec"] = False
            # When we have NO spec text (e.g., parser-only fixture or
            # corpus record without description), don't apply penalty
            # — the False here means "no signal", not "validated absent".
        return
    for f in findings:
        term = (f.get("term") or "").strip()
        in_spec = bool(term) and term in spec_text
        f["term_in_spec"] = in_spec
        if not in_spec and "confidence_score" in f:
            # Validated walker over-capture signal — push out of bucket.
            f["confidence_score"] = max(0, f["confidence_score"] - 15)


def annotate_term_in_symbol_table(
    findings: list[dict],
    symbol_table_norms: set[str],
) -> None:
    """Post-walker annotator — sets `term_in_symbol_table: bool` per finding.

    R61b (2026-05-05): TIPO-style hybrid uses 符號說明 as a *lookup table*
    (not a walker silencer — see ``feedback_no_symbol_table_antecedent_bridge.md``
    for why silencing was rejected). Drafter-declared element names in
    符號說明 are evidence the element exists; missing claim-chain intro
    on a declared element is more likely a real legit defect than walker
    over-capture. The flag rides on the finding payload so frontend can
    render a "declared in 符號說明" chip and the confidence-score helper
    can use it as a small +boost.

    The walker itself sets `term_in_symbol_table` at emit-time when
    available (so the boost flows into ``confidence_score`` directly);
    this helper exists for parity with ``annotate_term_in_spec`` and for
    pipeline-level recomputation if the walker is ever called without
    symbol_table context.

    Mutates ``findings`` in place. Empty ``symbol_table_norms`` leaves
    every finding's flag at False.
    """
    if not symbol_table_norms:
        for f in findings:
            f.setdefault("term_in_symbol_table", False)
        return
    for f in findings:
        term = (f.get("term") or "").strip()
        if "term_in_symbol_table" not in f:
            f["term_in_symbol_table"] = bool(term) and term in symbol_table_norms


def make_document_dedup_key(term: str, reference_form: str) -> str:
    """Per-document dedup key for an antecedent-basis finding.

    The walker emits at `(claim_id, term, reference_form)` granularity.
    Across N dependent claims that all reference `the X` when X has no
    antecedent, N redundant findings fire — same logical defect, just
    surfaced in N claim contexts. Collapsing them at the display layer
    needs a stable key that ignores claim_id but preserves the
    (term, reference_form) pair, which IS the logical defect identity.

    Format: ``"<term>|<reference_form>"`` — pipe-delimited so JSON-
    serializable + readable in trace output. Whitespace-collapsed and
    case-folded for cross-claim equivalence under common stylistic
    drift (`said widget`, `said widget `, `Said widget`).
    """
    t = " ".join((term or "").split()).casefold()
    r = " ".join((reference_form or "").split()).casefold()
    return f"{t}|{r}"


# Closed set of "formal-register" reference prefixes across jurisdictions.
# Formal register correlates weakly but consistently with deliberate
# drafter intent (drafter chose `said` over `the`); the +5 confidence
# adjustment reflects that, not absolute correctness.
_FORMAL_PREFIXES = frozenset({"said", "所述", "前述"})

# R59: precompiled regex for ordinal-zh detection (used in compute_confidence_score)
_re_ordinal_zh = re.compile(r'^第[一二三四五六七八九十百0-9]+')


def _r59_ml_path_match(
    *,
    is_us: bool,
    intros_pool: int,
    term_len: int,
    ref_len: int,
    has_latin: bool,
    is_ordinal_zh: bool,
    is_cross_branch: bool,
) -> bool:
    """R59 (2026-05-05): match against ML-distilled high-precision paths.

    Trained sklearn DecisionTree (depth 8, min_leaf 30) on combined
    phase2b verdicts (55,503 labeled findings, 21.8% absolute precision).
    Identified 11 leaves with ≥50% precision (combined 70.4% precision
    on 452 findings — at the 70%-bucket goal).

    Each leaf's decision path encoded as one branch below. Returns True
    if a finding's feature vector matches any high-precision leaf.
    Pure deterministic Python — no model file shipped at runtime.

    Top-precision branches (top 4 of 11):
      Leaf 264: 94.1% (n=68) — US, intros_pool>67, term_len>6, ref_len≤17
      Leaf 255: 89.4% (n=47) — US, intros_pool 54-63, term_len 7-11, ref_len>14
      Leaf 263: 74.2% (n=31) — US, intros_pool>67, term_len≤6, ref_len≤17
      Leaf 261: 72.9% (n=48) — US, intros_pool 63-67, ref_len≤17
    """
    # R59c (2026-05-05): single robust ML-distilled path.
    # depth-4 DT, min_samples_leaf=200, ONE leaf passing strict
    # cross-validation: train_p=70.9% (n=316), test_p=56.5% (n=85).
    # Path: is_us AND intros_pool > 53.5 AND ref_len <= 20.5
    if is_us and intros_pool > 53.5 and ref_len <= 20.5:
        return True
    # FALLBACK GUARD: rest of original R59 paths kept commented for
    # ablation; they overfit (in-sample 70-94% but test 5-30%).
    if False and is_us and intros_pool > 4.5 and ref_len <= 20.5 and intros_pool > 54.5:
        # Subtree at intros_pool > 54.5 (leaves 254/255/258/261/263/264/265)
        if intros_pool > 63.5:
            if ref_len <= 17.5:
                if intros_pool > 67.5:
                    if term_len > 6.5:
                        return True  # leaf 264, 94.1%
                    else:
                        return True  # leaf 263, 74.2%
                else:
                    return True  # leaf 261, 72.9%
            else:
                return True  # leaf 265, 62.2%
        else:  # 54.5 < intros_pool ≤ 63.5
            if term_len > 6.5:
                if term_len > 11.5:
                    if ref_len > 18.5:
                        return True  # leaf 258, 64.1%
                else:  # term_len 7-11
                    if ref_len > 14.5:
                        return True  # leaf 255, 89.4%
                    else:
                        return True  # leaf 254, 63.2%
    # US, ref_len 21-40, very high pool (leaf 284, 285)
    if is_us and intros_pool > 4.5 and 20.5 < ref_len <= 40.5 and intros_pool > 73.5:
        if intros_pool <= 211.0:
            return True  # leaf 284, 61.8%
        else:
            return True  # leaf 285, 50.0%
    # US, low pool, very long term (leaf 185, 56.5%)
    if is_us and intros_pool <= 4.5 and not is_cross_branch and 11.5 < term_len <= 17.5:
        return True
    # CN/TW path REMOVED: holdout test showed in-sample 58.8% on TW leaf
    # 22 (the only non-US qualifying path) regressed to 5.7% on TEST
    # data — the tree overfit. Keeping only US paths which retained
    # ~54.6% precision on test data (vs absolute 32%, +23pp lift).
    # CN/TW need their own per-juris model + stricter cross-validation
    # before any path encoding ships (R60 follow-up).
    return False


def compute_confidence_score(
    *,
    term: str,
    prefix: str,
    intros_pool_size: int,
    has_suggested_match: bool,
    suggested_cross_branch: bool,
    suggested_jaccard: float | None = None,
    suggested_same_claim: bool = False,
    term_in_spec: bool = False,
    term_in_symbol_table: bool = False,
    is_quoted_reference_format: bool = False,
    reference_form: str = "",
    jurisdiction: str = "",
) -> int:
    """Confidence score (0–100) for an antecedent-basis finding.

    Computed at walker emit-time from signals available when the
    finding fires. NOT a probability — a coarsely-calibrated ranking
    score for the user-facing tier-display knob (Phase 5 of the
    precision-push plan).

    Formula evolution (in-source for transparency — calibration is a
    research problem, the values are working hypotheses):

    - **v1** (shipped `c3b83f2`): baseline 80 + ±5 adjustments.
      Pilot calibration showed 99% of findings clustered 75–90 with
      no spread.
    - **v2** (shipped `24edd56`): baseline 50 + larger bonuses on
      "strong positive evidence" signals. Pilot showed meaningful
      spread BUT empirical signal-correlation analysis on the broad
      pre-R34 supplement data (CN 7556, US 13578, TW 5283 verdicts)
      revealed v2's positive signals are INVERSELY correlated with
      `legit_drafting_error` — high-conf buckets had LOWER precision
      than absolute. v2 was push findings the wrong way.
    - **v3** (this version): empirically-grounded sign reversal. Each
      signal direction matches the broad-corpus correlation:
      `very_short` correlates with legit (+); `long_term`,
      `paren_term`, `short_upper_latin`, `zero_pool` correlate with
      walker_fp (−). On US 13578 verdicts: absolute 29.4% → bucket
      precision 45.3% at threshold 45 (+15.9pp lift, 1454 findings).

    V3 signals (sign matches empirical correlation):

    - **+8** very-short term (≤2 chars) — empirical +6.1pp lift; many
      single-char CJK component refs (該下/該上/該左/該右) ARE legit
      defects; intuition was wrong, data wins.
    - **+10** suggested-match same-claim — kept positive (small
      negative correlation in data but theoretically a strong signal
      for stylistic-drift typos).
    - **+5** suggested-match (any) with high Jaccard (≥0.75) — small
      positive on weak correlation.
    - **−8** long term (≥8 chars) — empirical −12.6pp; catches walker
      over-extraction past head noun.
    - **−5** paren term (`X(YYY)` shape) — empirical −9.4pp; walker
      grabbing parenthetical context = over-extraction signal.
    - **−15** short ASCII-uppercase (≤3 chars) — empirical −18.0pp;
      Latin acronym over-bridge class (R34/R40/R41/R42 cluster).
    - **−15** zero intros in chain — empirical −19.5pp; walker-parser
      failure indicator, NOT a defect-strength signal as v2 assumed.
    - **−10** suggested-match cross-branch only — chain-invalid by
      strict §112(b) definition.

    NOT yet validated against post-R48 verdicts (Phase 1 supplement_v2
    in-flight). When those arrive, re-run signal correlation analysis
    and ship v4 if directions shift.

    Clamped to [0, 100].
    """
    # R58 (2026-05-05) — ML-distilled v4 weights. Logistic regression on
    # 19,645 supplement_v2 labeled findings provides empirically-grounded
    # signal magnitudes (raw coefficients, original units):
    #     is_us:             +1.93   → score +25
    #     same_claim:        +0.33   → score +8
    #     ref_len:           +0.15/c → folded into long_term bonus
    #     paren_num/any:     -1.25   → score -12
    #     latin_upper_short: -1.70   → score -18
    #     has_latin:         -0.87   → handled via short-acronym + paren guards
    #     ordinal_zh:        -0.48   → score -5
    #     term_len > 10:     small-neg (over-capture) → score -3 if very long
    #
    # Per-jurisdiction calibration: post-R52 walker has US precision 35.5%,
    # CN 14.5%, TW 12.7%. The is_us signal would massively help but is not
    # currently passed via this signature; deferred to R59 if needed.
    #
    # Distillation discipline: ML output is walker code patches, NOT ML
    # inference at runtime. Stays purely deterministic Python.
    import re as _re
    term_str = term or ""
    score = 50
    # Term-length signals
    if 0 < len(term_str) <= 2:
        score += 8
    elif 5 <= len(term_str) <= 10:
        score += 5  # mid-length terms = empirically more legit
    elif len(term_str) > 12:
        score -= 3  # very-long = walker over-capture
    # Paren-containing — strong WFP per LR (-1.25/-0.87)
    if "(" in term_str or "（" in term_str:
        score -= 12
    # Short ASCII-uppercase Latin — strongest WFP signal (LR -1.70)
    if (
        term_str
        and len(term_str) <= 3
        and term_str.isascii()
        and term_str.isupper()
    ):
        score -= 18
    # Ordinal-Chinese-prefix — counter-intuitive WFP signal (LR -0.48)
    if _re.match(r'^第[一二三四五六七八九十百0-9]+', term_str):
        score -= 5
    # 2026-06-01 confidence-tuning: English-ordinal-led terms (`first X` /
    # `second X` / `third X`) are over-represented in walker_fp at high
    # confidence per LR analysis (coef -0.85). Bumped penalty to -10.
    if _re.match(r'^(first|second|third|fourth|fifth)\s+', term_str.lower()):
        score -= 10
    # 2026-06-01 confidence-tuning: single-word English terms (no
    # whitespace in term, no digit) are over-represented in walker_fp
    # at high confidence (LR coef -0.49) — these are typically generic
    # domain nouns (cancer / instructions / operations / customers / data)
    # that get bound to refs but are spec-defined rather than claim-intro'd.
    # Gated by jurisdiction (US/EPC English) and digit-absence so CJK
    # terms + Latin acronyms with digits are unaffected.
    if (
        jurisdiction in ("US", "EPC")
        and term_str
        and term_str.isascii()
        and " " not in term_str
        and not any(c.isdigit() for c in term_str)
    ):
        score -= 5
    # Empty intro pool — slight WFP signal
    if intros_pool_size == 0:
        score -= 5
    # Suggested-match signals (LR + 0.33 for same_claim)
    if has_suggested_match:
        j = suggested_jaccard if suggested_jaccard is not None else 0.0
        if j >= 0.75:
            score += 5
        if suggested_same_claim:
            score += 8  # R58: stronger weight per LR
        if suggested_cross_branch and not suggested_same_claim:
            score -= 10
    # Formal-register prefix — minor positive
    if prefix and prefix.strip().lower() in _FORMAL_PREFIXES:
        score += 5
    # R57c (2026-05-05) REVERTED: term_in_spec was assumed +10 positive
    # but empirical test on supplement_v2 (using abstract as proxy) showed
    # NEGATIVE signal: in_abs=True precision 13.4% vs in_abs=False 18.7%.
    # Walker over-captures legit noun phrases that also appear in spec,
    # so spec presence weakly correlates with WFP not legit.
    # Kept the kwarg for forward compatibility but no score change.
    if term_in_spec:
        pass  # signal not currently used; placeholder for future training
    # R61b (2026-05-05): TIPO-style 符號說明 lookup-table — empirically
    # NEUTRAL after corpus validation (Path 1 result, 2026-05-05).
    #
    # Initial direction (+5 boost) was based on local TW fixtures showing
    # 9/9 in_st findings as legit defects. Corpus measurement on 9382
    # judged supplement_v2 findings flipped the picture:
    #
    #   in_st (inline-mined):  9.7% legit (n=945)
    #   not_in_st:            13.1% legit (n=8947)
    #   baseline:             12.8% legit
    #
    # Symbol_table presence is mildly NEGATIVE for legit (-3pp), not
    # positive. Local fixtures were biased: zero walker_fp ground-truth
    # in their hand-labels (walker hardened against them over many
    # rounds), so every in_st finding was guaranteed legit by sample
    # construction. Corpus is authoritative.
    #
    # Held at zero until: (a) we have a clean structured-符號說明
    # corpus signal (vs the inline-miner used in measure_term_in_desc.py)
    # to discriminate production walker behavior from corpus-measured
    # behavior, OR (b) we ship a re-judging round that distinguishes
    # "trivial-amendable" from "substantive" subcategories of legit.
    #
    # Kept the kwargs in place so the (b) did-you-mean enrichment and
    # (c) finding-payload flag continue working without churn.
    if term_in_symbol_table and not is_quoted_reference_format:
        pass  # corpus-empirical: signal is mildly negative, not positive
    # R59 (2026-05-05): ML-distilled high-precision-path bonus. When the
    # finding matches one of 11 sklearn DecisionTree leaves identified at
    # ≥50% precision (combined 70.4% on 452 findings), boost score by +25
    # to lift into the high-conf tier. Pure deterministic encoding of
    # the trained tree's decision paths.
    if reference_form and jurisdiction:
        is_us = (jurisdiction == "US")
        ref_len = len(reference_form)
        has_latin = any('A' <= c <= 'z' for c in (term or ""))
        is_ordinal_zh = bool(_re_ordinal_zh.match(term or ""))
        is_cross_branch = suggested_cross_branch and not suggested_same_claim
        if _r59_ml_path_match(
            is_us=is_us,
            intros_pool=intros_pool_size,
            term_len=len(term or ""),
            ref_len=ref_len,
            has_latin=has_latin,
            is_ordinal_zh=is_ordinal_zh,
            is_cross_branch=is_cross_branch,
        ):
            score += 25
    return max(0, min(100, score))

# Hyphen-aware word token: matches "multi-stage", "non-transitory", "widget"
# R5 (2026-05-26): extend NP joiners to U+2010 HYPHEN and U+2011 NON-BREAKING
# HYPHEN in addition to ASCII U+002D. Drafters who write `large‑size silicon
# carbide particle` with U+2011 (issue #97) or `flow‑channel layer` with U+2011
# (issue #103 / spec extractor) previously had NP captures truncated at the
# hyphen, emitting bare `large` / `channel layer` (1-3 token fragments) instead
# of the full compound. Same `_WORD` is shared by US claims walker (this file)
# and the spec numeralConsistency name extractor — one change covers both.
_WORD = r"\w+(?:[-\u2010\u2011]\w+)*"

# Captures noun phrases (up to 6 words) after "the"/"said" or "a"/"an".
_STOP_WORDS = (
    r"(?:is|are|was|were|has|have|had|do|does|did|being|been|"
    r"can|could|may|might|will|would|shall|should|must|"
    r"of|to|from|with|and|or|that|which|for|by|on|in|at|as|"
    r"along|between|through|within|upon|above|below|across|"
    r"toward|towards|against|around|during|into|onto|"
    r"beside|beneath|beyond|behind|before|after|among|about|"
    r"inside|outside|throughout|until|without|"
    r"but|if|so|yet|nor|who|whom|whose|where|when|while|"
    r"wherein|comprising|consisting|including|having|configured|"
    # Finite (3sg / base) forms of the transitional + enumeration verbs.
    # The -ing gerunds above were stopped, but `_NP_CORE` bled through
    # `X comprises Y` / `X consists of Y` clauses (389 `comprises` walker
    # FPs in the US pool: `hardware input data comprises human interface`
    # captured whole). `meets` / `reaches` mirror the same N+V over-capture
    # (`confidence measurement meets`, `second node respectively reaches`).
    # All are unambiguous verbs — never noun-phrase constituents.
    r"comprises|comprise|consists|consist|meets|reaches|"
    # R3 (2026-05-22): further finite 3sg verbs that bled into the NP
    # capture across `<noun> <verb>` claim clauses — issues #86 (`the
    # leakage inspection region presents`), #87 (`annular groove
    # constitutes`), #88 (`contact lens storage solution flows`),
    # #89 (`presents`), #92 (`control unit uses`). The walker's own
    # did-you-mean already names the clean head noun in every case.
    r"presents|constitutes|flows|uses|"
    # R7 (2026-05-29): finite-verb over-capture (drained from
    # 2026-05-29 report queue — issues #120 `guiding pattern exceeds`,
    # #127 `second mounting portion extend`, #128 `encapsulation layer
    # jointly constitute`, #135 `second magnetic component stays`).
    # `exceeds` joins the existing `meets|reaches` measurement-comparison
    # family; `extend`/`constitute` cover the base-form gaps left by
    # R2/R3 (which seeded only the 3sg `extends`/`constitutes`); `stays`
    # is a positional verb common in mechanical claims. All four are
    # unambiguous finite verbs in claim diction — MPEP § 2173.05(e)
    # treats only noun phrases as §112(b) reference targets.
    r"exceeds|extend|constitute|stays|"
    # R8 (2026-06-01): clock-domain / PLL-class verbs surfaced by issue
    # #152 (`master comparison signal occur`, `phase-delayed clock signal
    # successively approach`). `occur` / `approach` are unambiguous
    # event-domain verbs (different word from `occurring` gerund which
    # CAN be part of a compound noun like `non-naturally occurring
    # pathogen` — word boundary semantics protect that). `successively`
    # is added to _ADVERB_STOPS (trailing strip) to handle the adverb-
    # before-verb shape `<noun> successively <verb>`.
    r"occur|approach|"
    # 2026-06-01 batch — additional finite verbs from US bulk-report
    # batch (mechanical adapter / monitor mount drafter): `move`
    # (positional / kinematic verb), `complies` (3sg conformance
    # verb). Both unambiguous finite verbs in claim diction.
    r"move|complies|"
    # R11 (2026-06-04): finite-verb over-capture from the 2026-06-04 report
    # batch (battery-pack / clamping-member mechanical drafter). `passes`
    # is the matrix verb in `the <noun> passes through the <hole>` clauses
    # (#188 `pressing member passes`, #189 `clamping member passes`, #190
    # `first/second extension arm passes`); `correspond` is the base-form
    # gap left by the existing 3sg `corresponds` (#188 `two poles
    # respectively correspond` — plural subject takes base form, mirror of
    # R7's base-form `extend|constitute`). The intervening `respectively`
    # adverb is already stripped by `_ADVERB_STOPS`. Both unambiguous finite
    # verbs in claim diction — MPEP § 2173.05(e) treats only noun phrases as
    # §112(b) reference targets. Shared `_NP_CORE` covers the spec-support
    # extractor too (#192 same `<arm> passes` over-capture, cross-CHECK
    # symmetry for free). No CN/TW report of the analogous verb yet —
    # deferred per DR-1 (CJK 穿經/穿過 is a single token, different shape).
    r"passes|correspond|"
    # R12 (2026-06-09): finite-verb over-capture from the 2026-06-09 US
    # report batch. `depends` (3sg, `the virtual plane depends on …` #205)
    # and `stores` (3sg, `the storage circuit further stores …` #200,
    # `the host stores …` #218) are unambiguous matrix verbs — never noun
    # termini in claim diction. `not` is NOT added — `the strand not
    # conjugated to the label` is a legitimate negative-limitation noun
    # phrase, so `not` has real NP uses (queued for a US walker-round).
    # Spec-support shares `_NP_CORE` (cross-CHECK covered for free). No
    # CN/TW report of the analogous verbs — deferred per DR-1.
    r"depends|stores|"
    # R13 (2026-06-09): `refers` (3sg) — `the reference point refers to a
    # center …` (#204) over-captured `reference point refers`. Unambiguous
    # finite verb (`X refers to Y`). The 4 active `particular zone refers`
    # labels that previously blocked this were re-triaged this round
    # (legit_drafting_error → walker_fp, DR-10): their own notes call them
    # "verb phrase fragment, not a noun" and the clean head `particular
    # zone` is introduced via `a particular zone` (Pattern A) — so they
    # were doubly mis-shaped corpus labels, not real §112 defects.
    r"refers|"
    # R16 (2026-06-23, ADR-159 Zero-FP Sweep 1A): `conforms` (3sg) — the
    # matrix verb in `the interface conforms to <standard>` (US9582415B2
    # c6/c7/c12/c13) over-captured `interface conforms`. Unambiguous finite
    # verb (`X conforms to Y`); no noun sense in claim diction. The clean head
    # `the interface` resolves to `an interface` (Pattern A, claim 1). The
    # base form `conform` and 3sg sibling are not added (no corpus signal);
    # `replicates` was withheld — it carries a real biotech noun sense
    # (`triplicate replicates`), so it needs a gated round, not a bare add.
    # Shared `_NP_CORE` covers the spec-support extractor (cross-CHECK). EPC
    # reuses the US walker. No CN/TW report — DR-1.
    r"conforms|"
    # R19 (2026-06-25, ADR-159): `follows` (3sg) — trailing finite verb surfaced
    # by the normalization-asymmetry probe (gold walker_fp where the bare-noun
    # intro already exists; the relative-clause verb bled into the reference,
    # e.g. `second field follows`). Unambiguous finite verb (`X follows Y`), no
    # claim noun sense; clean head resolves to its Pattern-A intro. FN-guarded
    # (validate_fix silenced_legit==0). The siblings `matches`/`fails`/`intends`
    # were WITHHELD — each silenced gold-legit (`authentication data matches`,
    # `usage fraction fails`, `customer intends`): the strip resolves a reference
    # the gold treats as a real §112 defect, and the deterministic gold-corrector
    # can't verify those overnight (need a gated round + claim read). Shared
    # `_NP_CORE` → spec-support too. EPC reuses US. No CN/TW report — DR-1.
    r"follows|"
    # R20 (2026-06-25, ADR-159): batch of trailing 3sg finite verbs from the
    # normalization-asymmetry probe (relative-clause matrix verbs that bled into
    # the captured reference; the bare-noun head already has its intro). Noun-gray
    # verbs (sets/interfaces/transforms/results) EXCLUDED per the campaign's
    # noun-sense caution. FN-guard auto-narrowed the batch: occurs/sends/remains/
    # continues WITHHELD (each silenced gold-legit — e.g. `display area continues`,
    # `unlicensed spectrum occurs` — resolving references the gold treats as real
    # defects; unverifiable overnight). Shipped subset = silenced_legit==0.
    r"differs|acts|equals|obtains|enters|"
    # R21 (2026-06-26, ADR-159): long-tail batch of trailing 3sg finite verbs
    # (normalization-asymmetry probe, count>=2). Noun-gray verbs excluded a
    # priori (processes/hosts/reads/issues/changes/triggers/supplies/links).
    # FN-guard narrowed: finishes/completes WITHHELD (silenced gold-legit
    # `personal computer finishes`/`completes`). Shipped subset silenced 88
    # walker_fp / 0 legit; examiner FN-guard 0 of 2,964.
    r"accesses|schedules|displays|forwards|opens|varies|resides|"
    r"denotes|derives|mismatches|deletes|arrives|manages|displaces|succeeds|"
    r"refuses|desires|"
    # R22 (2026-06-26, ADR-159): trailing finite verbs from the report-queue
    # drain — #275 (`control circuit finds`), #287 (`first cutting grooves
    # penetrate`). `penetrate(s)` has no noun sense; `finds` noun-sense
    # (archaeological finds) is absent from claim corpora.
    r"finds|penetrate|penetrates|"
    # R23 (2026-06-26): `counts` (#276 `conversion circuit counts a coarse
    # oscillation period`) — noun-gray (bit/pulse/vote counts are real elements),
    # so a bare stop silenced a gold-legit (caught by the FN-guard in R22).
    # Lookahead-gated like `accounts(?=\s+for)`: fire ONLY when followed by an
    # article/determiner (the verb-object pattern `counts a/an/the X`); the noun
    # usage (`the bit counts.` / `counts of …`) is unaffected.
    r"counts(?=\s+(?:a|an|the)\b)|"
    # R25 (2026-06-26): `sent` (passive participle — `the dns response sent to …`)
    # and `prior` lookahead-gated to the relational `prior to` (so the `prior art`
    # noun is untouched). Both surfaced by the asymmetry probe; FN-guarded.
    r"sent|prior(?=\s+to\b)|"
    # R26 (2026-06-27, asymmetry probe): `removes` 3sg finite verb
    # (`the second direction removes …`) — no noun sense in claim diction.
    r"removes|"
    # R27 (2026-06-27, asymmetry probe): `intends`/`occurs` (pure 3sg verbs,
    # no noun sense) + lookahead-gated `matches`/`fails` (noun senses
    # `matches`/`failures` are gray, so fire ONLY in the verb-object pattern
    # `<noun> matches/fails the/a/an X` / `fails to`). FN-guarded.
    r"intends|occurs|matches(?=\s+(?:a|an|the)\b)|fails(?=\s+(?:to|a|an|the)\b)|"
    # R28 (2026-06-27, asymmetry probe): pure 3sg verbs sends/continues +
    # lookahead-gated `sets(?=\s+(?:a|an|the))` (the noun `data sets` is
    # preserved). WITHHELD: `results` (`results in` ambiguous — verb vs noun
    # `the results in the database`, 2 FNs); `remains` (interior `<nodes>
    # remains available` strips to an un-re-firing `second computing nodes`,
    # 2 FNs — US10642603B2). FN-guarded.
    r"sends|continues|sets(?=\s+(?:a|an|the)\b)|"
    # R29 (2026-06-28, asymmetry re-verify): base-form gaps left by the 3sg
    # `executes`/`reflects` already in this set — plural/coordinate subjects
    # take the base form (`the executable code execute`, `the certainty score
    # reflect`). Both are verb-only in claim diction (the nouns are
    # `execution`/`executable` and `reflection`), so no lookahead gate is
    # needed; the walker's own did-you-mean already names the clean head noun
    # (`executable code` / `certainty score`). FN-guarded.
    r"execute|reflect|"
    # R30 (2026-06-29, report #307/#308): battery/power-domain matrix verbs
    # `charges`/`discharges` over-captured into the antecedent reference
    # (`the energy storage unit selectively charges`, `the energy storage
    # module discharges`). Both have noun senses (electric charges, the
    # discharges), so they fire ONLY in the verb-coordination pattern —
    # `charges` solely before `or` (the `charges or discharges` battery
    # pair; `charges from/to the supplier/account` stays a noun),
    # `discharges` before or/to/from (rarely a noun). Never the `the
    # charges the user pays` reading. `selectively` is already an
    # _ADVERB_STOPS member so the residue strips to the clean head.
    # FN-guarded (examiner 0, corpus silenced_legit 0).
    r"charges(?=\s+or\b)|discharges(?=\s+(?:or|to|from)\b)|"
    # Issue #136 (2026-06-01): `face` is ambiguous noun/verb — legitimate
    # noun in `terminal face` / `mounting face` / `contact face` etc.
    # but clearly the matrix verb in `the first magnetic bowl face toward
    # each other` (parallel `first`/`second` + `toward each other`
    # collocation). Lookahead-gated stop (mirrors `accounts(?=\s+for)`
    # pattern below): `face` terminates NP capture ONLY when followed
    # by spatial prepositions `toward|towards|inward|outward|away|each
    # other` (verb usage). Bare `face` (noun) is unaffected.
    r"face(?=\s+(?:toward|towards|inward|outward|away|each\s+other))|"
    # R32 (2026-07-06, report #326): `drive` / `swing` over-captured into the
    # antecedent reference when a plural / coordinate subject takes the
    # base-form finite verb (`the two guiding slots respectively drive the
    # two guiding structures`; `the two swing arms swing on the side
    # surface`). Both are noun-gray — `drive` is a noun in `disk drive` /
    # `drive shaft` / `drive unit`; `swing` in `swing arm` — so a bare stop
    # is FN-unsafe. Lookahead-gated (mirrors `counts` / `face`): `drive`
    # fires ONLY in verb-object shape (followed by an object determiner),
    # `swing` ONLY before a spatial preposition (the `face` gate pattern).
    # The compound noun-modifier occurrence (`swing arm`, `drive shaft`) is
    # followed by its head noun, not the gate token, so it is untouched;
    # `respectively` between subject and verb is already an _ADVERB_STOPS
    # member. FN-guarded (examiner 0, corpus silenced_legit 0). Shared
    # `_NP_CORE` covers the spec-support extractor (cross-CHECK). EPC reuses
    # US. No CN/TW mirror (English-verb over-capture) — TW `對接` is a
    # separate interior-cut class (#330/#331).
    r"drive(?=\s+(?:a|an|the)\b)|swing(?=\s+(?:on|toward|towards|inward|outward|away)\b)|"
    # R5 (2026-05-26): `accounts` as 3sg finite verb only — lookahead on
    # `\s+for` discriminates the `<noun> accounts for X` verb-object pattern
    # (#98 alumina, #99 silica) from the bare-noun usage (`financial accounts`,
    # `accounts receivable`) which active US labels confirm exists in corpus.
    r"accounts(?=\s+for)|"
    # R33 (2026-07-13, report #374): interior verb terminator. `_STOP_WORDS` is
    # the ONLY interior cut the US NP capture has (the trailing cleaner in
    # `clean_noun_phrase` pops from the end and cannot reach a verb that has an
    # object behind it). The base form `include` was missing — only the 3sg
    # `includes` was a stop — so a plural subject ran the capture straight
    # through into the object: `wherein the reaction condition data include feed
    # temperature, feed pressure…` captured `the reaction condition data include
    # feed temperature`. FN-safe as a bare stop: `include` has no noun sense in
    # patent diction (the noun is `inclusion`). EPC reuses the US walker, so it
    # inherits this for free.
    #
    # `using` was TRIALED IN THIS ROUND AND WITHHELD (reports #357/#364). It
    # cleanly recovers `the target zone` from `the target zone using another
    # sensing data`, but validate_fix caught it silencing 2 gold-legit defects —
    # `the resection using dynamic visualization data` (US11896442B2 c16) and
    # `the language model using textual data` (US20220309089A1 c7). Those are
    # structurally IDENTICAL to #357 (`the <head> using <NP>`), so no surface
    # gate can separate them. The cut is not what fails: it exposes an intro-side
    # gap (the bare head resolves against a bare-noun intro the ensemble does not
    # accept) that the over-capture had been accidentally masking. Shipping it
    # would trade 2 real defects for the FP — an FN, which we never ship. The
    # `using` class is therefore blocked on the intro side, not here.
    r"include|"
    r"adapted|arranged|coupled|connected|mounted|disposed|storing|determining|corresponding|"
    r"extends|provides|receives|generates|produces|performs|"
    r"executes|transmits|operates|determines|defines|forms|"
    r"supports|enables|allows|causes|includes|contains|"
    r"encompasses|creates|maintains|controls|establishes|"
    r"represents|surrounds|overlaps|"
    # Additional 3sg verbs / adjectives surfaced by testspec12 optics patent
    # (and similar math/physics-heavy claims where a term is followed by a
    # verb phrase like "satisfies formula (1)" or by the adjective "close
    # to X"). Adding them to the regex stop set prevents the NP capture
    # from bleeding past the head noun into the verb/adjective clause.
    r"satisfies|crosses|corresponds|relates|close|directed|"
    r"a|an|the|said)"
)

_NP_CORE = rf"(?:(?!{_STOP_WORDS}\b){_WORD}\s+){{0,5}}(?:(?!{_STOP_WORDS}\b){_WORD})"
_NP_CAPTURE = rf"({_NP_CORE})"

_DEFINITE_REF = re.compile(
    rf"\b(?P<prefix>the|said)\s+(?P<noun>{_NP_CORE})",
    re.IGNORECASE,
)

_INDEFINITE_REF = re.compile(
    rf"\b(?:a|an)\s+{_NP_CAPTURE}",
    re.IGNORECASE,
)

# Extended introduction patterns for antecedent basis.
# Matches all standard patent element-introduction phrases:
#   a/an X, at least one/a/an X, one or more X, a plurality of X,
#   two/three/four X. Ordinals (first..tenth and beyond) are NOT consumed
#   as a prefix — they fall through to the generic ``(?:a|an)\s+`` arm and
#   are picked up by ``_NP_CORE`` as the leading word of the captured noun
#   phrase, so "a first engaging structure" yields the full phrase
#   "first engaging structure" rather than dropping the ordinal.
_INTRO_PATTERNS = re.compile(
    r"\b(?:"
    # Specific multi-word patterns first (before generic a/an)
    r"at\s+least\s+(?:one|a|an)\s+"        # at least one widget
    r"|one\s+or\s+more\s+"                  # one or more widgets
    r"|a\s+plurality\s+of\s+"              # a plurality of widgets
    r"|(?:one|two|three|four|five|six|seven|eight|nine|ten)\s+"  # five widgets
    # Generic a/an last — captures any following noun phrase, including
    # ones that begin with an ordinal (first/second/.../tenth/...)
    r"|(?:a|an)\s+"                          # a widget, a first widget, an apparatus
    r")" + _NP_CAPTURE,
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Noun phrase trailing-word cleanup
# ---------------------------------------------------------------------------

# Adverbs and patent function words — always strip from phrase end
_ADVERB_STOPS = {
    # Adverbs
    "further", "additionally", "generally", "respectively",
    "jointly", "collectively", "simultaneously", "preferably",
    "optionally", "selectively", "removably", "rotatably",
    "slidably", "pivotally", "movably", "fixedly",
    "substantially", "essentially", "approximately",
    "typically", "normally", "merely", "primarily",
    # R8 (2026-06-01): sequential / iteration adverbs surfaced by #152
    # (`phase-delayed clock signal successively approach` — `successively`
    # bled between noun head and trailing verb).
    "successively", "sequentially", "iteratively", "progressively",
    # R12 (2026-06-09): `again` is a temporal adverb that bled between the
    # noun head and a trailing infinitive in `transmit the control command
    # again to cause …` (#216/#217/#219/#220 — `control command again` →
    # `control command`). Never a noun terminus. (`also` looked like the
    # same shape but was NOT added — as an _ADVERB_STOPS member it strips on
    # the INTRO side too, spuriously introducing `players` from `players
    # also …` and legit_drifting 4 US labels; the `triple store also`
    # residue is dual-labeled instead.)
    "again",
    # Patent function words
    "thereof", "therein", "thereto", "thereby", "therefrom",
    "thereon", "therethrough", "therebetween",
    "according", "accordingly",
    "herein", "hereinafter", "hereinbefore",
    # Conjunctions/prepositions that shouldn't end a noun phrase
    "when", "where", "while", "so", "such",
}

# Universal patent verbs (appear in every technology area)
_VERB_STOPS = {
    # Be/have
    "is", "are", "was", "were", "has", "have", "had", "being",
    # Universal patent-drafting verbs (base / -s / -ed / -ing where unambiguous)
    "include", "includes", "including", "included",
    "comprise", "comprises", "comprising", "comprised",
    "consist", "consists", "consisting",
    "define", "defines", "defined", "defining",
    "provide", "provides", "provided", "providing",
    "form", "forms", "formed", "forming",
    "having",
    # Common 3rd-person present forms in patent descriptions
    "pushes", "pulls", "holds", "moves", "slides", "rotates",
    "engages", "extends", "receives", "supports", "contacts",
    "connects", "abuts", "faces", "carries", "covers",
    # #327 — base-form 'abut' (plural/coordinate subjects take the base form:
    # "two ends of the elastic member respectively abut against ..."). The 3sg
    # 'abuts' was already stopped; 'abut' has no noun sense (the noun is
    # 'abutment'), so the whole-word strip is FN-safe and symmetric.
    "abut",
    # R33 (2026-07-13, reports #362 + #375) — never-noun verb forms that
    # over-captured into the trailing position of a reference/intro:
    #   enters / re-enters — `the sensing system re-enters the offline phase`
    #     (the NP capture stops at the object determiner `the`, leaving the
    #     finite verb as the trailing token). No noun sense exists (the noun
    #     is `entry`/`entrance`), so a bare strip is FN-safe. `re-enters` is a
    #     single `_WORD` token (the pattern spans hyphens), so it needs its own
    #     entry — the `enters` entry does NOT cover it.
    #   built — irregular past participle, so it is invisible to the `-ed`
    #     heuristic in `_is_likely_past_participle` (that was the gap): the
    #     INTRO `a chemical theoretical model built by data fitting` captured
    #     `chemical theoretical model built`, which then failed to match the
    #     bare reference `the chemical theoretical model` (#375). Stripped in
    #     the TRAILING cleaner (not `_STOP_WORDS`) deliberately: the compound
    #     modifier `built-in` is one hyphenated `_WORD` token here and so is
    #     untouched, whereas a `_STOP_WORDS` entry would terminate the capture
    #     of `the built-in memory` at `built` (a real FN).
    "enters", "re-enters", "built",
    "executes", "transmits", "generates", "determines", "operates",
    "leaves", "allows", "enables", "prevents", "permits",
    "encompasses", "contains", "produces", "creates", "maintains",
    "controls", "establishes", "represents", "surrounds", "overlaps",
    # Additional 3sg verb forms observed over-capturing NP boundaries in
    # US fixtures (testspec2/3/6, test6, testspec9). Empirical denylist —
    # each form verified against the fixture that surfaced it.
    "exhibit", "exhibits", "exhibited", "exhibiting",
    "compare", "compares", "compared", "comparing",
    "apply", "applies", "applied", "applying",
    "turn", "turns", "turned", "turning",
    "stop", "stops", "stopped", "stopping",
    "multiply", "multiplies", "multiplied", "multiplying",
    # 5-char verb form below the _is_likely_third_person_verb 6-char floor.
    # Reported via issue #41: "electronic elements completely falls" captured
    # as a reference term. Adding 'falls' to the explicit denylist rather
    # than dropping the floor, to avoid catching legitimate 5-char nouns.
    "falls",
    # Modal verbs
    "must", "shall", "should", "can", "could", "may", "might", "will", "would",
}

# -ing words that are UNAMBIGUOUSLY verbs in patent context (never nouns)
_ING_VERB_ONLY = {
    "comprising", "consisting", "including", "having",
    "being", "using", "providing", "forming",
    "defining", "resulting",
}

# Known -ed words that are nouns, not participles
_ED_NOUNS = {"bed", "red", "shed", "led", "fed", "infrared", "overhead"}

# Prepositions that should not end a noun phrase
_PREPOSITION_STOPS = {
    "along", "between", "through", "within", "upon", "above", "below",
    "across", "toward", "towards", "against", "around", "during", "into",
    "onto", "over", "under", "from", "with", "without", "beside", "beneath",
    "beyond", "behind", "before", "after", "among", "about", "inside",
    "outside", "throughout", "near", "past", "until", "as", "via",
    # Directional adverb commonly used as a postpositional modifier in
    # optics/geometry claims ("extension direction away from the axis").
    # Stripping bilaterally cleans both "extension direction away" intros
    # and "the extension direction" references so they match.
    "away",
}

# Trailing conjunctions and relative pronouns
_TRAILING_FUNCTION_WORDS = {
    "and", "or", "but", "that", "which", "who", "whom", "whose",
    "where", "when", "while", "if", "so", "yet", "nor",
}

# Trailing bare cardinals — strip when the captured NP ends on a cardinal
# because the regex bled past a verb+numeral chain (e.g. "respectively
# define two"). Only applied when the phrase has additional tokens so a
# standalone "two" / "three" captured from "the two" / "the three" is
# preserved and handled elsewhere.
_TRAILING_CARDINAL_STOPS = {
    # R32 (2026-05-04): added 'one' to strip the trailing-cardinal residue
    # in over-captured noun phrases like `first message comprises one`. The
    # `len(words) > 1` guard at the strip site preserves standalone `the
    # one` references (handled by _QUANTIFIER_STOPS at the walker level).
    # Empirical: 212 walker_fp findings of shape `^.* (?:comprises|...)
    # one$` from US round-1 corpus over-captured into a verb + cardinal
    # determiner clause.
    "one",
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
}

# Quantifiers/pronouns that should NOT be flagged as standalone elements
_QUANTIFIER_STOPS = {
    "one", "another", "other", "others",
    "plurality", "remainder", "rest",
    "each", "both", "either", "neither",
    "any", "some", "all", "none",
    "former", "latter",
    "first", "second", "third", "fourth", "fifth",
    "same", "certain", "particular",
    # Hyphen prefixes (belt-and-suspenders in case regex splits them)
    "non", "pre", "sub", "bi", "multi", "semi", "co", "re",
    "inter", "intra", "over", "under", "anti", "cross", "self", "single",
}


def _is_likely_past_participle(word: str) -> bool:
    """Detect -ed words that are likely verbs/participles, not nouns."""
    if not word.endswith("ed"):
        return False
    if word in _ED_NOUNS:
        return False
    return len(word) >= 5


# Known -es words that are nouns, not 3rd-person verbs
_ES_NOUNS = {
    "devices", "interfaces", "surfaces", "instances", "sequences",
    "databases", "voltages", "packages", "images", "edges", "bridges",
    "ridges", "passages", "stages", "ranges", "changes", "charges",
    "exchanges", "resources", "sources", "forces", "services",
    "grooves", "pieces", "valves", "processes", "addresses",
    "matrices", "indices", "vertices", "appendices",
    "structures",
    "lenses", "buses", "gases", "axes", "bases", "cases",
    "phases", "cables", "tables", "modules", "nodes", "modes",
    "types", "tubes", "plates", "gates", "states", "rates",
    "wires", "cores", "pores", "stores", "frames", "names",
    "files", "tiles", "holes", "poles", "roles", "rules",
    "lines", "zones", "tones", "sides", "guides", "codes",
    "diodes", "anodes", "cathodes", "electrodes",
}


def _is_likely_third_person_verb(word: str) -> bool:
    """Detect -s/-es words that are likely 3rd-person present verbs, not nouns."""
    if len(word) < 6:
        return False
    if word in _ES_NOUNS:
        return False
    verb_suffixes = ('ates', 'izes', 'ifies', 'ects', 'uces', 'ases', 'oses',
                     'ures', 'ises', 'ples', 'bles', 'ades', 'odes', 'udes',
                     'eases',
                     # Commit 9d: catch verbs like 'subtracts' (-cts),
                     # 'accepts' (-pts), 'converts' (-rts), 'consists' (-sts).
                     'cts', 'pts', 'rts', 'sts',
                     # Commit 10b: catch 'outputs' (-uts). Surfaced by the
                     # testspec5 browser smoke test where claim 2 captured
                     # 'the surge detection driver circuit outputs' as a
                     # reference term. Other gaps (-its, -rns, -ops, -ies)
                     # deferred to Phase 9.
                     'uts')
    return any(word.endswith(s) for s in verb_suffixes)


# Tokens that, when sitting immediately before a -uts word, mean the
# -uts word is the head noun and must NOT be stripped. Articles and
# the prepositional 'of' are the load-bearing cases ('the outputs',
# 'plurality of inputs'). See the guard in clean_noun_phrase.
_UTS_GUARD_PRECEDERS = {"the", "a", "an", "said", "of"}

# -ly words that are nouns in patent context. Trailing -ly adverbs are
# stripped unless the word is in this allowlist.
_LY_NOUN_ALLOWLIST = {
    "supply", "assembly", "family", "anomaly", "reply", "ally", "rally",
    "subassembly", "resupply",
}


# Trailing distributive quantifiers ("the four unit regions each",
# "the groups each having X") — these are post-modifier quantifiers, not part
# of the noun phrase. Stripping them bilaterally (intro + reference) dedups
# distributive references against plain plural intros.
_DISTRIBUTIVE_QUANTIFIERS = frozenset({"each", "both", "all", "every"})


def _is_trailing_distributive(word: str) -> bool:
    return word in _DISTRIBUTIVE_QUANTIFIERS


# Trailing arithmetic operators ("the current duty cycle minus an adjusted …",
# "the first value plus …"). These are math operators / prepositions, not part
# of the NP head. `over` omitted — commonly a spatial preposition in claims
# ("the layer over the substrate").
_ARITHMETIC_OPERATORS = frozenset({"minus", "plus", "times", "divided", "modulo", "mod"})


def _is_trailing_arithmetic(word: str) -> bool:
    return word in _ARITHMETIC_OPERATORS


# Relational / positional adjectives that typically head a predicative phrase
# ("the X opposite to Y", "the X relative to Z", "the X adjacent to W") rather
# than belonging to the noun phrase itself. Strip only when trailing; leading
# or internal uses ("an opposite surface", "a lateral region") are preserved
# because clean_noun_phrase walks from the end and stops at the first word
# that survives the denylist. Applies to US-only; CJK walkers use different
# tokenization and would need a separate denylist if this class of bug
# surfaces there.
_RELATIONAL_ADJ_STOPS = frozenset({
    "opposite", "opposing",
    "relative", "relatively",
    "adjacent", "adjoining",
    "parallel", "perpendicular", "orthogonal", "oblique",
    "concentric", "collinear", "coaxial",
    "similar", "identical", "equal", "equivalent",
    "proximate", "distal", "proximal", "medial", "lateral",
    "closer", "nearer", "farther",
    # R24 (2026-06-26, ADR-159): post-nominal adjectives in reduced relative
    # clauses that bled into the captured reference (`the transceiver different
    # from …`, `the engine resident in …`, `the spool means movable to …`) — the
    # bare-noun head already has its intro. Surfaced by the normalization-asymmetry
    # probe; FN-guarded by validate_fix. None is a noun head. `prior` (prior art) /
    # `used` (legit labels) / `also`/`only` (intro-side strip) deliberately held.
    "different", "separate", "subsequent", "resident",
    "configurable", "movable", "moveable", "extendable", "installable",
})


def _is_trailing_relational_adj(word: str) -> bool:
    return word in _RELATIONAL_ADJ_STOPS


# Predicative post-nominal adjectives — they sit after the head noun as a
# reduced relative clause taking a preposition ("a first signal INDICATIVE of
# X", "a product OPERABLE to Y", "a circuit RESPONSIVE to Z"). The intro
# extractor over-captures them onto the noun ("first signal indicative") so a
# later "the first signal" no longer matches → false positive (ADR-159
# missed_introduction class; suggested_match='first signal indicative'). Strip
# ONLY when trailing AFTER a head noun — clean_noun_phrase walks from the end
# and a single-word NP falls back to the original, so a bare noun use is
# preserved. Curated to clearly-adjectival -ive/-ble forms (never head nouns in
# the trailing position); the corpus FN-guard (silenced_legit==0) gates this.
# US-only (CJK walkers tokenize differently).
_POST_NOMINAL_PREDICATIVE_ADJ = frozenset({
    # DR-1: only the forms empirically driving corpus FPs + their unambiguous
    # -ive/-ble cousins. The broader set (representative/characteristic/
    # accessible/…) over-generalised intros and the corpus FN-guard caught it
    # silencing 8 real `legit` defects — kept out. These remaining words are
    # never head nouns in the trailing position.
    "indicative", "operable", "responsive",
    # R26 (2026-06-27, asymmetry probe): `conditional` (-al) — post-nominal
    # predicative adjective never used as a head noun in the trailing position
    # (`trace enabler conditional`). `operative` WITHHELD — the FN-guard caught
    # it silencing 2 gold-legit (`amplifier unit operative to amplify`, the
    # functional `operative to <verb>` clause that carries intro semantics like
    # `configured to`). FN-guarded (silenced_legit==0).
    "conditional",
})


def _is_trailing_predicative_adj(word: str) -> bool:
    return word in _POST_NOMINAL_PREDICATIVE_ADJ


def _is_trailing_ly_adverb(word: str) -> bool:
    """Detect -ly adverbs that terminate over-captured NPs.

    Patent intro / reference captures routinely bleed past a noun into an
    adverb+participle post-modifier ("a microphone electrically connected to
    …"). The `_STOP_WORDS` regex stops at the participle ("connected") but
    leaves the -ly adverb attached to the noun. Strip when trailing.
    """
    if len(word) < 5 or not word.endswith("ly"):
        return False
    if word in _LY_NOUN_ALLOWLIST:
        return False
    return True


# Known -ing words that are legitimate nouns in patent context
_ING_NOUNS = {
    "ring", "spring", "string", "wiring", "bearing", "housing",
    "coating", "opening", "coupling", "mounting", "casing", "tubing",
    "spacing", "sealing", "shielding", "plating", "grounding",
    "bonding", "molding", "shaping", "imaging", "computing",
    "processing", "printing", "recording", "building", "ceiling",
    "setting", "fitting", "cutting", "routing", "lighting",
    "padding", "mapping", "logging", "binding", "lining",
    "timing", "rating", "loading", "testing",
}


def _should_strip_trailing(word: str) -> bool:
    w = word.lower().rstrip(".,;:")
    if (
        w in _ADVERB_STOPS
        or w in _VERB_STOPS
        or w in _ING_VERB_ONLY
        or w in _PREPOSITION_STOPS
        or w in _TRAILING_FUNCTION_WORDS
        or _is_likely_past_participle(w)
        or _is_likely_third_person_verb(w)
        or _is_trailing_ly_adverb(w)
        or _is_trailing_distributive(w)
        or _is_trailing_arithmetic(w)
        or _is_trailing_relational_adj(w)
        or _is_trailing_predicative_adj(w)
    ):
        return True
    # Strip trailing -ing verbs/gerunds (mirrors single-word rejection at clean_noun_phrase)
    if w.endswith("ing") and len(w) >= 6 and w not in _ING_NOUNS:
        return True
    return False


# Contextual verb stops: words that are ambiguous between noun and verb use
# (irregular past participles like `output`/`input`; verb/plural-noun pairs
# like `range`/`ranges`). Strip from the trailing position of a captured NP
# only when the source-text token immediately following the span is in the
# complement set — that signals verb use ("the signals output TO the driver",
# "the agent ranges FROM X to Y"). Plain "the outputs" / "the temperature
# ranges" (no following complement) keeps the head noun.
_CONTEXTUAL_VERB_STOPS = {
    "output":  frozenset({"to", "from", "by", "with", "via", "on", "into", "onto", "toward", "towards"}),
    "input":   frozenset({"to", "from", "by", "with", "via", "on", "into", "onto"}),
    # R33 (2026-07-13, reports #362/#363): `scans` / `monitors` as 3sg finite
    # verbs (`the first sensing apparatus scans the target zone`; `the sensing
    # system monitors the target zone in real time`). Both are genuinely
    # noun-gray — `scans` is a noun in `the CT scans`, `monitors` in `the
    # display monitors` — so a bare `_VERB_STOPS` entry would be FN-unsafe.
    # Gated on a following object determiner, which is the verb-object shape:
    # the plural-noun reading is followed by a predicate (`the monitors are
    # coupled…`), never by `a`/`an`/`the`. Same gate as R32's `drive`.
    # (`_is_likely_third_person_verb` cannot reach either: `scans` is below its
    # 6-char floor, and `-ors` is not one of its verb suffixes.)
    "scans":    frozenset({"a", "an", "the"}),
    "monitors": frozenset({"a", "an", "the"}),
    # R34 (2026-07-18, reports #391 + #397): same 3sg/base-form finite-verb
    # shape as R33, gated identically on a following object determiner.
    #   sandwich — `the third die and the first die sandwich the first
    #     sandwiching portion` (#391). Noun-gray: `a die sandwich` is a real
    #     stacked structure, so a bare `_VERB_STOPS` entry would be FN-unsafe.
    #     The noun reading is always followed by a predicate, never by
    #     `a`/`an`/`the`.
    #   join — `to make one of the ports closely join the other of the ports`
    #     (#397). Noun-gray in software claims (`the join operation`, `the
    #     join between the two tables`), where the following token is a noun
    #     or preposition — never a bare object determiner.
    "sandwich": frozenset({"a", "an", "the"}),
    "join":     frozenset({"a", "an", "the"}),
    # R36 (2026-07-22, private-tracker reports #427 + #409/#410): two more
    # base/3sg finite verbs that over-captured into the trailing position of a
    # REFERENCE noun phrase, gated identically on a following object determiner.
    #   face — `the first active surface and the second active surface face the
    #     lead frame` (#427). Genuinely noun-gray: `the mounting face`, `the
    #     die face` are real element names, so a bare `_VERB_STOPS` entry would
    #     be FN-unsafe. In the noun reading the trailing token is `of` / a
    #     predicate / punctuation — never a bare object determiner, so the
    #     `a`/`an`/`the` gate is disjoint. (The 3sg `faces` is already an
    #     unconditional `_VERB_STOPS` entry; base-form `face` takes a plural /
    #     coordinate subject — `surface A and surface B face C` — exactly the
    #     `abut` situation from #327.)
    #   pre-charges — `the inductor pre-charges the flying capacitor module`
    #     (#410); `the flying capacitor pre-charging method pre-charges the …`
    #     (#409). Hyphenated 3sg verb: `_is_likely_third_person_verb` misses it
    #     (its base `charges` is in `_ES_NOUNS`, and `-rges` is not a verb
    #     suffix), so it needs an explicit entry. Noun-gray (`the pre-charges of
    #     the capacitors` is a plural noun), hence the determiner gate — the
    #     noun reading is followed by `of`, never by `a`/`an`/`the`.
    "face":        frozenset({"a", "an", "the"}),
    "pre-charges": frozenset({"a", "an", "the"}),
    "range":   frozenset({"from", "between", "to", "over", "in", "through"}),
    "ranges":  frozenset({"from", "between", "to", "over", "in", "through"}),
    "ranged":  frozenset({"from", "between", "to", "over", "in", "through"}),
    "ranging": frozenset({"from", "between", "to", "over", "in", "through"}),
}

_NEXT_WORD_RE = re.compile(r"\s*([A-Za-z][A-Za-z'\u2019-]*)")
_NEXT_TWO_WORDS_RE = re.compile(
    r"\s*([A-Za-z][A-Za-z'\u2019-]*)\s+([A-Za-z][A-Za-z'\u2019-]*)"
)

# R34 (2026-07-18, reports #386/#401): two-token contextual verb stops. A
# handful of noun-gray verbs take a PREPOSITIONAL object rather than a bare
# determiner, so the one-token gate above cannot reach them \u2014 but gating on
# the bare preposition alone would be FN-unsafe.
#
# R35 (2026-07-20, reports #386/#401) — `switches` as a 3sg finite verb
# (`the selection line switches to the channel`). This was WITHHELD across
# three sessions with the note "queued until the examiner FN-guard is
# runnable", because the US examiner ground truth carries TWO confirmed
# §112(b) rejections whose term is the plural NOUN `switches`
# (`the main switches` — app 18599360; `the semi-conductor switches` —
# app 18573531), and a term-level check cannot clear them.
#
# UNBLOCKED. Both applications' claim text was pulled from EdgeXpert and read
# directly, and the feared collision does not occur:
#   18599360  "...adjust the switching instants of the main switches TO CONTROL
#             the commutation-induced current difference..."   -> `to control`,
#             an infinitive, NOT a determiner.
#   18573531  "...the semi-conductor switches ARE DESIGNED as GaN power
#             switches..."                                     -> no `switches
#             to` construction anywhere in the claims.
# So the two-token `to the` / `to a` / `to an` gate is provably disjoint from
# both. The standing worry (`the main switches to the load`, a noun+PP reading
# indistinguishable under fixed-width lookahead) is real in the abstract but
# has ZERO instances in the authoritative ground truth — which is exactly the
# question only the DB could answer, and why the class waited for it.
#
# Verified with tests/eval/examiner_fn_guard.py (new this round): recalled
# examiner-confirmed terms 1347 -> 1347, LOST 0 of 1347.
#
# This is the FIRST use of the two-word mechanism. `_CONTEXTUAL_VERB_STOPS_2W`
# was built empty in R34 in anticipation of precisely this case; the consumer
# below was already wired.
_CONTEXTUAL_VERB_STOPS_2W: dict[str, frozenset[str]] = {
    "switches": frozenset({"to the", "to a", "to an"}),
}


def strip_contextual_verb(term: str, following_text: str) -> str:
    """Strip a trailing ambiguous verb form when following text confirms verb use.

    ``following_text`` is the source text immediately after the captured span.
    """
    if not term:
        return term
    words = term.split()
    if not words:
        return term
    last = words[-1].lower().rstrip(".,;:")
    complements = _CONTEXTUAL_VERB_STOPS.get(last)
    if complements:
        m = _NEXT_WORD_RE.match(following_text)
        if m and m.group(1).lower() in complements:
            return " ".join(words[:-1])
        return term
    complements_2w = _CONTEXTUAL_VERB_STOPS_2W.get(last)
    if complements_2w:
        m2 = _NEXT_TWO_WORDS_RE.match(following_text)
        if m2 and f"{m2.group(1).lower()} {m2.group(2).lower()}" in complements_2w:
            return " ".join(words[:-1])
    return term


# R34 (2026-07-18, report #397): manner adverbs that over-captured into the
# trailing position of a REFERENCE noun phrase once the finite verb they
# modify was stripped (`the ports closely join the other \u2026` \u2192 `ports closely`
# after the `join` stop fires). A trailing `-ly` adverb is never a noun head,
# but a blanket `-ly` suffix test is NOT safe \u2014 `assembly`, `supply`, `poly`
# and `anomaly` are real patent nouns. Hence an explicit curated set of the
# manner adverbs that actually occur in claim predicates.
#
# Reference-side ONLY (never in `clean_noun_phrase`), following the WS-A3
# precedent: an intro-side strip could generalize an introduction and mask a
# real \u00a7112(b) defect, whereas a reference-side strip can only ever relax the
# match for the reference that already over-captured.
_TRAILING_ADVERB_STOPS = frozenset({
    "closely", "directly", "indirectly", "fixedly", "slidably", "rotatably",
    "pivotally", "movably", "removably", "detachably", "electrically",
    "mechanically", "thermally", "optically", "operatively", "operably",
    "communicatively", "respectively", "selectively", "sequentially",
    "simultaneously", "partially", "completely", "substantially",
    # NOT `further`: it is a focus particle, not a manner adverb, and in
    # `the generating further comprises …` it heads the claim-transition
    # idiom rather than over-capturing. Measured on the US corpus it ends
    # ZERO FPs and merely re-keys 31 gerund-process-step findings from
    # `generating further` to `generating` — churn that would need ADR-111
    # dual-labeling for no precision gain, and that collides with the
    # DEFERRED R33-gerund class (#336/#337). DR-1: no report evidences it.
})


def strip_trailing_adverb(term: str) -> str:
    """Strip a trailing manner adverb from an over-captured reference phrase.

    Requires at least one remaining token so a standalone adverb capture is
    left untouched for the existing short-residual guards to reject.
    """
    if not term:
        return term
    words = term.split()
    while len(words) > 1 and words[-1].lower().rstrip(".,;:") in _TRAILING_ADVERB_STOPS:
        words = words[:-1]
    return " ".join(words)


_VARIABLE_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9]?'?$")


def _is_trailing_variable_identifier(word: str, prev_word: str | None) -> bool:
    """Detect 1-2 char trailing tokens that are math/physics variable names.

    In lowercased claim text, tokens like ``vd`` (from ``Vd``), ``dz``
    (``Dz``), ``so`` (``So``), or ``p`` / ``p'`` tacked onto the end of a
    noun phrase are variable identifiers rather than part of the noun. Only
    strip when the preceding token is a substantive noun, not an article or
    preposition that would make the short token the actual head.
    """
    if not _VARIABLE_IDENTIFIER_RE.match(word):
        return False
    if prev_word is None:
        return False
    if prev_word.lower() in _UTS_GUARD_PRECEDERS:
        return False
    return True


# Closed set of comparative words that precede `than` in a comparative clause.
# Used ONLY when the term ends in `than` (see _strip_comparative_tail), so these
# are removed strictly in the comparative context — a noun ending in "-er"
# (layer/member/container) is never in this set, and `other`/`greater` survive
# in non-comparative positions ("the other end", "the greater portion").
_COMPARATIVE_TRAILING = frozenset({
    "other", "greater", "less", "lesser", "more", "fewer", "larger", "smaller",
    "wider", "narrower", "higher", "lower", "longer", "shorter", "bigger",
    "thinner", "thicker", "deeper", "shallower", "closer", "farther", "further",
    "stronger", "weaker", "faster", "slower", "heavier", "lighter", "denser",
    "broader", "finer", "coarser", "rather", "better", "worse", "cooler",
    "warmer", "hotter", "colder", "brighter", "darker", "greater", "nearer",
    "later", "earlier", "sooner", "younger", "older", "fewer", "slimmer",
})

_COMPARATIVE_COPULA = frozenset({
    "is", "are", "be", "being", "becomes", "become", "that", "which", "no",
})


def _strip_comparative_tail(words: list[str]) -> list[str]:
    """Strip a trailing comparative clause when the phrase ends in `than`.

    `than` always introduces a comparative complement, so a captured NP that
    ends in `than` over-ran the head noun. Drop `than`, then a preceding
    closed-set comparative / `other`, then any copula remnant. Requiring `than`
    as the final token keeps non-comparative uses intact.
    """
    if not words or words[-1].lower().rstrip(".,;:") != "than":
        return words
    out = words[:-1]
    if out and out[-1].lower().rstrip(".,;:") in _COMPARATIVE_TRAILING:
        out = out[:-1]
        while out and out[-1].lower().rstrip(".,;:") in _COMPARATIVE_COPULA:
            out = out[:-1]
    return out if out else words


def clean_noun_phrase(phrase: str) -> str:
    """Strip trailing verbs, adverbs, and function words from a noun phrase."""
    words = phrase.strip().split()
    # NOTE: the comparative-tail strip (_strip_comparative_tail) is deliberately
    # NOT applied here — clean_noun_phrase cleans BOTH references and intros, and
    # stripping `… larger than` from an INTRO (`an inner diameter larger than the
    # inner diameters …`) creates a too-general intro that spuriously resolves an
    # unrelated plural reference (a real FN; US7811436B2 c18). The comparative
    # strip is applied REFERENCE-side only, at the _DEFINITE_REF site in claims.py.
    # Strip a trailing 1-2 char variable identifier ("viewing distance vd",
    # "physical distance dz"). Applied once before the generic trailing-word
    # loop so subsequent rules see the cleaned tail.
    if len(words) >= 2:
        last = words[-1].rstrip(".,;:")
        prev = words[-2].rstrip(".,;:")
        if _is_trailing_variable_identifier(last, prev):
            words.pop()
    while words:
        last = words[-1].lower().rstrip(".,;:")
        # Trailing bare cardinal ("respectively define two") — strip only
        # when the phrase has other tokens, so standalone "two" captured
        # from "the two" survives to be handled by the walker's quantifier
        # stop-list.
        if last in _TRAILING_CARDINAL_STOPS and len(words) > 1:
            words.pop()
            continue
        if not _should_strip_trailing(words[-1]):
            break
        # Guard for the -uts suffix: 'inputs' / 'outputs' are ambiguous
        # between verb ('the circuit outputs the signal') and plural noun
        # ('the inputs', 'plurality of outputs'). The general suffix rule
        # cannot tell them apart, so apply this disambiguator: only strip
        # the -uts word when popping would leave a real noun behind. If
        # the remaining phrase would end on an article or preposition,
        # the -uts word IS the head noun — keep it.
        candidate = words[-1].lower().rstrip(".,;:")
        if candidate.endswith("uts") and len(words) >= 2:
            prev = words[-2].lower().rstrip(".,;:")
            if prev in _UTS_GUARD_PRECEDERS:
                break
        if candidate.endswith("uts") and len(words) < 2:
            # Standalone 'outputs' / 'inputs' is also a head noun, not a verb.
            break
        words.pop()
    # Strip possessives: "device's" → "device", "users'" → "users"
    words = [w.replace("\u2019s", "").replace("'s", "").rstrip("\u2019'") for w in words]
    # Remove any tokens that became empty after stripping
    words = [w for w in words if w]
    result = " ".join(words) if words else phrase
    # Reject single-word results that are likely verbs/adjectives, not nouns
    if len(result.split()) == 1:
        w = result.lower().rstrip(".,;:")
        if w in _ING_VERB_ONLY:
            return ""
        if w.endswith("ing") and len(w) >= 6 and w not in _ING_NOUNS:
            return ""
    return result


# Abbreviation pattern: "full term (ABBREV) trailing_noun"
_ABBREVIATION_PATTERN = re.compile(
    r"\b(?:[a-z][\w-]*\s+){1,5}"    # 1-5 words before abbreviation
    r"\(([A-Z]{2,}s?)\)\s*"         # (ABBREV) — 2+ uppercase letters, optional
                                     # plural `s` (`(OIDs)`, `(CSSDs)`) so the
                                     # pluralized acronym `the oids` resolves
    r"(\w+)?",                        # optional trailing noun
)


def extract_abbreviation_intros(text: str) -> list[str]:
    """Extract abbreviated forms from parenthetical abbreviation patterns.

    E.g., "alternating current (AC) source" → "ac source"
    """
    results: list[str] = []
    for m in _ABBREVIATION_PATTERN.finditer(text):
        abbrev = m.group(1).lower()
        trailing = m.group(2)
        if trailing:
            results.append(f"{abbrev} {trailing.lower()}")
        results.append(abbrev)
    return results


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------


# List-context introduction extraction.
#
# Patents commonly drop articles for the second-and-later items of a list:
#   "comprising a base, pivot, and arm"
#   "includes a base; pivot; and arm"
#   "selected from the group consisting of methanol, ethanol, and propanol"
# The bare nouns ('pivot', 'arm', 'ethanol', 'propanol') are introductions
# but the existing _INTRO_PATTERNS regex requires an article prefix and
# misses them. We capture the run after a list-context trigger word, then
# split on commas/semicolons/and/or to recover each list item.
#
# Extraction is *gated* on a list-context trigger so arbitrary commas
# elsewhere in claim text do not produce noise.
_LIST_CONTEXT_PATTERN = re.compile(
    r"\b(?:"
    r"includes?"
    r"|including"
    r"|comprises?"
    r"|comprising"
    r"|consisting(?:\s+essentially)?\s+of"
    r"|selected\s+from(?:\s+the\s+group(?:\s+consisting\s+of)?)?"
    # R6 (2026-05-26, missed triage on #98/#99): Markush enumeration
    # `(at\s+least\s+)?one\s+of A, B, and C` — claim 1 of the silicon-
    # carbide composite case introduces `alumina`/`silica` via the closed
    # Markush list `at least one of silicon carbide, alumina, and silica`.
    # Without this trigger, the list items are not registered as intros
    # and downstream `the alumina` / `the silica` references flag.
    r"|(?:at\s+least\s+)?one\s+(?:or\s+more\s+)?of"
    r")\s*:?\s*"
    # R48 (2026-05-04): bumped trailing `\s+` to `\s*` to accept the
    # PDF-collapse `comprising:(a) <gerund-step>` shape where the
    # space between `:` and `(a)` was dropped. Pre-fix, the entire
    # list-context match failed and bare-noun-from-method-step
    # extraction missed all gerund-led intros. Audited 7 over-strict
    # judge protect:true labels (US12562966B2 c21-76 + US20230189199A1
    # c4) — verified each has a gerund-step bare-noun intro in the
    # SAME claim that this relax surfaces; demoted as
    # walker_fp.over_strict_judge_label in the labels file.
    r"(?P<list>(?:(?!\bwherein\b)[^.])+)",
    re.IGNORECASE | re.DOTALL,
)

_LIST_ITEM_SPLIT = re.compile(r"[,;]|\s+and\s+|\s+or\s+", re.IGNORECASE)
# Semicolon-dominant lists (multi-line "comprising:" / "includes:" blocks)
# split on ``;`` only, so internal commas/"and" inside a single item do not
# fragment the item (e.g. "X connected to A, B, and C" stays one item).
_SEMICOLON_SPLIT = re.compile(r";")
# R36 (2026-05-04): also strip `and<word>` (PDF whitespace collapse) so
# items like `andprocessing logic` parse as bare-noun intro `processing
# logic`. Per PDF-extract diagnostic on US round-1 corpus, `and<word>`
# collapse occurs 2982 times; top: `andwherein` 532 / `anddetermining`
# 183 / `andsaid` 113 — fixing it inside the list-context split is safe
# because `and` is always a list conjunction in that scope (never the
# proper-name `Andrew` etc.).
_LEADING_AND = re.compile(r"^\s*and(?:\s+|(?=[a-z]))", re.IGNORECASE)
# Only ``a``/``an`` are stripped — list items starting with ``the`` are
# back-references, not introductions, and must not be re-registered.
_LEADING_ARTICLE = re.compile(r"^(?:a|an)\s+", re.IGNORECASE)
_LIST_CONTEXT_BREAKER = re.compile(r"\bwherein\b", re.IGNORECASE)


# R45 (2026-05-04): method-step bare-noun intro extraction. Process
# claims commonly introduce elements via gerund-led method steps with
# explicit (a)/(b)/(1) step labels:
#   `comprising:(a) isolating lipoprotein particles from a biological sample`
# Pattern A doesn't match (no `a` before `lipoprotein particles`); the
# bare-noun list extraction misses because the item starts with a
# gerund, not a noun.
#
# Narrow gate: REQUIRE the explicit step label `(a)`/`(b)`/`(1)` at the
# start (filters out arbitrary gerund text); REQUIRE a known stop word
# (from/via/in/on/by/at/to/for/with/of/using/wherein/;) immediately
# after the captured noun phrase (anchors the extraction); cap noun
# phrase length at 5 words.
_METHOD_STEP_BARE_NOUN_RE = re.compile(
    r'[\(\[]\s*[a-z0-9]+\s*[\)\]]\s*'           # step label (a) (b) (1) etc.
    r'(?:[a-z]+(?:ing|ed))\s+'                   # gerund or past participle
    r'((?:[a-z][\w\-]*\s+){0,4}[a-z][\w\-]*)'   # 1-5 word noun phrase
    r'(?=\s+(?:from|via|in|on|by|at|to|for|with|of|using|wherein|so|when|while|;)\b)',
    re.IGNORECASE,
)


def extract_method_step_intros(text: str) -> list[str]:
    """Extract bare-noun intros from method-step gerund constructions.

    Pattern: `(label) <gerund> <bare-noun> <stop-word>`. Used as a
    supplementary intro source for process-claim element introduction
    in method steps that lack the standard `a/an X` form.
    """
    refs: list[str] = []
    for m in _METHOD_STEP_BARE_NOUN_RE.finditer(text):
        cleaned = clean_noun_phrase(m.group(1).strip())
        if cleaned and len(cleaned) >= 4:
            refs.append(cleaned)
    return refs


# R35 (2026-07-20, reports #336/#337) — the GERUND ITSELF as an intro.
#
# `extract_method_step_intros` above registers the gerund's OBJECT
# (`bonding a first die` -> `first die`). It does not register the gerund, so a
# later `wherein the bonding is metal-to-metal direct bonding` had no
# antecedent and fired. The drafter DID introduce it: the method step
# `bonding a first die to a second die` names the act.
#
# THIS CLASS WAS BLOCKED FOR THREE SESSIONS on the examiner FN-guard, because
# `us_examiner_legit.json` carries 24 single-word gerund terms that a
# TERM-level check cannot clear — and, importantly, several are ordinary -ing
# NOUNS rather than process gerunds: `the housing` (x3), `the opening` (x2),
# `the winding`, `the beginning`, `the remaining`. Registering an intro for
# those from an unrelated gerund use would silence a real examiner rejection.
#
# MEASURED against all 24, using the actual EdgeXpert claim text: only 2
# (`the punching`, `the mining`) have ANY gerund+object use at all, and
# NEITHER is in method-step position, so the step-headed gate reaches 0 of 24.
# Confirmed end to end by tests/eval/examiner_fn_guard.py: recalled
# examiner-confirmed terms unchanged, LOST 0.
#
# The gate is deliberately the METHOD-STEP position, not a bare -ing test:
#   * step-headed  `; bonding a first die to ...`      -> intro (the act is named)
#   * mid-clause   `a chamber housing the components`  -> NOT an intro
# The second shape is the one that would endanger `the housing` / `the opening`,
# and it is exactly what the position gate excludes. This also keeps clear of
# the standing protect:true label US20240185203A1 c1 `the information`, which
# is a real defect on the gerund's OBJECT (`collecting information`) — this
# extractor never registers the object, only the head.
_GERUND_HEAD_STEP_RE = re.compile(
    r'(?:^|[;:]\s*|comprising\s*:?\s*|[\(\[]\s*[a-z0-9]+\s*[\)\]]\s*)'
    r'([a-z][\w\-]*ing)\s+'                      # the gerund heading the step
    r'(?:a|an|the|at\s+least)\b',                # taking an explicit object
    re.IGNORECASE,
)

# -ing words that are ordinary nouns or non-eventive, so naming one in step
# position still does not introduce an "act". Kept tight and evidence-driven:
# every member is attested as an examiner-rejected NOUN term in
# us_examiner_legit.json, so excluding them can only ever preserve a real
# defect, never create one.
_NON_EVENTIVE_ING = frozenset({
    "housing", "opening", "winding", "beginning", "remaining", "sliding",
    "casing", "coating", "spring", "bearing", "ring", "string", "wiring",
    "tubing", "packaging", "building",
})


def extract_gerund_head_intros(text: str) -> list[str]:
    """Register a method-step gerund head as an introduction of the act.

    Position-gated (step-initial only) and filtered against -ing words that
    are ordinary nouns. See the block comment above for the measurement that
    unblocked this against real USPTO examiner ground truth.
    """
    refs: list[str] = []
    for m in _GERUND_HEAD_STEP_RE.finditer(text):
        g = m.group(1).lower()
        if g in _NON_EVENTIVE_ING:
            continue
        # Deliberately NOT run through clean_noun_phrase: that helper's job is
        # to STRIP verbs, and it reduces most gerunds to the empty string
        # (heating/cooling/curing/mating/sensing/filling all -> ''), which
        # would leave this extractor silently inert except for the handful of
        # gerunds absent from the verb-stop list. Here the gerund IS the term.
        if len(g) >= 4:
            refs.append(g)
    return refs


# R47 (2026-05-04): `having <bare-noun> <past-participle>` intro
# extraction. US round-1 corpus has 94 occurrences of this pattern
# in apparatus claims like:
#   `having program instructions stored thereon`
#   `having unique identification data stored on`
#   `having a slot defined by`
# The participle (stored/configured/coupled/etc.) is the disambiguating
# signal that <bare-noun> is being introduced as a claim element with
# a structural attribute.
_HAVING_BARE_NOUN_RE = re.compile(
    r'\bhaving\s+'
    r'((?:[a-z][\w\-]*\s+){0,4}[a-z][\w\-]*)'   # 1-5 word noun phrase
    r'\s+(?:stored|configured|arranged|positioned|coupled|connected|disposed|operable|adapted|defined|formed|integrated|attached|mounted)\b',
    re.IGNORECASE,
)


def extract_having_bare_noun_intros(text: str) -> list[str]:
    """Extract bare-noun intros from `having X <past-participle>`.

    Catches apparatus-claim element introductions where the drafter
    uses a structural-attribute participle phrase (`having X stored`,
    `having X configured`) instead of the standard `a/an X` form.
    """
    refs: list[str] = []
    for m in _HAVING_BARE_NOUN_RE.finditer(text):
        cleaned = clean_noun_phrase(m.group(1).strip())
        if cleaned and len(cleaned) >= 4:
            # Drop spurious captures like 'been' / 'a slot' (already
            # covered by Pattern A) — keep multi-word noun phrases.
            words = cleaned.split()
            if len(words) == 1 and words[0] in {'been', 'said', 'the'}:
                continue
            refs.append(cleaned)
    return refs


def extract_bare_noun_intros(text: str) -> list[str]:
    """Extract introductions from bare-noun list contexts.

    Three patterns previously missed by ``_INTRO_PATTERNS``:

    1. Semicolon-separated bare-noun lists::

           "the assembly includes a base; pivot; and arm"

       ``pivot`` and ``arm`` are bare nouns following an established list
       separator and inherit introduction status.

    2. Comma-separated preamble lists::

           "An apparatus comprising base, pivot, and arm"

       Same shape, comma instead of semicolon, no leading article on
       second-and-later items.

    3. Markush group members::

           "selected from the group consisting of methanol, ethanol, and propanol"

       Each chemical name is an introduction. The bare ``group`` itself
       should not be flagged as missing an antecedent — that false-positive
       is handled at the walker level in commit 9b.

    The captured run is truncated at ``wherein`` so wherein-clauses do not
    bleed into the list. Items are then split on ``,``/``;``/``and``/``or``,
    article-stripped, and run through ``clean_noun_phrase``.
    """
    refs: list[str] = []
    for m in _LIST_CONTEXT_PATTERN.finditer(text):
        list_text = m.group("list")
        breaker = _LIST_CONTEXT_BREAKER.search(list_text)
        if breaker:
            list_text = list_text[: breaker.start()]
        # Pick the list separator. When semicolons are present the list
        # is a semicolon-dominant enumeration where a single item can
        # contain internal commas and "and" ("X connected to A, B, and
        # C"), so splitting on commas/and would mis-fragment items and
        # surface back-references like "the <X>" as false intros. Fall
        # back to comma/and/or only for pure-comma lists (Markush groups
        # and single-line "comprising a, b, and c" preambles).
        if ";" in list_text:
            raw_items = _SEMICOLON_SPLIT.split(list_text)
        else:
            raw_items = _LIST_ITEM_SPLIT.split(list_text)
        for raw in raw_items:
            item = _LEADING_AND.sub("", raw.strip()).strip()
            if not item:
                continue
            item = _LEADING_ARTICLE.sub("", item).strip()
            # Reduce each item to its head NP via the core NP pattern so
            # multi-line list items like "polyurethane microparticles
            # having a glass transition temperature of 40°C" collapse to
            # "polyurethane microparticles" (stops at the post-modifier
            # "having"). Items whose first token is a stop word (e.g.
            # "when the impermeable medium contains...") produce no NP
            # match and are skipped.
            np_match = re.match(rf"\s*({_NP_CORE})", item, re.IGNORECASE)
            if not np_match:
                continue
            cleaned = clean_noun_phrase(np_match.group(1).strip())
            if cleaned:
                refs.append(cleaned.lower())
    return refs


_DEFINITE_PRECEDER = re.compile(r"(?:\bthe|\bsaid)\s+$", re.IGNORECASE)


# Self-definition pattern: "the <NP> [optional 1-2 char identifier] is
# (a|an) <definition>". Equation-heavy / math-variable claims use this
# construction to introduce a named quantity together with its symbol
# (e.g. "the equivalent object distance So is a distance calculated by…",
# "the physical distance Dz is an actual distance from…"). The NP before
# "is a/an" is the definiendum — register it as an implicit intro so
# subsequent "the <NP>" references in the same claim (or descendants)
# resolve without an explicit "a <NP>" precursor.
_SELF_DEFINITION_RE = re.compile(
    rf"\bthe\s+(?P<defined>{_NP_CORE})"
    rf"(?:\s+[a-z][a-z0-9]?'?)?"
    rf"\s+is\s+(?:a|an)\s+",
    re.IGNORECASE,
)


# Wherein-subject bare-noun introduction. After "wherein", capture a
# bare noun phrase acting as the grammatical subject (no leading
# article). Requires the subject length ≥3 chars to reject single-char
# variable subjects like "wherein n is a positive integer". The
# subsequent token set ("of <determiner>", "gradually/respectively/…",
# intransitive-verb heads) gates against runaway captures.
_WHEREIN_BARE_SUBJECT_RE = re.compile(
    rf"\bwherein\s+(?P<subj>{_NP_CORE})\s+"
    rf"(?:of\s+(?:the|a|an|each|said|one|two|three|four|five|six|seven|eight|nine|ten)"
    rf"|gradually|respectively|generally|substantially|essentially"
    rf"|form|forms|include|includes|comprise|comprises"
    rf"|correspond|corresponds|represent|represents)",
    re.IGNORECASE,
)


def extract_introductions(text: str) -> list[str]:
    """Extract all element-introduction noun phrases from patent text.

    Covers standard patent quantifiers (a/an, at least one, one or more,
    a plurality of, ordinals, bare numerals) AND bare-noun list contexts
    (comprising / includes / consisting of / selected from … X, Y, and Z).

    Returns list of lowercase noun phrases (may contain duplicates).

    Matches preceded by ``the`` or ``said`` are back-references, not
    introductions, and are filtered out. This prevents quantified
    back-references like ``the two second edges`` from re-introducing
    ``second edges`` in downstream claims and masking the real earlier
    intro.
    """
    lowered = text.lower()
    refs: list[str] = []
    for m in _INTRO_PATTERNS.finditer(lowered):
        preceding = lowered[max(0, m.start() - 8) : m.start()]
        if _DEFINITE_PRECEDER.search(preceding):
            continue
        cleaned = clean_noun_phrase(m.group(1).strip())
        if cleaned:
            refs.append(cleaned)
    refs.extend(extract_bare_noun_intros(lowered))
    refs.extend(_extract_self_definition_intros(lowered))
    refs.extend(_extract_wherein_bare_subject_intros(lowered))
    refs.extend(extract_method_step_intros(lowered))
    refs.extend(extract_gerund_head_intros(lowered))
    refs.extend(extract_having_bare_noun_intros(lowered))
    return refs


def extract_pattern_a_intros(text: str) -> list[str]:
    """Extract ONLY Pattern A intros (a/an + noun, plurality of, etc.).

    R32-US (2026-05-04): subset of `extract_introductions` that excludes
    bare-noun-list intros, self-definition intros, and wherein-bare-subject
    intros. Used by the head-noun-from-intro mechanism in
    `check_antecedent_basis` so that promoted head nouns come ONLY from
    explicitly-introduced (`a X for Y`) phrases — never from gerund-phrase
    bare-noun-list captures (`collecting information` from a comprising
    list, which Phase 2c flagged as a real §112(b) defect to preserve).
    """
    lowered = text.lower()
    refs: list[str] = []
    for m in _INTRO_PATTERNS.finditer(lowered):
        preceding = lowered[max(0, m.start() - 8) : m.start()]
        if _DEFINITE_PRECEDER.search(preceding):
            continue
        cleaned = clean_noun_phrase(m.group(1).strip())
        if cleaned:
            refs.append(cleaned)
    return refs


def _extract_self_definition_intros(lowered: str) -> list[str]:
    refs: list[str] = []
    for m in _SELF_DEFINITION_RE.finditer(lowered):
        cleaned = clean_noun_phrase(m.group("defined").strip())
        if cleaned and len(cleaned) >= 3:
            refs.append(cleaned)
    return refs


def _extract_wherein_bare_subject_intros(lowered: str) -> list[str]:
    refs: list[str] = []
    for m in _WHEREIN_BARE_SUBJECT_RE.finditer(lowered):
        cleaned = clean_noun_phrase(m.group("subj").strip())
        if not cleaned or len(cleaned) < 3:
            continue
        # Reject single-token captures that look like placeholder letters
        # ("p represents …") — any 1-2 char single word is a variable name,
        # not an introduced element.
        words = cleaned.split()
        if len(words) == 1 and len(words[0]) <= 2:
            continue
        refs.append(cleaned)
    return refs


def extract_introductions_permissive(text: str) -> list[str]:
    """Variant of extract_introductions used by the cross-claim fallback
    registry (Fix #47). When an intro match is filtered (preceded by
    ``the``/``said``), advances by a single char rather than consuming past
    the match — so a later unfiltered trigger inside the filtered span
    (e.g. ``the two X ... two Y``) still surfaces. Emission-path extraction
    stays unchanged.
    """
    lowered = text.lower()
    refs: list[str] = []
    pos = 0
    while pos < len(lowered):
        m = _INTRO_PATTERNS.search(lowered, pos)
        if not m:
            break
        preceding = lowered[max(0, m.start() - 8) : m.start()]
        if _DEFINITE_PRECEDER.search(preceding):
            pos = m.start() + 1
            continue
        cleaned = clean_noun_phrase(m.group(1).strip())
        if cleaned:
            refs.append(cleaned)
        pos = m.end()
    refs.extend(extract_bare_noun_intros(lowered))
    return refs


def extract_noun_phrases(text: str) -> list[str]:
    """Extract meaningful noun phrases from patent text.

    Reused by antecedent basis check and spec support check.
    Returns deduplicated list of lowercase noun phrases.
    """
    phrases: set[str] = set()
    for m in _INDEFINITE_REF.finditer(text.lower()):
        cleaned = clean_noun_phrase(m.group(1).strip())
        if cleaned:
            phrases.add(cleaned)
    for m in _DEFINITE_REF.finditer(text.lower()):
        cleaned = clean_noun_phrase(m.group("noun").strip())
        if cleaned:
            phrases.add(cleaned)
    return sorted(phrases)


def extract_definite_refs(text: str) -> list[str]:
    """Extract definite references ('the X', 'said X') from text."""
    refs: list[str] = []
    for m in _DEFINITE_REF.finditer(text.lower()):
        cleaned = clean_noun_phrase(m.group("noun").strip())
        if cleaned:
            refs.append(cleaned)
    return refs


def extract_indefinite_refs(text: str) -> list[str]:
    """Extract indefinite references ('a X', 'an X') from text."""
    refs: list[str] = []
    for m in _INDEFINITE_REF.finditer(text.lower()):
        cleaned = clean_noun_phrase(m.group(1).strip())
        if cleaned:
            refs.append(cleaned)
    return refs


def token_set_jaccard(a: str, b: str) -> float:
    """Token-set Jaccard similarity over whitespace-split lowercase tokens.

    Used by the antecedent walker's did-you-mean suggestion layer (commit 10):
    when a definite reference has no exact-match introduction, the highest
    Jaccard intro in the same claim's ancestor set is offered as a hint when
    similarity is at least 0.5. Morphological variants such as "common voltage
    difference calculation circuit" vs "common voltage difference calculating
    circuit" share four of five tokens (Jaccard 0.667) and surface as a
    suggestion rather than being silently matched.
    """
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def first_ancestor_with_term(chain: list, term: str) -> tuple[int | None, str | None]:
    """Find the first proper ancestor whose text literally contains ``term``.

    ``chain`` is the ``[claim, ...ancestors]`` list the antecedent
    walkers build via ``get_ancestor_chain*``; index 0 (the claim
    itself) is skipped — only parent claims are scanned. Match is
    case-insensitive substring.

    Returns ``(ancestor_claim_id, ancestor_claim_text)`` for the first
    match, else ``(None, None)``.

    Enriches an antecedent-basis finding with a parent-claim diagnostic:
    a term flagged as lacking antecedent basis that DOES appear verbatim
    in an ancestor was introduced there in a shape the intro extractor
    missed (walker FP); a term absent from every ancestor is a genuine
    §112 antecedent gap. Lets the de-identified report payload
    self-classify the finding without the user's draft.
    """
    term_lc = (term or "").strip().lower()
    if not term_lc:
        return None, None
    for ancestor in chain[1:]:
        if term_lc in (getattr(ancestor, "text", "") or "").lower():
            return ancestor.id, ancestor.text
    return None, None


_ARTICLE_BEFORE_RE = re.compile(r"(?:\bthe|\bsaid|\ba|\ban)\s+$", re.IGNORECASE)


def has_bare_noun_introduction(
    claim_text: str, chain: list, term: str, ref_offset: int
) -> bool:
    """True if the multi-word noun phrase ``term`` is introduced earlier.

    "Introduced earlier" = a whole-phrase, article-less occurrence of
    ``term`` that precedes the reference in document order: in
    ``claim_text`` strictly before ``ref_offset``, or anywhere in an
    ancestor claim (``chain[1:]`` — every ancestor is wholly earlier).

    MPEP § 2173.05(e): antecedent basis need not be an explicit ``a/an``
    — if the scope is reasonably ascertainable, ``the X`` after a prior
    article-less mention of the same specific term is not indefinite.
    The intro-pattern extractors only register quantified (``a X``,
    ``a plurality of X``) or framed introductions; they miss the
    article-less first mention — a preamble term (``based on
    ultra-wideband connection``) or a verb object (``generate real-time
    driving environment information``). This rescue closes that gap.

    Gated **multi-word** (≥2 whitespace tokens): a lone bare noun is too
    generic for an article-less occurrence to be a deliberate
    introduction. An occurrence preceded by ``the/said`` (a
    back-reference) — or by ``a/an`` (a Pattern-A intro the extractors
    already handle) — does not count; only a fresh article-less mention.
    """
    t = (term or "").strip().lower()
    if not t or len(t.split()) < 2:
        # DEFERRED R33 (reports #336/#337): a single-word GERUND process-noun
        # (`bonding`) recited earlier in article-less verb-object position
        # (`bonding the wafers`) DOES supply antecedent (MPEP §2173.05(e)), so
        # `the bonding` in a dependent claim is not indefinite. The mechanism
        # is built + PA-corpus-validated (validate_fix: 3 gold FPs silenced /
        # 0 legit) but BLOCKED on the examiner FN-guard: us_examiner_legit.json
        # carries 24 single-word gerund terms (the bonding / filling / heating
        # / cooling / mating / sensing / winding / …) that must be cleared via
        # the examiner ODP join (tests/eval/ws_a3_examiner_join.py), which
        # needs the EdgeXpert DB (Tailscale, unreachable this session). Ship
        # only after that join returns 0 silenced examiner terms. The TW mirror
        # (#340) has no examiner-DB dependency and ships independently.
        return False
    pat = re.compile(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])")
    low = (claim_text or "").lower()
    for m in pat.finditer(low):
        if m.start() >= ref_offset:
            break
        if not _ARTICLE_BEFORE_RE.search(low[max(0, m.start() - 6): m.start()]):
            return True
    for ancestor in chain[1:]:
        atext = (getattr(ancestor, "text", "") or "").lower()
        for m in pat.finditer(atext):
            if not _ARTICLE_BEFORE_RE.search(atext[max(0, m.start() - 6): m.start()]):
                return True
    return False
