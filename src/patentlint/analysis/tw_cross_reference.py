# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""TW cross-reference and drawings analysis checks.

Two cross-reference checks and one internal figure count check
for Taiwan patent documents against TIPO rules.
"""

from __future__ import annotations

import re

from patentlint.models import CheckItem, TwPatentDocument

_FIG_NUM_RE = re.compile(r"(\d+)")


# ── Check 31 ────────────────────────────────────────────────────────────


def check_symbol_vs_rep_drawing(doc: TwPatentDocument) -> list[CheckItem]:
    """Compare representative drawing symbols against symbol table entries.

    Returns an empty list when the document does not carry a 代表圖之符號簡單說明
    section, suppressing the check card entirely for that document.
    """
    if not doc.representative_drawing_symbols:
        return []

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
            details_key="details.tw.symbolVsRepDrawing.description",
            details_params={"symbol_mismatch_triples": {"mismatches": mismatches[:10]}},
            reference="專利審查基準",
        )]

    return [CheckItem(
        status="pass",
        message="Representative drawing symbols consistent with symbol table.",
        message_key="check.tw.crossRef.symbolVsRepDrawing.pass",
        details_key="details.tw.symbolVsRepDrawing.description",
        reference="專利審查基準",
    )]


# ── Check 32 ────────────────────────────────────────────────────────────


def check_bracket_format(doc: TwPatentDocument) -> list[CheckItem]:
    """Flag canonical TIPO section headers that lack the required 【】 brackets.

    Consumes ``TwPatentDocument.bracketless_section_headers``, populated by
    ``sections_tw._find_bracketless_section_headers``. Detects both bare
    canonical names (``先前技術`` alone on a line) and variant-bracket forms
    (``[先前技術]``, ``〔先前技術〕``, ``(先前技術)``, ``（先前技術）``) per
    專利法施行細則 §17.
    """
    flagged = doc.bracketless_section_headers
    if not flagged:
        return [CheckItem(
            status="pass",
            message="All section headers use the required 【】 bracket format.",
            message_key="check.tw.crossRef.bracketFormat.pass",
            reference="專利法施行細則 §17",
        )]

    headers_str = ", ".join(flagged[:10])
    return [CheckItem(
        status="verify",
        message=(
            "Section headers not in the required 【】 bracket format: "
            f"{headers_str}."
        ),
        message_key="check.tw.crossRef.bracketFormat.verify",
        details_params={"headers": headers_str},
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


# ── Check 34 ───────────────────────────────────────────────────────────


def check_figures_sequential(doc: TwPatentDocument) -> list[CheckItem]:
    """Check that figure numbers form a contiguous 1..N set with no gaps.

    Sub-figure suffixes (圖1A, 圖1B, 第1圖(a)) are collapsed onto their
    parent figure number. Ranges and list forms in the source text are
    already expanded by ``TW_PARSER`` before reaching ``doc.figure_refs``.
    """
    numbers: set[int] = set()
    for fid in doc.figure_refs:
        m = _FIG_NUM_RE.match(fid)
        if m:
            numbers.add(int(m.group(1)))

    if not numbers:
        # Separate message key from the normal pass case — the `.pass`
        # template interpolates `{{found_max}}` which we'd have nothing
        # to provide here, so sharing the key would render the raw
        # placeholder. `.passNone` has its own placeholder-free template.
        return [CheckItem(
            status="pass",
            message="No figures found.",
            message_key="check.tw.drawings.figuresSequential.passNone",
            reference="專利審查基準",
        )]

    max_n = max(numbers)
    expected = set(range(1, max_n + 1))
    missing = sorted(expected - numbers)

    if missing:
        return [CheckItem(
            status="amend",
            message=f"Figure numbers are not sequential; missing: {missing}.",
            message_key="check.tw.drawings.figuresSequential.amend",
            details_params={
                "figure_list": missing,
                "found_max": str(max_n),
            },
            reference="專利審查基準",
        )]

    return [CheckItem(
        status="pass",
        message=f"Figures 1–{max_n} are numbered sequentially.",
        message_key="check.tw.drawings.figuresSequential.pass",
        details_params={"found_max": str(max_n)},
        reference="專利審查基準",
    )]
