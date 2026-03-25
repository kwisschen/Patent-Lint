# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""DOCX document loader using python-docx.

Extracts numbered paragraphs from patent .docx files, tracking paragraph and claim
numberings, missing endings, and restrictive wording — mirroring the Java
PatentAnalyzer's loadDocxContent() and processParagraph() logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from patentlint.analysis.specification import detect_restrictive_wording, has_valid_ending
from patentlint.parser.sections import extract_description_of_drawings_section


@dataclass
class LoadedDocument:
    """Structured result of loading a patent .docx file.

    Contains the full document text plus numbering metadata extracted
    from Word's paragraph numbering XML.
    """

    full_text: str
    paragraph_numberings: list[int] = field(default_factory=list)
    claim_numberings: list[int] = field(default_factory=list)
    missing_ending_paragraphs: list[int] = field(default_factory=list)
    improper_spec_paragraphs: list[int] = field(default_factory=list)
    improper_spec_phrases: str = ""
    has_tracked_changes: bool = False


def detect_tracked_changes(doc) -> bool:
    """Check if a .docx document contains tracked changes (w:del or w:ins).

    Tracked changes mean the document has unresolved revisions that should
    be accepted or rejected before final filing.
    """
    body = doc.element.body
    return (
        len(body.findall('.//' + qn('w:del'))) > 0
        or len(body.findall('.//' + qn('w:ins'))) > 0
    )


def _get_paragraph_num_id(paragraph) -> str | None:
    """Extract the numbering ID from a paragraph's XML properties."""
    pPr = paragraph._element.find(qn("w:pPr"))
    if pPr is None:
        return None
    numPr = pPr.find(qn("w:numPr"))
    if numPr is None:
        return None
    numId_elem = numPr.find(qn("w:numId"))
    if numId_elem is None:
        return None
    val = numId_elem.get(qn("w:val"))
    # numId 0 means "no numbering"
    if val is None or val == "0":
        return None
    return val


def _get_paragraph_ilvl(paragraph) -> int:
    """Extract the indentation level from a paragraph's numbering properties."""
    pPr = paragraph._element.find(qn("w:pPr"))
    if pPr is None:
        return 0
    numPr = pPr.find(qn("w:numPr"))
    if numPr is None:
        return 0
    ilvl_elem = numPr.find(qn("w:ilvl"))
    if ilvl_elem is None:
        return 0
    val = ilvl_elem.get(qn("w:val"))
    return int(val) if val else 0


def _get_numbering_start(document, num_id: str, ilvl: int) -> int:
    """Get the start value for a numbering definition at a given level.

    Walks the numbering XML: num -> abstractNumId -> abstractNum -> lvl -> start.
    """
    numbering_part = document.part.numbering_part
    if numbering_part is None:
        return 1

    numbering_xml = numbering_part._element

    # Find the <w:num w:numId="..."> element
    for num_elem in numbering_xml.findall(qn("w:num")):
        if num_elem.get(qn("w:numId")) == num_id:
            abstract_ref = num_elem.find(qn("w:abstractNumId"))
            if abstract_ref is None:
                return 1
            abstract_num_id = abstract_ref.get(qn("w:val"))

            # Find the corresponding <w:abstractNum>
            for abstract_elem in numbering_xml.findall(qn("w:abstractNum")):
                if abstract_elem.get(qn("w:abstractNumId")) == abstract_num_id:
                    # Find the <w:lvl w:ilvl="..."> element
                    for lvl_elem in abstract_elem.findall(qn("w:lvl")):
                        if lvl_elem.get(qn("w:ilvl")) == str(ilvl):
                            start_elem = lvl_elem.find(qn("w:start"))
                            if start_elem is not None:
                                val = start_elem.get(qn("w:val"))
                                return int(val) if val else 1
                    return 1
            return 1
    return 1


_CLAIMS_HEADER = re.compile(r"^(CLAIMS|What is claimed is|I claim|We claim)$", re.IGNORECASE)


def load_docx(file_path: str | Path) -> LoadedDocument:
    """Load a patent .docx file and extract structured content.

    Mirrors the Java PatentAnalyzer's loadDocxContent() and processParagraph():
    - Detects Word numbering via XML (numId, abstractNum, lvl start values)
    - Tracks separate counters per numbering list ID
    - Splits paragraphs into spec (beforeClaims) and claims sections
    - Checks spec paragraphs for valid endings and restrictive wording
    - Detects description-of-drawings section for relaxed ending rules

    Args:
        file_path: Path to the .docx file.

    Returns:
        LoadedDocument with full text and numbering metadata.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file is not a valid .docx.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if path.suffix.lower() != ".docx":
        raise ValueError(f"Not a .docx file: {path}")

    try:
        doc = Document(str(path))
    except Exception as e:
        raise ValueError(f"Invalid .docx file: {e}") from e

    # Build full document text first (for section extraction)
    full_text_lines: list[str] = []
    for para in doc.paragraphs:
        full_text_lines.append(para.text.strip())
    full_text = "\n".join(full_text_lines)

    # Extract drawings section for relaxed ending rules
    drawings_section = extract_description_of_drawings_section(full_text)

    # State tracking (mirrors Java's loadDocxContent)
    list_start_numbers: dict[str, int] = {}  # numId -> current counter
    before_claims = True
    paragraph_numberings: list[int] = []
    claim_numberings: list[int] = []
    missing_ending_paragraphs: list[int] = []
    improper_spec_paragraphs: list[int] = []
    improper_spec_phrases_parts: list[str] = []
    formatted_lines: list[str] = []

    for para in doc.paragraphs:
        paragraph_text = para.text.strip()

        # Check for CLAIMS header
        if _CLAIMS_HEADER.match(paragraph_text):
            before_claims = False

        # Determine if in drawings section
        in_drawings = bool(drawings_section and paragraph_text and paragraph_text in drawings_section)

        # Extract numbering info
        num_id = _get_paragraph_num_id(para)

        if num_id is not None:
            ilvl = _get_paragraph_ilvl(para)
            start = _get_numbering_start(doc, num_id, ilvl)
            current_num = list_start_numbers.get(num_id, start)

            if paragraph_text:
                if before_claims:
                    # Check valid ending
                    if not has_valid_ending(paragraph_text, in_drawings):
                        missing_ending_paragraphs.append(current_num)

                    formatted_lines.append(f"[{current_num}] {paragraph_text}")
                    paragraph_numberings.append(current_num)

                    # Check restrictive wording
                    wording_result = detect_restrictive_wording(paragraph_text, current_num)
                    if wording_result.flagged_paragraphs:
                        for pn in wording_result.flagged_paragraphs:
                            if pn not in improper_spec_paragraphs:
                                improper_spec_paragraphs.append(pn)
                        improper_spec_phrases_parts.append(wording_result.formatted_phrases)
                else:
                    # Claims section
                    formatted_lines.append(f"{current_num}. {paragraph_text}")
                    claim_numberings.append(current_num)

            list_start_numbers[num_id] = current_num + 1
        else:
            # Non-numbered paragraph
            if paragraph_text:
                formatted_lines.append(paragraph_text)

    tracked_changes = detect_tracked_changes(doc)

    return LoadedDocument(
        full_text="\n".join(formatted_lines),
        paragraph_numberings=paragraph_numberings,
        claim_numberings=claim_numberings,
        missing_ending_paragraphs=missing_ending_paragraphs,
        improper_spec_paragraphs=improper_spec_paragraphs,
        improper_spec_phrases="".join(improper_spec_phrases_parts),
        has_tracked_changes=tracked_changes,
    )
