# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""PatentLint analysis pipeline — zero web-framework dependencies.

Entry points for CLI and API. This module is also what Pyodide calls in the browser.
"""

from __future__ import annotations

import tempfile

from patentlint.analysis import abstract as abstract_analysis
from patentlint.analysis import claims as claims_analysis
from patentlint.analysis import cn_abstract as cn_abstract_analysis
from patentlint.analysis import cn_claims as cn_claims_analysis
from patentlint.analysis import cn_spec_support as cn_spec_support_analysis
from patentlint.analysis import cn_specification as cn_spec_analysis
from patentlint.analysis import drawings as drawings_analysis
from patentlint.analysis import specification as spec_analysis
from patentlint.analysis import tw_abstract as tw_abstract_analysis
from patentlint.analysis import tw_claims as tw_claims_analysis
from patentlint.analysis import tw_cross_reference as tw_cross_ref_analysis
from patentlint.analysis import tw_spec_support as tw_spec_support_analysis
from patentlint.analysis import tw_specification as tw_spec_analysis
from patentlint.models import AnalysisResult, CheckItem, CnPatentDocument, Jurisdiction, TwPatentDocument
from patentlint.parser import claims as claims_parser
from patentlint.parser import sections
from patentlint.parser.docx_loader import load_docx, load_docx_cn, load_docx_tw
from patentlint.parser.jurisdiction_mismatch import detect_jurisdiction_mismatch
from patentlint.parser.sections_cn import classify_document_cn, extract_cn_sections_from_docx
from patentlint.parser.sections_tw import classify_document_tw, extract_tw_sections
from patentlint.parser.xml_loader import extract_cn_xml_from_zip, parse_cnipa_xml
from patentlint.rubric import (
    compute_rubric_grade,
    detect_completeness_gap,
    detect_has_drawings,
    flatten_checks_from_lists,
)


# Issue #9 / ADR-082 revisit (2026-04-27) — language/jurisdiction mismatch
# detection lives in ``patentlint.parser.jurisdiction_mismatch`` and is
# wired in at the ``analyze_file`` / ``analyze_bytes`` entry points below.
# Result rides on AnalysisResult.jurisdiction_mismatch / suggested_jurisdiction.


def _attach_rubric_grade(
    result: AnalysisResult,
    *,
    has_drawings: bool,
    title: str,
    has_claims: bool,
    has_spec_body: bool,
    has_abstract: bool,
) -> None:
    """Compute and attach the rubric grade to a freshly-built AnalysisResult.

    Uses ``result.to_report_data()`` to gather the canonical user-visible
    check lists (the same lists the UI / PDF surface), so the grade is
    grounded in exactly what the drafter sees, not internal state.
    """
    report = result.to_report_data()
    all_checks = flatten_checks_from_lists(
        report.specification_checks,
        report.claims_checks,
        report.drawings_checks,
        report.abstract_checks,
    )
    gap = detect_completeness_gap(
        title=title,
        has_claims=has_claims,
        has_spec_body=has_spec_body,
        has_abstract=has_abstract,
    )
    result.rubric_grade = compute_rubric_grade(
        jurisdiction=result.jurisdiction,
        all_checks=all_checks,
        has_drawings=has_drawings,
        completeness_gap=gap,
    )


def _run_cn_pipeline(
    cn_doc: CnPatentDocument,
    *,
    likely_patent: bool = True,
    patent_detection_reason: str | None = None,
    has_tracked_changes: bool = False,
    suggested_jurisdiction: str | None = None,
    strict_plural_reference_matching: bool = False,
    strict_qualifier_matching: bool = False,
) -> AnalysisResult:
    """Run CN analysis pipeline with all 24 checks."""
    para_count = len(cn_doc.paragraph_numbers) if cn_doc.paragraph_numbers else (
        len(cn_doc.technical_field)
        + len(cn_doc.background)
        + len(cn_doc.summary)
        + len(cn_doc.drawings_description)
        + len(cn_doc.detailed_description)
    )

    # --- Specification checks (1–9) ---
    spec_checks: list[CheckItem] = []
    if has_tracked_changes:
        spec_checks.append(CheckItem(
            status="amend",
            message="Document contains tracked changes (revisions). Accept or reject all changes before filing.",
            message_key="check.cn.spec.trackedChanges.amend",
            reference="专利法实施细则 §20",
            diagnostics={"reason_code": "tracked_changes_present"},
        ))
    spec_checks = spec_checks + (
        cn_spec_analysis.check_required_sections(cn_doc)
        + cn_spec_analysis.check_section_ordering(cn_doc)
        + cn_spec_analysis.check_paragraph_numbering(cn_doc)
        + cn_spec_analysis.check_paragraph_ending(cn_doc)
        + cn_spec_analysis.check_figure_reference_consistency(cn_doc)
        # numeralConsistency follows figureRef — both validate refnum usage
        + cn_spec_analysis.check_numeral_consistency_cn(cn_doc)
        + cn_spec_analysis.check_patent_type_terminology(cn_doc)
        + cn_spec_analysis.check_title(cn_doc)
        + cn_spec_analysis.check_spec_claim_reference(cn_doc)
    )

    # --- Claims checks (9–21) ---
    # Emission order follows canonical groups (ADR-149):
    #   G4 claims-structure: sequential → dependency_format → self_dependent
    #     → forward_dependency → single_sentence → ref_numeral_parens
    #     → subject_consistency → transition_phrase → dependent_ordering
    #   G5 claims cross-jurisdiction: tw_terminology → claims_spec_reference
    #     → multi_multi_dep → connection_relationships
    #   G6 claims § 112: antecedent_basis → omnibus → markush_open_transition
    claims_checks = (
        cn_claims_analysis.check_claims_sequential(cn_doc)
        + cn_claims_analysis.check_dependency_format(cn_doc)
        + cn_claims_analysis.check_independent_preamble(cn_doc)
        + cn_claims_analysis.check_self_dependent(cn_doc)
        + cn_claims_analysis.check_forward_dependency(cn_doc)
        + cn_claims_analysis.check_single_sentence(cn_doc)
        + cn_claims_analysis.check_reference_numeral_parentheses(cn_doc)
        + cn_claims_analysis.check_subject_name_consistency(cn_doc)
        + cn_claims_analysis.check_transition_phrase(cn_doc)
        + cn_claims_analysis.check_dependent_ordering(cn_doc)
        + cn_claims_analysis.check_tw_terminology(cn_doc)
        + cn_claims_analysis.check_claims_spec_reference(cn_doc)
        + cn_claims_analysis.check_multi_multi_dependency(cn_doc)
        + cn_claims_analysis.check_connection_relationships_cn(cn_doc)
    )

    # Phase 8c: CN antecedent walker (parallel to TW). Emits structured
    # per-occurrence findings; the CheckItem summary tile aggregates.
    cn_antecedent_basis = cn_claims_analysis.check_antecedent_basis_cn(
        cn_doc,
        strict_plural_reference_matching=strict_plural_reference_matching,
        strict_qualifier_matching=strict_qualifier_matching,
    )
    # R57 (2026-05-05): cross-validate against spec body. Annotates each
    # finding with `term_in_spec` for the confidence-score helper.
    from patentlint.analysis.utils import annotate_term_in_spec
    cn_spec_text = "\n".join(
        list(cn_doc.technical_field)
        + list(cn_doc.background)
        + list(cn_doc.summary)
        + list(cn_doc.drawings_description)
        + list(cn_doc.detailed_description)
    )
    annotate_term_in_spec(cn_antecedent_basis, cn_spec_text)
    if cn_antecedent_basis:
        from patentlint.diagnostic_extractors import extract_antecedent_basis
        issue_count = len(cn_antecedent_basis)
        claim_ids = sorted({item["claim_id"] for item in cn_antecedent_basis})
        claim_count = len(claim_ids)
        claims_checks = list(claims_checks) + [
            CheckItem(
                status="amend",
                message="Possible missing antecedent basis found.",
                message_key="check.cn.claims.antecedentBasis.amend",
                details=f"{issue_count} term(s) may lack antecedent basis across {claim_count} claim(s).",
                details_key="details.cn.antecedentBasisTerms",
                details_params={
                    "issue_count": issue_count,
                    "claim_count": claim_count,
                    "claims": claim_ids,
                },
                reference="审查指南",
                diagnostics=extract_antecedent_basis(cn_antecedent_basis, len(cn_doc.claims)),
            )
        ]
    else:
        claims_checks = list(claims_checks) + [
            CheckItem(
                status="pass",
                message="All referenced terms have antecedent basis.",
                message_key="check.cn.claims.antecedentBasis.pass",
                reference="审查指南",
            )
        ]

    # G6 spec_support — CN port of ADR-138 TW spec-support. Emits
    # UnsupportedTerm findings for claim noun phrases that fail the 3-tier
    # match (normalized exact / raw exact / char-window). No Tier 0
    # symbol-table whitelist — CN has no 符号说明 surface. Statute anchor:
    # 专利法 §26 第4款 + 审查指南 第二部分第二章 §3.2.1.
    cn_unsupported_terms = cn_spec_support_analysis.check_spec_support_cn(
        cn_doc,
        antecedent_findings=cn_antecedent_basis,
        strict_qualifier_matching=strict_qualifier_matching,
    )
    # Cross-ref link: same (claim_id, term) appearing in both walkers
    # gets annotated so the Section112 frontend renders sibling-check
    # hints (§26 第2款/第3款 ↔ §26 第4款 equivalents in CNIPA terms).
    cn_spec_support_analysis.attach_cross_references_cn(
        cn_antecedent_basis,
        cn_unsupported_terms,
    )
    if cn_unsupported_terms:
        from patentlint.diagnostic_extractors import extract_spec_support
        issue_count = len(cn_unsupported_terms)
        claim_ids = sorted({ut.claim_number for ut in cn_unsupported_terms})
        claim_count = len(claim_ids)
        cn_spec_paragraph_count = (
            len(cn_doc.technical_field) + len(cn_doc.background) + len(cn_doc.summary)
            + len(cn_doc.drawings_description) + len(cn_doc.detailed_description)
        )
        claims_checks = list(claims_checks) + [
            CheckItem(
                status="amend",
                message="Possible claim terms not supported by the specification.",
                message_key="check.cn.claims.specSupport.amend",
                details=f"{issue_count} term(s) may lack specification support across {claim_count} claim(s).",
                details_key="details.cn.specSupportTerms",
                details_params={
                    "issue_count": issue_count,
                    "claim_count": claim_count,
                    "claims": claim_ids,
                },
                reference="专利法 §26 第4款",
                diagnostics=extract_spec_support(
                    cn_unsupported_terms,
                    total_claims=len(cn_doc.claims),
                    spec_paragraph_count=cn_spec_paragraph_count,
                ),
            )
        ]
    else:
        claims_checks = list(claims_checks) + [
            CheckItem(
                status="pass",
                message="All claim terms supported by the specification.",
                message_key="check.cn.claims.specSupport.pass",
                reference="专利法 §26 第4款",
            )
        ]

    # G6 — omnibus (§3.3) and Markush open transition (§9.3) emit after
    # the spec-support tile per the canonical claims §112 order.
    claims_checks = list(claims_checks) + (
        cn_claims_analysis.check_omnibus_claims(cn_doc)
        + cn_claims_analysis.check_markush_open_transition(cn_doc)
    )

    # --- Abstract checks (21–23) ---
    abstract_checks = (
        cn_abstract_analysis.check_abstract_char_count(cn_doc)
        + cn_abstract_analysis.check_abstract_title_match(cn_doc)
        + cn_abstract_analysis.check_commercial_language(cn_doc)
    )

    # --- Drawings checks (24–25) ---
    # Emission order: figure_count → figures_sequential per Phase 10C
    # document-order invariant (see CLAUDE.md "Check-ordering consistency
    # invariant"). Swapped from legacy sequential-then-count order.
    drawings_checks = (
        cn_abstract_analysis.check_figure_count(cn_doc)
        + cn_abstract_analysis.check_drawings_prior_art(cn_doc)
        + cn_abstract_analysis.check_figures_sequential(cn_doc)
    )

    result = AnalysisResult(
        jurisdiction=Jurisdiction.CN,
        patent_type=cn_doc.patent_type.value,
        paragraph_count=para_count,
        claims=cn_doc.claims,
        independent_claims_count=sum(1 for c in cn_doc.claims if c.independent),
        dependent_claims_count=sum(1 for c in cn_doc.claims if not c.independent),
        figures_count=cn_doc.figure_count,
        abstract_word_count=cn_doc.abstract_char_count,
        likely_patent=likely_patent,
        patent_detection_reason=patent_detection_reason,
        has_tracked_changes=has_tracked_changes,
        has_scanned_fallback=cn_doc.has_doc_page_fallback,
        cn_specification_checks=spec_checks,
        cn_claims_checks=claims_checks,
        cn_abstract_checks=abstract_checks,
        cn_drawings_checks=drawings_checks,
        cn_omnibus_claims=cn_claims_analysis.detect_omnibus_claims_cn(cn_doc),
        cn_markush_open_claims=[cid for cid, _ in cn_claims_analysis.detect_markush_open_transition_cn(cn_doc)],
        antecedent_basis_issues=cn_antecedent_basis,
        unsupported_terms=cn_unsupported_terms,
        jurisdiction_mismatch=bool(suggested_jurisdiction),
        suggested_jurisdiction=suggested_jurisdiction,
    )
    _attach_rubric_grade(
        result,
        has_drawings=detect_has_drawings(figures_count=cn_doc.figure_count, figure_refs=cn_doc.figure_refs),
        title=cn_doc.title,
        has_claims=bool(cn_doc.claims),
        has_spec_body=bool(
            "".join(cn_doc.technical_field + cn_doc.background + cn_doc.summary + cn_doc.detailed_description).strip()
        ),
        has_abstract=bool(cn_doc.abstract_text and cn_doc.abstract_text.strip()),
    )
    return result


def _run_pipeline(
    loaded,
    full_text: str,
    *,
    jurisdiction: Jurisdiction = Jurisdiction.US,
    suggested_jurisdiction: str | None = None,
) -> AnalysisResult:
    """Core pipeline logic shared by analyze_file and analyze_bytes."""

    # --- Document type detection ---
    likely_patent, detection_reason = sections.classify_document(full_text)
    patent_detection_reason = detection_reason.value

    # --- Title extraction (MPEP § 606) ---
    title = sections.extract_title(full_text)

    # --- Section extraction ---
    claims_section = sections.extract_claims_section(full_text)
    abstract_section = sections.extract_abstract_section(full_text)
    drawings_section = sections.extract_description_of_drawings_section(full_text)
    cross_ref_section = sections.extract_cross_reference_section(full_text)
    background_section = sections.extract_background_section(full_text)
    detailed_desc_section = sections.extract_detailed_description_section(full_text)
    summary_section = sections.extract_summary_section(full_text)

    # --- Claims analysis ---
    claims = claims_parser.parse_claims(claims_section)

    if claims:
        claim_ids = [c.id for c in claims]
        punctuation_checks = claims_analysis.check_claim_punctuation(claims)
        multiple_deps = claims_analysis.find_multiple_dependents(claims)
        chained_multi_deps = claims_analysis.find_chained_multi_dependents(claims)
        self_deps = claims_analysis.find_self_dependent_claims(claims)
        claims_seq = claims_analysis.are_claims_sequential(claim_ids)
        last_seq_claim = claims_analysis.get_last_sequential_index(claim_ids)
        claims_restrictive = claims_parser.detect_restrictive_absolutes_in_claims(claims)
        claims_indefinite = claims_parser.detect_indefinite_wording_in_claims(claims)
        means_plus_function = claims_analysis.detect_means_plus_function(claims)
        antecedent_basis = claims_analysis.check_antecedent_basis(claims)
        preamble_checks = claims_analysis.check_preamble_consistency(claims)
        transition_checks = claims_analysis.check_claim_transitions(claims)
        special_format_checks = claims_analysis.check_special_claim_formats(claims)
        spec_text = (summary_section or "") + "\n" + (detailed_desc_section or "")
        # R61c (2026-05-05): cross-validate US findings against spec body.
        # Path 1 corpus measurement on TW supplement_v2 surfaced
        # term_in_description=False as the strongest production signal
        # (0.8% legit on n=264 absent-from-spec findings vs 12.8% baseline).
        # Same `annotate_term_in_spec` helper applies the validated −15
        # confidence penalty when the term is missing from spec body.
        from patentlint.analysis.utils import annotate_term_in_spec
        annotate_term_in_spec(antecedent_basis, spec_text)
        unsupported_terms = claims_analysis.check_spec_support(claims, spec_text)
        # ADR-091 (Option Y): both checks emit independently; compute the
        # cross-reference set so the frontend can render hint lines linking
        # related findings rather than silently hiding one branch.
        claims_analysis.attach_cross_references(antecedent_basis, unsupported_terms)
        independent_count = claims_analysis.count_independent(claims)
        dependent_count = claims_analysis.count_dependent(claims)
    else:
        claim_ids = []
        punctuation_checks = []
        multiple_deps = []
        chained_multi_deps = []
        self_deps = []
        claims_seq = True
        last_seq_claim = 0
        claims_restrictive = claims_parser.detect_restrictive_absolutes_in_claims([])
        claims_indefinite = claims_parser.detect_indefinite_wording_in_claims([])
        means_plus_function = []
        antecedent_basis = []
        preamble_checks = []
        transition_checks = []
        special_format_checks = []
        unsupported_terms = []
        independent_count = 0
        dependent_count = 0

    # --- Drawings analysis ---
    figures_count = drawings_analysis.get_figure_count(drawings_section) if drawings_section else 0
    figures_seq = drawings_analysis.are_figures_sequential(drawings_section) if drawings_section else True
    figures_missing = (
        drawings_analysis.compute_missing_figure_numbers(drawings_section)
        if (drawings_section and not figures_seq)
        else []
    )
    single_fig = drawings_analysis.is_single_figure(full_text)
    wrong_label = drawings_analysis.uses_wrong_label_for_single_figure(full_text) if single_fig else False
    prior_art_drawings = drawings_analysis.contains_prior_art_references(drawings_section) if drawings_section else False

    # --- Reference numeral inventory ---
    ref_spec_text = (detailed_desc_section or "") + "\n" + (summary_section or "") + "\n" + (drawings_section or "")
    ref_numerals = spec_analysis.extract_reference_numeral_inventory(ref_spec_text) if ref_spec_text.strip() else []

    # --- Abstract analysis ---
    abstract_word_count = abstract_analysis.count_words(abstract_section)
    abstract_structure = abstract_analysis.is_single_paragraph_and_final(full_text, abstract_section) if abstract_section else True
    abstract_implied_phrases = abstract_analysis.detect_implied_phrases(abstract_section) if abstract_section else []
    abstract_implied = bool(abstract_implied_phrases)
    abstract_legal_phraseology = abstract_analysis.detect_legal_phraseology(abstract_section) if abstract_section else ""
    abstract_legal_phraseology_items = abstract_analysis.detect_legal_phraseology_items(abstract_section) if abstract_section else []
    abstract_merit_language = abstract_analysis.detect_merit_language(abstract_section) if abstract_section else ""
    abstract_merit_language_items = abstract_analysis.detect_merit_language_items(abstract_section) if abstract_section else []

    # --- Required sections check ---
    required_sections_checks = spec_analysis.check_required_sections(full_text)

    # --- Scope-limit wording (US, MPEP § 2111 + Phillips v. AWH) ---
    # Scan the spec BODY only — concatenate background + summary + detailed
    # description. Title/claims/abstract have their own checks.
    scope_limit_text = " ".join(
        s for s in [background_section, summary_section, detailed_desc_section]
        if s
    )
    scope_limit_checks = spec_analysis.check_scope_limit_wording(scope_limit_text)

    # --- Reference numeral consistency (D1, US, MPEP § 608.01(g)) ---
    # Same scope as scope-limit (spec body — background + summary + DD).
    # Detects same-numeral / different-name conflicts; permits same-name /
    # different-numeral (legit multiple instances).
    numeral_consistency_checks = spec_analysis.check_numeral_consistency(scope_limit_text)

    # --- Figure cross-reference consistency ---
    figure_xref_checks = drawings_analysis.check_figure_cross_references(
        drawings_section or "", detailed_desc_section or "",
    )

    # --- Specification analysis ---
    para_nums = loaded.paragraph_numberings
    para_seq = spec_analysis.are_paragraphs_sequential(para_nums)
    last_seq_para = spec_analysis.get_last_sequential_index(para_nums)
    seq_listing = spec_analysis.has_sequence_listing_mismatch(full_text)

    # Prior art citations from cross-reference and background
    cross_ref_citations = sections.detect_prior_art_citations(cross_ref_section) if cross_ref_section else ""
    prior_art_citations = sections.detect_prior_art_citations(background_section) if background_section else ""

    result = AnalysisResult(
        jurisdiction=jurisdiction,
        # Document-level flag
        likely_patent=likely_patent,
        patent_detection_reason=patent_detection_reason,
        # Specification
        title=title,
        has_tracked_changes=loaded.has_tracked_changes,
        paragraph_count=len(para_nums),
        improper_spec_paragraphs=loaded.improper_spec_paragraphs,
        improper_spec_phrases_formatted=loaded.improper_spec_phrases,
        paragraphs_sequential=para_seq,
        last_sequential_paragraph=last_seq_para,
        missing_ending_paragraphs=loaded.missing_ending_paragraphs,
        sequence_listing_mismatch=seq_listing,
        cross_reference_text=cross_ref_section,
        cross_reference_citations=cross_ref_citations,
        prior_art_citations=prior_art_citations,
        # Drawings
        figures_count=figures_count,
        figures_sequential=figures_seq,
        figures_missing=figures_missing,
        contains_prior_art_in_drawings=prior_art_drawings,
        single_figure=single_fig,
        wrong_label_for_single_figure=wrong_label,
        # Claims
        claims=claims,
        restrictive_absolute_claims=claims_restrictive.improper_claims,
        restrictive_absolute_phrases_formatted=claims_restrictive.formatted_phrases,
        indefinite_wording_claims=claims_indefinite.improper_claims,
        indefinite_wording_phrases_formatted=claims_indefinite.formatted_phrases,
        independent_claims_count=independent_count,
        dependent_claims_count=dependent_count,
        claims_sequential=claims_seq,
        last_sequential_claim=last_seq_claim,
        punctuation_checks=punctuation_checks,
        multiple_dependent_claims=multiple_deps,
        chained_multi_dep_claims=chained_multi_deps,
        self_dependent_claims=self_deps,
        means_plus_function_claims=means_plus_function,
        antecedent_basis_issues=antecedent_basis,
        preamble_checks=preamble_checks,
        transition_checks=transition_checks,
        special_format_checks=special_format_checks,
        unsupported_terms=unsupported_terms,
        # Drawings — reference numerals
        reference_numerals=ref_numerals,
        # Phase 5 — Issue #2 & #3
        required_sections_checks=required_sections_checks,
        figure_xref_checks=figure_xref_checks,
        # Scope-limit wording (US, MPEP § 2111 + Phillips)
        scope_limit_checks=scope_limit_checks,
        # Numeral consistency D1 (US, MPEP § 608.01(g))
        numeral_consistency_checks=numeral_consistency_checks,
        # Abstract
        abstract_word_count=abstract_word_count,
        abstract_text=abstract_section or "",
        abstract_structure_good=abstract_structure,
        abstract_has_implied_phrase=abstract_implied,
        abstract_implied_phrases=abstract_implied_phrases,
        abstract_legal_phraseology_formatted=abstract_legal_phraseology,
        abstract_legal_phraseology_items=abstract_legal_phraseology_items,
        abstract_merit_language_formatted=abstract_merit_language,
        abstract_merit_language_items=abstract_merit_language_items,
        jurisdiction_mismatch=bool(suggested_jurisdiction),
        suggested_jurisdiction=suggested_jurisdiction,
    )
    _attach_rubric_grade(
        result,
        has_drawings=detect_has_drawings(figures_count=figures_count),
        title=title,
        has_claims=bool(claims),
        has_spec_body=bool((detailed_desc_section or "").strip() or (background_section or "").strip()),
        has_abstract=abstract_word_count > 0,
    )
    return result


def _run_tw_pipeline(
    tw_doc: TwPatentDocument,
    *,
    likely_patent: bool = True,
    patent_detection_reason: str | None = None,
    has_tracked_changes: bool = False,
    suggested_jurisdiction: str | None = None,
    strict_plural_reference_matching: bool = False,
    strict_qualifier_matching: bool = False,
) -> AnalysisResult:
    """Run TW pipeline with specification checks."""
    para_count = len(tw_doc.paragraph_numbers) if tw_doc.paragraph_numbers else (
        len(tw_doc.technical_field)
        + len(tw_doc.prior_art)
        + len(tw_doc.disclosure)
        + len(tw_doc.drawings_description)
        + len(tw_doc.embodiment)
    )

    # --- Specification checks (1–11) ---
    # Emission order follows canonical groups (ADR-149):
    #   G1 spec-structure: required_sections → section_ordering
    #     → paragraph_numbering → paragraph_ending → bracket_format
    #   G2 spec-content: figure_ref_consistency → patent_type_terminology
    #     → title → claim_reference → symbol_table_presence
    #     → symbol_table_consistency → symbol_vs_rep_drawing (spliced below)
    # bracket_format (施行細則 §17 header structure) moved up from trailing
    # position to its canonical G1 slot after paragraph_ending.
    spec_checks = (
        tw_spec_analysis.check_required_sections(tw_doc)
        + tw_spec_analysis.check_section_ordering(tw_doc)
        + tw_spec_analysis.check_paragraph_numbering(tw_doc)
        + tw_spec_analysis.check_paragraph_ending(tw_doc)
        + tw_cross_ref_analysis.check_bracket_format(tw_doc)
        + tw_spec_analysis.check_figure_ref_consistency(tw_doc)
        # numeralConsistency follows figureRef — both validate refnum usage
        + tw_spec_analysis.check_numeral_consistency_tw(tw_doc)  # idx 15
        + tw_spec_analysis.check_patent_type_terminology(tw_doc)
        + tw_spec_analysis.check_title(tw_doc)
        + tw_spec_analysis.check_spec_claim_reference(tw_doc)
        + tw_spec_analysis.check_symbol_table_presence(tw_doc)   # idx 50
        + tw_spec_analysis.check_symbol_table_coverage_tw(tw_doc)  # idx 55
        + tw_spec_analysis.check_symbol_table_consistency(tw_doc)  # idx 60
        + tw_spec_analysis.check_indigenous_terms(tw_doc)
    )

    # --- Claims checks (11–27) ---
    claims_checks = (
        tw_claims_analysis.check_claims_sequential(tw_doc)
        + tw_claims_analysis.check_dependency_format(tw_doc)
        + tw_claims_analysis.check_independent_preamble(tw_doc)
        + tw_claims_analysis.check_self_dependent(tw_doc)
        + tw_claims_analysis.check_circular_dependency(tw_doc)
        + tw_claims_analysis.check_forward_dependency(tw_doc)
        + tw_claims_analysis.check_single_sentence(tw_doc)
        + tw_claims_analysis.check_ref_numeral_parens(tw_doc)
        + tw_claims_analysis.check_subject_consistency(tw_doc)
        + tw_claims_analysis.check_transition_phrase(tw_doc)
        + tw_claims_analysis.check_cn_terminology(tw_doc)
        + tw_claims_analysis.check_spec_drawing_ref(tw_doc)
        + tw_claims_analysis.check_multi_dep_on_multi_dep(tw_doc)
        + tw_claims_analysis.check_multi_dep_alternative(tw_doc)
        + tw_claims_analysis.check_title_subject_match(tw_doc)
        + tw_claims_analysis.check_claims_symbol_table_consistency(tw_doc)
        + tw_claims_analysis.check_connection_relationships_tw(tw_doc)
    )

    # Phase 8b: walker emits structured per-occurrence findings. Both the
    # CheckItem summary tile (appended below) and the structured payload
    # (passed via AnalysisResult.antecedent_basis_issues for the
    # Section112 frontend card) come from the same walker call.
    tw_antecedent_basis = tw_claims_analysis.check_antecedent_basis(
        tw_doc,
        strict_plural_reference_matching=strict_plural_reference_matching,
        strict_qualifier_matching=strict_qualifier_matching,
    )
    # R57 (2026-05-05): cross-validate TW findings against spec body.
    from patentlint.analysis.utils import annotate_term_in_spec
    tw_spec_text = "\n".join(
        list(tw_doc.technical_field)
        + list(tw_doc.prior_art)
        + list(tw_doc.disclosure)
        + list(tw_doc.drawings_description)
        + list(tw_doc.embodiment)
    )
    annotate_term_in_spec(tw_antecedent_basis, tw_spec_text)

    # ADR-138: TW specification-support check (專利法 §26 第3項).
    # Emits UnsupportedTerm findings for claim noun phrases that fail
    # the 4-tier match (symbol table / normalized exact / raw exact /
    # char-window). Walker-tuning flags intentionally NOT forwarded —
    # spec-support normalization is a separate semantic axis.
    tw_unsupported_terms = tw_spec_support_analysis.check_spec_support_tw(tw_doc)
    # ADR-138 supersedes ADR-091's "TW cross_ref expected to remain null"
    # — populate cross_ref on overlapping (claim_id, term) pairs so the
    # Section112 frontend cards render sibling-check hint lines.
    tw_spec_support_analysis.attach_cross_references_tw(
        tw_antecedent_basis,
        tw_unsupported_terms,
    )
    # Emit antecedent tile BEFORE spec-support tile so the summary-grid
    # ordering matches Section112Container (antecedent card renders first,
    # spec-support card renders below). Both cite 專利法 §26 第3項 — they
    # are sibling sub-requirements under the same statute clause
    # (ADR-138), so the umbrella heading + the two tiles carry a single
    # coherent citation.
    if tw_antecedent_basis:
        from patentlint.diagnostic_extractors import extract_antecedent_basis
        issue_count = len(tw_antecedent_basis)
        claim_ids = sorted({item["claim_id"] for item in tw_antecedent_basis})
        claim_count = len(claim_ids)
        claims_checks = list(claims_checks) + [
            CheckItem(
                status="amend",
                message="Possible missing antecedent basis found.",
                message_key="check.tw.claims.antecedentBasis.amend",
                details=f"{issue_count} term(s) may lack antecedent basis across {claim_count} claim(s).",
                details_key="details.tw.antecedentBasisTerms",
                details_params={
                    "issue_count": issue_count,
                    "claim_count": claim_count,
                    "claims": claim_ids,
                },
                reference="專利法 §26 第3項",
                diagnostics=extract_antecedent_basis(tw_antecedent_basis, len(tw_doc.claims)),
            )
        ]
    else:
        claims_checks = list(claims_checks) + [
            CheckItem(
                status="pass",
                message="All referenced terms have antecedent basis.",
                message_key="check.tw.claims.antecedentBasis.pass",
                reference="專利法 §26 第3項",
            )
        ]
    if tw_unsupported_terms:
        from patentlint.diagnostic_extractors import extract_spec_support
        issue_count = len(tw_unsupported_terms)
        claim_ids = sorted({ut.claim_number for ut in tw_unsupported_terms})
        claim_count = len(claim_ids)
        tw_spec_paragraph_count = (
            len(tw_doc.technical_field) + len(tw_doc.prior_art) + len(tw_doc.disclosure)
            + len(tw_doc.drawings_description) + len(tw_doc.embodiment)
        )
        claims_checks = list(claims_checks) + [
            CheckItem(
                status="amend",
                message="Possible claim terms not supported by the specification.",
                message_key="check.tw.claims.specSupport.amend",
                details=f"{issue_count} term(s) may lack specification support across {claim_count} claim(s).",
                details_key="details.tw.specSupportTerms",
                details_params={
                    "issue_count": issue_count,
                    "claim_count": claim_count,
                    "claims": claim_ids,
                },
                reference="專利法 §26 第3項",
                diagnostics=extract_spec_support(
                    tw_unsupported_terms,
                    total_claims=len(tw_doc.claims),
                    spec_paragraph_count=tw_spec_paragraph_count,
                ),
            )
        ]
    else:
        claims_checks = list(claims_checks) + [
            CheckItem(
                status="pass",
                message="All claim terms supported by the specification.",
                message_key="check.tw.claims.specSupport.pass",
                reference="專利法 §26 第3項",
            )
        ]

    # --- Abstract checks (27–30) ---
    abstract_checks = (
        tw_abstract_analysis.check_abstract_char_count(tw_doc)
        + tw_abstract_analysis.check_abstract_title_match(tw_doc)
        + tw_abstract_analysis.check_commercial_language(tw_doc)
        + tw_abstract_analysis.check_representative_drawing(tw_doc)
    )

    # --- Cross-reference checks (spec-level G2 tail) ---
    # symbol_vs_rep_drawing is a cross-ref content consistency check (G2);
    # bracket_format moved to its G1 slot above (ADR-149).
    spec_checks = list(spec_checks) + tw_cross_ref_analysis.check_symbol_vs_rep_drawing(tw_doc)

    # --- Drawings checks (33–34) ---
    # Emission order: figure_count → figures_sequential per Phase 10C
    # document-order invariant (see CLAUDE.md "Check-ordering consistency
    # invariant"). Swapped from legacy sequential-then-count order.
    drawings_checks = (
        tw_cross_ref_analysis.check_figure_count(tw_doc)
        + tw_cross_ref_analysis.check_figures_sequential(tw_doc)
    )

    result = AnalysisResult(
        jurisdiction=Jurisdiction.TW,
        patent_type=tw_doc.patent_type.value,
        paragraph_count=para_count,
        claims=tw_doc.claims,
        independent_claims_count=sum(1 for c in tw_doc.claims if c.independent),
        dependent_claims_count=sum(1 for c in tw_doc.claims if not c.independent),
        figures_count=len(tw_doc.figure_refs),
        abstract_word_count=tw_doc.abstract_char_count,
        likely_patent=likely_patent,
        patent_detection_reason=patent_detection_reason,
        has_tracked_changes=has_tracked_changes,
        tw_specification_checks=spec_checks,
        tw_claims_checks=claims_checks,
        tw_abstract_checks=abstract_checks,
        tw_drawings_checks=drawings_checks,
        antecedent_basis_issues=tw_antecedent_basis,
        unsupported_terms=tw_unsupported_terms,
        jurisdiction_mismatch=bool(suggested_jurisdiction),
        suggested_jurisdiction=suggested_jurisdiction,
    )
    _attach_rubric_grade(
        result,
        has_drawings=detect_has_drawings(figures_count=len(tw_doc.figure_refs), figure_refs=list(tw_doc.figure_refs)),
        title=tw_doc.title,
        has_claims=bool(tw_doc.claims),
        has_spec_body=bool(
            "".join(tw_doc.technical_field + tw_doc.prior_art + tw_doc.disclosure + tw_doc.embodiment).strip()
        ),
        has_abstract=bool(tw_doc.abstract_text and tw_doc.abstract_text.strip()),
    )
    return result


def analyze_file(
    file_path: str,
    jurisdiction: Jurisdiction = Jurisdiction.US,
    *,
    tw_strict_plural_reference_matching: bool = False,
    tw_strict_qualifier_matching: bool = False,
    cn_strict_plural_reference_matching: bool = False,
    cn_strict_qualifier_matching: bool = False,
) -> AnalysisResult:
    """Analyze a patent document file."""
    lower = file_path.lower()

    if jurisdiction == Jurisdiction.TW:
        if not lower.endswith(".docx"):
            msg = f"Unsupported file type for TW jurisdiction: {file_path}"
            raise ValueError(msg)
        loaded_tw = load_docx_tw(file_path)
        likely_patent, detection_reason = classify_document_tw(loaded_tw.paragraphs)
        tw_doc = extract_tw_sections(
            loaded_tw.paragraphs,
            loaded_tw.paragraph_word_numbers,
        )
        suggested = detect_jurisdiction_mismatch(
            "\n".join(loaded_tw.paragraphs), Jurisdiction.TW,
        )
        return _run_tw_pipeline(
            tw_doc,
            likely_patent=likely_patent,
            patent_detection_reason=detection_reason.value,
            has_tracked_changes=loaded_tw.has_tracked_changes,
            suggested_jurisdiction=suggested,
            strict_plural_reference_matching=tw_strict_plural_reference_matching,
            strict_qualifier_matching=tw_strict_qualifier_matching,
        )

    if jurisdiction == Jurisdiction.CN:
        if lower.endswith(".xml"):
            with open(file_path, "rb") as f:
                cn_doc = parse_cnipa_xml(f.read())
            return _run_cn_pipeline(
                cn_doc,
                strict_plural_reference_matching=cn_strict_plural_reference_matching,
                strict_qualifier_matching=cn_strict_qualifier_matching,
            )
        if lower.endswith(".zip"):
            with open(file_path, "rb") as f:
                xml_data, _ = extract_cn_xml_from_zip(f.read())
            cn_doc = parse_cnipa_xml(xml_data)
            return _run_cn_pipeline(
                cn_doc,
                strict_plural_reference_matching=cn_strict_plural_reference_matching,
                strict_qualifier_matching=cn_strict_qualifier_matching,
            )
        if lower.endswith(".docx"):
            loaded_cn = load_docx_cn(file_path)
            all_cn_paragraphs = [p for s in loaded_cn.sections for p in s.paragraphs]
            likely_patent, detection_reason = classify_document_cn(all_cn_paragraphs)
            cn_doc = extract_cn_sections_from_docx(loaded_cn.sections)
            suggested = detect_jurisdiction_mismatch(
                "\n".join(all_cn_paragraphs), Jurisdiction.CN,
            )
            return _run_cn_pipeline(
                cn_doc,
                likely_patent=likely_patent,
                patent_detection_reason=detection_reason.value,
                has_tracked_changes=loaded_cn.has_tracked_changes,
                suggested_jurisdiction=suggested,
                strict_plural_reference_matching=cn_strict_plural_reference_matching,
                strict_qualifier_matching=cn_strict_qualifier_matching,
            )
        msg = f"Unsupported file type for CN jurisdiction: {file_path}"
        raise ValueError(msg)

    # US jurisdiction (existing behavior, unchanged)
    loaded = load_docx(file_path)
    suggested = detect_jurisdiction_mismatch(loaded.full_text, Jurisdiction.US)
    return _run_pipeline(
        loaded, loaded.full_text, jurisdiction=jurisdiction, suggested_jurisdiction=suggested,
    )


def analyze_bytes(
    content: bytes,
    filename: str,
    jurisdiction: Jurisdiction = Jurisdiction.US,
    *,
    tw_strict_plural_reference_matching: bool = False,
    tw_strict_qualifier_matching: bool = False,
    cn_strict_plural_reference_matching: bool = False,
    cn_strict_qualifier_matching: bool = False,
) -> AnalysisResult:
    """Analyze patent document from raw bytes."""
    lower = filename.lower()

    if jurisdiction == Jurisdiction.TW:
        if not lower.endswith(".docx"):
            msg = f"Unsupported file type for TW jurisdiction: {filename}"
            raise ValueError(msg)
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
            tmp.write(content)
            tmp.flush()
            loaded_tw = load_docx_tw(tmp.name)
        likely_patent, detection_reason = classify_document_tw(loaded_tw.paragraphs)
        tw_doc = extract_tw_sections(
            loaded_tw.paragraphs,
            loaded_tw.paragraph_word_numbers,
        )
        suggested = detect_jurisdiction_mismatch(
            "\n".join(loaded_tw.paragraphs), Jurisdiction.TW,
        )
        return _run_tw_pipeline(
            tw_doc,
            likely_patent=likely_patent,
            patent_detection_reason=detection_reason.value,
            has_tracked_changes=loaded_tw.has_tracked_changes,
            suggested_jurisdiction=suggested,
            strict_plural_reference_matching=tw_strict_plural_reference_matching,
            strict_qualifier_matching=tw_strict_qualifier_matching,
        )

    if jurisdiction == Jurisdiction.CN:
        if lower.endswith(".zip"):
            xml_data, _ = extract_cn_xml_from_zip(content)
            cn_doc = parse_cnipa_xml(xml_data)
            return _run_cn_pipeline(
                cn_doc,
                strict_plural_reference_matching=cn_strict_plural_reference_matching,
                strict_qualifier_matching=cn_strict_qualifier_matching,
            )
        if lower.endswith(".xml"):
            cn_doc = parse_cnipa_xml(content)
            return _run_cn_pipeline(
                cn_doc,
                strict_plural_reference_matching=cn_strict_plural_reference_matching,
                strict_qualifier_matching=cn_strict_qualifier_matching,
            )
        if lower.endswith(".docx"):
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
                tmp.write(content)
                tmp.flush()
                loaded_cn = load_docx_cn(tmp.name)
            all_cn_paragraphs = [p for s in loaded_cn.sections for p in s.paragraphs]
            likely_patent, detection_reason = classify_document_cn(all_cn_paragraphs)
            cn_doc = extract_cn_sections_from_docx(loaded_cn.sections)
            suggested = detect_jurisdiction_mismatch(
                "\n".join(all_cn_paragraphs), Jurisdiction.CN,
            )
            return _run_cn_pipeline(
                cn_doc,
                likely_patent=likely_patent,
                patent_detection_reason=detection_reason.value,
                has_tracked_changes=loaded_cn.has_tracked_changes,
                suggested_jurisdiction=suggested,
                strict_plural_reference_matching=cn_strict_plural_reference_matching,
                strict_qualifier_matching=cn_strict_qualifier_matching,
            )
        msg = f"Unsupported file type for CN jurisdiction: {filename}"
        raise ValueError(msg)

    # US jurisdiction
    if not lower.endswith(".docx"):
        msg = f"Unsupported file type: {filename}"
        raise ValueError(msg)

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
        tmp.write(content)
        tmp.flush()
        loaded = load_docx(tmp.name)
    suggested = detect_jurisdiction_mismatch(loaded.full_text, Jurisdiction.US)
    return _run_pipeline(
        loaded, loaded.full_text, jurisdiction=jurisdiction, suggested_jurisdiction=suggested,
    )
