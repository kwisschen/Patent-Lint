# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Patent claim parsing and analysis.

Parses claim text into structured Claim objects and detects
wording/formatting issues. Patterns validated against real U.S. patent conventions.
"""

import re

from patentlint.models import Claim, ClaimWordingResult

# Pattern to detect claim dependency references.
# Supports: "claim 1", "claims 1-3", "according to claim 1",
# "as recited in claim 1", "as set forth in claim 1", "as defined in claim 1"
_DEP_REF = re.compile(
    r"\b("
    r"(according\s+to\s+)?"
    r"|(as\s+(recited|set\s+forth|defined)\s+in\s+)"
    r")?"
    r"claims?\s+\d+(?:\s*(?:to|and|or|-)\s*\d+)?\b",
    re.IGNORECASE,
)

# Pattern to match individual claim blocks.
# Uses [\r\n] instead of \n for cross-platform .docx compatibility.
_CLAIM_BLOCK = re.compile(
    r"(?m)^\s*(\d{1,3})\.\s*(.*?)(?=[\r\n]+\s*\d{1,3}\.\s|\Z)",
    re.DOTALL,
)

# Pattern to detect multiple dependency
_MULTIPLE_DEP = re.compile(
    r"claim(s)?\s+\d+\s*(to|and|or|-)\s*(claim(s)?\s+)?\d+",
    re.IGNORECASE,
)

# Improper/indefinite wording pattern for claims.
# Split into categories for future per-category severity:
# - Absolute terms (MPEP 2173.01): invention, always, never, must, solely, every, required, essential, critical, key, vital
# - Relative/indefinite terms (MPEP 2173.05(b)): substantially, approximately, about, capable of, etc.
# - Potentially indefinite: may, might, can, could, should
# - 112(f) triggers: means, step (flagged for awareness, not necessarily errors)
#
# REMOVED from original: "it" (too many false positives — appears in nearly every claim),
# "high", "low" (legitimate as modifiers: "high-frequency", "low-power"),
# "long", "short" (legitimate in many contexts: "short-range", "long-lived")
# ADDED: "preferably", "for example", "such as", "or the like", "type of", "kind of"
_IMPROPER_CLAIM_WORDING = re.compile(
    r"\b("
    r"invention|always|never|must|solely|every|required|essential|critical|key|vital"
    r"|may|might|can|could|should"
    r"|substantially|approximately|capable of|about"
    r"|generally|normally|typically|usually"
    r"|relatively|fairly|reasonably"
    r"|essentially|similar|comparable"
    r"|means|step|improved|optimized"
    r"|close|near|fast|slow|hard|soft|wide|narrow"
    r"|preferably|or the like"
    r")\b"
    r"|\b(for example|such as|kind of|type of)\b",
    re.IGNORECASE,
)

# Words that require a comma after "wherein"
_WORDS_REQUIRING_COMMA = [
    "when", "after", "before", "during", "once", "while", "upon", "according",
    "unless", "provided that", "assuming", "contingent upon", "depending on",
    "because", "since", "due to", "owing to", "given that", "considering that",
    "whereas", "as opposed to", "relative to", "between", "among", "within", "based on",
    "if", "as", "on", "under", "in", "at", "for", "along",
]


def is_method_claim(text: str) -> bool:
    """A claim is a method claim if 'method' appears before the first comma."""
    comma_idx = text.find(",")
    method_idx = text.lower().find("method")
    return method_idx != -1 and (comma_idx == -1 or method_idx < comma_idx)


def parse_dependencies(text: str, independent: bool, claim_number: int) -> list[int]:
    """Extract dependency claim numbers from claim text.

    Self-references (e.g., claim 11 listing itself as a parent) are silently
    dropped: such input is parser noise from malformed source, but it causes
    infinite loops in BFS antecedent walkers.
    """
    if independent:
        return []
    dependencies = [
        int(m.group(1)) for m in re.finditer(r"\bclaims?\s*(\d+)\b", text, re.IGNORECASE)
    ]
    return [d for d in dependencies if d != claim_number]


def parse_claims(claims_text: str) -> list[Claim]:
    """Parse raw claims section text into a list of Claim objects.

    Strips all known claims headers before parsing individual claim blocks.
    """
    cleaned = re.sub(r"(?is)^\s*CLAIMS\s*", "", claims_text)
    cleaned = re.sub(
        r"(?is)^\s*(What\s+is\s+claimed\s+is|I\s+claim|We\s+(hereby\s+)?claim|Claimed\s+are)\s*:\s*",
        "",
        cleaned,
    )

    if not cleaned.strip():
        return []

    claims = []
    for match in _CLAIM_BLOCK.finditer(cleaned):
        claim_number = int(match.group(1))
        claim_text = match.group(2).strip()

        independent = not _DEP_REF.search(claim_text)
        multiple_dependent = bool(_MULTIPLE_DEP.search(claim_text))
        method = is_method_claim(claim_text)
        dependencies = parse_dependencies(claim_text, independent, claim_number)

        claims.append(Claim(
            id=claim_number,
            text=claim_text,
            independent=independent,
            multiple_dependent=multiple_dependent,
            method_claim=method,
            dependencies=dependencies,
        ))

    return claims


_PARENTHETICAL_PREPS = {"in", "on", "at", "for", "by", "with", "from", "of", "to", "during", "after", "before", "under", "over", "between", "among", "within", "along", "through", "across", "upon"}


def _is_parenthetical_prep_phrase(text_after_comma: str) -> bool:
    """Detect parenthetical prepositional phrases: 'wherein, <prep ...>, <clause>'.

    Pattern: text starts with a preposition and contains another comma
    within ~60 characters, indicating a parenthetical insertion where both
    commas are grammatically correct.
    """
    stripped = text_after_comma.strip().lower()
    first_word = stripped.split()[0] if stripped.split() else ""
    if first_word not in _PARENTHETICAL_PREPS:
        return False
    second_comma = stripped.find(",")
    return 0 < second_comma <= 60


def detect_wherein_issue(claim_text: str) -> bool:
    """Check a single claim for wherein comma issues. Returns True if issue found."""
    for match in re.finditer(r"\bwherein\b", claim_text, re.IGNORECASE):
        wherein_idx = match.start()
        following = claim_text[wherein_idx + 7:].strip()

        if not following:
            continue

        has_comma = following.startswith(",")
        remaining = following.lstrip(",").strip().lower()

        # Skip parenthetical prepositional phrases: "wherein, in each group, the..."
        if has_comma and _is_parenthetical_prep_phrase(remaining):
            continue

        requires_comma = False

        for phrase in _WORDS_REQUIRING_COMMA:
            if remaining == phrase:
                requires_comma = True
                break

            if " " in phrase and remaining.startswith(phrase + " "):
                requires_comma = True
                break

            if " " not in phrase and remaining.startswith(phrase + " "):
                after_phrase = remaining[len(phrase):].strip()
                tokens = after_phrase.split()
                if tokens:
                    next_word = tokens[0]
                    if not re.match(
                        r"(?i)least|most|several|many|few|each|every|any|some|all",
                        next_word,
                    ):
                        requires_comma = True
                        break

        if (requires_comma and not has_comma) or (not requires_comma and has_comma):
            return True

    return False


def detect_incorrect_wherein_commas(claims: list[Claim]) -> list[int]:
    """Returns list of claim IDs with incorrect wherein comma usage."""
    return [c.id for c in claims if detect_wherein_issue(c.text)]


def detect_improper_claim_wording(claims: list[Claim]) -> ClaimWordingResult:
    """Detect improper/indefinite wording in claims."""
    improper_claims: list[int] = []
    phrases_parts: list[str] = []

    for claim in claims:
        for match in _IMPROPER_CLAIM_WORDING.finditer(claim.text):
            matched = match.group(1) or match.group(2)  # group(1) for single words, group(2) for multi-word
            if claim.id not in improper_claims:
                improper_claims.append(claim.id)
            phrases_parts.append(f'[{claim.id}] → "{matched}"\n              ')

    return ClaimWordingResult(
        improper_claims=improper_claims,
        formatted_phrases="".join(phrases_parts),
    )
