"""Specification section analysis.

Checks paragraph endings, numbering sequentiality, restrictive wording,
sequence listing references, and reference numeral consistency.
"""

import re
from collections import Counter

from patentlint.models import CheckItem, ReferenceNumeral, SpecWordingResult

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


# --- Reference numeral extraction (B2) ---

# Pattern A: noun phrase (1-4 words) followed by number: "base plate 102"
_REFNUM_AFTER_NOUN = re.compile(
    r"(?<![.\d])"
    r"(?:(?:the|a|an|said|each|first|second|third|fourth|fifth)\s+)?"
    r"((?:[a-z]{2,15}\s+){0,3}[a-z]{2,15})"
    r"\s+"
    r"(\d{2,4})"
    r"(?!\d)"        # not followed by another digit
    r"(?!\.\d)"      # not followed by decimal point + digit
    r"(?![%°])"      # not followed by % or degree
    r"\b",
    re.IGNORECASE,
)

# Pattern B: parenthetical numeral: "base plate (102)"
_REFNUM_PARENS = re.compile(
    r"((?:[a-z]{2,15}\s+){0,3}[a-z]{2,15})"
    r"\s*\((\d{2,4})\)",
    re.IGNORECASE,
)

# Exclusion: unit followers
_UNIT_PATTERN = re.compile(
    r"^\s*(?:mm|cm|m|km|µm|nm|in|ft|°[CF]|K|%|Hz|kHz|MHz|GHz|THz"
    r"|V|mV|kV|A|mA|W|kW|MW|Ω|psi|bar|atm|Pa|kPa|MPa"
    r"|g|kg|mg|lb|oz|mol|L|mL|dB|s|ms|µs|ns|rpm)\b",
)

# Exclusion: preceding keywords
_EXCLUDE_KEYWORDS = {
    "claim", "claims", "fig", "figs", "figure", "figures",
    "paragraph", "step", "table", "example", "embodiment",
    "equation", "patent", "no", "number", "page", "version",
    "vol", "chapter", "section", "part", "item",
    "approximately", "about",
}


def _is_year(num_str: str) -> bool:
    """Check if a number looks like a year."""
    return bool(re.match(r"^(19|20)\d\d$", num_str))



def extract_reference_numeral_inventory(
    spec_text: str,
) -> list[ReferenceNumeral]:
    """Extract a reference numeral inventory from specification text.

    Combines DD + Summary + Brief Description of Drawings into one pass.
    Returns sorted list of ReferenceNumeral with occurrence counts.
    """
    from patentlint.analysis.utils import clean_noun_phrase

    candidates: dict[int, str] = {}
    occurrence_count: Counter = Counter()

    for pattern in [_REFNUM_AFTER_NOUN, _REFNUM_PARENS]:
        for m in pattern.finditer(spec_text):
            noun = m.group(1).strip().lower()
            num_str = m.group(2)
            num = int(num_str)

            # Exclusion: year
            if _is_year(num_str):
                continue

            # Exclusion: keyword in noun phrase
            noun_words = noun.split()
            if any(w in _EXCLUDE_KEYWORDS for w in noun_words):
                continue

            # Exclusion: unit follower
            after = spec_text[m.end():][:5]
            if _UNIT_PATTERN.match(after):
                continue

            # Exclusion: bracket paragraph [0035]
            before = spec_text[max(0, m.start() - 2):m.start()]
            if "[" in before:
                continue

            # Exclusion: 5+ digits (patent number)
            if len(num_str) >= 5:
                continue

            occurrence_count[num] += 1
            if num not in candidates:
                cleaned = clean_noun_phrase(noun)
                candidates[num] = cleaned if cleaned else noun

    # Confidence filter: require at least 2 occurrences
    result: list[ReferenceNumeral] = []
    for num in sorted(candidates):
        if occurrence_count[num] >= 2:
            result.append(ReferenceNumeral(
                number=num,
                element_name=candidates[num],
                occurrences=occurrence_count[num],
            ))

    return result


def has_sequence_listing_mismatch(full_text: str) -> bool:
    """Check if spec mentions SEQ ID NO but lacks a sequence listing statement."""
    mentions_seq = bool(re.search(r"(?i)SEQ\.?\s*(ID|NO)\.?\s*(NO\.)?", full_text))
    has_section = bool(re.search(r"(?i)STATEMENT REGARDING SEQUENCE LISTING", full_text))
    return mentions_seq and not has_section
