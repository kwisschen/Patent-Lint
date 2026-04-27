# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Claim-level structural analysis.

Checks for missing periods, extra periods, dependencies, similarity, sequentiality,
preamble consistency, and spec support.
"""

import re
from typing import Any, Optional

import snowballstemmer as _sb

from patentlint.analysis.en_normalize import en_number_key
from patentlint.analysis.utils import (
    _DEFINITE_REF, _QUANTIFIER_STOPS, _dx,
    extract_introductions, extract_introductions_permissive,
    extract_abbreviation_intros, clean_noun_phrase,
    strip_contextual_verb, token_set_jaccard,
)
from patentlint.models import Claim, CheckItem, UnsupportedTerm


def find_missing_periods(claims: list[Claim]) -> list[int]:
    """Find claims missing a final period."""
    return [
        c.id for c in claims
        if not re.search(r"(?s)\.\s*$", c.text, re.UNICODE)
    ]


def has_extra_periods(claim_text: str) -> bool:
    """Check if a claim has extra/misplaced periods."""
    lines = re.split(r"\r?\n", claim_text)
    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue
        is_last = i == len(lines) - 1

        if ".." in line:
            return True

        if line.endswith(".") and not is_last:
            if (
                not re.search(r"\d+\.$", line)
                and not re.match(r"(?i)^wherein ", line)
                and not re.search(r"(?i)\bdifference between\b", line)
            ):
                return True

    return False


def find_extra_periods(claims: list[Claim]) -> list[int]:
    """Find claims with extra/misplaced periods."""
    return [c.id for c in claims if has_extra_periods(c.text)]


def find_multiple_dependents(claims: list[Claim]) -> list[int]:
    return [c.id for c in claims if c.multiple_dependent]


def find_chained_multi_dependents(claims: list[Claim]) -> list[int]:
    """35 U.S.C. § 112(e) prohibits a multi-dependent claim that depends on
    another multi-dependent claim. Returns the IDs of claims that violate
    this rule — multi-dep claims whose chain includes another multi-dep.

    Mirrors CN cn_claims::check_multi_multi_dep and TW tw_claims::
    check_multi_dep_on_multi_dep (专利法实施细则 §25 第3款 / 專利法施行細則 §18)."""
    multi_dep_ids = {c.id for c in claims if c.multiple_dependent}
    if not multi_dep_ids:
        return []
    return [
        c.id for c in claims
        if c.multiple_dependent
        and any(dep in multi_dep_ids for dep in c.dependencies)
    ]


def find_self_dependent_claims(claims: list[Claim]) -> list[int]:
    return [c.id for c in claims if c.id in c.dependencies]


def count_independent(claims: list[Claim]) -> int:
    return sum(1 for c in claims if c.independent)


def count_dependent(claims: list[Claim]) -> int:
    return sum(1 for c in claims if not c.independent)


def are_claims_sequential(claim_numbers: list[int]) -> bool:
    for i in range(1, len(claim_numbers)):
        if claim_numbers[i] - claim_numbers[i - 1] != 1:
            return False
    return True


def get_last_sequential_index(claim_numbers: list[int]) -> int:
    for i in range(1, len(claim_numbers)):
        if claim_numbers[i] - claim_numbers[i - 1] != 1:
            return i
    return len(claim_numbers)


def _find_claim_by_id(claim_id: int, claims: list[Claim]) -> Optional[Claim]:
    for c in claims:
        if c.id == claim_id:
            return c
    return None


def get_dependency_chain(claim: Claim, all_claims: list[Claim]) -> str:
    """Build the dependency chain string for a claim."""
    if claim.independent:
        return str(claim.id)

    if claim.dependencies:
        # Renders the primary (first-parent) chain only; multi-parent claims
        # show one of N possible chains.  UX decision, not a bug.
        parent_id = claim.dependencies[0]

        if parent_id == claim.id:
            return "SELF"

        parent = _find_claim_by_id(parent_id, all_claims)
        if parent is None:
            return f"{claim.id} → <Undefined> {parent_id}"

        if parent_id in parent.dependencies:
            return f"{claim.id} → {parent_id}"

        return f"{claim.id} → {get_dependency_chain(parent, all_claims)}"

    return str(claim.id)


_MEANS_PLUS_FUNCTION = re.compile(
    r"(?<!\bby\s)\b(means|step|mechanism|module)\s+for\s+\w+ing\b",
    re.IGNORECASE,
)


def detect_means_plus_function(claims: list[Claim]) -> list[int]:
    """Detect claims invoking 35 U.S.C. § 112(f) means-plus-function.

    Triggers: "means for", "step for", "mechanism for", "module for" + gerund
    Does NOT trigger: "by means of" (prepositional, not 112(f))
    """
    return [c.id for c in claims if _MEANS_PLUS_FUNCTION.search(c.text)]


_SKIP_TERMS = {"invention", "present invention", "same", "following", "above", "below"}

# Markush "the group" trailing context: when a "the X" reference where
# X is exactly "group" is followed by "consisting of" or "of", the term
# is the head noun of a Markush group definition rather than a missing
# antecedent. Walk-time skip rather than extraction-time carve-out so
# the heuristic stays narrow and inspectable.
_MARKUSH_GROUP_TRAIL = re.compile(r"^\s+(?:consisting\s+of|of)\b", re.IGNORECASE)


def _word_boundary_match(needle: str, haystack: str) -> bool:
    """Return True iff ``needle`` appears in ``haystack`` as a complete
    word sequence (case-insensitive, anchored on word boundaries).

    Used by the antecedent walker to suppress findings only when an
    introduction and a reference share the same word sequence — short
    introductions like 'common voltage' must NOT silently mask longer
    references like 'the common voltage difference calculation circuit'.
    """
    needle = needle.strip()
    if not needle:
        return False
    pattern = r"\b" + re.escape(needle) + r"\b"
    return re.search(pattern, haystack, re.IGNORECASE) is not None


def check_antecedent_basis(claims: list[Claim]) -> list[dict]:
    """Check claims for antecedent basis issues.

    A finding is emitted when a definite reference ("the X" or "said X") in
    a claim does not have a matching prior introduction ("a X", "an X", "at
    least one X", etc.) in the same claim or any of its ancestor claims
    (walking the full multi-parent dependency graph).

    Returns: list of dicts with keys claim_id, term, reference_form,
    claim_text, suggested_match. ``suggested_match`` is None for findings
    with no near-match introduction in the ancestor set, otherwise a dict
    ``{"term": <intro_term>, "claim_id": <intro_claim_id>}`` carrying the
    highest-Jaccard introduction (≥ 0.5). Findings are deduped by
    (claim_id, term, reference_form) and sorted.

    Known limitations (deferred):
    - Generic terms ("the user", "the step", "the output") are flagged
      unconditionally even when they may be implicit. A confidence-bucketing
      pass is future work.
    - Possessive constructions are normalized by stripping 's, but complex
      possessives ("the second device's first housing") may still produce
      unexpected captures.
    """
    def get_ancestor_chain(claim: Claim, all_claims: list[Claim]) -> list[Claim]:
        """Return [claim, ...ancestors] walking the full multi-parent BFS.

        Multi-dependent claims (e.g., "claim 5 of claim 1 or claim 3")
        collect introductions from every ancestor path.
        """
        claims_by_id = {c.id: c for c in all_claims}
        chain = [claim]
        visited = {claim.id}
        queue = list(claim.dependencies)
        while queue:
            parent_id = queue.pop(0)
            if parent_id in visited:
                continue
            visited.add(parent_id)
            parent = claims_by_id.get(parent_id)
            if parent is None:
                continue
            chain.append(parent)
            queue.extend(parent.dependencies)
        return chain

    # All-prior-claims intro registry (Fix #47). Used ONLY as a secondary
    # did-you-mean fallback when the ancestor-chain suggestion is None, so a
    # cross-branch intro (e.g., testspec9 c12 introduces "extending lines"
    # but c13 depends on c9) still surfaces as a hint. Emission decisions
    # remain driven by the ancestor chain — a cross-branch term has no
    # antecedent basis under §112 ¶2 and stays flagged.
    all_intros_registry: dict[str, int] = {}
    for _c in sorted(claims, key=lambda x: x.id):
        for _phrase in extract_introductions_permissive(_c.text):
            if _phrase not in all_intros_registry:
                all_intros_registry[_phrase] = _c.id
        for _abbrev in extract_abbreviation_intros(_c.text):
            if _abbrev not in all_intros_registry:
                all_intros_registry[_abbrev] = _c.id

    issues: list[dict] = []

    for claim in claims:
        chain = get_ancestor_chain(claim, claims)
        claim_text_lower = claim.text.lower()

        # Gather all introductions, tracking the ancestor claim each came from.
        # When the same intro phrase appears in multiple ancestors, prefer the
        # lowest claim id (the earliest claim that introduced the term) so
        # did-you-mean attributes references to the original intro, not a
        # re-mention in a nearer ancestor.
        intros_by_term: dict[str, int] = {}

        def _record(phrase: str, ancestor_id: int) -> None:
            existing = intros_by_term.get(phrase)
            if existing is None or ancestor_id < existing:
                intros_by_term[phrase] = ancestor_id

        for ancestor in chain:
            ancestor_lower = ancestor.text.lower()
            for phrase in extract_introductions(ancestor_lower):
                _record(phrase, ancestor.id)
            for abbrev_intro in extract_abbreviation_intros(ancestor.text):
                _record(abbrev_intro, ancestor.id)

        intros = set(intros_by_term.keys())

        intros_by_number_key: dict[str, int] = {}
        for phrase, phrase_claim_id in intros_by_term.items():
            key = en_number_key(phrase)
            intros_by_number_key.setdefault(key, phrase_claim_id)

        # Find definite references ("the X" and "said X") in this claim
        seen: set[tuple[str, str]] = set()
        for m in _DEFINITE_REF.finditer(claim_text_lower):
            term = clean_noun_phrase(m.group("noun").strip())
            term = strip_contextual_verb(term, claim_text_lower[m.end():])
            if not term:
                continue
            # Skip standalone quantifiers/pronouns ("the one", "the another")
            if term.lower() in _QUANTIFIER_STOPS:
                continue
            # Markush "the group consisting of A, B, C" — 'group' is the
            # head of the Markush definition, not a missing antecedent.
            if term.lower() == "group" and _MARKUSH_GROUP_TRAIL.match(
                claim_text_lower[m.end():]
            ):
                continue
            # Primary: bidirectional word-boundary exact match.
            # Fallback: ADR-095 Rule 3 analogue — number-agnostic key match
            # for plural-intro / singular-reference pairs.
            has_basis = any(
                _word_boundary_match(intro, term) and _word_boundary_match(term, intro)
                for intro in intros
            ) or en_number_key(term) in intros_by_number_key

            if not has_basis:
                if term not in _SKIP_TERMS and not term.startswith("fig") and not term.startswith("claim"):
                    prefix = m.group("prefix").lower()
                    reference_form = f"{prefix} {term}"
                    dedup_key = (term, reference_form)
                    if dedup_key not in seen:
                        seen.add(dedup_key)
                        # Did-you-mean: highest-Jaccard intro in ancestor set
                        # at threshold ≥ 0.5. Surfaces morphological variants
                        # (calculation/calculating, protection/protecting)
                        # without silently matching them.
                        # Did-you-mean: pick the highest-Jaccard intro at
                        # threshold ≥ 0.5, with a stemmed-symmetric-difference
                        # tiebreak so morphological pairs (protection/protecting,
                        # both stem to 'protect') beat coincidental token
                        # overlaps with unrelated nouns.
                        #
                        # Tiebreak rationale: when two candidates tie on
                        # Jaccard, the one whose differing tokens stem to the
                        # SAME root as the reference's differing tokens is the
                        # morphological pair we want to surface. On testspec5,
                        # 'surge protecting circuit' ties with both 'surge
                        # protection circuit' (stem_sym_diff = ∅, perfect pair)
                        # and 'surge suppressor circuit' (stem_sym_diff = 2,
                        # unrelated). Stemmed comparison picks the former.
                        #
                        # ADR-090 not violated: this only chooses a BETTER hint
                        # within an already-emitted finding. The reference is
                        # still flagged; stemming never silently masks anything.
                        # Quality threshold (#57): require Jaccard ≥ 2/3
                        # (≥2-of-3 token overlap), with a carveout admitting
                        # 0.5 ≤ score < 2/3 IFF stemming collapsed the
                        # symmetric difference (stem_sym_diff < raw_sym_diff) —
                        # pure morphological variants like protecting/protection
                        # or resister/resistor stay surfaced, while coincidental
                        # 2-of-4-token overlaps ("duty cycle threshold" ↔
                        # "specified duty cycle") drop out.
                        _MIN_JACCARD = 2.0 / 3.0
                        def _accept(score: float, raw_diff: int, stem_diff: int) -> bool:
                            if score + 1e-9 >= _MIN_JACCARD:
                                return True
                            return score >= 0.5 and stem_diff < raw_diff
                        suggested_match: Optional[dict] = None
                        best_score = 0.0
                        best_stem_diff: Optional[int] = None
                        term_tokens = set(term.lower().split())
                        for intro in intros:
                            score = token_set_jaccard(term, intro)
                            intro_tokens = set(intro.lower().split())
                            sym_diff = term_tokens ^ intro_tokens
                            stem_sym_diff = len(
                                set(_stemmer.stemWords(list(sym_diff)))
                            )
                            if not _accept(score, len(sym_diff), stem_sym_diff):
                                continue
                            if (
                                score > best_score
                                or (
                                    score == best_score
                                    and (
                                        best_stem_diff is None
                                        or stem_sym_diff < best_stem_diff
                                    )
                                )
                            ):
                                best_score = score
                                best_stem_diff = stem_sym_diff
                                suggested_match = {
                                    "term": intro,
                                    "claim_id": intros_by_term[intro],
                                }
                        # Fix #47 fallback + cross-branch exact-match override:
                        # scan all-prior-claims registry for a cross-branch intro
                        # from an earlier-numbered claim. Promote when (a) no
                        # ancestor suggestion surfaced, OR (b) the cross-branch
                        # candidate strictly outscores the ancestor pick — this
                        # lets a Jaccard=1.0 cross-branch exact match override a
                        # loose ancestor-chain pairing (e.g. "duty cycle threshold"
                        # in c10 beats "current duty cycle" in c9 ancestor chain).
                        # Informational only; finding remains flagged because
                        # §112 ¶2 antecedent basis requires an ancestor intro.
                        fb_best_score = best_score
                        fb_best_stem_diff: Optional[int] = best_stem_diff
                        for fb_intro, fb_cid in all_intros_registry.items():
                            if fb_cid >= claim.id:
                                continue
                            if fb_intro in intros_by_term:
                                continue
                            fb_score = token_set_jaccard(term, fb_intro)
                            fb_intro_tokens = set(fb_intro.lower().split())
                            fb_sym_diff = term_tokens ^ fb_intro_tokens
                            fb_stem_sym_diff = len(
                                set(_stemmer.stemWords(list(fb_sym_diff)))
                            )
                            if not _accept(fb_score, len(fb_sym_diff), fb_stem_sym_diff):
                                continue
                            if (
                                fb_score > fb_best_score
                                or (
                                    fb_score == fb_best_score
                                    and (
                                        fb_best_stem_diff is None
                                        or fb_stem_sym_diff < fb_best_stem_diff
                                    )
                                )
                            ):
                                fb_best_score = fb_score
                                fb_best_stem_diff = fb_stem_sym_diff
                                # cross_branch flag distinguishes an intro found
                                # outside the current claim's ancestor chain from
                                # an ancestor-chain near-miss. The UI uses this
                                # plus an exact-term-match check to render a
                                # "term defined in claim N, not in dependency
                                # chain" message instead of the generic
                                # "Did you mean …?" DYM hint — the drafter
                                # already knows the term; the real issue is the
                                # dependency structure.
                                suggested_match = {
                                    "term": fb_intro,
                                    "claim_id": fb_cid,
                                    "cross_branch": True,
                                }
                        # Structural fingerprint (ADR-145) — surfaces walker
                        # intro-pool + did-you-mean state. Counts + booleans
                        # only; no claim text, no noun content.
                        diagnostics = {
                            "prefix": prefix,  # "the" or "said" — closed set
                            "term_charlen": len(term),
                            "intros_pool_size": len(intros_by_term),
                            "has_suggested_match": suggested_match is not None,
                            "suggested_cross_branch": bool(
                                suggested_match
                                and suggested_match.get("cross_branch")
                            ) if suggested_match else False,
                        }
                        issues.append({
                            "claim_id": claim.id,
                            "term": term,
                            "reference_form": reference_form,
                            "claim_text": claim.text,
                            "suggested_match": suggested_match,
                            "cross_ref": None,
                            "diagnostics": diagnostics,
                        })

    issues.sort(key=lambda x: (x["claim_id"], x["term"], x["reference_form"]))
    return issues


def _get_ngrams(text: str, n: int) -> list[str]:
    words = text.lower().split()
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity using N-gram Jaccard index."""
    ngrams1 = set(_get_ngrams(text1, 1) + _get_ngrams(text1, 2))
    ngrams2 = set(_get_ngrams(text2, 1) + _get_ngrams(text2, 2))

    intersection = ngrams1 & ngrams2
    union = ngrams1 | ngrams2

    return len(intersection) / len(union) if union else 0.0


# --- Preamble consistency (B1) ---

_TRANSITIONS = re.compile(
    r",?\s*(?:"
    r"(?:"
    r"comprising\s*(?:the\s+steps?\s+of\s*)?"
    r"|consisting\s+essentially\s+of"
    r"|consisting\s+of"
    r"|including"
    r"|having"
    r")\s*:"
    r"|wherein\b"
    r")",
    re.IGNORECASE,
)

_DEP_PREAMBLE = re.compile(
    # Covers MPEP § 608.01(n)(iii) accepted forms:
    #   "The X of claim N"           (most common)
    #   "The X according to claim N"
    #   "The X as in claim N"        ("as in")
    #   "The X as claimed in claim N"  (British form)
    #   "The X as recited in claim N"
    #   "The X as set forth in claim N"
    r"^(The|An?)\s+(.*?)\s+"
    r"(?:"
    r"of"
    r"|according\s+to"
    r"|as\s+in"
    r"|as\s+claimed\s+in"
    r"|as\s+recited\s+in"
    r"|as\s+set\s+forth\s+in"
    r")\s+claims?\s+(\d+)",
    re.IGNORECASE,
)

_JEPSON_PATTERN = re.compile(
    r"^In\s+(?:a|an)\s+.*?,\s+the\s+improvement\s+comprising",
    re.IGNORECASE,
)

_METHOD_NOUNS = {"method", "process", "technique", "procedure", "step"}
_CRM_NOUNS = {"medium", "memory", "storage"}
_CRM_CONTEXT = {"readable", "transitory", "non-transitory"}

# Stop words for head noun extraction.
# Includes prepositional / participial phrase markers so the head noun
# extractor stops at the first qualifier rather than swallowing the rest
# of the preamble (e.g., "motor driver for adjusting power based on
# common voltage" → "motor driver" instead of the whole string).
_PREAMBLE_STOP = re.compile(
    r"\b(for|of|to|with|having|comprising|including|that|which"
    r"|based\s+on|adapted\s+to|configured\s+to|capable\s+of|storing)\b",
    re.IGNORECASE,
)


def _extract_head_noun(preamble_text: str) -> str | None:
    """Extract the core head noun from a claim preamble text."""
    # Remove leading article
    text = re.sub(r"^(?:a|an|the)\s+", "", preamble_text.strip(), flags=re.IGNORECASE).strip()
    if not text:
        return None

    # Stop at first comma, or purpose clause
    comma_idx = text.find(",")
    if comma_idx > 0:
        text = text[:comma_idx].strip()

    # Stop at stop words
    m = _PREAMBLE_STOP.search(text)
    if m:
        text = text[:m.start()].strip()

    # Take last meaningful word(s) — typically the head noun
    words = text.lower().split()
    if not words:
        return None

    return " ".join(words)


def _classify_entity(head_noun: str, full_preamble: str) -> str:
    """Classify entity as 'method', 'crm', or 'product'."""
    words = head_noun.lower().split()
    # Check if any word is a method noun
    if any(w in _METHOD_NOUNS for w in words):
        return "method"
    # Check CRM
    if any(w in _CRM_NOUNS for w in words):
        preamble_lower = full_preamble.lower()
        if any(ctx in preamble_lower for ctx in _CRM_CONTEXT):
            return "crm"
    return "product"


def _find_root_independent(claim: Claim, all_claims: list[Claim]) -> Claim | None:
    """Walk dependency graph (BFS) to find the first reachable independent claim.

    If a dependent claim has multiple independent roots with conflicting
    preamble entity types (rare in multi-dep claims), only the first
    BFS-reached root is returned.  This is a known limitation.
    """
    if claim.independent:
        return claim
    claims_by_id = {c.id: c for c in all_claims}
    visited: set[int] = {claim.id}
    queue = list(claim.dependencies)
    while queue:
        parent_id = queue.pop(0)
        if parent_id in visited:
            continue
        visited.add(parent_id)
        parent = claims_by_id.get(parent_id)
        if parent is None:
            continue
        if parent.independent:
            return parent
        queue.extend(parent.dependencies)
    return None


def _find_immediate_parent(claim: Claim, all_claims: list[Claim]) -> Claim | None:
    """Return the first existing immediate parent from claim.dependencies.

    For multi-dependent claims (dependencies = [1, 5]), callers should iterate
    all dependencies via _find_all_immediate_parents to unflag when ANY parent
    head matches. This helper returns only the first existing parent.

    Unlike _find_root_independent (which walks the full dependency graph BFS
    to find the transitive root), this helper walks exactly one hop. Used by
    check_preamble_consistency per ADR-092: the comparison target for
    §608.01(m) indefinite-article and noun-mismatch branches is the immediate
    parent, not the transitive root. Cross-category dependents (MPEP
    608.01(n)(III)) may introduce new entities that incorporate their parent,
    and the article rule applies relative to the nearest ancestor, not the
    original independent.
    """
    if claim.independent:
        return None
    claims_by_id = {c.id: c for c in all_claims}
    for parent_id in claim.dependencies:
        parent = claims_by_id.get(parent_id)
        if parent is not None:
            return parent
    return None


def _find_all_immediate_parents(claim: Claim, all_claims: list[Claim]) -> list[Claim]:
    """Return all existing immediate parent claims (multi-dependent support).

    Multi-dependent claim unflagging rule: check_preamble_consistency unflags
    when the dep head noun matches ANY immediate parent's head noun.
    """
    if claim.independent:
        return []
    claims_by_id = {c.id: c for c in all_claims}
    parents: list[Claim] = []
    for parent_id in claim.dependencies:
        parent = claims_by_id.get(parent_id)
        if parent is not None:
            parents.append(parent)
    return parents


def _preamble_head_info(claim: Claim) -> tuple[str, str] | None:
    """Return (head_noun, entity_type) for any claim (independent or dependent).

    Independent claims: extract the head noun from the preamble text before
    the transitional phrase. Dependent claims: use the noun phrase captured
    between the leading article and "of claim N" / "according to claim N"
    in the dependent preamble, then normalize via _extract_head_noun so the
    comma stop and stop-word tail trimming apply consistently.
    """
    if claim.independent:
        tm = _TRANSITIONS.search(claim.text)
        if not tm:
            return None
        preamble_text = claim.text[:tm.start()].strip()
        head = _extract_head_noun(preamble_text)
        if not head:
            return None
        return head, _classify_entity(head, preamble_text)

    dm = _DEP_PREAMBLE.match(claim.text)
    if not dm:
        return None
    dep_raw = dm.group(2).strip()
    head = _extract_head_noun(dep_raw)
    if not head:
        return None
    return head, _classify_entity(head, dep_raw)


def _heads_match(dep_head: str, parent_head: str) -> bool:
    """Case-insensitive exact-or-substring match per ADR-092 v1 semantics.

    Hyponym detection is deferred; exact and substring containment are
    sufficient for observed cross-category dependents.
    """
    if not dep_head or not parent_head:
        return False
    a = dep_head.lower().strip()
    b = parent_head.lower().strip()
    if a == b:
        return True
    return a in b or b in a


def check_preamble_consistency(claims: list[Claim]) -> list[CheckItem]:
    """Check that dependent claims reference the same entity type as their
    immediate parent (ADR-092).

    Both branches (indefinite-article §608.01(m) and noun/entity mismatch)
    compare the dependent claim's head noun against its immediate parent(s),
    not the transitive root independent. For multi-dependent claims, a match
    against ANY existing immediate parent unflags the finding.

    Returns CheckItem per finding (PASS if no issues, AMEND/VERIFY per problem).
    """
    results: list[CheckItem] = []
    has_issue = False
    # ADR-145: track dependents whose preamble didn't match any recognized
    # MPEP § 608.01(n)(iii) form so the aggregate parseUnclear finding can
    # surface them as a single "walker couldn't verify" signal rather than
    # silently skipping.
    unclear_ids: list[int] = []
    unclear_fp: dict[str, Any] | None = None

    for claim in claims:
        if claim.independent:
            continue

        dm = _DEP_PREAMBLE.match(claim.text)
        if not dm:
            unclear_ids.append(claim.id)
            if unclear_fp is None:
                unclear_fp = {
                    "dep_preamble_matched": False,
                    "claim_charlen": len(claim.text),
                }
            continue

        article = dm.group(1)
        parent_claim_num = int(dm.group(3))

        dep_info = _preamble_head_info(claim)
        if dep_info is None:
            unclear_ids.append(claim.id)
            if unclear_fp is None:
                unclear_fp = {
                    "dep_preamble_matched": True,
                    "head_noun_extracted": False,
                }
            continue
        dep_noun, dep_entity = dep_info

        parents = _find_all_immediate_parents(claim, claims)
        parent_infos = [
            info for info in (_preamble_head_info(p) for p in parents) if info is not None
        ]
        if not parent_infos:
            continue

        # §608.01(m) indefinite-article branch. Per MPEP 608.01(n)(III), a
        # dependent claim may introduce a new entity that incorporates its
        # parent — in that case "A/An" is mandatory. Only flag when the dep
        # head noun matches an immediate parent's head noun (i.e., same
        # entity, user typed the wrong article).
        if article.lower() in ("a", "an"):
            matches_parent = any(
                _heads_match(dep_noun, p_noun) for p_noun, _ in parent_infos
            )
            if matches_parent:
                results.append(CheckItem(
                    status="amend",
                    message=f"Claim {claim.id}: indefinite article '{article}' in dependent claim preamble (should be 'The').",
                    message_key="checks.preamble_indefinite_article",
                    details=f"Claim {claim.id} depends on claim {parent_claim_num}",
                    details_key="details.preambleIndefiniteArticle",
                    details_params={
                        "claim": str(claim.id),
                        "parent": str(parent_claim_num),
                        "article": article,
                        "noun": dep_noun,
                    },
                    diagnostics={
                        "article": article.lower(),
                        "dep_head_charlen": len(dep_noun),
                    },
                ))
                has_issue = True
            continue

        # Noun/entity mismatch branch. Unflag if any immediate parent matches
        # both head noun and entity type.
        if any(
            _heads_match(dep_noun, p_noun) and dep_entity == p_entity
            for p_noun, p_entity in parent_infos
        ):
            continue

        # No immediate parent matched — report against the first parent.
        p_noun, p_entity = parent_infos[0]

        if dep_entity != p_entity:
            results.append(CheckItem(
                status="amend",
                message=f"Claim {claim.id}: cross-category mismatch ({dep_entity} depends on {p_entity} claim {parent_claim_num}).",
                message_key="checks.preamble_cross_category_mismatch",
                details=f"Dependent '{dep_noun}' vs parent '{p_noun}'",
                details_key="details.nounMismatch",
                details_params={"dependent": dep_noun, "independent": p_noun},
                diagnostics={
                    "dep_entity": dep_entity,
                    "parent_entity": p_entity,
                    "dep_head_charlen": len(dep_noun),
                    "parent_head_charlen": len(p_noun),
                },
            ))
            has_issue = True
        elif dep_noun != p_noun:
            results.append(CheckItem(
                status="verify",
                message=f"Claim {claim.id}: preamble noun '{dep_noun}' differs from parent claim '{p_noun}'.",
                message_key="checks.preamble_noun_mismatch",
                details=f"Claim {claim.id} depends on claim {parent_claim_num}",
                details_key="details.preambleNounMismatch",
                details_params={
                    "claim": str(claim.id),
                    "parent": str(parent_claim_num),
                    "dependent": dep_noun,
                    "independent": p_noun,
                },
                diagnostics={
                    "dep_head_charlen": len(dep_noun),
                    "parent_head_charlen": len(p_noun),
                },
            ))
            has_issue = True

    if unclear_ids:
        claims_str = ", ".join(str(i) for i in unclear_ids)
        results.append(CheckItem(
            status="verify",
            message=f"{len(unclear_ids)} dependent claim(s) with an unrecognized preamble — couldn't verify preamble consistency (claims: {claims_str}).",
            message_key="checks.preamble_parse_unclear",
            details=f"{len(unclear_ids)} claims",
            details_key="details.preambleParseUnclear",
            details_params={"count": len(unclear_ids), "claims": unclear_ids},
            diagnostics=unclear_fp,
        ))
        has_issue = True

    if not has_issue:
        results.append(CheckItem(
            status="pass",
            message="Claim preambles are consistent.",
            message_key="checks.preamble_cross_category_pass",
        ))

    return results


# --- Spec support (B3) ---

_stemmer = _sb.stemmer("english")

# --- Claim transition phrase check (Issue #4) ---

_TRANSITION_PHRASES = re.compile(
    r"\b(?:"
    r"comprising|comprises"
    r"|consisting\s+essentially\s+of|consists\s+essentially\s+of"
    r"|consisting\s+of|consists\s+of"
    r"|including|includes"
    r"|containing|contains"
    r"|having"
    r"|characterized\s+in\s+that"
    r"|characterized\s+by"
    r")\b",
    re.IGNORECASE,
)

_TRANSITION_AT_BOUNDARY = re.compile(
    r"\b(?:"
    r"(?:comprising|comprises)\s*(?:the\s+steps?\s+of\s*)?"
    r"|(?:consisting|consists)\s+essentially\s+of"
    r"|(?:consisting|consists)\s+of"
    r"|including|includes"
    r"|containing|contains"
    r"|having"
    r"|characterized\s+by"
    r")\s*:"
    r"|\bcharacterized\s+in\s+that\b",
    re.IGNORECASE,
)


def check_claim_transitions(claims: list[Claim]) -> list[CheckItem]:
    """Check that every independent claim contains a recognized transition phrase.

    Returns one AMEND CheckItem per independent claim missing a transition,
    or a single PASS if all independent claims have transitions.
    """
    results: list[CheckItem] = []

    for claim in claims:
        if not claim.independent:
            continue
        has_transition = _TRANSITION_AT_BOUNDARY.search(claim.text)
        if not has_transition:
            if ":" not in claim.text:
                has_transition = _TRANSITION_PHRASES.search(claim.text)
        if not has_transition:
            results.append(CheckItem(
                status="amend",
                message=f"Claim {claim.id} is missing a transitional phrase (e.g., 'comprising', 'consisting of')",
                message_key="check.claims.missingTransition",
                details=f"Claim {claim.id} does not contain a recognized transitional phrase. Every claim must include a transitional phrase such as 'comprising', 'consisting of', 'consisting essentially of', 'including', 'containing', 'characterized by', or 'characterized in that' between the preamble and the claim body.",
                details_key="check.claims.missingTransitionDetails",
                details_params={"claimNumber": str(claim.id)},
                diagnostics=_dx(
                    flagged_claim_id=claim.id,
                    has_colon=":" in claim.text,
                ),
            ))

    if not results:
        results.append(CheckItem(
            status="pass",
            message="All claims contain transitional phrases.",
            message_key="check.claims.transitionsPresent",
        ))

    return results


# --- Special claim format checks (Issue #6) ---

_JEPSON_SPECIAL = re.compile(
    r"\b(?:"
    r"the\s+improvement\s+(?:comprising|which\s+comprises|wherein)"
    r"|wherein\s+the\s+improvement(?:\s+comprises)?"
    r")\b",
    re.IGNORECASE,
)

_CRM_MEDIUM = re.compile(
    r"\b(?:computer[- ]?readable|machine[- ]?readable)\s+(?:storage\s+)?medium"
    r"|\b(?:storage|recording)\s+medium",
    re.IGNORECASE,
)

_NON_TRANSITORY = re.compile(r"\bnon[- ]?transitory\b", re.IGNORECASE)

_MARKUSH_OPEN = re.compile(
    r"selected\s+from\s+(?:the|a)\s+group\s+"
    r"(comprising|including|containing)",
    re.IGNORECASE,
)

_OMNIBUS_LANG = re.compile(
    r"\bsubstantially\s+as\s+(?:shown|described|illustrated)\b"
    r"|\bas\s+(?:herein|hereinbefore|hereinabove)\s+described\b"
    r"|\bas\s+(?:shown|described|illustrated|depicted)\s+in\s+(?:the\s+)?(?:figures?|drawings?|FIG)\b"
    r"|\bthe\s+invention\s+as\s+described\b",
    re.IGNORECASE,
)


def check_special_claim_formats(claims: list[Claim]) -> list[CheckItem]:
    """Detect special claim formats and emit actionable warnings.

    Returns CheckItems only for detected formats — no PASS when nothing found.

    Checks:
    1. Jepson claims — prior art concession warning (VERIFY)
    2. CRM claims missing "non-transitory" (AMEND)
    3. Markush groups with open transitional phrase (VERIFY)
    4. Omnibus claims (AMEND)
    """
    results: list[CheckItem] = []

    for claim in claims:
        # 1. Jepson — independent only
        if claim.independent and _JEPSON_SPECIAL.search(claim.text):
            results.append(CheckItem(
                status="verify",
                message=(
                    f"Claim {claim.id} uses Jepson format — preamble elements "
                    f"are treated as admitted prior art (MPEP § 2129)"
                ),
                message_key="claims.jepsonPriorArt",
                details=(
                    f"Claim {claim.id} is drafted in Jepson format. Under MPEP § 2129, "
                    f"the elements recited in the preamble of a Jepson claim are treated "
                    f"as an implied admission that they are prior art. Verify that this "
                    f"admission is intentional."
                ),
                details_key="claims.jepsonPriorArtDetails",
                details_params={"claimNumber": str(claim.id)},
                diagnostics=_dx(
                    flagged_claim_id=claim.id,
                    total_claims=len(claims),
                    reason_code="jepson_format",
                ),
            ))

        # 2. CRM non-transitory — independent only
        if claim.independent and _CRM_MEDIUM.search(claim.text):
            if not _NON_TRANSITORY.search(claim.text):
                results.append(CheckItem(
                    status="amend",
                    message=(
                        f"Claim {claim.id}: computer-readable medium claim "
                        f"is missing 'non-transitory' qualifier"
                    ),
                    message_key="claims.crmNonTransitory",
                    details=(
                        f"Claim {claim.id} recites a computer-readable medium without "
                        f"the 'non-transitory' qualifier. Without this qualifier, the "
                        f"claim covers transitory signals (e.g., carrier waves), which "
                        f"are not patent-eligible subject matter under 35 U.S.C. § 101. "
                        f"Add 'non-transitory' before the medium term."
                    ),
                    details_key="claims.crmNonTransitoryDetails",
                    details_params={"claimNumber": str(claim.id)},
                    diagnostics=_dx(
                        flagged_claim_id=claim.id,
                        total_claims=len(claims),
                        reason_code="missing_non_transitory_qualifier",
                    ),
                ))

        # 3. Markush — all claims
        markush_match = _MARKUSH_OPEN.search(claim.text)
        if markush_match:
            transition = markush_match.group(1)
            results.append(CheckItem(
                status="amend",
                message=(
                    f"Claim {claim.id}: Markush group uses open-ended "
                    f"'{transition}' instead of 'consisting of'"
                ),
                message_key="claims.markushOpenTransition",
                details=(
                    f"Claim {claim.id} contains a Markush group using '{transition}' "
                    f"instead of the required 'consisting of'. Markush groups must use "
                    f"closed transitional language per MPEP § 2117. Using open-ended "
                    f"language may result in an improper Markush grouping rejection."
                ),
                details_key="claims.markushOpenTransitionDetails",
                details_params={"claimNumber": str(claim.id), "transition": transition},
                diagnostics=_dx(
                    flagged_claim_id=claim.id,
                    transition=transition.lower(),
                ),
            ))

        # 4. Omnibus — all claims, requires short text + omnibus language
        word_count = len(claim.text.split())
        if word_count < 50 and _OMNIBUS_LANG.search(claim.text):
            results.append(CheckItem(
                status="amend",
                message=f"Claim {claim.id} appears to be an omnibus claim",
                message_key="claims.omnibusClaim",
                details=(
                    f"Claim {claim.id} references the description or drawings without "
                    f"reciting specific technical features. Omnibus claims are "
                    f"categorically rejected under 35 U.S.C. § 112(b) in U.S. utility "
                    f"patents (MPEP § 2173.05(r)). Rewrite the claim to recite specific "
                    f"structural or method limitations."
                ),
                details_key="claims.omnibusClaimDetails",
                details_params={"claimNumber": str(claim.id)},
                diagnostics=_dx(
                    flagged_claim_id=claim.id,
                    word_count=word_count,
                ),
            ))

    if not results:
        results.append(CheckItem(
            status="pass",
            message="No special claim format issues detected.",
            message_key="claims.specialFormatsPass",
        ))

    return results


def check_claim_punctuation(claims: list[Claim]) -> list[CheckItem]:
    """Check claim punctuation rules per MPEP § 608.01(m).

    Sub-checks:
    1. Missing final period — every claim must end with a period
    2. Extra periods — claims should not contain misplaced periods mid-claim
    3. Wherein comma — 'wherein' clauses require correct comma placement

    Emits individual AMEND/VERIFY per finding, or single PASS if all clean.
    """
    from patentlint.parser.claims import detect_incorrect_wherein_commas

    results: list[CheckItem] = []

    # Pre-compute per-claim character lookups so fingerprints can carry
    # the last-char codepoint (spots fullwidth vs halfwidth period
    # confusion) without rescanning claims for every finding.
    claim_text_by_id = {c.id: c.text.strip() for c in claims}

    for claim_id in find_missing_periods(claims):
        text = claim_text_by_id.get(claim_id, "")
        last_cp = ord(text[-1]) if text else None
        results.append(CheckItem(
            status="amend",
            message=f"Claim {claim_id} does not end with a period.",
            message_key="claims.missingPeriod",
            details=f"Claim {claim_id} is missing its final period. Every claim must end with a single period per MPEP § 608.01(m).",
            details_key="claims.missingPeriodDetails",
            details_params={"claimNumber": str(claim_id)},
            diagnostics=_dx(
                flagged_claim_id=claim_id,
                last_codepoint=last_cp,
            ),
        ))

    for claim_id in find_extra_periods(claims):
        text = claim_text_by_id.get(claim_id, "")
        results.append(CheckItem(
            status="amend",
            message=f"Claim {claim_id} contains extra or misplaced periods.",
            message_key="claims.extraPeriod",
            details=f"Claim {claim_id} has periods in unexpected positions. A claim should contain only one period at the very end per MPEP § 608.01(m).",
            details_key="claims.extraPeriodDetails",
            details_params={"claimNumber": str(claim_id)},
            diagnostics=_dx(
                flagged_claim_id=claim_id,
                period_count=text.count("."),
            ),
        ))

    for claim_id in detect_incorrect_wherein_commas(claims):
        results.append(CheckItem(
            status="verify",
            message=f"Claim {claim_id}: review comma usage before 'wherein' clause.",
            message_key="claims.whereinComma",
            details=f"Claim {claim_id} may have incorrect comma placement around a 'wherein' clause. Review punctuation per MPEP § 608.01(m).",
            details_key="claims.whereinCommaDetails",
            details_params={"claimNumber": str(claim_id)},
            diagnostics=_dx(
                flagged_claim_id=claim_id,
                total_claims=len(claims),
                reason_code="wherein_comma_irregular",
            ),
        ))

    if not results:
        results.append(CheckItem(
            status="pass",
            message="Claim punctuation is correct.",
            message_key="claims.punctuationPass",
        ))

    return results


_GENERIC_TERMS = {
    "system", "device", "method", "apparatus", "means", "step", "element",
    "member", "portion", "surface", "end", "side", "part",
}

_BOILERPLATE_TERMS = {
    "plurality", "embodiment", "thereof", "herein", "foregoing",
}

# Sliding-window size for spec-support proximity matching (Tier 2 stemmed,
# Tier 3 raw). Hoisted so both tiers share a single constant.
WINDOW_SIZE = 10


def check_spec_support(
    claims: list[Claim],
    spec_text: str,
) -> list[UnsupportedTerm]:
    """Check that claim noun phrases have support in the specification.

    Three-tier matching: exact, stemmed, word-window.

    Per ADR-091 (Option Y), this check no longer suppresses phrases already
    flagged by ``check_antecedent_basis``. Both checks now emit findings
    independently; the pipeline computes a cross-reference set so the
    frontend can render hint lines linking related findings instead of
    silently hiding one branch.
    """
    from patentlint.analysis.utils import extract_noun_phrases

    spec_lower = spec_text.lower()
    spec_words = spec_lower.split()

    # Pre-stem spec words for Tier 2. Order-preserving list (not a set) so
    # the Tier 2 sliding window can enforce proximity rather than checking
    # set membership across the entire spec.
    spec_stems = list(_stemmer.stemWords(spec_words))

    unsupported: list[UnsupportedTerm] = []

    for claim in claims:
        # Extract noun phrases from the claim body (skip preamble)
        # Find transition to skip preamble
        tm = _TRANSITIONS.search(claim.text)
        if tm:
            body = claim.text[tm.end():]
        else:
            body = claim.text

        phrases = extract_noun_phrases(body)

        for phrase in phrases:
            phrase_lower = phrase.lower()

            # Skip generic/boilerplate terms
            if phrase_lower in _GENERIC_TERMS or phrase_lower in _BOILERPLATE_TERMS:
                continue

            # Skip single common words
            if len(phrase_lower.split()) == 1 and phrase_lower in _GENERIC_TERMS:
                continue

            tiers_checked: list[str] = []

            # Tier 1: Exact match
            tiers_checked.append("exact")
            if phrase_lower in spec_lower:
                continue

            # Tier 2: Stemmed sliding window. All phrase stems must appear
            # together inside a single window. Window size grows to fit the
            # phrase if the phrase is longer than WINDOW_SIZE; otherwise the
            # window is fixed at WINDOW_SIZE so multi-word terms whose stems
            # are scattered across the spec are NOT silently matched.
            tiers_checked.append("stemmed")
            phrase_stems = list(_stemmer.stemWords(phrase_lower.split()))
            if phrase_stems:
                phrase_stem_set = set(phrase_stems)
                window_size = max(len(phrase_stems), WINDOW_SIZE)
                stem_loop_end = max(1, len(spec_stems) - window_size + 1)
                found_stem_window = False
                for i in range(stem_loop_end):
                    window = set(spec_stems[i:i + window_size])
                    if phrase_stem_set.issubset(window):
                        found_stem_window = True
                        break
                if found_stem_window:
                    continue

            # Tier 3: Word window (all words appear within WINDOW_SIZE-word window)
            tiers_checked.append("word_window")
            phrase_words = phrase_lower.split()
            if len(phrase_words) >= 2:
                found_window = False
                for i in range(len(spec_words) - len(phrase_words) + 1):
                    window = set(spec_words[i:i + WINDOW_SIZE])
                    if all(w in window for w in phrase_words):
                        found_window = True
                        break
                if found_window:
                    continue

            unsupported.append(UnsupportedTerm(
                claim_number=claim.id,
                phrase=phrase,
                tiers_checked=tiers_checked,
            ))

    return unsupported


def attach_cross_references(
    antecedent_findings: list[dict],
    unsupported_terms: list[UnsupportedTerm],
) -> None:
    """Cross-link antecedent and spec-support findings on the same term.

    Per ADR-091 (Option Y), the spec-support check no longer suppresses
    phrases already flagged by antecedent basis. Instead, when the same
    ``(claim_id, term)`` pair appears in both lists, each finding is
    annotated with a ``cross_ref`` pointing at the sibling check so the
    frontend can render a hint line:

    - ``cross_ref="spec_support"`` on antecedent findings → "Also flagged
      for spec support — see § 112(a) card."
    - ``cross_ref="antecedent"`` on spec-support findings → "Also flagged
      for antecedent basis — see § 112(b) card."

    Mutates both lists in place. Comparison is case-insensitive on the
    bare term.
    """
    ab_pairs: set[tuple[int, str]] = {
        (item["claim_id"], item["term"].lower()) for item in antecedent_findings
    }
    spec_pairs: set[tuple[int, str]] = {
        (ut.claim_number, ut.phrase.lower()) for ut in unsupported_terms
    }

    for item in antecedent_findings:
        if (item["claim_id"], item["term"].lower()) in spec_pairs:
            item["cross_ref"] = "spec_support"

    for ut in unsupported_terms:
        if (ut.claim_number, ut.phrase.lower()) in ab_pairs:
            ut.cross_ref = "antecedent"
