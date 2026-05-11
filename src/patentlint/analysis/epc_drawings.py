# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""EPC drawings-level checks (G3 in the canonical 7-group order).

  - check_figures_sequential_epc  — Rule 46(2)(a) EPC: figures numbered 1..N
                                    without gaps
  - check_single_figure_label_epc — Guidelines F-V § 1.2: single-figure
                                    drafts conventionally use "Fig." or
                                    "The figure" (EPC) rather than "FIG."
                                    (US). REVIEW-status advisory.
  - check_prior_art_labeling_epc  — Rule 46(2)(h) EPC: figures depicting
                                    prior art must be labeled accordingly.
                                    Flag when "prior art" / "conventional"
                                    keywords appear with a figure number
                                    in the brief description.
  - check_figure_count_epc         — informational tile (not a failure check)

Re-uses the US drawings helpers — figure regex is English-vocabulary and
works identically across US and EPC drafts. Statute references are
re-mapped to EPC Rules / Guidelines.
"""

from __future__ import annotations

from patentlint.analysis.drawings import (
    _extract_figure_ids,
    are_figures_sequential,
    compute_missing_figure_numbers,
    contains_prior_art_references,
    is_single_figure,
    uses_wrong_label_for_single_figure,
)
from patentlint.analysis.utils import _dx
from patentlint.models import CheckItem


def check_figures_sequential_epc(full_text: str) -> list[CheckItem]:
    """Verify figures are numbered sequentially per Rule 46(2)(a) EPC.

    Rule 46(2)(a) requires the drawings to be numbered consecutively in
    Arabic numerals. Gaps in the numbering sequence are flagged.
    """
    if not full_text or not full_text.strip():
        return [CheckItem(
            status="pass",
            message="No drawings text to check.",
            message_key="check.epc.drawings.figuresSequential.pass",
            reference="Rule 46(2)(a) EPC",
        )]
    sequential = are_figures_sequential(full_text)
    if sequential:
        return [CheckItem(
            status="pass",
            message="Figures appear in sequential order.",
            message_key="check.epc.drawings.figuresSequential.pass",
            reference="Rule 46(2)(a) EPC",
        )]

    missing = compute_missing_figure_numbers(full_text)
    return [CheckItem(
        status="amend",
        message=(
            f"Figures are not sequential. Missing figure number(s): "
            f"{', '.join(str(n) for n in missing) if missing else 'see diagnostic'}."
        ),
        message_key="check.epc.drawings.figuresSequential.amend",
        details=", ".join(str(n) for n in missing) if missing else None,
        reference="Rule 46(2)(a) EPC",
        diagnostics=_dx(
            missing_count=len(missing),
            missing_numbers=missing,
            first_missing=missing[0] if missing else None,
        ),
    )]


def check_single_figure_label_epc(full_text: str) -> list[CheckItem]:
    """Advisory check on single-figure label convention per Guidelines F-V § 1.2.

    EPC drafts conventionally use "Fig." (mixed case) or "The figure" when
    only one figure exists. US drafters often write "FIG. 1" — the EPO
    does not reject this but Guidelines F-V § 1.2 prefers the EPC form.
    REVIEW status: flagged for verification only, not an FIX.
    """
    if not is_single_figure(full_text):
        return [CheckItem(
            status="pass",
            message="More than one figure detected — single-figure label check not applicable.",
            message_key="check.epc.drawings.singleFigureLabel.pass",
            reference="EPO Guidelines F-V § 1.2",
        )]

    if not uses_wrong_label_for_single_figure(full_text):
        # No figure-labelling form detected at all — flag in case the
        # drafter forgot to label the figure.
        return [CheckItem(
            status="verify",
            message="Single figure detected but no Fig./FIG./Figure label found near it.",
            message_key="check.epc.drawings.singleFigureLabel.verify",
            reference="EPO Guidelines F-V § 1.2",
        )]

    # Has a Fig.-style label — fine for EPC v1 (we don't currently
    # distinguish "FIG." from "Fig." for single-figure drafts).
    return [CheckItem(
        status="pass",
        message="Single figure labeled.",
        message_key="check.epc.drawings.singleFigureLabel.pass",
        reference="EPO Guidelines F-V § 1.2",
    )]


def check_prior_art_labeling_epc(full_text: str) -> list[CheckItem]:
    """Verify prior-art figures are labeled per Rule 46(2)(h) EPC.

    Rule 46(2)(h) requires the description to briefly describe the
    figures, and figures depicting prior art must be labeled as such.
    EPO commonly flags drafts whose description mentions "prior art"
    near a figure number without an explicit prior-art label on the
    figure itself.

    v1: when prior-art keywords (prior art / conventional / traditional /
    art) appear in the drawings section, emit a REVIEW advisory to
    verify the figure is labeled correctly. False positives are avoided
    via the existing keyword-pattern; full label-text inspection lands
    in a future revision once a real-corpus signal motivates it.
    """
    from patentlint.parser.sections_epc import (
        extract_drawings_description_section_epc,
    )

    drawings_text = extract_drawings_description_section_epc(full_text)
    if not drawings_text:
        return [CheckItem(
            status="pass",
            message="No drawings description to check.",
            message_key="check.epc.drawings.priorArtLabeling.pass",
            reference="Rule 46(2)(h) EPC",
        )]
    if contains_prior_art_references(drawings_text):
        return [CheckItem(
            status="verify",
            message=(
                "Drawings description references prior art — verify the figure(s) "
                "are labeled accordingly per Rule 46(2)(h) EPC."
            ),
            message_key="check.epc.drawings.priorArtLabeling.verify",
            reference="Rule 46(2)(h) EPC",
        )]
    return [CheckItem(
        status="pass",
        message="No prior-art references in drawings description.",
        message_key="check.epc.drawings.priorArtLabeling.pass",
        reference="Rule 46(2)(h) EPC",
    )]


def check_figure_count_epc(full_text: str) -> list[CheckItem]:
    """Informational tile: how many unique figures the document declares.

    Not a failure check (always status='pass'). Counts unique figure IDs
    (1, 2A, 3 etc.) so the same figure mentioned multiple times in spec
    body counts once. Surfaces the figure count so the report UI can
    show it as a stat card.
    """
    count = len(_extract_figure_ids(full_text))
    return [CheckItem(
        status="pass",
        message=f"Detected {count} figure(s).",
        message_key="check.epc.drawings.figureCount.pass",
        reference="Rule 46(2)(a) EPC",
        diagnostics=_dx(figure_count=count),
    )]


def run_g3_drawings_checks(full_text: str) -> list[CheckItem]:
    """Run all G3 drawings checks in canonical idx order:

      1. figureCount (idx 10, informational)
      2. singleFigureLabel (idx 20)
      3. priorArtLabeling (idx 30)
      4. figuresSequential (idx 40)
    """
    results: list[CheckItem] = []
    results.extend(check_figure_count_epc(full_text))
    results.extend(check_single_figure_label_epc(full_text))
    results.extend(check_prior_art_labeling_epc(full_text))
    results.extend(check_figures_sequential_epc(full_text))
    return results
