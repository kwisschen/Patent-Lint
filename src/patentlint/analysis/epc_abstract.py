# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""EPC abstract-level checks (G7 in the canonical 7-group order).

  - check_abstract_word_count_epc   — Rule 47(2) EPC + Guidelines F-II § 2.3
                                      (EPO practice: 50 to 150 words)
  - check_abstract_structure_epc    — Rule 47(2) EPC: single paragraph, no
                                      commercial language, no implied phrases,
                                      no merit / self-referential claims

Re-uses the US abstract detectors (English regex) where the rules align;
re-keys CheckItems into the EPC namespace + cites EPC statutes.
"""

from __future__ import annotations

import re

from patentlint.analysis.abstract import (
    count_words,
    detect_implied_phrases,
    detect_legal_phraseology_items,
    detect_merit_language_items,
)
from patentlint.analysis.utils import _dx
from patentlint.models import CheckItem


# Minimal English stop-word list for title-match noun-overlap detection.
# Kept short on purpose: only function words and very common adjectives
# that carry no topical signal. Anything load-bearing for the invention
# (e.g., "method", "system", "apparatus") should still count toward
# overlap so the check fires on substantive divergence between title
# and abstract.
_EN_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "for", "of", "in", "on",
    "to", "with", "from", "by", "at", "as", "is", "are", "was", "were",
    "be", "been", "being", "this", "that", "these", "those", "it", "its",
    "such", "more", "any", "some", "all", "each", "having", "having",
    "comprising", "comprises", "comprise", "including", "includes",
    "include", "thereof", "wherein", "said",
})

# Match "claim N", "claims N", "claim N to M", "claims N-M", etc.
_ABSTRACT_CLAIM_REF_RE = re.compile(
    r"\bclaims?\s+\d+(?:\s*(?:to|and|or|[\-,–])\s*\d+)*",
    re.IGNORECASE,
)


def _title_content_words(title: str) -> list[str]:
    """Extract content-bearing words from a title for overlap matching."""
    if not title:
        return []
    # Drop punctuation, lowercase, then filter stopwords + short tokens.
    tokens = re.findall(r"[A-Za-z]{4,}", title.lower())
    return [t for t in tokens if t not in _EN_STOPWORDS]


# EPO Guidelines F-II § 2.3 + Rule 47(2) practice: abstracts are typically
# 50 to 150 words. Below 50 is rarely flagged as a hard error but the
# EPO will request expansion; above 150 commonly draws a written-objection.
_EPC_ABSTRACT_MIN = 50
_EPC_ABSTRACT_MAX = 150


def check_abstract_word_count_epc(abstract_text: str) -> list[CheckItem]:
    """Verify abstract word count per Rule 47(2) EPC + Guidelines F-II § 2.3.

    EPO practice: 50-150 words. Above 150 is the more commonly cited
    objection (Guidelines F-II § 2.3 specifies "as a guide, 50 to 150
    words"). Below 50 is flagged as a verify-status advisory because EPO
    examiners sometimes accept shorter abstracts for short claim sets.
    """
    word_count = count_words(abstract_text)

    if word_count == 0:
        return [CheckItem(
            status="amend",
            message="Abstract is missing or empty.",
            message_key="check.epc.abstract.wordCount.amend",
            reference="Rule 47(2) EPC",
            diagnostics=_dx(word_count=0),
        )]

    if word_count > _EPC_ABSTRACT_MAX:
        return [CheckItem(
            status="amend",
            message=(
                f"Abstract is {word_count} words, exceeding the EPO Guidelines "
                f"F-II § 2.3 guide of {_EPC_ABSTRACT_MAX} words maximum."
            ),
            message_key="check.epc.abstract.wordCount.amend",
            reference="Rule 47(2) EPC; EPO Guidelines F-II § 2.3",
            diagnostics=_dx(
                word_count=word_count,
                limit=_EPC_ABSTRACT_MAX,
                overage=word_count - _EPC_ABSTRACT_MAX,
            ),
        )]

    if word_count < _EPC_ABSTRACT_MIN:
        return [CheckItem(
            status="verify",
            message=(
                f"Abstract is {word_count} words, below the EPO Guidelines "
                f"F-II § 2.3 guide of {_EPC_ABSTRACT_MIN} words minimum."
            ),
            message_key="check.epc.abstract.wordCount.verify",
            reference="Rule 47(2) EPC; EPO Guidelines F-II § 2.3",
            diagnostics=_dx(
                word_count=word_count,
                floor=_EPC_ABSTRACT_MIN,
                shortfall=_EPC_ABSTRACT_MIN - word_count,
            ),
        )]

    return [CheckItem(
        status="pass",
        message=f"Abstract is {word_count} words (within EPO Guidelines F-II § 2.3 range).",
        message_key="check.epc.abstract.wordCount.pass",
        reference="Rule 47(2) EPC; EPO Guidelines F-II § 2.3",
        diagnostics=_dx(word_count=word_count),
    )]


def check_abstract_structure_epc(abstract_text: str) -> list[CheckItem]:
    """Verify abstract structure per Rule 47(2) EPC + Guidelines F-II § 2.3.

    Flags:
      - Multi-paragraph abstracts (Rule 47(2) practice: single paragraph)
      - Implied / boilerplate openers ("is provided", "are provided",
        "disclosure")
      - Claim-style legal phraseology ("means", "said", "comprising",
        "wherein", "thereof", "the same") — Guidelines F-II § 2.3 echoes
        the US prohibition against claim-style phrasing in abstracts
      - Merit / self-referential language ("novel", "innovative",
        "advantageous", "present invention", etc.)
    """
    if not abstract_text or not abstract_text.strip():
        return [CheckItem(
            status="pass",
            message="No abstract text to check.",
            message_key="check.epc.abstract.structure.pass",
            reference="Rule 47(2) EPC",
        )]

    # Strip the "ABSTRACT" heading from the start of the section if present
    body = abstract_text
    if body.upper().startswith("ABSTRACT"):
        body = body.split("\n", 1)[1] if "\n" in body else ""
    body = body.strip()

    issues: list[str] = []

    # Single-paragraph check — count non-empty paragraphs in the body
    paragraphs = [p for p in body.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        issues.append(f"abstract has {len(paragraphs)} paragraphs (Rule 47(2) practice: single paragraph)")

    implied = detect_implied_phrases(body)
    if implied:
        issues.append(f"implied / boilerplate opener(s): {', '.join(implied)}")

    legal = detect_legal_phraseology_items(body)
    if legal:
        issues.append(f"claim-style legal phrase(s): {', '.join(legal)}")

    merit = detect_merit_language_items(body)
    if merit:
        issues.append(f"merit / self-referential language: {', '.join(merit)}")

    if issues:
        return [CheckItem(
            status="amend",
            message=(
                "Abstract structure violates Rule 47(2) EPC / Guidelines F-II § 2.3: "
                + "; ".join(issues) + "."
            ),
            message_key="check.epc.abstract.structure.amend",
            details="; ".join(issues),
            reference="Rule 47(2) EPC; EPO Guidelines F-II § 2.3",
            diagnostics=_dx(
                issue_count=len(issues),
                paragraph_count=len(paragraphs),
                implied_count=len(implied),
                legal_count=len(legal),
                merit_count=len(merit),
            ),
        )]

    return [CheckItem(
        status="pass",
        message="Abstract structure conforms to Rule 47(2) EPC.",
        message_key="check.epc.abstract.structure.pass",
        reference="Rule 47(2) EPC; EPO Guidelines F-II § 2.3",
    )]


def check_abstract_title_match_epc(abstract_text: str, title: str) -> list[CheckItem]:
    """Verify the abstract refers to the same invention as the title.

    EPO Guidelines F-II § 2.3.5: the abstract should give a clear summary
    of the invention named in the title. A complete topical mismatch is
    a strong signal of a wrong-file paste or a stale title. Detection is
    cheap: extract content words (length ≥ 4, not in stopwords) from the
    title and check whether any appear in the abstract body. A single
    overlap is enough to pass — EPC drafters legitimately re-phrase the
    title in the abstract.

    Status:
      - ``verify`` when both title and abstract are non-empty but no
        title content word appears in the abstract.
      - ``pass`` when overlap exists, or when title / abstract is empty
        (the empty cases are handled by titleRequired / wordCount and
        emitting amend here would double-flag).
    """
    abstract_clean = (abstract_text or "").strip()
    title_clean = (title or "").strip()
    if not abstract_clean or not title_clean:
        return [CheckItem(
            status="pass",
            message="Abstract title-match not applicable (title or abstract empty).",
            message_key="check.epc.abstract.titleMatch.pass",
            reference="EPO Guidelines F-II § 2.3.5",
        )]

    title_words = _title_content_words(title_clean)
    if not title_words:
        return [CheckItem(
            status="pass",
            message="Title has no content words to match against.",
            message_key="check.epc.abstract.titleMatch.pass",
            reference="EPO Guidelines F-II § 2.3.5",
        )]

    abstract_lower = abstract_clean.lower()
    matched = [w for w in title_words if w in abstract_lower]
    if matched:
        return [CheckItem(
            status="pass",
            message="Abstract references the title's invention.",
            message_key="check.epc.abstract.titleMatch.pass",
            reference="EPO Guidelines F-II § 2.3.5",
            diagnostics=_dx(
                title_word_count=len(title_words),
                matched_count=len(matched),
                matched_sample=matched[:5],
            ),
        )]

    return [CheckItem(
        status="verify",
        message=(
            "Abstract may not refer to the invention named in the title "
            "(no content-word overlap detected). EPO Guidelines F-II § 2.3.5 "
            "ask the abstract to summarize the invention named in the title."
        ),
        message_key="check.epc.abstract.titleMatch.verify",
        reference="EPO Guidelines F-II § 2.3.5",
        diagnostics=_dx(
            title_word_count=len(title_words),
            matched_count=0,
            title_words_sample=title_words[:5],
        ),
    )]


def check_abstract_claim_reference_epc(abstract_text: str) -> list[CheckItem]:
    """Flag claim-number references in the abstract per Guidelines F-II § 2.3.3.

    EPO Guidelines F-II § 2.3.3: the abstract must be self-contained and
    must not cross-reference specific claims by number. Regex matches
    "claim N", "claims N", "claim N to M", "claims N-M", etc.
    """
    body = (abstract_text or "").strip()
    if not body:
        return [CheckItem(
            status="pass",
            message="No abstract text to check.",
            message_key="check.epc.abstract.claimReference.pass",
            reference="EPO Guidelines F-II § 2.3.3",
        )]

    matches = list(_ABSTRACT_CLAIM_REF_RE.finditer(body))
    if not matches:
        return [CheckItem(
            status="pass",
            message="Abstract does not reference specific claims.",
            message_key="check.epc.abstract.claimReference.pass",
            reference="EPO Guidelines F-II § 2.3.3",
        )]

    snippets = [m.group() for m in matches[:5]]
    return [CheckItem(
        status="amend",
        message=(
            "Abstract references specific claim(s) (" + ", ".join(snippets) + ") — "
            "EPO Guidelines F-II § 2.3.3 require the abstract to be "
            "self-contained and not cross-reference claims by number."
        ),
        message_key="check.epc.abstract.claimReference.amend",
        details=", ".join(snippets),
        reference="EPO Guidelines F-II § 2.3.3",
        diagnostics=_dx(
            flagged_count=len(matches),
            matches_sample=snippets,
        ),
    )]


def run_g7_abstract_checks(
    abstract_text: str,
    title: str = "",
) -> list[CheckItem]:
    """Run all G7 abstract checks in canonical 7-group order.

      1. abstractWordCount       (idx 10)
      2. abstractTitleMatch      (idx 20)
      3. abstractClaimReference  (idx 30)
      4. abstractStructure       (idx 60)
    """
    results: list[CheckItem] = []
    results.extend(check_abstract_word_count_epc(abstract_text))
    results.extend(check_abstract_title_match_epc(abstract_text, title))
    results.extend(check_abstract_claim_reference_epc(abstract_text))
    results.extend(check_abstract_structure_epc(abstract_text))
    return results
