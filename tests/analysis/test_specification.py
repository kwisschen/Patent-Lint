# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for patentlint.analysis.specification."""

from patentlint.analysis.specification import (
    has_valid_ending,
    are_paragraphs_sequential,
    get_last_sequential_index,
    detect_restrictive_wording,
    has_sequence_listing_mismatch,
    check_required_sections,
    check_title,
)
from patentlint.models import AnalysisResult


class TestValidEnding:
    def test_period(self):
        assert has_valid_ending("Some text.") is True

    def test_colon(self):
        assert has_valid_ending("Some text:") is True

    def test_semicolon_drawings(self):
        assert has_valid_ending("Some text;", is_description_of_drawings=True) is True
        assert has_valid_ending("Some text;", is_description_of_drawings=False) is False

    def test_semicolon_and_drawings(self):
        assert has_valid_ending("Some text; and", is_description_of_drawings=True) is True
        assert has_valid_ending("Some text; and", is_description_of_drawings=False) is False

    def test_no_punctuation(self):
        assert has_valid_ending("Some text") is False

    def test_quoted(self):
        assert has_valid_ending('He said "done."') is True
        assert has_valid_ending("He said \u201Cdone.\u201D") is True


class TestParagraphSequentiality:
    def test_sequential(self):
        assert are_paragraphs_sequential([1, 2, 3, 4, 5]) is True

    def test_gap(self):
        assert are_paragraphs_sequential([1, 2, 4, 5]) is False

    def test_last_index(self):
        assert get_last_sequential_index([1, 2, 3, 5, 6]) == 3


class TestParagraphSequentialCheck:
    """Tests for the paragraph sequential check logic in AnalysisResult.to_report_data()."""

    def _get_paragraph_check(self, result):
        report = result.to_report_data()
        return next(
            (c for c in report.specification_checks
             if c.message_key and c.message_key.startswith("check.spec.paragraphSequential")),
            None,
        )

    def test_zero_paragraphs_patent_emits_amend(self):
        result = AnalysisResult(paragraph_count=0, likely_patent=True)
        check = self._get_paragraph_check(result)
        assert check is not None
        assert check.status == "amend"
        assert check.message_key == "check.spec.paragraphSequential.missing"

    def test_zero_paragraphs_non_patent_no_amend(self):
        result = AnalysisResult(paragraph_count=0, likely_patent=False)
        check = self._get_paragraph_check(result)
        assert check is not None
        assert check.status != "amend"

    def test_sequential_paragraphs_pass(self):
        result = AnalysisResult(
            paragraph_count=5, paragraphs_sequential=True, likely_patent=True,
        )
        check = self._get_paragraph_check(result)
        assert check is not None
        assert check.status == "pass"
        assert check.message_key == "check.spec.paragraphSequential.pass"

    def test_non_sequential_paragraphs_amend(self):
        result = AnalysisResult(
            paragraph_count=5, paragraphs_sequential=False,
            last_sequential_paragraph=3, likely_patent=True,
        )
        check = self._get_paragraph_check(result)
        assert check is not None
        assert check.status == "amend"
        assert check.message_key == "check.spec.paragraphSequential.amend"


class TestRestrictiveWording:
    def test_detected(self):
        result = detect_restrictive_wording("The device must always perform this step.", 5)
        assert 5 in result.flagged_paragraphs
        assert "must" in result.formatted_phrases
        assert "always" in result.formatted_phrases

    def test_mpep_narrowing_terms(self):
        """MPEP 2111.01(II) narrowing language: critical/essential/vital/necessary/imperative."""
        result = detect_restrictive_wording(
            "This feature is critical, essential, vital, and necessary.", 3
        )
        assert 3 in result.flagged_paragraphs
        for term in ("critical", "essential", "vital", "necessary"):
            assert term in result.formatted_phrases

    def test_absolute_quantifiers(self):
        result = detect_restrictive_wording(
            "The system must never fail, and solely operates in every mode.", 7
        )
        assert 7 in result.flagged_paragraphs
        for term in ("must", "never", "solely", "every"):
            assert term in result.formatted_phrases

    def test_phase_9_72b_tightened_terms_pass(self):
        """Removed in Phase 9 #72b: 'invention', 'particular', 'specific', 'key'
        are standard drafting words that were dominating verify noise with
        non-narrowing uses."""
        result = detect_restrictive_wording(
            "The present invention relates to a particular embodiment "
            "with a specific example illustrating the key feature.",
            4,
        )
        assert result.flagged_paragraphs == []

    def test_clean(self):
        result = detect_restrictive_wording("The device processes data according to the configuration.", 1)
        assert result.flagged_paragraphs == []


class TestSequenceListing:
    def test_mismatch(self):
        assert has_sequence_listing_mismatch("The protein has SEQ ID NO 1 and performs a function.") is True

    def test_no_mismatch(self):
        text = "STATEMENT REGARDING SEQUENCE LISTING\nSee attached.\nThe protein has SEQ ID NO 1."
        assert has_sequence_listing_mismatch(text) is False

    def test_no_seq_id(self):
        assert has_sequence_listing_mismatch("Normal patent text.") is False


def _make_full_doc(**overrides):
    """Build a full patent document with all sections present by default.

    Uses DISCLOSURE variants (modern patent practice) as defaults.
    """
    sections = {
        "title": "WIDGET FOR PROCESSING DATA",
        "cross_ref": "CROSS-REFERENCE TO RELATED APPLICATIONS\nThis application claims priority to U.S. App 16/123,456.",
        "background": "BACKGROUND OF THE DISCLOSURE\nWidgets are well known in the art.",
        "summary": "SUMMARY OF THE DISCLOSURE\nA widget is disclosed.",
        "brief_drawings": "BRIEF DESCRIPTION OF THE DRAWINGS\nFIG. 1 shows the widget.",
        "detailed_desc": "DETAILED DESCRIPTION OF THE EXEMPLARY EMBODIMENTS\nThe widget 100 includes a base plate 102.",
        "claims": "CLAIMS\n1. A widget comprising a base plate.",
        "abstract": "ABSTRACT OF THE DISCLOSURE\nA widget for processing data is disclosed.",
    }
    sections.update(overrides)
    parts = [v for v in sections.values() if v]
    return "\n\n".join(parts)


class TestRequiredSections:
    def test_all_sections_present(self):
        doc = _make_full_doc()
        results = check_required_sections(doc)
        statuses = [r.status for r in results]
        assert "amend" not in statuses
        assert any(r.message_key == "checks.required_sections_pass" for r in results)

    def test_missing_background_and_summary(self):
        doc = _make_full_doc(background="", summary="")
        results = check_required_sections(doc)
        amend = [r for r in results if r.status == "amend"]
        assert len(amend) == 1
        assert "Background of the Invention" in amend[0].message
        assert "Brief Summary of the Invention" in amend[0].message

    def test_missing_only_cross_reference_is_verify(self):
        doc = _make_full_doc(cross_ref="")
        results = check_required_sections(doc)
        assert not any(r.status == "amend" for r in results)
        verify = [r for r in results if r.status == "verify"]
        assert len(verify) == 1
        assert verify[0].message_key == "checks.optional_section_missing"

    def test_minimal_doc_claims_and_abstract_only(self):
        # No figure references in the body → BDoD is conditionally
        # not required (37 CFR 1.74). Other required sections still
        # missing should be flagged.
        doc = (
            "CLAIMS\n1. A widget comprising a base plate.\n\n"
            "ABSTRACT OF THE DISCLOSURE\nA widget is disclosed."
        )
        results = check_required_sections(doc)
        amend = [r for r in results if r.status == "amend"]
        assert len(amend) == 1
        assert "Background" in amend[0].message
        assert "Summary" in amend[0].message
        assert "Detailed Description" in amend[0].message
        # BDoD NOT required when no figures are mentioned anywhere in body.
        assert "Brief Description of the Drawings" not in amend[0].message

    def test_bdod_required_when_figures_referenced(self):
        # Body mentions FIG. 1 but the BDoD heading is removed —
        # BDoD must surface as missing per 37 CFR 1.74.
        doc = (
            "TITLE OF THE INVENTION\nWidget With Base Plate\n\n"
            "BACKGROUND OF THE INVENTION\nWidgets are known.\n\n"
            "BRIEF SUMMARY OF THE INVENTION\nA widget is disclosed.\n\n"
            "DETAILED DESCRIPTION OF THE INVENTION\nFIG. 1 shows the widget.\n\n"
            "CLAIMS\n1. A widget comprising a base plate.\n\n"
            "ABSTRACT OF THE DISCLOSURE\nA widget is disclosed."
        )
        results = check_required_sections(doc)
        amend = [r for r in results if r.status == "amend"]
        assert len(amend) == 1
        assert "Brief Description of the Drawings" in amend[0].message

    def test_variant_header_spellings(self):
        doc = "\n\n".join([
            "METHOD FOR DATA PROCESSING",
            "BACKGROUND",
            "Widgets are known.",
            "SUMMARY",
            "A method is disclosed.",
            "DESCRIPTION OF THE DRAWINGS",
            "FIG. 1 shows the method.",
            "DETAILED DESCRIPTION OF THE PREFERRED EMBODIMENTS",
            "The method includes steps.",
            "CLAIMS",
            "1. A method for processing data.",
            "ABSTRACT",
            "A method for data processing.",
        ])
        results = check_required_sections(doc)
        assert not any(r.status == "amend" for r in results)
        assert any(r.message_key == "checks.required_sections_pass" for r in results)

    def test_invention_variants(self):
        """INVENTION family headers should also be recognized."""
        doc = "\n\n".join([
            "APPARATUS FOR SIGNAL PROCESSING",
            "CROSS-REFERENCE TO RELATED APPLICATIONS",
            "This claims priority.",
            "BACKGROUND OF THE INVENTION",
            "Signal processing is known.",
            "BRIEF SUMMARY OF THE INVENTION",
            "An apparatus is disclosed.",
            "BRIEF DESCRIPTION OF THE DRAWINGS",
            "FIG. 1 shows the apparatus.",
            "DETAILED DESCRIPTION OF THE INVENTION",
            "The apparatus includes a processor.",
            "CLAIMS",
            "1. An apparatus for signal processing.",
            "ABSTRACT OF THE INVENTION",
            "An apparatus for signal processing is disclosed.",
        ])
        results = check_required_sections(doc)
        assert not any(r.status == "amend" for r in results)
        assert any(r.message_key == "checks.required_sections_pass" for r in results)

    def test_bare_summary_detected(self):
        """Plain 'SUMMARY' without qualifier should be detected."""
        doc = _make_full_doc(summary="SUMMARY\nA widget is disclosed.")
        results = check_required_sections(doc)
        assert not any(r.status == "amend" for r in results)

    def test_disclosure_variants(self):
        """DISCLOSURE family headers (modern practice) should be recognized."""
        doc = "\n\n".join([
            "SURGE PROTECTION CIRCUIT",
            "CROSS-REFERENCE TO RELATED PATENT APPLICATION",
            "This claims priority to U.S. App 17/456,789.",
            "BACKGROUND OF THE DISCLOSURE",
            "Surge protection is known.",
            "SUMMARY OF THE DISCLOSURE",
            "A circuit is disclosed.",
            "BRIEF DESCRIPTION OF THE DRAWINGS",
            "FIG. 1 shows the circuit.",
            "DETAILED DESCRIPTION OF THE DISCLOSURE",
            "The circuit includes a varistor.",
            "CLAIMS",
            "1. A surge protection circuit.",
            "ABSTRACT OF THE DISCLOSURE",
            "A surge protection circuit is disclosed.",
        ])
        results = check_required_sections(doc)
        assert not any(r.status == "amend" for r in results)
        assert any(r.message_key == "checks.required_sections_pass" for r in results)

    def test_brief_summary_of_disclosure(self):
        """'BRIEF SUMMARY OF THE DISCLOSURE' should be detected."""
        doc = _make_full_doc(summary="BRIEF SUMMARY OF THE DISCLOSURE\nA widget is disclosed.")
        results = check_required_sections(doc)
        assert not any(r.status == "amend" for r in results)

    def test_no_recognizable_headers(self):
        doc = "This is just some random text with no patent structure at all."
        results = check_required_sections(doc)
        amend = [r for r in results if r.status == "amend"]
        assert len(amend) == 1
        assert amend[0].message_key == "checks.required_sections_missing"


class TestCheckTitle:
    def test_missing_title(self):
        results = check_title("")
        assert len(results) == 1
        assert results[0].status == "amend"
        assert results[0].message_key == "check.spec.title.amendMissing"

    def test_pass(self):
        results = check_title("Method and Apparatus for Widget Assembly")
        assert len(results) == 1
        assert results[0].status == "pass"
        assert results[0].message_key == "check.spec.title.pass"

    def test_too_long(self):
        # 501 characters
        long_title = "A " + ("very " * 100) + "title"
        assert len(long_title) >= 500
        results = check_title(long_title)
        assert any(
            r.message_key == "check.spec.title.amendLength" for r in results
        )

    def test_trademark_rejected(self):
        results = check_title("Coca-Cola® Bottling Method")
        assert any(
            r.message_key == "check.spec.title.amendContent" for r in results
        )

    def test_model_number_rejected(self):
        results = check_title("Widget XJ-9000 Assembly System")
        assert any(
            r.message_key == "check.spec.title.amendContent" for r in results
        )

    def test_wordy_title_verify(self):
        # 18 words
        wordy = " ".join(["word"] * 18)
        results = check_title(wordy)
        assert any(
            r.message_key == "check.spec.title.verify" for r in results
        )

    def test_short_title_no_verify(self):
        # Five words — no warning.
        results = check_title("Method for Assembling a Widget")
        assert all(
            r.message_key != "check.spec.title.verify" for r in results
        )


class TestScopeLimitWording:
    """check_scope_limit_wording — MPEP § 2111 + Phillips v. AWH.

    Detects "the (present) invention" / "this invention" in spec body
    text. REVIEW-level — many drafts use these benignly; the check
    surfaces count + samples for drafter triage.
    """

    def test_pass_on_clean_spec(self):
        from patentlint.analysis.specification import check_scope_limit_wording
        results = check_scope_limit_wording(
            "Embodiments may include a housing 102 and a controller 110."
        )
        assert len(results) == 1
        assert results[0].status == "pass"
        assert results[0].message_key == "check.spec.scopeLimitWording.pass"

    def test_pass_on_empty(self):
        from patentlint.analysis.specification import check_scope_limit_wording
        results = check_scope_limit_wording("")
        assert results[0].status == "pass"

    def test_verify_present_invention(self):
        from patentlint.analysis.specification import check_scope_limit_wording
        results = check_scope_limit_wording(
            "The present invention provides a system for processing data."
        )
        assert len(results) == 1
        assert results[0].status == "verify"
        assert results[0].message_key == "check.spec.scopeLimitWording.verify"
        assert results[0].details_params["count"] == 1

    def test_verify_this_invention(self):
        from patentlint.analysis.specification import check_scope_limit_wording
        results = check_scope_limit_wording(
            "This invention relates to a system. In one aspect of this "
            "invention, a controller is provided."
        )
        assert results[0].status == "verify"
        assert results[0].details_params["count"] == 2

    def test_verify_the_invention_alone(self):
        """'the invention' (without 'present') should also fire."""
        from patentlint.analysis.specification import check_scope_limit_wording
        results = check_scope_limit_wording(
            "Aspects of the invention will now be described."
        )
        assert results[0].status == "verify"

    def test_case_insensitive(self):
        from patentlint.analysis.specification import check_scope_limit_wording
        results = check_scope_limit_wording(
            "THE PRESENT INVENTION provides a system."
        )
        assert results[0].status == "verify"

    def test_samples_capped_at_5(self):
        """Sample list capped at 5; 'extra' carries the overflow count."""
        from patentlint.analysis.specification import check_scope_limit_wording
        text = " ".join(["The present invention does X."] * 8)
        results = check_scope_limit_wording(text)
        assert results[0].details_params["count"] == 8
        assert len(results[0].details_params["samples"]) == 5
        assert results[0].details_params["extra"] == 3

    def test_does_not_match_unrelated_invention_word(self):
        """'inventions' (plural) is intentionally not matched — different
        register; drafters don't use it as a scope-defining phrase."""
        from patentlint.analysis.specification import check_scope_limit_wording
        results = check_scope_limit_wording(
            "Various inventions in this field include systems."
        )
        # 'this field' shouldn't match; 'inventions' shouldn't match either.
        # But 'various inventions' contains no whole-word 'invention' so the
        # \binvention\b boundary excludes it.
        # Actually re.IGNORECASE + \binvention\b matches 'invention' but
        # not 'inventions' since \b is at the boundary.
        # Verify pass behavior:
        assert results[0].status == "pass"


class TestNumeralConsistencyD1:
    """check_numeral_consistency — MPEP § 608.01(g) D1.

    Same numeral with multiple distinct element names = drafter copy-paste
    error. Same name with multiple numerals is permitted (legit multiple
    instances) and intentionally NOT flagged.
    """

    def test_pass_on_clean_spec(self):
        from patentlint.analysis.specification import check_numeral_consistency
        results = check_numeral_consistency(
            "The housing 102 holds a controller 110 connected to a sensor 120."
        )
        assert results[0].status == "pass"
        assert results[0].message_key == "check.spec.numeralConsistency.pass"

    def test_pass_on_empty(self):
        from patentlint.analysis.specification import check_numeral_consistency
        assert check_numeral_consistency("")[0].status == "pass"

    def test_pass_on_no_numerals(self):
        from patentlint.analysis.specification import check_numeral_consistency
        assert check_numeral_consistency(
            "The system has many parts that work together."
        )[0].status == "pass"

    def test_d1_same_numeral_different_names_amend(self):
        """Real D1: numeral 102 used with two truly disjoint names, each
        appearing ≥2 times. Precision filter requires both repetition
        AND no shared content word."""
        from patentlint.analysis.specification import check_numeral_consistency
        results = check_numeral_consistency(
            "The housing 102 holds a sensor. The housing 102 is metal. "
            "The container 102 contains liquid. The container 102 is sealed."
        )
        assert results[0].status == "amend"
        assert results[0].message_key == "check.spec.numeralConsistency.amend"
        assert results[0].details_params["count"] == 1
        finding = results[0].details_params["findings"][0]
        # Numerals are strings now (Latin-prefix refs like LD1 supported)
        assert finding["numeral"] == "102"
        # New canonical+outliers shape: each finding has a canonical
        # name (most-frequent) and outlier list. Both 'housing' and
        # 'container' must appear (one as canonical, one as outlier).
        all_names = [finding["canonical"]] + [o["name"] for o in finding["outliers"]]
        assert "housing" in all_names
        assert "container" in all_names

    def test_single_occurrence_alternate_filtered(self):
        """One occurrence of an alternate name is regex noise — don't flag.
        Real D1 conflicts have both names appearing repeatedly."""
        from patentlint.analysis.specification import check_numeral_consistency
        results = check_numeral_consistency(
            "The housing 102 holds a controller. The housing 102 is metal. "
            "The housing 102 is durable. With respect to 102 grams, the result is X."
        )
        # 'respect' is a single-occurrence noise capture; should be filtered
        assert results[0].status == "pass"

    def test_low_total_occurrences_filtered(self):
        """Numerals appearing <3 times total are likely measurements,
        not real reference numerals. Don't flag."""
        from patentlint.analysis.specification import check_numeral_consistency
        # Each numeral appears only twice (1x each name) — below the
        # ≥3-total threshold required for D1 emission
        results = check_numeral_consistency(
            "The housing 102 is heavy. The container 102 is light."
        )
        assert results[0].status == "pass"

    def test_d2_same_name_different_numerals_does_not_fire(self):
        """Multiple physical instances of same element type get distinct
        numerals — this is normal drafting and must NOT fire."""
        from patentlint.analysis.specification import check_numeral_consistency
        results = check_numeral_consistency(
            "The pillar 4 supports the frame. The pillar 5 supports the wall. "
            "The pillar 6 supports the panel."
        )
        # Three pillars with three numerals — each numeral has only one name
        # ('pillar'). D1 doesn't fire.
        assert results[0].status == "pass"

    def test_multiple_conflicts(self):
        """Two genuine D1 conflicts — each name repeated."""
        from patentlint.analysis.specification import check_numeral_consistency
        results = check_numeral_consistency(
            "The housing 102 is metal. The housing 102 is heavy. "
            "The container 102 is plastic. The container 102 holds water. "
            "The motor 200 spins fast. The motor 200 is electric. "
            "The pump 200 fills the tank. The pump 200 is reliable."
        )
        assert results[0].status == "amend"
        assert results[0].details_params["count"] == 2

    def test_extract_pairs_returns_per_occurrence(self):
        from patentlint.analysis.specification import extract_numeral_name_pairs
        pairs = extract_numeral_name_pairs(
            "The housing 102 is here. The housing 102 also appears again."
        )
        # Two occurrences of (102, 'housing') — both kept
        # Numerals are now strings (to support Latin-prefix refs like LD1)
        assert len(pairs) == 2
        assert all(p[0] == "102" and "housing" in p[1] for p in pairs)


class TestNumeralConsistencyD1Synthetic:
    """Synthetic edge-case suite for D1 — covers cases from real drafter
    feedback (Latin-prefix refs, single-occurrence typos, ordinal-instance
    collisions, letter-suffix preservation, suffix-cluster merging) so
    these defects don't silently regress."""

    def test_latin_prefix_collision(self):
        """LD1 used with two disjoint elements — common in circuit
        patents (low-bridge switch / high-bridge switch notation)."""
        from patentlint.analysis.specification import check_numeral_consistency
        results = check_numeral_consistency(
            "The first low-bridge switch LD1 connects to source. "
            "The first low-bridge switch LD1 has a gate. "
            "The second high-bridge switch LD1 connects to drain. "
            "The second high-bridge switch LD1 has another gate."
        )
        assert results[0].status == "amend"
        finding = results[0].details_params["findings"][0]
        assert finding["numeral"] == "LD1"

    def test_single_occurrence_typo_with_existing_canonical(self):
        """User's actual D1 case: drafter has 'voltage threshold setting
        circuit 10' (×many, canonical) and ONE accidental 'voltage
        difference calculating circuit 10' typo. The two phrases share
        ('voltage', 'circuit') yet identify completely different parts;
        Case B distinguishing-word check catches it."""
        from patentlint.analysis.specification import check_numeral_consistency
        results = check_numeral_consistency(
            "The voltage threshold setting circuit 10 is fast. "
            "The voltage threshold setting circuit 10 is connected. "
            "The voltage threshold setting circuit 10 emits a signal. "
            "The voltage threshold setting circuit 10 is calibrated. "
            "Now the voltage difference calculating circuit 10 outputs."
        )
        assert results[0].status == "amend"
        finding = results[0].details_params["findings"][0]
        assert finding["numeral"] == "10"
        # Inline summary must surface the conflicting names so users can
        # navigate to the typo without opening details.
        assert "inline_summary" in results[0].details_params
        assert "threshold" in results[0].details_params["inline_summary"].lower()
        assert "calculating" in results[0].details_params["inline_summary"].lower()

    def test_letter_suffix_distinct(self):
        """10a and 10b are sub-instance distinct refs — must not collapse
        into '10' bucket."""
        from patentlint.analysis.specification import extract_numeral_name_pairs
        pairs = extract_numeral_name_pairs(
            "The first lens 10a focuses light. The first lens 10a is "
            "convex. The second lens 10b diverges light. The second "
            "lens 10b is concave."
        )
        nums = {p[0] for p in pairs}
        assert "10a" in nums
        assert "10b" in nums

    def test_ordinal_instance_collision(self):
        """First switch 30 vs third switch 30 — same head with different
        ordinal = drafter assigned same numeral to two instances."""
        from patentlint.analysis.specification import check_numeral_consistency
        results = check_numeral_consistency(
            "The first switch 30 closes. The first switch 30 is fast. "
            "The third switch 30 opens. The third switch 30 is slow."
        )
        assert results[0].status == "amend"
        finding = results[0].details_params["findings"][0]
        assert finding["case"] == "instance"

    def test_suffix_cluster_merges_un_stripped_subjects(self):
        """'present disclosure comprises lens 10' should merge into
        canonical 'lens 10' rather than appearing as a separate outlier."""
        from patentlint.analysis.specification import (
            _detect_d1_conflicts,
            extract_numeral_name_pairs,
        )
        pairs = extract_numeral_name_pairs(
            "The lens 10 is convex. The lens 10 is glass. "
            "The lens 10 transmits light. "
            "Wherein the optical assembly comprises lens 10."
        )
        conflicts = _detect_d1_conflicts(pairs)
        # Cluster merge means no real conflict surfaces here
        assert all(c["numeral"] != "10" for c in conflicts)

    def test_year_excluded(self):
        """1995 / 2026 are years, not refnums."""
        from patentlint.analysis.specification import check_numeral_consistency
        results = check_numeral_consistency(
            "Filed in 1995, the original patent 1995 was published. "
            "Updated in 2026, the new patent 2026 was filed."
        )
        assert results[0].status == "pass"

    def test_unit_excluded(self):
        """Numbers followed by units (mm, %, °C) are measurements."""
        from patentlint.analysis.specification import check_numeral_consistency
        results = check_numeral_consistency(
            "The diameter is 102 mm. The thickness is 102%. "
            "The temperature is 102°C. The voltage is 102 mV."
        )
        assert results[0].status == "pass"


class TestNumeralConsistencyD1CN:
    """CJK D1 — same canonical+outliers semantics with iterative-strip
    + suffix-cluster merge. These tests exercise CN/TW capture quirks."""

    def test_cn_iterative_strip_handles_compound_prefix(self):
        from patentlint.analysis.cn_specification import (
            _cn_d1_head_noun_with_ordinal,
        )
        # 則是設置在第一手柄主體 — 4-layer prefix peel
        assert _cn_d1_head_noun_with_ordinal(
            "則是設置在第一手柄主體"
        ) == "第一手柄主體"

    def test_cn_quantifier_strip(self):
        from patentlint.analysis.cn_specification import (
            _cn_d1_head_noun_with_ordinal,
        )
        # 各個 / 多個 / 的 all should peel
        assert _cn_d1_head_noun_with_ordinal(
            "各個第一外齒狀結構"
        ) == "第一外齒狀結構"
        assert _cn_d1_head_noun_with_ordinal(
            "的多個第一外齒狀結構"
        ) == "第一外齒狀結構"

    def test_cn_figure_ref_filtered(self):
        from patentlint.analysis.cn_specification import (
            _cn_d1_head_noun_with_ordinal,
        )
        # 至圖, 和圖, 如圖 — ending in 圖/图 = figure context
        assert _cn_d1_head_noun_with_ordinal("至圖") == ""
        assert _cn_d1_head_noun_with_ordinal("和圖") == ""
        assert _cn_d1_head_noun_with_ordinal("如圖") == ""
        assert _cn_d1_head_noun_with_ordinal("说明例如图") == ""
        # Real elements ending in 圖 (示意圖) are also filtered — refnums
        # bound to "示意圖N" denote figure number, not element
        assert _cn_d1_head_noun_with_ordinal("示意圖") == ""

    def test_cn_ordinal_instance_collision(self):
        """CJK instance collision: 第一手柄主體 / 第二手柄主體 sharing
        numeral 11 = drafter assigned same refnum to two instances."""
        from patentlint.analysis.cn_specification import (
            _cn_extract_numeral_name_pairs,
            _cn_detect_d1_conflicts,
        )
        text = (
            "第一手柄主體11被連接。第一手柄主體11是金屬。"
            "第一手柄主體11可移動。第二手柄主體11也被連接。"
            "第二手柄主體11是塑膠。第二手柄主體11可旋轉。"
        )
        pairs = _cn_extract_numeral_name_pairs(text)
        conflicts = _cn_detect_d1_conflicts(pairs)
        # Should detect #11 instance collision
        c11 = [c for c in conflicts if c["numeral"] == "11"]
        assert c11
        assert c11[0]["case"] == "instance"

    def test_r67_interior_verb_split_issue_29_originals(self):
        """R67 (issue #29) — the four literal over-captures from the
        user-reported fixture must each truncate to the bound noun.

        Drafter writes `當使用者踩踏踏板E10` (4×) + `端連接一踏板E10`
        (1×) + `共同形成一封閉空間SP2` + `應設置於封閉空間SP2`. The
        12-CJK-char greedy noun-group regex captures the whole clause,
        producing fake D1 conflicts. Post-fix: every clause reduces
        to the bound noun (`踏板` / `封閉空間`); no conflict surfaces.
        """
        from patentlint.analysis.cn_specification import (
            _cn_d1_head_noun_with_ordinal,
        )
        assert _cn_d1_head_noun_with_ordinal("當使用者踩踏踏板") == "踏板"
        assert _cn_d1_head_noun_with_ordinal("端連接一踏板") == "踏板"
        assert _cn_d1_head_noun_with_ordinal("共同形成一封閉空間") == "封閉空間"
        assert _cn_d1_head_noun_with_ordinal("應設置於封閉空間") == "封閉空間"

    def test_r67_interior_verb_split_pattern_coverage(self):
        """R67 — same bug class with mutated context. Per skill
        section 8 future-proofing: connection / spatial / form /
        reference / containment verbs all matching the
        `<adverb><verb><quantifier-or-prep><noun>` shape must split.
        """
        from patentlint.analysis.cn_specification import (
            _cn_d1_head_noun_with_ordinal,
        )
        # Connection verbs
        assert _cn_d1_head_noun_with_ordinal("抵接該基座的彈簧片") == "彈簧片"
        assert _cn_d1_head_noun_with_ordinal("配合一基座的卡扣") == "卡扣"
        # Spatial verbs
        assert _cn_d1_head_noun_with_ordinal("位於頂端的散熱片") == "散熱片"
        assert _cn_d1_head_noun_with_ordinal("安裝在底座上的風扇") == "風扇"
        assert _cn_d1_head_noun_with_ordinal("容納於外殼內的電路板") == "電路板"
        # Form / composition
        assert _cn_d1_head_noun_with_ordinal("構成主結構的支柱") == "支柱"
        assert _cn_d1_head_noun_with_ordinal("嵌入主體的銷桿") == "銷桿"
        # Reference / correspondence
        assert _cn_d1_head_noun_with_ordinal("對應於前述基座的螺孔") == "螺孔"

    def test_r67_interior_verb_simplified_chinese_parity(self):
        """R67 — Simplified-Chinese mirror of issue #29 originals.
        CN drafters using Simplified character set get the same fix
        through the same shared helpers (cross-jurisdiction parity).
        """
        from patentlint.analysis.cn_specification import (
            _cn_d1_head_noun_with_ordinal,
        )
        assert _cn_d1_head_noun_with_ordinal("当用户踩踏踏板") == "踏板"
        assert _cn_d1_head_noun_with_ordinal("端连接一踏板") == "踏板"
        assert _cn_d1_head_noun_with_ordinal("共同形成一封闭空间") == "封闭空间"
        assert _cn_d1_head_noun_with_ordinal("应设置于封闭空间") == "封闭空间"
        # Simplified anti-corpus — verb root inside compound noun preserved
        # (`第一连接器` ends in `器`; full chain through R67 split keeps it).
        # `形成部` standalone (3 chars) is collapsed by pre-existing
        # `_cn_strip_iterative` behavior unrelated to R67; the longer
        # `组织图像形成部` form is the realistic case and is preserved.
        assert _cn_d1_head_noun_with_ordinal("第一连接器") == "第一连接器"
        assert _cn_d1_head_noun_with_ordinal("组织图像形成部") == "组织图像形成部"

    def test_r67_interior_verb_preserves_compound_nouns(self):
        """R67 — verb-root morphemes inside compound nouns must NOT
        trigger split. Anti-corpus guard for the standard patent
        element-morpheme suffixes (器/件/體/座/面/部/腔/...).
        """
        from patentlint.analysis.cn_specification import (
            _cn_d1_head_noun_with_ordinal,
            _cn_split_on_interior_verb,
        )
        # The split helper alone — these are ≥4 chars so the helper runs.
        # Each contains a verb compound followed by a noun-suffix char.
        for compound in [
            "第一連接器",      # 連接 + 器
            "組織圖像形成部",  # 形成 + 部
            "前述抵接面",      # 抵接 + 面
            "上方接觸點",      # 接觸 + 點
            "下方接觸面",      # 接觸 + 面
            "中央安裝座",      # 安裝 + 座
            "底部容納腔",      # 容納 + 腔
            "頂部容納部",      # 容納 + 部
            "後方樞接件",      # 樞接 + 件
            "前述結合器",      # 結合 + 器
            "侧壁配合件",      # 配合 + 件
        ]:
            assert _cn_split_on_interior_verb(compound) == compound, (
                f"split helper wrongly truncated {compound!r}"
            )
        # End-to-end pipeline preservation:
        assert _cn_d1_head_noun_with_ordinal("第一連接器") == "第一連接器"
        assert _cn_d1_head_noun_with_ordinal("組織圖像形成部") == "組織圖像形成部"
