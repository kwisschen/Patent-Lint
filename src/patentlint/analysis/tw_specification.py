# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
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
    r"[(（]"                # require opening paren (ASCII or fullwidth)
    r"(\d{1,4}[a-zA-Z]?)"   # 1-4 digit + optional single letter suffix
    r"[)）]"                # require closing paren
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
    """Verify sections appear in prescribed TIPO order.

    Reads ``doc.section_order`` — the list of canonical body-section keys
    in the order the parser first encountered each 【】bracket header. A
    non-increasing canonical-index sequence indicates the drafter placed
    sections out of the 專利法施行細則 §17 order. Empty ``section_order``
    (no bracket headers found) passes vacuously.
    """
    canonical_index = {name: idx for idx, name in enumerate(_CANONICAL_ORDER)}
    indices = [
        canonical_index[s] for s in doc.section_order if s in canonical_index
    ]
    is_sorted = all(indices[i] < indices[i + 1] for i in range(len(indices) - 1))

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
        examples_str = ", ".join(bad_format[:5])
        return [CheckItem(
            status="amend",
            message=f"{len(bad_format)} paragraph(s) use non-[NNNN] format.",
            message_key="check.tw.spec.paragraphNumbering.amendFormat",
            details_key="details.tw.paragraphNumbering",
            details_params={"count": len(bad_format), "examples": examples_str},
            reference="專利法施行細則 §17",
        )]

    # Check sequential
    int_nums = [int(n) for n in nums]
    for i in range(1, len(int_nums)):
        if int_nums[i] != int_nums[i - 1] + 1:
            return [CheckItem(
                status="amend",
                message=f"Paragraph numbering has a gap: [{nums[i - 1]}] is followed by [{nums[i]}].",
                message_key="check.tw.spec.paragraphNumbering.amendGap",
                details_key="details.tw.paragraphNumbering",
                details_params={"prev": nums[i - 1], "next": nums[i]},
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
# JP-translation-style numbered sub-claim marker in the disclosure body,
# e.g. `[1]一種蓋組件...，` / `[2]如所述[1]記載的蓋組件...`. When a paragraph
# starts with this marker, the sub-claim body may legitimately span multiple
# Word paragraphs (intermediate lines ending with ，/、/；, closing line with 。).
_BRACKET_CLAIM_MARKER = re.compile(r"^\[\d+\]")


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

    Relaxed sections (發明內容, 圖式簡單說明, 實施方式) also treat
    JP-translation-style `[N]`-numbered sub-claim groups as single logical
    units — intermediate continuation paragraphs are skipped and only the
    closing paragraph of the unit (the one that ends with valid punctuation)
    is validated. A unit is opened by a paragraph starting with `[<digit>+]`
    that lacks a valid ending, and closed by the first subsequent paragraph
    that ends with valid punctuation (or by a new heading/section boundary).
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
    # Parallel word-numbers aligned with the same concatenation order used
    # by sections_to_check. Populated by extract_tw_sections for .docx
    # input; may be empty for other input paths (XML, legacy callers), in
    # which case the check falls back to an internal ordinal.
    word_numbers = doc.body_paragraph_word_numbers

    bad_paragraphs: list[int | str] = []
    ordinal = 0
    for section_paras, relaxed in sections_to_check:
        in_claim_unit = False
        for para in section_paras:
            stripped = para.strip()
            if not stripped:
                continue
            ordinal += 1
            if _is_skip_paragraph_ending(stripped):
                # Full-bracket subheadings reset any open claim unit.
                if _BRACKET_SUBHEADING.match(stripped):
                    in_claim_unit = False
                continue
            has_valid = _has_valid_ending_tw(stripped, relaxed)
            if relaxed and _BRACKET_CLAIM_MARKER.match(stripped):
                # Start of an [N]-numbered sub-claim group.
                in_claim_unit = not has_valid
                if not has_valid:
                    continue  # unit continues into subsequent paragraphs
            elif relaxed and in_claim_unit:
                # Continuation paragraph inside an open [N] unit.
                if has_valid:
                    in_claim_unit = False
                continue
            if not has_valid:
                # Prefer the Word 【NNNN】 auto-number when the drafter's
                # file carried it; fall back to the internal ordinal
                # otherwise so XML/legacy paths still produce useful output.
                label: int | str = ordinal
                if ordinal - 1 < len(word_numbers):
                    wn = word_numbers[ordinal - 1]
                    if wn is not None:
                        label = wn
                bad_paragraphs.append(label)

    if bad_paragraphs:
        paras_str = ", ".join(str(n) for n in bad_paragraphs)
        return [CheckItem(
            status="amend",
            message=f"{len(bad_paragraphs)} paragraph(s) have invalid ending punctuation (paragraphs: {paras_str}).",
            message_key="check.tw.spec.paragraphEnding.amend",
            details=f"{len(bad_paragraphs)} paragraphs",
            details_key="details.tw.paragraphEnding",
            details_params={"count": len(bad_paragraphs), "paragraphs": bad_paragraphs},
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

    # Collapse sub-figure suffixes onto the parent figure number so that
    # 圖12, 圖12(A), 圖12A all compare as figure 12. Without this, a drawings
    # section listing 圖12(A) and 圖12(B) would not match an embodiment
    # reference to bare 圖12, and the old ``_to_int_safe`` filter silently
    # dropped suffix IDs from the rendered mismatch list.
    def _parent_num(fid: str) -> int | None:
        m = re.match(r"(\d+)", fid)
        return int(m.group(1)) if m else None

    drawings_parents = {p for p in (_parent_num(f) for f in drawings_figs) if p is not None}
    embodiment_parents = {p for p in (_parent_num(f) for f in embodiment_figs) if p is not None}

    only_drawings = sorted(drawings_parents - embodiment_parents)
    only_embodiment = sorted(embodiment_parents - drawings_parents)

    if only_drawings or only_embodiment:
        return [CheckItem(
            status="verify",
            message="Figure references differ between 圖式簡單說明 and 實施方式.",
            message_key="check.tw.spec.figureRefConsistency.verify",
            details_key="details.tw.figureRefConsistency",
            details_params={
                "figure_ref_inconsistency": {
                    "only_drawings": only_drawings,
                    "only_embodiment": only_embodiment,
                    "jurisdiction": "tw",
                },
            },
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

    items: list[dict] = []
    tm_match = _TRADEMARK_RE.search(title)
    if tm_match:
        items.append({"kind": "trademark", "token": tm_match.group()})
    model_match = _MODEL_NUMBER_RE.search(title)
    if model_match:
        items.append({"kind": "model", "token": model_match.group()})

    if items:
        return [CheckItem(
            status="amend",
            message="Title contains prohibited content.",
            message_key="check.tw.spec.title.amendContent",
            details_key="details.tw.title",
            details_params={"title_prohibited_items": {"items": items}},
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
        return [CheckItem(
            status="verify",
            message="符號說明 entries inconsistent with 實施方式.",
            message_key="check.tw.spec.symbolTableConsistency.verify",
            details_key="details.tw.symbolTableConsistency",
            details_params={
                "symbol_table_inconsistency": {
                    "unreferenced": sorted(unreferenced)[:10],
                    "undefined": sorted(undefined)[:10],
                },
            },
            reference="專利審查基準",
        )]

    return [CheckItem(
        status="pass",
        message="符號說明 entries consistent with specification.",
        message_key="check.tw.spec.symbolTableConsistency.pass",
        reference="專利審查基準",
    )]
