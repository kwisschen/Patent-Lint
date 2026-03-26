# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Claim-level structural analysis.

Checks for missing periods, extra periods, dependencies, similarity, sequentiality,
preamble consistency, and spec support.
"""

import re
from typing import Optional

import snowballstemmer as _sb

from patentlint.analysis.utils import (
    _DEFINITE_REF, _QUANTIFIER_STOPS,
    extract_introductions, extract_abbreviation_intros, clean_noun_phrase,
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


def check_antecedent_basis(claims: list[Claim]) -> list[dict]:
    """Check for missing antecedent basis in claims.

    For each claim, find "the [noun phrase]" and "said [noun phrase]".
    Check whether an introduction (a/an, at least one, a plurality of,
    ordinals, bare numerals) appears earlier in the same claim or any
    ancestor claim.

    Returns: [{"claim_id": int, "term": str}, ...]
    """
    def get_ancestor_texts(claim: Claim, all_claims: list[Claim]) -> tuple[str, str]:
        """Return (lowered_text, original_text) for claim + ancestors."""
        texts_lower = [claim.text.lower()]
        texts_orig = [claim.text]
        visited = {claim.id}
        current = claim
        while current.dependencies:
            parent_id = current.dependencies[0]
            if parent_id in visited:
                break
            visited.add(parent_id)
            parent = next((c for c in all_claims if c.id == parent_id), None)
            if parent is None:
                break
            texts_lower.append(parent.text.lower())
            texts_orig.append(parent.text)
            current = parent
        return " ".join(texts_lower), " ".join(texts_orig)

    issues: list[dict] = []

    for claim in claims:
        full_text, full_text_orig = get_ancestor_texts(claim, claims)
        claim_text_lower = claim.text.lower()

        # Gather ALL introductions (a/an, at least one, plurality, ordinals, numerals)
        intros: set[str] = set()
        for phrase in extract_introductions(full_text):
            intros.add(phrase)

        # Register abbreviated forms: "alternating current (AC) source" → "ac source"
        # Use original-case text so uppercase abbreviations are detected
        for abbrev_intro in extract_abbreviation_intros(full_text_orig):
            intros.add(abbrev_intro)

        # Find definite references ("the X" and "said X") in this claim
        for m in _DEFINITE_REF.finditer(claim_text_lower):
            term = clean_noun_phrase(m.group(1).strip())
            if not term:
                continue
            # Skip standalone quantifiers/pronouns ("the one", "the another")
            if term.lower() in _QUANTIFIER_STOPS:
                continue
            has_basis = any(term in intro or intro in term for intro in intros)
            if not has_basis:
                if term not in _SKIP_TERMS and not term.startswith("fig") and not term.startswith("claim"):
                    issues.append({"claim_id": claim.id, "term": term})

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
    r"comprising\s*(?:the\s+steps?\s+of\s*)?"
    r"|consisting\s+essentially\s+of"
    r"|consisting\s+of"
    r"|including"
    r"|having"
    r")\s*:",
    re.IGNORECASE,
)

_DEP_PREAMBLE = re.compile(
    r"^(The|An?)\s+(.*?)\s+(?:of|according\s+to)\s+claim\s+(\d+)",
    re.IGNORECASE,
)

_JEPSON_PATTERN = re.compile(
    r"^In\s+(?:a|an)\s+.*?,\s+the\s+improvement\s+comprising",
    re.IGNORECASE,
)

_METHOD_NOUNS = {"method", "process", "technique", "procedure", "step"}
_CRM_NOUNS = {"medium", "memory", "storage"}
_CRM_CONTEXT = {"readable", "transitory", "non-transitory"}

# Stop words for head noun extraction
_PREAMBLE_STOP = re.compile(
    r"\b(for|of|to|adapted\s+to|configured\s+to|capable\s+of|storing)\b",
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
    """Walk dependency chain to find the root independent claim."""
    visited: set[int] = set()
    current = claim
    while not current.independent and current.dependencies:
        parent_id = current.dependencies[0]
        if parent_id in visited:
            break
        visited.add(parent_id)
        parent = _find_claim_by_id(parent_id, all_claims)
        if parent is None:
            break
        current = parent
    return current if current.independent else None


def check_preamble_consistency(claims: list[Claim]) -> list[CheckItem]:
    """Check that dependent claims reference the same entity type as their parent.

    Returns CheckItem per finding (PASS if no issues, AMEND/VERIFY per problem).
    """
    results: list[CheckItem] = []

    # Build map of independent claim preambles
    indep_preambles: dict[int, tuple[str, str]] = {}  # claim_id -> (head_noun, entity_type)

    for claim in claims:
        if not claim.independent:
            continue

        # Jepson claim
        if _JEPSON_PATTERN.match(claim.text):
            # Extract improvement entity (skip for now — just mark the root)
            pass

        # Find transition
        tm = _TRANSITIONS.search(claim.text)
        if not tm:
            continue

        preamble_text = claim.text[:tm.start()].strip()
        head = _extract_head_noun(preamble_text)
        if head:
            entity = _classify_entity(head, preamble_text)
            indep_preambles[claim.id] = (head, entity)

    # Check each dependent claim
    has_issue = False
    for claim in claims:
        if claim.independent:
            continue

        dm = _DEP_PREAMBLE.match(claim.text)
        if not dm:
            continue

        article = dm.group(1)
        dep_noun_raw = dm.group(2).strip().lower()
        parent_claim_num = int(dm.group(3))

        # Find root independent claim
        root = _find_root_independent(claim, claims)
        if root is None or root.id not in indep_preambles:
            continue

        root_noun, root_entity = indep_preambles[root.id]

        # Check indefinite article (should be "The", not "A"/"An")
        if article.lower() in ("a", "an"):
            results.append(CheckItem(
                status="amend",
                message=f"Claim {claim.id}: indefinite article '{article}' in dependent claim preamble (should be 'The').",
                message_key="checks.preamble_indefinite_article",
                details=f"Claim {claim.id} depends on claim {parent_claim_num}",
                details_key="details.claimDependsOn",
                details_params={"claim": str(claim.id), "parent": str(parent_claim_num)},
            ))
            has_issue = True
            continue

        dep_entity = _classify_entity(dep_noun_raw, dep_noun_raw)

        # Cross-category mismatch
        if dep_entity != root_entity:
            results.append(CheckItem(
                status="amend",
                message=f"Claim {claim.id}: cross-category mismatch ({dep_entity} depends on {root_entity} claim {root.id}).",
                message_key="checks.preamble_cross_category_mismatch",
                details=f"Dependent '{dep_noun_raw}' vs independent '{root_noun}'",
                details_key="details.nounMismatch",
                details_params={"dependent": dep_noun_raw, "independent": root_noun},
            ))
            has_issue = True
        elif dep_noun_raw != root_noun:
            # Same category, different noun
            results.append(CheckItem(
                status="verify",
                message=f"Claim {claim.id}: preamble noun '{dep_noun_raw}' differs from independent claim '{root_noun}'.",
                message_key="checks.preamble_noun_mismatch",
                details=f"Claim {claim.id} depends on claim {root.id}",
                details_key="details.claimDependsOn",
                details_params={"claim": str(claim.id), "parent": str(root.id)},
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

_GENERIC_TERMS = {
    "system", "device", "method", "apparatus", "means", "step", "element",
    "member", "portion", "surface", "end", "side", "part",
}

_BOILERPLATE_TERMS = {
    "plurality", "embodiment", "thereof", "herein", "foregoing",
}


def check_spec_support(
    claims: list[Claim],
    spec_text: str,
    antecedent_flagged: list[dict] | None = None,
) -> list[UnsupportedTerm]:
    """Check that claim noun phrases have support in the specification.

    Three-tier matching: exact, stemmed, word-window.
    """
    from patentlint.analysis.utils import extract_noun_phrases

    spec_lower = spec_text.lower()
    spec_words = spec_lower.split()

    # Pre-stem spec words for tier 2
    spec_stemmed = set(_stemmer.stemWords(spec_words))

    # Build set of already-flagged antecedent basis terms
    ab_flagged: set[str] = set()
    if antecedent_flagged:
        for item in antecedent_flagged:
            ab_flagged.add(item["term"].lower())

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

            # Skip if already flagged by antecedent basis
            if phrase_lower in ab_flagged:
                continue

            tiers_checked: list[str] = []

            # Tier 1: Exact match
            tiers_checked.append("exact")
            if phrase_lower in spec_lower:
                continue

            # Tier 2: Stemmed match
            tiers_checked.append("stemmed")
            phrase_stems = set(_stemmer.stemWords(phrase_lower.split()))
            if phrase_stems and phrase_stems.issubset(spec_stemmed):
                continue

            # Tier 3: Word window (all words appear within 10-word window)
            tiers_checked.append("word_window")
            phrase_words = phrase_lower.split()
            if len(phrase_words) >= 2:
                found_window = False
                for i in range(len(spec_words) - len(phrase_words) + 1):
                    window = set(spec_words[i:i + 10])
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
