# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
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
    # Range tail: allow an explicit ``請求項`` before the end number
    # (e.g. ``如請求項4至請求項10中任一項所述``).
    r"(?:\s*(?:~|至|到)\s*(?:請求項\s*)?(\d+))?"
    r"((?:\s*(?:或|、)\s*(?:請求項\s*)?\d+)*)"
    r"(?:\s*中\s*任一?項)?"
    r"\s*所?述?[之的]?"
)

# Extract individual numbers from the "或N、N" tail
_OR_NUMS = re.compile(r"(\d+)")

# Independent-claim preamble: `一種X` / `一個X` at the start of the claim
# body (after the "N. " number prefix). Per TIPO 專利法施行細則 §18, the
# statutory marker of an independent claim is the preamble subject form,
# not the absence of 如請求項N references — claims in 引用記載型式
# (quoted-reference format) use `一種X，具備如請求項N所述的Y` to declare
# a new invention subject X while incorporating claim N's Y by reference.
_TW_INDEP_PREAMBLE = re.compile(r"^(?:一種|一個)\s*")


def parse_tw_claims(paragraphs: list[str]) -> list[Claim]:
    """Parse TW claims into Claim model objects.

    TW claims use Arabic numerals: '1.', '2.', etc.
    Dependencies use '如請求項N所述之' format.

    Claim independence is classified by **preamble**, not by the absence of
    ``如請求項N`` references: claims in 引用記載型式 (quoted-reference
    format) have both a `一種X` preamble declaring a new subject AND a
    body-embedded `如請求項N所述的Y` that incorporates Y from claim N as a
    sub-component. Such claims are independent per §18 — the embedded
    reference is incorporation-by-reference, not a dependency. Treating
    them as dependent produces spurious subject-consistency, dependency-
    format, and multi-dep flags.
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

        # Strip the "N. " prefix to isolate the body for preamble check.
        body = _TW_CLAIM_NUM.sub("", claim_text, count=1).lstrip()
        has_indep_preamble = bool(_TW_INDEP_PREAMBLE.match(body))

        # Scan the full claim text for ``如請求項N所述`` refs. These are
        # routed to either ``dependencies`` (statutory parent) or
        # ``quoted_references`` (引用記載型式 incorporation-by-reference)
        # depending on the preamble form.
        refs: list[int] = []
        for dep_match in _TW_DEP_PATTERN.finditer(claim_text):
            dep_start = int(dep_match.group(1))
            dep_end_str = dep_match.group(2)
            or_tail = dep_match.group(3)

            if dep_end_str:
                # Range: 請求項1~3
                dep_end = int(dep_end_str)
                refs.extend(range(dep_start, dep_end + 1))
            else:
                refs.append(dep_start)

            # Additional numbers from "或N、N" tail
            if or_tail:
                for m in _OR_NUMS.finditer(or_tail):
                    refs.append(int(m.group(1)))

        # Deduplicate (keep self-refs for check detection downstream)
        refs = sorted(set(refs))

        if has_indep_preamble:
            # 引用記載型式 / pure independent: preamble declares a new
            # subject. Any 如請求項N in the body is incorporation-by-
            # reference for the walker's ancestor chain, NOT a statutory
            # dependency.
            deps: list[int] = []
            quoted_refs: list[int] = refs
            is_independent = True
        else:
            # Standard dependent (or multi-dependent) preamble: the refs
            # are statutory parent claims.
            deps = refs
            quoted_refs = []
            is_independent = len(deps) == 0

        claims.append(Claim(
            id=num,
            text=claim_text,
            independent=is_independent,
            dependencies=deps,
            quoted_references=quoted_refs,
            multiple_dependent=len(deps) > 1,
            method_claim=False,
        ))

    return claims
