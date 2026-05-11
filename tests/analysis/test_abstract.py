# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Tests for patentlint.analysis.abstract."""

from patentlint.analysis.abstract import (
    _IMPLIED_PHRASES,
    _LEGAL_PHRASEOLOGY_ABSTRACT_RE,
    _MERIT_LANGUAGE_ABSTRACT_RE,
    count_words,
    is_single_paragraph_and_final,
    has_implied_phrase,
    detect_implied_phrases,
    detect_legal_phraseology,
    detect_legal_phraseology_items,
    detect_merit_language,
    detect_merit_language_items,
)


class TestCountWords:
    def test_standard(self):
        assert count_words("ABSTRACT\nA method for doing things with widgets.") == 8

    def test_empty(self):
        assert count_words("") == 0
        assert count_words(None) == 0

    def test_boundary_150(self):
        text = " ".join(["word"] * 150)
        assert count_words(text) == 150


class TestSingleParagraphAndFinal:
    def test_valid(self):
        abstract = "ABSTRACT\nA method for processing data is disclosed."
        doc = "Some content.\n" + abstract
        assert is_single_paragraph_and_final(doc, abstract) is True

    def test_multi_paragraph(self):
        abstract = "ABSTRACT\nFirst paragraph.\nSecond paragraph."
        doc = "Some content.\n" + abstract
        assert is_single_paragraph_and_final(doc, abstract) is False

    def test_no_period(self):
        abstract = "ABSTRACT\nA method for processing data"
        doc = "Some content.\n" + abstract
        assert is_single_paragraph_and_final(doc, abstract) is False


class TestImpliedPhrase:
    def test_is_provided(self):
        assert has_implied_phrase("A method is provided for processing.") is True

    def test_disclosure(self):
        assert has_implied_phrase("This disclosure relates to widgets.") is True

    def test_clean(self):
        assert has_implied_phrase("A method for processing data includes steps A and B.") is False


class TestDetectImpliedPhrases:
    """detect_implied_phrases surfaces the actual matched tokens so the
    UI can show users WHICH phrase triggered the finding."""

    def test_is_provided(self):
        assert detect_implied_phrases("A method is provided for processing.") == ["is provided"]

    def test_are_provided(self):
        assert detect_implied_phrases("Several improvements are provided herein.") == ["are provided"]

    def test_disclosure(self):
        assert detect_implied_phrases("This disclosure relates to widgets.") == ["disclosure"]

    def test_multiple(self):
        # "A disclosure is provided for..." → both trigger
        phrases = detect_implied_phrases("A disclosure is provided for processing.")
        assert "is provided" in phrases
        assert "disclosure" in phrases

    def test_clean(self):
        assert detect_implied_phrases("A method for processing data includes steps A and B.") == []

    def test_empty_input(self):
        assert detect_implied_phrases("") == []


class TestLegalPhraseology:
    """MPEP § 608.01(b): 'the form and legal phraseology often used in
    patent claims, such as means and said, should be avoided.' The MPEP names
    only two examples but the rule is the CLASS of claim-style phraseology.
    Practitioner guidance (BlueIron IP, IPWatchdog, Patent Trademark Blog)
    agrees that comprising-mutations, wherein, thereof, and the same all
    qualify under the same § 608.01(b) prohibition."""

    def test_names_means_and_said(self):
        result = detect_legal_phraseology("A method using means for said processing.")
        assert "means" in result
        assert "said" in result

    def test_comprising_mutations(self):
        result = detect_legal_phraseology("A method comprising steps. A widget comprises parts. A system comprised of modules. The article comprise.")
        assert "comprising" in result
        assert "comprises" in result
        assert "comprised" in result
        assert "comprise" in result

    def test_wherein(self):
        result = detect_legal_phraseology("A device wherein the processor runs.")
        assert "wherein" in result

    def test_thereof_and_the_same(self):
        result = detect_legal_phraseology("A method for processing thereof and the same.")
        assert "thereof" in result
        assert "the same" in result

    def test_does_not_catch_merit_language(self):
        # merit-family is the meritLanguage detector's job.
        assert detect_legal_phraseology_items("A novel and innovative widget.") == []

    def test_does_not_catch_absolute_quantifiers(self):
        # 'always', 'never', 'must' are § 2173.05(b) claim-indefiniteness terms,
        # not § 608.01(b) legal phraseology. Keep out.
        assert detect_legal_phraseology_items("must always process and never omit") == []

    def test_clean(self):
        assert detect_legal_phraseology("A widget that processes data.") == ""


class TestMeritLanguage:
    """MPEP § 608.01(b): 'should not refer to purported merits... of the
    invention.' Covers evaluative adjectives and self-referential phrasing."""

    def test_evaluative_adjectives(self):
        result = detect_merit_language("A novel and innovative method for unique processing.")
        assert "novel" in result
        assert "innovative" in result
        assert "unique" in result

    def test_evaluative_nouns(self):
        result = detect_merit_language("An important and significant method.")
        assert "important" in result
        assert "significant" in result

    def test_merit_and_advantage(self):
        result = detect_merit_language("The method has merit and multiple advantages.")
        assert "merit" in result
        assert "advantages" in result

    def test_present_invention(self):
        result = detect_merit_language("The present invention relates to widgets.")
        assert "present invention" in result

    def test_does_not_catch_absolute_quantifiers(self):
        # 'always', 'never', 'must' are § 2173.05 claim-indefiniteness terms,
        # not § 608.01(b) merit terms. Keep out.
        assert detect_merit_language_items("must always be used and never omitted") == []

    def test_clean(self):
        assert detect_merit_language("A widget that processes data.") == ""


class TestDetectorMutualExclusivity:
    """Invariant: tokens handled by the dedicated detect_implied_phrases must
    NOT also be caught by detect_legal_phraseology or detect_merit_language.
    Without this invariant, an opening pattern like 'A method is provided…'
    triggers both checks and the UI renders the same token under two cards."""

    def test_implied_phrase_tokens_not_in_other_detectors(self):
        for phrase in _IMPLIED_PHRASES:
            assert not _LEGAL_PHRASEOLOGY_ABSTRACT_RE.search(phrase), (
                f"Token '{phrase}' is in _IMPLIED_PHRASES and also matches "
                f"_LEGAL_PHRASEOLOGY_ABSTRACT_RE — remove from the latter. "
                f"Dedicated detectors take precedence."
            )
            assert not _MERIT_LANGUAGE_ABSTRACT_RE.search(phrase), (
                f"Token '{phrase}' is in _IMPLIED_PHRASES and also matches "
                f"_MERIT_LANGUAGE_ABSTRACT_RE — remove from the latter."
            )

    def test_legal_and_merit_detectors_cover_disjoint_tokens(self):
        """Same-category tokens should not be caught by both detectors; the
        split is supposed to be clean MPEP § 608.01(b) subcategorization."""
        text = "A novel means is said to be present invention."
        legal = set(detect_legal_phraseology_items(text))
        merit = set(detect_merit_language_items(text))
        assert legal & merit == set(), (
            f"Overlap between legal phraseology and merit language detectors: "
            f"{legal & merit}. Each token should belong to exactly one subcategory."
        )

    def test_opening_implied_sentence_not_double_flagged(self):
        text = "A method is provided for processing data. The novel method has advantages."
        implied = detect_implied_phrases(text)
        legal = detect_legal_phraseology_items(text)
        merit = detect_merit_language_items(text)
        assert "is provided" in implied
        # 'is provided' / 'disclosure' / 'are provided' are implied-only.
        assert not any(tok in ("disclosure", "is provided", "are provided") for tok in legal)
        assert not any(tok in ("disclosure", "is provided", "are provided") for tok in merit)
        # 'novel' and 'advantages' legitimately flagged by merit detector.
        assert "novel" in merit
        assert "advantages" in merit
