# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""PatentLint FastAPI application.

POST /api/analyze: Upload .docx → full patent analysis → JSON
POST /api/analyze/report: Upload .docx → full analysis → PDF report
GET /api/health: Service health check
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from patentlint.models import AnalysisResult
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


async def _run_analysis_pipeline(upload_file: UploadFile) -> AnalysisResult:
    """Validate upload, read bytes, delegate to pipeline.analyze_bytes()."""
    if not upload_file.filename or not upload_file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="File must be a .docx document")

    try:
        contents = await upload_file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read uploaded file")

    try:
        return analyze_bytes(contents, upload_file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


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
