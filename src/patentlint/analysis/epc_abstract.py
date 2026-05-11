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

from patentlint.analysis.abstract import (
    count_words,
    detect_implied_phrases,
    detect_legal_phraseology_items,
    detect_merit_language_items,
)
from patentlint.analysis.utils import _dx
from patentlint.models import CheckItem


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


def run_g7_abstract_checks(abstract_text: str) -> list[CheckItem]:
    """Run all G7 abstract checks in canonical 7-group order.

      1. abstractWordCount
      2. abstractStructure
    """
    results: list[CheckItem] = []
    results.extend(check_abstract_word_count_epc(abstract_text))
    results.extend(check_abstract_structure_epc(abstract_text))
    return results
