# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""TW symbol table parser — 符號說明 and 代表圖之符號簡單說明."""

from __future__ import annotations

import re

from patentlint.models import SymbolEntry

# Matches: numeral + separator + name
# Separators: ‧ (U+2027), · (U+00B7), . (ASCII), … (ellipsis), ： (fullwidth colon),
#             : (ASCII colon), tab, or sequences of dots/middle dots
TW_SYMBOL_PATTERN = re.compile(
    r"^([A-Za-z0-9~～\-、,，]+)\s*"
    r"(?:[‧·.…：:\t]\s*[‧·.…]*\s*|\s{2,})"
    r"(.+)$"
)

_NUMERAL_SEP_RE = re.compile(r"[、,，]")
# Range form: pure-digit endpoints joined by ASCII tilde, FW tilde, or hyphen.
# Hyphen-with-letter (43-a) is intentionally excluded — that's sub-suffix
# notation, not a range. Bounded to ≤30 expanded numerals to cap runaway
# (mirrors the CN _CN_REFNUM_RANGE convention).
_RANGE_RE = re.compile(r"^(\d+)\s*[~～\-]\s*(\d+)$")
# Letter-prefixed ranges where the upper bound is the literal `n` / `N`
# (drafter-shorthand for "and so on" — TIPO 符號說明 convention for
# enumerated families: `PHA1~PHAn`, `PR1~PRn`, `L1~Ln`, `C1~Cn`).
# Issue #159 — the symbol table declares `PR1~PRn` but spec uses `PR2`;
# the walker flagged PR2 as missing because the unbounded `n` end-marker
# wasn't recognized. Expanded to a safe cap (_MAX_LETTER_RANGE_EXPAND)
# so any `<prefix><k>` for 1 ≤ k ≤ cap is covered.
_LETTER_RANGE_OPEN_RE = re.compile(
    r"^([A-Z][A-Za-z]*?)(\d+)\s*[~～\-]\s*\1[nN]$"
)
# Letter-prefixed enumerated ranges (`LD1~LD5`).
_LETTER_RANGE_ENUM_RE = re.compile(
    r"^([A-Z][A-Za-z]*?)(\d+)\s*[~～\-]\s*\1(\d+)$"
)
_MAX_RANGE_SPAN = 30
# Cap for open-ended `<prefix>n` ranges. Drafters typically use up to ~10
# in practice (PHA1~PHA10 is already long); 20 is the safe ceiling that
# accommodates real drafts without exploding the symbol table.
_MAX_LETTER_RANGE_EXPAND = 20


def _expand_numeral_token(token: str) -> list[str]:
    """Expand a single numeral token into one-or-more concrete numerals.

    Plain numerals (`20`, `43a`, `LD1`, `43-a`) return as-is.
    Digit-only range notation (`20~25`, `20～25`, `20-25`) expands to the
    enumerated set when the span is within ``_MAX_RANGE_SPAN``; otherwise
    falls back to the raw token (parser stays loss-bounded).
    Letter-prefixed enumerated ranges (`LD1~LD5`) expand similarly with
    the same span cap; open-ended `<prefix>n` ranges (`PR1~PRn`) expand
    to `<prefix>1`..`<prefix>{_MAX_LETTER_RANGE_EXPAND}`.
    """
    m = _RANGE_RE.match(token)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        if end < start or (end - start) > _MAX_RANGE_SPAN:
            return [token]
        return [str(n) for n in range(start, end + 1)]
    # Letter-prefixed enumerated range: PR1~PR5 → [PR1, PR2, PR3, PR4, PR5]
    m = _LETTER_RANGE_ENUM_RE.match(token)
    if m:
        prefix = m.group(1)
        start, end = int(m.group(2)), int(m.group(3))
        if end < start or (end - start) > _MAX_RANGE_SPAN:
            return [token]
        return [f"{prefix}{n}" for n in range(start, end + 1)]
    # Letter-prefixed open range: PR1~PRn → [PR1, PR2, ..., PR{cap}]
    m = _LETTER_RANGE_OPEN_RE.match(token)
    if m:
        prefix = m.group(1)
        start = int(m.group(2))
        if start > _MAX_LETTER_RANGE_EXPAND:
            return [token]
        return [f"{prefix}{n}" for n in range(start, _MAX_LETTER_RANGE_EXPAND + 1)]
    return [token]


def parse_tw_symbol_table(lines: list[str]) -> list[SymbolEntry]:
    """Parse TW symbol table entries from 符號說明 or 代表圖之符號簡單說明 lines.

    Each line is expected to be: numeral + separator + name.
    Handles ‧‧‧, ..., tab, and colon separators. Multi-numeral entries
    like "100、100a:容器本體" or "100、101、102、103：隨身碟" are expanded
    into separate SymbolEntry instances sharing the same name.

    Range notation (`20~25:外殼系列`) is expanded so cross-reference checks
    against rep drawing don't FP when drafter uses range-shorthand in one
    section and enumerated form in the other (issues #61/#63).
    """
    entries: list[SymbolEntry] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        m = TW_SYMBOL_PATTERN.match(stripped)
        if m:
            numeral_part = m.group(1).strip()
            name = m.group(2).strip()
            if not name:
                continue
            for numeral in _NUMERAL_SEP_RE.split(numeral_part):
                numeral = numeral.strip()
                if not numeral:
                    continue
                for expanded in _expand_numeral_token(numeral):
                    entries.append(SymbolEntry(numeral=expanded, name=name))
    return entries
