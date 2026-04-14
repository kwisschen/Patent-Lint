# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""TW specification analysis checks.

Ten pure functions checking Taiwan patent specification formatting
against TIPO rules (專利法施行細則 and 專利審查基準).
"""

from __future__ import annotations

import re

from patentlint.analysis.figure_refs import TW_PARSER
from patentlint.models import CheckItem, TwPatentDocument, TwPatentType

# Canonical section order per 專利法施行細則 §17
_CANONICAL_ORDER = [
    "technical_field",
    "prior_art",
    "disclosure",
    "drawings_description",
    "embodiment",
    "symbol_table",
]

_SECTION_NAMES_TW = {
    "technical_field": "技術領域",
    "prior_art": "先前技術",
    "disclosure_invention": "發明內容",
    "disclosure_utility": "新型內容",
    "drawings_description": "圖式簡單說明",
    "embodiment": "實施方式",
    "symbol_table": "符號說明",
}

_VALID_ENDINGS = frozenset("。！？")

_TRADEMARK_RE = re.compile(r"[®™©]")
_MODEL_NUMBER_RE = re.compile(r"[A-Z]{2,}-\d{2,}", re.IGNORECASE)
_CLAIM_REF_RE = re.compile(r"如請求項\s*\d+")
_REF_NUMERAL_RE = re.compile(
    r"(?<![【\d])"      # not preceded by 【 or digit
    r"(?<!第)"          # not ordinal 第N
    r"(\d{2,4})"        # 2-4 digit number
    r"(?![】\d])"       # not followed by 】 or digit
    r"(?![°℃%a-zA-Z])" # not followed by unit/measurement
)


def _all_spec_sections(doc: TwPatentDocument) -> list[str]:
    """Collect all spec paragraphs from body sections."""
    return (
        doc.technical_field
        + doc.prior_art
        + doc.disclosure
        + doc.drawings_description
        + doc.embodiment
    )


def _all_spec_text(doc: TwPatentDocument) -> str:
    """Join all spec paragraphs into a single string."""
    return "\n".join(_all_spec_sections(doc))


def _section_has_content(items: list) -> bool:
    """Check whether a section list has any non-empty content."""
    if not items:
        return False
    if isinstance(items[0], str):
        return any(p.strip() for p in items)
    # SymbolEntry list — non-empty means has content
    return True


def _fig_sort_key(fig_id: str) -> tuple[int, str]:
    """Sort key for figure IDs that may have alpha suffixes (e.g. '5A')."""
    m = re.match(r"(\d+)([A-Z]?)$", fig_id)
    if m:
        return (int(m.group(1)), m.group(2))
    return (0, fig_id)


# ── Check 1 ──────────────────────────────────────────────────────────────


def check_required_sections(doc: TwPatentDocument) -> list[CheckItem]:
    """Check that mandatory spec sections are non-empty."""
    missing = []

    if not _section_has_content(doc.technical_field):
        missing.append("技術領域")
    if not _section_has_content(doc.prior_art):
        missing.append("先前技術")

    disclosure_name = (
        "新型內容" if doc.patent_type == TwPatentType.UTILITY_MODEL else "發明內容"
    )
    if not _section_has_content(doc.disclosure):
        missing.append(disclosure_name)

    if not _section_has_content(doc.embodiment):
        missing.append("實施方式")

    # Conditional: when drawings exist, require 圖式簡單說明 and 符號說明
    if _section_has_content(doc.drawings_description):
        if not _section_has_content(doc.symbol_table):
            missing.append("符號說明")
    elif _section_has_content(doc.symbol_table):
        # symbol_table exists but no drawings_description — check 圖式簡單說明
        if not _section_has_content(doc.drawings_description):
            missing.append("圖式簡單說明")

    if missing:
        return [CheckItem(
            status="amend",
            message=f"Missing required sections: {', '.join(missing)}",
            message_key="check.tw.spec.requiredSections.amend",
            details=", ".join(missing),
            details_key="details.tw.requiredSections",
            details_params={"sections": ", ".join(missing)},
            reference="專利法施行細則 §17",
        )]
    return [CheckItem(
        status="pass",
        message="All required specification sections are present.",
        message_key="check.tw.spec.requiredSections.pass",
        reference="專利法施行細則 §17",
    )]


# ── Check 2 ──────────────────────────────────────────────────────────────


def check_section_ordering(doc: TwPatentDocument) -> list[CheckItem]:
    """Verify sections appear in prescribed TIPO order."""
    section_data = [
        ("technical_field", doc.technical_field),
        ("prior_art", doc.prior_art),
        ("disclosure", doc.disclosure),
        ("drawings_description", doc.drawings_description),
        ("embodiment", doc.embodiment),
        ("symbol_table", doc.symbol_table),
    ]

    present = []
    for idx, (_, items) in enumerate(section_data):
        if _section_has_content(items):
            present.append(idx)

    is_sorted = all(present[i] < present[i + 1] for i in range(len(present) - 1))

    if not is_sorted:
        return [CheckItem(
            status="amend",
            message="Specification sections are not in the required order.",
            message_key="check.tw.spec.sectionOrdering.amend",
            details_key="details.tw.sectionOrdering",
            reference="專利法施行細則 §17",
        )]
    return [CheckItem(
        status="pass",
        message="Specification sections are in the correct order.",
        message_key="check.tw.spec.sectionOrdering.pass",
        reference="專利法施行細則 §17",
    )]


# ── Check 3 ──────────────────────────────────────────────────────────────


def check_paragraph_numbering(doc: TwPatentDocument) -> list[CheckItem]:
    """Check paragraph numbering format when present (optional per §17)."""
    if not doc.has_paragraph_numbering:
        return [CheckItem(
            status="pass",
            message="Paragraph numbering is absent (optional per 施行細則 §17).",
            message_key="check.tw.spec.paragraphNumbering.pass",
            reference="專利法施行細則 §17",
        )]

    nums = doc.paragraph_numbers
    if not nums:
        return [CheckItem(
            status="pass",
            message="Paragraph numbering correct.",
            message_key="check.tw.spec.paragraphNumbering.pass",
            reference="專利法施行細則 §17",
        )]

    # Verify 4-digit format
    four_digit_re = re.compile(r"^\d{4}$")
    bad_format = [n for n in nums if not four_digit_re.match(n)]
    if bad_format:
        detail = f"Non-4-digit format: {', '.join(bad_format[:5])}"
        return [CheckItem(
            status="amend",
            message="Paragraph numbering format incorrect.",
            message_key="check.tw.spec.paragraphNumbering.amend",
            details=detail,
            details_key="details.tw.paragraphNumbering",
            details_params={"detail": detail},
            reference="專利法施行細則 §17",
        )]

    # Check sequential
    int_nums = [int(n) for n in nums]
    for i in range(1, len(int_nums)):
        if int_nums[i] != int_nums[i - 1] + 1:
            detail = f"Gap after 【{nums[i - 1]}】: next is 【{nums[i]}】"
            return [CheckItem(
                status="amend",
                message="Paragraph numbering has gaps.",
                message_key="check.tw.spec.paragraphNumbering.amend",
                details=detail,
                details_key="details.tw.paragraphNumbering",
                details_params={"detail": detail},
                reference="專利法施行細則 §17",
            )]

    return [CheckItem(
        status="pass",
        message="Paragraph numbering is correct.",
        message_key="check.tw.spec.paragraphNumbering.pass",
        reference="專利法施行細則 §17",
    )]


# ── Check 4 ──────────────────────────────────────────────────────────────


_BRACKET_SUBHEADING = re.compile(r"^\[.+\]$")
_SYMBOL_TABLE_ENTRY = re.compile(
    r"^[A-Za-z0-9~\-]+\s*(?:[‧·.…：:\t]\s*[‧·.…]*\s*|\s{2,}).+"
)


def _is_skip_paragraph_ending(text: str) -> bool:
    """Check if paragraph should be excluded from ending punctuation check."""
    # Half-width bracket sub-headings: [第一實施例]
    if _BRACKET_SUBHEADING.match(text):
        return True
    # Symbol table entry patterns: numeral + separator + name
    if _SYMBOL_TABLE_ENTRY.match(text):
        return True
    return False


def check_paragraph_ending(doc: TwPatentDocument) -> list[CheckItem]:
    """Check each specification paragraph ends with valid Chinese punctuation.

    Excludes 符號說明 section, half-width bracket sub-headings, and
    symbol table entry patterns from the check.
    """
    # Relaxed endings for 圖式簡單說明, 發明內容/新型內容, 實施方式
    # (semicolons and colons allowed for enumerations and step descriptions)
    _RELAXED_VALID = _VALID_ENDINGS | frozenset("；：")

    def _has_valid_ending_tw(text: str, relaxed: bool) -> bool:
        endings = _RELAXED_VALID if relaxed else _VALID_ENDINGS
        if text[-1] in endings:
            return True
        # Allow "；以及" and "；及" endings (penultimate list item)
        if relaxed and (text.endswith("；以及") or text.endswith("；及")):
            return True
        return False

    # Only check body sections, NOT 符號說明.
    # Strict (。！？ only) for 技術領域 and 先前技術.
    # Relaxed (+ ；：) for 發明內容, 圖式簡單說明, 實施方式.
    sections_to_check = [
        (doc.technical_field, False),
        (doc.prior_art, False),
        (doc.disclosure, True),
        (doc.drawings_description, True),
        (doc.embodiment, True),
    ]
    bad_count = 0
    for section_paras, relaxed in sections_to_check:
        for para in section_paras:
            stripped = para.strip()
            if not stripped:
                continue
            if _is_skip_paragraph_ending(stripped):
                continue
            if not _has_valid_ending_tw(stripped, relaxed):
                bad_count += 1

    if bad_count:
        return [CheckItem(
            status="amend",
            message=f"{bad_count} paragraph(s) have invalid ending punctuation.",
            message_key="check.tw.spec.paragraphEnding.amend",
            details=f"{bad_count} paragraphs",
            details_key="details.tw.paragraphEnding",
            details_params={"count": str(bad_count)},
            reference="專利審查基準",
        )]
    return [CheckItem(
        status="pass",
        message="All paragraphs have valid ending punctuation.",
        message_key="check.tw.spec.paragraphEnding.pass",
        reference="專利審查基準",
    )]


# ── Check 5 ──────────────────────────────────────────────────────────────


def check_figure_ref_consistency(doc: TwPatentDocument) -> list[CheckItem]:
    """Compare figure references between 圖式簡單說明 and 實施方式."""
    drawings_text = "\n".join(doc.drawings_description)
    embodiment_text = "\n".join(doc.embodiment)

    if not drawings_text.strip():
        return [CheckItem(
            status="pass",
            message="No 圖式簡單說明 to check.",
            message_key="check.tw.spec.figureRefConsistency.pass",
            reference="專利審查基準",
        )]

    drawings_figs = TW_PARSER.extract(drawings_text).ids
    embodiment_figs = TW_PARSER.extract(embodiment_text).ids

    only_drawings = sorted(drawings_figs - embodiment_figs, key=_fig_sort_key)
    only_embodiment = sorted(embodiment_figs - drawings_figs, key=_fig_sort_key)

    if only_drawings or only_embodiment:
        parts = []
        if only_drawings:
            parts.append("圖" + ", 圖".join(only_drawings) + " in 圖式簡單說明 only")
        if only_embodiment:
            parts.append("圖" + ", 圖".join(only_embodiment) + " in 實施方式 only")
        detail = "; ".join(parts)
        return [CheckItem(
            status="verify",
            message="Figure references differ between 圖式簡單說明 and 實施方式.",
            message_key="check.tw.spec.figureRefConsistency.verify",
            details=detail,
            details_key="details.tw.figureRefConsistency",
            details_params={"detail": detail},
            reference="專利審查基準",
        )]

    return [CheckItem(
        status="pass",
        message="Figure references are consistent across sections.",
        message_key="check.tw.spec.figureRefConsistency.pass",
        reference="專利審查基準",
    )]


# ── Check 6 ──────────────────────────────────────────────────────────────


def check_patent_type_terminology(doc: TwPatentDocument) -> list[CheckItem]:
    """Flag mixed 本發明 / 本新型 usage based on patent type."""
    text = _all_spec_text(doc)

    if doc.patent_type == TwPatentType.INVENTION:
        if "本新型" in text:
            return [CheckItem(
                status="verify",
                message="Invention patent contains utility model terminology.",
                message_key="check.tw.spec.patentTypeTerminology.verify",
                details="Patent type mismatch: 本新型",
                details_key="details.tw.patentTypeTerminology",
                details_params={"term": "本新型"},
                reference="專利審查基準",
            )]
    elif doc.patent_type == TwPatentType.UTILITY_MODEL:
        if "本發明" in text:
            return [CheckItem(
                status="verify",
                message="Utility model contains invention patent terminology.",
                message_key="check.tw.spec.patentTypeTerminology.verify",
                details="Patent type mismatch: 本發明",
                details_key="details.tw.patentTypeTerminology",
                details_params={"term": "本發明"},
                reference="專利審查基準",
            )]

    return [CheckItem(
        status="pass",
        message="Patent type terminology is consistent.",
        message_key="check.tw.spec.patentTypeTerminology.pass",
        reference="專利審查基準",
    )]


# ── Check 7 ──────────────────────────────────────────────────────────────


def check_title(doc: TwPatentDocument) -> list[CheckItem]:
    """Check title for prohibited content (no character limit for TW)."""
    title = doc.title
    if not title.strip():
        return [CheckItem(
            status="amend",
            message="Title is missing.",
            message_key="check.tw.spec.title.amendMissing",
            details_key="details.tw.titleMissing",
            details="",
            reference="專利審查基準",
        )]

    found = []
    tm_match = _TRADEMARK_RE.search(title)
    if tm_match:
        found.append(f"Trademark symbol: {tm_match.group()}")
    model_match = _MODEL_NUMBER_RE.search(title)
    if model_match:
        found.append(f"Model number: {model_match.group()}")

    if found:
        detail = "; ".join(found)
        return [CheckItem(
            status="amend",
            message="Title contains prohibited content.",
            message_key="check.tw.spec.title.amendContent",
            details=detail,
            details_key="details.tw.title",
            details_params={"detail": detail},
            reference="專利審查基準",
        )]

    return [CheckItem(
        status="pass",
        message="Title meets requirements.",
        message_key="check.tw.spec.title.pass",
        reference="專利審查基準",
    )]


# ── Check 8 ──────────────────────────────────────────────────────────────


def check_spec_claim_reference(doc: TwPatentDocument) -> list[CheckItem]:
    """Flag specification text that references specific claims."""
    text = _all_spec_text(doc)
    match = _CLAIM_REF_RE.search(text)

    if match:
        snippet = match.group()[:50]
        return [CheckItem(
            status="amend",
            message="Specification references a specific claim.",
            message_key="check.tw.spec.claimReference.amend",
            details=snippet,
            details_key="details.tw.claimReference",
            details_params={"detail": snippet},
            reference="專利法施行細則 §17",
        )]

    return [CheckItem(
        status="pass",
        message="No claim references found in specification.",
        message_key="check.tw.spec.claimReference.pass",
        reference="專利法施行細則 §17",
    )]


# ── Check 9 ──────────────────────────────────────────────────────────────


def check_symbol_table_presence(doc: TwPatentDocument) -> list[CheckItem]:
    """Check 符號說明 presence when drawings exist."""
    if _section_has_content(doc.drawings_description) and not _section_has_content(doc.symbol_table):
        return [CheckItem(
            status="amend",
            message="符號說明 section missing but 圖式簡單說明 is present.",
            message_key="check.tw.spec.symbolTablePresence.amend",
            details_key="details.tw.symbolTablePresence",
            reference="專利法施行細則 §17",
        )]

    return [CheckItem(
        status="pass",
        message="符號說明 section present.",
        message_key="check.tw.spec.symbolTablePresence.pass",
        reference="專利法施行細則 §17",
    )]


# ── Check 10 ─────────────────────────────────────────────────────────────


def check_symbol_table_consistency(doc: TwPatentDocument) -> list[CheckItem]:
    """Compare 符號說明 entries against 實施方式 text."""
    if not doc.symbol_table:
        return [CheckItem(
            status="pass",
            message="No 符號說明 to check.",
            message_key="check.tw.spec.symbolTableConsistency.pass",
            reference="專利審查基準",
        )]

    embodiment_text = "\n".join(doc.embodiment)

    # Check defined but unreferenced
    unreferenced = []
    for entry in doc.symbol_table:
        # For range numerals (e.g., S21~S25, 3001~3010), check if any
        # component appears in the text
        parts = re.split(r"[~\-]", entry.numeral)
        found = any(p in embodiment_text for p in parts if p.strip())
        if not found:
            unreferenced.append(entry.numeral)

    # Check reference numerals in embodiment not defined in symbol_table
    # Build set of all individual numerals covered by symbol_table entries
    defined_numerals: set[str] = set()
    for entry in doc.symbol_table:
        defined_numerals.add(entry.numeral)
        # Also add individual parts of range numerals
        for part in re.split(r"[~\-]", entry.numeral):
            part = part.strip()
            if part:
                defined_numerals.add(part)
    embodiment_numerals = set(_REF_NUMERAL_RE.findall(embodiment_text))
    undefined = sorted(embodiment_numerals - defined_numerals)

    if unreferenced or undefined:
        parts = []
        if unreferenced:
            parts.append(f"Defined but unreferenced: {', '.join(unreferenced[:10])}")
        if undefined:
            parts.append(f"Referenced but undefined: {', '.join(undefined[:10])}")
        detail = "; ".join(parts)
        return [CheckItem(
            status="verify",
            message="符號說明 entries inconsistent with 實施方式.",
            message_key="check.tw.spec.symbolTableConsistency.verify",
            details=detail,
            details_key="details.tw.symbolTableConsistency",
            details_params={"detail": detail},
            reference="專利審查基準",
        )]

    return [CheckItem(
        status="pass",
        message="符號說明 entries consistent with specification.",
        message_key="check.tw.spec.symbolTableConsistency.pass",
        reference="專利審查基準",
    )]
