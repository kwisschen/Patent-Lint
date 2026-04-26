# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Scoring rubric — converts FIX/REVIEW/PASS findings into a deterministic grade.

Reads the existing 109-check catalog (no new rules added). Buckets each
emitted CheckItem into one of 5 weighted sections, applies per-section
deductions, then a FIX-count gate, and produces a letter grade.

The rubric is deterministic: same draft always gets the same grade.
There is no AI judgment — every input is the FIX/REVIEW/PASS status
already set by an existing checker, and every output is a pure
arithmetic aggregation. This is the trust property that lets the
"No AI" badge stand alongside a numeric/letter score.

Weights: Spec 20% / Drawings 10% / Claims 45% / Antecedent+SpecSupport 15% /
Abstract 10%. When drawings are absent, Drawings is N/A and its weight
redistributes proportionally across the other 4 sections.

Gate: any FIX caps the grade at B-; multiple FIX cap progressively lower.
Statutory issues always headline regardless of how polished other
sections are — matches partner-triage reality ("any blockers? then how
clean?").

Completeness gap: when a universally-required section (title, claims,
spec body, abstract) is structurally empty, no grade is emitted; the
hero shows "Draft incomplete — grade unavailable" instead. An A grade
on an empty draft would be misleading and legally exposing.
"""

from __future__ import annotations

from patentlint.check_order import CANONICAL_CHECK_ORDER, CheckBucket
from patentlint.models import (
    CheckItem,
    CompletenessGap,
    ImpactItem,
    Jurisdiction,
    RubricGrade,
    RubricSection,
    SectionGrade,
)


# === Constants ===========================================================

RUBRIC_VERSION = "1.0"

# Per-finding deductions on the 0-100 section scale (tunable).
FIX_DEDUCTION = 15
REVIEW_DEDUCTION = 3

# Threshold for "structurally empty" body — section header parsed but
# fewer than this many meaningful tokens (post-tokenization, post
# header-echo strip). Tunable.
EMPTY_TOKEN_THRESHOLD = 50


# Advisory REVIEW keys — informational, not problem-indicating.
#
# These checks fire when the draft contains content that warrants
# verification but isn't necessarily a defect: cross-references to
# related applications, prior-art citations in background, indigenous-
# terminology disclosure flags. A senior-attorney drafter who legitimately
# cites cross-references and prior art shouldn't see the grade drop —
# the REVIEW status is a "please verify" prompt, not a problem flag.
#
# These items still display as REVIEW in the TriagePanel (so the user
# can verify), but they are excluded from the rubric's REVIEW deduction
# count and from the impact list. Effectively: visible-but-zero-points.
#
# Adding to this set is the conservative move when introducing a new
# advisory-style check; the test gate ensures the rubric semantics stay
# explicit.
ADVISORY_REVIEW_KEYS: frozenset[str] = frozenset({
    # US
    "check.spec.crossReference.verify",
    "check.spec.priorArt.verify",
    "check.drawings.priorArt.verify",
    # CN
    "check.cn.drawings.priorArt.verify",
    # TW
    "check.tw.spec.indigenousTerms.verify",
})


# Section weights — must sum to 100 (5 buckets, jurisdiction-uniform).
SECTION_WEIGHTS: dict[RubricSection, int] = {
    RubricSection.SPECIFICATION: 20,
    RubricSection.DRAWINGS: 10,
    RubricSection.CLAIMS: 45,
    RubricSection.ANTECEDENT_SPEC_SUPPORT: 15,
    RubricSection.ABSTRACT: 10,
}

assert sum(SECTION_WEIGHTS.values()) == 100, "section weights must sum to 100"


# === Section applicability matrix ========================================

# Per-jurisdiction: which sections are required vs. conditional.
# Each section maps to a dict with EITHER {"required": True} OR
# {"conditional": <predicate-name>}. Predicate names are resolved
# against the runtime context (currently only "has_drawings").
#
# JP/KR onboard via additional entries here when those jurisdictions
# come online — no code change needed.
SECTION_APPLICABILITY: dict[Jurisdiction, dict[RubricSection, dict]] = {
    Jurisdiction.US: {
        RubricSection.SPECIFICATION: {"required": True},
        # 37 CFR 1.74: required iff drawings exist
        RubricSection.DRAWINGS: {"conditional": "has_drawings"},
        RubricSection.CLAIMS: {"required": True},
        RubricSection.ANTECEDENT_SPEC_SUPPORT: {"required": True},
        RubricSection.ABSTRACT: {"required": True},
    },
    Jurisdiction.CN: {
        RubricSection.SPECIFICATION: {"required": True},
        # 实施细则 §20 第1款 第4项 (post-2024-01-20 revision): required
        # iff drawings exist
        RubricSection.DRAWINGS: {"conditional": "has_drawings"},
        RubricSection.CLAIMS: {"required": True},
        RubricSection.ANTECEDENT_SPEC_SUPPORT: {"required": True},
        RubricSection.ABSTRACT: {"required": True},
    },
    Jurisdiction.TW: {
        RubricSection.SPECIFICATION: {"required": True},
        # 施行細則 §17 第1款 第5項: required iff drawings exist
        RubricSection.DRAWINGS: {"conditional": "has_drawings"},
        RubricSection.CLAIMS: {"required": True},
        RubricSection.ANTECEDENT_SPEC_SUPPORT: {"required": True},
        RubricSection.ABSTRACT: {"required": True},
    },
}


# === Check → section mapping =============================================

# Walker-based §112 checks roll into a dedicated bucket so the
# Antecedent + Spec Support rubric section captures both surfaces of
# the same statute family rather than splitting them into Claims.
_ANTECEDENT_SPEC_SUPPORT_KEY_PREFIXES = (
    "check.claims.antecedentBasis.",
    "check.cn.claims.antecedentBasis.",
    "check.tw.claims.antecedentBasis.",
    "checks.spec_support_",
    "check.cn.claims.specSupport.",
    "check.tw.claims.specSupport.",
)

# Several checks emit in the SPEC bucket but are conceptually drawings
# (figure-ref consistency, TW symbol-table presence/consistency, the
# TW symbol-vs-representative-drawing cross-reference). Route them
# into the Drawings rubric section so their findings get the drawings
# weight and conditional-N/A behavior.
_DRAWINGS_KEY_PREFIXES_FROM_OTHER_BUCKETS = (
    "check.cn.spec.figureRefConsistency.",
    "check.tw.spec.figureRefConsistency.",
    "check.tw.spec.symbolTablePresence.",
    "check.tw.spec.symbolTableConsistency.",
    "check.tw.crossRef.symbolVsRepDrawing.",
    "check.tw.claims.symbolTableConsistency.",
)


def section_for_message_key(message_key: str) -> RubricSection:
    """Map a CheckItem message_key to its rubric section.

    Walker-based §112 checks (antecedent / spec support) and figure /
    symbol-table checks have explicit prefix routing; everything else
    derives from the canonical CheckBucket.
    """
    if not message_key:
        # Unkeyed CheckItem (defensive). Treat as SPEC — the conservative
        # bucket since SPEC is the default landing for ungrouped findings.
        return RubricSection.SPECIFICATION

    if any(message_key.startswith(p) for p in _ANTECEDENT_SPEC_SUPPORT_KEY_PREFIXES):
        return RubricSection.ANTECEDENT_SPEC_SUPPORT
    if any(message_key.startswith(p) for p in _DRAWINGS_KEY_PREFIXES_FROM_OTHER_BUCKETS):
        return RubricSection.DRAWINGS

    entry = CANONICAL_CHECK_ORDER.get(message_key)
    if entry is None:
        # Unregistered key — should never happen in practice (the
        # check_emission_order test gates this), but be tolerant.
        return RubricSection.SPECIFICATION
    bucket, _, _ = entry
    if bucket == CheckBucket.SPEC:
        return RubricSection.SPECIFICATION
    if bucket == CheckBucket.DRAWINGS:
        return RubricSection.DRAWINGS
    if bucket == CheckBucket.ABSTRACT:
        return RubricSection.ABSTRACT
    return RubricSection.CLAIMS


# === Pure-function helpers ===============================================


def compute_section_score(fix_count: int, review_count: int) -> int:
    """Compute a section's 0-100 score from per-finding deductions."""
    return max(0, 100 - FIX_DEDUCTION * fix_count - REVIEW_DEDUCTION * review_count)


def letter_for_score(score: int) -> str:
    """Map a 0-100 score to a letter grade."""
    if score >= 97:
        return "A"
    if score >= 93:
        return "A-"
    if score >= 88:
        return "B+"
    if score >= 83:
        return "B"
    if score >= 78:
        return "B-"
    if score >= 73:
        return "C+"
    if score >= 68:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def gate_cap_for_fix_count(fix_count: int) -> tuple[int, str | None]:
    """Apply the FIX-count gate. Returns (max_score, reason or None).

    The gate enforces "any statutory blocker headlines the grade":
    a single FIX caps at B- regardless of how clean other sections are.
    """
    if fix_count == 0:
        return 100, None
    if fix_count == 1:
        return 82, "1 FIX caps grade at B-"
    if fix_count == 2:
        return 77, "2 FIX cap grade at C+"
    if fix_count == 3:
        return 72, "3 FIX cap grade at C"
    if fix_count == 4:
        return 67, "4 FIX cap grade at D"
    return 59, f"{fix_count} FIX cap grade at F"


# === Detection helpers ===================================================


def detect_has_drawings(*, figures_count: int = 0, figure_refs: list | None = None) -> bool:
    """Detect whether the document has drawings.

    True when either:
    - a non-zero figure count was parsed from the drawings section, OR
    - figure references (FIG. N / 圖N / 图N) were extracted from spec body.
    """
    if figures_count > 0:
        return True
    if figure_refs:
        return True
    return False


def detect_completeness_gap(
    *,
    title: str,
    has_claims: bool,
    has_spec_body: bool,
    has_abstract: bool,
) -> CompletenessGap | None:
    """Detect when a universally-required section is missing.

    Returns a CompletenessGap when title / claims / spec body / abstract
    is structurally empty. Returns None when the draft is complete enough
    to grade.
    """
    missing: list[str] = []
    if not title or not title.strip():
        missing.append("title")
    if not has_claims:
        missing.append("claims")
    if not has_spec_body:
        missing.append("specification")
    if not has_abstract:
        missing.append("abstract")
    if missing:
        return CompletenessGap(missing_sections=missing)
    return None


# === Top-level grading ===================================================


def compute_rubric_grade(
    *,
    jurisdiction: Jurisdiction,
    all_checks: list[CheckItem],
    has_drawings: bool,
    completeness_gap: CompletenessGap | None = None,
) -> RubricGrade:
    """Compute the rubric grade for an analysis run.

    Args:
        jurisdiction: which applicability matrix to use.
        all_checks: every CheckItem emitted across all sections.
        has_drawings: whether the document has drawings (drives Drawings
            section conditional applicability).
        completeness_gap: when set, the grade is unavailable and this is
            returned as-is.

    Returns:
        RubricGrade with score, letter, section breakdown, impact list,
        and optionally a completeness gap.
    """
    if completeness_gap is not None and completeness_gap.missing_sections:
        return RubricGrade(
            rubric_version=RUBRIC_VERSION,
            score=0,
            letter="—",
            completeness_gap=completeness_gap,
        )

    applicability = SECTION_APPLICABILITY.get(jurisdiction, SECTION_APPLICABILITY[Jurisdiction.US])

    # Bucket findings by (section, status).
    bucket_fix: dict[RubricSection, int] = {s: 0 for s in RubricSection}
    bucket_review: dict[RubricSection, int] = {s: 0 for s in RubricSection}
    bucket_pass: dict[RubricSection, int] = {s: 0 for s in RubricSection}

    for check in all_checks:
        section = section_for_message_key(check.message_key or "")
        if check.status == "amend":
            bucket_fix[section] += 1
        elif check.status == "verify":
            # Advisory REVIEWs are informational only — counted as PASS for
            # grading purposes so they don't deduct. They still display as
            # REVIEW in the UI / PDF / triage list (the bucketing here is
            # purely for the score formula).
            if check.message_key in ADVISORY_REVIEW_KEYS:
                bucket_pass[section] += 1
            else:
                bucket_review[section] += 1
        elif check.status == "pass":
            bucket_pass[section] += 1

    # Determine applicability per section.
    applicable: dict[RubricSection, bool] = {}
    for section in RubricSection:
        config = applicability.get(section, {})
        if config.get("required"):
            applicable[section] = True
        elif config.get("conditional") == "has_drawings":
            applicable[section] = has_drawings
        else:
            # Defensive: unknown predicate → applicable.
            applicable[section] = True

    # Renormalize weights across applicable sections so they sum to 100.
    total_applicable_weight = sum(SECTION_WEIGHTS[s] for s in RubricSection if applicable[s])
    if total_applicable_weight == 0:
        total_applicable_weight = 1  # defensive; can't happen with current matrix

    section_grades: list[SectionGrade] = []
    overall_weighted: float = 0.0
    total_fix = 0

    for section in RubricSection:
        weight = SECTION_WEIGHTS[section]
        is_applicable = applicable[section]
        fix_n = bucket_fix[section]
        rev_n = bucket_review[section]
        pass_n = bucket_pass[section]

        if is_applicable:
            sec_score = compute_section_score(fix_n, rev_n)
            effective_weight = weight * 100 / total_applicable_weight
            overall_weighted += sec_score * (weight / total_applicable_weight)
            total_fix += fix_n
        else:
            sec_score = 0
            effective_weight = 0.0

        section_grades.append(
            SectionGrade(
                section=section,
                weight=weight,
                effective_weight=round(effective_weight, 1),
                score=sec_score,
                fix_count=fix_n,
                review_count=rev_n,
                pass_count=pass_n,
                applicable=is_applicable,
            )
        )

    overall_score = round(overall_weighted)

    # Apply FIX-count gate.
    cap_max, cap_reason = gate_cap_for_fix_count(total_fix)
    final_score = min(overall_score, cap_max)
    final_letter = letter_for_score(final_score)

    # Surface the gate reason only when the cap actually pulled the score down.
    surfaced_reason = cap_reason if (cap_reason and overall_score > cap_max) else None

    impact_list = _compute_impact_list(
        applicable=applicable,
        total_applicable_weight=total_applicable_weight,
        all_checks=all_checks,
    )

    return RubricGrade(
        rubric_version=RUBRIC_VERSION,
        score=final_score,
        letter=final_letter,
        cap_reason=surfaced_reason,
        section_grades=section_grades,
        impact_list=impact_list,
    )


def _compute_impact_list(
    *,
    applicable: dict[RubricSection, bool],
    total_applicable_weight: int,
    all_checks: list[CheckItem],
) -> list[ImpactItem]:
    """Top-3 unaddressed findings ranked by overall-score-delta-if-resolved.

    A finding's delta is its per-finding deduction times its section's
    renormalized weight. Larger delta = bigger lever on the grade.
    """
    items: list[ImpactItem] = []
    for check in all_checks:
        if check.status not in ("amend", "verify"):
            continue
        # Advisory REVIEWs are informational — no deduction means no impact
        # delta means no entry on the lever-list.
        if check.status == "verify" and check.message_key in ADVISORY_REVIEW_KEYS:
            continue
        section = section_for_message_key(check.message_key or "")
        if not applicable.get(section, False):
            continue
        deduction = FIX_DEDUCTION if check.status == "amend" else REVIEW_DEDUCTION
        renorm = SECTION_WEIGHTS[section] / total_applicable_weight if total_applicable_weight else 0.0
        delta = round(deduction * renorm)
        items.append(
            ImpactItem(
                message_key=check.message_key or "",
                section=section,
                status=check.status,
                delta=delta,
            )
        )
    items.sort(key=lambda i: (-i.delta, i.message_key))
    return items[:3]


# === AnalysisResult integration ==========================================


def flatten_checks_from_lists(*lists_of_checks: list[CheckItem]) -> list[CheckItem]:
    """Flatten multiple CheckItem lists into a single list.

    Convenience for pipelines: pass each per-section checks list and
    receive a single flat list ready for compute_rubric_grade.
    """
    out: list[CheckItem] = []
    for lst in lists_of_checks:
        out.extend(lst)
    return out
