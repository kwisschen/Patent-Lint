# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Tests for patentlint.analysis.claims."""

from patentlint.models import Claim
from patentlint.parser.claims import parse_claims, parse_dependencies
from patentlint.analysis.claims import (
    find_missing_periods,
    has_extra_periods,
    find_self_dependent_claims,
    find_chained_multi_dependents,
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
    _TRANSITIONS,
)


class TestChainedMultiDependents:
    """35 U.S.C. § 112(e): a multi-dependent claim cannot depend on another
    multi-dependent claim. Flags the actual chain violation (FIX), unlike
    find_multiple_dependents which just flags presence (REVIEW)."""

    def test_no_multi_deps(self):
        claims = [
            Claim(id=1, text="1. A method.", independent=True, method_claim=True),
            Claim(id=2, text="2. The method of claim 1.", independent=False, method_claim=True, dependencies=[1]),
        ]
        assert find_chained_multi_dependents(claims) == []

    def test_single_multi_dep_no_chain(self):
        # Claim 3 is multi-dep (depends on 1 or 2), but 1 and 2 are single-dep — no violation.
        claims = [
            Claim(id=1, text="1. A method.", independent=True, method_claim=True),
            Claim(id=2, text="2. An apparatus.", independent=True, method_claim=False),
            Claim(id=3, text="3. The method/apparatus of claim 1 or 2.", independent=False,
                  method_claim=True, dependencies=[1, 2], multiple_dependent=True),
        ]
        assert find_chained_multi_dependents(claims) == []

    def test_chained_violation_detected(self):
        # Claim 3 is multi-dep; claim 4 is multi-dep that depends on claim 3 — § 112(e) violation.
        claims = [
            Claim(id=1, text="1. A method.", independent=True, method_claim=True),
            Claim(id=2, text="2. An apparatus.", independent=True, method_claim=False),
            Claim(id=3, text="3. The method/apparatus of claim 1 or 2.", independent=False,
                  method_claim=True, dependencies=[1, 2], multiple_dependent=True),
            Claim(id=4, text="4. The method of claim 3 or 1.", independent=False,
                  method_claim=True, dependencies=[3, 1], multiple_dependent=True),
        ]
        assert find_chained_multi_dependents(claims) == [4]

    def test_chained_deep(self):
        claims = [
            Claim(id=1, text="1. A method.", independent=True, method_claim=True),
            Claim(id=2, text="2. An apparatus.", independent=True, method_claim=False),
            Claim(id=3, text="3. The method/apparatus of claim 1 or 2.", independent=False,
                  method_claim=True, dependencies=[1, 2], multiple_dependent=True),
            Claim(id=4, text="4. The method of claim 1 or 3.", independent=False,
                  method_claim=True, dependencies=[1, 3], multiple_dependent=True),
            Claim(id=5, text="5. The method of claim 3 or 4.", independent=False,
                  method_claim=True, dependencies=[3, 4], multiple_dependent=True),
        ]
        # 4 chains via 3; 5 chains via both 3 and 4.
        assert find_chained_multi_dependents(claims) == [4, 5]


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

    def test_finite_verb_not_overcaptured(self):
        """N+V clauses (`X comprises Y`, `X meets Y`, `X respectively
        reaches Y`) must not bleed the verb + object into the captured
        term. Regression for the over-capture FP class (issues #72/#73).
        """
        claims = [
            Claim(
                id=1,
                text=(
                    "A device comprising a hardware module, wherein the "
                    "hardware module comprises a human interface and the "
                    "confidence measurement meets a threshold."
                ),
                independent=True,
                method_claim=False,
            ),
        ]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        # No emitted term may carry a trailing finite verb / its object.
        for t in terms:
            assert "comprises" not in t, f"verb bled into term: {t!r}"
            assert "meets" not in t, f"verb bled into term: {t!r}"
        # The clean head noun is still flagged (no intro for it here).
        assert any(t == "confidence measurement" for t in terms), terms

    def test_bare_noun_introduction_same_claim(self):
        """R4 (issue #91): a multi-word term first mentioned article-less
        earlier in the SAME claim (preamble term / verb object) has
        antecedent basis — MPEP § 2173.05(e)."""
        claims = [
            Claim(
                id=1, independent=True, dependencies=[], method_claim=False,
                text=(
                    "A control system based on ultra-wideband connection, "
                    "comprising a radar unit configured to generate "
                    "real-time driving environment information, wherein the "
                    "ultra-wideband connection is established and a signal "
                    "is generated from the real-time driving environment "
                    "information."
                ),
            ),
        ]
        terms = [i["term"] for i in check_antecedent_basis(claims)]
        assert "ultra-wideband connection" not in terms, terms
        assert "real-time driving environment information" not in terms, terms

    def test_bare_noun_introduction_cross_claim(self):
        """R4 (#71): a multi-word term introduced article-less in a parent
        claim gives a child-claim `the X` antecedent basis."""
        claims = [
            Claim(id=1, independent=True, dependencies=[], method_claim=False,
                  text="An ESD circuit configured to control electrostatic "
                       "energy discharged from a control node."),
            Claim(id=2, independent=False, dependencies=[1], method_claim=False,
                  text="The circuit of claim 1, wherein the electrostatic "
                       "energy at the control node is monitored."),
        ]
        terms = [i["term"] for i in check_antecedent_basis(claims)
                 if i["claim_id"] == 2]
        assert "electrostatic energy" not in terms, terms

    def test_bare_noun_intro_genuine_defect_still_flagged(self):
        """A genuinely-undefined multi-word term (no prior mention at all)
        must still be flagged — the rescue requires a real prior occ."""
        claims = [
            Claim(id=1, independent=True, dependencies=[], method_claim=False,
                  text="An apparatus comprising a base."),
            Claim(id=2, independent=False, dependencies=[1], method_claim=False,
                  text="The apparatus of claim 1, wherein the thermal relay "
                       "module is engaged."),
        ]
        terms = [i["term"] for i in check_antecedent_basis(claims)
                 if i["claim_id"] == 2]
        assert any("thermal relay module" in t for t in terms), terms

    def test_finite_verb_not_overcaptured_r3(self):
        """R3 (issues #86–#89, #92): `presents` / `constitutes` / `flows`
        / `uses` must terminate the noun-phrase capture, not bleed in."""
        claims = [
            Claim(
                id=1,
                text=(
                    "A device wherein the leakage inspection region "
                    "presents a defect, the annular groove constitutes a "
                    "seal, the storage solution flows through a channel, "
                    "and the control unit uses a sensor."
                ),
                independent=True,
                method_claim=False,
            ),
        ]
        terms = [i["term"] for i in check_antecedent_basis(claims)
                 if i["claim_id"] == 1]
        for verb in ("presents", "constitutes", "flows", "uses"):
            for t in terms:
                assert verb not in t, f"{verb!r} bled into term: {t!r}"
        # Clean head nouns still surface (no intro for them here).
        assert "leakage inspection region" in terms, terms
        assert "annular groove" in terms, terms

    def test_finite_verb_not_overcaptured_r8(self):
        """R8 (issue #152): `occur` / `approach` are event-domain finite
        verbs that bled through `<noun phrase> [adverb] <verb>` claim
        clauses (PLL / clock-domain drafters). `successively` (adverb)
        is now also stripped from NP tails via _ADVERB_STOPS. Word
        boundary semantics preserve `non-naturally occurring pathogen`
        (gerund, different word from base `occur`)."""
        claims = [
            Claim(
                id=1,
                text=(
                    "A PLL wherein the master comparison signal occur "
                    "at preset intervals, and the phase-delayed clock "
                    "signal successively approach the locked frequency."
                ),
                independent=True,
                method_claim=False,
            ),
        ]
        terms = [i["term"] for i in check_antecedent_basis(claims)
                 if i["claim_id"] == 1]
        for verb in ("occur", "approach", "successively"):
            for t in terms:
                assert verb not in t, f"{verb!r} bled into term: {t!r}"
        # Head nouns still surface as flagged refs (no intro in synthetic).
        assert any("master comparison signal" in t for t in terms), terms
        assert any("phase-delayed clock signal" in t for t in terms), terms

    def test_finite_verb_not_overcaptured_r7(self):
        """R7 (issues #120 / #127 / #128 / #135): `exceeds` / `extend` /
        `constitute` / `stays` must terminate NP capture. R2/R3 covered
        the 3sg `extends`/`constitutes` but left base-form gaps that
        bled through `<noun> exceeds X` / `<noun> jointly constitute X`
        / `<noun> stays in X` claim clauses."""
        claims = [
            Claim(
                id=1,
                text=(
                    "An apparatus wherein the guiding pattern exceeds a "
                    "preset range, the second mounting portion extend "
                    "toward each other, the encapsulation layer jointly "
                    "constitute an integrated structure, and the second "
                    "magnetic component stays in the first position."
                ),
                independent=True,
                method_claim=False,
            ),
        ]
        terms = [i["term"] for i in check_antecedent_basis(claims)
                 if i["claim_id"] == 1]
        for verb in ("exceeds", "extend", "constitute", "stays"):
            for t in terms:
                assert verb not in t, f"{verb!r} bled into term: {t!r}"
        # Head nouns still surface (no intro for them in this fragment).
        assert any("guiding pattern" in t for t in terms), terms
        assert any("second mounting portion" in t for t in terms), terms
        assert any("encapsulation layer" in t for t in terms), terms
        assert any("second magnetic component" in t for t in terms), terms

    def test_accounts_for_verb_not_overcaptured_r5(self):
        """R5 (issues #98 / #99): `<noun> accounts for X%` — `accounts` is a
        3sg finite verb in this pattern and must terminate NP capture. The
        lookahead `accounts(?=\\s+for)` distinguishes the verb from the
        bare-noun usage tested separately below."""
        claims = [
            Claim(
                id=1,
                text="A sintered body comprising silicon carbide and an alumina.",
                independent=True, method_claim=False,
            ),
            Claim(
                id=2,
                text=(
                    "The sintered body of claim 1, wherein the alumina "
                    "accounts for at least 5% of a total mass."
                ),
                independent=False, dependencies=[1], method_claim=False,
            ),
        ]
        terms = [i["term"] for i in check_antecedent_basis(claims)]
        for t in terms:
            assert "accounts" not in t, f"`accounts` bled into term: {t!r}"

    def test_accounts_noun_usage_preserved_r5(self):
        """R5 negative-control: bare-noun `accounts` (`financial accounts`,
        `accounts receivable`) must NOT be silenced — the verb-gating
        lookahead `(?=\\s+for)` discriminates."""
        claims = [
            Claim(
                id=1,
                text="A method comprising managing financial accounts.",
                independent=True, method_claim=False,
            ),
            Claim(
                id=2,
                text=(
                    "The method of claim 1, wherein the financial accounts "
                    "are encrypted."
                ),
                independent=False, dependencies=[1], method_claim=False,
            ),
        ]
        # Resolves cleanly — intro `financial accounts` matches ref the same.
        assert check_antecedent_basis(claims) == []

    def test_unicode_hyphen_np_span_r5(self):
        """R5 (issues #97 / #103): U+2010 HYPHEN and U+2011 NON-BREAKING
        HYPHEN must be NP-internal joiners, same as ASCII U+002D. Drafters
        using non-breaking hyphens (`large‑size silicon carbide particle`)
        previously had NP captures truncated at the hyphen."""
        claims = [
            Claim(
                id=1,
                text=(
                    "A sintered body comprising silicon carbide particles "
                    "of various sizes."
                ),
                independent=True, method_claim=False,
            ),
            Claim(
                id=2,
                text=(
                    "The sintered body of claim 1, wherein the large‑size "
                    "silicon carbide particle is greater than the medium‑size "
                    "silicon carbide particle."
                ),
                independent=False, dependencies=[1], method_claim=False,
            ),
        ]
        terms = [i["term"] for i in check_antecedent_basis(claims)]
        # NP span across U+2011 — emit full compounds, not truncated `large`/`medium`
        assert all(t not in ("large", "medium") for t in terms), terms
        assert any("large‑size" in t for t in terms), terms

    def test_ascii_hyphen_unchanged_r5(self):
        """R5 negative-control: ASCII `-` behavior unchanged."""
        claims = [
            Claim(
                id=1,
                text="A device comprising a high-voltage relay.",
                independent=True, method_claim=False,
            ),
            Claim(
                id=2,
                text="The device of claim 1, wherein the high-voltage relay is closed.",
                independent=False, dependencies=[1], method_claim=False,
            ),
        ]
        assert check_antecedent_basis(claims) == []

    def test_markush_at_least_one_of_intros_r6(self):
        """R6 (missed-triage on #98/#99): a Markush enumeration
        `at least one of A, B, and C` introduces each member as an
        antecedent under MPEP § 2173.05(e). Mirrors the silicon-carbide
        composite case where claim 1 says `at least one of silicon carbide,
        alumina, and silica` — `the alumina` and `the silica` in dep
        claims resolve cleanly."""
        claims = [
            Claim(
                id=1,
                text=(
                    "A composite comprising a metallic copper phase and a "
                    "ceramic phase, wherein the ceramic phase is composed "
                    "of at least one of silicon carbide, alumina, and silica."
                ),
                independent=True, method_claim=False,
            ),
            Claim(
                id=5,
                text=(
                    "The composite of claim 1, wherein the alumina accounts "
                    "for at least 5% of total mass."
                ),
                independent=False, dependencies=[1], method_claim=False,
            ),
            Claim(
                id=7,
                text=(
                    "The composite of claim 1, wherein the silica accounts "
                    "for 1% to 20% of total mass."
                ),
                independent=False, dependencies=[1], method_claim=False,
            ),
        ]
        assert check_antecedent_basis(claims) == []

    def test_markush_one_of_no_at_least_r6(self):
        """R6 — bare `one of A, B, and C` also triggers list-context
        extraction. Common in shorter Markush expressions."""
        claims = [
            Claim(
                id=1,
                text=(
                    "A signal processor selecting one of bone, tissue, "
                    "and nerves for ultrasound emission."
                ),
                independent=True, method_claim=False,
            ),
            Claim(
                id=2,
                text="The signal processor of claim 1, wherein the bone is targeted.",
                independent=False, dependencies=[1], method_claim=False,
            ),
        ]
        terms = [i["term"] for i in check_antecedent_basis(claims)]
        assert "bone" not in terms, terms

    def test_one_or_more_of_intros_r6(self):
        """R6 — `one or more of A, B, and C` variant."""
        claims = [
            Claim(
                id=1,
                text=(
                    "A method comprising selecting one or more of methanol, "
                    "ethanol, and propanol as a solvent."
                ),
                independent=True, method_claim=False,
            ),
            Claim(
                id=2,
                text="The method of claim 1, wherein the ethanol is anhydrous.",
                independent=False, dependencies=[1], method_claim=False,
            ),
        ]
        terms = [i["term"] for i in check_antecedent_basis(claims)]
        assert "ethanol" not in terms, terms


class TestTransitionsRegexWherein:
    """`_TRANSITIONS` recognizes `wherein` (no colon) as a preamble/body boundary."""

    def test_wherein_no_colon_matches(self):
        text = "1. An apparatus comprising a widget, wherein the widget is blue."
        match = _TRANSITIONS.search(text)
        assert match is not None
        # Preamble (text before the matched transition) should not include 'wherein'.
        preamble = text[: match.start()]
        body = text[match.end():]
        assert "wherein" not in preamble
        assert "the widget is blue" in body

    def test_comprising_with_colon_still_matches_first(self):
        # When both a colon-style transition and a `wherein` exist, the
        # leftmost (colon-style) match wins so existing behavior is preserved.
        text = "1. An apparatus comprising: a widget, wherein the widget is blue."
        match = _TRANSITIONS.search(text)
        assert match is not None
        preamble = text[: match.start()]
        body = text[match.end():]
        assert "comprising" not in body  # transition was consumed
        assert "a widget, wherein the widget is blue" in body
        assert "An apparatus" in preamble

    def test_no_transition_no_match(self):
        text = "1. An apparatus that is blue."
        assert _TRANSITIONS.search(text) is None


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
        """'selected from the group comprising A, B, and C' -> FIX (improper Markush per MPEP § 2117)."""
        claims = [Claim(id=1, text="A composition comprising a metal selected from the group comprising gold, silver, and copper.", independent=True)]
        results = check_special_claim_formats(claims)
        markush = [r for r in results if r.message_key == "claims.markushOpenTransition"]
        assert len(markush) == 1
        assert markush[0].status == "amend"
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
