# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""TW claim parser — extract claims from Taiwan patent .docx text."""

from __future__ import annotations

import re

from patentlint.models import Claim

# Claim number: "1." or "1．" at start of line (possibly with leading whitespace)
_TW_CLAIM_NUM = re.compile(r"^[\s\u3000]*(\d+)\s*[.．]\s*", re.MULTILINE)

# Dependency patterns:
# 如請求項1所述之, 如請求項1之, 如請求項1或2之,
# 如請求項1~3中任一項所述之, 如請求項1至3中任一項之
_TW_DEP_PATTERN = re.compile(
    r"如請求項\s*"
    r"(\d+)"
    r"(?:\s*(?:~|至|到)\s*(\d+))?"
    r"((?:\s*(?:或|、)\s*\d+)*)"
    r"(?:\s*中\s*任一?項)?"
    r"\s*所?述?[之的]?"
)

# Extract individual numbers from the "或N、N" tail
_OR_NUMS = re.compile(r"(\d+)")


def parse_tw_claims(paragraphs: list[str]) -> list[Claim]:
    """Parse TW claims into Claim model objects.

    TW claims use Arabic numerals: '1.', '2.', etc.
    Dependencies use '如請求項N所述之' format.
    """
    text = "\n".join(paragraphs)
    if not text.strip():
        return []

    matches = list(_TW_CLAIM_NUM.finditer(text))
    if not matches:
        return []

    claims: list[Claim] = []
    for i, match in enumerate(matches):
        num = int(match.group(1))
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        claim_text = text[start:end].strip()

        deps: list[int] = []
        for dep_match in _TW_DEP_PATTERN.finditer(claim_text):
            dep_start = int(dep_match.group(1))
            dep_end_str = dep_match.group(2)
            or_tail = dep_match.group(3)

            if dep_end_str:
                # Range: 請求項1~3
                dep_end = int(dep_end_str)
                deps.extend(range(dep_start, dep_end + 1))
            else:
                deps.append(dep_start)

            # Additional numbers from "或N、N" tail
            if or_tail:
                for m in _OR_NUMS.finditer(or_tail):
                    deps.append(int(m.group(1)))

        # Deduplicate (keep self-refs for check detection downstream)
        deps = sorted(set(deps))

        claims.append(Claim(
            id=num,
            text=claim_text,
            independent=len(deps) == 0,
            dependencies=deps,
            multiple_dependent=len(deps) > 1,
            method_claim=False,
        ))

    return claims
