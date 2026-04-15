# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Unit tests for patentlint.models."""

from patentlint.models import CheckItem, ReportData


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
