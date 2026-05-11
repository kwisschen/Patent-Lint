# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Canonical check-emission order (ADR-149).

Single source of truth for the order in which CheckItems appear in any
jurisdiction's AnalysisResult / ReportData. Every message_key emitted
across the three pipelines (US / CN / TW) is registered here exactly
once with its (bucket, group, index-within-group).

The seven canonical groups (1..7) match the document-order invariant in
CLAUDE.md:

  1. Spec structure     — required sections, section ordering,
                          paragraph numbering, paragraph endings,
                          bracket format (TW 施行細則 §17).
  2. Spec content       — figure-ref consistency, patent-type wording,
                          title, claim-reference (forbidden), symbol
                          table (TW), plus US-specific filing content
                          (sequence listing, cross-reference, prior art,
                          spec restrictive wording, drawings overview),
                          and the TW symbol-vs-representative-drawing
                          cross-reference.
  3. Drawings           — figure count, single-figure label, prior-art
                          labeling, figures-sequential, figure x-ref.
  4. Claims structure   — sequential numbering, dependency format,
                          self-dep, circular, forward-dep, single
                          sentence, ref numeral parens, subject
                          consistency, transition phrase, dependent
                          ordering, multiple-dependent (US).
  5. Claims cross-jur.  — tw_terminology (CN), cn_terminology (TW),
                          claims_spec_reference / spec_drawing_ref,
                          multi-dep-on-multi-dep, multi-dep-alt,
                          title-subject-match, symbol-table
                          consistency (TW claims side), connection
                          relationships, claims restrictive wording.
  6. Claims § 112       — means-plus-function, antecedent basis,
                          spec support, preamble consistency, special
                          formats (Jepson / CRM / Markush / omnibus),
                          claim punctuation, claims overview summary.
  7. Abstract           — word / char count, title match, commercial
                          language, restrictive wording, implied
                          phrases, structure, representative drawing.

Per-bucket sort order is (group, index-within-group). The index lets
two different check families in the same group emit in a fixed relative
order; values need only be unique and stable, not dense.

See tests/test_check_emission_order.py for the drift gate: every
emitted CheckItem must have a registered message_key, and the actual
emission order must be monotonically non-decreasing in (group, index).
"""

from __future__ import annotations

from enum import IntEnum


class CheckBucket(IntEnum):
    """Which final list a CheckItem lands in on ReportData."""

    SPEC = 1
    CLAIMS = 2
    ABSTRACT = 3
    DRAWINGS = 4


class CheckGroup(IntEnum):
    """The 7 canonical groups within the unified document order."""

    SPEC_STRUCTURE = 1
    SPEC_CONTENT = 2
    DRAWINGS = 3
    CLAIMS_STRUCTURE = 4
    CLAIMS_CROSS_JURISDICTION = 5
    CLAIMS_SECTION_112 = 6
    ABSTRACT = 7


# Mapping: message_key → (bucket, group, idx_within_group).
# Every message_key emitted by any analysis function must appear here.
# idx_within_group establishes the canonical order among check families
# that share a group; ties (same idx) are acceptable for variants of a
# single family (e.g., pass vs. amend status).
CANONICAL_CHECK_ORDER: dict[str, tuple[CheckBucket, CheckGroup, int]] = {
    # =====================================================================
    # SPEC bucket
    # =====================================================================
    # --- Group 1: Spec structure ---
    "check.spec.trackedChanges.amend": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 10),
    "check.cn.spec.trackedChanges.amend": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 10),

    "checks.required_sections_missing": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 20),
    "checks.required_sections_pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 20),
    "checks.optional_section_missing": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 20),
    "check.cn.spec.requiredSections.amend": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 20),
    "check.cn.spec.requiredSections.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 20),
    "check.tw.spec.requiredSections.amend": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 20),
    "check.tw.spec.requiredSections.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 20),

    "check.cn.spec.sectionOrdering.amend": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 30),
    "check.cn.spec.sectionOrdering.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 30),
    "check.tw.spec.sectionOrdering.amend": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 30),
    "check.tw.spec.sectionOrdering.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 30),

    "check.spec.paragraphSequential.missing": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 40),
    "check.spec.paragraphSequential.amend": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 40),
    "check.spec.paragraphSequential.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 40),
    "check.cn.spec.paragraphNumbering.amendDocx": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 40),
    "check.cn.spec.paragraphNumbering.amendXmlDuplicate": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 40),
    "check.cn.spec.paragraphNumbering.amendXmlGap": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 40),
    "check.cn.spec.paragraphNumbering.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 40),
    "check.tw.spec.paragraphNumbering.amendFormat": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 40),
    "check.tw.spec.paragraphNumbering.amendGap": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 40),
    "check.tw.spec.paragraphNumbering.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 40),

    "check.spec.paragraphEnding.verify": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 50),
    "check.spec.paragraphEnding.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 50),
    "check.cn.spec.paragraphEnding.verify": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 50),
    "check.cn.spec.paragraphEnding.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 50),
    "check.tw.spec.paragraphEnding.verify": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 50),
    "check.tw.spec.paragraphEnding.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 50),

    "check.tw.crossRef.bracketFormat.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 60),
    "check.tw.crossRef.bracketFormat.amend": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 60),

    # --- Group 2: Spec content ---
    "check.cn.spec.figureRefConsistency.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 10),
    "check.cn.spec.figureRefConsistency.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 10),
    "check.tw.spec.figureRefConsistency.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 10),
    "check.tw.spec.figureRefConsistency.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 10),

    "check.cn.spec.patentTypeTerminology.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 20),
    "check.cn.spec.patentTypeTerminology.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 20),
    "check.tw.spec.patentTypeTerminology.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 20),
    "check.tw.spec.patentTypeTerminology.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 20),

    "check.spec.title.amendContent": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.spec.title.amendLength": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.spec.title.amendMissing": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.spec.title.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.spec.title.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.cn.spec.title.amendContent": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.cn.spec.title.amendLength": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.cn.spec.title.amendMissing": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.cn.spec.title.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.tw.spec.title.amendContent": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.tw.spec.title.amendMissing": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.tw.spec.title.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),

    "check.cn.spec.claimReference.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 40),
    "check.cn.spec.claimReference.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 40),
    "check.tw.spec.claimReference.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 40),
    "check.tw.spec.claimReference.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 40),

    # Numeral consistency D1 (per-jurisdiction). 实施细则 §21 / 施行細則 §19.
    # idx 45 sits between claimReference (40) and TW symbolTablePresence (50).
    "check.cn.spec.numeralConsistency.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 15),
    "check.cn.spec.numeralConsistency.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 15),
    "check.cn.spec.numeralConsistency.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 15),
    "check.tw.spec.numeralConsistency.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 15),
    "check.tw.spec.numeralConsistency.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 15),
    "check.tw.spec.numeralConsistency.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 15),
    # TW D3 — symbolTableCoverage sits between symbolTablePresence (50)
    # and the ordering of subsequent checks, idx 55.
    "check.tw.spec.symbolTableCoverage.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 55),
    "check.tw.spec.symbolTableCoverage.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 55),

    "check.tw.spec.symbolTablePresence.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 50),
    "check.tw.spec.symbolTablePresence.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 50),
    "check.tw.spec.symbolTableConsistency.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 60),
    "check.tw.spec.symbolTableConsistency.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 60),

    # TW-specific sensitive-terms advisory (原住民族傳統智慧創作保護條例) —
    # emits after the other spec-content checks so it doesn't intrude on
    # structural-error flow.
    "check.tw.spec.indigenousTerms.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 65),
    "check.tw.spec.indigenousTerms.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 65),

    # US-specific spec content (sequence listing → cross-reference → prior art
    # → restrictive wording → drawings overview tile). These emit only on
    # US pipelines, so their relative order vs. the CN/TW items above is
    # observationally irrelevant.
    "check.spec.sequenceListing.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 70),
    "check.spec.sequenceListing.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 70),
    "check.spec.crossReference.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 80),
    "check.spec.crossReference.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 80),
    "check.spec.priorArt.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 90),
    "check.spec.priorArt.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 90),
    "check.spec.restrictiveWording.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 100),
    "check.spec.restrictiveWording.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 100),
    # Scope-limit wording (Phillips v. AWH, MPEP § 2111) — sits immediately
    # after restrictiveWording in the spec-content group. Different
    # doctrine + surface from the claims-side restrictiveWording check;
    # see specification.py check_scope_limit_wording for rationale.
    "check.spec.scopeLimitWording.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 105),
    "check.spec.scopeLimitWording.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 105),
    # Reference numeral consistency D1 (MPEP § 608.01(g)) — placed
    # immediately after figureRefConsistency (idx 10) since both check
    # refnum usage in the spec. Consistent across US/CN/TW jurisdictions
    # so users see the same relative position regardless of jurisdiction.
    "check.spec.numeralConsistency.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 15),
    "check.spec.numeralConsistency.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 15),
    "check.spec.numeralConsistency.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 15),
    "check.spec.drawings": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 110),

    # TW symbol-vs-representative-drawing is a spec-content cross-reference.
    "check.tw.crossRef.symbolVsRepDrawing.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 120),
    "check.tw.crossRef.symbolVsRepDrawing.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 120),

    # =====================================================================
    # DRAWINGS bucket (Group 3)
    # =====================================================================
    "check.drawings.count": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 10),
    "check.cn.drawings.figureCount.pass": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 10),
    "check.tw.drawings.figureCount.pass": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 10),

    "check.drawings.singleFigure.amend": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 20),
    "check.drawings.singleFigure.pass": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 20),

    "check.drawings.priorArt.verify": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 30),
    "check.drawings.priorArt.pass": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 30),
    "check.cn.drawings.priorArt.verify": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 30),
    "check.cn.drawings.priorArt.pass": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 30),

    "check.drawings.sequential.amend": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 40),
    "check.drawings.sequential.pass": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 40),
    "check.cn.drawings.figuresSequential.amend": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 40),
    "check.cn.drawings.figuresSequential.pass": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 40),
    "check.cn.drawings.figuresSequential.passNone": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 40),
    "check.tw.drawings.figuresSequential.amend": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 40),
    "check.tw.drawings.figuresSequential.pass": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 40),
    "check.tw.drawings.figuresSequential.passNone": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 40),

    "checks.figure_xref_orphaned_brief": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 50),
    "checks.figure_xref_orphaned_detailed": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 50),
    "checks.figure_xref_pass": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 50),

    # =====================================================================
    # CLAIMS bucket
    # =====================================================================
    # --- Group 4: Claims structure ---
    "check.claims.sequential.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 10),
    "check.claims.sequential.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 10),
    "check.cn.claims.sequential.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 10),
    "check.cn.claims.sequential.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 10),
    "check.tw.claims.sequential.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 10),
    "check.tw.claims.sequential.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 10),

    "check.cn.claims.dependencyFormat.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 20),
    "check.cn.claims.dependencyFormat.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 20),
    "check.tw.claims.dependencyFormat.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 20),
    "check.tw.claims.dependencyFormat.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 20),

    # Independent claim opening — advisory (VERIFY). Statute (施行細則 §18 /
    # 实施细则 §22) requires preamble to state subject-matter name but does
    # NOT literally mandate 一種/一种; it's a strong practitioner convention
    # that TIPO 偵錯系統 + CNIPA 审查指南 §3.1.1 canonical examples follow.
    # Emit right after dependency-format since both validate preamble text.
    "check.cn.claims.independentPreamble.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 22),
    "check.cn.claims.independentPreamble.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 22),
    "check.tw.claims.independentPreamble.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 22),
    "check.tw.claims.independentPreamble.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 22),

    "check.claims.multipleDependent.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 25),
    "check.claims.multipleDependent.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 25),
    "check.claims.chainedMultiDep.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 27),
    "check.claims.chainedMultiDep.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 27),

    "check.claims.selfDependent.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 30),
    "check.claims.selfDependent.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 30),
    "check.cn.claims.selfDependent.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 30),
    "check.cn.claims.selfDependent.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 30),
    "check.tw.claims.selfDependent.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 30),
    "check.tw.claims.selfDependent.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 30),

    "check.tw.claims.circularDependency.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 40),
    "check.tw.claims.circularDependency.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 40),

    "check.cn.claims.forwardDependency.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 50),
    "check.cn.claims.forwardDependency.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 50),
    "check.tw.claims.forwardDependency.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 50),
    "check.tw.claims.forwardDependency.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 50),

    "check.cn.claims.singleSentence.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 60),
    "check.cn.claims.singleSentence.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 60),
    "check.tw.claims.singleSentence.amendMissingPeriod": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 60),
    "check.tw.claims.singleSentence.amendMultiSentence": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 60),
    "check.tw.claims.singleSentence.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 60),

    "check.cn.claims.refNumeralParens.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 70),
    "check.cn.claims.refNumeralParens.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 70),
    "check.tw.claims.refNumeralParens.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 70),
    "check.tw.claims.refNumeralParens.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 70),

    "check.cn.claims.subjectConsistency.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 80),
    "check.cn.claims.subjectConsistency.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 80),
    "check.cn.claims.subjectConsistencyParseUnclear": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 80),
    "check.tw.claims.subjectConsistency.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 80),
    "check.tw.claims.subjectConsistency.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 80),
    "check.tw.claims.subjectConsistencyParseUnclear": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 80),

    # US transition_checks populate claims_checks; the transition-phrase
    # walker emits one summary CheckItem + follow-up rows.
    "check.claims.missingTransition": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 90),
    "check.claims.transitionsPresent": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 90),
    "check.cn.claims.transitionPhrase.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 90),
    "check.cn.claims.transitionPhrase.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 90),
    "check.tw.claims.transitionPhrase.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 90),
    "check.tw.claims.transitionPhrase.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 90),

    "check.cn.claims.dependentOrdering.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 100),
    "check.cn.claims.dependentOrdering.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 100),

    # --- Group 5: Claims cross-jurisdiction ---
    "check.cn.claims.twTerminology.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 10),
    "check.cn.claims.twTerminology.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 10),
    "check.tw.claims.cnTerminology.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 10),
    "check.tw.claims.cnTerminology.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 10),

    "check.cn.claims.specReference.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 20),
    "check.cn.claims.specReference.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 20),
    "check.tw.claims.specDrawingRef.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 20),
    "check.tw.claims.specDrawingRef.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 20),

    "check.cn.claims.multiMultiDep.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 30),
    "check.cn.claims.multiMultiDep.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 30),
    "check.tw.claims.multiDepOnMultiDep.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 30),
    "check.tw.claims.multiDepOnMultiDep.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 30),

    "check.tw.claims.multiDepAlternative.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 40),
    "check.tw.claims.multiDepAlternative.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 40),

    "check.tw.claims.titleSubjectMatch.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 50),
    "check.tw.claims.titleSubjectMatch.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 50),

    "check.tw.claims.symbolTableConsistency.noClaimNumerals": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 60),
    "check.tw.claims.symbolTableConsistency.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 60),
    "check.tw.claims.symbolTableConsistency.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 60),

    # Connection-relationships — CN + TW both emit last in cross-jurisdiction.
    "check.cn.claims.connectionRelationships.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 70),
    "check.cn.claims.connectionRelationships.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 70),
    "check.tw.claims.connectionRelationships.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 70),
    "check.tw.claims.connectionRelationships.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 70),

    "check.claims.restrictiveAbsolutes.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 80),
    "check.claims.restrictiveAbsolutes.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 80),
    "check.claims.indefiniteWording.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 82),
    "check.claims.indefiniteWording.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 82),

    # --- Group 6: Claims § 112 analysis ---
    "check.claims.meansFunction.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 10),
    "check.claims.meansFunction.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 10),

    "check.claims.antecedentBasis.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 20),
    "check.claims.antecedentBasis.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 20),
    "check.cn.claims.antecedentBasis.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 20),
    "check.cn.claims.antecedentBasis.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 20),
    "check.tw.claims.antecedentBasis.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 20),
    "check.tw.claims.antecedentBasis.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 20),

    "checks.spec_support_pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 30),
    "checks.spec_support_unsupported_terms": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 30),
    "check.cn.claims.specSupport.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 30),
    "check.cn.claims.specSupport.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 30),
    "check.tw.claims.specSupport.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 30),
    "check.tw.claims.specSupport.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 30),

    # US preamble walker.
    "checks.preamble_cross_category_mismatch": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 40),
    "checks.preamble_cross_category_pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 40),
    "checks.preamble_indefinite_article": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 40),
    "checks.preamble_noun_mismatch": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 40),
    "checks.preamble_parse_unclear": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 40),

    # Special claim formats — MPEP §§ 2117 / 2129 / 2173.05(r), 35 U.S.C. §101 CRM.
    "claims.jepsonPriorArt": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 50),
    "claims.crmNonTransitory": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 50),
    "claims.markushOpenTransition": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 50),
    "claims.omnibusClaim": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 50),
    "claims.specialFormatsPass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 50),
    "check.cn.claims.omnibus.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 50),
    "check.cn.claims.omnibus.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 50),
    "check.cn.claims.markushOpenTransition.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 50),
    "check.cn.claims.markushOpenTransition.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 50),

    # Claim punctuation (MPEP § 608.01(m) / 35 U.S.C. §112(b)).
    "claims.extraPeriod": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 60),
    "claims.missingPeriod": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 60),
    "claims.whereinComma": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 60),
    "claims.punctuationPass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 60),

    # End-of-bucket summary tile.
    "check.claims.overview": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 99),

    # =====================================================================
    # ABSTRACT bucket (Group 7)
    # =====================================================================
    "check.abstract.wordCount.amend": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 10),
    "check.abstract.wordCount.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 10),
    "check.cn.abstract.charCount.amend": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 10),
    "check.cn.abstract.charCount.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 10),
    "check.tw.abstract.charCount.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 10),
    "check.tw.abstract.charCount.amend": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 10),

    "check.cn.abstract.titleMatch.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 20),
    "check.cn.abstract.titleMatch.passCompound": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 20),
    "check.cn.abstract.titleMatch.verify": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 20),
    "check.tw.abstract.titleMatch.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 20),
    "check.tw.abstract.titleMatch.passCompound": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 20),
    "check.tw.abstract.titleMatch.verify": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 20),

    "check.cn.abstract.commercialLanguage.amend": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 30),
    "check.cn.abstract.commercialLanguage.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 30),
    "check.tw.abstract.commercialLanguage.amend": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 30),
    "check.tw.abstract.commercialLanguage.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 30),

    "check.abstract.legalPhraseology.verify": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 40),
    "check.abstract.legalPhraseology.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 40),
    "check.abstract.meritLanguage.verify": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 42),
    "check.abstract.meritLanguage.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 42),

    "check.abstract.impliedPhrases.amend": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 50),
    "check.abstract.impliedPhrases.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 50),

    "check.abstract.structure.amend": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 60),
    "check.abstract.structure.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 60),

    "check.tw.abstract.representativeDrawing.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 70),
    "check.tw.abstract.representativeDrawing.verify": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 70),

    # =====================================================================
    # EPC bucket assignments (v1 beta) — mirror US/CN/TW canonical idx
    # values for parallel keys. Anchors the rubric routing (every key
    # registered here ends up in the right RubricSection via
    # section_for_message_key); also documents the canonical group +
    # index for any future EPC-emission-order monotonicity test.
    # =====================================================================
    # --- SPEC / Group 1: spec structure ---
    "check.epc.spec.requiredSections.amend": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 20),
    "check.epc.spec.requiredSections.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 20),
    "check.epc.spec.sectionOrdering.amend": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 30),
    "check.epc.spec.sectionOrdering.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 30),
    "check.epc.spec.paragraphNumbering.verify": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 40),
    "check.epc.spec.paragraphNumbering.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 40),
    "check.epc.spec.paragraphEnding.verify": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 50),
    "check.epc.spec.paragraphEnding.pass": (CheckBucket.SPEC, CheckGroup.SPEC_STRUCTURE, 50),

    # --- SPEC / Group 2: spec content ---
    # figureRefConsistency is dual-routed to DRAWINGS by the rubric's
    # explicit prefix list; still register here for the canonical map.
    "check.epc.spec.figureRefConsistency.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 10),
    "check.epc.spec.figureRefConsistency.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 10),
    "check.epc.spec.figureRefConsistency.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 10),
    "check.epc.spec.numeralConsistency.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 15),
    "check.epc.spec.numeralConsistency.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 15),
    "check.epc.spec.numeralConsistency.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 15),
    "check.epc.spec.titleRequired.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.epc.spec.titleRequired.verify": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.epc.spec.titleRequired.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 30),
    "check.epc.spec.claimReferenceInSpec.amend": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 40),
    "check.epc.spec.claimReferenceInSpec.pass": (CheckBucket.SPEC, CheckGroup.SPEC_CONTENT, 40),

    # --- DRAWINGS / Group 3 ---
    "check.epc.drawings.figureCount.pass": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 10),
    "check.epc.drawings.singleFigureLabel.verify": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 20),
    "check.epc.drawings.singleFigureLabel.pass": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 20),
    "check.epc.drawings.priorArtLabeling.verify": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 30),
    "check.epc.drawings.priorArtLabeling.pass": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 30),
    "check.epc.drawings.figuresSequential.amend": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 40),
    "check.epc.drawings.figuresSequential.pass": (CheckBucket.DRAWINGS, CheckGroup.DRAWINGS, 40),

    # --- CLAIMS / Group 4: claims structure ---
    "check.epc.claims.sequential.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 10),
    "check.epc.claims.sequential.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 10),
    "check.epc.claims.dependencyFormat.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 20),
    "check.epc.claims.dependencyFormat.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 20),
    "check.epc.claims.selfDependent.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 30),
    "check.epc.claims.selfDependent.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 30),
    "check.epc.claims.forwardDependency.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 50),
    "check.epc.claims.forwardDependency.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 50),
    "check.epc.claims.singleSentence.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 60),
    "check.epc.claims.singleSentence.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 60),
    "check.epc.claims.refSignsInParens.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 70),
    "check.epc.claims.refSignsInParens.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 70),
    "check.epc.claims.subjectConsistency.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 80),
    "check.epc.claims.subjectConsistency.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 80),
    "check.epc.claims.transitionPhrase.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 90),
    "check.epc.claims.transitionPhrase.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_STRUCTURE, 90),

    # --- CLAIMS / Group 5: cross-jurisdiction / format guards ---
    "check.epc.claims.specReference.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 20),
    "check.epc.claims.specReference.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 20),
    "check.epc.claims.multiDepOnMultiDep.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 30),
    "check.epc.claims.multiDepOnMultiDep.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 30),
    # markushFormat (Guidelines F-IV § 4.20) — EPC treats Markush as a
    # format guard for closed groups. Sits in CROSS_JURISDICTION rather
    # than SECTION_112 (US convention) so the run_g5 runner stays
    # monotonic.
    "check.epc.claims.markushFormat.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 35),
    "check.epc.claims.markushFormat.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 35),
    # EPC-specific advisories — independentClaimCount (Rule 43(2)+(3))
    # and twoPartForm (Rule 43(1)) — get late CROSS_JURISDICTION idx
    # values so they emit after structural guards within the runner.
    "check.epc.claims.independentClaimCount.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 75),
    "check.epc.claims.independentClaimCount.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 75),
    "check.epc.claims.twoPartForm.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 95),
    "check.epc.claims.twoPartForm.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_CROSS_JURISDICTION, 95),

    # --- CLAIMS / Group 6: § 112-equivalent (Art. 84 EPC) ---
    # EPC-specific idx values arrange emit order to be monotonic with
    # the run_g6 runner: punctuation → restrictiveAbsolutes → antecedent
    # → spec_support → markushFormat. Punctuation gets the lowest idx
    # (5) so it emits first in the SECTION_112 group; restrictiveAbsolutes
    # at idx 10; antecedent at the canonical 20; spec_support at 30;
    # markushFormat at 50.
    "check.epc.claims.punctuation.missingPeriod.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 5),
    "check.epc.claims.punctuation.extraPeriod.amend": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 5),
    "check.epc.claims.punctuation.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 5),
    "check.epc.claims.restrictiveAbsolutes.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 10),
    "check.epc.claims.restrictiveAbsolutes.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 10),
    "check.epc.claims.antecedentBasis.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 20),
    "check.epc.claims.antecedentBasis.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 20),
    "check.epc.claims.specSupport.verify": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 30),
    "check.epc.claims.specSupport.pass": (CheckBucket.CLAIMS, CheckGroup.CLAIMS_SECTION_112, 30),

    # --- ABSTRACT / Group 7 ---
    "check.epc.abstract.wordCount.amend": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 10),
    "check.epc.abstract.wordCount.verify": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 10),
    "check.epc.abstract.wordCount.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 10),
    "check.epc.abstract.structure.amend": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 60),
    "check.epc.abstract.structure.pass": (CheckBucket.ABSTRACT, CheckGroup.ABSTRACT, 60),
}


def canonical_rank(message_key: str) -> tuple[CheckBucket, CheckGroup, int] | None:
    """Return (bucket, group, idx) for a registered message_key, else None.

    A None return means the key is not registered in CANONICAL_CHECK_ORDER
    — treat as a drift signal. The regression test in
    tests/test_check_emission_order.py fails loudly on unregistered keys
    emitted by any pipeline, which forces new check families to be
    slotted into the canonical order before they can ship.
    """
    return CANONICAL_CHECK_ORDER.get(message_key)


def sort_key(check_item) -> tuple[int, int, int]:
    """Sort key for a CheckItem. Unregistered keys sort last (sentinel)."""
    rank = canonical_rank(check_item.message_key)
    if rank is None:
        return (CheckBucket.DRAWINGS.value + 1, 0, 0)
    bucket, group, idx = rank
    return (bucket.value, group.value, idx)
