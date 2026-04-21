# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""CN claim parser — extract claims from Chinese patent .docx text."""

from __future__ import annotations

import re

from patentlint.models import Claim

# Claim number: "1." or "1．" or "1。" at start of line
_CN_CLAIM_NUM = re.compile(r"^[\s\u3000]*(\d+)\s*[.．。]\s*", re.MULTILINE)

# Mid-paragraph claim boundary: drafters sometimes pack two claims into one
# Word paragraph (no newline between them). Preprocessing inserts a newline
# before a digit+dot token that is preceded by sentence-end punctuation +
# whitespace OR by ≥2 whitespace chars, AND followed by a claim-start
# content character. The lookahead guards against false positives on
# step references (`步骤S2`, `2.3`), inline enumerations, and formulas.
_MID_PARAGRAPH_CLAIM_BOUNDARY = re.compile(
    r"(?:(?<=[。；！？])[\s\u3000]+|(?<=[\s\u3000]{2}))"
    r"(\d+)[\s\u3000]*[.．。][\s\u3000]*"
    r"(?=[一如根其权依包对将在本])"
)

# Dependency — covers all real-world CN dependent-claim forms:
#   prefix   : 如 | 根据 | 依据 | bare (dominant form in real CNIPA
#              filings is 根据权利要求N所述的; bare form seen in older
#              filings as 权利要求N的)
#   numspec  : N               (single)
#              N{至,到,-}M[中任一/意项]  (range)
#              N或M              (disjunction)
#              N、M[、...][或K]   (enumeration)
#   suffix   : 所述的 | 所述 | bare
#
# The full spec (post-prefix, pre-suffix) is captured in named group
# ``spec`` and expanded into a parent-claim list by
# ``_expand_dependency_spec``.
_NUMSPEC_RANGE = r"\d+\s*[至到\-]\s*\d+(?:\s*中?\s*任[一意]\s*项)?"
_NUMSPEC_ENUM = r"\d+(?:\s*[、,]\s*\d+)+(?:\s*或\s*\d+)?"
_NUMSPEC_OR = r"\d+\s*或\s*\d+"
_NUMSPEC_SINGLE = r"\d+"
_CN_DEPENDENCY = re.compile(
    r"(?:如|根据|依据)?\s*权利要求\s*"
    r"(?P<spec>"
    + f"(?:{_NUMSPEC_RANGE}|{_NUMSPEC_ENUM}|{_NUMSPEC_OR}|{_NUMSPEC_SINGLE})"
    + r")"
    r"\s*(?:所述的?)?"
)


def _expand_dependency_spec(spec: str) -> list[int]:
    """Expand a dependency spec string into a list of parent claim numbers.

    Accepts the four numspec forms recognized by ``_CN_DEPENDENCY``:

    - ``"1"``              → ``[1]``
    - ``"1至5中任一项"``    → ``[1, 2, 3, 4, 5]``
    - ``"1或3"``            → ``[1, 3]``
    - ``"1、2或3"``         → ``[1, 2, 3]``
    """
    s = re.sub(r"\s+", "", spec)
    # Range form first — contains 至/到/- between the two numbers.
    m = re.match(r"^(\d+)[至到\-](\d+)(?:中?任[一意]项)?$", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        lo, hi = (a, b) if a <= b else (b, a)
        return list(range(lo, hi + 1))
    # Enumeration / disjunction — split on 、 and 或.
    parts = re.split(r"[、,或]", s)
    return [int(p) for p in parts if p.isdigit()]


def parse_cn_claims_docx(text: str) -> list[Claim]:
    """Parse claims from CN patent .docx text.

    CN claims in .docx use plain Arabic numerals: '1.', '2.', etc.
    Dependencies follow the '如权利要求N所述的' format.
    """
    if not text.strip():
        return []

    text = _MID_PARAGRAPH_CLAIM_BOUNDARY.sub(
        lambda m: "\n" + m.group(0).lstrip(), text
    )

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
            deps.extend(_expand_dependency_spec(dep_match.group("spec")))

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
