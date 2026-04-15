# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for noun phrase cleanup and capture width (Bugs 3, 5, 6b, 10, 11, 12)."""

from patentlint.analysis.utils import (
    clean_noun_phrase, extract_noun_phrases, extract_abbreviation_intros,
    extract_definite_refs, extract_introductions, extract_bare_noun_intros,
)


class TestStripping:
    """Trailing verbs, adverbs, and function words should be stripped."""

    def test_trailing_verb_pushes(self):
        assert clean_noun_phrase("pushing portion pushes") == "pushing portion"

    def test_trailing_adverb_jointly(self):
        assert clean_noun_phrase("elastic arm jointly") == "elastic arm"

    def test_trailing_multiple_words(self):
        assert clean_noun_phrase("movable component further includes") == "movable component"

    def test_trailing_thereof(self):
        assert clean_noun_phrase("inner side thereof") == "inner side"

    def test_trailing_according(self):
        assert clean_noun_phrase("connector assembly according") == "connector assembly"

    def test_trailing_ed_configured(self):
        """Morphological -ed detection (software domain)."""
        assert clean_noun_phrase("processing unit configured") == "processing unit"

    def test_trailing_ed_connected(self):
        """Morphological -ed detection (electrical domain)."""
        assert clean_noun_phrase("switching circuit connected") == "switching circuit"

    def test_trailing_ed_disposed(self):
        """Morphological -ed detection (biotech domain)."""
        assert clean_noun_phrase("coating layer disposed") == "coating layer"


class TestPreservation:
    """Gerund-derived nouns must NOT be stripped (multi-domain)."""

    def test_accommodating_slot(self):
        assert clean_noun_phrase("accommodating slot") == "accommodating slot"

    def test_pushing_portion(self):
        assert clean_noun_phrase("pushing portion") == "pushing portion"

    def test_processing_unit(self):
        assert clean_noun_phrase("processing unit") == "processing unit"

    def test_computing_device(self):
        assert clean_noun_phrase("computing device") == "computing device"

    def test_rendering_engine(self):
        assert clean_noun_phrase("rendering engine") == "rendering engine"

    def test_switching_circuit(self):
        assert clean_noun_phrase("switching circuit") == "switching circuit"

    def test_grounding_terminal(self):
        assert clean_noun_phrase("grounding terminal") == "grounding terminal"

    def test_binding_site(self):
        assert clean_noun_phrase("binding site") == "binding site"

    def test_coating_layer(self):
        assert clean_noun_phrase("coating layer") == "coating layer"

    def test_standalone_opening(self):
        assert clean_noun_phrase("opening") == "opening"

    def test_standalone_housing(self):
        assert clean_noun_phrase("housing") == "housing"


class TestTrailingPrepositions:
    """Trailing prepositions should be stripped from noun phrases."""

    def test_trailing_along(self):
        assert clean_noun_phrase("alignment glass sheet along") == "alignment glass sheet"

    def test_trailing_between(self):
        assert clean_noun_phrase("space between") == "space"

    def test_trailing_through(self):
        assert clean_noun_phrase("passage through") == "passage"

    def test_trailing_upon(self):
        assert clean_noun_phrase("conductive layer upon") == "conductive layer"

    def test_regex_does_not_capture_along(self):
        """Regex-level: 'along' should never be part of a captured noun phrase."""
        refs = extract_definite_refs("the alignment glass sheet along the centerline")
        assert "alignment glass sheet" in refs
        assert not any("along" in r for r in refs)

    def test_regex_does_not_capture_between(self):
        refs = extract_definite_refs("the gap between the walls")
        assert "gap" in refs
        assert not any("between" in r for r in refs)


class TestTrailingFunctionWords:
    """Trailing conjunctions and relative pronouns should be stripped."""

    def test_trailing_and(self):
        assert clean_noun_phrase("mounting bracket and") == "mounting bracket"

    def test_trailing_that(self):
        assert clean_noun_phrase("filter element that") == "filter element"

    def test_trailing_which(self):
        assert clean_noun_phrase("housing assembly which") == "housing assembly"


class TestNoFalseStripping:
    """Words that look like function words but are part of the noun should be preserved."""

    def test_sensor_chip(self):
        assert clean_noun_phrase("sensor chip") == "sensor chip"

    def test_alignment_slot(self):
        assert clean_noun_phrase("alignment slot") == "alignment slot"

    def test_two_engaging_structures(self):
        """Bug: 'structures' was wrongly stripped by suffix-based verb detection."""
        assert clean_noun_phrase("two engaging structures") == "two engaging structures"

    def test_engaging_structures(self):
        """Head noun 'structures' must be retained after adjective."""
        assert clean_noun_phrase("engaging structures") == "engaging structures"


class TestTrailingVerbS:
    """Bug: Third-person present tense verbs (-s/-es) captured as part of noun phrases."""

    def test_trailing_encompasses(self):
        assert clean_noun_phrase("protective layer encompasses") == "protective layer"

    def test_trailing_contains(self):
        assert clean_noun_phrase("storage container contains") == "storage container"

    def test_trailing_produces(self):
        assert clean_noun_phrase("reaction chamber produces") == "reaction chamber"

    def test_trailing_creates(self):
        assert clean_noun_phrase("processing module creates") == "processing module"

    def test_trailing_maintains(self):
        assert clean_noun_phrase("control unit maintains") == "control unit"

    def test_trailing_represents(self):
        assert clean_noun_phrase("data structure represents") == "data structure"

    def test_trailing_overlaps(self):
        assert clean_noun_phrase("sealing flange overlaps") == "sealing flange"


class TestCaptureWidth:
    """Bug 5: Noun phrase capture should handle up to 6 words."""

    def test_four_word_phrase(self):
        """'two connection terminal assemblies' should be captured in full."""
        text = "the two connection terminal assemblies are flexible"
        phrases = extract_noun_phrases(text)
        assert any("two connection terminal assemblies" in p for p in phrases)

    def test_four_word_ordinal(self):
        """'first auxiliary engaging structure' should be captured in full."""
        text = "a first auxiliary engaging structure is provided"
        phrases = extract_noun_phrases(text)
        assert any("first auxiliary engaging structure" in p for p in phrases)

    def test_three_word_still_works(self):
        """Existing 3-word phrases should still be captured (regression)."""
        text = "a connection terminal assembly is provided"
        phrases = extract_noun_phrases(text)
        assert any("connection terminal assembly" in p for p in phrases)


class TestModalVerbStripping:
    """Bug 6b-continued: Modal verbs should be stripped from noun phrases."""

    def test_trailing_must(self):
        assert clean_noun_phrase("insulating base further must include") == "insulating base"

    def test_trailing_shall(self):
        assert clean_noun_phrase("conductive element shall") == "conductive element"

    def test_trailing_should(self):
        assert clean_noun_phrase("filter circuit should") == "filter circuit"

    def test_trailing_can(self):
        assert clean_noun_phrase("switching device can") == "switching device"

    def test_trailing_may(self):
        assert clean_noun_phrase("housing assembly may") == "housing assembly"


class TestAbbreviationExtraction:
    """Bug 11: Extract abbreviated forms from parenthetical patterns."""

    def test_ac_source(self):
        intros = extract_abbreviation_intros("an alternating current (AC) source")
        assert "ac source" in intros
        assert "ac" in intros

    def test_pcb_standalone(self):
        intros = extract_abbreviation_intros("a printed circuit board (PCB)")
        assert "pcb" in intros

    def test_fpga_device(self):
        intros = extract_abbreviation_intros("a field-programmable gate array (FPGA) device")
        assert "fpga device" in intros
        assert "fpga" in intros

    def test_no_abbreviation(self):
        intros = extract_abbreviation_intros("a simple device")
        assert intros == []


class TestHyphenatedCompoundCapture:
    """Bug 12: Hyphenated compound words must be captured as single tokens."""

    def test_multi_stage_filter_circuit(self):
        refs = extract_definite_refs("the multi-stage filter circuit is grounded")
        assert "multi-stage filter circuit" in refs

    def test_non_transitory_medium(self):
        refs = extract_definite_refs("the non-transitory computer-readable storage medium is configured")
        assert "non-transitory computer-readable storage medium" in refs

    def test_bi_directional_zener_diode(self):
        refs = extract_definite_refs("the bi-directional Zener diode is connected")
        assert "bi-directional zener diode" in refs

    def test_self_aligning_bearing_intro(self):
        intros = extract_introductions("a self-aligning bearing is provided")
        assert "self-aligning bearing" in intros

    def test_pre_determined_threshold(self):
        refs = extract_definite_refs("the pre-determined threshold is exceeded")
        assert "pre-determined threshold" in refs

    def test_cross_sectional_area(self):
        refs = extract_definite_refs("the cross-sectional area of the housing is circular")
        assert "cross-sectional area" in refs

    def test_prefix_fragment_not_captured(self):
        """'multi' alone should NOT appear — full 'multi-stage' should."""
        refs = extract_definite_refs("the multi-stage filter circuit is grounded")
        assert "multi" not in refs

    def test_noun_phrases_hyphenated(self):
        """extract_noun_phrases should also handle hyphens."""
        phrases = extract_noun_phrases("a non-volatile memory cell is provided in the non-volatile memory cell")
        assert any("non-volatile memory cell" in p for p in phrases)


class TestHyphenatedAntecedentBasis:
    """Bug 12: Antecedent basis check with hyphenated terms."""

    def test_multi_stage_intro_and_ref(self):
        from patentlint.analysis.claims import check_antecedent_basis
        from patentlint.models import Claim

        claims = [Claim(
            id=1,
            text="A device comprising a multi-stage filter circuit, wherein the multi-stage filter circuit is grounded.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "multi-stage filter circuit" not in terms
        assert "multi" not in terms

    def test_trailing_preposition_not_in_term(self):
        """'alignment glass sheet along' — 'along' must not appear in stored term."""
        from patentlint.analysis.claims import check_antecedent_basis
        from patentlint.models import Claim

        claims = [Claim(
            id=7,
            text="A device comprising an alignment glass sheet along a centerline, wherein the alignment glass sheet along the centerline is transparent.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 7]
        # "alignment glass sheet" should match intro — no issue reported
        assert "alignment glass sheet along" not in terms
        assert "alignment glass sheet" not in terms

    def test_trailing_between_not_in_term(self):
        """'gap between' — 'between' must not appear in stored term."""
        from patentlint.analysis.claims import check_antecedent_basis
        from patentlint.models import Claim

        claims = [Claim(
            id=1,
            text="A device comprising a gap between two walls, wherein the gap is sealed.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "gap between" not in terms
        assert "gap" not in terms

    def test_non_transitory_intro_and_ref(self):
        from patentlint.analysis.claims import check_antecedent_basis
        from patentlint.models import Claim

        claims = [Claim(
            id=1,
            text="A non-transitory medium, wherein the non-transitory medium stores instructions.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "non-transitory medium" not in terms
        assert "non" not in terms


class TestExtractBareNounIntros:
    """Commit 8: bare-noun list-context introduction extraction."""

    def test_semicolon_list_after_includes(self):
        """'includes a base; pivot; and arm' → all three are introductions."""
        intros = extract_bare_noun_intros("the assembly includes a base; pivot; and arm.")
        assert "base" in intros
        assert "pivot" in intros
        assert "arm" in intros

    def test_comma_preamble_list(self):
        """'comprising base, pivot, and arm' → all three are introductions."""
        intros = extract_bare_noun_intros("an apparatus comprising base, pivot, and arm.")
        assert "base" in intros
        assert "pivot" in intros
        assert "arm" in intros

    def test_markush_group_members(self):
        """'selected from the group consisting of methanol, ethanol, and propanol' →
        each chemical is an introduction.
        """
        intros = extract_bare_noun_intros(
            "selected from the group consisting of methanol, ethanol, and propanol."
        )
        assert "methanol" in intros
        assert "ethanol" in intros
        assert "propanol" in intros

    def test_truncates_at_wherein(self):
        """List run is truncated at 'wherein' so the wherein-clause does not
        bleed into the list and produce noise like 'the device is flat'.
        """
        intros = extract_bare_noun_intros(
            "comprising a base, wherein the device is flat."
        )
        assert "base" in intros
        # Words after 'wherein' must NOT have been split into list items
        assert "the device is flat" not in intros
        assert "device is flat" not in intros

    def test_no_list_context_no_extraction(self):
        """Arbitrary commas outside a list context produce nothing."""
        intros = extract_bare_noun_intros("the widget moves, slides, and rotates.")
        # No trigger word matched → empty extraction
        assert intros == []

    def test_consisting_essentially_of(self):
        """'consisting essentially of A, B, and C' is also a list context."""
        intros = extract_bare_noun_intros(
            "consisting essentially of copper, iron, and zinc."
        )
        assert "copper" in intros
        assert "iron" in intros
        assert "zinc" in intros

    def test_extract_introductions_includes_bare_nouns(self):
        """Top-level extract_introductions should include bare-noun intros
        additively (existing _INTRO_PATTERNS arm still runs).
        """
        intros = extract_introductions(
            "an apparatus comprising a base, pivot, and arm."
        )
        # 'a base' captured by both arms; 'pivot' and 'arm' only by bare-noun
        assert "base" in intros
        assert "pivot" in intros
        assert "arm" in intros


class TestExpandedNumeralIntros:
    """Commit 9c: numeral pattern expanded from two..four to one..ten."""

    def test_one_widget(self):
        """'one widget' → 'widget' captured."""
        intros = extract_introductions("a device with one widget mounted on top.")
        assert "widget" in intros

    def test_five_widgets(self):
        """'five widgets' → 'widgets' captured."""
        intros = extract_introductions("five widgets are arranged in a row.")
        assert "widgets" in intros

    def test_ten_processors(self):
        """'ten processors' → 'processors' captured."""
        intros = extract_introductions("ten processors are mounted on the board.")
        # "are" is a stop word so capture ends at "processors"
        assert "processors" in intros

    def test_expanded_numeral_walker_no_flag(self):
        """End-to-end: 'five widgets' intro suppresses 'the widgets' reference."""
        from patentlint.analysis.claims import check_antecedent_basis
        from patentlint.models import Claim

        claims = [Claim(
            id=1,
            text="A device comprising five widgets, wherein the widgets are aligned.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 1]
        assert "widgets" not in terms


class TestExpandedVerbSuffixes:
    """Commit 9d: -cts/-pts/-rts/-sts trailing verbs are stripped."""

    def test_cts_subtracts(self):
        """'circuit subtracts' → 'circuit' (subtracts is a verb)."""
        assert clean_noun_phrase("circuit subtracts") == "circuit"

    def test_pts_accepts(self):
        """'driver accepts' → 'driver' (accepts is a verb)."""
        assert clean_noun_phrase("driver accepts") == "driver"

    def test_rts_converts(self):
        """'controller converts' → 'controller' (converts is a verb)."""
        assert clean_noun_phrase("controller converts") == "controller"

    def test_sts_consists(self):
        """'composition consists' → 'composition' (consists is a verb)."""
        assert clean_noun_phrase("composition consists") == "composition"

    def test_short_word_not_stripped(self):
        """Short -sts words (<6 chars) are not stripped."""
        # 'lists' is 5 chars → _is_likely_third_person_verb returns False
        assert clean_noun_phrase("input lists") == "input lists"
