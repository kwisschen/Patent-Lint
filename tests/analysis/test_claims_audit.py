# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""Adversarial tests for analysis/claims — Phase 4 B6 audit."""

from patentlint.models import Claim
from patentlint.analysis.claims import (
    check_antecedent_basis,
    detect_means_plus_function,
)


class TestAntecedentBasisAudit:
    def test_said_with_prior_introduction(self):
        """'said base' with prior 'a base' should NOT be flagged."""
        claims = [Claim(id=1, text="A device comprising a base, wherein said base is flat.", independent=True, method_claim=False)]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "base" not in terms

    def test_chain_walk_grandchild(self):
        """Grandchild claim should inherit basis from grandparent."""
        claims = [
            Claim(id=1, text="A device comprising a base plate.", independent=True, method_claim=False),
            Claim(id=2, text="The device of claim 1, further comprising a cover.", independent=False, method_claim=False, dependencies=[1]),
            Claim(id=3, text="The device of claim 2, wherein the base plate is metal.", independent=False, method_claim=False, dependencies=[2]),
        ]
        issues = check_antecedent_basis(claims)
        claim3_terms = [i["term"] for i in issues if i["claim_id"] == 3]
        assert "base plate" not in claim3_terms

    def test_skip_fig_references(self):
        """References to 'the figure' should not be flagged."""
        claims = [Claim(id=1, text="A method as shown in the figure.", independent=True, method_claim=True)]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        # Should be filtered (starts with 'fig')
        assert not any("figure" in t for t in terms)


class TestMeansPlusFunctionAudit:
    def test_by_means_of_excluded(self):
        """'by means of' is prepositional, not 112(f)."""
        claims = [Claim(id=1, text="A device connected by means of a bolt.", independent=True, method_claim=False)]
        assert detect_means_plus_function(claims) == []

    def test_mechanism_for_detected(self):
        claims = [Claim(id=1, text="A device comprising a mechanism for fastening components.", independent=True, method_claim=False)]
        assert detect_means_plus_function(claims) == [1]

    def test_means_without_gerund_not_detected(self):
        """'means' without 'for [gerund]' should not trigger."""
        claims = [Claim(id=1, text="A device with electrical means.", independent=True, method_claim=False)]
        assert detect_means_plus_function(claims) == []


class TestAntecedentBasisIntroPatterns:
    """Bug 2: Expanded introduction patterns for antecedent basis."""

    def test_at_least_one(self):
        """'at least one conductive component' → 'the conductive component' → no flag."""
        claims = [Claim(
            id=1,
            text="A mechanism comprising at least one conductive component, wherein the conductive component is metal.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "conductive component" not in terms

    def test_one_or_more(self):
        """'one or more processors' → 'the processors' → no flag."""
        claims = [Claim(
            id=1,
            text="A system comprising one or more processors, wherein the processors execute instructions.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "processors" not in terms

    def test_plurality_of(self):
        """'a plurality of connection cables' → 'the connection cables' → no flag."""
        claims = [Claim(
            id=1,
            text="A device comprising a plurality of connection cables, wherein the connection cables are flexible.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "connection cables" not in terms

    def test_ordinal_first(self):
        """'a first engaging structure' → 'the first engaging structure' → no flag.

        Commit 7 dropped the explicit ``a\\s+(?:first|second|third)\\s+``
        prefix arm so ordinals fall through to the generic ``a/an`` arm and
        are captured by ``_NP_CORE`` as the leading word of the noun phrase.
        The introduction now reads "first engaging structure" and matches
        the reference exactly under word-boundary equivalence.
        """
        claims = [Claim(
            id=1,
            text="A device comprising a first engaging structure, wherein the first engaging structure is rigid.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "first engaging structure" not in terms

    def test_ordinal_fourth(self):
        """Ordinals beyond the old 'first/second/third' list (e.g., fourth)
        must also be preserved in the captured noun phrase.
        """
        claims = [Claim(
            id=1,
            text="A device comprising a fourth bracket, wherein the fourth bracket is rigid.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "fourth bracket" not in terms

    def test_ordinal_tenth(self):
        """Tenth-and-higher ordinals must work too (no explicit list cap)."""
        claims = [Claim(
            id=1,
            text="A system comprising a tenth processor, wherein the tenth processor handles overflow.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "tenth processor" not in terms

    def test_bare_numeral_two(self):
        """'two conductive components' → 'the two conductive components' → no flag."""
        claims = [Claim(
            id=1,
            text="A mechanism comprising two conductive components, wherein the conductive components are aligned.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "conductive components" not in terms

    def test_said_with_prior_a(self):
        """'said movable component' with prior 'a movable component' → no flag."""
        claims = [Claim(
            id=1,
            text="A device comprising a movable component, wherein said movable component slides.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "movable component" not in terms

    def test_no_introduction_still_flagged(self):
        """'the widget' with NO prior introduction → still flagged (regression)."""
        claims = [Claim(
            id=1,
            text="A device wherein the widget is connected.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "widget" in terms

    def test_nested_introductions(self):
        """'a device comprising at least one module' → both 'device' and 'module' introduced."""
        claims = [Claim(
            id=1,
            text="A device comprising at least one module, wherein the device houses the module.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "device" not in terms
        assert "module" not in terms


class TestAntecedentWordBoundaryWalker:
    """Word-boundary substring matching: short intros must NOT mask longer
    references that contain them as a prefix or substring (commit 6, ADR-089).
    """

    def test_short_intro_does_not_mask_long_reference(self):
        """'a common voltage' must NOT suppress 'the common voltage difference circuit'."""
        claims = [
            Claim(
                id=1,
                text="An apparatus comprising a common voltage.",
                independent=True, method_claim=False,
            ),
            Claim(
                id=2,
                text="The apparatus of claim 1, wherein the common voltage difference circuit is metal.",
                independent=False, method_claim=False, dependencies=[1],
            ),
        ]
        issues = check_antecedent_basis(claims)
        claim2_terms = [i["term"] for i in issues if i["claim_id"] == 2]
        assert "common voltage difference circuit" in claim2_terms

    def test_long_intro_does_not_mask_short_reference(self):
        """'a common voltage difference circuit' must NOT suppress bare 'the common voltage'."""
        claims = [
            Claim(
                id=1,
                text="An apparatus comprising a common voltage difference circuit.",
                independent=True, method_claim=False,
            ),
            Claim(
                id=2,
                text="The apparatus of claim 1, wherein the common voltage is calibrated.",
                independent=False, method_claim=False, dependencies=[1],
            ),
        ]
        issues = check_antecedent_basis(claims)
        claim2_terms = [i["term"] for i in issues if i["claim_id"] == 2]
        assert "common voltage" in claim2_terms

    def test_exact_word_sequence_still_matches(self):
        """Regression: a widget intro still suppresses the widget reference."""
        claims = [
            Claim(
                id=1,
                text="A device comprising a widget, wherein the widget is metal.",
                independent=True, method_claim=False,
            ),
        ]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "widget" not in terms

    def test_testspec2_morphology_surfaces_calculation_pair(self):
        """Real fixture: morphological pair (calculation/calculating) was previously
        masked by the bidirectional substring match. With word-boundary matching,
        the longer 'common voltage difference calculation circuit' style references
        should now surface antecedent findings.
        """
        from pathlib import Path

        import pytest

        from patentlint.parser.claims import parse_claims
        from patentlint.parser.docx_loader import load_docx
        from patentlint.parser import sections

        fixture = (
            Path(__file__).parent.parent
            / "fixtures"
            / "us"
            / "local"
            / "testspec2_motor_driver_morphology.docx"
        )
        if not fixture.exists():
            pytest.skip(f"Real US patent fixture not present: {fixture}")

        loaded = load_docx(fixture)
        claims_section = sections.extract_claims_section(loaded.full_text)
        claims = parse_claims(claims_section) if claims_section else []
        if not claims:
            pytest.skip("Fixture loaded but no claims parsed")

        issues = check_antecedent_basis(claims)
        # Some new finding must surface that mentions 'calculation' or
        # 'calculating' (the morphological-pair signature). Loose check
        # since the exact term shape depends on extraction details.
        all_terms = " ".join(i["term"] for i in issues)
        assert "calculation" in all_terms or "calculating" in all_terms, (
            f"Expected at least one calculation/calculating finding after "
            f"word-boundary fix; got terms: {[i['term'] for i in issues][:30]}"
        )


class TestMarkushGroupSkip:
    """Commit 9b: 'the group consisting of ...' must not flag 'group'."""

    def test_group_consisting_of_not_flagged(self):
        """'the group consisting of A, B, and C' → no finding for 'group'."""
        claims = [Claim(
            id=1,
            text=(
                "A composition selected from the group consisting of methanol, "
                "ethanol, and propanol."
            ),
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "group" not in terms

    def test_group_of_not_flagged(self):
        """'the group of X' (without 'consisting') → no finding for 'group'."""
        claims = [Claim(
            id=1,
            text="A device comprising the group of resistors and capacitors.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "group" not in terms

    def test_bare_group_still_flagged(self):
        """'the group' with no Markush trail → still flagged (regression)."""
        claims = [Claim(
            id=1,
            text="A device wherein the group is active.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "group" in terms


class TestBareNounListIntroductions:
    """Commit 8: bare-noun list-context extraction in the antecedent walker."""

    def test_semicolon_list_walker_no_flag(self):
        """'includes a base; pivot; and arm' followed by 'the pivot' → no flag."""
        claims = [Claim(
            id=1,
            text="An assembly that includes a base; pivot; and arm, wherein the pivot is rigid.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "pivot" not in terms

    def test_comma_preamble_list_walker_no_flag(self):
        """'comprising base, pivot, and arm' followed by 'the arm' → no flag."""
        claims = [Claim(
            id=1,
            text="An apparatus comprising base, pivot, and arm, wherein the arm is movable.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "arm" not in terms

    def test_markush_member_walker_no_flag(self):
        """'selected from the group consisting of methanol, ethanol, and propanol'
        followed by 'the ethanol' → no flag.
        """
        claims = [Claim(
            id=1,
            text=(
                "A composition selected from the group consisting of methanol, "
                "ethanol, and propanol, wherein the ethanol is the dominant component."
            ),
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "ethanol" not in terms

    def test_dependent_claim_can_reference_bare_list_member(self):
        """Dependent claim referencing a bare-noun list member from parent → no flag."""
        claims = [
            Claim(
                id=1,
                text="An apparatus comprising base, pivot, and arm.",
                independent=True, method_claim=False,
            ),
            Claim(
                id=2,
                text="The apparatus of claim 1, wherein the pivot is hinged.",
                independent=False, method_claim=False, dependencies=[1],
            ),
        ]
        issues = check_antecedent_basis(claims)
        claim2_terms = [i["term"] for i in issues if i["claim_id"] == 2]
        assert "pivot" not in claim2_terms


class TestPreambleIntroduction:
    """Bug 6: Preamble introductions must be registered for antecedent basis."""

    def test_preamble_intro_independent(self):
        """'A fuse carrying mechanism, comprising:' → 'the fuse carrying mechanism' NOT flagged."""
        claims = [Claim(
            id=1,
            text="A fuse carrying mechanism, comprising: a base plate, wherein the fuse carrying mechanism is durable.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "fuse carrying mechanism" not in terms

    def test_preamble_intro_dependent(self):
        """Dependent claim referencing parent preamble entity → NOT flagged."""
        claims = [
            Claim(id=1, text="A device comprising: a base plate.", independent=True, method_claim=False),
            Claim(id=2, text="The device of claim 1, wherein the device is metal.", independent=False, method_claim=False, dependencies=[1]),
        ]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 2]
        assert "device" not in terms

    def test_method_preamble_intro(self):
        """'A method comprising: a step of X' → 'the method' NOT flagged."""
        claims = [Claim(
            id=1,
            text="A method comprising: a step of processing, wherein the method is fast.",
            independent=True, method_claim=True,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "method" not in terms


class TestCleanNounPhraseInAntecedentBasis:
    """Bug 6b: clean_noun_phrase() must be applied to definite refs."""

    def test_trailing_further_stripped(self):
        """'the conductive component further' → flags 'conductive component', not with 'further'."""
        claims = [Claim(
            id=1,
            text="A device wherein the conductive component further includes a wire.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "conductive component further" not in terms
        # Should flag "conductive component" (no introduction)
        assert "conductive component" in terms

    def test_trailing_included_stripped(self):
        """'the conductive component included' → flags 'conductive component'."""
        claims = [Claim(
            id=1,
            text="A device wherein the conductive component included by the housing.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "conductive component included" not in terms

    def test_cleaned_term_matches_intro(self):
        """After cleanup, term matches introduction and is NOT flagged."""
        claims = [Claim(
            id=1,
            text="A device comprising a movable component, wherein the movable component further slides.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "movable component" not in terms
        assert "movable component further" not in terms

    def test_possessive_s_stripped(self):
        """'the device's housing' with 'a device' and 'a housing' introduced → no finding."""
        claims = [Claim(
            id=1,
            text="A device comprising a housing, wherein the device's housing is sealed.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "device's housing" not in terms
        assert "device housing" not in terms  # both words introduced separately

    def test_trailing_apostrophe_stripped(self):
        """'the users' devices' with 'a user' and 'a device' introduced → no finding."""
        claims = [Claim(
            id=1,
            text="A system comprising a user and a device, wherein the users' devices are connected.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "users'" not in terms
        assert "users' devices" not in terms


class TestQuantifierStops:
    """Bug 10: Standalone quantifiers/pronouns should not be flagged."""

    def test_the_one_not_flagged(self):
        """'the one of the plurality' → 'one' NOT flagged."""
        claims = [Claim(
            id=1,
            text="A device comprising a plurality of widgets, wherein the one of the plurality is red.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "one" not in terms

    def test_the_another_not_flagged(self):
        """'the another of the plurality' → 'another' NOT flagged."""
        claims = [Claim(
            id=1,
            text="A device comprising a plurality of inductors, wherein the another of the plurality is blue.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "another" not in terms

    def test_the_plurality_not_flagged(self):
        """'the plurality' → 'plurality' NOT flagged (standalone quantifier)."""
        claims = [Claim(
            id=1,
            text="A device comprising a plurality of widgets, wherein the plurality is arranged.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "plurality" not in terms

    def test_multiword_with_first_still_captured(self):
        """'the first filter inductor' → IS captured (multi-word phrase)."""
        claims = [Claim(
            id=1,
            text="A device wherein the first filter inductor is grounded.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "first filter inductor" in terms

    def test_multiword_with_other_still_captured(self):
        """'the other end' → IS captured (multi-word phrase)."""
        claims = [Claim(
            id=1,
            text="A device wherein the other end is connected.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "other end" in terms


class TestAbbreviationIntros:
    """Bug 11: Parenthetical abbreviations register abbreviated forms."""

    def test_ac_source_not_flagged(self):
        """'an alternating current (AC) source' → 'the AC source' NOT flagged."""
        claims = [Claim(
            id=1,
            text="A device comprising an alternating current (AC) source, wherein the AC source provides power.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "ac source" not in terms

    def test_pcb_not_flagged(self):
        """'a printed circuit board (PCB)' → 'the PCB' NOT flagged."""
        claims = [Claim(
            id=1,
            text="A device comprising a printed circuit board (PCB), wherein the PCB is rigid.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "pcb" not in terms

    def test_fpga_device_not_flagged(self):
        """'a field-programmable gate array (FPGA) device' → 'the FPGA device' NOT flagged."""
        claims = [Claim(
            id=1,
            text="A system comprising a field-programmable gate array (FPGA) device, wherein the FPGA device processes data.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "fpga device" not in terms

    def test_no_abbreviation_still_flagged(self):
        """'the XYZ module' with no prior '(XYZ)' → still flagged."""
        claims = [Claim(
            id=1,
            text="A device wherein the XYZ module is active.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        # XYZ was never introduced
        assert any("xyz" in t.lower() for t in terms)


class TestMultiParentDependencies:
    """Multi-parent dependency walking for antecedent basis."""

    def test_two_parent_or_dependency_either_introduces(self):
        """Claim 3 depends on [1, 2]. Claim 1 introduces 'a base'. → no finding."""
        claims = [
            Claim(id=1, text="A device comprising a base.", independent=True),
            Claim(id=2, text="A method comprising a step.", independent=True, method_claim=True),
            Claim(id=3, text="The device of claim 1 or claim 2, wherein the base is flat.",
                  independent=False, dependencies=[1, 2]),
        ]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 3]
        assert "base" not in terms

    def test_two_parent_or_dependency_only_second_introduces(self):
        """Claim 3 depends on [1, 2]. Only claim 2 introduces 'a widget'. → no finding."""
        claims = [
            Claim(id=1, text="A device comprising a base.", independent=True),
            Claim(id=2, text="A device comprising a widget.", independent=True),
            Claim(id=3, text="The device of claim 1 or claim 2, wherein the widget is red.",
                  independent=False, dependencies=[1, 2]),
        ]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 3]
        assert "widget" not in terms

    def test_two_parent_or_dependency_neither_introduces(self):
        """Neither parent introduces 'a sensor'. → finding emitted."""
        claims = [
            Claim(id=1, text="A device comprising a base.", independent=True),
            Claim(id=2, text="A device comprising a widget.", independent=True),
            Claim(id=3, text="The device of claim 1 or claim 2, wherein the sensor is active.",
                  independent=False, dependencies=[1, 2]),
        ]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 3]
        assert "sensor" in terms

    def test_three_parent_dependency(self):
        """Claim 4 depends on [1, 2, 3]. Only claim 3 introduces. → no finding."""
        claims = [
            Claim(id=1, text="A device comprising a base.", independent=True),
            Claim(id=2, text="A device comprising a lid.", independent=True),
            Claim(id=3, text="A device comprising a relay.", independent=True),
            Claim(id=4, text="The device of claim 1, 2, or 3, wherein the relay is active.",
                  independent=False, dependencies=[1, 2, 3]),
        ]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 4]
        assert "relay" not in terms

    def test_dependency_cycle_does_not_loop(self):
        """Pathological cycle: claim 2 → claim 3 → claim 2. Should not infinite-loop."""
        claims = [
            Claim(id=2, text="The device of claim 3, wherein the widget is red.",
                  independent=False, dependencies=[3]),
            Claim(id=3, text="The device of claim 2, wherein the sensor is blue.",
                  independent=False, dependencies=[2]),
        ]
        # Should complete without hanging; findings expected since no introductions
        issues = check_antecedent_basis(claims)
        assert isinstance(issues, list)

    def test_nonexistent_parent_id_skipped(self):
        """Dependency on non-existent claim 99. Should not crash."""
        claims = [
            Claim(id=5, text="The device of claim 99, wherein the base is flat.",
                  independent=False, dependencies=[99]),
        ]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 5]
        assert "base" in terms


class TestFindingShape:
    """Finding dicts include claim_id, term, reference_form, claim_text."""

    def test_finding_has_claim_id_and_term(self):
        """Backward compat: claim_id and term always present."""
        claims = [Claim(id=1, text="A device wherein the widget is active.", independent=True)]
        issues = check_antecedent_basis(claims)
        assert len(issues) >= 1
        assert "claim_id" in issues[0]
        assert "term" in issues[0]

    def test_finding_has_reference_form(self):
        claims = [Claim(id=1, text="A device wherein the widget is active.", independent=True)]
        issues = check_antecedent_basis(claims)
        assert "reference_form" in issues[0]

    def test_finding_has_claim_text(self):
        claim_text = "A device wherein the widget is active."
        claims = [Claim(id=1, text=claim_text, independent=True)]
        issues = check_antecedent_basis(claims)
        assert issues[0]["claim_text"] == claim_text

    def test_reference_form_preserves_prefix(self):
        """reference_form should be 'the base plate', not 'base plate'."""
        claims = [Claim(id=1, text="A device wherein the base plate is flat.", independent=True)]
        issues = check_antecedent_basis(claims)
        issue = next(i for i in issues if i["term"] == "base plate")
        assert issue["reference_form"] == "the base plate"

    def test_reference_form_strips_trailing_junk(self):
        """'the base plate further comprising' → reference_form='the base plate'."""
        claims = [Claim(id=1, text="A device wherein the base plate further comprising a lid.", independent=True)]
        issues = check_antecedent_basis(claims)
        issue = next(i for i in issues if i["term"] == "base plate")
        assert issue["reference_form"] == "the base plate"

    def test_said_prefix_preserved_in_reference_form(self):
        claims = [Claim(id=1, text="A device comprising a memory, wherein said processor executes code.", independent=True)]
        issues = check_antecedent_basis(claims)
        issue = next(i for i in issues if "processor" in i["term"])
        assert issue["reference_form"].startswith("said ")


class TestAntecedentBasisDedup:
    """Dedup within-claim by (term, reference_form), keep across claims."""

    def test_same_term_same_form_within_claim_deduped(self):
        """'the base ... the base' in one claim → 1 finding."""
        claims = [Claim(
            id=3,
            text="A device wherein the base is flat and the base is wide.",
            independent=True,
        )]
        issues = check_antecedent_basis(claims)
        base_issues = [i for i in issues if i["term"] == "base" and i["claim_id"] == 3]
        assert len(base_issues) == 1

    def test_same_term_different_forms_within_claim_kept(self):
        """'the base' and 'said base' in one claim → 2 findings."""
        claims = [Claim(
            id=3,
            text="A device wherein the base is flat and said base is wide.",
            independent=True,
        )]
        issues = check_antecedent_basis(claims)
        base_issues = [i for i in issues if i["term"] == "base" and i["claim_id"] == 3]
        assert len(base_issues) == 2
        forms = {i["reference_form"] for i in base_issues}
        assert "the base" in forms
        assert "said base" in forms

    def test_same_term_across_claims_kept(self):
        """Same unmatched term in claim 3 and claim 7 → 2 findings."""
        claims = [
            Claim(id=3, text="A device wherein the widget is flat.", independent=True),
            Claim(id=7, text="A device wherein the widget is wide.", independent=True),
        ]
        issues = check_antecedent_basis(claims)
        widget_issues = [i for i in issues if i["term"] == "widget"]
        claim_ids = [i["claim_id"] for i in widget_issues]
        assert 3 in claim_ids
        assert 7 in claim_ids

    def test_findings_sorted_by_claim_then_term_then_form(self):
        """Findings sorted by (claim_id, term, reference_form) — all three keys exercised."""
        claims = [
            # Claim 3 first in list (out of ID order), two terms: "widget" and "base"
            Claim(id=3, text="A device wherein the widget is red and said base is flat.", independent=True),
            # Claim 1: same term "widget" with both "said" and "the" forms
            Claim(id=1, text="A device wherein said widget is blue and the widget is green.", independent=True),
        ]
        issues = check_antecedent_basis(claims)
        actual = [(i["claim_id"], i["term"], i["reference_form"]) for i in issues]
        expected = [
            (1, "widget", "said widget"),   # claim 1, term "widget", form "said"
            (1, "widget", "the widget"),     # claim 1, term "widget", form "the"
            (3, "base", "said base"),        # claim 3, term "base" < "widget"
            (3, "widget", "the widget"),     # claim 3, term "widget"
        ]
        assert actual == expected


class TestTokenSetJaccard:
    """Commit 10: Token-set Jaccard helper for did-you-mean suggestion layer."""

    def test_morphological_pair_above_threshold(self):
        """The motivating case: calculation/calculating differ in one token of five."""
        from patentlint.analysis.utils import token_set_jaccard
        a = "common voltage difference calculation circuit"
        b = "common voltage difference calculating circuit"
        assert token_set_jaccard(a, b) >= 0.5

    def test_unrelated_terms_zero(self):
        """Disjoint token sets → Jaccard 0.0."""
        from patentlint.analysis.utils import token_set_jaccard
        assert token_set_jaccard("widget", "sprocket") == 0.0

    def test_empty_string_zero(self):
        """Empty input → 0.0 (avoids ZeroDivisionError)."""
        from patentlint.analysis.utils import token_set_jaccard
        assert token_set_jaccard("", "widget") == 0.0
        assert token_set_jaccard("widget", "") == 0.0

    def test_identical_strings_one(self):
        """Identical token sets → 1.0."""
        from patentlint.analysis.utils import token_set_jaccard
        assert token_set_jaccard("base plate", "base plate") == 1.0

    def test_case_insensitive(self):
        """Case differences do not affect the score."""
        from patentlint.analysis.utils import token_set_jaccard
        assert token_set_jaccard("Base PLATE", "base plate") == 1.0


class TestSuggestedMatchOnFinding:
    """Commit 10: walker attaches suggested_match for morphological near-misses."""

    def test_calculation_calculating_pair_attaches_suggestion(self):
        """The motivating case: 'calculation' intro, 'calculating' reference.

        Both share the same long base phrase; word-boundary AND-match
        does not suppress the finding (one token differs), and Jaccard ≥ 0.5
        attaches a suggested_match pointing at the introduced phrase.
        """
        claims = [Claim(
            id=1,
            text=(
                "A device comprising a common voltage difference calculation circuit, "
                "wherein the common voltage difference calculating circuit is active."
            ),
            independent=True,
            method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        target = next(
            (i for i in issues if "calculating circuit" in i["term"]),
            None,
        )
        assert target is not None, "expected unmatched 'calculating circuit' finding"
        assert target["suggested_match"] is not None
        assert "calculation" in target["suggested_match"]["term"]
        assert target["suggested_match"]["claim_id"] == 1

    def test_no_near_match_no_suggestion(self):
        """If no intro is within Jaccard ≥ 0.5, suggested_match is None."""
        claims = [Claim(
            id=1,
            text="A device comprising a base, wherein the sprocket is sharp.",
            independent=True,
            method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        target = next((i for i in issues if i["term"] == "sprocket"), None)
        assert target is not None
        assert target["suggested_match"] is None

    def test_suggestion_carries_introducing_claim_id(self):
        """Multi-claim chain: suggestion carries the ancestor claim ID."""
        claims = [
            Claim(
                id=1,
                text="A device comprising a common voltage difference calculation circuit.",
                independent=True,
                method_claim=False,
            ),
            Claim(
                id=2,
                text="The device of claim 1, wherein the common voltage difference calculating circuit is active.",
                independent=False,
                method_claim=False,
                dependencies=[1],
            ),
        ]
        issues = check_antecedent_basis(claims)
        target = next(
            (i for i in issues if i["claim_id"] == 2 and "calculating" in i["term"]),
            None,
        )
        assert target is not None
        assert target["suggested_match"] is not None
        # Suggested match originates from claim 1, not claim 2
        assert target["suggested_match"]["claim_id"] == 1


class TestAttachCrossReferences:
    """Commit 10: cross-reference annotation across the two checks."""

    def test_same_term_in_both_lists_gets_cross_ref(self):
        from patentlint.analysis.claims import (
            attach_cross_references,
            check_antecedent_basis,
            check_spec_support,
        )
        claims = [Claim(
            id=1,
            text="A device comprising a base, wherein the connector is flat.",
            independent=True,
            method_claim=False,
        )]
        ab = check_antecedent_basis(claims)
        ss = check_spec_support(claims, "no mention here")
        attach_cross_references(ab, ss)
        connector_ab = next(i for i in ab if i["term"] == "connector")
        connector_ss = next(u for u in ss if u.phrase == "connector")
        assert connector_ab["cross_ref"] == "spec_support"
        assert connector_ss.cross_ref == "antecedent"

    def test_term_only_in_antecedent_no_cross_ref(self):
        from patentlint.analysis.claims import (
            attach_cross_references,
            check_antecedent_basis,
            check_spec_support,
        )
        claims = [Claim(
            id=1,
            text="A device comprising a base, wherein the widget is flat.",
            independent=True,
            method_claim=False,
        )]
        ab = check_antecedent_basis(claims)
        # Spec mentions widget so it is supported, but no antecedent intro
        ss = check_spec_support(claims, "the widget is described in detail here.")
        attach_cross_references(ab, ss)
        widget_ab = next(i for i in ab if i["term"] == "widget")
        assert widget_ab["cross_ref"] is None


class TestSuggestedMatchTiebreak:
    """Commit 10b: stemmed-symmetric-difference tiebreak for did-you-mean.

    When two intros tie at the same Jaccard score, the morphologically
    related candidate (smaller stemmed symmetric difference) wins.
    Surfaced by the testspec5 browser smoke test where 'surge protecting
    circuit' was tied between 'surge protection circuit' (correct
    morphological pair) and 'surge suppressor circuit' (coincidental
    overlap), and the strict ``>`` loop picked whichever arrived first.
    """

    def test_stemmed_pair_beats_unrelated_at_same_jaccard(self):
        """Two intros tie at Jaccard 0.5; the stemmed-pair candidate wins.

        Reference: 'surge protecting circuit' (stems: surg, protect, circuit).
        Intro A:  'surge protection circuit' (stems: surg, protect, circuit)
                  → sym_diff = {'protecting', 'protection'}, both stem to
                  'protect', stem_sym_diff size = 1.
        Intro B:  'surge suppressor circuit' (stems: surg, suppressor, circuit)
                  → sym_diff = {'protecting', 'suppressor'}, two distinct
                  stems, stem_sym_diff size = 2.

        Lower stem_sym_diff wins → A is the suggestion.
        """
        # Inject the suppressor candidate FIRST so without the tiebreak it
        # would beat the protection candidate.
        claims = [Claim(
            id=1,
            text=(
                "A device comprising a surge suppressor circuit and a surge "
                "protection circuit, wherein the surge protecting circuit is active."
            ),
            independent=True,
            method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        target = next(
            (i for i in issues if i["term"] == "surge protecting circuit"),
            None,
        )
        assert target is not None
        assert target["suggested_match"] is not None
        assert target["suggested_match"]["term"] == "surge protection circuit"

    def test_calculation_calculating_pair_still_resolves(self):
        """Regression: testspec2's pair has only one candidate at ≥0.5,
        so the tiebreak is a no-op and the suggestion still lands.
        """
        claims = [Claim(
            id=1,
            text=(
                "A device comprising a common voltage difference calculation circuit, "
                "wherein the common voltage difference calculating circuit is active."
            ),
            independent=True,
            method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        target = next(
            (i for i in issues if "calculating circuit" in i["term"]),
            None,
        )
        assert target is not None
        assert target["suggested_match"]["term"] == "common voltage difference calculation circuit"

    def test_real_fixture_testspec5_surge_protecting(self):
        """Real fixture: every 'surge protecting circuit' finding on testspec5
        suggests 'surge protection circuit', not 'surge suppressor circuit'.
        Skipped if the gitignored fixture is not present.
        """
        import pytest
        from pathlib import Path
        from patentlint.pipeline import analyze_file
        from patentlint.models import Jurisdiction

        fixture = Path(
            "tests/fixtures/us/local/testspec5_surge_nested_lists.docx"
        )
        if not fixture.exists():
            pytest.skip("real fixture not present")
        result = analyze_file(str(fixture), jurisdiction=Jurisdiction.US)
        targets = [
            f for f in result.antecedent_basis_issues
            if f["term"] == "surge protecting circuit"
        ]
        assert len(targets) > 0, "expected at least one surge protecting circuit finding"
        for f in targets:
            sm = f["suggested_match"]
            assert sm is not None
            assert sm["term"] == "surge protection circuit", (
                f"claim {f['claim_id']} suggested {sm['term']!r} "
                f"instead of 'surge protection circuit'"
            )


class TestUtsVerbSuffix:
    """Commit 10b: -uts trailing verbs (e.g., 'outputs') stripped.

    Surfaced by the testspec5 smoke test where claim 2 captured
    'the surge detection driver circuit outputs' as a reference term.
    """

    def test_circuit_outputs_stripped(self):
        from patentlint.analysis.utils import clean_noun_phrase
        assert clean_noun_phrase("circuit outputs") == "circuit"

    def test_real_fixture_testspec5_no_outputs_capture(self):
        """Real fixture: testspec5 claim 2 no longer captures
        'the surge detection driver circuit outputs' as a finding.
        Skipped if the gitignored fixture is not present.
        """
        import pytest
        from pathlib import Path
        from patentlint.pipeline import analyze_file
        from patentlint.models import Jurisdiction

        fixture = Path(
            "tests/fixtures/us/local/testspec5_surge_nested_lists.docx"
        )
        if not fixture.exists():
            pytest.skip("real fixture not present")
        result = analyze_file(str(fixture), jurisdiction=Jurisdiction.US)
        outputs_findings = [
            f for f in result.antecedent_basis_issues
            if "outputs" in f["term"]
        ]
        assert outputs_findings == [], (
            f"expected no -outputs findings, got: "
            f"{[(f['claim_id'], f['term']) for f in outputs_findings]}"
        )
