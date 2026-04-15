# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for CN pipeline routing in analyze_bytes / analyze_file."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from patentlint.models import Jurisdiction
from patentlint.pipeline import analyze_bytes

FIXTURES = Path(__file__).parent / "fixtures" / "cn"


class TestCnXmlAnalyzeBytes:
    def test_cn_xml_analyze_bytes(self):
        data = (FIXTURES / "cn_minimal_pass.xml").read_bytes()
        result = analyze_bytes(data, "test.xml", jurisdiction=Jurisdiction.CN)
        assert result.jurisdiction == Jurisdiction.CN
        assert result.paragraph_count == 5
        assert len(result.claims) == 2
        assert result.independent_claims_count == 1
        assert result.dependent_claims_count == 1
        assert result.figures_count == 1

    def test_cn_checks_populated(self):
        """All 24 CN checks should produce at least one CheckItem each."""
        data = (FIXTURES / "cn_minimal_pass.xml").read_bytes()
        result = analyze_bytes(data, "test.xml", jurisdiction=Jurisdiction.CN)
        # 8 spec + 12 claims + 3 abstract + 1 drawings = 24 minimum
        total = (
            len(result.cn_specification_checks)
            + len(result.cn_claims_checks)
            + len(result.cn_abstract_checks)
            + len(result.cn_drawings_checks)
        )
        assert total >= 24
        assert len(result.cn_specification_checks) >= 8
        assert len(result.cn_claims_checks) >= 12
        assert len(result.cn_abstract_checks) >= 3
        assert len(result.cn_drawings_checks) >= 1

    def test_cn_report_data(self):
        """to_report_data() should route CN results correctly."""
        data = (FIXTURES / "cn_minimal_pass.xml").read_bytes()
        result = analyze_bytes(data, "test.xml", jurisdiction=Jurisdiction.CN)
        report = result.to_report_data()
        assert report.jurisdiction == Jurisdiction.CN
        assert len(report.specification_checks) >= 8
        assert len(report.claims_checks) >= 12
        assert len(report.abstract_checks) >= 3
        assert len(report.drawings_checks) >= 1


class TestCnXmlDocPage:
    def test_cn_xml_doc_page(self):
        data = (FIXTURES / "cn_doc_page.xml").read_bytes()
        result = analyze_bytes(data, "test.xml", jurisdiction=Jurisdiction.CN)
        assert result.jurisdiction == Jurisdiction.CN
        assert result.paragraph_count == 0
        assert len(result.claims) == 0


class TestCnZipAnalyzeBytes:
    def test_cn_zip_analyze_bytes(self):
        xml_data = (FIXTURES / "cn_minimal_pass.xml").read_bytes()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("patent.xml", xml_data)
        zip_data = buf.getvalue()
        result = analyze_bytes(zip_data, "converter_output.zip", jurisdiction=Jurisdiction.CN)
        assert result.jurisdiction == Jurisdiction.CN
        assert len(result.claims) == 2


class TestCnUnsupportedFiletype:
    def test_cn_unsupported_filetype(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            analyze_bytes(b"data", "test.pdf", jurisdiction=Jurisdiction.CN)


class TestUsUnchanged:
    def test_us_unchanged(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            analyze_bytes(b"data", "test.txt", jurisdiction=Jurisdiction.US)


class TestUsDefaultJurisdiction:
    def test_us_default_jurisdiction(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            analyze_bytes(b"data", "test.txt")
