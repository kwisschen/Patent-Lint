# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
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
from patentlint.analysis import cn_specification as cn_spec_analysis
from patentlint.analysis import drawings as drawings_analysis
from patentlint.analysis import specification as spec_analysis
from patentlint.analysis import tw_abstract as tw_abstract_analysis
from patentlint.analysis import tw_claims as tw_claims_analysis
from patentlint.analysis import tw_cross_reference as tw_cross_ref_analysis
from patentlint.analysis import tw_specification as tw_spec_analysis
from patentlint.models import AnalysisResult, CheckItem, CnPatentDocument, Jurisdiction, TwPatentDocument
from patentlint.parser import claims as claims_parser
from patentlint.parser import sections
from patentlint.parser.docx_loader import load_docx, load_docx_cn, load_docx_tw
from patentlint.parser.sections_cn import detect_patent_document_cn, extract_cn_sections_from_docx
from patentlint.parser.sections_tw import detect_patent_document_tw, extract_tw_sections
from patentlint.parser.xml_loader import extract_cn_xml_from_zip, parse_cnipa_xml


# TODO Phase 7: Add language mismatch detection (English content in CN mode, Chinese content in US mode)


def _run_cn_pipeline(
    cn_doc: CnPatentDocument,
    *,
    likely_patent: bool = True,
    has_tracked_changes: bool = False,
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

    # --- Specification checks (1–8) ---
    spec_checks = (
        cn_spec_analysis.check_required_sections(cn_doc)
        + cn_spec_analysis.check_section_ordering(cn_doc)
        + cn_spec_analysis.check_paragraph_numbering(cn_doc)
        + cn_spec_analysis.check_paragraph_ending(cn_doc)
        + cn_spec_analysis.check_figure_reference_consistency(cn_doc)
        + cn_spec_analysis.check_patent_type_terminology(cn_doc)
        + cn_spec_analysis.check_title(cn_doc)
        + cn_spec_analysis.check_spec_claim_reference(cn_doc)
    )

    # --- Claims checks (9–20) ---
    claims_checks = (
        cn_claims_analysis.check_claims_sequential(cn_doc)
        + cn_claims_analysis.check_dependency_format(cn_doc)
        + cn_claims_analysis.check_self_dependent(cn_doc)
        + cn_claims_analysis.check_forward_dependency(cn_doc)
        + cn_claims_analysis.check_single_sentence(cn_doc)
        + cn_claims_analysis.check_reference_numeral_parentheses(cn_doc)
        + cn_claims_analysis.check_subject_name_consistency(cn_doc)
        + cn_claims_analysis.check_transition_phrase(cn_doc)
        + cn_claims_analysis.check_tw_terminology(cn_doc)
        + cn_claims_analysis.check_claims_spec_reference(cn_doc)
        + cn_claims_analysis.check_multi_multi_dependency(cn_doc)
        + cn_claims_analysis.check_dependent_ordering(cn_doc)
    )

    # Phase 8c: CN antecedent walker (parallel to TW). Emits structured
    # per-occurrence findings; the CheckItem summary tile aggregates.
    cn_antecedent_basis = cn_claims_analysis.check_antecedent_basis_cn(
        cn_doc,
        strict_plural_reference_matching=strict_plural_reference_matching,
        strict_qualifier_matching=strict_qualifier_matching,
    )
    if cn_antecedent_basis:
        issue_count = len(cn_antecedent_basis)
        claim_ids = sorted({item["claim_id"] for item in cn_antecedent_basis})
        claim_count = len(claim_ids)
        claims_checks = list(claims_checks) + [
            CheckItem(
                status="verify",
                message="Possible missing antecedent basis found.",
                message_key="check.cn.claims.antecedentBasis.verify",
                details=f"{issue_count} term(s) may lack antecedent basis across {claim_count} claim(s).",
                details_key="details.cn.antecedentBasisTerms",
                details_params={
                    "issue_count": issue_count,
                    "claim_count": claim_count,
                    "claims": claim_ids,
                },
                reference="审查指南",
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

    # --- Abstract checks (21–23) ---
    abstract_checks = (
        cn_abstract_analysis.check_abstract_char_count(cn_doc)
        + cn_abstract_analysis.check_abstract_title_match(cn_doc)
        + cn_abstract_analysis.check_commercial_language(cn_doc)
    )

    # --- Drawings checks (24–25) ---
    drawings_checks = (
        cn_abstract_analysis.check_figures_sequential(cn_doc)
        + cn_abstract_analysis.check_figure_count(cn_doc)
    )

    return AnalysisResult(
        jurisdiction=Jurisdiction.CN,
        patent_type=cn_doc.patent_type.value,
        paragraph_count=para_count,
        claims=cn_doc.claims,
        independent_claims_count=sum(1 for c in cn_doc.claims if c.independent),
        dependent_claims_count=sum(1 for c in cn_doc.claims if not c.independent),
        figures_count=cn_doc.figure_count,
        abstract_word_count=cn_doc.abstract_char_count,
        likely_patent=likely_patent,
        has_tracked_changes=has_tracked_changes,
        has_scanned_fallback=cn_doc.has_doc_page_fallback,
        cn_specification_checks=spec_checks,
        cn_claims_checks=claims_checks,
        cn_abstract_checks=abstract_checks,
        cn_drawings_checks=drawings_checks,
        antecedent_basis_issues=cn_antecedent_basis,
    )


def _run_pipeline(loaded, full_text: str, *, jurisdiction: Jurisdiction = Jurisdiction.US) -> AnalysisResult:
    """Core pipeline logic shared by analyze_file and analyze_bytes."""

    # --- Document type detection ---
    likely_patent = sections.detect_patent_document(full_text)

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
        self_deps = claims_analysis.find_self_dependent_claims(claims)
        claims_seq = claims_analysis.are_claims_sequential(claim_ids)
        last_seq_claim = claims_analysis.get_last_sequential_index(claim_ids)
        wording = claims_parser.detect_improper_claim_wording(claims)
        means_plus_function = claims_analysis.detect_means_plus_function(claims)
        antecedent_basis = claims_analysis.check_antecedent_basis(claims)
        preamble_checks = claims_analysis.check_preamble_consistency(claims)
        transition_checks = claims_analysis.check_claim_transitions(claims)
        special_format_checks = claims_analysis.check_special_claim_formats(claims)
        spec_text = (summary_section or "") + "\n" + (detailed_desc_section or "")
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
        self_deps = []
        claims_seq = True
        last_seq_claim = 0
        wording = claims_parser.detect_improper_claim_wording([])
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
    single_fig = drawings_analysis.is_single_figure(full_text)
    wrong_label = drawings_analysis.uses_wrong_label_for_single_figure(full_text) if single_fig else False
    prior_art_drawings = drawings_analysis.contains_prior_art_references(drawings_section) if drawings_section else False

    # --- Reference numeral inventory ---
    ref_spec_text = (detailed_desc_section or "") + "\n" + (summary_section or "") + "\n" + (drawings_section or "")
    ref_numerals = spec_analysis.extract_reference_numeral_inventory(ref_spec_text) if ref_spec_text.strip() else []

    # --- Abstract analysis ---
    abstract_word_count = abstract_analysis.count_words(abstract_section)
    abstract_structure = abstract_analysis.is_single_paragraph_and_final(full_text, abstract_section) if abstract_section else True
    abstract_implied = abstract_analysis.has_implied_phrase(abstract_section) if abstract_section else False
    abstract_wording = abstract_analysis.detect_improper_wording(abstract_section) if abstract_section else ""

    # --- Required sections check ---
    required_sections_checks = spec_analysis.check_required_sections(full_text)

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

    return AnalysisResult(
        jurisdiction=jurisdiction,
        # Document-level flag
        likely_patent=likely_patent,
        # Specification
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
        contains_prior_art_in_drawings=prior_art_drawings,
        single_figure=single_fig,
        wrong_label_for_single_figure=wrong_label,
        # Claims
        claims=claims,
        improper_claims=wording.improper_claims,
        improper_claim_phrases_formatted=wording.formatted_phrases,
        independent_claims_count=independent_count,
        dependent_claims_count=dependent_count,
        claims_sequential=claims_seq,
        last_sequential_claim=last_seq_claim,
        punctuation_checks=punctuation_checks,
        multiple_dependent_claims=multiple_deps,
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
        # Abstract
        abstract_word_count=abstract_word_count,
        abstract_structure_good=abstract_structure,
        abstract_has_implied_phrase=abstract_implied,
        improper_abstract_phrases_formatted=abstract_wording,
    )


def _run_tw_pipeline(
    tw_doc: TwPatentDocument,
    *,
    likely_patent: bool = True,
    has_tracked_changes: bool = False,
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

    # --- Specification checks (1–10) ---
    spec_checks = (
        tw_spec_analysis.check_required_sections(tw_doc)
        + tw_spec_analysis.check_section_ordering(tw_doc)
        + tw_spec_analysis.check_paragraph_numbering(tw_doc)
        + tw_spec_analysis.check_paragraph_ending(tw_doc)
        + tw_spec_analysis.check_figure_ref_consistency(tw_doc)
        + tw_spec_analysis.check_patent_type_terminology(tw_doc)
        + tw_spec_analysis.check_title(tw_doc)
        + tw_spec_analysis.check_spec_claim_reference(tw_doc)
        + tw_spec_analysis.check_symbol_table_presence(tw_doc)
        + tw_spec_analysis.check_symbol_table_consistency(tw_doc)
    )

    # --- Claims checks (11–26) ---
    claims_checks = (
        tw_claims_analysis.check_claims_sequential(tw_doc)
        + tw_claims_analysis.check_dependency_format(tw_doc)
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
    if tw_antecedent_basis:
        issue_count = len(tw_antecedent_basis)
        claim_ids = sorted({item["claim_id"] for item in tw_antecedent_basis})
        claim_count = len(claim_ids)
        claims_checks = list(claims_checks) + [
            CheckItem(
                status="verify",
                message="Possible missing antecedent basis found.",
                message_key="check.tw.claims.antecedentBasis.verify",
                details=f"{issue_count} term(s) may lack antecedent basis across {claim_count} claim(s).",
                details_key="details.tw.antecedentBasisTerms",
                details_params={
                    "issue_count": issue_count,
                    "claim_count": claim_count,
                    "claims": claim_ids,
                },
                reference="專利審查基準",
            )
        ]
    else:
        claims_checks = list(claims_checks) + [
            CheckItem(
                status="pass",
                message="All referenced terms have antecedent basis.",
                message_key="check.tw.claims.antecedentBasis.pass",
                reference="專利審查基準",
            )
        ]

    # --- Abstract checks (27–30) ---
    abstract_checks = (
        tw_abstract_analysis.check_abstract_char_count(tw_doc)
        + tw_abstract_analysis.check_abstract_title_match(tw_doc)
        + tw_abstract_analysis.check_commercial_language(tw_doc)
        + tw_abstract_analysis.check_representative_drawing(tw_doc)
    )

    # --- Cross-reference checks (31–32) → spec-level ---
    spec_checks = list(spec_checks) + (
        tw_cross_ref_analysis.check_symbol_vs_rep_drawing(tw_doc)
        + tw_cross_ref_analysis.check_bracket_format(tw_doc)
    )

    # --- Drawings checks (33–34) ---
    drawings_checks = (
        tw_cross_ref_analysis.check_figures_sequential(tw_doc)
        + tw_cross_ref_analysis.check_figure_count(tw_doc)
    )

    return AnalysisResult(
        jurisdiction=Jurisdiction.TW,
        patent_type=tw_doc.patent_type.value,
        paragraph_count=para_count,
        claims=tw_doc.claims,
        independent_claims_count=sum(1 for c in tw_doc.claims if c.independent),
        dependent_claims_count=sum(1 for c in tw_doc.claims if not c.independent),
        figures_count=len(tw_doc.figure_refs),
        abstract_word_count=tw_doc.abstract_char_count,
        likely_patent=likely_patent,
        has_tracked_changes=has_tracked_changes,
        tw_specification_checks=spec_checks,
        tw_claims_checks=claims_checks,
        tw_abstract_checks=abstract_checks,
        tw_drawings_checks=drawings_checks,
        antecedent_basis_issues=tw_antecedent_basis,
    )


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
        likely_patent = detect_patent_document_tw(loaded_tw.paragraphs)
        tw_doc = extract_tw_sections(
            loaded_tw.paragraphs,
            loaded_tw.paragraph_word_numbers,
        )
        return _run_tw_pipeline(
            tw_doc,
            likely_patent=likely_patent,
            has_tracked_changes=loaded_tw.has_tracked_changes,
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
            likely_patent = detect_patent_document_cn(all_cn_paragraphs)
            cn_doc = extract_cn_sections_from_docx(loaded_cn.sections)
            return _run_cn_pipeline(
                cn_doc,
                likely_patent=likely_patent,
                has_tracked_changes=loaded_cn.has_tracked_changes,
                strict_plural_reference_matching=cn_strict_plural_reference_matching,
                strict_qualifier_matching=cn_strict_qualifier_matching,
            )
        msg = f"Unsupported file type for CN jurisdiction: {file_path}"
        raise ValueError(msg)

    # US jurisdiction (existing behavior, unchanged)
    loaded = load_docx(file_path)
    return _run_pipeline(loaded, loaded.full_text, jurisdiction=jurisdiction)


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
        likely_patent = detect_patent_document_tw(loaded_tw.paragraphs)
        tw_doc = extract_tw_sections(
            loaded_tw.paragraphs,
            loaded_tw.paragraph_word_numbers,
        )
        return _run_tw_pipeline(
            tw_doc,
            likely_patent=likely_patent,
            has_tracked_changes=loaded_tw.has_tracked_changes,
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
            likely_patent = detect_patent_document_cn(all_cn_paragraphs)
            cn_doc = extract_cn_sections_from_docx(loaded_cn.sections)
            return _run_cn_pipeline(
                cn_doc,
                likely_patent=likely_patent,
                has_tracked_changes=loaded_cn.has_tracked_changes,
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
    return _run_pipeline(loaded, loaded.full_text, jurisdiction=jurisdiction)
