# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""CN patent .docx section extraction — 五書模板 format."""

from __future__ import annotations

import re

from patentlint.models import CnPatentDocument
from patentlint.parser.claims_cn import parse_cn_claims_docx
from patentlint.parser.docx_loader import DocxSection

# ---------------------------------------------------------------------------
# Header matching patterns — match Word section header text to document parts
# ---------------------------------------------------------------------------

_HEADER_SPEC = re.compile(r"说明书(?!摘要|附图)")
_HEADER_CLAIMS = re.compile(r"权利要求书")
_HEADER_ABSTRACT = re.compile(r"说明书摘要|摘要(?!附图)")
_HEADER_ABSTRACT_DRAWING = re.compile(r"摘要附图")
_HEADER_DRAWINGS = re.compile(r"说明书附图")

# ---------------------------------------------------------------------------
# Spec sub-section header patterns — matched against body paragraph text
# ---------------------------------------------------------------------------

_SPEC_SUBSECTIONS = [
    ("technical_field", re.compile(r"^[\s\u3000]*技术领域[\s\u3000]*$")),
    ("background", re.compile(r"^[\s\u3000]*背景技术[\s\u3000]*$")),
    ("summary", re.compile(r"^[\s\u3000]*发明内容[\s\u3000]*$")),
    ("drawings_description", re.compile(r"^[\s\u3000]*附图说明[\s\u3000]*$")),
    ("detailed_description", re.compile(r"^[\s\u3000]*具体实施方式[\s\u3000]*$")),
]

# ---------------------------------------------------------------------------
# Paragraph numbering detection — user-added numbering in CN .docx is an error
# ---------------------------------------------------------------------------

_PARA_NUM_PATTERN = re.compile(r"^\[(\d{4})\]")

# ---------------------------------------------------------------------------
# Figure reference patterns
# ---------------------------------------------------------------------------

_FIGURE_REF_PATTERN = re.compile(r"图\s*(\d+[a-zA-Z]?)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _identify_section(header_text: str) -> str | None:
    """Identify which CN patent document part a Word section header corresponds to."""
    if not header_text:
        return None
    # Order matters: check more specific patterns before less specific
    if _HEADER_ABSTRACT_DRAWING.search(header_text):
        return "abstract_drawing"
    if _HEADER_ABSTRACT.search(header_text):
        return "abstract"
    if _HEADER_DRAWINGS.search(header_text):
        return "drawings"
    if _HEADER_CLAIMS.search(header_text):
        return "claims"
    if _HEADER_SPEC.search(header_text):
        return "specification"
    return None


def _split_spec_subsections(paragraphs: list[str]) -> dict[str, list[str]]:
    """Split specification paragraphs into sub-sections by header detection.

    Returns a dict with keys: technical_field, background, summary,
    drawings_description, detailed_description. Each value is a list of
    paragraph strings (excluding the header line itself).
    """
    result: dict[str, list[str]] = {
        "technical_field": [],
        "background": [],
        "summary": [],
        "drawings_description": [],
        "detailed_description": [],
    }

    current_key: str | None = None
    for para in paragraphs:
        # Check if this paragraph is a sub-section header
        matched_key = None
        for key, pattern in _SPEC_SUBSECTIONS:
            if pattern.match(para):
                matched_key = key
                break

        if matched_key is not None:
            current_key = matched_key
            continue  # Skip the header line itself

        if current_key is not None:
            result[current_key].append(para)

    return result


def _detect_paragraph_numbering(paragraphs: list[str]) -> tuple[bool, list[int]]:
    """Detect user-added paragraph numbering in CN .docx paragraphs.

    Returns (has_numbering, list_of_numbers).
    """
    nums: list[int] = []
    for para in paragraphs:
        m = _PARA_NUM_PATTERN.match(para)
        if m:
            nums.append(int(m.group(1)))
    return len(nums) > 0, sorted(nums)


def _extract_title(paragraphs: list[str]) -> str:
    """Extract invention title from spec paragraphs.

    The title appears before any sub-section header (技术领域, etc.).
    """
    for para in paragraphs:
        # Stop at first sub-section header
        for _, pattern in _SPEC_SUBSECTIONS:
            if pattern.match(para):
                return ""
        # Non-empty paragraph before any header is likely the title
        if para.strip():
            return para.strip()
    return ""


def _extract_figure_refs(text: str) -> list[str]:
    """Extract figure reference strings from text (e.g., '图1', '图2a')."""
    return [m.group(0) for m in _FIGURE_REF_PATTERN.finditer(text)]


def _count_figures_from_descriptions(paragraphs: list[str]) -> int:
    """Count distinct figure numbers referenced in drawings description paragraphs."""
    nums: set[str] = set()
    for para in paragraphs:
        for m in _FIGURE_REF_PATTERN.finditer(para):
            nums.add(m.group(1))
    return len(nums)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def extract_cn_sections_from_docx(sections: list[DocxSection]) -> CnPatentDocument:
    """Extract CN patent document structure from Word sections.

    Maps Word section headers to document parts (说明书, 权利要求书, etc.),
    then extracts spec sub-sections via regex on body text.
    """
    spec_paragraphs: list[str] = []
    claims_paragraphs: list[str] = []
    abstract_paragraphs: list[str] = []

    for section in sections:
        doc_part = _identify_section(section.header_text)
        if doc_part == "specification":
            spec_paragraphs = section.paragraphs
        elif doc_part == "claims":
            claims_paragraphs = section.paragraphs
        elif doc_part == "abstract":
            abstract_paragraphs = section.paragraphs

    # Split specification into sub-sections
    subsections = _split_spec_subsections(spec_paragraphs)

    # Extract title (before first sub-section header)
    title = _extract_title(spec_paragraphs)

    # Detect user-added paragraph numbering (should not exist in CN .docx)
    all_spec_paras: list[str] = []
    for paras in subsections.values():
        all_spec_paras.extend(paras)
    has_numbering, para_nums = _detect_paragraph_numbering(all_spec_paras)

    # Parse claims
    claims_text = "\n".join(claims_paragraphs)
    claims = parse_cn_claims_docx(claims_text)

    # Abstract
    abstract_text = "\n".join(abstract_paragraphs).strip()
    abstract_char_count = len(
        abstract_text.replace("\n", "").replace(" ", "").replace("\u3000", "")
    )

    # Figure references from detailed description and drawings description
    detail_text = "\n".join(subsections["detailed_description"])
    drawings_desc_text = "\n".join(subsections["drawings_description"])
    all_refs_text = detail_text + "\n" + drawings_desc_text
    figure_refs = _extract_figure_refs(all_refs_text)
    figure_count = _count_figures_from_descriptions(subsections["drawings_description"])

    return CnPatentDocument(
        title=title,
        technical_field=subsections["technical_field"],
        background=subsections["background"],
        summary=subsections["summary"],
        drawings_description=subsections["drawings_description"],
        detailed_description=subsections["detailed_description"],
        claims=claims,
        abstract_text=abstract_text,
        abstract_char_count=abstract_char_count,
        paragraph_numbers=para_nums,
        figure_count=figure_count,
        figure_refs=figure_refs,
        has_paragraph_numbering=has_numbering,
        input_format="docx",
        has_doc_page_fallback=False,
    )
