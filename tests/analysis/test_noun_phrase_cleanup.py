# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""Tests for noun phrase cleanup and capture width (Bugs 3, 5, 6b, 10, 11, 12)."""

from patentlint.analysis.utils import (
    clean_noun_phrase, extract_noun_phrases, extract_abbreviation_intros,
    extract_definite_refs, extract_introductions, extract_bare_noun_intros,
    gerund_display_head, _strip_comparative_tail,
)


def _ct(s: str) -> str:
    return " ".join(_strip_comparative_tail(s.split()))


class TestComparativeTailStrip:
    """WS-A3 (examiner-grounded): a reference ending in `than` over-captured a
    comparative clause. Strip it back to the head noun - reference-side only."""

    def test_other_than(self):
        assert _ct("first element other than") == "first element"

    def test_comparative_adj_than(self):
        assert _ct("second element wider than") == "second element"
        assert _ct("value greater than") == "value"
        assert _ct("pdsch starting later than") == "pdsch starting"

    def test_bare_than(self):
        assert _ct("substrate than") == "substrate"

    def test_copula_remnant_removed(self):
        assert _ct("first gap is greater than") == "first gap"

    def test_non_comparative_untouched(self):
        # FN-safety: `than` not final → no strip; `other`/`greater` survive.
        assert _ct("other end") == "other end"
        assert _ct("greater portion") == "greater portion"
        assert _ct("first layer") == "first layer"
        assert _ct("inner diameter") == "inner diameter"


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
        """'multi' alone should NOT appear - full 'multi-stage' should."""
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
        """'alignment glass sheet along' - 'along' must not appear in stored term."""
        from patentlint.analysis.claims import check_antecedent_basis
        from patentlint.models import Claim

        claims = [Claim(
            id=7,
            text="A device comprising an alignment glass sheet along a centerline, wherein the alignment glass sheet along the centerline is transparent.",
            independent=True, method_claim=False,
        )]
        issues = check_antecedent_basis(claims)
        terms = [i["term"] for i in issues if i["claim_id"] == 7]
        # "alignment glass sheet" should match intro - no issue reported
        assert "alignment glass sheet along" not in terms
        assert "alignment glass sheet" not in terms

    def test_trailing_between_not_in_term(self):
        """'gap between' - 'between' must not appear in stored term."""
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


class TestTrailingRelationalAdjectives:
    """Relational/positional adjectives (opposite/relative/adjacent/parallel/...)
    that head a predicative phrase must be stripped when trailing. Surfaced
    by TestSpec123.docx: 'the lower cover surface opposite to the upper cover
    surface' was being captured as 'lower cover surface opposite' and flooding
    spec-support + antecedent-DYM output."""

    def test_opposite_trailing(self):
        assert clean_noun_phrase("lower cover surface opposite") == "lower cover surface"

    def test_opposing_trailing(self):
        assert clean_noun_phrase("first wall opposing") == "first wall"

    def test_relative_trailing(self):
        assert clean_noun_phrase("conductive substrate relative") == "conductive substrate"

    def test_adjacent_trailing(self):
        assert clean_noun_phrase("region adjacent") == "region"

    def test_adjoining_trailing(self):
        assert clean_noun_phrase("electrode adjoining") == "electrode"

    def test_parallel_trailing(self):
        assert clean_noun_phrase("reference plane parallel") == "reference plane"

    def test_perpendicular_trailing(self):
        assert clean_noun_phrase("beam axis perpendicular") == "beam axis"

    def test_orthogonal_trailing(self):
        assert clean_noun_phrase("first vector orthogonal") == "first vector"

    def test_oblique_trailing(self):
        assert clean_noun_phrase("side face oblique") == "side face"

    def test_concentric_trailing(self):
        assert clean_noun_phrase("outer ring concentric") == "outer ring"

    def test_collinear_trailing(self):
        assert clean_noun_phrase("second axis collinear") == "second axis"

    def test_coaxial_trailing(self):
        assert clean_noun_phrase("rotor shaft coaxial") == "rotor shaft"

    def test_similar_trailing(self):
        assert clean_noun_phrase("resistance value similar") == "resistance value"

    def test_identical_trailing(self):
        assert clean_noun_phrase("secondary coil identical") == "secondary coil"

    def test_equal_trailing(self):
        assert clean_noun_phrase("duty cycle equal") == "duty cycle"

    def test_equivalent_trailing(self):
        assert clean_noun_phrase("input signal equivalent") == "input signal"

    def test_proximate_trailing(self):
        assert clean_noun_phrase("sensor array proximate") == "sensor array"

    def test_distal_trailing(self):
        assert clean_noun_phrase("catheter tip distal") == "catheter tip"

    def test_proximal_trailing(self):
        assert clean_noun_phrase("anchor end proximal") == "anchor end"

    def test_medial_trailing(self):
        assert clean_noun_phrase("tibial surface medial") == "tibial surface"

    def test_lateral_trailing(self):
        assert clean_noun_phrase("femoral surface lateral") == "femoral surface"

    def test_closer_trailing(self):
        assert clean_noun_phrase("second lens closer") == "second lens"

    def test_nearer_trailing(self):
        assert clean_noun_phrase("first element nearer") == "first element"

    def test_farther_trailing(self):
        assert clean_noun_phrase("third element farther") == "third element"


class TestRelationalAdjectivesPreservedInLeadingPosition:
    """Leading and internal uses of the same adjectives must NOT be stripped -
    'opposite' at the start of 'opposite surface' is a legitimate modifier.
    The trailing-only strip only walks from the right end of the phrase."""

    def test_opposite_leading(self):
        assert clean_noun_phrase("opposite surface") == "opposite surface"

    def test_adjacent_leading(self):
        assert clean_noun_phrase("adjacent region") == "adjacent region"

    def test_parallel_leading(self):
        assert clean_noun_phrase("parallel plates") == "parallel plates"

    def test_perpendicular_leading(self):
        assert clean_noun_phrase("perpendicular axis") == "perpendicular axis"

    def test_lateral_leading(self):
        assert clean_noun_phrase("lateral surface") == "lateral surface"

    def test_medial_leading(self):
        assert clean_noun_phrase("medial layer") == "medial layer"

    def test_similar_internal(self):
        assert clean_noun_phrase("similar housing structure") == "similar housing structure"

    def test_opposite_internal(self):
        assert clean_noun_phrase("opposite cover surface") == "opposite cover surface"

    def test_concentric_leading(self):
        assert clean_noun_phrase("concentric rings") == "concentric rings"

    def test_coaxial_leading(self):
        assert clean_noun_phrase("coaxial cable") == "coaxial cable"


# ---------------------------------------------------------------------------
# Engine-1 REFERENCE-SIDE DISPLAY cleanup (2026-09-02, reports #676/#681/#688).
#
# `clean_noun_phrase` falls back to the RAW capture when every token strips
# away, so the drafter's whole predicate was emitted as the element name.
# `gerund_display_head` cleans that for DISPLAY only. Each control below is a
# design that was implemented and MEASURED before this one shipped, so these
# are regression pins on real failures, not hypotheticals.
# ---------------------------------------------------------------------------
class TestGerundDisplayHead:
    def test_cleans_the_reported_class(self):
        # `the monitoring operable to predict ...` (US8706518B2), 22 findings -
        # the whole US Engine-1 pin apart from `respective`.
        assert gerund_display_head("monitoring operable") == "monitoring"
        assert gerund_display_head("comparing indicating") == "comparing"
        assert gerund_display_head("generating further") == "generating"
        assert gerund_display_head("closing thereof") == "closing"

    def test_keeps_a_verb_ambiguous_noun_head(self):
        # THE EXAMINER FN-GUARD CAUGHT THIS ONE. `_should_strip_trailing`
        # returns True for the verb-ambiguous noun `speed`, so an earlier
        # design that trusted "the strip loop consumed everything" emitted
        # `moving` and LOST a real USPTO examiner 112 rejection on app
        # 18613510. The head must be re-earned, never inherited.
        assert gerund_display_head("moving speed") == ""

    def test_keeps_real_element_names(self):
        # A gerund followed by a NOUN is a normal element name, not a
        # predicate. `bonding adhesive` also pins why the `-ive`/`-ed`
        # morphological shortcuts were rejected: `adhesive` and `speed` both
        # look adjectival by suffix and are nouns.
        for term in ("processing unit", "driving unit", "bonding adhesive"):
            assert gerund_display_head(term) == ""

    def test_keeps_terms_damaged_by_a_second_cleaning_pass(self):
        # Re-running `clean_noun_phrase` over its own output is NOT idempotent:
        # its pre-loop 1-2 char variable-identifier strip fires on the already
        # cleaned term. Measured damage: `remote ue` -> `remote` (9 findings),
        # `wlan ap` -> `wlan` (4), `relay ue` -> `relay` (4).
        for term in ("remote ue", "wlan ap", "relay ue", "second ue"):
            assert gerund_display_head(term) == ""

    def test_leading_adjective_is_not_a_gerund_head(self):
        # `the respective said intake and said exhaust ports` - the adjective
        # LEADS and the capture truncated before its head, so there is no noun
        # to fall back to. These are the 6 remaining US pinned residuals and
        # cleaning is deliberately not the lever.
        for term in ("respective one", "respective grouping", "respective"):
            assert gerund_display_head(term) == ""

    def test_single_word_capture_is_untouched(self):
        # Gated on a MULTI-word capture so single-word captures keep the
        # intro-side behaviour exactly and no finding can be added.
        assert gerund_display_head("monitoring") == ""
        assert gerund_display_head("respective") == ""

    def test_intro_side_contract_is_unchanged(self):
        # The intro side must still REJECT a bare gerund - a gerund must never
        # BECOME an antecedent - and must still fall back to the raw capture.
        from patentlint.analysis.utils import clean_noun_phrase
        assert clean_noun_phrase("monitoring") == ""
        assert clean_noun_phrase("monitoring operable") == "monitoring operable"


class TestBareDistributiveSelector:
    """US R50 - a bare selector is not an element reference.

    `a sealing apparatus around the respective said intake and said exhaust
    ports` captures the single word `respective`, because the noun scan stops
    at the determiner that follows. `the` attaches to the noun phrase, not to
    the selector, so the selector can never carry an antecedent of its own.
    ATTORNEY READ (Christopher, 2026-09-02): silence it - and no defect is
    lost, because the real head is flagged by its own reference.
    """

    def _terms(self, text):
        from patentlint.models import Claim
        from patentlint.analysis.claims import check_antecedent_basis
        claims = [Claim(id="1", text=text, independent=True, dependencies=[])]
        return {f["term"] for f in check_antecedent_basis(claims)}

    def test_selector_before_said_is_not_a_reference(self):
        terms = self._terms(
            "A valve system comprising a housing configured to retain a sealing "
            "apparatus around the respective said intake and said exhaust ports."
        )
        assert "respective" not in terms

    def test_selector_before_at_least_one_of_is_not_a_reference(self):
        terms = self._terms(
            "A method comprising receiving a third information element from the "
            "respective at least one of the original source and the potential "
            "relay device."
        )
        assert "respective" not in terms

    def test_the_real_head_is_still_flagged(self):
        # The guard drops a truncation artifact, never the defect: the element
        # the selector modifies is checked by its own reference.
        terms = self._terms(
            "A valve system comprising a housing configured to retain a sealing "
            "apparatus around the respective said intake and said exhaust ports."
        )
        assert terms, "dropping the selector must not empty the claim's findings"

    def test_selector_without_a_following_determiner_is_untouched(self):
        # The guard is gated on evidence that the head continues past the
        # capture. With no determiner following, nothing is assumed.
        from patentlint.analysis.claims import _TRUNCATED_SELECTOR_TRAIL
        assert _TRUNCATED_SELECTOR_TRAIL.match(" said intake and said exhaust")
        assert _TRUNCATED_SELECTOR_TRAIL.match(" at least one of the source")
        assert not _TRUNCATED_SELECTOR_TRAIL.match(" ports of the housing")

    def test_predicative_adjective_set_is_shared_not_duplicated(self):
        # R50 reuses the closed set R49 factored out, so this is not a new
        # one-member denylist and the two cannot drift.
        from patentlint.analysis.utils import (
            _PREDICATIVE_ADJECTIVES, _DISPLAY_POST_MODIFIERS,
        )
        assert "respective" in _PREDICATIVE_ADJECTIVES
        assert _PREDICATIVE_ADJECTIVES <= _DISPLAY_POST_MODIFIERS


class TestUsR51TrailingOvercaptures:
    """US R51 - four over-capture classes from the 2026-09-03 report batch.

    Each fix is shaped by what the CORPUS says about the token, not by the
    token's part of speech in the abstract.
    """

    def test_unconditional_verb_stops_are_not_noun_gray(self):
        # reports #694/#695 (antecedent) and #697/#699/#704 (spec-support).
        # `decays` / `elapses` measure ZERO determiner-preceded occurrences
        # across 1,200 corpus drafts, which is what makes an unconditional stop
        # safe - and unconditional is REQUIRED, because spec-support reaches the
        # phrase through `extract_noun_phrases`, which has no following text.
        assert clean_noun_phrase("motor decays") == "motor"
        assert clean_noun_phrase("preset decay time elapses") == "preset decay time"

    def test_spec_support_sees_the_fix_too(self):
        # The reporter's point on #704: `preset decay time` would have been a
        # correct catch had the term not been miscaptured.
        from patentlint.analysis.utils import extract_noun_phrases
        phrases = extract_noun_phrases(
            "detecting the current of the motor after a preset decay time "
            "elapses from an end time point of the dead time."
        )
        assert "preset decay time" in phrases
        assert "preset decay time elapses" not in phrases

    def test_drives_is_gated_because_it_IS_noun_gray(self):
        # report #695. `drives` has 24 determiner-preceded corpus occurrences
        # (disk drives, belt drives), so it takes the R32/R33 object-determiner
        # gate rather than an unconditional stop.
        from patentlint.analysis.utils import strip_contextual_verb
        assert strip_contextual_verb(
            "output stage circuit drives", " a motor; controlling"
        ) == "output stage circuit"
        # the plural-noun reading is followed by `of` / a predicate, never a
        # bare object determiner
        assert strip_contextual_verb("optical drives", " of the array") == "optical drives"
        assert strip_contextual_verb("the drives", " are coupled") == "the drives"

    def test_measurement_condition_tail(self):
        # reports #705/#706: `a dielectric loss of the glass fiber material
        # under 10 GHz is between 0.0005 and 0.0020`.
        from patentlint.analysis.utils import _strip_measurement_condition_tail as strip
        assert strip("glass fiber material under 10 ghz".split()) == [
            "glass", "fiber", "material"]
        assert strip("signal above 1 ghz".split()) == ["signal"]

    def test_measurement_gate_needs_a_NUMERAL(self):
        # The numeral is the whole discriminator: without it, `under` cannot be
        # told apart from a real element name.
        from patentlint.analysis.utils import _strip_measurement_condition_tail as strip
        for term in ("device under test", "layer under the substrate",
                     "coating over the electrode"):
            assert strip(term.split()) == term.split()

    def test_trailing_not_is_DISPLAY_only(self):
        # report #693. Shipping `not` as an ordinary trailing stop was measured
        # first and silenced SIX gold-legit findings, because the shortened term
        # then resolves. Resolution must be untouched; only the emitted term
        # changes.
        from patentlint.analysis.utils import strip_display_negation
        assert clean_noun_phrase("output stage circuit not") == "output stage circuit not"
        assert strip_display_negation("output stage circuit not") == "output stage circuit"
        assert strip_display_negation("scheduling pdcch not") == "scheduling pdcch"
        assert strip_display_negation("not") == ""

    def test_ends_is_withheld_because_it_is_strongly_noun_gray(self):
        # WITHHELD WITH ITS NUMBER: `ends` has 50 determiner-preceded corpus
        # occurrences, 40 of them followed by `of` - the plural noun `the ends
        # of the shaft`. The verb reading in #694/#695 is distinguished only by
        # a following clause boundary, which noun lists produce too.
        assert clean_noun_phrase("dead time ends") == "dead time ends"
        assert clean_noun_phrase("opposite ends") == "opposite ends"
