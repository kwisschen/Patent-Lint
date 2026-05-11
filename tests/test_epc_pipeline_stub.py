# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Scaffolding-stage assertions for the EPC pipeline.

These tests do NOT exercise any real EPC check logic. They lock in that the
EPC routing path through ``analyze_bytes`` works end-to-end without crashing,
and that the empty-stub pipeline returns a well-formed ``AnalysisResult`` /
``ReportData`` pair so the frontend can render an EPC analysis page (empty
sections, no findings) the moment the picker offers EPC.

When real EPC checks ship per the implementation plan, these tests stay as
the regression gate — every G-group commit should leave them passing.
"""

from __future__ import annotations

import io

import pytest
from docx import Document

from patentlint.models import AnalysisResult, Jurisdiction, ReportData
from patentlint.pipeline import _run_epc_pipeline, analyze_bytes


def _make_minimal_docx_bytes() -> bytes:
    """Build a one-paragraph English .docx in memory."""
    doc = Document()
    doc.add_paragraph("Example title")
    doc.add_paragraph("This is a placeholder English paragraph for EPC pipeline scaffolding tests.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_run_epc_pipeline_stub_returns_well_formed_result():
    """Pipeline runs G1 spec-structure checks (5 emissions). G2-G7 are still
    pending so their respective check lists stay empty."""
    result = _run_epc_pipeline("any english text", suggested_jurisdiction=None)
    assert isinstance(result, AnalysisResult)
    assert result.jurisdiction == Jurisdiction.EPC
    # G1 spec-structure checks emit 5 CheckItems (mix of amend/verify/pass
    # depending on the input). Empty text triggers amends for missing
    # title + sections.
    assert len(result.epc_specification_checks) == 5
    assert result.epc_claims_checks == []
    assert result.epc_abstract_checks == []
    assert result.epc_drawings_checks == []


def test_analyze_bytes_routes_epc_jurisdiction_without_crashing():
    content = _make_minimal_docx_bytes()
    result = analyze_bytes(content, "epc_sample.docx", jurisdiction=Jurisdiction.EPC)
    assert isinstance(result, AnalysisResult)
    assert result.jurisdiction == Jurisdiction.EPC


def test_analyze_bytes_rejects_non_docx_for_epc():
    with pytest.raises(ValueError, match="Unsupported file type for EPC"):
        analyze_bytes(b"", "epc_sample.xml", jurisdiction=Jurisdiction.EPC)


def test_epc_report_data_adapter_round_trips():
    result = _run_epc_pipeline("any english text")
    report = result.to_report_data()
    assert isinstance(report, ReportData)
    assert report.jurisdiction == Jurisdiction.EPC
    # G1 ships 5 spec-structure checks; G2-G7 still pending so other lists
    # remain empty at this stage of the implementation plan.
    assert len(report.specification_checks) == 5
    assert report.claims_checks == []
    assert report.abstract_checks == []
    assert report.drawings_checks == []
