# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""TW abstract analysis checks.

Four pure functions checking Taiwan patent abstract formatting
against TIPO rules (專利法施行細則 and 專利審查基準).
"""

from __future__ import annotations

from patentlint.models import CheckItem, TwPatentDocument

# TW commercial language terms (Traditional Chinese)
_COMMERCIAL_TERMS = [
    "最優", "最佳", "世界領先", "國際領先", "國內首創", "填補空白",
]


# ── Check 27 ────────────────────────────────────────────────────────────


def check_abstract_char_count(doc: TwPatentDocument) -> list[CheckItem]:
    """Check abstract character count against 250-char soft limit."""
    count = doc.abstract_char_count

    if count > 250:
        return [CheckItem(
            status="verify",
            message=f"Abstract has {count} characters (recommended max 250).",
            message_key="check.tw.abstract.charCount.verify",
            details=f"{count} characters",
            details_key="details.tw.abstractCharCount",
            details_params={"count": str(count)},
            reference="專利法施行細則 §21",
        )]

    return [CheckItem(
        status="pass",
        message=f"Abstract has {count} characters (within 250 limit).",
        message_key="check.tw.abstract.charCount.pass",
        details_params={"count": str(count)},
        reference="專利法施行細則 §21",
    )]


# ── Check 28 ────────────────────────────────────────────────────────────


def check_abstract_title_match(doc: TwPatentDocument) -> list[CheckItem]:
    """Check if the title appears in the abstract text."""
    title = doc.title.strip()
    abstract = doc.abstract_text.strip()

    if not abstract or not title:
        return [CheckItem(
            status="pass",
            message="Abstract or title empty — skipping title match check.",
            message_key="check.tw.abstract.titleMatch.pass",
            reference="專利審查基準",
        )]

    if title not in abstract:
        return [CheckItem(
            status="verify",
            message="Title does not appear in the abstract.",
            message_key="check.tw.abstract.titleMatch.verify",
            details_key="details.tw.abstractTitleMatch",
            details_params={"detail": title},
            reference="專利審查基準",
        )]

    return [CheckItem(
        status="pass",
        message="Title appears in the abstract.",
        message_key="check.tw.abstract.titleMatch.pass",
        reference="專利審查基準",
    )]


# ── Check 29 ────────────────────────────────────────────────────────────


def check_commercial_language(doc: TwPatentDocument) -> list[CheckItem]:
    """Scan abstract for commercial advertising language (商業性宣傳用語)."""
    abstract = doc.abstract_text
    found = [term for term in _COMMERCIAL_TERMS if term in abstract]

    if found:
        terms_str = ", ".join(found)
        return [CheckItem(
            status="amend",
            message=f"Commercial language found in abstract: {terms_str}.",
            message_key="check.tw.abstract.commercialLanguage.amend",
            details=terms_str,
            details_key="details.tw.commercialLanguage",
            details_params={"terms": terms_str},
            reference="專利法施行細則 §21",
        )]

    return [CheckItem(
        status="pass",
        message="No commercial language found in abstract.",
        message_key="check.tw.abstract.commercialLanguage.pass",
        reference="專利法施行細則 §21",
    )]


# ── Check 30 ────────────────────────────────────────────────────────────


def check_representative_drawing(doc: TwPatentDocument) -> list[CheckItem]:
    """Check that a representative drawing is designated when drawings exist."""
    has_drawings = bool(doc.figure_refs)

    if not has_drawings:
        return [CheckItem(
            status="pass",
            message="No drawings — representative drawing not required.",
            message_key="check.tw.abstract.representativeDrawing.pass",
            reference="專利法施行細則 §21",
        )]

    if not doc.representative_drawing:
        return [CheckItem(
            status="verify",
            message="No representative drawing designation found.",
            message_key="check.tw.abstract.representativeDrawing.verify",
            details_key="details.tw.representativeDrawing",
            reference="專利法施行細則 §21",
        )]

    return [CheckItem(
        status="pass",
        message="Representative drawing designated.",
        message_key="check.tw.abstract.representativeDrawing.pass",
        reference="專利法施行細則 §21",
    )]
