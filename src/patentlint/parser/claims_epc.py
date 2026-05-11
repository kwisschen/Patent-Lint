# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Claim parser for EPC English drafts.

EPC claim format under Rule 43 EPC:
  - Sequential Arabic numbering (Rule 43(5)).
  - Independent claims: ``1. A method comprising...``
  - Dependent claims: ``2. A method according to claim 1, wherein...``
    or ``2. A method according to any preceding claim, wherein...``
    or ``2. A method according to any one of claims 1 to 3, wherein...``
  - Reference signs in parentheses (Rule 43(7)).
  - Two-part form preamble + characterising portion (Rule 43(1), conditional).

EPC-specific dependency phrasings v1 recognises:
  - ``claim N`` / ``claims N``                (simple)
  - ``claim N and M`` / ``claim N or M``      (multi-dep)
  - ``claims N to M`` / ``claims N-M``        (range, multi-dep)
  - ``any of claims N to M``                  (range, multi-dep)
  - ``any one of claims N to M``              (range, multi-dep)
  - ``any preceding claim``                   (depends on all 1..N-1)

The "any preceding claim" form is uniquely EPC; the US parser does not
need to handle it. v1 expands this form into a concrete dependency list
(1..N-1) at parse time so downstream walker logic sees a normal numeric
dependency list rather than a sentinel.
"""

from __future__ import annotations

import re

from patentlint.models import Claim


# Claim-block boundary: "<num>. <body>" until the next "<num>. " or EOF.
# Mirrors the US parser's _CLAIM_BLOCK.
_CLAIM_BLOCK_EPC = re.compile(
    r"(?m)^\s*(\d{1,3})\.\s*(.*?)(?=[\r\n]+\s*\d{1,3}\.\s|\Z)",
    re.DOTALL,
)

# Independent / dependent detector: any reference to "claim N" or
# "any preceding claim" makes the claim dependent. Case-insensitive.
_DEP_REF_EPC = re.compile(
    r"\b("
    r"any\s+preceding\s+claim"
    r"|any(?:\s+one)?\s+of\s+claims?\s+\d+(?:\s*(?:to|and|or|-)\s*\d+)?"
    r"|according\s+to\s+claims?\s+\d+(?:\s*(?:to|and|or|-)\s*\d+)?"
    r"|claims?\s+\d+(?:\s*(?:to|and|or|-)\s*\d+)?"
    r")\b",
    re.IGNORECASE,
)

# Multi-dep detection. Catches:
#   - "claims 1 to 5", "claims 1-5"  → range
#   - "claim 2 or 3", "claim 2 and 3" → alternative
#   - "any preceding claim"          → multi-dep on all prior
#   - "any of claims 1 to 5"         → range
_MULTIPLE_DEP_EPC = re.compile(
    r"any\s+preceding\s+claim"
    r"|any(?:\s+one)?\s+of\s+claims?\s+\d+\s*(?:to|and|or|-)\s*\d+"
    r"|claims?\s+\d+\s*(?:to|and|or|-)\s*(?:claims?\s+)?\d+",
    re.IGNORECASE,
)


def is_method_claim_epc(text: str) -> bool:
    """A claim is a method claim if 'method' or 'process' appears before the
    first comma. EPC drafters sometimes use 'process' instead of 'method'.
    """
    comma_idx = text.find(",")
    lower = text.lower()
    method_idx = lower.find("method")
    process_idx = lower.find("process")
    earliest = min((i for i in (method_idx, process_idx) if i != -1), default=-1)
    return earliest != -1 and (comma_idx == -1 or earliest < comma_idx)


def parse_dependencies_epc(
    text: str,
    independent: bool,
    claim_number: int,
) -> list[int]:
    """Extract dependency claim numbers from claim text.

    Returns a list of parent claim IDs. Handles EPC-specific forms:
      - "any preceding claim" → all integers 1..(claim_number-1)
      - "claims N to M" / "claims N-M" → range N..M
      - "claim N", "claim N and M", "claim N or M" → enumerated
    Self-references are silently dropped (parser noise guard).
    """
    if independent:
        return []

    deps: set[int] = set()

    # "any preceding claim" — depends on all earlier claims
    if re.search(r"\bany\s+preceding\s+claim\b", text, re.IGNORECASE):
        deps.update(range(1, claim_number))

    # "any (one) of claims N to M" / "claims N to M" / "claims N-M"
    for m in re.finditer(
        r"\bclaims?\s+(\d+)\s*(?:to|-)\s*(\d+)\b",
        text, re.IGNORECASE,
    ):
        start, end = int(m.group(1)), int(m.group(2))
        if start <= end:
            deps.update(range(start, end + 1))

    # "claims N and M" / "claim N or M"
    for m in re.finditer(
        r"\bclaims?\s+(\d+)\s*(?:and|or)\s*(?:claims?\s+)?(\d+)\b",
        text, re.IGNORECASE,
    ):
        deps.add(int(m.group(1)))
        deps.add(int(m.group(2)))

    # Simple "claim N" references
    for m in re.finditer(r"\bclaims?\s+(\d+)\b", text, re.IGNORECASE):
        deps.add(int(m.group(1)))

    # Drop self-reference (malformed source guard)
    deps.discard(claim_number)
    return sorted(deps)


def parse_claims_epc(claims_section: str) -> list[Claim]:
    """Parse raw EPC claims-section text into a list of Claim objects.

    Strips known claims headers ("CLAIMS", "What is claimed is:", etc.)
    before parsing individual claim blocks. The dependency list on each
    Claim object reflects the resolved-and-expanded form (e.g.,
    "any preceding claim" on claim 5 yields dependencies=[1, 2, 3, 4]).
    """
    cleaned = re.sub(r"(?is)^\s*CLAIMS\s*", "", claims_section)
    cleaned = re.sub(
        r"(?is)^\s*(What\s+is\s+claimed\s+is|I\s+claim|We\s+(hereby\s+)?claim|Claimed\s+are)\s*:\s*",
        "",
        cleaned,
    )
    if not cleaned.strip():
        return []

    claims: list[Claim] = []
    for match in _CLAIM_BLOCK_EPC.finditer(cleaned):
        claim_number = int(match.group(1))
        claim_text = match.group(2).strip()

        independent = not _DEP_REF_EPC.search(claim_text)
        multiple_dependent = bool(_MULTIPLE_DEP_EPC.search(claim_text))
        method = is_method_claim_epc(claim_text)
        dependencies = parse_dependencies_epc(claim_text, independent, claim_number)

        claims.append(Claim(
            id=claim_number,
            text=claim_text,
            independent=independent,
            multiple_dependent=multiple_dependent,
            method_claim=method,
            dependencies=dependencies,
        ))
    return claims
