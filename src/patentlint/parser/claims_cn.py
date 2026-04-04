# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""CN claim parser — extract claims from Chinese patent .docx text."""

from __future__ import annotations

import re

from patentlint.models import Claim

# Claim number: "1." or "1．" or "1。" at start of line
_CN_CLAIM_NUM = re.compile(r"^[\s\u3000]*(\d+)\s*[.．。]\s*", re.MULTILINE)

# Dependency: "如权利要求N所述的" with optional range and "任一项"
_CN_DEPENDENCY = re.compile(
    r"如权利要求\s*(\d+)\s*(?:[至到\-]\s*(\d+)\s*)?(?:中\s*)?(?:任[一意]\s*项\s*)?所述的"
)


def parse_cn_claims_docx(text: str) -> list[Claim]:
    """Parse claims from CN patent .docx text.

    CN claims in .docx use plain Arabic numerals: '1.', '2.', etc.
    Dependencies follow the '如权利要求N所述的' format.
    """
    if not text.strip():
        return []

    # Find all claim boundaries by number pattern
    matches = list(_CN_CLAIM_NUM.finditer(text))
    if not matches:
        return []

    claims: list[Claim] = []
    for i, match in enumerate(matches):
        num = int(match.group(1))
        # Claim text extends from this match to the next match (or end)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        claim_text = text[start:end].strip()

        # Extract dependencies
        deps: list[int] = []
        for dep_match in _CN_DEPENDENCY.finditer(claim_text):
            dep_start = int(dep_match.group(1))
            dep_end_str = dep_match.group(2)
            if dep_end_str:
                # Range: 权利要求1至3
                dep_end = int(dep_end_str)
                deps.extend(range(dep_start, dep_end + 1))
            else:
                deps.append(dep_start)

        # Remove self-references and deduplicate
        deps = sorted(set(d for d in deps if d != num))

        claims.append(Claim(
            id=num,
            text=claim_text,
            independent=len(deps) == 0,
            dependencies=deps,
            multiple_dependent=len(deps) > 1,
            method_claim=False,
        ))

    return claims
