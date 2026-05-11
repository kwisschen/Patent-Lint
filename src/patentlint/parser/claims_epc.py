# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Claim parser for EPC English drafts.

EPC claim format under Rule 43:
  - Sequential Arabic numbering ("1.", "2.", ...) — Rule 43(5)
  - Dependent claims explicitly reference parent ("A device according to
    claim N, characterised in that ...") — Rule 43(4)
  - Reference signs in parentheses, non-limiting — Rule 43(7)
  - Two-part form (preamble + characterising portion) "where appropriate" —
    Rule 43(1); CONDITIONAL, not mandatory

The US claim parser (``parser/claims.py``) is the foundation: EPC claims share
the Arabic numbering and dependency-by-explicit-reference structure. v1 port
copies the US parser entry points and tunes the dependency-extraction regex
for EPC-specific phrasing ("claim N", "claims N and M", "any preceding claim",
"any one of claims N to M"). The Rule 43(1) two-part-form recognition lands as
a separate advisory check, not as a parser-level requirement.

Stubs only at scaffolding stage.
"""

from __future__ import annotations

from patentlint.models import Claim


def parse_claims_epc(claims_section: str) -> list[Claim]:
    """Parse EPC claims from a claims-section text block.

    Stub: returns empty list. Real implementation follows the US
    ``parser/claims.py::parse_claims`` shape with EPC-specific dependency
    regex.
    """
    return []
