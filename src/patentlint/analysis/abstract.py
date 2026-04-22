# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
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


_IMPLIED_PHRASES = ("is provided", "are provided", "disclosure")


def has_implied_phrase(abstract_text: str) -> bool:
    """Check if first sentence contains 'is provided', 'are provided', or 'disclosure'."""
    sentences = re.split(r"(?<=[.!?])\s+", abstract_text)
    if not sentences:
        return False
    first = sentences[0].lower()
    return any(phrase in first for phrase in _IMPLIED_PHRASES)


def detect_implied_phrases(abstract_text: str) -> list[str]:
    """Return the ordered list of implied phrases present in the first sentence.

    Unlike has_implied_phrase (which returns bool), this surfaces the actual
    matched tokens so downstream callers can render them in the user-facing
    finding. Matched phrases preserve their source-text casing."""
    sentences = re.split(r"(?<=[.!?])\s+", abstract_text)
    if not sentences:
        return []
    first = sentences[0]
    first_lower = first.lower()
    return [phrase for phrase in _IMPLIED_PHRASES if phrase in first_lower]


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
