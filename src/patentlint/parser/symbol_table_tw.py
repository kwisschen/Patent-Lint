# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""TW symbol table parser — 符號說明 and 代表圖之符號簡單說明."""

from __future__ import annotations

import re

from patentlint.models import SymbolEntry

# Matches: numeral + separator + name
# Separators: ‧ (U+2027), · (U+00B7), . (ASCII), … (ellipsis), ： (fullwidth colon),
#             : (ASCII colon), tab, or sequences of dots/middle dots
TW_SYMBOL_PATTERN = re.compile(
    r"^([A-Za-z0-9~\-]+)\s*"
    r"(?:[‧·.…：:\t]\s*[‧·.…]*\s*|\s{2,})"
    r"(.+)$"
)


def parse_tw_symbol_table(lines: list[str]) -> list[SymbolEntry]:
    """Parse TW symbol table entries from 符號說明 or 代表圖之符號簡單說明 lines.

    Each line is expected to be: numeral + separator + name.
    Handles ‧‧‧, ..., tab, and colon separators.
    """
    entries: list[SymbolEntry] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        m = TW_SYMBOL_PATTERN.match(stripped)
        if m:
            numeral = m.group(1).strip()
            name = m.group(2).strip()
            if numeral and name:
                entries.append(SymbolEntry(numeral=numeral, name=name))
    return entries
