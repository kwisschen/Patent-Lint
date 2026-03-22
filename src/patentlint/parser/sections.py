"""Patent document section extraction using regex patterns.

All functions are pure — no side effects, no I/O.
Patterns validated against USPTO DOCX Section Headers (May 2022) and MPEP § 608.
"""

import re


def extract_claims_section(text: str) -> str:
    """Extract the Claims section from full document text.

    Supports all USPTO-recognized claims headers:
    CLAIMS, What is claimed is:, I claim:, We claim:, We hereby claim:, Claimed are:
    """
    start_match = re.search(
        r"(^\s*("
        r"CLAIMS([\s\r\n]*(What is claimed is|I claim|We claim|We hereby claim|Claimed are):?)?"
        r"|What is claimed is:"
        r"|I claim:"
        r"|We (hereby )?claim:"
        r"|Claimed are:"
        r")[\s\r\n]*1\.\s+[\s\S]*?)",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    start = start_match.start() if start_match else -1

    end_match = re.search(
        r"\bABSTRACT\b(\s+OF\s+(THE\s+)?(DISCLOSURE|INVENTION))?",
        text,
        re.IGNORECASE,
    )
    end = end_match.start() if end_match else len(text)

    if start != -1 and start < end:
        return text[start:end].strip()
    return ""


def extract_abstract_section(text: str) -> str:
    """Extract the Abstract section, ending before 'reference numerals/numbers'.

    Supports: ABSTRACT, ABSTRACT OF THE DISCLOSURE, ABSTRACT OF THE INVENTION.
    Uses \\Z (absolute end-of-string) to avoid lazy+$ bug where $ in MULTILINE
    mode matches end-of-line and lazy quantifier returns empty match.
    """
    match = re.search(
        r"\bABSTRACT\b(\s+OF\s+(THE\s+)?(DISCLOSURE|INVENTION))?"
        r"[\s\S]*?(?=\b(reference numerals|reference numbers)\b|\Z)",
        text,
        re.IGNORECASE,
    )
    return match.group().strip() if match else ""


def extract_cross_reference_section(text: str) -> str:
    """Extract the Cross-Reference section.

    Supports: CROSS-REFERENCE TO RELATED APPLICATIONS, CROSS-REFERENCES,
    REFERENCE TO RELATED APPLICATIONS, RELATED APPLICATIONS,
    REFERENCE TO RELATED PATENTS
    """
    match = re.search(
        r"\b(cross[- ]?references?\s+to\s+related\s+applications?"
        r"|reference\s+to\s+related\s+(applications?|patents?)"
        r"|related\s+applications?"
        r")\b"
        r"[\s\S]*?"
        r"(?=\b("
        r"field\s+of\s+(the\s+)?(disclosure|invention)"
        r"|technical\s+field"
        r"|background"
        r")\b)",
        text,
        re.IGNORECASE,
    )
    return match.group().strip() if match else ""


def extract_background_section(text: str) -> str:
    """Extract the Background section.

    Supports: BACKGROUND OF THE INVENTION, BACKGROUND ART,
    DESCRIPTION OF RELATED ART, DESCRIPTION OF THE RELATED ART,
    PRIOR ART, DESCRIPTION OF THE PRIOR ART,
    FIELD AND BACKGROUND OF THE INVENTION
    """
    match = re.search(
        r"\b("
        r"background\s+(of\s+(the\s+)?)?(disclosure|invention|art)"
        r"|description\s+of\s+(the\s+)?(related\s+art|prior\s+art)"
        r"|prior\s+art"
        r"|field\s+and\s+background\s+of\s+(the\s+)?invention"
        r")\b"
        r"[\s\S]*?"
        r"(?=\b("
        r"(brief\s+)?summary(\s+of\s+(the\s+)?invention)?"
        r"|object(\s+and\s+summary)?\s+of\s+(the\s+)?invention"
        r"|brief\s+description\s+of"
        r"|disclosure\s+of\s+invention"
        r")\b|\Z)",
        text,
        re.IGNORECASE,
    )
    return match.group().strip() if match else ""


def extract_description_of_drawings_section(text: str) -> str:
    """Extract the Brief Description of Drawings section.

    Supports: BRIEF DESCRIPTION OF DRAWINGS, BRIEF DESCRIPTION OF THE DRAWINGS,
    BRIEF DESCRIPTION OF FIGURES, BRIEF DESCRIPTION OF THE FIGURES,
    DESCRIPTION OF DRAWINGS
    """
    match = re.search(
        r"\b(brief\s+)?description\s+of\s+(the\s+)?(drawings|figures)\b"
        r"[\s\S]*?"
        r"(?=\b("
        r"detailed\s+description(\s+of\s+(the\s+)?(\w+\s+)?(embodiment|embodiments|invention|drawings))?"
        r"|description\s+of\s+(the\s+)?invention"
        r"|best\s+mode\s+for\s+carrying\s+out"
        r")\b|\Z)",
        text,
        re.IGNORECASE,
    )
    return match.group().strip() if match else ""


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
