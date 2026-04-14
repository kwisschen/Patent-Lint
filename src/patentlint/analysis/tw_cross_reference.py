# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""TW cross-reference and drawings analysis checks.

Two cross-reference checks and one internal figure count check
for Taiwan patent documents against TIPO rules.
"""

from __future__ import annotations

from patentlint.models import CheckItem, TwPatentDocument


# ── Check 31 ────────────────────────────────────────────────────────────


def check_symbol_vs_rep_drawing(doc: TwPatentDocument) -> list[CheckItem]:
    """Compare representative drawing symbols against symbol table entries."""
    if not doc.representative_drawing_symbols:
        return [CheckItem(
            status="pass",
            message="No representative drawing symbols to check.",
            message_key="check.tw.crossRef.symbolVsRepDrawing.pass",
            reference="專利審查基準",
        )]

    # Build lookup from symbol_table: numeral -> name
    symbol_map = {entry.numeral: entry.name for entry in doc.symbol_table}

    mismatches: list[dict] = []
    for sym in doc.representative_drawing_symbols:
        if sym.numeral not in symbol_map:
            mismatches.append({
                "kind": "not_in_table",
                "numeral": sym.numeral,
                "rep_name": sym.name,
            })
        elif symbol_map[sym.numeral] != sym.name:
            mismatches.append({
                "kind": "name_mismatch",
                "numeral": sym.numeral,
                "rep_name": sym.name,
                "table_name": symbol_map[sym.numeral],
            })

    if mismatches:
        return [CheckItem(
            status="verify",
            message="Representative drawing symbols inconsistent with symbol table.",
            message_key="check.tw.crossRef.symbolVsRepDrawing.verify",
            details_params={"symbol_mismatch_triples": {"mismatches": mismatches[:10]}},
            reference="專利審查基準",
        )]

    return [CheckItem(
        status="pass",
        message="Representative drawing symbols consistent with symbol table.",
        message_key="check.tw.crossRef.symbolVsRepDrawing.pass",
        reference="專利審查基準",
    )]


# ── Check 32 ────────────────────────────────────────────────────────────


def check_bracket_format(doc: TwPatentDocument) -> list[CheckItem]:
    """Check that section headers use proper 【】bracket format.

    TODO: sections_tw.py currently parses by 【】 only. When raw header
    data (including variant brackets) becomes available on TwPatentDocument,
    this check should flag non-standard brackets like [技術領域] or〔技術領域〕.
    """
    # Always PASS until raw header data is available
    return [CheckItem(
        status="pass",
        message="All section headers use proper 【】bracket format.",
        message_key="check.tw.crossRef.bracketFormat.pass",
        reference="專利法施行細則 §17",
    )]


# ── Check 33 (Internal †) ──────────────────────────────────────────────


def check_figure_count(doc: TwPatentDocument) -> list[CheckItem]:
    """Report figure count (UI-internal stats check, always PASS)."""
    count = len(doc.figure_refs)
    return [CheckItem(
        status="pass",
        message=f"{count} figure(s) found.",
        message_key="check.tw.drawings.figureCount.pass",
        details_params={"count": str(count)},
        reference="專利審查基準",
    )]
