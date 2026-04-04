# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""CN abstract and drawings analysis checks.

Four pure functions checking Chinese patent abstract and drawings
against CNIPA rules (专利法实施细则 and 审查指南).
"""

from __future__ import annotations

from patentlint.models import CheckItem, CnPatentDocument

# ── Check 21 ─────────────────────────────────────────────────────────────


def check_abstract_char_count(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check abstract character count is within the 300-char limit."""
    count = cn_doc.abstract_char_count

    if count > 300:
        return [CheckItem(
            status="amend",
            message=f"Abstract has {count} characters (max 300).",
            message_key="check.cn.abstract.charCount.amend",
            details=f"{count} characters",
            details_key="details.cn.abstractCharCount",
            details_params={"count": str(count)},
            reference="专利法实施细则 §23",
        )]

    return [CheckItem(
        status="pass",
        message=f"Abstract has {count} characters (within 300 limit).",
        message_key="check.cn.abstract.charCount.pass",
        details_params={"count": str(count)},
        reference="专利法实施细则 §23",
    )]


# ── Check 22 ─────────────────────────────────────────────────────────────


def check_abstract_title_match(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check if the title appears in the abstract text."""
    title = cn_doc.title.strip()
    abstract = cn_doc.abstract_text.strip()

    if not abstract:
        return [CheckItem(
            status="verify",
            message="Abstract is empty — cannot verify title match.",
            message_key="check.cn.abstract.titleMatch.verify",
            details_key="details.cn.abstractTitleMatch",
            reference="审查指南",
        )]

    if not title or title not in abstract:
        return [CheckItem(
            status="verify",
            message="Title does not appear in the abstract.",
            message_key="check.cn.abstract.titleMatch.verify",
            details_key="details.cn.abstractTitleMatch",
            reference="审查指南",
        )]

    return [CheckItem(
        status="pass",
        message="Title appears in the abstract.",
        message_key="check.cn.abstract.titleMatch.pass",
        reference="审查指南",
    )]


# ── Check 23 ─────────────────────────────────────────────────────────────

_COMMERCIAL_TERMS = [
    "最优", "最佳", "世界领先", "国际领先", "国内领先",
    "国内首创", "填补空白", "首次发现", "首次提出", "独家",
]


def check_commercial_language(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Scan abstract for commercial advertising language."""
    abstract = cn_doc.abstract_text
    found = [term for term in _COMMERCIAL_TERMS if term in abstract]

    if found:
        terms_str = ", ".join(found)
        return [CheckItem(
            status="amend",
            message=f"Commercial language found in abstract: {terms_str}.",
            message_key="check.cn.abstract.commercialLanguage.amend",
            details=terms_str,
            details_key="details.cn.commercialLanguage",
            details_params={"terms": terms_str},
            reference="专利法实施细则 §23",
        )]

    return [CheckItem(
        status="pass",
        message="No commercial language found in abstract.",
        message_key="check.cn.abstract.commercialLanguage.pass",
        reference="专利法实施细则 §23",
    )]


# ── Check 24 ─────────────────────────────────────────────────────────────


def check_figure_count(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Report figure count (UI-internal stats check, always PASS)."""
    count = cn_doc.figure_count
    return [CheckItem(
        status="pass",
        message=f"{count} figure(s) found.",
        message_key="check.cn.drawings.figureCount.pass",
        details_params={"count": str(count)},
        reference="审查指南",
    )]
