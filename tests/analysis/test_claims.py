# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.analysis.claims."""

from patentlint.models import Claim
from patentlint.parser.claims import parse_claims, parse_dependencies
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
    check_claim_transitions,
    check_special_claim_formats,
    check_claim_punctuation,
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


class TestClaimPunctuation:
    def test_missing_period_detected(self):
        claims = [
            Claim(id=1, text="A method comprising step A.", independent=True, method_claim=True),
            Claim(id=2, text="The method of claim 1 with step B", independent=False, method_claim=True, dependencies=[1]),
        ]
        results = check_claim_punctuation(claims)
        assert any(r.message_key == "claims.missingPeriod" and r.status == "amend" for r in results)
        assert any("2" in (r.details_params or {}).get("claimNumber", "") for r in results)

    def test_extra_period_detected(self):
        claims = [
            Claim(id=1, text="A method comprising..\nstep A.", independent=True, method_claim=True),
        ]
        results = check_claim_punctuation(claims)
        assert any(r.message_key == "claims.extraPeriod" and r.status == "amend" for r in results)

    def test_wherein_comma_detected(self):
        claims = [
            Claim(id=1, text="A method wherein when the input is received, processing occurs.", independent=True, method_claim=True),
        ]
        results = check_claim_punctuation(claims)
        assert any(r.message_key == "claims.whereinComma" and r.status == "verify" for r in results)

    def test_all_clean_returns_pass(self):
        claims = [
            Claim(id=1, text="A method comprising step A.", independent=True, method_claim=True),
            Claim(id=2, text="The method of claim 1, wherein the step A is repeated.", independent=False, method_claim=True, dependencies=[1]),
        ]
        results = check_claim_punctuation(claims)
        assert len(results) == 1
        assert results[0].status == "pass"
        assert results[0].message_key == "claims.punctuationPass"

    def test_multiple_issues_multiple_items(self):
        claims = [
            Claim(id=1, text="A method comprising step A", independent=True, method_claim=True),  # missing period
            Claim(id=2, text="The method of claim 1 comprising..\nstep B.", independent=False, method_claim=True, dependencies=[1]),  # extra period
        ]
        results = check_claim_punctuation(claims)
        assert len(results) >= 2
        keys = [r.message_key for r in results]
        assert "claims.missingPeriod" in keys
        assert "claims.extraPeriod" in keys


class TestSelfDependency:
    def test_detected(self):
        claims = [
            Claim(id=1, text="A method.", independent=True, method_claim=True),
            Claim(id=2, text="The method of claim 2.", independent=False, method_claim=True, dependencies=[2]),
        ]
        assert find_self_dependent_claims(claims) == [2]


class TestParseDependenciesSelfDependent:
    """Self-references in parsed dependencies are silently dropped."""

    def test_only_self_yields_empty_dependencies(self):
        text = "The apparatus of claim 11, wherein the apparatus is blue."
        assert parse_dependencies(text, independent=False, claim_number=11) == []

    def test_self_and_other_drops_only_self(self):
        text = "The apparatus of claims 10 and 11, wherein the apparatus is blue."
        assert parse_dependencies(text, independent=False, claim_number=11) == [10]

    def test_no_self_unchanged(self):
        text = "The apparatus of claim 1, wherein the apparatus is blue."
        assert parse_dependencies(text, independent=False, claim_number=2) == [1]

    def test_parse_claims_drops_self_reference(self):
        # End-to-end via parse_claims: a self-dependent claim emits dependencies=[].
        claims_text = (
            "1. An apparatus.\n"
            "11. The apparatus of claim 11, wherein the apparatus is blue.\n"
        )
        claims = parse_claims(claims_text)
        claim_11 = next(c for c in claims if c.id == 11)
        assert claim_11.dependencies == []


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


class TestClaimTransitions:
    def test_comprising_passes(self):
        """Single independent claim with 'comprising' → PASS."""
        claims = [Claim(id=1, text="A method comprising step A.", independent=True, method_claim=True)]
        results = check_claim_transitions(claims)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_consisting_of_passes(self):
        """Single independent claim with 'consisting of' → PASS."""
        claims = [Claim(id=1, text="A widget consisting of a base and a lid.", independent=True)]
        results = check_claim_transitions(claims)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_no_transition_amend(self):
        """Independent claim with no transition → AMEND."""
        claims = [Claim(id=1, text="A widget with a base and a lid.", independent=True)]
        results = check_claim_transitions(claims)
        assert len(results) == 1
        assert results[0].status == "amend"
        assert "1" in results[0].message

    def test_dependent_not_checked(self):
        """Dependent claim with 'wherein' only — parent has 'comprising' → PASS."""
        claims = [
            Claim(id=1, text="A device comprising a base.", independent=True),
            Claim(id=2, text="The device of claim 1, wherein the base is flat.", independent=False, dependencies=[1]),
        ]
        results = check_claim_transitions(claims)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_jepson_claim_passes(self):
        """Jepson claim with 'comprising' → PASS."""
        claims = [Claim(id=1, text="In a widget, the improvement comprising a new lid.", independent=True)]
        results = check_claim_transitions(claims)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_having_passes(self):
        """Claim with 'having' as transition → PASS."""
        claims = [Claim(id=1, text="A device having a processor and a memory.", independent=True)]
        results = check_claim_transitions(claims)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_mixed_one_missing(self):
        """Multiple independent claims: one with transition, one without → one AMEND."""
        claims = [
            Claim(id=1, text="A method comprising step A.", independent=True, method_claim=True),
            Claim(id=2, text="A widget with a base.", independent=True),
        ]
        results = check_claim_transitions(claims)
        assert len(results) == 1
        assert results[0].status == "amend"
        assert "2" in results[0].message

    def test_including_passes(self):
        """Claim with 'including' → PASS."""
        claims = [Claim(id=1, text="A system including a processor.", independent=True)]
        results = check_claim_transitions(claims)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_consists_essentially_of_passes(self):
        """Claim with 'consists essentially of' → PASS."""
        claims = [Claim(id=1, text="A composition consists essentially of compound A and compound B.", independent=True)]
        results = check_claim_transitions(claims)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_contains_passes(self):
        """Claim with 'contains' → PASS."""
        claims = [Claim(id=1, text="A vessel contains a fluid.", independent=True)]
        results = check_claim_transitions(claims)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_characterized_by_passes(self):
        """Claim with 'characterized by' → PASS."""
        claims = [Claim(id=1, text="A device characterized by a lid attached to a base.", independent=True)]
        results = check_claim_transitions(claims)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_characterized_in_that_passes(self):
        """Claim with 'characterized in that' (PCT/EPO two-part format) → PASS."""
        claims = [Claim(id=1, text="A widget of the type having a base, characterized in that the base includes a groove.", independent=True)]
        results = check_claim_transitions(claims)
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_transition_not_at_boundary(self):
        """Issue #7: 'containing' in body should not satisfy transition check."""
        claims = [
            Claim(id=1, text="A semiconductor device with: a substrate; and a layer containing copper deposited on the substrate.", independent=True),
        ]
        results = check_claim_transitions(claims)
        amends = [r for r in results if r.status == "amend"]
        assert len(amends) == 1
        assert "1" in amends[0].message

    def test_transition_at_boundary_ignores_body(self):
        """'comprising:' at boundary passes even if 'containing' appears in body."""
        claims = [
            Claim(id=1, text="A semiconductor device comprising: a substrate; and a layer containing copper deposited on the substrate.", independent=True),
        ]
        results = check_claim_transitions(claims)
        passes = [r for r in results if r.status == "pass"]
        assert len(passes) == 1

    def test_characterized_in_that_no_colon(self):
        """EPO/PCT two-part claim with 'characterized in that' (no colon)."""
        claims = [
            Claim(id=1, text="A semiconductor device characterized in that a substrate is disposed on a base.", independent=True),
        ]
        results = check_claim_transitions(claims)
        passes = [r for r in results if r.status == "pass"]
        assert len(passes) == 1

    def test_no_colon_fallback(self):
        """Claim with no colon uses full-text fallback."""
        claims = [
            Claim(id=1, text="A method of manufacturing a device, comprising depositing a layer on a substrate.", independent=True, method_claim=True),
        ]
        results = check_claim_transitions(claims)
        passes = [r for r in results if r.status == "pass"]
        assert len(passes) == 1


class TestSpecialClaimFormats:
    # --- Jepson (5 tests) ---

    def test_jepson_improvement_comprising(self):
        """Independent claim with 'the improvement comprising' -> VERIFY."""
        claims = [Claim(id=1, text="In a widget having a base, the improvement comprising a lid attached to the base.", independent=True)]
        results = check_special_claim_formats(claims)
        assert len(results) == 1
        assert results[0].status == "verify"
        assert results[0].message_key == "claims.jepsonPriorArt"

    def test_jepson_wherein_improvement_comprises(self):
        """Independent claim with 'wherein the improvement comprises' -> VERIFY."""
        claims = [Claim(id=1, text="In a device having a housing, wherein the improvement comprises a sensor mounted on the housing.", independent=True)]
        results = check_special_claim_formats(claims)
        assert len(results) == 1
        assert results[0].status == "verify"
        assert results[0].message_key == "claims.jepsonPriorArt"

    def test_jepson_normal_claim_no_finding(self):
        """Normal independent claim (no Jepson language) -> PASS."""
        claims = [Claim(id=1, text="A method comprising step A and step B.", independent=True, method_claim=True)]
        results = check_special_claim_formats(claims)
        assert len(results) == 1
        assert results[0].status == "pass"
        assert results[0].message_key == "claims.specialFormatsPass"

    def test_jepson_dependent_not_checked(self):
        """Dependent claim with Jepson-like language -> empty list."""
        claims = [Claim(id=2, text="The device of claim 1, the improvement comprising a seal.", independent=False, dependencies=[1])]
        results = check_special_claim_formats(claims)
        jepson = [r for r in results if r.message_key == "claims.jepsonPriorArt"]
        assert len(jepson) == 0

    def test_jepson_multiple_independent_one_jepson(self):
        """Two independent claims, one Jepson one normal -> exactly one VERIFY."""
        claims = [
            Claim(id=1, text="A method comprising step A.", independent=True, method_claim=True),
            Claim(id=2, text="In a widget having a base, the improvement comprising a lid.", independent=True),
        ]
        results = check_special_claim_formats(claims)
        jepson = [r for r in results if r.message_key == "claims.jepsonPriorArt"]
        assert len(jepson) == 1
        assert "2" in jepson[0].message

    # --- CRM non-transitory (5 tests) ---

    def test_crm_with_non_transitory_passes(self):
        """'A non-transitory computer-readable medium...' -> empty list."""
        claims = [Claim(id=1, text="A non-transitory computer-readable medium storing instructions that cause a processor to perform a method.", independent=True)]
        results = check_special_claim_formats(claims)
        crm = [r for r in results if r.message_key == "claims.crmNonTransitory"]
        assert len(crm) == 0

    def test_crm_missing_non_transitory_amend(self):
        """'A computer-readable medium...' without non-transitory -> AMEND."""
        claims = [Claim(id=1, text="A computer-readable medium storing instructions that cause a processor to perform a method.", independent=True)]
        results = check_special_claim_formats(claims)
        crm = [r for r in results if r.message_key == "claims.crmNonTransitory"]
        assert len(crm) == 1
        assert crm[0].status == "amend"

    def test_crm_no_hyphen_non_transitory_passes(self):
        """'A non transitory machine-readable medium...' (no hyphen) -> empty list."""
        claims = [Claim(id=1, text="A non transitory machine-readable medium storing code.", independent=True)]
        results = check_special_claim_formats(claims)
        crm = [r for r in results if r.message_key == "claims.crmNonTransitory"]
        assert len(crm) == 0

    def test_crm_storage_medium_missing_qualifier(self):
        """'A computer-readable storage medium...' without non-transitory -> AMEND."""
        claims = [Claim(id=1, text="A computer-readable storage medium having instructions stored thereon.", independent=True)]
        results = check_special_claim_formats(claims)
        crm = [r for r in results if r.message_key == "claims.crmNonTransitory"]
        assert len(crm) == 1
        assert crm[0].status == "amend"

    def test_crm_normal_apparatus_no_finding(self):
        """Normal apparatus claim (no CRM language) -> empty list."""
        claims = [Claim(id=1, text="An apparatus comprising a processor and a memory.", independent=True)]
        results = check_special_claim_formats(claims)
        crm = [r for r in results if r.message_key == "claims.crmNonTransitory"]
        assert len(crm) == 0

    # --- Markush (4 tests) ---

    def test_markush_consisting_of_correct(self):
        """'selected from the group consisting of A, B, and C' -> empty list."""
        claims = [Claim(id=1, text="A composition comprising a metal selected from the group consisting of gold, silver, and copper.", independent=True)]
        results = check_special_claim_formats(claims)
        markush = [r for r in results if r.message_key == "claims.markushOpenTransition"]
        assert len(markush) == 0

    def test_markush_comprising_flagged(self):
        """'selected from the group comprising A, B, and C' -> VERIFY."""
        claims = [Claim(id=1, text="A composition comprising a metal selected from the group comprising gold, silver, and copper.", independent=True)]
        results = check_special_claim_formats(claims)
        markush = [r for r in results if r.message_key == "claims.markushOpenTransition"]
        assert len(markush) == 1
        assert markush[0].status == "verify"
        assert markush[0].details_params["transition"] == "comprising"

    def test_markush_including_flagged(self):
        """'selected from a group including X, Y, or Z' -> VERIFY."""
        claims = [Claim(id=2, text="The device of claim 1, wherein the material is selected from a group including aluminum, titanium, or steel.", independent=False, dependencies=[1])]
        results = check_special_claim_formats(claims)
        markush = [r for r in results if r.message_key == "claims.markushOpenTransition"]
        assert len(markush) == 1
        assert markush[0].details_params["transition"] == "including"

    def test_markush_no_markush_language(self):
        """Claim with no Markush language -> empty list."""
        claims = [Claim(id=1, text="A device comprising a base and a lid.", independent=True)]
        results = check_special_claim_formats(claims)
        markush = [r for r in results if r.message_key == "claims.markushOpenTransition"]
        assert len(markush) == 0

    # --- Omnibus (4 tests) ---

    def test_omnibus_short_substantially_as_shown(self):
        """Short claim 'substantially as shown and described' -> AMEND."""
        claims = [Claim(id=1, text="A device substantially as shown and described.", independent=True)]
        results = check_special_claim_formats(claims)
        omnibus = [r for r in results if r.message_key == "claims.omnibusClaim"]
        assert len(omnibus) == 1
        assert omnibus[0].status == "amend"

    def test_omnibus_short_as_herein_described(self):
        """Short claim 'as herein described' -> AMEND."""
        claims = [Claim(id=1, text="The invention as herein described.", independent=True)]
        results = check_special_claim_formats(claims)
        omnibus = [r for r in results if r.message_key == "claims.omnibusClaim"]
        assert len(omnibus) == 1
        assert omnibus[0].status == "amend"

    def test_omnibus_long_claim_not_flagged(self):
        """Long claim (60+ words) with 'as shown in FIG. 3' -> empty list (not omnibus)."""
        long_text = (
            "A semiconductor device comprising: a substrate having a first surface and a second surface; "
            "a plurality of transistors formed on the first surface of the substrate; an interconnect layer "
            "disposed above the plurality of transistors, the interconnect layer comprising a plurality of "
            "metal lines and vias; and a passivation layer disposed above the interconnect layer, "
            "as shown in FIG. 3, wherein the passivation layer protects the metal lines from oxidation."
        )
        claims = [Claim(id=1, text=long_text, independent=True)]
        results = check_special_claim_formats(claims)
        omnibus = [r for r in results if r.message_key == "claims.omnibusClaim"]
        assert len(omnibus) == 0

    def test_omnibus_normal_claim_no_finding(self):
        """Normal claim with no omnibus language -> empty list."""
        claims = [Claim(id=1, text="A method comprising receiving data and processing the data.", independent=True, method_claim=True)]
        results = check_special_claim_formats(claims)
        omnibus = [r for r in results if r.message_key == "claims.omnibusClaim"]
        assert len(omnibus) == 0


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
