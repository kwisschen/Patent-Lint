# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
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
    if not spec_text:
        for f in findings:
            f["term_in_spec"] = False
        return
    for f in findings:
        term = (f.get("term") or "").strip()
        in_spec = bool(term) and term in spec_text
        f["term_in_spec"] = in_spec
        if in_spec and "confidence_score" in f:
            f["confidence_score"] = min(100, int(f["confidence_score"]) + 10)


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
    # R57: spec-body cross-validation +10 (applied separately by
    # `annotate_term_in_spec` in pipeline; included here for direct callers).
    if term_in_spec:
        score += 10
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
_WORD = r"\w+(?:-\w+)*"

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
})


def _is_trailing_relational_adj(word: str) -> bool:
    return word in _RELATIONAL_ADJ_STOPS


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
    "range":   frozenset({"from", "between", "to", "over", "in", "through"}),
    "ranges":  frozenset({"from", "between", "to", "over", "in", "through"}),
    "ranged":  frozenset({"from", "between", "to", "over", "in", "through"}),
    "ranging": frozenset({"from", "between", "to", "over", "in", "through"}),
}

_NEXT_WORD_RE = re.compile(r"\s*([A-Za-z][A-Za-z'\u2019-]*)")


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
    if not complements:
        return term
    m = _NEXT_WORD_RE.match(following_text)
    if not m:
        return term
    if m.group(1).lower() not in complements:
        return term
    return " ".join(words[:-1])


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


def clean_noun_phrase(phrase: str) -> str:
    """Strip trailing verbs, adverbs, and function words from a noun phrase."""
    words = phrase.strip().split()
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
    r"\(([A-Z]{2,})\)\s*"            # (ABBREV) — 2+ uppercase letters
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
