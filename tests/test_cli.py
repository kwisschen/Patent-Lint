"""Tests for patentlint CLI."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from patentlint.cli import main
from patentlint.models import AnalysisResult


def _mock_result():
    """Create a minimal AnalysisResult for testing."""
    return AnalysisResult(
        paragraph_count=10,
        independent_claims_count=1,
        dependent_claims_count=1,
        figures_count=2,
        abstract_word_count=80,
    )


class TestAnalyzeCommand:
    def test_json_to_stdout(self, tmp_path):
        """analyze <file> outputs JSON to stdout."""
        docx_file = tmp_path / "test.docx"
        docx_file.touch()

        runner = CliRunner()
        with patch("patentlint.cli.analyze_file", return_value=_mock_result()):
            result = runner.invoke(main, ["analyze", str(docx_file)])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["paragraph_count"] == 10

    def test_json_to_file(self, tmp_path):
        """analyze <file> -o <path> writes JSON to file."""
        docx_file = tmp_path / "test.docx"
        docx_file.touch()
        out_file = tmp_path / "result.json"

        runner = CliRunner()
        with patch("patentlint.cli.analyze_file", return_value=_mock_result()):
            result = runner.invoke(main, ["analyze", str(docx_file), "-o", str(out_file)])

        assert result.exit_code == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["paragraph_count"] == 10

    def test_pdf_requires_output(self, tmp_path):
        """analyze --format pdf without -o should fail."""
        docx_file = tmp_path / "test.docx"
        docx_file.touch()

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(docx_file), "--format", "pdf"])
        assert result.exit_code == 2

    def test_missing_file(self):
        """analyze <nonexistent> should fail."""
        runner = CliRunner()
        result = runner.invoke(main, ["analyze", "/nonexistent/file.docx"])
        assert result.exit_code != 0

    def test_exit_code_findings(self, tmp_path):
        """Exit code 1 when findings exist."""
        docx_file = tmp_path / "test.docx"
        docx_file.touch()

        mock_result = _mock_result()
        mock_result.missing_period_claims = [1]  # This creates an AMEND finding

        runner = CliRunner()
        with patch("patentlint.cli.analyze_file", return_value=mock_result):
            result = runner.invoke(main, ["analyze", str(docx_file)])

        assert result.exit_code == 1

    def test_exit_code_clean(self, tmp_path):
        """Exit code 0 when no findings."""
        docx_file = tmp_path / "test.docx"
        docx_file.touch()

        # Clean result — all checks should pass
        mock_result = _mock_result()
        mock_result.abstract_word_count = 80
        mock_result.paragraphs_sequential = True
        mock_result.claims_sequential = True
        mock_result.figures_sequential = True

        runner = CliRunner()
        with patch("patentlint.cli.analyze_file", return_value=mock_result):
            result = runner.invoke(main, ["analyze", str(docx_file)])

        assert result.exit_code == 0


class TestBatchCommand:
    def test_batch_json(self, tmp_path):
        """batch <dir> --output <dir> processes all .docx files."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "a.docx").touch()
        (input_dir / "b.docx").touch()
        output_dir = tmp_path / "output"

        runner = CliRunner()
        with patch("patentlint.cli.analyze_file", return_value=_mock_result()):
            result = runner.invoke(main, ["batch", str(input_dir), "--output", str(output_dir)])

        assert result.exit_code == 0
        assert (output_dir / "a.json").exists()
        assert (output_dir / "b.json").exists()

    def test_batch_no_docx(self, tmp_path):
        """batch with no .docx files should fail."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        output_dir = tmp_path / "output"

        runner = CliRunner()
        result = runner.invoke(main, ["batch", str(empty_dir), "--output", str(output_dir)])
        assert result.exit_code == 2

    def test_batch_error_handling(self, tmp_path):
        """batch continues on error, exits with code 2."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "good.docx").touch()
        (input_dir / "bad.docx").touch()
        output_dir = tmp_path / "output"

        def mock_analyze(path):
            if "bad" in str(path):
                raise ValueError("Bad file")
            return _mock_result()

        runner = CliRunner()
        with patch("patentlint.cli.analyze_file", side_effect=mock_analyze):
            result = runner.invoke(main, ["batch", str(input_dir), "--output", str(output_dir)])

        assert result.exit_code == 2


class TestVersionFlag:
    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert "1.0.0" in result.output
        assert result.exit_code == 0
