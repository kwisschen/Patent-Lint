# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
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


class TestDependencyPrefixVariants:
    """Each prefix variant (如 / 根据 / 依据 / bare) must extract the
    parent claim number correctly. 根据 is the dominant form in real
    CNIPA filings; the Stage 1 regex only covered 如 which is why Stage
    1.5 had to ship this extension before the Stage 2 walker port."""

    def _parse(self, dep_text: str) -> list[int]:
        text = (
            "1. 一种装置，包括第一组件。\n"
            f"2. {dep_text}，改进A。"
        )
        return parse_cn_claims_docx(text)[1].dependencies

    def test_prefix_ru(self):
        assert self._parse("如权利要求1所述的装置") == [1]

    def test_prefix_genju(self):
        assert self._parse("根据权利要求1所述的装置") == [1]

    def test_prefix_yiju(self):
        assert self._parse("依据权利要求1所述的装置") == [1]

    def test_prefix_bare(self):
        # Bare form seen in older filings.
        assert self._parse("权利要求1的装置") == [1]


class TestDependencyRangeMultidep:
    def test_genju_range_any_one(self):
        text = (
            "1. 一种装置。\n"
            "2. 如权利要求1所述的装置。\n"
            "3. 如权利要求1所述的装置。\n"
            "4. 如权利要求1所述的装置。\n"
            "5. 根据权利要求1至5中任一项所述的装置。"
        )
        claims = parse_cn_claims_docx(text)
        # Self-references stripped — claim 5 cannot depend on itself.
        assert claims[4].dependencies == [1, 2, 3, 4]
        assert claims[4].multiple_dependent is True

    def test_range_without_any_one(self):
        # Some filings omit 任一项 — range still expands.
        text = (
            "1. 一种装置。\n"
            "2. 如权利要求1所述的装置。\n"
            "3. 如权利要求1所述的装置。\n"
            "4. 根据权利要求1至3所述的装置。"
        )
        claims = parse_cn_claims_docx(text)
        assert claims[3].dependencies == [1, 2, 3]


class TestDependencyDisjunction:
    def test_genju_disjunction(self):
        text = (
            "1. 一种装置。\n"
            "2. 一种装置的变体。\n"
            "3. 一种装置的另一变体。\n"
            "4. 根据权利要求1或3所述的装置。"
        )
        claims = parse_cn_claims_docx(text)
        assert claims[3].dependencies == [1, 3]
        assert claims[3].multiple_dependent is True


class TestDependencyEnumeration:
    def test_genju_enumeration(self):
        text = (
            "1. 一种装置。\n"
            "2. 一种装置的变体。\n"
            "3. 一种装置的另一变体。\n"
            "4. 根据权利要求1、2或3所述的装置。"
        )
        claims = parse_cn_claims_docx(text)
        assert claims[3].dependencies == [1, 2, 3]
        assert claims[3].multiple_dependent is True

    def test_enumeration_without_or(self):
        text = (
            "1. 一种装置。\n"
            "2. 一种装置的变体。\n"
            "3. 一种装置的另一变体。\n"
            "4. 根据权利要求1、2、3所述的装置。"
        )
        claims = parse_cn_claims_docx(text)
        assert claims[3].dependencies == [1, 2, 3]


class TestNonClaimTextNotMatched:
    def test_quanli_yaoqiu_shu_not_matched(self):
        """Spec text referencing '权利要求书' (the document, not a claim
        number) must not be mistaken for a dependency. The regex requires
        a digit after 权利要求 so this is a digit-absence guard."""
        text = (
            "1. 一种装置。\n"
            "2. 如权利要求书所载的装置实施例。"
        )
        claims = parse_cn_claims_docx(text)
        # Claim 2 has no numeric dependency — must parse as independent.
        assert claims[1].dependencies == []
        assert claims[1].independent is True


class TestMidParagraphClaimBoundary:
    """Real CNIPA filings sometimes pack two claims into one Word
    paragraph with no newline between them. The preprocessing pass
    must recover these boundaries without false-positives on
    step references or inline enumerations."""

    def test_two_claims_one_paragraph_sentence_end(self):
        text = "1. 一种装置，包括组件A。 2. 如权利要求1所述的装置，其特征在于，包括组件B。"
        claims = parse_cn_claims_docx(text)
        assert [c.id for c in claims] == [1, 2]
        assert claims[1].dependencies == [1]

    def test_two_claims_one_paragraph_double_space(self):
        text = "1 .一种方法，包括步骤A。  2 .根据权利要求1所述的方法，其特征在于，包括步骤B。"
        claims = parse_cn_claims_docx(text)
        assert [c.id for c in claims] == [1, 2]
        assert claims[1].dependencies == [1]

    def test_step_reference_not_mid_boundary(self):
        """`步骤S2` or `2.3中` inside a claim body must not create a
        spurious claim boundary. The lookahead `[一如根其权依包对将在本]`
        guards against this."""
        text = "1 .一种方法，其特征在于，步骤S1中制备培养基；步骤S2中分离细胞。"
        claims = parse_cn_claims_docx(text)
        assert len(claims) == 1
        assert claims[0].id == 1

    def test_new_independent_claim_after_sentence_end(self):
        """Second independent claim (`一种X`) following first claim's
        period+space must be recovered."""
        text = "1. 一种方法，包括步骤A。 2. 一种装置，包括组件A。"
        claims = parse_cn_claims_docx(text)
        assert [c.id for c in claims] == [1, 2]
        assert claims[1].independent is True
