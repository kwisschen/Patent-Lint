# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""PatentLint FastAPI application.

POST /api/analyze: Upload .docx → full patent analysis → JSON
POST /api/analyze/report: Upload .docx → full analysis → PDF report
GET /api/health: Service health check
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from patentlint.i18n import normalize_locale
from patentlint.models import AnalysisResult, Jurisdiction
from patentlint.pipeline import analyze_bytes
from patentlint.report.generator import render_pdf

logger = logging.getLogger("patentlint")

app = FastAPI(title="PatentLint", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _run_analysis_pipeline(
    upload_file: UploadFile,
    jurisdiction: Jurisdiction = Jurisdiction.US,
) -> AnalysisResult:
    """Validate upload, read bytes, delegate to pipeline.analyze_bytes()."""
    if jurisdiction == Jurisdiction.CN:
        valid_extensions = (".docx", ".xml", ".zip")
    else:
        valid_extensions = (".docx",)  # US and TW both accept .docx only
    if not upload_file.filename or not upload_file.filename.lower().endswith(valid_extensions):
        exts = ", ".join(valid_extensions)
        raise HTTPException(
            status_code=400,
            detail=f"File must be {exts} for {jurisdiction.value} jurisdiction",
        )

    try:
        contents = await upload_file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read uploaded file")

    try:
        return analyze_bytes(contents, upload_file.filename, jurisdiction=jurisdiction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    format: str = "raw",
    jurisdiction: str = "us",
):
    """Analyze a patent .docx file and return structured results.

    Query params:
        format: "raw" (default) returns AnalysisResult, "report" returns ReportData.
        jurisdiction: "us" (default) or "cn".
    """
    j = Jurisdiction(jurisdiction.upper())
    result = await _run_analysis_pipeline(file, jurisdiction=j)
    if format == "report":
        return result.to_report_data().model_dump()
    return result.model_dump()


def _pick_locale(query_locale: str | None, accept_language: str | None) -> str:
    """Resolve the PDF output locale.

    Precedence: explicit ``?locale=`` query param > first Accept-Language
    tag > default ``en``. BCP-47 normalization collapses regional
    variants (zh-Hant-TW → zh-TW, en-US → en) so the caller can pass
    browser-grade language tags through unchanged.
    """
    if query_locale:
        return normalize_locale(query_locale)
    if accept_language:
        # Take the first tag; RFC 7231 permits quality-weighted lists
        # but we don't need best-match scoring for a 5-locale set.
        first_tag = accept_language.split(",")[0].split(";")[0].strip()
        return normalize_locale(first_tag)
    return "en"


@app.post("/api/analyze/report")
async def analyze_report(
    file: UploadFile = File(...),
    jurisdiction: str = "us",
    locale: str | None = None,
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
):
    """Upload .docx -> full analysis -> PDF report download.

    Locale resolution (precedence): ?locale=... > Accept-Language > en.
    """
    j = Jurisdiction(jurisdiction.upper())
    result = await _run_analysis_pipeline(file, jurisdiction=j)
    resolved_locale = _pick_locale(locale, accept_language)
    pdf_bytes = render_pdf(result, locale=resolved_locale)
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
