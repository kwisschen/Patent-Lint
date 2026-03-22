"""Abstract section analysis.

Checks word count, structure, implied phrases, and improper wording per MPEP § 608.01(b).
"""

import re


def count_words(abstract_text: str | None) -> int:
    if not abstract_text:
        return 0
    stripped = abstract_text.strip()
    return len(stripped.split()) if stripped else 0


def is_single_paragraph_and_final(document_text: str, abstract_text: str) -> bool:
    """Check if abstract is single paragraph, ends with proper punctuation, and is at document end."""
    body = re.sub(r"^ABSTRACT[\s\S]*?\n", "", abstract_text, count=1).strip()

    single_paragraph = "\n" not in body
    at_end = document_text.strip().endswith(body)
    proper_ending = body.endswith(".") or body.endswith("!") or body.endswith("?")

    return single_paragraph and at_end and proper_ending


def has_implied_phrase(abstract_text: str) -> bool:
    """Check if first sentence contains 'is provided', 'are provided', or 'disclosure'."""
    sentences = re.split(r"(?<=[.!?])\s+", abstract_text)
    if not sentences:
        return False
    first = sentences[0].lower()
    return "is provided" in first or "are provided" in first or "disclosure" in first


def detect_improper_wording(abstract_text: str) -> str:
    """Detect improper/restrictive wording in the abstract per MPEP § 608.01(b).

    Flags:
    - Restrictive absolute terms (invention, always, never, must, etc.)
    - Legal phraseology (comprising, means, said, thereof, the same)
    - Merit/advantage language (merit, advantage)
    - Implied phrases (disclosure, is provided, are provided)
    """
    pattern = re.compile(
        r"(?i)\b(invention|always|never|must|solely|every|required|essential|critical|key|vital|"
        r"compris(?:e|es|ed|ing)|means|said|merit|advantag(?:e|es)|disclosure|is provided|are provided|"
        r"the same|thereof|novel|innovative|unique|important|significant|present invention)\b"
    )
    parts: list[str] = []
    for match in pattern.finditer(abstract_text):
        parts.append(f'→ "{match.group()}"\n        ')
    return "".join(parts)
