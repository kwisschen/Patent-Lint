# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for CN claim parser."""

from __future__ import annotations

from patentlint.parser.claims_cn import parse_cn_claims_docx


class TestIndependentClaim:
    def test_independent_claim(self):
        text = "1. 一种测试装置，其特征在于，包括第一组件。"
        claims = parse_cn_claims_docx(text)
        assert len(claims) == 1
        assert claims[0].id == 1
        assert claims[0].independent is True
        assert claims[0].dependencies == []


class TestDependentClaim:
    def test_dependent_claim(self):
        text = (
            "1. 一种测试装置，其特征在于，包括第一组件。\n"
            "2. 如权利要求1所述的测试装置，其特征在于，还包括第二组件。"
        )
        claims = parse_cn_claims_docx(text)
        assert len(claims) == 2
        assert claims[1].id == 2
        assert claims[1].dependencies == [1]
        assert claims[1].independent is False


class TestMultipleClaims:
    def test_multiple_claims(self):
        text = (
            "1. 一种测试装置，其特征在于，包括第一组件。\n"
            "2. 如权利要求1所述的测试装置，其特征在于，还包括第二组件。\n"
            "3. 如权利要求2所述的测试装置，其特征在于，第二组件为金属。\n"
            "4. 一种测试方法，其特征在于，包括步骤A。\n"
            "5. 如权利要求4所述的测试方法，其特征在于，还包括步骤B。"
        )
        claims = parse_cn_claims_docx(text)
        assert len(claims) == 5
        assert [c.id for c in claims] == [1, 2, 3, 4, 5]
        assert claims[0].independent is True
        assert claims[1].dependencies == [1]
        assert claims[2].dependencies == [2]
        assert claims[3].independent is True
        assert claims[4].dependencies == [4]


class TestRangeDependency:
    def test_range_dependency(self):
        text = (
            "1. 一种装置。\n"
            "2. 如权利要求1所述的装置，改进A。\n"
            "3. 如权利要求1所述的装置，改进B。\n"
            "4. 如权利要求1至3中任一项所述的装置，改进C。"
        )
        claims = parse_cn_claims_docx(text)
        assert claims[3].dependencies == [1, 2, 3]
        assert claims[3].multiple_dependent is True


class TestFullwidthPeriod:
    def test_fullwidth_period(self):
        text = "1．一种装置，其特征在于，包括组件。"
        claims = parse_cn_claims_docx(text)
        assert len(claims) == 1
        assert claims[0].id == 1
        assert claims[0].independent is True


class TestEmptyText:
    def test_empty_text(self):
        assert parse_cn_claims_docx("") == []


class TestNoClaims:
    def test_no_claims(self):
        text = "这不是权利要求文本。"
        assert parse_cn_claims_docx(text) == []


class TestSelfReferenceExcluded:
    def test_self_reference_excluded(self):
        text = (
            "1. 一种装置。\n"
            "2. 如权利要求1所述的装置，改进A。"
        )
        claims = parse_cn_claims_docx(text)
        # Claim 1 should not have itself as dependency
        assert claims[0].dependencies == []
        assert claims[0].independent is True


class TestClaimTextBoundaries:
    def test_claim_text_boundaries(self):
        text = (
            "1. 第一权利要求内容。\n"
            "2. 如权利要求1所述的装置，第二权利要求。\n"
            "3. 如权利要求2所述的装置，第三权利要求。"
        )
        claims = parse_cn_claims_docx(text)
        assert "第一权利要求" in claims[0].text
        assert "第二权利要求" in claims[1].text
        assert "第三权利要求" in claims[2].text
        # Each claim's text should NOT contain the next claim's content
        assert "第二权利要求" not in claims[0].text
        assert "第三权利要求" not in claims[1].text


class TestAlternativeDependencyFormat:
    def test_alternative_dependency_format(self):
        text = (
            "1. 一种装置。\n"
            "2. 如权利要求1所述的装置，改进A。\n"
            "3. 如权利要求1所述的装置，改进B。\n"
            "4. 如权利要求1所述的装置，改进C。\n"
            "5. 如权利要求2到4中任意项所述的装置，改进D。"
        )
        claims = parse_cn_claims_docx(text)
        assert claims[4].dependencies == [2, 3, 4]
        assert claims[4].multiple_dependent is True
