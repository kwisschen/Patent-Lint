"""PatentLint FastAPI application.

POST /api/analyze: Upload .docx → full patent analysis → JSON
POST /api/analyze/report: Upload .docx → full analysis → PDF report
GET /api/health: Service health check
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from patentlint.analysis import abstract as abstract_analysis
from patentlint.analysis import claims as claims_analysis
from patentlint.analysis import drawings as drawings_analysis
from patentlint.analysis import specification as spec_analysis
from patentlint.models import AnalysisResult
from patentlint.parser import claims as claims_parser
from patentlint.parser import sections
from patentlint.parser.docx_loader import load_docx
from patentlint.report.generator import render_pdf

logger = logging.getLogger("patentlint")

app = FastAPI(title="PatentLint", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _run_analysis_pipeline(upload_file: UploadFile) -> AnalysisResult:
    """Shared pipeline: validate upload -> save to temp -> load docx -> run analyzers -> return result."""
    if not upload_file.filename or not upload_file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="File must be a .docx document")

    try:
        contents = await upload_file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read uploaded file")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
        tmp.write(contents)
        tmp.flush()
        tmp_path = Path(tmp.name)

        try:
            loaded = load_docx(tmp_path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    full_text = loaded.full_text

    # --- Section extraction ---
    claims_section = sections.extract_claims_section(full_text)
    abstract_section = sections.extract_abstract_section(full_text)
    drawings_section = sections.extract_description_of_drawings_section(full_text)
    cross_ref_section = sections.extract_cross_reference_section(full_text)
    background_section = sections.extract_background_section(full_text)

    # --- Claims analysis ---
    claims = claims_parser.parse_claims(claims_section)

    if claims:
        claim_ids = [c.id for c in claims]
        missing_periods = claims_analysis.find_missing_periods(claims)
        extra_periods = claims_analysis.find_extra_periods(claims)
        multiple_deps = claims_analysis.find_multiple_dependents(claims)
        self_deps = claims_analysis.find_self_dependent_claims(claims)
        claims_seq = claims_analysis.are_claims_sequential(claim_ids)
        last_seq_claim = claims_analysis.get_last_sequential_index(claim_ids)
        wording = claims_parser.detect_improper_claim_wording(claims)
        wherein_issues = claims_parser.detect_incorrect_wherein_commas(claims)
        means_plus_function = claims_analysis.detect_means_plus_function(claims)
        antecedent_basis = claims_analysis.check_antecedent_basis(claims)
        independent_count = claims_analysis.count_independent(claims)
        dependent_count = claims_analysis.count_dependent(claims)
    else:
        claim_ids = []
        missing_periods = []
        extra_periods = []
        multiple_deps = []
        self_deps = []
        claims_seq = True
        last_seq_claim = 0
        wording = claims_parser.detect_improper_claim_wording([])
        wherein_issues = []
        means_plus_function = []
        antecedent_basis = []
        independent_count = 0
        dependent_count = 0

    # --- Drawings analysis ---
    figures_count = drawings_analysis.get_figure_count(drawings_section) if drawings_section else 0
    figures_seq = drawings_analysis.are_figures_sequential(drawings_section) if drawings_section else True
    single_fig = drawings_analysis.is_single_figure(full_text)
    wrong_label = drawings_analysis.uses_wrong_label_for_single_figure(full_text) if single_fig else False
    prior_art_drawings = drawings_analysis.contains_prior_art_references(drawings_section) if drawings_section else False

    # --- Abstract analysis ---
    abstract_word_count = abstract_analysis.count_words(abstract_section)
    abstract_structure = abstract_analysis.is_single_paragraph_and_final(full_text, abstract_section) if abstract_section else True
    abstract_implied = abstract_analysis.has_implied_phrase(abstract_section) if abstract_section else False
    abstract_wording = abstract_analysis.detect_improper_wording(abstract_section) if abstract_section else ""

    # --- Specification analysis ---
    para_nums = loaded.paragraph_numberings
    para_seq = spec_analysis.are_paragraphs_sequential(para_nums)
    last_seq_para = spec_analysis.get_last_sequential_index(para_nums)
    seq_listing = spec_analysis.has_sequence_listing_mismatch(full_text)

    # Prior art citations from cross-reference and background
    cross_ref_citations = sections.detect_prior_art_citations(cross_ref_section) if cross_ref_section else ""
    prior_art_citations = sections.detect_prior_art_citations(background_section) if background_section else ""

    return AnalysisResult(
        # Specification
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
        missing_period_claims=missing_periods,
        extra_periods_claims=extra_periods,
        multiple_dependent_claims=multiple_deps,
        self_dependent_claims=self_deps,
        incorrect_wherein_comma_claims=wherein_issues,
        means_plus_function_claims=means_plus_function,
        antecedent_basis_issues=antecedent_basis,
        # Abstract
        abstract_word_count=abstract_word_count,
        abstract_structure_good=abstract_structure,
        abstract_has_implied_phrase=abstract_implied,
        improper_abstract_phrases_formatted=abstract_wording,
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), format: str = "raw"):
    """Analyze a patent .docx file and return structured results.

    Query params:
        format: "raw" (default) returns AnalysisResult, "report" returns ReportData.
    """
    result = await _run_analysis_pipeline(file)
    if format == "report":
        return result.to_report_data().model_dump()
    return result.model_dump()


@app.post("/api/analyze/report")
async def analyze_report(file: UploadFile = File(...)):
    """Upload .docx -> full analysis -> PDF report download."""
    result = await _run_analysis_pipeline(file)
    pdf_bytes = render_pdf(result)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=patentlint-report.pdf"},
    )


# --- Static file serving for production (frontend/dist) ---
_frontend_dist = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "frontend", "dist"
)
_frontend_dist = os.path.normpath(_frontend_dist)

if os.path.isdir(_frontend_dist):

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Serve the React SPA. Static files if they exist, else index.html."""
        file_path = os.path.join(_frontend_dist, path)
        if path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(_frontend_dist, "index.html"))
