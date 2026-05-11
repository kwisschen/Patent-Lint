# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Section extraction for EPC (European Patent Convention) English drafts.

EPC drafts follow the Rule 42(1) EPC structure for the description:
  (a) state the technical field
  (b) indicate the background art
  (c) disclose the invention (summary)
  (d) briefly describe the figures (if any)
  (e) describe in detail one way of carrying out the invention with examples

Plus per Art. 78(1) EPC: title (Rule 41(2)(b)), description, claims, abstract,
drawings (if any).

The US section extractor in ``sections.py`` already recognises most of the
EPC English section-header vocabulary (TECHNICAL FIELD, BACKGROUND ART,
DISCLOSURE OF INVENTION, etc.) via the master ``_ANY_SECTION_HEADER``
regex. v1 EPC extractor delegates to the US extractors for those overlaps
and adds EPC-specific tuning where the conventions diverge.

References:
  Art. 78(1) EPC — required application contents
  Rule 41(2) EPC — request-form requirements
  Rule 42(1) EPC — description sub-sections
  Rule 43 EPC — claims
  Rule 46 EPC — drawings
  Rule 47 EPC — abstract
  EPO Guidelines Part F-II § 4 (description); F-IV (claims)
"""

from __future__ import annotations

import re

from patentlint.parser import sections as us_sections


# Master EPC English section-header regex. Reuses every alternation from the
# US master regex (which already covers EPC variants like "TECHNICAL FIELD"
# and "BACKGROUND ART") and adds patterns EPC drafters use that US drafters
# typically don't. The bare-line anchor + IGNORECASE flags match the US
# convention.
_EPC_HEADER_PATTERNS = list(us_sections._SECTION_HEADER_PATTERNS) + [
    # EPC-specific variants on the disclosure / summary
    r"DISCLOSURE\s+OF\s+(?:THE\s+)?INVENTION",  # EPC convention
    r"SUMMARY\s+OF\s+(?:THE\s+)?DISCLOSURE",
    # EPC-specific variants on background
    r"BACKGROUND\s+ART",
    # EPC-specific variants on detailed description
    r"DETAILED\s+DESCRIPTION\s+OF\s+(?:THE\s+)?EMBODIMENT(?:S)?",
    r"WAYS?\s+OF\s+CARRYING\s+OUT(?:\s+THE\s+INVENTION)?",
]

_EPC_ANY_HEADER = re.compile(
    r"^[ \t]*(?:" + "|".join(_EPC_HEADER_PATTERNS) + r")[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)


# --- Section extractors -------------------------------------------------------
# v1: delegate to US extractors. The US regex already covers EPC variants
# because EPO Guidelines F-II and MPEP § 608.01(a) share most heading
# vocabulary in English. EPC-specific divergences land here as overrides
# only when real-corpus signal motivates them.


def extract_title_epc(full_text: str) -> str:
    """Extract the title of the invention per Rule 41(2)(b) EPC.

    Uses the same heuristic as the US extractor: title is the last non-empty
    line before the first recognised section header.
    """
    first_header = _EPC_ANY_HEADER.search(full_text)
    candidate = full_text[: first_header.start()] if first_header else full_text
    lines = [ln.strip() for ln in candidate.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def extract_claims_section_epc(full_text: str) -> str:
    """Extract the claims section per Rule 43 EPC.

    Reuses the US claims extractor — same English claims-section headers
    (CLAIMS, "What is claimed is:", etc.) are valid in EPC English drafts.
    """
    return us_sections.extract_claims_section(full_text)


def extract_abstract_section_epc(full_text: str) -> str:
    """Extract the abstract per Rule 47 EPC."""
    return us_sections.extract_abstract_section(full_text)


def extract_background_section_epc(full_text: str) -> str:
    """Extract the Background Art per Rule 42(1)(b) EPC."""
    return us_sections.extract_background_section(full_text)


def extract_technical_field_section_epc(full_text: str) -> str:
    """Extract the Technical Field per Rule 42(1)(a) EPC.

    Boundary: from a "FIELD" or "TECHNICAL FIELD" header to the next
    recognised section. Mirrors the US background extractor's shape but
    targets the Field-of-Invention header family.
    """
    start_match = re.search(
        r"^[ \t]*(?:"
        r"FIELD\s+OF\s+THE\s+(?:INVENTION|DISCLOSURE)"
        r"|TECHNICAL\s+FIELD"
        r"|FIELD\s+AND\s+BACKGROUND\s+OF\s+(?:THE\s+)?INVENTION"
        r")[ \t]*$",
        full_text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not start_match:
        return ""
    start = start_match.start()
    next_match = _EPC_ANY_HEADER.search(full_text, pos=start_match.end())
    end = next_match.start() if next_match else len(full_text)
    return full_text[start:end].strip()


def extract_summary_section_epc(full_text: str) -> str:
    """Extract the disclosure / summary per Rule 42(1)(c) EPC."""
    return us_sections.extract_summary_section(full_text)


def extract_drawings_description_section_epc(full_text: str) -> str:
    """Extract the brief description of the drawings per Rule 46(2)(h) EPC."""
    return us_sections.extract_description_of_drawings_section(full_text)


def extract_detailed_description_section_epc(full_text: str) -> str:
    """Extract the detailed description per Rule 42(1)(e) EPC."""
    return us_sections.extract_detailed_description_section(full_text)


def extract_description_section_epc(full_text: str) -> str:
    """Extract the entire description (Rule 42 sub-sections concatenated).

    For checks that need the full description body rather than a single
    sub-section. Concatenates Technical Field + Background + Summary +
    Drawings Description + Detailed Description in that order, separating
    with blank lines.
    """
    parts = [
        extract_technical_field_section_epc(full_text),
        extract_background_section_epc(full_text),
        extract_summary_section_epc(full_text),
        extract_drawings_description_section_epc(full_text),
        extract_detailed_description_section_epc(full_text),
    ]
    return "\n\n".join(p for p in parts if p)
