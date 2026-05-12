# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Tests for Phase 7A: TW jurisdiction foundation (enum, model, pipeline, CLI)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from unittest.mock import patch

from patentlint.cli import main
from patentlint.models import (
    AnalysisResult,
    Jurisdiction,
    SymbolEntry,
    TwPatentDocument,
    TwPatentType,
)
from patentlint.pipeline import analyze_bytes


class TestJurisdictionEnum:
    def test_tw_enum_exists(self):
        assert Jurisdiction.TW == "TW"
        assert Jurisdiction.TW.value == "TW"

    def test_tw_enum_from_string(self):
        assert Jurisdiction("TW") == Jurisdiction.TW

    def test_all_jurisdictions(self):
        assert set(Jurisdiction) == {
            Jurisdiction.US,
            Jurisdiction.CN,
            Jurisdiction.TW,
            Jurisdiction.EPC,
        }


class TestTwPatentType:
    def test_invention(self):
        assert TwPatentType.INVENTION == "INVENTION"

    def test_utility_model(self):
        assert TwPatentType.UTILITY_MODEL == "UTILITY_MODEL"


class TestSymbolEntry:
    def test_basic(self):
        entry = SymbolEntry(numeral="100", name="base plate")
        assert entry.numeral == "100"
        assert entry.name == "base plate"


class TestTwPatentDocument:
    def test_default_instantiation(self):
        doc = TwPatentDocument()
        assert doc.patent_type == TwPatentType.INVENTION
        assert doc.title == ""
        assert doc.technical_field == []
        assert doc.prior_art == []
        assert doc.disclosure == []
        assert doc.drawings_description == []
        assert doc.embodiment == []
        assert doc.symbol_table == []
        assert doc.claims == []
        assert doc.abstract_text == ""
        assert doc.abstract_char_count == 0
        assert doc.representative_drawing is None
        assert doc.representative_drawing_symbols == []
        assert doc.figure_refs == []
        assert doc.paragraph_numbers == []
        assert doc.has_paragraph_numbering is False
        assert doc.input_format == "docx"

    def test_with_symbol_table(self):
        doc = TwPatentDocument(
            symbol_table=[SymbolEntry(numeral="10", name="框架")],
        )
        assert len(doc.symbol_table) == 1
        assert doc.symbol_table[0].name == "框架"

    def test_utility_model_type(self):
        doc = TwPatentDocument(patent_type=TwPatentType.UTILITY_MODEL)
        assert doc.patent_type == TwPatentType.UTILITY_MODEL


FIXTURES = Path(__file__).parent / "fixtures" / "tw"


class TestTwPipelineRouting:
    def test_tw_analyze_bytes_returns_tw_jurisdiction(self):
        data = (FIXTURES / "invention_complete.docx").read_bytes()
        result = analyze_bytes(data, "test.docx", jurisdiction=Jurisdiction.TW)
        assert result.jurisdiction == Jurisdiction.TW
        assert result.likely_patent is True

    def test_tw_unsupported_file_type(self):
        with pytest.raises(ValueError, match="Unsupported file type for TW"):
            analyze_bytes(b"<xml/>", "test.xml", jurisdiction=Jurisdiction.TW)

    def test_tw_zip_rejected(self):
        with pytest.raises(ValueError, match="Unsupported file type for TW"):
            analyze_bytes(b"PK", "test.zip", jurisdiction=Jurisdiction.TW)

    def test_tw_report_data(self):
        data = (FIXTURES / "invention_complete.docx").read_bytes()
        result = analyze_bytes(data, "test.docx", jurisdiction=Jurisdiction.TW)
        report = result.to_report_data()
        assert report.jurisdiction == Jurisdiction.TW
        # 10 spec checks + 2 cross-ref checks + indigenousTerms (TIPO #19)
        # + numeralConsistency D1 + symbolTableCoverage D3 = 15
        assert len(report.specification_checks) == 15
        # 18 claims checks + independentPreamble (TIPO #20 indep-half) +
        # excessClaims (fee threshold) = 20
        assert len(report.claims_checks) == 20
        # 4 abstract checks wired in Phase 7C-4
        assert len(report.abstract_checks) == 4
        # 2 drawings checks (figures sequential + figure count)
        assert len(report.drawings_checks) == 2


class TestTwCli:
    def test_cli_accepts_tw_jurisdiction(self, tmp_path):
        docx_file = tmp_path / "test.docx"
        docx_file.touch()

        runner = CliRunner()
        result_obj = AnalysisResult(jurisdiction=Jurisdiction.TW)
        with patch("patentlint.cli.analyze_file", return_value=result_obj):
            result = runner.invoke(main, [
                "analyze", str(docx_file), "--jurisdiction", "tw",
            ])

        assert result.exit_code == 0
