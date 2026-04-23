# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""TW patent .docx section extraction — 【】bracket header format."""

from __future__ import annotations

import re

from patentlint.analysis.figure_refs import TW_PARSER
from patentlint.models import TwPatentDocument, TwPatentType
from patentlint.parser.claims_tw import parse_tw_claims
from patentlint.parser.detection import (
    HANGUL_REJECTION_RATIO,
    JP_KANA_REJECTION_RATIO,
    DetectionReason,
    DetectionResult,
)
from patentlint.parser.language import (
    count_cjk_chars,
    hangul_ratio,
    jp_kana_ratio,
)
from patentlint.parser.symbol_table_tw import parse_tw_symbol_table

# ---------------------------------------------------------------------------
# Bracket header patterns — 【section_name】
# ---------------------------------------------------------------------------

# Match bracket headers but NOT paragraph numbers 【0001】
_BRACKET_HEADER = re.compile(r"^【([^\d].+?)】(.*)$")

# Map bracket header content to TwPatentDocument field names.
# Includes both statute-standard headers and firm-variant prefixed headers.
_SECTION_MAP: dict[str, str] = {
    # Title variants
    "發明名稱": "title",
    "新型名稱": "title",
    "中文發明名稱": "title",
    "中文新型名稱": "title",
    # Body sections
    "技術領域": "technical_field",
    "先前技術": "prior_art",
    "發明內容": "disclosure",
    "新型內容": "disclosure",
    "圖式簡單說明": "drawings_description",
    "實施方式": "embodiment",
    "符號說明": "symbol_table",
    # Claims variants
    "申請專利範圍": "claims",
    "發明申請專利範圍": "claims",
    "新型申請專利範圍": "claims",
    # Abstract variants
    "摘要": "abstract",
    "發明摘要": "abstract",
    "新型摘要": "abstract",
    # Representative drawing
    "代表圖": "representative_drawing",
    "指定代表圖": "representative_drawing",
    "代表圖之符號簡單說明": "representative_drawing_symbols",
}

# Canonical TwPatentDocument body-section field names. Used to filter
# _SECTION_MAP targets when populating section_order; non-body targets
# (title/claims/abstract/representative_drawing/representative_drawing_symbols)
# are not tracked because check_section_ordering only evaluates body sections.
_BODY_SECTION_KEYS: frozenset[str] = frozenset({
    "technical_field",
    "prior_art",
    "disclosure",
    "drawings_description",
    "embodiment",
    "symbol_table",
})

# Headers to skip (not content sections — top-level dividers or English titles)
_SKIP_HEADERS: set[str] = {
    "發明說明書",
    "新型說明書",
    "英文發明名稱",
    "英文新型名稱",
}

# Headers that indicate utility model (any header containing 新型)
_UTILITY_MODEL_KEYWORDS = {"新型摘要", "新型說明書", "新型內容", "新型申請專利範圍", "新型名稱", "中文新型名稱"}

# All canonical TIPO section names (for bracketless / variant-bracket detection).
# Includes _SECTION_MAP keys (body sections, title, claims, abstract, etc.) plus
# _SKIP_HEADERS (top-level dividers like 發明說明書) since those also must carry
# 【】 per 專利法施行細則 §17.
_CANONICAL_SECTION_NAMES: frozenset[str] = (
    frozenset(_SECTION_MAP.keys()) | frozenset(_SKIP_HEADERS)
)

# Variant bracket pairs some drafters use instead of the required 【】.
_VARIANT_BRACKET_PAIRS: tuple[tuple[str, str], ...] = (
    ("[", "]"),
    ("〔", "〕"),
    ("(", ")"),
    ("（", "）"),
)

# ---------------------------------------------------------------------------
# Paragraph numbering: 【NNNN】 at start of body text
# ---------------------------------------------------------------------------

_PARA_NUM_PATTERN = re.compile(r"^【(\d{4})】")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Backwards-compat alias — callers and tests import _count_cjk_chars from
# this module. The canonical implementation lives in parser.language.
_count_cjk_chars = count_cjk_chars


def _find_bracketless_section_headers(paragraphs: list[str]) -> list[str]:
    """Scan paragraphs for canonical TIPO section names lacking required 【】.

    Detects four missing-bracket patterns:
    (a) bare canonical name alone on a line (``先前技術``)
    (b) opening 【 only, closing 】 missing (``【先前技術``)
    (c) closing 】 only, opening 【 missing (``先前技術】``)
    (d) variant brackets wrapping a canonical name (``[先前技術]``,
        ``〔先前技術〕``, ``(先前技術)``, ``（先前技術）``)

    Correctly-bracketed 【…】 headers matched by the main parser regex are
    not flagged. Returns first-seen occurrences, de-duplicated, capped at 50
    entries to bound worst-case payload size.
    """
    seen: set[str] = set()
    findings: list[str] = []
    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            continue
        # Correctly bracketed 【<name>】... — main parser handles.
        if _BRACKET_HEADER.match(stripped):
            continue
        candidate: str | None = None
        # Bare canonical name (no brackets at all)
        if stripped in _CANONICAL_SECTION_NAMES:
            candidate = stripped
        # Opening 【 only, closing 】 absent
        elif stripped.startswith("【") and "】" not in stripped:
            inner = stripped[1:].strip()
            if inner in _CANONICAL_SECTION_NAMES:
                candidate = stripped
        # Closing 】 only, opening 【 absent
        elif stripped.endswith("】") and "【" not in stripped:
            inner = stripped[:-1].strip()
            if inner in _CANONICAL_SECTION_NAMES:
                candidate = stripped
        # Variant brackets wrapping a canonical name
        else:
            for open_b, close_b in _VARIANT_BRACKET_PAIRS:
                if stripped.startswith(open_b) and stripped.endswith(close_b):
                    inner = stripped[len(open_b):-len(close_b)].strip()
                    if inner in _CANONICAL_SECTION_NAMES:
                        candidate = stripped
                    break
        if candidate is not None and candidate not in seen:
            seen.add(candidate)
            findings.append(candidate)
            if len(findings) >= 50:
                break
    return findings


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def classify_document_tw(paragraphs: list[str]) -> DetectionResult:
    """Classify a .docx as TW patent or explain why it isn't.

    Two-layer decision (ADR-150):

    1. Cross-script rejection runs FIRST with a ratio threshold
       (:data:`JP_KANA_REJECTION_RATIO` / :data:`HANGUL_REJECTION_RATIO`).
       A document with meaningful JP kana or KO Hangul content is
       rejected as the corresponding jurisdiction regardless of how
       many 【】 bracket headers it carries — JPO patents also use
       【】 headers, so bracket count alone cannot distinguish TIPO
       from JPO; kana content does.

    2. Positive TW evidence wins AFTER cross-script clears. Single
       【section-name】 header or single 請求項 mention is enough —
       neither character is used by CN simplified or US. 【NNNN】
       paragraph numbers alone need ≥ 3 since the convention is
       shared with other jurisdictions.

    The ratio-based cross-script check (not presence) is the key
    anti-false-positive measure: real-world TW drafts translated
    from JP priority documents sometimes retain trace katakana
    (brand names, a stray middle-dot) well below 0.5% content.
    Pre-ADR-150 presence-based logic rejected those documents; the
    ratio tolerates them while still catching genuinely JP input.
    """
    full_text = "\n".join(paragraphs)

    # --- Layer 1: Cross-script rejection (ratio-based, always first) ---
    kana = jp_kana_ratio(full_text)
    hangul = hangul_ratio(full_text)
    if kana >= JP_KANA_REJECTION_RATIO:
        return (False, DetectionReason.CROSS_SCRIPT_JAPANESE)
    if hangul >= HANGUL_REJECTION_RATIO:
        return (False, DetectionReason.CROSS_SCRIPT_KOREAN)

    # --- Layer 2: Positive TW evidence ---
    bracket_count = 0
    qing_count = 0
    para_num_count = 0
    for para in paragraphs:
        stripped = para.strip()
        if _BRACKET_HEADER.match(stripped):
            bracket_count += 1
        if "請求項" in stripped:
            qing_count += 1
        if _PARA_NUM_PATTERN.match(stripped):
            para_num_count += 1

    if bracket_count >= 1 or qing_count >= 1 or para_num_count >= 3:
        return (True, DetectionReason.PATENT_DETECTED)

    return (False, DetectionReason.CONTENT_MISSING)


def detect_patent_document_tw(paragraphs: list[str]) -> bool:
    """Back-compat boolean wrapper around :func:`classify_document_tw`."""
    is_patent, _ = classify_document_tw(paragraphs)
    return is_patent


def extract_tw_sections(
    paragraphs: list[str],
    paragraph_word_numbers: list[str | None] | None = None,
) -> TwPatentDocument:
    """Extract TW patent sections from .docx paragraphs using 【】bracket headers.

    Scans paragraphs for bracket-delimited section headers and collects
    content into the corresponding TwPatentDocument fields.

    Handles both statute-standard headers (【發明名稱】) and firm-variant
    prefixed headers (【中文發明名稱】, 【發明申請專利範圍】, etc.).

    ``paragraph_word_numbers`` is an optional parallel list with the Word
    auto-numbering string (``"0001"``, ``"0109"``, …) for each paragraph,
    or ``None`` for paragraphs Word doesn't auto-number. When supplied, the
    word-numbers of body paragraphs are preserved on
    ``TwPatentDocument.body_paragraph_word_numbers`` so downstream checks
    can flag paragraphs by the 【NNNN】 label the drafter sees in Word
    rather than an internal ordinal.
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
    # Parallel word-number lists for body sections only (others don't need it).
    body_section_word_numbers: dict[str, list[str | None]] = {
        "technical_field": [],
        "prior_art": [],
        "disclosure": [],
        "drawings_description": [],
        "embodiment": [],
    }

    def _word_num_at(index: int) -> str | None:
        if paragraph_word_numbers is None:
            return None
        if index < 0 or index >= len(paragraph_word_numbers):
            return None
        return paragraph_word_numbers[index]

    is_utility_model = False
    current_section: str | None = None
    section_order: list[str] = []
    in_spec_body = False  # Track whether we're inside 【發明說明書】/【新型說明書】
    waiting_for_abstract_text = False  # After 【中文】, next non-empty para is abstract
    spec_title: str | None = None  # Title from spec body (preferred)
    abstract_title: str | None = None  # Title from abstract preamble (fallback)
    abstract_header_seen = False  # 【摘要】/【發明摘要】/【新型摘要】 encountered
    claims_header_seen = False    # 【申請專利範圍】 / 【發明申請專利範圍】 / 【新型申請專利範圍】

    for idx, para in enumerate(paragraphs):
        stripped = para.strip()
        if not stripped:
            continue

        # Check for bracket header
        m = _BRACKET_HEADER.match(stripped)
        if m:
            header_text = m.group(1).strip()
            inline_text = m.group(2).strip()

            # Handle 【中文】 — abstract text marker
            if header_text == "中文":
                waiting_for_abstract_text = True
                current_section = "abstract"
                continue

            # Stop waiting for abstract text on any new header
            waiting_for_abstract_text = False

            # Skip headers (top-level dividers, English titles)
            if header_text in _SKIP_HEADERS:
                if header_text in ("發明說明書", "新型說明書"):
                    in_spec_body = True
                if header_text in _UTILITY_MODEL_KEYWORDS:
                    is_utility_model = True
                current_section = None
                continue

            # Check utility model
            if header_text in _UTILITY_MODEL_KEYWORDS:
                is_utility_model = True

            mapped = _SECTION_MAP.get(header_text)
            if mapped is not None:
                current_section = mapped
                if mapped in _BODY_SECTION_KEYS and mapped not in section_order:
                    section_order.append(mapped)
                if mapped == "abstract":
                    abstract_header_seen = True
                elif mapped == "claims":
                    claims_header_seen = True

                # Handle inline text after header (e.g., 【中文發明名稱】高頻基板用...)
                if inline_text:
                    if mapped == "title":
                        if in_spec_body:
                            spec_title = inline_text
                        else:
                            abstract_title = inline_text
                    elif mapped == "representative_drawing":
                        section_content[mapped].append(inline_text)
                    # For other sections, inline text is just content
                    elif mapped not in ("title",):
                        section_content[mapped].append(inline_text)
                        if mapped in body_section_word_numbers:
                            body_section_word_numbers[mapped].append(None)
                continue

            # Unknown header — stop accumulating into current section
            current_section = None
            continue

        # Handle abstract text after 【中文】 marker
        if waiting_for_abstract_text:
            section_content["abstract"].append(stripped)
            waiting_for_abstract_text = False
            current_section = "abstract"
            continue

        if current_section is not None:
            section_content[current_section].append(stripped)
            if current_section in body_section_word_numbers:
                body_section_word_numbers[current_section].append(_word_num_at(idx))

    # --- Patent type ---
    patent_type = TwPatentType.UTILITY_MODEL if is_utility_model else TwPatentType.INVENTION

    # --- Title: prefer spec body title over abstract preamble title ---
    if spec_title:
        title = spec_title
    elif abstract_title:
        title = abstract_title
    elif section_content["title"]:
        title = " ".join(section_content["title"]).strip()
    else:
        title = ""

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

    # Flat parallel list of Word auto-numbers aligned with the same
    # body-section concatenation order used elsewhere in the pipeline.
    body_paragraph_word_numbers: list[str | None] = (
        body_section_word_numbers["technical_field"]
        + body_section_word_numbers["prior_art"]
        + body_section_word_numbers["disclosure"]
        + body_section_word_numbers["drawings_description"]
        + body_section_word_numbers["embodiment"]
    )
    has_paragraph_numbering = (
        len(paragraph_numbers) > 0
        or any(n is not None for n in body_paragraph_word_numbers)
    )

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
    combined_text = drawings_text + "\n" + embodiment_text
    figure_refs = list(TW_PARSER.extract(combined_text).ordered)

    bracketless_section_headers = _find_bracketless_section_headers(paragraphs)

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
        body_paragraph_word_numbers=body_paragraph_word_numbers,
        section_order=section_order,
        bracketless_section_headers=bracketless_section_headers,
        abstract_header_seen=abstract_header_seen,
        claims_header_seen=claims_header_seen,
        input_format="docx",
    )
