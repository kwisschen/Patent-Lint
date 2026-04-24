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


# MPEP § 608.01(b): "the form and legal phraseology often used in patent
# claims, such as 'means' and 'said,' should be avoided." MPEP names only
# two explicit examples but the rule is clearly the class, not the list —
# practitioner guidance (BlueIron IP, IPWatchdog, Patent Trademark Blog)
# agrees that claim-transitional phrases ("comprising" and mutations),
# claim modifiers ("wherein"), and claim-style archaic pronouns ("thereof,"
# "the same") all fall under the same § 608.01(b) prohibition.
_LEGAL_PHRASEOLOGY_ABSTRACT_RE = re.compile(
    r"(?i)\b("
    r"means|said"
    r"|compris(?:e|es|ed|ing)"
    r"|wherein"
    r"|thereof|the same"
    r")\b"
)

# MPEP § 608.01(b): "should not refer to purported merits or speculative
# applications of the invention." Merit adjectives + self-referential
# "present invention" phrasing fall under this clause.
_MERIT_LANGUAGE_ABSTRACT_RE = re.compile(
    r"(?i)\b(novel|innovative|unique|important|significant|merit|advantag(?:e|es)|present invention)\b"
)


def detect_legal_phraseology(abstract_text: str) -> str:
    """Detect claim-style legal phraseology in the abstract per MPEP § 608.01(b).

    Flags the two terms MPEP § 608.01(b) explicitly names as legal phraseology
    often used in patent claims: "means" and "said"."""
    parts: list[str] = []
    for match in _LEGAL_PHRASEOLOGY_ABSTRACT_RE.finditer(abstract_text):
        parts.append(f'→ "{match.group()}"\n        ')
    return "".join(parts)


def detect_legal_phraseology_items(abstract_text: str) -> list[str]:
    return [m.group() for m in _LEGAL_PHRASEOLOGY_ABSTRACT_RE.finditer(abstract_text)]


def detect_merit_language(abstract_text: str) -> str:
    """Detect purported-merit / self-referential language per MPEP § 608.01(b).

    MPEP § 608.01(b): the abstract "should not refer to purported merits or
    speculative applications of the invention and should not compare the
    invention with the prior art." Flags merit adjectives (novel, innovative,
    unique, important, significant, merit, advantage[s]) and the
    self-referential pattern "present invention"."""
    parts: list[str] = []
    for match in _MERIT_LANGUAGE_ABSTRACT_RE.finditer(abstract_text):
        parts.append(f'→ "{match.group()}"\n        ')
    return "".join(parts)


def detect_merit_language_items(abstract_text: str) -> list[str]:
    return [m.group() for m in _MERIT_LANGUAGE_ABSTRACT_RE.finditer(abstract_text)]
