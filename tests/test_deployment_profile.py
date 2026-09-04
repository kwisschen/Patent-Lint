"""Deployment-profile suppression of advisory § 112 findings.

The load-bearing assertions here are the two the project's own gate
discipline demands of any filter: that the no-op path is genuinely a no-op,
and that the active path is genuinely able to remove something. A profile
that silently matched nothing would pass a naive "did it crash" test while
being completely inert.
"""

from __future__ import annotations

import json

import pytest

from patentlint import profile as prof
from patentlint.models import UnsupportedTerm
from patentlint.profile import (
    ENV_VAR,
    Profile,
    ProfileError,
    active_profile,
    load_profile_file,
    parse_profile,
    suppress_antecedent,
    suppress_findings,
    suppress_spec_support,
)


@pytest.fixture(autouse=True)
def _clear_profile_env(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    prof._CACHE.clear()


def _write(tmp_path, payload):
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return p


def _ab(term, reference_form=None, claim_id=1):
    return {"claim_id": claim_id, "term": term, "reference_form": reference_form}


# --- the no-op path -------------------------------------------------------

def test_no_env_var_returns_the_identical_list_object():
    items = [_ab("controller")]
    assert suppress_antecedent(items, "US") is items


def test_active_profile_is_none_without_env_var():
    assert active_profile() is None


def test_empty_profile_is_a_no_op(tmp_path, monkeypatch):
    path = _write(tmp_path, {"version": 1, "suppress_terms": {}})
    monkeypatch.setenv(ENV_VAR, str(path))
    items = [_ab("controller")]
    assert suppress_antecedent(items, "US") is items


# --- the active path MUST be able to remove something ---------------------

def test_profile_actually_suppresses_a_matching_term(tmp_path, monkeypatch):
    """Non-vacuity: the filter is shown to fire, not merely to run."""
    path = _write(tmp_path, {"version": 1, "suppress_terms": {"US": ["controller"]}})
    monkeypatch.setenv(ENV_VAR, str(path))
    items = [_ab("controller"), _ab("housing")]
    out = suppress_antecedent(items, "US")
    assert [d["term"] for d in out] == ["housing"]


def test_suppression_is_scoped_to_its_jurisdiction(tmp_path, monkeypatch):
    path = _write(tmp_path, {"version": 1, "suppress_terms": {"CN": ["控制模块"]}})
    monkeypatch.setenv(ENV_VAR, str(path))
    items = [_ab("控制模块")]
    assert suppress_antecedent(items, "CN") == []
    assert suppress_antecedent(items, "TW") is items


def test_star_applies_to_every_jurisdiction(tmp_path, monkeypatch):
    path = _write(tmp_path, {"version": 1, "suppress_terms": {"*": ["widget"]}})
    monkeypatch.setenv(ENV_VAR, str(path))
    for juris in ("US", "CN", "TW"):
        assert suppress_antecedent([_ab("widget")], juris) == []


def test_flat_list_is_sugar_for_star(tmp_path, monkeypatch):
    path = _write(tmp_path, {"version": 1, "suppress_terms": ["widget"]})
    monkeypatch.setenv(ENV_VAR, str(path))
    assert suppress_antecedent([_ab("widget")], "US") == []


def test_matches_the_reference_form_not_only_the_cleaned_term(tmp_path, monkeypatch):
    """The UI renders ``reference_form || term``, so that is the string a
    reader copies out of a report and puts in a profile."""
    path = _write(tmp_path, {"version": 1, "suppress_terms": {"US": ["the controller"]}})
    monkeypatch.setenv(ENV_VAR, str(path))
    items = [_ab("controller", reference_form="the controller")]
    assert suppress_antecedent(items, "US") == []


def test_spec_support_findings_are_matched_on_phrase(tmp_path, monkeypatch):
    path = _write(tmp_path, {"version": 1, "suppress_terms": {"TW": ["感測模組"]}})
    monkeypatch.setenv(ENV_VAR, str(path))
    items = [
        UnsupportedTerm(claim_number=1, phrase="感測模組"),
        UnsupportedTerm(claim_number=1, phrase="電源模組"),
    ]
    out = suppress_spec_support(items, "TW")
    assert [t.phrase for t in out] == ["電源模組"]


# --- normalisation --------------------------------------------------------

@pytest.mark.parametrize(
    ("configured", "found"),
    [
        ("Controller", "controller"),      # case
        ("controller", "  controller  "),  # edge whitespace
        ("ＣＰＵ", "CPU"),                  # fullwidth Latin -> halfwidth
    ],
)
def test_matching_normalises_case_width_and_edge_whitespace(
    tmp_path, monkeypatch, configured, found,
):
    path = _write(tmp_path, {"version": 1, "suppress_terms": {"US": [configured]}})
    monkeypatch.setenv(ENV_VAR, str(path))
    assert suppress_antecedent([_ab(found)], "US") == []


def test_matching_is_exact_not_substring(tmp_path, monkeypatch):
    """A substring rule would silently swallow unrelated findings."""
    path = _write(tmp_path, {"version": 1, "suppress_terms": {"US": ["controller"]}})
    monkeypatch.setenv(ENV_VAR, str(path))
    items = [_ab("controller board")]
    assert [d["term"] for d in suppress_antecedent(items, "US")] == ["controller board"]


# --- a malformed profile must fail LOUDLY --------------------------------

def test_unknown_top_level_key_is_rejected():
    """A silently-dropped typo is the vacuous-gate failure class."""
    with pytest.raises(ProfileError, match="unknown profile key"):
        parse_profile({"version": 1, "supress_terms": ["typo"]})


def test_unsupported_version_is_rejected():
    with pytest.raises(ProfileError, match="unsupported profile version"):
        parse_profile({"version": 99})


def test_missing_version_is_rejected():
    with pytest.raises(ProfileError, match="unsupported profile version"):
        parse_profile({"suppress_terms": []})


def test_non_object_profile_is_rejected():
    with pytest.raises(ProfileError, match="must be a JSON object"):
        parse_profile([1, 2, 3])


def test_wrong_suppress_terms_type_is_rejected():
    with pytest.raises(ProfileError, match="must be a list or an object"):
        parse_profile({"version": 1, "suppress_terms": "widget"})


def test_non_string_term_is_rejected():
    with pytest.raises(ProfileError, match="must be a list of strings"):
        parse_profile({"version": 1, "suppress_terms": {"US": [1]}})


def test_invalid_json_is_rejected(tmp_path, monkeypatch):
    p = tmp_path / "profile.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ProfileError, match="invalid JSON"):
        load_profile_file(p)


def test_missing_file_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "nope.json"))
    with pytest.raises(ProfileError, match="cannot stat profile"):
        active_profile()


# --- cache invalidation ---------------------------------------------------

def test_edited_profile_is_picked_up_without_restart(tmp_path, monkeypatch):
    path = _write(tmp_path, {"version": 1, "suppress_terms": {"US": ["alpha"]}})
    monkeypatch.setenv(ENV_VAR, str(path))
    assert suppress_antecedent([_ab("alpha")], "US") == []

    import os
    stat = path.stat()
    path.write_text(
        json.dumps({"version": 1, "suppress_terms": {"US": ["beta"]}}), encoding="utf-8",
    )
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

    assert [d["term"] for d in suppress_antecedent([_ab("alpha")], "US")] == ["alpha"]
    assert suppress_antecedent([_ab("beta")], "US") == []


# --- explicit-profile form (no environment involved) ----------------------

def test_explicit_profile_argument_bypasses_the_environment():
    p = Profile(suppress_terms={"US": frozenset({"widget"})})
    out = suppress_findings(
        [_ab("widget"), _ab("gear")],
        "US",
        candidates=lambda d: (d.get("term"), d.get("reference_form")),
        profile=p,
    )
    assert [d["term"] for d in out] == ["gear"]


# --- end to end through the real pipeline --------------------------------

def test_pipeline_suppression_removes_the_finding_and_leaves_the_grade(
    tmp_path, monkeypatch,
):
    """The wiring sits upstream of both the CheckItem build and the grade.

    Suppressing an ADVISORY finding must remove it from the card, decrement
    the summary tile's count, and leave the rubric grade byte-identical -
    advisory keys carry zero grade impact by construction.
    """
    from patentlint.models import Jurisdiction
    from patentlint.pipeline import analyze_file

    fixture = "tests/fixtures/tw/claim_dependencies.docx"

    before = analyze_file(fixture, Jurisdiction.TW)
    phrases = [t.phrase for t in before.unsupported_terms]
    assert len(phrases) >= 2, "fixture must yield >=2 findings for this test to bite"
    target = phrases[0]
    grade_before = before.rubric_grade.letter

    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps({"version": 1, "suppress_terms": {"TW": [target]}}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_VAR, str(path))
    prof._CACHE.clear()

    after = analyze_file(fixture, Jurisdiction.TW)
    after_phrases = [t.phrase for t in after.unsupported_terms]

    assert target not in after_phrases
    assert len(after_phrases) == len(phrases) - 1
    assert after.rubric_grade.letter == grade_before

    # the summary tile's count must track the filtered list, not the raw one
    report = after.to_report_data()
    tiles = [
        c for c in report.claims_checks
        if c.message_key and "specSupport" in c.message_key
    ]
    if tiles:
        assert tiles[0].details_params["issue_count"] == len(after_phrases)


def test_pipeline_without_a_profile_is_byte_identical(monkeypatch):
    """The unprofiled path is the public web tier. It must not move."""
    from patentlint.models import Jurisdiction
    from patentlint.pipeline import analyze_file

    monkeypatch.delenv(ENV_VAR, raising=False)
    prof._CACHE.clear()
    a = analyze_file("tests/fixtures/tw/claim_dependencies.docx", Jurisdiction.TW)
    b = analyze_file("tests/fixtures/tw/claim_dependencies.docx", Jurisdiction.TW)
    assert a.to_report_data().model_dump_json() == b.to_report_data().model_dump_json()
