# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""Tests for patentlint.analysis.claims."""

from patentlint.models import Claim
from patentlint.parser.claims import parse_claims, parse_dependencies
from patentlint.analysis.utils import strip_contextual_verb
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
        # Claim 3 is multi-dep (depends on 1 or 2), but 1 and 2 are single-dep - no violation.
        claims = [
            Claim(id=1, text="1. A method.", independent=True, method_claim=True),
            Claim(id=2, text="2. An apparatus.", independent=True, method_claim=False),
            Claim(id=3, text="3. The method/apparatus of claim 1 or 2.", independent=False,
                  method_claim=True, dependencies=[1, 2], multiple_dependent=True),
        ]
        assert find_chained_multi_dependents(claims) == []

    def test_chained_violation_detected(self):
        # Claim 3 is multi-dep; claim 4 is multi-dep that depends on claim 3 - § 112(e) violation.
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
        """'a base' introduces, 'the base' references - no issue."""
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
        antecedent basis - MPEP § 2173.05(e)."""
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
        must still be flagged - the rescue requires a real prior occ."""
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
        """R3 (issues #86-#89, #92): `presents` / `constitutes` / `flows`
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

    def test_finite_verb_not_overcaptured_r11(self):
        """R11 (issues #188 / #189 / #190 / #192): `passes` (3sg) is the
        matrix verb in `the <noun> passes through the <hole>` clauses;
        `correspond` (base form, plural subject) is the gap left by the
        existing 3sg `corresponds`. The intervening `respectively` adverb
        is stripped by _ADVERB_STOPS. Neither may bleed into the term."""
        claims = [
            Claim(
                id=1,
                text=(
                    "An apparatus wherein the pressing member passes through "
                    "the first through hole, the first extension arm passes "
                    "through two adjacent ones of the first outer sidewalls, "
                    "and the two poles respectively correspond in position "
                    "to the first inner surface."
                ),
                independent=True,
                method_claim=False,
            ),
        ]
        terms = [i["term"] for i in check_antecedent_basis(claims)
                 if i["claim_id"] == 1]
        for tok in ("passes", "correspond", "respectively"):
            for t in terms:
                assert tok not in t, f"{tok!r} bled into term: {t!r}"
        # Head nouns still surface as clean refs (no intro in this fragment).
        assert any("pressing member" in t for t in terms), terms
        assert any("first extension arm" in t for t in terms), terms
        assert any("two poles" in t for t in terms), terms
        # `bypasses` / `corresponds` / `corresponding` are unaffected
        # (word-boundary semantics: `passes` is not matched inside
        # `bypasses`, and the 3sg/-ing forms are separate alternatives).
        from patentlint.analysis.utils import _DEFINITE_REF, clean_noun_phrase
        caps = [clean_noun_phrase(m.group("noun").strip())
                for m in _DEFINITE_REF.finditer("the second clutch bypasses the gear")]
        assert "second clutch bypasses" in caps, caps

    def test_finite_verb_not_overcaptured_r12(self):
        """R12 (issues #205 / #200 / #218 / #216-220): `depends` / `stores`
        (3sg verbs) and the temporal adverb `again` must terminate NP
        capture. `not` and `refers` were deliberately withheld
        (legit_drift) - not covered here."""
        claims = [
            Claim(
                id=1,
                text=(
                    "An apparatus wherein the virtual plane depends on a "
                    "pose, the storage circuit further stores a plurality "
                    "of records, the host stores a pairing setting, and "
                    "transmits the control command again to cause a switch."
                ),
                independent=True,
                method_claim=False,
            ),
        ]
        terms = [i["term"] for i in check_antecedent_basis(claims)
                 if i["claim_id"] == 1]
        for tok in ("depends", "stores", "again"):
            for t in terms:
                assert tok not in t, f"{tok!r} bled into term: {t!r}"
        assert any("virtual plane" in t for t in terms), terms
        assert any("storage circuit" in t for t in terms), terms
        assert any("control command" in t for t in terms), terms
        # Guard: the logic-gate noun `the NOT gate` is preserved (no `not`
        # stop-word), and `refers` is NOT stripped (legit labels protected).
        from patentlint.analysis.utils import _DEFINITE_REF, clean_noun_phrase
        not_caps = [clean_noun_phrase(m.group("noun").strip())
                    for m in _DEFINITE_REF.finditer("the not gate receives a signal")]
        assert "not gate" in not_caps, not_caps

    def test_finite_verb_not_overcaptured_r13(self):
        """R13 (#204): `refers` (3sg) must terminate NP capture. `not` is
        NOT a stop word - `the strand not conjugated to the label` is a
        legitimate negative-limitation noun phrase."""
        claims = [
            Claim(
                id=1,
                text="An apparatus wherein the reference point refers to a center of a head.",
                independent=True, method_claim=False,
            ),
        ]
        terms = [i["term"] for i in check_antecedent_basis(claims)
                 if i["claim_id"] == 1]
        for t in terms:
            assert "refers" not in t, f"`refers` bled into term: {t!r}"
        assert any("reference point" in t for t in terms), terms
        # Guard: `not` is NOT a stop word - it survives NP capture (the term
        # retains `not`, rather than truncating to `strand`), so a
        # negative-limitation noun phrase is not split at `not`.
        from patentlint.analysis.utils import _DEFINITE_REF, clean_noun_phrase
        caps = [clean_noun_phrase(m.group("noun").strip())
                for m in _DEFINITE_REF.finditer(
                    "the strand not conjugated to the label is detected")]
        assert any("strand not" in c for c in caps), caps

    def test_conditional_removes_stops_r26(self):
        """R26 (asymmetry probe): `conditional` (post-nominal predicative adj)
        and `removes` (3sg verb) terminate NP capture. `operative` is NOT a
        stop (withheld - the functional `operative to <verb>` clause)."""
        from patentlint.analysis.utils import _DEFINITE_REF, clean_noun_phrase

        def cap(text):
            return [clean_noun_phrase(m.group("noun").strip())
                    for m in _DEFINITE_REF.finditer(text)]

        assert any("trace enabler" in c and "conditional" not in c
                   for c in cap("the trace enabler conditional on a flag"))
        assert any("second direction" in c and "removes" not in c
                   for c in cap("the second direction removes the layer"))
        # operative stays attached (withheld to preserve `operative to` intros)
        assert any("operative" in c
                   for c in cap("the amplifier unit operative to amplify"))

    def test_intends_occurs_matches_fails_stops_r27(self):
        """R27 (asymmetry probe): `intends`/`occurs` (pure verbs) always stop;
        `matches`/`fails` stop ONLY in the verb-object lookahead pattern, so the
        noun senses (`the matches`, `the failures`) are preserved."""
        from patentlint.analysis.utils import _DEFINITE_REF, clean_noun_phrase

        def cap(text):
            return [clean_noun_phrase(m.group("noun").strip())
                    for m in _DEFINITE_REF.finditer(text)]

        assert any("first customer" in c and "intends" not in c
                   for c in cap("the first customer intends to buy"))
        assert any("serosal tissue" in c and "occurs" not in c
                   for c in cap("the serosal tissue occurs at a site"))
        assert any("usage fraction" in c and "fails" not in c
                   for c in cap("the usage fraction fails to exceed a limit"))
        assert any("metadata tag" in c and "matches" not in c
                   for c in cap("the metadata tag matches the second tag"))
        # R28: sends/continues (pure verbs); sets gated; results/remains withheld
        assert any("display area" in c and "continues" not in c
                   for c in cap("the display area continues to render"))
        assert any("cloud service application" in c and "sends" not in c
                   for c in cap("the cloud service application sends a packet"))
        # `results in` ambiguous → NOT stripped (withheld)
        assert any("test results" in c
                   for c in cap("the test results in the database are stored"))

    def test_spec_support_shares_passes_correspond_stop_r11(self):
        """R11 cross-CHECK (#192): the spec-support noun-phrase extractor
        shares `_NP_CORE`/`_STOP_WORDS`, so the same `<arm> passes`
        over-capture is fixed on the §112(a) engine for free."""
        from patentlint.analysis.utils import extract_noun_phrases
        phrases = extract_noun_phrases(
            "the first extension arm passes through two adjacent ones of "
            "the first outer sidewalls"
        )
        for p in phrases:
            assert "passes" not in p, f"`passes` bled into spec-support phrase: {p!r}"
        assert any("first extension arm" in p for p in phrases), phrases

    def test_accounts_for_verb_not_overcaptured_r5(self):
        """R5 (issues #98 / #99): `<noun> accounts for X%` - `accounts` is a
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
        `accounts receivable`) must NOT be silenced - the verb-gating
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
        # Resolves cleanly - intro `financial accounts` matches ref the same.
        assert check_antecedent_basis(claims) == []

    def test_r39_gated_verb_prep_stops_not_overcaptured(self):
        """R39 (reports #444/#435/#436): `surround`/`takes`/`via` terminate NP
        capture in the verb/preposition reading (determiner/cardinal-gated)."""
        # #444 - base-form `surround` (coordinate subject) + object determiner.
        c = [
            Claim(id=18, text=(
                "A power module comprising a first power converter, a first "
                "magnetic column body, and a coil, wherein a primary coil and a "
                "secondary coil of a first transformer of the first power "
                "converter surround the first magnetic column body."
            ), independent=True, method_claim=False),
        ]
        assert not any("surround" in i["term"] for i in check_antecedent_basis(c))
        # #435 - `takes up` matrix verb.
        c = [
            Claim(id=7, text="A bag comprising a stress buffer pattern.",
                  independent=True, method_claim=False),
            Claim(id=9, text=(
                "The bag of claim 7, wherein the stress buffer pattern takes up "
                "20% to 80% of a total area."
            ), independent=False, dependencies=[7], method_claim=False),
        ]
        assert not any("takes" in i["term"] for i in check_antecedent_basis(c))
        # #436 - preposition `via` before a cardinal.
        c = [
            Claim(id=10, text="A method comprising forming a bottom sealing structure.",
                  independent=True, method_claim=False),
            Claim(id=11, text=(
                "The method of claim 10, forming a section of the bottom sealing "
                "structure via two sealing operations."
            ), independent=False, dependencies=[10], method_claim=False),
        ]
        assert not any("via" in i["term"] for i in check_antecedent_basis(c))

    def test_r41_directional_adverb_and_enter(self):
        """R41 (#489/#497/#499): trailing directional adverb + `enter` matrix verb."""
        from patentlint.analysis.utils import _DEFINITE_REF

        def heads(text):
            return [m.group("noun") for m in _DEFINITE_REF.finditer(text)]

        # #497/#499 - ADVERBIAL position: the stop fires, the head survives.
        # (`gas conveyed` is a separate, pre-existing past-participle over-capture
        # in the same span - not what this round touches.)
        assert heads("eject the gas conveyed by the gas conduit outward.") == [
            "gas conveyed", "gas conduit"
        ]
        assert heads("moves the piston outward and downward") == ["piston"]
        # #489-f2 - matrix verb with a BARE object, so no determiner gate could fire.
        assert heads(
            "a portion of the thermal interface material enter pores of the region"
        ) == ["thermal interface material", "region"]
        assert heads("the data enters the buffer") == ["data", "buffer"]

    def test_r42_suitable_and_rotates(self):
        """R42 (#506/#507): trailing `suitable` + `rotate`/`rotates` matrix verb."""
        from patentlint.analysis.utils import _DEFINITE_REF, extract_introductions

        def heads(text):
            return [m.group("noun") for m in _DEFINITE_REF.finditer(text)]

        # #506 - the preamble frame `An <element> suitable for <use>, comprising:`
        # must key the intro on the element, not on the adjective.
        intros = list(extract_introductions(
            "An uninterruptible power supply suitable for a discontinuous power "
            "supply environment, comprising: a permanent magnet motor."
        ))
        assert "uninterruptible power supply" in intros
        assert "uninterruptible power supply suitable" not in intros

        # #507 - the matrix verb terminates the capture at the subject.
        assert heads(
            "wherein the permanent magnet motor rotates due to inertia"
        ) == ["permanent magnet motor"]
        assert heads("the drive member rotates one complete revolution") == [
            "drive member"
        ]

    def test_r42_attributive_and_participle_preserved(self):
        """R42 negative-controls - where a broader stop would have been an FN.

        `suitable` is only ever popped from the END of a phrase, so the
        attributive use survives (this covers the three examiner-confirmed
        terms `the suitable antigen` / `the suitable substrate` / `the suitable
        concentration of anti-ige`). The participle `rotating` is deliberately
        NOT a stop - it is attributive in `the rotating shaft`."""
        from patentlint.analysis.utils import _DEFINITE_REF, clean_noun_phrase

        def heads(text):
            return [m.group("noun") for m in _DEFINITE_REF.finditer(text)]

        assert heads("the suitable antigen is bound") == ["suitable antigen"]
        assert heads("the suitable substrate is coated") == ["suitable substrate"]
        assert clean_noun_phrase("suitable concentration of anti-ige") == (
            "suitable concentration of anti-ige"
        )
        # The participle keeps its head noun, and the finite form still cuts.
        assert heads("the rotating shaft is coupled to the housing") == [
            "rotating shaft", "housing"
        ]
        assert heads("the rotating drive member rotates two complete turns") == [
            "rotating drive member"
        ]

    def test_r41_attributive_and_noun_senses_preserved(self):
        """R41 negative-controls - this is where a BARE stop would have been an FN.

        In attributive position the -ward token is followed by its head noun, not
        by punctuation or a conjunction, so the gate does not fire. Includes the
        examiner-confirmed `the radially inward direction`."""
        from patentlint.analysis.utils import _DEFINITE_REF

        def heads(text):
            return [m.group("noun") for m in _DEFINITE_REF.finditer(text)]

        assert heads("the outward surface is flat") == ["outward surface"]
        assert heads("the forward end of the shaft") == ["forward end", "shaft"]
        assert heads("the downward force and the spring") == ["downward force", "spring"]
        # Examiner-confirmed term (us_examiner_legit.json) - must stay whole.
        assert heads("the radially inward direction of the hub") == [
            "radially inward direction", "hub"
        ]
        # The fixed UI compound carved out of the `enter` stop - a bare stop was
        # measured to drop this entirely.
        assert heads("the enter key is pressed") == ["enter key"]
        assert heads("the enter button") == ["enter button"]

    def test_r39_noun_senses_preserved(self):
        """R39 negative-controls: the noun senses are FN-safe.
        - `via` the semiconductor element (head, followed by a verb) is kept.
        - `surround`/`takes` gates fire only before a determiner/particle, so a
          `via a` gerund reference (gold-legit) is NOT cut."""
        # Semiconductor `via` as head resolves against its intro (not silenced).
        c = [
            Claim(id=1, text="A device comprising a first via and a second via.",
                  independent=True, method_claim=False),
            Claim(id=2, text="The device of claim 1, wherein the first via is filled.",
                  independent=False, dependencies=[1], method_claim=False),
        ]
        assert check_antecedent_basis(c) == []
        # `via a <NP>` (article, not cardinal) is NOT gated - `via` stays in the
        # captured reference (the gold-legit `the extracting performed via a …`
        # shape that validate_fix protects).
        c = [
            Claim(id=1, text="A method.", independent=True, method_claim=False),
            Claim(id=2, text=(
                "The method of claim 1, wherein the extracting performed via a "
                "solvent is repeated."
            ), independent=False, dependencies=[1], method_claim=False),
        ]
        assert any("via" in i["term"] for i in check_antecedent_basis(c))

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
        # NP span across U+2011 - emit full compounds, not truncated `large`/`medium`
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
        alumina, and silica` - `the alumina` and `the silica` in dep
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
        """R6 - bare `one of A, B, and C` also triggers list-context
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
        """R6 - `one or more of A, B, and C` variant."""
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
        """Dependent claim with 'wherein' only - parent has 'comprising' → PASS."""
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

    def test_transition_before_colon_not_at_boundary_passes(self):
        """#212/#213: a transition phrase that sits earlier in the preamble
        ahead of a body-introducing colon (not immediately before it) must
        still count. Previously the colon-gate suppressed the fallback and
        these were flagged as missing a transition."""
        claims = [
            # #212 - `comprising performing, by a device, … processes:`
            Claim(
                id=1,
                text=(
                    "A power planning method for reducing timing impacts, "
                    "comprising performing, by a computing device, the "
                    "following processes:\ncomparing values; adjusting a plan."
                ),
                independent=True, method_claim=True,
            ),
            # #213 - CRM `… medium comprising a plurality of instructions "
            # that, when executed, cause the processor to:`
            Claim(
                id=15,
                text=(
                    "A non-transitory computer-readable medium, the medium "
                    "comprising a plurality of instructions that, when "
                    "executed by a processor, cause the processor to: "
                    "compare values; adjust a plan."
                ),
                independent=True, method_claim=False,
            ),
        ]
        results = check_claim_transitions(claims)
        assert all(r.status == "pass" for r in results), [r.message for r in results]

    def test_colon_with_no_pre_colon_transition_still_amends(self):
        """Guard: a real missing-transition (colon present, but no transition
        phrase before it) is still flagged; an incidental `having` INSIDE the
        colon-introduced body must not rescue it."""
        claims = [
            Claim(id=1, text="A method for processing: step A; step B.", independent=True, method_claim=True),
            Claim(id=2, text="A device for control: a module having a memory; a processor.", independent=True),
        ]
        results = check_claim_transitions(claims)
        amended = [r for r in results if r.status == "amend"]
        assert len(amended) == 2, [r.message for r in results]

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


class TestR34ReferenceSideOverCapture:
    """R34 (2026-07-18) - reports #391 / #397 / #400.

    Three reference-side over-capture mechanisms. Each test pairs the FP that
    must be silenced with the FN-guard case that must keep firing.
    """

    @staticmethod
    def _terms(claims):
        return {f["term"] for f in check_antecedent_basis(claims)}

    def test_sandwich_finite_verb_gated_on_object_determiner(self):
        """`the first die sandwich the first ...` - verb, not a `die sandwich`."""
        claims = [
            Claim(id=1, independent=True, text=(
                "A package comprising a first die, a third die and a first "
                "sandwiching portion."
            )),
            Claim(id=7, independent=False, dependencies=[1], text=(
                "The package of claim 1, wherein the third die and the first "
                "die sandwich the first sandwiching portion."
            )),
        ]
        assert "first die sandwich" not in self._terms(claims)

    def test_sandwich_noun_reading_still_flagged(self):
        """FN-guard: no object determiner follows -> genuine noun, stays flagged."""
        claims = [
            Claim(id=1, independent=True, text="A package comprising a first die."),
            Claim(id=7, independent=False, dependencies=[1], text=(
                "The package of claim 1, wherein the die sandwich is mounted "
                "on a substrate."
            )),
        ]
        assert "die sandwich" in self._terms(claims)

    def test_trailing_manner_adverb_stripped_after_verb_stop(self):
        """`the ports closely join the other ...` -> `ports`, not `ports closely join`."""
        claims = [
            Claim(id=2, independent=True, text="A device comprising a substrate having two ports."),
            Claim(id=3, independent=False, dependencies=[2], text=(
                "The device of claim 2, further comprising a material wrapping "
                "around the ports to make one of the ports closely join the "
                "other of the ports."
            )),
        ]
        assert "ports closely join" not in self._terms(claims)

    def test_ly_noun_is_not_treated_as_adverb(self):
        """FN-guard: `assembly` ends in -ly but is a noun - must survive."""
        from patentlint.analysis.utils import strip_trailing_adverb
        assert strip_trailing_adverb("drive assembly") == "drive assembly"
        assert strip_trailing_adverb("power supply") == "power supply"
        assert strip_trailing_adverb("ports closely") == "ports"

    def test_partitive_past_participle_pronoun_skipped(self):
        """`the switched one of the plurality of channels` heads on a pronoun."""
        claims = [
            Claim(id=1, independent=True, text=(
                "An apparatus comprising a plurality of channels, wherein a "
                "voltage is converted through a scale corresponding to the "
                "switched one of the plurality of channels."
            )),
        ]
        assert "switched one" not in self._terms(claims)

    def test_partitive_ordinal_singular_still_flagged(self):
        """FN-guard: the examiner corpus confirms `the first one` as a real
        defect, so an ordinal-modified singular must NOT be skipped."""
        from patentlint.analysis.claims import _is_partitive_pronoun_head
        assert _is_partitive_pronoun_head("remaining ones") is True
        assert _is_partitive_pronoun_head("switched one") is True
        for examiner_term in ("first one", "at least one", "respective one", "current one"):
            assert _is_partitive_pronoun_head(examiner_term) is False

class TestR35SwitchesAndGerundHead:
    """R35 (2026-07-20) - two US classes unblocked by the EdgeXpert examiner
    FN-guard (tests/eval/examiner_fn_guard.py). Both had been deferred for
    three sessions with the note "queued until the examiner guard is runnable".
    """

    def test_switches_finite_verb_stripped_before_determiner(self):
        # Report #386/#401: `the selection line switches to the channel`.
        assert strip_contextual_verb(
            "the selection line switches", "to the channel"
        ) == "the selection line"

    def test_switches_noun_survives_infinitive(self):
        # Examiner app 18599360: `the main switches TO CONTROL the ...`.
        # A confirmed real 112(b) term - the gate must not reach it.
        assert strip_contextual_verb(
            "the main switches", "to control the commutation-induced current"
        ) == "the main switches"

    def test_switches_noun_survives_predicate(self):
        # Examiner app 18573531: `the semi-conductor switches ARE DESIGNED ...`.
        assert strip_contextual_verb(
            "the semi-conductor switches", "are designed as GaN power switches"
        ) == "the semi-conductor switches"

    def test_gerund_head_step_introduces_the_act(self):
        # Report #336/#337: the method step names the act, so `the bonding`
        # in a later claim has an antecedent.
        claims = parse_claims(
            "1. A method of forming a package, comprising: bonding a first "
            "die to a second die; and encapsulating the first die.\n"
            "5. The structure according to claim 1, wherein the bonding is "
            "metal-to-metal direct bonding or eutectic bonding."
        )
        terms = [f["term"] for f in check_antecedent_basis(claims)]
        assert "bonding" not in terms

    def test_gerund_head_absent_still_fires(self):
        # NEGATIVE CONTROL - without the step there is no antecedent, so the
        # finding must survive. This is the FN-safety of the mechanism.
        claims = parse_claims(
            "1. An apparatus comprising a first die and a second die.\n"
            "5. The apparatus of claim 1, wherein the bonding is eutectic "
            "bonding."
        )
        terms = [f["term"] for f in check_antecedent_basis(claims)]
        assert "bonding" in terms

    def test_non_eventive_ing_noun_never_introduced(self):
        # `housing` / `opening` are ordinary -ing NOUNS and are examiner-
        # rejected terms in the ground truth. A mid-clause participial use
        # must never register an introduction for them.
        from patentlint.analysis.utils import extract_gerund_head_intros
        assert extract_gerund_head_intros(
            "the device includes a chamber housing the components"
        ) == []
        assert extract_gerund_head_intros(
            "an apparatus comprising a housing and an opening"
        ) == []
