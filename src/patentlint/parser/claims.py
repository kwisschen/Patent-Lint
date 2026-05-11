# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
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

# PDF→text whitespace collapse: dep-preamble "of claim N" sometimes loses
# its space ("ofclaim N") in machine-translated/PDF-extract pipelines. The
# walker then fails to match the dep-preamble exclusion and emits the
# whole "the X ofclaim N" as a §112(b) reference. Normalize so downstream
# regexes (incl. _DEP_REF above and the dep-preamble body-scan exclusion)
# see canonical spacing. Idempotent on already-spaced text.
#
# R35 (2026-05-04): widened from `of\s*claims?` to `(of|to)\s*claims?`.
# US round-1 corpus has 564 `toclaim N` occurrences (`according toclaim 7`)
# in addition to 10316 `ofclaim` occurrences — same root cause (Google
# Patents PDF→HTML extraction collapses prep-then-claim whitespace).
# Without `to` coverage, dep-claims using `according to claim N` form
# parsed as independent → broken chain → walker_fp inflation.
_OFCLAIM_FIX = re.compile(r"\b(of|to)\s*(claims?)\b", re.IGNORECASE)

# R35 (2026-05-04): claim-number → following-word boundary fix. After
# the OFCLAIM normalization above, US corpus still has 1257 occurrences
# of `claim N<word>` (no space between digit and following letter):
# `claim 1wherein` 825x, `claim 1further` 214x, `claim 1comprising` 105x,
# `claim 1where` 36x, etc. Python regex `\b` requires a non-word char
# between the digit and the next letter to fire — without this fix, the
# `_DEP_REF` regex (`claims?\s+\d+\b`) misses these and the affected
# dep-claim falls back to independent classification → ancestor chain
# empty → walker emits spurious antecedent findings on every body
# reference. Idempotent on already-spaced text.
_CLAIM_NUM_BOUNDARY_FIX = re.compile(
    r"(\bclaims?\s+\d+)([a-zA-Z])", re.IGNORECASE
)

# Pattern to detect multiple dependency
_MULTIPLE_DEP = re.compile(
    r"claim(s)?\s+\d+\s*(to|and|or|-)\s*(claim(s)?\s+)?\d+",
    re.IGNORECASE,
)

# MPEP § 2173.01: restrictive absolutes. Over-qualifying a claim limitation
# with absolute language ("must," "essential," "required," etc.) unnecessarily
# narrows scope and can create §112(b) indefiniteness when the specification
# doesn't actually require the absoluteness asserted.
_RESTRICTIVE_ABSOLUTES_CLAIM_RE = re.compile(
    r"\b(always|never|must|solely|every|required|essential|critical|key|vital)\b",
    re.IGNORECASE,
)

# MPEP § 2173.05(b): relative / indefinite terminology. Covers probabilistic
# modals, approximation adverbs, frequency qualifiers, relative adjectives,
# and open-ended exemplars that each leave claim scope unclear.
_INDEFINITE_WORDING_CLAIM_RE = re.compile(
    r"\b("
    r"may|might|can|could|should"
    r"|substantially|approximately|capable of|about"
    r"|generally|normally|typically|usually"
    r"|relatively|fairly|reasonably"
    r"|essentially|similar|comparable"
    r"|close|near|fast|slow|hard|soft|wide|narrow"
    r"|preferably|or the like"
    r")\b"
    r"|\b(for example|such as|kind of|type of)\b",
    re.IGNORECASE,
)

# Notes on intentionally-excluded tokens (vs. the pre-split history):
# - "means", "step": § 112(f) MPF triggers handled by detect_means_plus_function;
#   keeping them here would double-flag the same token under two checks.
# - "improved", "optimized": no § 2173 support; pure puffery, not indefiniteness.
# - "invention": standalone self-reference is legitimate in many claims (e.g.
#   antecedent-basis patterns); not a § 2173.01 absolute. Removed to cut noise.
# - "it", "high", "low", "long", "short": removed in a prior pass (too many FPs).

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
        # Lowercase the preposition (of/to) to match the original
        # ofclaim-fix behavior; preserve the `Claim`/`claim` capitalization.
        claim_text = _OFCLAIM_FIX.sub(
            lambda m: f"{m.group(1).lower()} {m.group(2)}",
            match.group(2).strip(),
        )
        claim_text = _CLAIM_NUM_BOUNDARY_FIX.sub(r"\1 \2", claim_text)

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


def _scan_claims(pattern: re.Pattern, claims: list[Claim]) -> ClaimWordingResult:
    flagged: list[int] = []
    parts: list[str] = []
    for claim in claims:
        for match in pattern.finditer(claim.text):
            matched = match.group(1) or (match.group(2) if match.lastindex and match.lastindex >= 2 else None)
            if matched is None:
                matched = match.group(0)
            if claim.id not in flagged:
                flagged.append(claim.id)
            parts.append(f'[{claim.id}] → "{matched}"\n              ')
    return ClaimWordingResult(improper_claims=flagged, formatted_phrases="".join(parts))


def detect_restrictive_absolutes_in_claims(claims: list[Claim]) -> ClaimWordingResult:
    """Detect MPEP § 2173.01 restrictive absolutes (must, essential, always, etc.)."""
    return _scan_claims(_RESTRICTIVE_ABSOLUTES_CLAIM_RE, claims)


def detect_indefinite_wording_in_claims(claims: list[Claim]) -> ClaimWordingResult:
    """Detect MPEP § 2173.05(b) relative/indefinite terminology (may, substantially,
    approximately, generally, typically, relatively, similar, preferably, for example, etc.)."""
    return _scan_claims(_INDEFINITE_WORDING_CLAIM_RE, claims)
