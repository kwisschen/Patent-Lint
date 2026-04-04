# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""TW patent .docx section extraction — 【】bracket header format."""

from __future__ import annotations

import re

from patentlint.models import TwPatentDocument, TwPatentType
from patentlint.parser.claims_tw import parse_tw_claims
from patentlint.parser.symbol_table_tw import parse_tw_symbol_table

# ---------------------------------------------------------------------------
# Bracket header patterns — 【section_name】
# ---------------------------------------------------------------------------

_BRACKET_HEADER = re.compile(r"^【(.+?)】\s*$")

# Map bracket header content to TwPatentDocument field names
_SECTION_MAP: dict[str, str] = {
    "發明名稱": "title",
    "新型名稱": "title",
    "技術領域": "technical_field",
    "先前技術": "prior_art",
    "發明內容": "disclosure",
    "新型內容": "disclosure",
    "圖式簡單說明": "drawings_description",
    "實施方式": "embodiment",
    "符號說明": "symbol_table",
    "申請專利範圍": "claims",
    "摘要": "abstract",
    "代表圖": "representative_drawing",
    "代表圖之符號簡單說明": "representative_drawing_symbols",
}

# Headers that indicate utility model
_UTILITY_MODEL_HEADERS = {"新型名稱", "新型內容"}

# ---------------------------------------------------------------------------
# Paragraph numbering: 【NNNN】 at start of body text
# ---------------------------------------------------------------------------

_PARA_NUM_PATTERN = re.compile(r"^【(\d{4})】")

# ---------------------------------------------------------------------------
# Figure reference patterns for TW: 圖N, 第N圖, 圖式N
# ---------------------------------------------------------------------------

_FIGURE_REF_PATTERN = re.compile(r"(?:第\s*(\d+)\s*圖|圖式?\s*(\d+[a-zA-Z]?))")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_cjk_chars(text: str) -> int:
    """Count CJK characters in text (excluding ASCII, spaces, and punctuation).

    Counts CJK Unified Ideographs, CJK Extension blocks, Bopomofo,
    Katakana, Hiragana, and fullwidth alphanumeric — i.e., characters
    that TIPO counts toward the 250-char abstract limit.
    """
    count = 0
    for ch in text:
        cp = ord(ch)
        if (
            0x4E00 <= cp <= 0x9FFF        # CJK Unified Ideographs
            or 0x3400 <= cp <= 0x4DBF      # CJK Extension A
            or 0x20000 <= cp <= 0x2A6DF    # CJK Extension B
            or 0x2A700 <= cp <= 0x2B73F    # CJK Extension C
            or 0x2B740 <= cp <= 0x2B81F    # CJK Extension D
            or 0x3040 <= cp <= 0x309F      # Hiragana
            or 0x30A0 <= cp <= 0x30FF      # Katakana
            or 0x3100 <= cp <= 0x312F      # Bopomofo
            or 0xFF01 <= cp <= 0xFF5E      # Fullwidth ASCII variants
        ):
            count += 1
    return count


def _extract_figure_refs(text: str) -> list[str]:
    """Extract figure reference strings from text."""
    refs: list[str] = []
    for m in _FIGURE_REF_PATTERN.finditer(text):
        refs.append(m.group(0))
    return refs


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def extract_tw_sections(paragraphs: list[str]) -> TwPatentDocument:
    """Extract TW patent sections from .docx paragraphs using 【】bracket headers.

    Scans paragraphs for bracket-delimited section headers and collects
    content into the corresponding TwPatentDocument fields.
    """
    # Accumulate paragraphs per section
    section_content: dict[str, list[str]] = {
        "title": [],
        "technical_field": [],
        "prior_art": [],
        "disclosure": [],
        "drawings_description": [],
        "embodiment": [],
        "symbol_table": [],
        "claims": [],
        "abstract": [],
        "representative_drawing": [],
        "representative_drawing_symbols": [],
    }

    is_utility_model = False
    current_section: str | None = None

    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            continue

        # Check for bracket header
        m = _BRACKET_HEADER.match(stripped)
        if m:
            header_text = m.group(1).strip()
            mapped = _SECTION_MAP.get(header_text)
            if mapped is not None:
                current_section = mapped
                if header_text in _UTILITY_MODEL_HEADERS:
                    is_utility_model = True
                continue
            # Unknown header — stop accumulating into current section
            current_section = None
            continue

        if current_section is not None:
            section_content[current_section].append(stripped)

    # --- Patent type ---
    patent_type = TwPatentType.UTILITY_MODEL if is_utility_model else TwPatentType.INVENTION

    # --- Title ---
    title = " ".join(section_content["title"]).strip()

    # --- Paragraph numbering (from body sections) ---
    body_sections = (
        section_content["technical_field"]
        + section_content["prior_art"]
        + section_content["disclosure"]
        + section_content["drawings_description"]
        + section_content["embodiment"]
    )
    paragraph_numbers: list[str] = []
    for para in body_sections:
        pm = _PARA_NUM_PATTERN.match(para)
        if pm:
            paragraph_numbers.append(pm.group(1))
    has_paragraph_numbering = len(paragraph_numbers) > 0

    # --- Symbol table ---
    symbol_table = parse_tw_symbol_table(section_content["symbol_table"])

    # --- Representative drawing ---
    rep_drawing_text = " ".join(section_content["representative_drawing"]).strip()
    representative_drawing = rep_drawing_text if rep_drawing_text else None

    # --- Representative drawing symbols ---
    representative_drawing_symbols = parse_tw_symbol_table(
        section_content["representative_drawing_symbols"]
    )

    # --- Claims ---
    claims = parse_tw_claims(section_content["claims"])

    # --- Abstract ---
    abstract_text = "\n".join(section_content["abstract"]).strip()
    abstract_char_count = _count_cjk_chars(abstract_text)

    # --- Figure references ---
    drawings_text = "\n".join(section_content["drawings_description"])
    embodiment_text = "\n".join(section_content["embodiment"])
    figure_refs = _extract_figure_refs(drawings_text + "\n" + embodiment_text)

    return TwPatentDocument(
        patent_type=patent_type,
        title=title,
        technical_field=section_content["technical_field"],
        prior_art=section_content["prior_art"],
        disclosure=section_content["disclosure"],
        drawings_description=section_content["drawings_description"],
        embodiment=section_content["embodiment"],
        symbol_table=symbol_table,
        claims=claims,
        abstract_text=abstract_text,
        abstract_char_count=abstract_char_count,
        representative_drawing=representative_drawing,
        representative_drawing_symbols=representative_drawing_symbols,
        figure_refs=figure_refs,
        paragraph_numbers=paragraph_numbers,
        has_paragraph_numbering=has_paragraph_numbering,
        input_format="docx",
    )
