# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""CN abstract and drawings analysis checks.

Four pure functions checking Chinese patent abstract and drawings
against CNIPA rules (专利法实施细则 and 审查指南).
"""

from __future__ import annotations

import re

from patentlint.analysis.utils import _dx
from patentlint.models import CheckItem, CnPatentDocument

_CN_FIG_NUM_RE = re.compile(r"(?:图|附图)\s*(\d+)")

# Compound-title conjunctions (CN drafting). Two-char 以及 must precede 及
# in the alternation so split does not fire on its tail character.
_CN_TITLE_CONJ_RE = re.compile(r"以及|及|和|与")
_COMPOUND_HALF_MIN_CHARS = 2

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
            diagnostics=_dx(
                char_count=count,
                threshold=300,
                overage=count - 300,
            ),
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
            diagnostics=_dx(
                reason_code="empty_abstract",
                title_charlen=len(title),
            ),
        )]

    if not title:
        return [CheckItem(
            status="verify",
            message="Title does not appear in the abstract.",
            message_key="check.cn.abstract.titleMatch.verify",
            details_key="details.cn.abstractTitleMatch",
            reference="审查指南",
            diagnostics=_dx(
                reason_code="empty_title",
                abstract_charlen=len(abstract),
            ),
        )]

    if title in abstract:
        return [CheckItem(
            status="pass",
            message="Title appears in the abstract.",
            message_key="check.cn.abstract.titleMatch.pass",
            reference="审查指南",
        )]

    halves = [h for h in _CN_TITLE_CONJ_RE.split(title) if h]
    if (
        len(halves) >= 2
        and all(len(h) >= _COMPOUND_HALF_MIN_CHARS for h in halves)
        and all(h in abstract for h in halves)
    ):
        return [CheckItem(
            status="pass",
            message="All compound-title halves appear in the abstract.",
            message_key="check.cn.abstract.titleMatch.passCompound",
            details_params={"halves": "、".join(halves)},
            reference="审查指南",
        )]

    return [CheckItem(
        status="verify",
        message="Title does not appear in the abstract.",
        message_key="check.cn.abstract.titleMatch.verify",
        details_key="details.cn.abstractTitleMatch",
        reference="审查指南",
        diagnostics=_dx(
            title_charlen=len(title),
            abstract_charlen=len(abstract),
            compound_halves=len(halves),
        ),
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
            details_params={
                "terms": terms_str,
                "flagged_phrases": {
                    "items": [{"kind": "phrase", "token": t} for t in found]
                },
            },
            reference="专利法实施细则 §23",
            diagnostics=_dx(
                hit_count=len(found),
                total_terms_scanned=len(_COMMERCIAL_TERMS),
            ),
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


# ── Check 25 ─────────────────────────────────────────────────────────────


def check_figures_sequential(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check that figure numbers form a contiguous 1..N set with no gaps.

    Sub-figure suffixes (图1a, 图1b, 附图2A) are collapsed onto their parent
    number. Accepts both ``图N`` and ``附图N`` prefixes; the entries in
    ``cn_doc.figure_refs`` are the raw match strings from
    ``_extract_figure_refs`` (e.g. ``"图1"``, ``"图3a"``).
    """
    numbers: set[int] = set()
    for fid in cn_doc.figure_refs:
        m = _CN_FIG_NUM_RE.search(fid)
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
            message_key="check.cn.drawings.figuresSequential.passNone",
            reference="审查指南",
        )]

    max_n = max(numbers)
    expected = set(range(1, max_n + 1))
    missing = sorted(expected - numbers)

    if missing:
        return [CheckItem(
            status="amend",
            message=f"Figure numbers are not sequential; missing: {missing}.",
            message_key="check.cn.drawings.figuresSequential.amend",
            details_params={
                "figure_list": missing,
                "found_max": str(max_n),
            },
            reference="审查指南",
            diagnostics=_dx(
                missing_count=len(missing),
                found_max=max_n,
                total_figures_found=len(numbers),
            ),
        )]

    return [CheckItem(
        status="pass",
        message=f"Figures 1–{max_n} are numbered sequentially.",
        message_key="check.cn.drawings.figuresSequential.pass",
        details_params={"found_max": str(max_n)},
        reference="审查指南",
    )]
