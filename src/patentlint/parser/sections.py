# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
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


def detect_patent_document(full_text: str) -> bool:
    """Heuristic check for whether the document appears to be a patent specification.

    Returns True if patent indicators are found, False otherwise.
    Errs on the side of True — false positives are much less harmful than
    false negatives (flagging a real patent as non-patent).
    """
    # 1. Recognized section header
    if _ANY_SECTION_HEADER.search(full_text):
        return True

    # 2. Numbered claims pattern: "1. A ..." or "1. An ..."
    if re.search(r"^\s*\d+\.\s+(?:A|An|The)\s+", full_text, re.MULTILINE | re.IGNORECASE):
        return True

    # 3. Bracketed paragraph numbers [0001] style — need 3+
    if len(re.findall(r"\[\d{4}\]", full_text)) >= 3:
        return True

    return False


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
