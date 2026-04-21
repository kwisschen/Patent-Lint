# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.parser.sections — direct port of Java characterization tests."""

from patentlint.parser.sections import (
    extract_claims_section,
    extract_abstract_section,
    extract_cross_reference_section,
    extract_background_section,
    extract_description_of_drawings_section,
    detect_prior_art_citations,
    detect_patent_document,
)


class TestExtractClaimsSection:
    def test_standard_header(self):
        doc = "BACKGROUND\nSome background text.\n\nCLAIMS\n1. A method comprising step A.\n2. The method of claim 1, further comprising step B.\n\nABSTRACT\nThis is the abstract."
        result = extract_claims_section(doc)
        assert "1. A method comprising step A." in result
        assert "2. The method of claim 1" in result
        assert "ABSTRACT" not in result
        assert "background" not in result

    def test_what_is_claimed(self):
        doc = "SUMMARY\nSome summary.\n\nWhat is claimed is:\n1. An apparatus comprising a widget.\n\nABSTRACT\nAbstract text."
        assert "1. An apparatus comprising a widget." in extract_claims_section(doc)

    def test_no_claims(self):
        assert extract_claims_section("BACKGROUND\nSome text.\nABSTRACT\nAbstract.") == ""

    def test_combined_header(self):
        doc = "CLAIMS\nWhat is claimed is:\n1. A device for processing data.\n\nABSTRACT\nText."
        assert "1. A device for processing data." in extract_claims_section(doc)


class TestExtractAbstractSection:
    def test_standard(self):
        doc = "CLAIMS\n1. A method.\n\nABSTRACT\nA method for doing things is disclosed."
        result = extract_abstract_section(doc)
        assert result.startswith("ABSTRACT")
        assert "A method for doing things is disclosed." in result

    def test_stops_at_reference_numerals(self):
        doc = "ABSTRACT\nA device is shown.\nreference numerals\n100 widget\n200 gadget"
        result = extract_abstract_section(doc)
        assert "A device is shown." in result
        assert "100 widget" not in result

    def test_none(self):
        assert extract_abstract_section("CLAIMS\n1. A method.\n") == ""


class TestExtractCrossReference:
    def test_standard(self):
        doc = "CROSS-REFERENCE TO RELATED APPLICATIONS\nThis application claims priority to 16/123,456.\n\nFIELD OF THE DISCLOSURE\nThis relates to widgets."
        assert "16/123,456" in extract_cross_reference_section(doc)

    def test_absent(self):
        assert extract_cross_reference_section("FIELD OF THE INVENTION\nWidgets.\nBACKGROUND\nStuff.") == ""


class TestExtractBackground:
    def test_standard(self):
        doc = "BACKGROUND OF THE INVENTION\nWidgets have been known for years.\n\nSUMMARY OF THE INVENTION\nWe improve widgets."
        assert "Widgets have been known for years." in extract_background_section(doc)

    def test_disclosure_variant(self):
        doc = "BACKGROUND OF THE DISCLOSURE\nPrior approaches failed.\n\nSUMMARY OF THE DISCLOSURE\nWe succeed."
        assert "Prior approaches failed." in extract_background_section(doc)


class TestExtractDrawings:
    def test_standard(self):
        doc = "BRIEF DESCRIPTION OF THE DRAWINGS\nFIG. 1 shows a widget.\nFIG. 2 shows a gadget.\n\nDETAILED DESCRIPTION OF THE EMBODIMENTS\nThe widget is described."
        result = extract_description_of_drawings_section(doc)
        assert "FIG. 1 shows a widget." in result
        assert "FIG. 2 shows a gadget." in result


class TestDetectPatentDocument:
    def test_claims_header(self):
        """Text with CLAIMS section header → True."""
        assert detect_patent_document("Some text.\nCLAIMS\n1. A method.") is True

    def test_abstract_header(self):
        """Text with ABSTRACT OF THE DISCLOSURE header → True."""
        assert detect_patent_document("ABSTRACT OF THE DISCLOSURE\nA method is disclosed.") is True

    def test_detailed_description_header(self):
        """Text with DETAILED DESCRIPTION header → True."""
        assert detect_patent_document("DETAILED DESCRIPTION\nThe widget includes a base.") is True

    def test_numbered_claims_pattern(self):
        """Text with numbered claims pattern → True."""
        assert detect_patent_document("Preamble text.\n1. A method comprising step A.\n2. The method of claim 1.") is True

    def test_bracketed_paragraph_numbers_alone_rejected(self):
        """[NNNN] numbering alone no longer accepts (Phase 9 #74).

        The convention is shared across US, CN, JP, KO, and several
        European patent offices — too ambiguous to anchor acceptance on.
        A US patent without either an English section header or an
        English claim preamble must bypass the non-patent banner via
        the "Show Results Anyway" button.
        """
        text = "[0001] First paragraph.\n[0002] Second paragraph.\n[0003] Third paragraph."
        assert detect_patent_document(text) is False

    def test_plain_essay(self):
        """Plain essay text with no patent indicators → False."""
        text = "This is an essay about technology. It discusses various topics. The conclusion follows."
        assert detect_patent_document(text) is False

    def test_business_letter(self):
        """Business letter text → False."""
        text = "Dear Mr. Smith,\nPlease find attached the requested documents.\nBest regards,\nJane Doe"
        assert detect_patent_document(text) is False

    def test_single_bracket_not_four_digit(self):
        """Text with only 1 bracketed number (not 4-digit format) → False."""
        text = "See reference [1] for details. Also [2] is relevant."
        assert detect_patent_document(text) is False

    def test_phase_9_73_rejects_cn_patent(self):
        """CN publication export with [NNNN] numbering must not false-positive US.

        The CN [0001] paragraph-number convention shares bracket shape with
        US [NNNN] numbering — the CJK short-circuit is what distinguishes.
        """
        text = (
            "用于调整神经网络的方法和装置\n"
            "[0001] 本申请涉及通信技术领域。\n"
            "[0002] 具体地，本申请涉及一种用于调整神经网络的方法和装置。\n"
            "[0003] 神经网络在无线通信中应用广泛。\n"
        )
        assert detect_patent_document(text) is False

    def test_phase_9_73_rejects_tw_patent(self):
        """TW 【】 section headers + 【NNNN】 paragraph numbers must not false-positive US."""
        text = (
            "【中文發明名稱】\n"
            "蓋組件及帶蓋容器\n"
            "【技術領域】\n"
            "本發明涉及蓋組件的技術領域。\n"
            "【0001】 本發明提供一種蓋組件。\n"
            "【0002】 所述蓋組件包括蓋本體。\n"
            "【0003】 所述蓋本體與外筒構件連接。\n"
        )
        assert detect_patent_document(text) is False

    def test_phase_9_73_accepts_us_with_cjk_prior_art_citation(self):
        """A US patent with a minor foreign-language citation should still pass.

        5% is the rejection threshold; typical US specs that mention a
        foreign application number or a single CJK term stay well below.
        """
        text = (
            "DETAILED DESCRIPTION\n"
            "The invention is described herein. It claims priority to "
            "Japanese Patent Application No. 2023-123456 (特許), which "
            "is incorporated by reference.\n"
            "1. A method comprising step A.\n"
        )
        assert detect_patent_document(text) is True

    def test_phase_9_74_rejects_jp_patent(self):
        """JPO patent (kanji + hiragana + katakana) must not false-positive US."""
        text = (
            "【特許請求の範囲】\n"
            "【請求項1】信号処理方法であって、\n"
            "第1の信号を受信するステップと、\n"
            "前記信号をニューラルネットワークで処理するステップと、を含む方法。\n"
        )
        assert detect_patent_document(text) is False

    def test_phase_9_74_rejects_ko_patent(self):
        """KIPO patent (Hangul) must not false-positive US.

        Hangul is outside the original CJK range, so before Phase 9 #74
        a Korean draft with [0001] numbering would have slipped through.
        """
        text = (
            "【청구항 1】\n"
            "장치에 있어서,\n"
            "처리기와,\n"
            "상기 처리기에 연결된 저장 매체를 포함하는 장치.\n"
            "[0001] 본 발명은 신호 처리 장치에 관한 것이다.\n"
            "[0002] 보다 구체적으로는 신경망을 이용한 처리 장치이다.\n"
            "[0003] 종래 기술의 문제점을 해결한다.\n"
        )
        assert detect_patent_document(text) is False

    def test_phase_9_74_rejects_de_patent(self):
        """DPMA / EPO German patent must not false-positive US.

        German patents share the [NNNN] paragraph-numbering convention
        but use German section headers (Patentansprüche, Beschreibung)
        and German claim preambles (Ein, Eine, Das). Removing the bare
        [NNNN] heuristic is what closes this gap.
        """
        text = (
            "Patentansprüche\n"
            "1. Ein Verfahren zur Signalverarbeitung, umfassend:\n"
            "das Empfangen eines ersten Signals, und\n"
            "das Verarbeiten des Signals mit einem neuronalen Netz.\n"
            "[0001] Die Erfindung betrifft die Signalverarbeitung.\n"
            "[0002] Genauer gesagt neuronale Netze.\n"
            "[0003] Der Stand der Technik löst das Problem nicht.\n"
        )
        assert detect_patent_document(text) is False

    def test_phase_9_74_rejects_fr_patent(self):
        """INPI / EPO French patent must not false-positive US."""
        text = (
            "Revendications\n"
            "1. Un procédé de traitement du signal, comprenant :\n"
            "la réception d'un premier signal, et\n"
            "le traitement du signal avec un réseau neuronal.\n"
            "[0001] La présente invention concerne le traitement du signal.\n"
            "[0002] Plus précisément, les réseaux neuronaux.\n"
            "[0003] L'art antérieur ne résout pas le problème.\n"
        )
        assert detect_patent_document(text) is False


class TestDetectPriorArtCitations:
    def test_found(self):
        text = "U.S. Patent No. 7,654,321 discloses a widget. Also see 10,123,456."
        result = detect_prior_art_citations(text)
        assert "7,654,321" in result
        assert "10,123,456" in result

    def test_none(self):
        assert detect_prior_art_citations("Widgets have been known for a long time.") == ""
