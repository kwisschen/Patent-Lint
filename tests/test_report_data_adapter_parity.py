# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""ReportData adapter parity canary (Phase 9 #41).

Regression coverage for the CN ``antecedent_basis_issues`` silent-drop class
fixed at ``c16caed``. Each ``_to_{us,cn,tw}_report_data`` adapter is exercised
with a synthetic ``AnalysisResult`` populated across every source field the
adapter is expected to carry forward; the resulting ``ReportData`` must have
every corresponding destination list non-empty.

The per-jurisdiction forwarding map lives at the top of this module as
explicit string constants. Adding a new list field to ``AnalysisResult`` or
``ReportData`` forces a contributor to either extend the relevant jurisdiction
entry below (ship the forwarding) or document that the field is intentionally
not forwarded — either way, this canary surfaces the decision rather than
letting a silent drop reach users.
"""

from __future__ import annotations

import pytest

from patentlint.models import (
    AnalysisResult,
    CheckItem,
    Claim,
    Jurisdiction,
    ReportData,
    UnsupportedTerm,
)


# --- forwarding maps (the canary's contract) ---------------------------------

# Each entry: (source_field_on_AnalysisResult, dest_field_on_ReportData,
# factory_for_nonempty_value). The factories must produce values pydantic
# will accept for that field's type.

def _make_check(key: str) -> CheckItem:
    return CheckItem(status="pass", message=key, message_key=key)


def _make_claim(claim_id: int, text: str = "1. A test claim.") -> Claim:
    return Claim(id=claim_id, text=text, independent=True)


def _make_unsupported(phrase: str) -> UnsupportedTerm:
    return UnsupportedTerm(claim_number=1, phrase=phrase, tiers_checked=["exact"])


# CN: cn_*_checks fed verbatim into *_checks; antecedent_basis_issues forwarded.
CN_FORWARD_MAP = [
    ("cn_specification_checks", "specification_checks",
     lambda: [_make_check("cn.spec.x")]),
    ("cn_claims_checks", "claims_checks",
     lambda: [_make_check("cn.claims.x")]),
    ("cn_abstract_checks", "abstract_checks",
     lambda: [_make_check("cn.abstract.x")]),
    ("cn_drawings_checks", "drawings_checks",
     lambda: [_make_check("cn.drawings.x")]),
    ("antecedent_basis_issues", "antecedent_basis_issues",
     lambda: [{"claim_id": 1, "term": "widget", "reference_form": "the widget",
               "claim_text": "1. A widget.", "suggested_match": None,
               "cross_ref": None}]),
]

# TW: tw_*_checks fed verbatim into *_checks; antecedent_basis_issues forwarded.
TW_FORWARD_MAP = [
    ("tw_specification_checks", "specification_checks",
     lambda: [_make_check("tw.spec.x")]),
    ("tw_claims_checks", "claims_checks",
     lambda: [_make_check("tw.claims.x")]),
    ("tw_abstract_checks", "abstract_checks",
     lambda: [_make_check("tw.abstract.x")]),
    ("tw_drawings_checks", "drawings_checks",
     lambda: [_make_check("tw.drawings.x")]),
    ("antecedent_basis_issues", "antecedent_basis_issues",
     lambda: [{"claim_id": 1, "term": "widget", "reference_form": "the widget",
               "claim_text": "1. A widget.", "suggested_match": None,
               "cross_ref": None}]),
]

# US: adapter synthesizes CheckItems from flat fields. For each flat source
# field the adapter reads, assert the corresponding destination *_checks
# accumulator ends up non-empty. The adapter also forwards
# antecedent_basis_issues + unsupported_terms onto ReportData verbatim.
US_FORWARD_MAP = [
    # Source -> (dest_attribute_on_ReportData, factory)
    # spec_checks accumulator
    ("improper_spec_paragraphs", "specification_checks", lambda: [4, 7]),
    ("missing_ending_paragraphs", "specification_checks", lambda: [12]),
    ("required_sections_checks", "specification_checks",
     lambda: [_make_check("us.req_sections.x")]),
    # claims_checks accumulator
    ("improper_claims", "claims_checks", lambda: [3]),
    ("multiple_dependent_claims", "claims_checks", lambda: [5]),
    ("self_dependent_claims", "claims_checks", lambda: [6]),
    ("means_plus_function_claims", "claims_checks", lambda: [2]),
    ("punctuation_checks", "claims_checks",
     lambda: [_make_check("us.punctuation.x")]),
    ("preamble_checks", "claims_checks",
     lambda: [_make_check("us.preamble.x")]),
    ("transition_checks", "claims_checks",
     lambda: [_make_check("us.transition.x")]),
    ("special_format_checks", "claims_checks",
     lambda: [_make_check("us.special_format.x")]),
    # drawings_checks accumulator
    ("figure_xref_checks", "drawings_checks",
     lambda: [_make_check("us.figure_xref.x")]),
    # Direct passthroughs on ReportData
    ("antecedent_basis_issues", "antecedent_basis_issues",
     lambda: [{"claim_id": 1, "term": "widget", "reference_form": "the widget",
               "claim_text": "1. A widget.", "suggested_match": None,
               "cross_ref": None}]),
    ("unsupported_terms", "unsupported_terms",
     lambda: [_make_unsupported("widget")]),
]

# claim_trees is built by every adapter from self.claims, not from a field
# named claim_trees. Exercised once per jurisdiction below.


# --- helpers -----------------------------------------------------------------

def _base_kwargs(jurisdiction: Jurisdiction) -> dict:
    """Minimal non-adapter-sensitive fields so AnalysisResult constructs."""
    return dict(jurisdiction=jurisdiction)


def _nonempty_list_report_field(report: ReportData, field: str) -> bool:
    value = getattr(report, field)
    return isinstance(value, list) and len(value) > 0


# --- per-jurisdiction canary tests ------------------------------------------

class TestReportDataAdapterParityCN:
    """CN adapter forwards every declared source field onto ReportData."""

    @pytest.mark.parametrize("src,dest,factory", CN_FORWARD_MAP,
                             ids=[m[0] for m in CN_FORWARD_MAP])
    def test_field_forwards(self, src: str, dest: str, factory):
        kwargs = _base_kwargs(Jurisdiction.CN)
        kwargs[src] = factory()
        result = AnalysisResult(**kwargs)
        report = result.to_report_data()
        assert _nonempty_list_report_field(report, dest), (
            f"CN adapter dropped {src} -> {dest}. "
            f"Source had {len(kwargs[src])} entries; destination is empty."
        )

    def test_claim_trees_populated_from_claims(self):
        kwargs = _base_kwargs(Jurisdiction.CN)
        kwargs["claims"] = [_make_claim(1)]
        report = AnalysisResult(**kwargs).to_report_data()
        assert _nonempty_list_report_field(report, "claim_trees")


class TestReportDataAdapterParityTW:
    """TW adapter forwards every declared source field onto ReportData."""

    @pytest.mark.parametrize("src,dest,factory", TW_FORWARD_MAP,
                             ids=[m[0] for m in TW_FORWARD_MAP])
    def test_field_forwards(self, src: str, dest: str, factory):
        kwargs = _base_kwargs(Jurisdiction.TW)
        kwargs[src] = factory()
        result = AnalysisResult(**kwargs)
        report = result.to_report_data()
        assert _nonempty_list_report_field(report, dest), (
            f"TW adapter dropped {src} -> {dest}. "
            f"Source had {len(kwargs[src])} entries; destination is empty."
        )

    def test_claim_trees_populated_from_claims(self):
        kwargs = _base_kwargs(Jurisdiction.TW)
        kwargs["claims"] = [_make_claim(1)]
        report = AnalysisResult(**kwargs).to_report_data()
        assert _nonempty_list_report_field(report, "claim_trees")


class TestReportDataAdapterParityUS:
    """US adapter synthesizes CheckItems from flat fields.

    Each entry in ``US_FORWARD_MAP`` is a source field the adapter reads;
    populating it with non-empty data must produce at least one item on the
    corresponding ``ReportData`` destination. The US adapter is richer than
    CN/TW (it builds CheckItems inline), so the assertion target is the
    accumulator list, not the field name.
    """

    @pytest.mark.parametrize("src,dest,factory", US_FORWARD_MAP,
                             ids=[m[0] for m in US_FORWARD_MAP])
    def test_field_forwards(self, src: str, dest: str, factory):
        kwargs = _base_kwargs(Jurisdiction.US)
        kwargs[src] = factory()
        result = AnalysisResult(**kwargs)
        report = result.to_report_data()
        assert _nonempty_list_report_field(report, dest), (
            f"US adapter dropped {src} -> {dest}. "
            f"Source had {len(kwargs[src])} entries; destination is empty."
        )

    def test_claim_trees_populated_from_claims(self):
        kwargs = _base_kwargs(Jurisdiction.US)
        kwargs["claims"] = [_make_claim(1)]
        report = AnalysisResult(**kwargs).to_report_data()
        assert _nonempty_list_report_field(report, "claim_trees")


# --- meta-canary: forwarding maps stay in sync with the model ----------------

class TestForwardMapsAreExhaustive:
    """When someone adds a new ``list[...]`` field to ``AnalysisResult``, this
    canary either confirms it's already covered by a jurisdiction's map or
    flags it as a deliberate exclusion. The allowlist below is the
    documented set of ``AnalysisResult`` list fields NOT forwarded to
    ReportData (they're consumed by computed properties, used only by the
    CLI summary, or genuinely not part of the report payload).
    """

    KNOWN_NON_FORWARDED_LIST_FIELDS: frozenset[str] = frozenset({
        # Consumed into `claim_trees` by `_build_claim_trees`, not forwarded
        # as a raw list on ReportData.
        "claims",
        # Surfaced via synthesized CheckItems on US adapter (no raw-list
        # destination on ReportData); CN/TW surface these through their
        # per-jurisdiction *_checks lists instead.
        "reference_numerals",
        # Consumed into the US figures_sequential amend CheckItem's
        # details_params by _to_us_report_data; not a raw list on ReportData.
        "figures_missing",
    })

    def test_every_list_field_is_either_forwarded_or_documented(self):
        # Pull list-typed fields off AnalysisResult via pydantic introspection.
        list_fields: set[str] = set()
        for name, field in AnalysisResult.model_fields.items():
            annot = field.annotation
            annot_repr = repr(annot)
            if annot_repr.startswith("list[") or "list[" in annot_repr:
                list_fields.add(name)

        forwarded = (
            {m[0] for m in CN_FORWARD_MAP}
            | {m[0] for m in TW_FORWARD_MAP}
            | {m[0] for m in US_FORWARD_MAP}
        )
        accounted = forwarded | self.KNOWN_NON_FORWARDED_LIST_FIELDS
        orphans = list_fields - accounted

        assert not orphans, (
            "AnalysisResult has list fields not covered by any forwarding "
            "map and not in KNOWN_NON_FORWARDED_LIST_FIELDS: "
            f"{sorted(orphans)}. Either add the field to the jurisdiction's "
            "forwarding map (and ensure the adapter carries it) or add it "
            "to KNOWN_NON_FORWARDED_LIST_FIELDS with a comment explaining "
            "why it's not part of ReportData."
        )
