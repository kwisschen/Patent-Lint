# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Pre-renders structured ``details_params`` fields, then translates.

Python mirror of ``frontend/src/lib/detailsFormatter.js``. Most check
items emit flat ``details_params`` (numbers, strings) that i18next's
``{{var}}`` interpolation handles directly. Some emit structured
payloads (arrays of objects, nested dicts) that need a formatter to
collapse them into a flat string before interpolation.

Field-name → formatter dispatch is intentionally 1:1 with the JS side.
A divergence here would cause the weasyprint PDF path and the React
path to render the same finding differently, which is exactly what
introducing server-side i18n was meant to eliminate.

The ``localize_message`` / ``localize_details`` helpers wrap the
``CheckItem`` protocol expected by ``ReportData``: consumers call
these instead of dereferencing ``item.message`` / ``item.details``
so the English fallback only surfaces when a locale bundle lacks the
``message_key`` / ``details_key``.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

from patentlint.i18n import translate


class _CheckItemLike(Protocol):
    """Structural type — covers ``CheckItem`` and any shim used in tests."""

    status: str
    message: str
    message_key: str
    details: str | None
    details_key: str | None
    details_params: dict[str, Any] | None


def _format_numerals_with_locations(arr: list, t: Callable[..., str]) -> str:
    if not isinstance(arr, list) or not arr:
        return ""
    parts = []
    for entry in arr:
        numeral = entry.get("numeral")
        claims = entry.get("claims") or []
        claim_strs = [t("term.claim.numbered", n=n) for n in claims]
        parts.append(f"{numeral} ({t('punct.listSeparator').join(claim_strs)})")
    return t("punct.listSeparator").join(parts)


def _format_figures_with_locations(arr: list, t: Callable[..., str]) -> str:
    if not isinstance(arr, list) or not arr:
        return ""
    parts = []
    for entry in arr:
        figure = entry.get("figure")
        paragraphs = entry.get("paragraphs") or []
        fig_str = t("term.figure.numbered", n=figure)
        para_strs = [t("term.paragraph.numbered", n=n) for n in paragraphs]
        parts.append(f"{fig_str} ({t('punct.listSeparator').join(para_strs)})")
    return t("punct.listSeparator").join(parts)


def _format_paragraph_list(arr: list, t: Callable[..., str]) -> str:
    if not isinstance(arr, list) or not arr:
        return ""
    return t("punct.listSeparator").join(t("term.paragraph.numbered", n=n) for n in arr)


def _with_ellipsis(joined: str, truncated: bool, t: Callable[..., str]) -> str:
    return joined + t("punct.ellipsis") if truncated else joined


def _format_figure_list(figs: list, t: Callable[..., str]) -> str:
    if not isinstance(figs, list) or not figs:
        return ""
    truncated = len(figs) > 10
    shown = figs[:10]
    rendered = t("punct.listSeparator").join(
        t("term.figure.numbered", n=n) for n in shown
    )
    return _with_ellipsis(rendered, truncated, t)


def _format_claim_list(claims: list, t: Callable[..., str]) -> str:
    if not isinstance(claims, list) or not claims:
        return ""
    truncated = len(claims) > 10
    shown = claims[:10]
    rendered = t("punct.listSeparator").join(
        t("term.claim.numbered", n=n) for n in shown
    )
    return _with_ellipsis(rendered, truncated, t)


def _format_paragraph_list_simple(paras: list, t: Callable[..., str]) -> str:
    if not isinstance(paras, list) or not paras:
        return ""
    truncated = len(paras) > 10
    shown = paras[:10]
    rendered = t("punct.listSeparator").join(
        t("term.paragraph.numbered", n=n) for n in shown
    )
    return _with_ellipsis(rendered, truncated, t)


def _format_numeral_list(nums: list, t: Callable[..., str]) -> str:
    if not isinstance(nums, list) or not nums:
        return ""
    truncated = len(nums) > 10
    shown = nums[:10]
    rendered = t("punct.listSeparator").join(str(n) for n in shown)
    return _with_ellipsis(rendered, truncated, t)


def _format_sample_names(
    names: list, t: Callable[..., str], params: dict[str, Any] | None
) -> str:
    if not isinstance(names, list) or not names:
        return ""
    joined = t("punct.listSeparator").join(names)
    total = (params or {}).get("component_count")
    if isinstance(total, int) and total > len(names):
        return joined + t("punct.ellipsis")
    return joined


def _format_figure_ref_inconsistency(
    data: dict, t: Callable[..., str], _params: dict[str, Any] | None = None
) -> str:
    if not isinstance(data, dict):
        return ""
    only_drawings = data.get("only_drawings") or []
    only_embodiment = data.get("only_embodiment") or []
    jurisdiction = data.get("jurisdiction") or "cn"
    parts = []
    if only_drawings:
        parts.append(
            t(
                f"details.{jurisdiction}.figureRefInconsistency.onlyDrawings",
                figs=_format_figure_list(only_drawings, t),
            )
        )
    if only_embodiment:
        parts.append(
            t(
                f"details.{jurisdiction}.figureRefInconsistency.onlyEmbodiment",
                figs=_format_figure_list(only_embodiment, t),
            )
        )
    return t("punct.sentenceSeparator").join(parts)


def _format_symbol_table_inconsistency(
    data: dict, t: Callable[..., str], _params: dict[str, Any] | None = None
) -> str:
    if not isinstance(data, dict):
        return ""
    unreferenced = data.get("unreferenced") or []
    undefined = data.get("undefined") or []
    parts = []
    if unreferenced:
        parts.append(
            t(
                "details.tw.symbolTableInconsistency.unreferenced",
                symbols=_format_numeral_list(unreferenced, t),
            )
        )
    if undefined:
        parts.append(
            t(
                "details.tw.symbolTableInconsistency.undefined",
                symbols=_format_numeral_list(undefined, t),
            )
        )
    return t("punct.sentenceSeparator").join(parts)


def _format_symbol_mismatch_triples(
    data: dict, t: Callable[..., str], _params: dict[str, Any] | None = None
) -> str:
    if not isinstance(data, dict):
        return ""
    mismatches = (data.get("mismatches") or [])[:10]
    rendered: list[str] = []
    for m in mismatches:
        kind = m.get("kind")
        if kind == "not_in_table":
            rendered.append(
                t(
                    "details.tw.symbolVsRepDrawing.notInTable",
                    numeral=m.get("numeral"),
                    name=m.get("rep_name"),
                )
            )
        elif kind == "name_mismatch":
            rendered.append(
                t(
                    "details.tw.symbolVsRepDrawing.nameMismatch",
                    numeral=m.get("numeral"),
                    rep_name=m.get("rep_name"),
                    table_name=m.get("table_name"),
                )
            )
    return t("punct.sentenceSeparator").join(s for s in rendered if s)


def _format_title_prohibited_items(
    data: dict, t: Callable[..., str], _params: dict[str, Any] | None = None
) -> str:
    if not isinstance(data, dict):
        return ""
    items = data.get("items") or []
    parts = [
        t(f"details.titleProhibited.{item.get('kind')}", token=item.get("token"))
        for item in items
    ]
    return t("punct.sentenceSeparator").join(parts)


def _format_paragraph_format_violations(
    data: dict, t: Callable[..., str], _params: dict[str, Any] | None = None
) -> str:
    if not isinstance(data, dict):
        return ""
    examples = (data.get("examples") or [])[:5]
    count = data.get("count", 0)
    return t(
        "details.paragraphFormat.examples",
        examples=t("punct.listSeparator").join(examples),
        count=count,
    )


# Array-shaped payloads. Formatter signature: ``(value, t)`` with an
# optional third ``params`` slot for formatters that need sibling params.
_ARRAY_FORMATTERS: dict[str, Callable[..., str]] = {
    "numerals_with_locations": _format_numerals_with_locations,
    "figures_with_locations": _format_figures_with_locations,
    "paragraph_list": _format_paragraph_list,
    "figure_list": _format_figure_list,
    "claim_list": _format_claim_list,
    "paragraph_list_simple": _format_paragraph_list_simple,
    "numeral_list": _format_numeral_list,
    # Semantic aliases (Python emit sites name fields by content).
    "claims": _format_claim_list,
    "paragraphs": _format_paragraph_list_simple,
    "sample_names": _format_sample_names,
}

_FORMATTERS_WITH_PARAMS = {"sample_names"}

# Object-shaped payloads.
_OBJECT_FORMATTERS: dict[str, Callable[..., str]] = {
    "figure_ref_inconsistency": _format_figure_ref_inconsistency,
    "symbol_table_inconsistency": _format_symbol_table_inconsistency,
    "symbol_mismatch_triples": _format_symbol_mismatch_triples,
    "title_prohibited_items": _format_title_prohibited_items,
    "paragraph_format_violations": _format_paragraph_format_violations,
}


def format_details(
    key: str, details_params: dict[str, Any] | None, locale: str = "en"
) -> str:
    """Pre-render any structured fields, then translate ``key``.

    Returns an empty string if ``key`` is falsy. Returns the translated
    template (with missing placeholders preserved) when ``details_params``
    is absent — matches the frontend ``formatDetails`` contract.
    """
    if not key:
        return ""

    def t(k: str, **params: Any) -> str:
        return translate(k, locale, **params)

    if not details_params:
        return t(key)

    rendered: dict[str, Any] = dict(details_params)

    for field, formatter in _ARRAY_FORMATTERS.items():
        value = details_params.get(field)
        if value is None or not isinstance(value, list):
            continue
        if field in _FORMATTERS_WITH_PARAMS:
            rendered[field] = formatter(value, t, details_params)
        else:
            rendered[field] = formatter(value, t)

    for field, formatter in _OBJECT_FORMATTERS.items():
        value = details_params.get(field)
        if value is None or not isinstance(value, dict):
            continue
        rendered[field] = formatter(value, t, details_params)

    return t(key, **rendered)


def localize_message(item: _CheckItemLike, locale: str = "en") -> str:
    """Translate ``item.message_key`` or fall back to ``item.message``.

    Falls back when the translation reduces to the key itself
    (indicating both the requested locale and ``en`` lack the entry) —
    users see the English fallback stored in ``CheckItem.message``
    rather than a raw key leaking through.
    """
    message_key = getattr(item, "message_key", "") or ""
    if message_key:
        rendered = format_details(
            message_key, getattr(item, "details_params", None), locale
        )
        if rendered and rendered != message_key:
            return rendered
    return getattr(item, "message", "") or ""


def localize_details(item: _CheckItemLike, locale: str = "en") -> str | None:
    """Translate ``item.details_key`` or fall back to ``item.details``."""
    details_key = getattr(item, "details_key", None)
    if details_key:
        rendered = format_details(
            details_key, getattr(item, "details_params", None), locale
        )
        if rendered and rendered != details_key:
            return rendered
    return getattr(item, "details", None)
