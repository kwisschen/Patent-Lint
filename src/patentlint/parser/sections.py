# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Patent document section extraction using regex patterns.

All functions are pure — no side effects, no I/O.
Patterns validated against USPTO DOCX Section Headers (May 2022) and MPEP § 608.

IMPORTANT: All section boundary patterns are anchored to standalone paragraph headers
(^...$, re.MULTILINE). Input text from docx_loader is newline-delimited paragraphs,
so section headers occupy their own line. This prevents matching header keywords that
appear inside body text (e.g., "This application claims the benefit of priority...").
"""

import re

from patentlint.parser.detection import (
    HANGUL_REJECTION_RATIO,
    JP_KANA_REJECTION_RATIO,
    DetectionReason,
    DetectionResult,
)
from patentlint.parser.language import (
    hangul_ratio,
    jp_kana_ratio,
)

# ---------------------------------------------------------------------------
# Master list of all recognised section headers (standalone paragraph patterns)
# ---------------------------------------------------------------------------

_SECTION_HEADER_PATTERNS = [
    r"CROSS[- ]REFERENCES?\s+TO\s+RELATED(?:\s+(?:PATENT\s+)?APPLICATIONS?)?",
    r"REFERENCE\s+TO\s+RELATED\s+(?:APPLICATIONS?|PATENTS?)",
    r"RELATED\s+APPLICATIONS?",
    r"FIELD\s+OF\s+THE\s+(?:INVENTION|DISCLOSURE)",
    r"TECHNICAL\s+FIELD",
    r"FIELD\s+AND\s+BACKGROUND\s+OF\s+(?:THE\s+)?INVENTION",
    r"BACKGROUND(?:\s+(?:OF\s+(?:THE\s+)?)?(?:DISCLOSURE|INVENTION|ART))?",
    r"DESCRIPTION\s+OF\s+(?:THE\s+)?(?:RELATED\s+ART|PRIOR\s+ART)",
    r"PRIOR\s+ART",
    r"(?:BRIEF\s+)?SUMMARY(?:\s+OF\s+(?:THE\s+)?(?:INVENTION|DISCLOSURE))?",
    r"OBJECT(?:\s+AND\s+SUMMARY)?\s+OF\s+(?:THE\s+)?INVENTION",
    r"DISCLOSURE\s+OF\s+INVENTION",
    r"(?:BRIEF\s+)?DESCRIPTION\s+OF\s+(?:THE\s+)?(?:SEVERAL\s+VIEWS\s+OF\s+(?:THE\s+)?)?(?:DRAWINGS|FIGURES)",
    r"DETAILED\s+DESCRIPTION(?:\s+OF\s+(?:THE\s+)?(?:EXEMPLARY\s+|PREFERRED\s+)?(?:EMBODIMENTS?|INVENTION|DISCLOSURE))?",
    r"DESCRIPTION\s+OF\s+(?:THE\s+)?INVENTION",
    r"BEST\s+MODE\s+FOR\s+CARRYING\s+OUT",
    r"CLAIMS",
    r"What\s+is\s+claimed\s+is\s*:?",
    r"I\s+claim\s*:?",
    r"We\s+(?:hereby\s+)?claim\s*:?",
    r"Claimed\s+are\s*:?",
    r"ABSTRACT(?:\s+OF\s+(?:THE\s+)?(?:DISCLOSURE|INVENTION))?",
]

# Compiled regex matching ANY section header as a standalone paragraph.
# Used as the generic "next section" boundary when extracting sections.
_ANY_SECTION_HEADER = re.compile(
    r"^[ \t]*(?:" + "|".join(_SECTION_HEADER_PATTERNS) + r")[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)


def _find_next_header(text: str, start_pos: int) -> int | None:
    """Find the start position of the next standalone section header after start_pos."""
    m = _ANY_SECTION_HEADER.search(text, pos=start_pos)
    return m.start() if m else None


# ---------------------------------------------------------------------------
# Section extractors
# ---------------------------------------------------------------------------


def extract_claims_section(text: str) -> str:
    """Extract the Claims section from full document text.

    Supports all USPTO-recognized claims headers:
    CLAIMS, What is claimed is:, I claim:, We claim:, We hereby claim:, Claimed are:

    The claims start header must be a standalone paragraph (anchored ^...$).
    """
    # Find standalone CLAIMS header or variant
    start_match = re.search(
        r"^[ \t]*("
        r"CLAIMS"
        r"|What\s+is\s+claimed\s+is\s*:?"
        r"|I\s+claim\s*:?"
        r"|We\s+(?:hereby\s+)?claim\s*:?"
        r"|Claimed\s+are\s*:?"
        r")[ \t]*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not start_match:
        return ""

    start = start_match.start()

    # Verify claim 1 follows
    after_header = text[start_match.end():]
    claim1 = re.search(r"1\.\s+", after_header)
    if not claim1:
        return ""

    # End at next standalone ABSTRACT header
    end_match = re.search(
        r"^[ \t]*ABSTRACT(?:\s+OF\s+(?:THE\s+)?(?:DISCLOSURE|INVENTION))?[ \t]*$",
        text[start:],
        re.IGNORECASE | re.MULTILINE,
    )
    end = start + end_match.start() if end_match else len(text)

    return text[start:end].strip()


def extract_abstract_section(text: str) -> str:
    """Extract the Abstract section, ending before 'reference numerals/numbers'.

    Supports: ABSTRACT, ABSTRACT OF THE DISCLOSURE, ABSTRACT OF THE INVENTION.
    The ABSTRACT header must be a standalone paragraph.
    """
    start_match = re.search(
        r"^[ \t]*ABSTRACT(?:\s+OF\s+(?:THE\s+)?(?:DISCLOSURE|INVENTION))?[ \t]*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not start_match:
        return ""

    start = start_match.start()
    rest = text[start:]

    # End at "reference numerals" or end of document
    end_match = re.search(r"\b(?:reference numerals|reference numbers)\b", rest, re.IGNORECASE)
    end_text = rest[:end_match.start()] if end_match else rest

    return end_text.strip()


def extract_cross_reference_section(text: str) -> str:
    """Extract the Cross-Reference section.

    Supports: CROSS-REFERENCE TO RELATED APPLICATIONS, CROSS-REFERENCES,
    REFERENCE TO RELATED APPLICATIONS, RELATED APPLICATIONS,
    REFERENCE TO RELATED PATENTS.
    Header must be standalone paragraph; ends at next standalone section header.
    """
    start_match = re.search(
        r"^[ \t]*("
        r"CROSS[- ]?REFERENCES?\s+TO\s+RELATED\s+(?:PATENT\s+)?APPLICATIONS?"
        r"|REFERENCE\s+TO\s+RELATED\s+(?:APPLICATIONS?|PATENTS?)"
        r"|RELATED\s+APPLICATIONS?"
        r")[ \t]*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not start_match:
        return ""

    start = start_match.start()
    # Find next section header after this one
    next_hdr = _find_next_header(text, start_match.end())
    end = next_hdr if next_hdr is not None else len(text)

    return text[start:end].strip()


def extract_background_section(text: str) -> str:
    """Extract the Background section.

    Supports: BACKGROUND, BACKGROUND OF THE INVENTION, BACKGROUND ART,
    BACKGROUND OF THE DISCLOSURE, DESCRIPTION OF RELATED ART,
    DESCRIPTION OF THE RELATED ART, PRIOR ART, DESCRIPTION OF THE PRIOR ART,
    FIELD AND BACKGROUND OF THE INVENTION.
    Header must be standalone paragraph; ends at next standalone section header.
    """
    start_match = re.search(
        r"^[ \t]*("
        r"BACKGROUND(?:\s+(?:OF\s+(?:THE\s+)?)?(?:DISCLOSURE|INVENTION|ART))?"
        r"|DESCRIPTION\s+OF\s+(?:THE\s+)?(?:RELATED\s+ART|PRIOR\s+ART)"
        r"|PRIOR\s+ART"
        r"|FIELD\s+AND\s+BACKGROUND\s+OF\s+(?:THE\s+)?INVENTION"
        r")[ \t]*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not start_match:
        return ""

    start = start_match.start()
    next_hdr = _find_next_header(text, start_match.end())
    end = next_hdr if next_hdr is not None else len(text)

    return text[start:end].strip()


def extract_description_of_drawings_section(text: str) -> str:
    """Extract the Brief Description of Drawings section.

    Supports: BRIEF DESCRIPTION OF DRAWINGS, BRIEF DESCRIPTION OF THE DRAWINGS,
    BRIEF DESCRIPTION OF FIGURES, BRIEF DESCRIPTION OF THE FIGURES,
    DESCRIPTION OF DRAWINGS, BRIEF DESCRIPTION OF THE SEVERAL VIEWS OF THE DRAWINGS.
    Header must be standalone paragraph; ends at next standalone section header.
    """
    start_match = re.search(
        r"^[ \t]*(?:BRIEF\s+)?DESCRIPTION\s+OF\s+(?:THE\s+)?(?:SEVERAL\s+VIEWS\s+OF\s+(?:THE\s+)?)?(?:DRAWINGS|FIGURES)[ \t]*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not start_match:
        return ""

    start = start_match.start()
    next_hdr = _find_next_header(text, start_match.end())
    end = next_hdr if next_hdr is not None else len(text)

    return text[start:end].strip()


def extract_detailed_description_section(text: str) -> str:
    """Extract the Detailed Description section.

    Supports: DETAILED DESCRIPTION, DETAILED DESCRIPTION OF THE INVENTION,
    DETAILED DESCRIPTION OF THE DISCLOSURE,
    DETAILED DESCRIPTION OF THE PREFERRED EMBODIMENT(S),
    DETAILED DESCRIPTION OF THE EXEMPLARY EMBODIMENT(S).
    Header must be standalone paragraph; ends at next standalone section header.
    """
    start_match = re.search(
        r"^[ \t]*DETAILED\s+DESCRIPTION"
        r"(?:\s+OF\s+(?:THE\s+)?(?:EXEMPLARY\s+|PREFERRED\s+)?(?:EMBODIMENTS?|INVENTION|DISCLOSURE))?"
        r"[ \t]*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not start_match:
        return ""

    start = start_match.start()
    next_hdr = _find_next_header(text, start_match.end())
    end = next_hdr if next_hdr is not None else len(text)

    return text[start:end].strip()


def extract_summary_section(text: str) -> str:
    """Extract the Summary of the Invention section.

    Supports: SUMMARY, SUMMARY OF THE INVENTION, SUMMARY OF THE DISCLOSURE,
    BRIEF SUMMARY, BRIEF SUMMARY OF THE INVENTION, BRIEF SUMMARY OF THE DISCLOSURE.
    Header must be standalone paragraph; ends at next standalone section header.
    """
    start_match = re.search(
        r"^[ \t]*(?:BRIEF\s+)?SUMMARY(?:\s+OF\s+(?:THE\s+)?(?:INVENTION|DISCLOSURE))?[ \t]*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not start_match:
        return ""

    start = start_match.start()
    next_hdr = _find_next_header(text, start_match.end())
    end = next_hdr if next_hdr is not None else len(text)

    return text[start:end].strip()


def classify_document(full_text: str) -> DetectionResult:
    """Classify a document as US patent or explain why it isn't.

    Positive-evidence-first (ADR-150). Recognized English section
    headers or English claim preambles short-circuit to accept even
    when there's minor cross-script noise (a JP priority doc
    reference, a CN term callout). Cross-script rejection only
    consults ratios when positive evidence is absent, and the ratios
    are specific (JP kana vs. KO Hangul vs. generic East-Asian) so
    the banner can describe WHY a document was rejected.
    """
    # --- Strong positive signals (short-circuit regardless of script) ---
    has_section_header = bool(_ANY_SECTION_HEADER.search(full_text))
    has_en_claim_preamble = bool(
        re.search(
            r"^\s*\d+\.\s+(?:A|An|The)\s+",
            full_text,
            re.MULTILINE | re.IGNORECASE,
        )
    )

    if has_section_header or has_en_claim_preamble:
        return (True, DetectionReason.PATENT_DETECTED)

    # --- No positive evidence: consult cross-script ratios to choose
    #     the banner reason. JP/KO are specific (detection infrastructure
    #     anticipates adding them as first-class jurisdictions); generic
    #     CJK falls through to CONTENT_MISSING since CN/TW re-selection
    #     is a valid recovery path already covered by the banner copy.
    kana = jp_kana_ratio(full_text)
    hangul = hangul_ratio(full_text)
    if kana >= JP_KANA_REJECTION_RATIO:
        return (False, DetectionReason.CROSS_SCRIPT_JAPANESE)
    if hangul >= HANGUL_REJECTION_RATIO:
        return (False, DetectionReason.CROSS_SCRIPT_KOREAN)

    return (False, DetectionReason.CONTENT_MISSING)


def detect_patent_document(full_text: str) -> bool:
    """Back-compat boolean wrapper around :func:`classify_document`."""
    is_patent, _ = classify_document(full_text)
    return is_patent


def extract_title(full_text: str) -> str:
    """Extract the patent title as text preceding the first section header.

    Mirrors the heuristic already used inside ``check_required_sections``.
    Titles are conventionally typeset above the first labeled section
    (CROSS-REFERENCE, BACKGROUND, etc.). Returns the stripped text or ``""``
    when no preceding text exists.
    """
    first_header = _ANY_SECTION_HEADER.search(full_text)
    candidate = full_text[:first_header.start()] if first_header else full_text
    # Keep the last non-empty line of the pre-header block — patent filings
    # typically carry boilerplate / applicant identifiers above the title.
    lines = [ln.strip() for ln in candidate.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def detect_prior_art_citations(text: str) -> str:
    """Detect prior art patent citations in text.

    Matches:
    - U.S. patent numbers: 7,654,321 or 10,123,456
    - U.S. application numbers: 16/123,456
    - Explicit references: U.S. Patent No. X,XXX,XXX
    - Generic long numeric sequences (original behavior preserved for backward compat)
    """
    # Original pattern preserved — matches long numeric sequences
    matches = re.findall(r"(\d{1,9}(?:[/,.\-\s]?\d{1,9}){5,})", text)
    return ", ".join(m.strip() for m in matches)
