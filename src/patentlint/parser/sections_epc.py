# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Section extraction for EPC (European Patent Convention) English drafts.

EPC drafts follow the Rule 42(1) structure: technical field → background art →
disclosure of invention → brief description of the drawings → description of
embodiments (typically headed "Detailed Description of [Embodiments]"). The
US loader (``load_docx``) is reused because EPC English drafts are Latin-script
.docx files; this module owns the EPC-specific section-header recognition and
the title-extraction rules (Rule 41(2)(b)).

Sections planned for v1 implementation order:
  1. extract_title_epc
  2. extract_claims_section_epc
  3. extract_description_section_epc (Rule 42 sub-section split)
  4. extract_abstract_section_epc
  5. extract_drawings_description_section_epc
  6. classify_document_epc — positive-evidence-first detection (ADR-150 style)

Stubs only at scaffolding stage. Each function returns an empty string / None
so the pipeline runs end-to-end without crashing; first-real-implementation
commits land per-section as the statute research grounds them.

References (verify before implementing):
  Art. 78(1) EPC — required application contents
  Rule 41(2) EPC — request-form requirements (title)
  Rule 42(1) EPC — description sub-sections
  Rule 43 EPC — claims form
  Rule 46 EPC — drawings
  Rule 47 EPC — abstract
  EPO Guidelines for Examination, Part F (formal requirements)
"""

from __future__ import annotations


def extract_title_epc(full_text: str) -> str:
    """Extract the title of the invention per Rule 41(2)(b) EPC.

    Stub: returns empty string. Real implementation pending statute-grounded
    section-header regex.
    """
    return ""


def extract_claims_section_epc(full_text: str) -> str:
    """Extract the claims section per Rule 43 EPC.

    Stub: returns empty string.
    """
    return ""


def extract_abstract_section_epc(full_text: str) -> str:
    """Extract the abstract per Rule 47 EPC.

    Stub: returns empty string.
    """
    return ""


def extract_description_section_epc(full_text: str) -> str:
    """Extract the description (Rule 42 sub-sections concatenated).

    Stub: returns empty string.
    """
    return ""


def extract_drawings_description_section_epc(full_text: str) -> str:
    """Extract the brief description of the drawings per Rule 46(2)(h).

    Stub: returns empty string.
    """
    return ""
