# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Unit tests for patentlint.models."""

from patentlint.models import AnalysisResult, CheckItem, Jurisdiction, ReportData


class TestReportDataAllChecks:
    """Tests for ReportData.all_checks consolidated accessor."""

    def _make_check(self, check_id: str) -> CheckItem:
        return CheckItem(
            status="pass",
            message=check_id,
            message_key=f"check.{check_id}",
        )

    def test_empty_returns_empty(self):
        report = ReportData(
            paragraph_count=0, total_claims=0, independent_count=0,
            dependent_count=0, figure_count=0, abstract_word_count=0,
            specification_checks=[], claims_checks=[],
            abstract_checks=[], drawings_checks=[],
            claim_trees=[],
        )
        assert report.all_checks == []

    def test_concatenation_order(self):
        spec = [self._make_check("spec.1")]
        claims = [self._make_check("claims.1"), self._make_check("claims.2")]
        abstract = [self._make_check("abstract.1")]
        drawings = [self._make_check("drawings.1")]
        report = ReportData(
            paragraph_count=0, total_claims=0, independent_count=0,
            dependent_count=0, figure_count=0, abstract_word_count=0,
            specification_checks=spec, claims_checks=claims,
            abstract_checks=abstract, drawings_checks=drawings,
            claim_trees=[],
        )
        keys = [c.message_key for c in report.all_checks]
        assert keys == [
            "check.spec.1", "check.claims.1", "check.claims.2",
            "check.abstract.1", "check.drawings.1",
        ]

    def test_returns_new_list_each_call(self):
        report = ReportData(
            paragraph_count=0, total_claims=0, independent_count=0,
            dependent_count=0, figure_count=0, abstract_word_count=0,
            specification_checks=[self._make_check("s1")],
            claims_checks=[], abstract_checks=[], drawings_checks=[],
            claim_trees=[],
        )
        a = report.all_checks
        b = report.all_checks
        assert a == b
        assert a is not b


class TestUsFiguresSequentialAmend:
    """US drawings amend check forwards missing figure numbers to the UI."""

    def _find_sequential_amend(self, report: ReportData) -> CheckItem | None:
        for check in report.drawings_checks:
            if check.message_key == "check.drawings.sequential.amend":
                return check
        return None

    def test_amend_emits_figure_list(self):
        result = AnalysisResult(
            jurisdiction=Jurisdiction.US,
            figures_count=3,
            figures_sequential=False,
            figures_missing=[2, 4],
        )
        report = result.to_report_data()
        check = self._find_sequential_amend(report)
        assert check is not None
        assert check.status == "amend"
        assert check.details_params == {"figure_list": [2, 4]}

    def test_pass_has_no_amend_check(self):
        result = AnalysisResult(
            jurisdiction=Jurisdiction.US,
            figures_count=3,
            figures_sequential=True,
        )
        report = result.to_report_data()
        assert self._find_sequential_amend(report) is None


class TestUsAbstractStructureAmendDiagnostics:
    """Regression for the abstract.structure.amend diagnostic crash —
    ``_to_us_report_data`` referenced ``self.abstract_text`` before that
    field existed on ``AnalysisResult``, so any document with
    ``abstract_structure_good=False`` (extra paragraphs / invalid
    ending) would crash at adapter time. Surfaced 2026-04-27 via
    real-user testing on TestSpec1/2; pre-existing from the ADR-145
    fingerprint sweep (b447ab6 / 1c35b54).
    """

    def _find_structure_amend(self, report: ReportData) -> CheckItem | None:
        for check in report.abstract_checks:
            if check.message_key == "check.abstract.structure.amend":
                return check
        return None

    def test_structure_amend_renders_with_abstract_text(self):
        result = AnalysisResult(
            jurisdiction=Jurisdiction.US,
            abstract_word_count=80,
            abstract_text="An invention. Extra paragraph here.",
            abstract_structure_good=False,
        )
        report = result.to_report_data()
        check = self._find_structure_amend(report)
        assert check is not None
        assert check.status == "amend"
        assert check.diagnostics is not None
        assert check.diagnostics.get("reason_code") == "bad_structure"
        assert check.diagnostics.get("abstract_word_count") == 80
        assert check.diagnostics.get("abstract_charlen") == len(
            "An invention. Extra paragraph here."
        )

    def test_structure_amend_renders_with_empty_abstract_text(self):
        # ``abstract_text=""`` was the silent-default before this fix;
        # adapter must still render the chip without crashing on
        # ``len(None)`` or ``ord("")[-1]``.
        result = AnalysisResult(
            jurisdiction=Jurisdiction.US,
            abstract_word_count=0,
            abstract_text="",
            abstract_structure_good=False,
        )
        report = result.to_report_data()
        check = self._find_structure_amend(report)
        assert check is not None
        assert check.diagnostics.get("abstract_charlen") == 0
        assert check.diagnostics.get("last_char_codepoint") is None
