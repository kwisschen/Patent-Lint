"""Claim-level structural analysis.

Checks for missing periods, extra periods, dependencies, similarity, and sequentiality.
"""

import re
from typing import Optional

from patentlint.models import Claim


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


# Captures noun phrases (1-3 words) after "the"/"said" or "a"/"an".
# Words in the phrase must not be common verbs/prepositions/conjunctions.
_STOP_WORDS = (
    r"(?:is|are|was|were|has|have|had|do|does|did|being|been|"
    r"of|to|from|with|and|or|that|which|for|by|on|in|at|"
    r"wherein|comprising|consisting|including|having|configured|"
    r"adapted|arranged|coupled|connected|mounted|disposed|"
    r"extends|provides|receives|generates|produces|performs|"
    r"executes|transmits|operates|determines|defines|forms|"
    r"supports|enables|allows|causes|includes|contains|"
    r"a|an|the|said)"
)

_DEFINITE_REF = re.compile(
    rf"\b(?:the|said)\s+((?:(?!{_STOP_WORDS}\b)\w+\s+){{0,2}}(?:(?!{_STOP_WORDS}\b)\w+))",
    re.IGNORECASE,
)

_INDEFINITE_REF = re.compile(
    rf"\b(?:a|an)\s+((?:(?!{_STOP_WORDS}\b)\w+\s+){{0,2}}(?:(?!{_STOP_WORDS}\b)\w+))",
    re.IGNORECASE,
)

_SKIP_TERMS = {"invention", "present invention", "same", "following", "above", "below"}


def check_antecedent_basis(claims: list[Claim]) -> list[dict]:
    """Check for missing antecedent basis in claims.

    For each claim, find "the [noun phrase]" and "said [noun phrase]".
    Check whether "a [noun phrase]" or "an [noun phrase]" appears earlier
    in the same claim or in any ancestor claim.

    Returns: [{"claim_id": int, "term": str}, ...]
    """
    def get_ancestor_text(claim: Claim, all_claims: list[Claim]) -> str:
        texts = [claim.text.lower()]
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
            texts.append(parent.text.lower())
            current = parent
        return " ".join(texts)

    issues: list[dict] = []

    for claim in claims:
        full_text = get_ancestor_text(claim, claims)
        claim_text_lower = claim.text.lower()

        intros: set[str] = set()
        for m in _INDEFINITE_REF.finditer(full_text):
            intros.add(m.group(1).strip())

        for m in _DEFINITE_REF.finditer(claim_text_lower):
            term = m.group(1).strip()
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
