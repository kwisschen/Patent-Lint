# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""PatentLint analysis pipeline — zero web-framework dependencies.

Entry points for CLI and API. This module is also what Pyodide calls in the browser.
"""

from __future__ import annotations

import tempfile

from patentlint.analysis import abstract as abstract_analysis
from patentlint.analysis import claims as claims_analysis
from patentlint.analysis import drawings as drawings_analysis
from patentlint.analysis import specification as spec_analysis
from patentlint.models import AnalysisResult, Jurisdiction
from patentlint.parser import claims as claims_parser
from patentlint.parser import sections
from patentlint.parser.docx_loader import load_docx


def _run_pipeline(loaded, full_text: str, *, jurisdiction: Jurisdiction = Jurisdiction.US) -> AnalysisResult:
    """Core pipeline logic shared by analyze_file and analyze_bytes."""

    if jurisdiction == Jurisdiction.CN:
        raise NotImplementedError("CN analysis checks not yet implemented")

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
        unsupported_terms = claims_analysis.check_spec_support(
            claims, spec_text, antecedent_flagged=antecedent_basis,
        )
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


def analyze_file(file_path: str, jurisdiction: Jurisdiction = Jurisdiction.US) -> AnalysisResult:
    """Run the full analysis pipeline on a .docx file path."""
    loaded = load_docx(file_path)
    return _run_pipeline(loaded, loaded.full_text, jurisdiction=jurisdiction)


def analyze_bytes(content: bytes, filename: str, jurisdiction: Jurisdiction = Jurisdiction.US) -> AnalysisResult:
    """Run the full analysis pipeline on in-memory bytes."""
    if jurisdiction == Jurisdiction.CN:
        if filename.endswith(".xml") or filename.endswith(".zip"):
            raise NotImplementedError("CN XML/ZIP parsing not yet implemented")
        # CN .docx falls through to load_docx, then routes in _run_pipeline

    if not filename.endswith(".docx"):
        msg = f"Unsupported file type: {filename}"
        raise ValueError(msg)

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
        tmp.write(content)
        tmp.flush()
        loaded = load_docx(tmp.name)

    return _run_pipeline(loaded, loaded.full_text, jurisdiction=jurisdiction)
