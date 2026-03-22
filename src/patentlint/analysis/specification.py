"""Specification section analysis.

Checks paragraph endings, numbering sequentiality, restrictive wording,
and sequence listing references.
"""

import re

from patentlint.models import SpecWordingResult

_RESTRICTIVE_WORDING = re.compile(
    r"(?i)\b(invention|always|never|must|solely|every|required|essential|critical|key|vital"
    r"|necessary|imperative|indispensable|particular|specific)\b"
)


def has_valid_ending(paragraph_text: str, is_description_of_drawings: bool = False) -> bool:
    """Check if a paragraph has valid ending punctuation."""
    t = paragraph_text.strip()
    base_endings = (
        t.endswith(".") or t.endswith('.\"') or t.endswith('.\u201D')
        or t.endswith("!") or t.endswith('!\"') or t.endswith('!\u201D')
        or t.endswith("?") or t.endswith('?\"') or t.endswith('?\u201D')
        or t.endswith(":")
    )
    if is_description_of_drawings:
        return base_endings or t.endswith(";") or t.endswith("; and")
    return base_endings


def are_paragraphs_sequential(paragraph_numbers: list[int]) -> bool:
    for i in range(1, len(paragraph_numbers)):
        if paragraph_numbers[i] - paragraph_numbers[i - 1] != 1:
            return False
    return True


def get_last_sequential_index(paragraph_numbers: list[int]) -> int:
    for i in range(1, len(paragraph_numbers)):
        if paragraph_numbers[i] - paragraph_numbers[i - 1] != 1:
            return i
    return len(paragraph_numbers)


def detect_restrictive_wording(paragraph_text: str, paragraph_number: int) -> SpecWordingResult:
    """Detect restrictive wording in a specification paragraph."""
    flagged: list[int] = []
    parts: list[str] = []

    for match in _RESTRICTIVE_WORDING.finditer(paragraph_text):
        parts.append(f'[{paragraph_number}] → "{match.group()}"\n              ')
        if paragraph_number not in flagged:
            flagged.append(paragraph_number)

    return SpecWordingResult(flagged_paragraphs=flagged, formatted_phrases="".join(parts))


def has_sequence_listing_mismatch(full_text: str) -> bool:
    """Check if spec mentions SEQ ID NO but lacks a sequence listing statement."""
    mentions_seq = bool(re.search(r"(?i)SEQ\.?\s*(ID|NO)\.?\s*(NO\.)?", full_text))
    has_section = bool(re.search(r"(?i)STATEMENT REGARDING SEQUENCE LISTING", full_text))
    return mentions_seq and not has_section
