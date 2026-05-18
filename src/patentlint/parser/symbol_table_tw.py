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
_MAX_RANGE_SPAN = 30


def _expand_numeral_token(token: str) -> list[str]:
    """Expand a single numeral token into one-or-more concrete numerals.

    Plain numerals (`20`, `43a`, `LD1`, `43-a`) return as-is.
    Range notation (`20~25`, `20～25`, `20-25` digit-only) expands to the
    enumerated set when the span is within ``_MAX_RANGE_SPAN``; otherwise
    falls back to the raw token (parser stays loss-bounded).
    """
    m = _RANGE_RE.match(token)
    if not m:
        return [token]
    start, end = int(m.group(1)), int(m.group(2))
    if end < start or (end - start) > _MAX_RANGE_SPAN:
        return [token]
    return [str(n) for n in range(start, end + 1)]


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
