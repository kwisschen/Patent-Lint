"""Tests for patentlint.analysis.claims."""

from patentlint.models import Claim
from patentlint.analysis.claims import (
    find_missing_periods,
    has_extra_periods,
    find_self_dependent_claims,
    are_claims_sequential,
    get_last_sequential_index,
    calculate_similarity,
    get_dependency_chain,
    count_independent,
    count_dependent,
    detect_means_plus_function,
    check_antecedent_basis,
)


class TestMissingPeriods:
    def test_detected(self):
        claims = [
            Claim(id=1, text="A method comprising step A.", independent=True, method_claim=True),
            Claim(id=2, text="The method of claim 1 with step B", independent=False, method_claim=True, dependencies=[1]),
        ]
        assert find_missing_periods(claims) == [2]

    def test_all_good(self):
        claims = [
            Claim(id=1, text="A method.", independent=True, method_claim=True),
            Claim(id=2, text="The method of claim 1.", independent=False, method_claim=True, dependencies=[1]),
        ]
        assert find_missing_periods(claims) == []


class TestExtraPeriods:
    def test_double_dot(self):
        assert has_extra_periods("A method comprising..\nstep A.") is True

    def test_mid_claim(self):
        assert has_extra_periods("A method comprising step A.\nfurther comprising step B.") is True

    def test_clean(self):
        assert has_extra_periods("A method comprising:\nstep A;\nstep B.") is False


class TestSelfDependency:
    def test_detected(self):
        claims = [
            Claim(id=1, text="A method.", independent=True, method_claim=True),
            Claim(id=2, text="The method of claim 2.", independent=False, method_claim=True, dependencies=[2]),
        ]
        assert find_self_dependent_claims(claims) == [2]


class TestSequentiality:
    def test_sequential(self):
        assert are_claims_sequential([1, 2, 3, 4]) is True

    def test_gap(self):
        assert are_claims_sequential([1, 2, 4, 5]) is False

    def test_last_index(self):
        assert get_last_sequential_index([1, 2, 4, 5]) == 2


class TestSimilarity:
    def test_identical(self):
        text = "A method comprising processing data in a processor."
        assert calculate_similarity(text, text) == 1.0

    def test_different(self):
        assert calculate_similarity("A method.", "The cat sat on the mat near the door.") < 0.2

    def test_similar(self):
        sim = calculate_similarity(
            "A method comprising processing data in a processor.",
            "A method comprising processing data in a computer.",
        )
        assert sim > 0.5


class TestDependencyChain:
    def test_independent(self):
        claims = [Claim(id=1, text="A method.", independent=True, method_claim=True)]
        assert get_dependency_chain(claims[0], claims) == "1"

    def test_traced(self):
        claims = [
            Claim(id=1, text="A method.", independent=True, method_claim=True),
            Claim(id=2, text="The method of claim 1.", independent=False, method_claim=True, dependencies=[1]),
            Claim(id=3, text="The method of claim 2.", independent=False, method_claim=True, dependencies=[2]),
        ]
        assert get_dependency_chain(claims[2], claims) == "3 → 2 → 1"

    def test_self(self):
        claims = [Claim(id=1, text="The method of claim 1.", independent=False, method_claim=True, dependencies=[1])]
        assert get_dependency_chain(claims[0], claims) == "SELF"


class TestMeansPlusFunction:
    def test_means_for_detected(self):
        claims = [Claim(id=1, text="A device comprising means for processing data.", independent=True, method_claim=False)]
        assert detect_means_plus_function(claims) == [1]

    def test_by_means_of_not_detected(self):
        claims = [Claim(id=1, text="A device connected by means of a processor.", independent=True, method_claim=False)]
        assert detect_means_plus_function(claims) == []

    def test_no_means_language(self):
        claims = [Claim(id=1, text="A method comprising receiving data.", independent=True, method_claim=True)]
        assert detect_means_plus_function(claims) == []

    def test_step_for_detected(self):
        claims = [Claim(id=1, text="A method comprising a step for processing data.", independent=True, method_claim=True)]
        assert detect_means_plus_function(claims) == [1]

    def test_module_for_detected(self):
        claims = [Claim(id=1, text="A system comprising a module for transmitting signals.", independent=True, method_claim=False)]
        assert detect_means_plus_function(claims) == [1]


class TestAntecedentBasis:
    def test_proper_basis(self):
        """'a base' introduces, 'the base' references — no issue."""
        claims = [Claim(id=1, text="A widget comprising a base, wherein the base is flat.", independent=True, method_claim=False)]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues]
        assert "base" not in terms

    def test_missing_basis_independent(self):
        """'The widget' without prior 'a widget' should be flagged."""
        claims = [Claim(id=1, text="The widget comprising a base, wherein the base is flat.", independent=True, method_claim=False)]
        issues = check_antecedent_basis(claims)
        flagged_terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert any("widget" in t for t in flagged_terms)

    def test_dependent_inherits_basis(self):
        """Dependent claim can use 'the base' if parent introduces 'a base'."""
        claims = [
            Claim(id=1, text="A device comprising a base, wherein the base is flat.", independent=True, method_claim=False),
            Claim(id=2, text="The device of claim 1, wherein the base is metal.", independent=False, method_claim=False, dependencies=[1]),
        ]
        issues = check_antecedent_basis(claims)
        claim2_terms = [i["term"] for i in issues if i["claim_id"] == 2]
        assert "base" not in claim2_terms

    def test_said_without_prior(self):
        """'said processor' without prior 'a processor' should be flagged."""
        claims = [Claim(id=1, text="A device comprising a memory, wherein said processor executes code.", independent=True, method_claim=False)]
        issues = check_antecedent_basis(claims)
        flagged_terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert any("processor" in t for t in flagged_terms)


class TestCounts:
    def test_counts(self):
        claims = [
            Claim(id=1, text="A method.", independent=True, method_claim=True),
            Claim(id=2, text="The method of claim 1.", independent=False, method_claim=True, dependencies=[1]),
            Claim(id=3, text="A system.", independent=True, method_claim=False),
            Claim(id=4, text="The system of claim 3.", independent=False, method_claim=False, dependencies=[3]),
        ]
        assert count_independent(claims) == 2
        assert count_dependent(claims) == 2
