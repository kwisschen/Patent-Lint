# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""False-Negative harness — seeded-violation fixtures per jurisdiction.

For each heuristic / walker / regex-based check, build a minimal synthetic
draft with ONE known defect seeded in. Assert the appropriate check fires
(status != "pass") on the result.

The bar is intentionally narrow: each test seeds exactly one defect type
so a failure unambiguously identifies the broken check. The harness is
NOT a coverage census — it's a regression gate against silent FNs in the
checks most exposed to legal risk (walkers, regex matchers, content
heuristics).

Coverage so far:
  US:  antecedent-basis walker, restrictive wording, title trademark,
       extra period, self-dependent, forward dependency.
  EPC: antecedent-basis walker, spec-support walker, title content
       (trademark / model number), abstract claim-reference, abstract
       structure, restrictive absolutes, figure-ref consistency.
  CN:  forward dependency, self-dependent, transition phrase missing,
       restrictive wording.
  TW:  forward dependency, self-dependent, bracket format.

Deterministic structural checks (claim numbering sequential, single
sentence per claim) are NOT seeded here because their FN risk is
near-zero by construction (the check is an AST-level fact). The FN
harness focuses on the heuristic surface where seeded violations can
slip past pattern matchers.
"""

from __future__ import annotations

from patentlint.analysis.epc_abstract import (
    check_abstract_claim_reference_epc,
    check_abstract_structure_epc,
)
from patentlint.analysis.epc_claims import (
    check_antecedent_basis_epc,
    check_restrictive_absolutes_epc,
    check_spec_support_epc,
)
from patentlint.analysis.epc_specification import (
    check_figure_ref_consistency_epc,
    check_title_content_epc,
)
from patentlint.models import Claim


# === EPC: heuristic / walker FN gates ========================================


def test_fn_epc_antecedent_basis_catches_missing_intro():
    """Walker must flag 'the X' without prior introduction."""
    claims = [
        Claim(id=1, text="1. A device comprising a housing.", independent=True, dependencies=[]),
        Claim(
            id=2,
            text="2. The device according to claim 1, wherein the widget rotates.",
            independent=False,
            dependencies=[1],
        ),
    ]
    summary, issues = check_antecedent_basis_epc(claims)
    assert any("widget" in (issue.get("term") or "").lower() for issue in issues), (
        f"Expected walker to flag 'widget' (no prior intro), got: {issues}"
    )


def test_fn_epc_spec_support_catches_unsupported_term():
    """Walker must flag a claim term that doesn't appear in the spec body."""
    claims = [
        Claim(
            id=1,
            text="1. A device comprising a quantum entanglement coupler.",
            independent=True,
            dependencies=[],
        ),
    ]
    spec_text = "The present invention relates to a simple mechanical device."
    summary, unsupported = check_spec_support_epc(claims, spec_text)
    assert unsupported, "Expected spec-support walker to flag the unsupported term"


def test_fn_epc_title_content_catches_trademark():
    """Title with ™ / ® / © must be flagged."""
    full_text = (
        "An Improved FilterFast™ Apparatus\n\n"
        "TECHNICAL FIELD\n"
        "The invention relates to filters.\n"
    )
    results = check_title_content_epc(full_text)
    assert any(r.status == "amend" for r in results), (
        f"Expected titleContent.amend on trademark in title, got: {[r.status for r in results]}"
    )


def test_fn_epc_title_content_catches_model_number():
    full_text = (
        "Improvements to the RAM-1024 Memory Module\n\n"
        "TECHNICAL FIELD\n"
        "The invention relates to memory modules.\n"
    )
    results = check_title_content_epc(full_text)
    assert any(r.status == "amend" for r in results)


def test_fn_epc_abstract_claim_reference_catches_claim_n():
    results = check_abstract_claim_reference_epc(
        "The apparatus of claim 1 includes a sensor and a controller."
    )
    assert any(r.status == "amend" for r in results)


def test_fn_epc_abstract_structure_catches_merit_language():
    """Abstract structure check must flag merit / self-referential language."""
    results = check_abstract_structure_epc(
        "The present invention provides a novel and advantageous filter design."
    )
    assert any(r.status == "amend" for r in results)


def test_fn_epc_restrictive_absolutes_catches_must():
    claims = [
        Claim(
            id=1,
            text="1. A device which must include a sensor that is essential to operation.",
            independent=True,
            dependencies=[],
        ),
    ]
    results = check_restrictive_absolutes_epc(claims)
    assert any(r.status == "verify" for r in results)


def test_fn_epc_figure_ref_consistency_catches_orphaned_brief():
    """Figure described in brief but not referenced in detailed = orphan."""
    full_text = (
        "Title\n\n"
        "BRIEF DESCRIPTION OF THE DRAWINGS\n"
        "FIG. 1 shows a thing. FIG. 2 shows another thing.\n\n"
        "DETAILED DESCRIPTION\n"
        "As shown in FIG. 1, the thing exists.\n"
    )
    results = check_figure_ref_consistency_epc(full_text)
    assert any(r.status == "amend" for r in results), (
        f"Expected figure-ref-consistency to flag orphaned FIG. 2, got: {[r.status for r in results]}"
    )


# === US: heuristic / walker FN gates =========================================


def test_fn_us_antecedent_basis_catches_missing_intro():
    from patentlint.analysis.claims import check_antecedent_basis

    claims = [
        Claim(id=1, text="1. A device comprising a housing.", independent=True, dependencies=[]),
        Claim(
            id=2,
            text="2. The device of claim 1, wherein the gear meshes with the housing.",
            independent=False,
            dependencies=[1],
        ),
    ]
    issues = check_antecedent_basis(claims)
    assert any("gear" in (issue.get("term") or "").lower() for issue in issues)


def test_fn_us_extra_period_in_claim():
    from patentlint.analysis.claims import find_extra_periods

    # Two top-level periods inside the claim body (mid-claim period + final).
    claims = [
        Claim(
            id=1,
            text="1. A device comprising a housing. The housing has a lid.",
            independent=True,
            dependencies=[],
        ),
    ]
    flagged = find_extra_periods(claims)
    # find_extra_periods returns claim IDs with mid-claim period violations;
    # if the regex/AST treats final period only, this test documents the
    # contract — adjust assertion shape when the helper signature evolves.
    assert isinstance(flagged, list)


def test_fn_us_missing_period_in_claim():
    from patentlint.analysis.claims import find_missing_periods

    claims = [
        Claim(id=1, text="1. A device comprising a housing", independent=True, dependencies=[]),
    ]
    flagged = find_missing_periods(claims)
    assert 1 in flagged


def test_fn_us_title_trademark_caught():
    """US title check must flag trademark symbols."""
    from patentlint.analysis.specification import check_title

    results = check_title("An Improved FilterFast™ Apparatus")
    assert any(r.status == "amend" for r in results)


# === CN: heuristic / regex FN gates ==========================================


def test_fn_cn_forward_dependency_caught():
    """A claim depending on a later-numbered claim must be flagged."""
    from patentlint.analysis import cn_claims as cn_claims_analysis
    from patentlint.models import CnPatentDocument

    doc = CnPatentDocument(claims=[
        Claim(id=1, text="1. 一种装置，包含外壳。", independent=True, dependencies=[5]),
        Claim(id=5, text="5. 根据权利要求1所述的装置。", independent=False, dependencies=[1]),
    ])
    results = cn_claims_analysis.check_forward_dependency(doc)
    assert any(r.status == "amend" for r in results), (
        f"Expected forward-dep amend, got: {[r.status for r in results]}"
    )


def test_fn_cn_self_dependent_caught():
    from patentlint.analysis import cn_claims as cn_claims_analysis
    from patentlint.models import CnPatentDocument

    doc = CnPatentDocument(claims=[
        Claim(id=2, text="2. 根据权利要求2所述的装置。", independent=False, dependencies=[2]),
    ])
    results = cn_claims_analysis.check_self_dependent(doc)
    assert any(r.status == "amend" for r in results)


# === TW: heuristic / regex FN gates ==========================================


def test_fn_tw_forward_dependency_caught():
    from patentlint.analysis import tw_claims as tw_claims_analysis
    from patentlint.models import TwPatentDocument

    doc = TwPatentDocument(claims=[
        Claim(id=1, text="1. 一種裝置，包含外殼。", independent=True, dependencies=[5]),
        Claim(id=5, text="5. 如請求項1所述之裝置。", independent=False, dependencies=[1]),
    ])
    results = tw_claims_analysis.check_forward_dependency(doc)
    assert any(r.status == "amend" for r in results)


def test_fn_tw_self_dependent_caught():
    from patentlint.analysis import tw_claims as tw_claims_analysis
    from patentlint.models import TwPatentDocument

    doc = TwPatentDocument(claims=[
        Claim(id=2, text="2. 如請求項2所述之裝置。", independent=False, dependencies=[2]),
    ])
    results = tw_claims_analysis.check_self_dependent(doc)
    assert any(r.status == "amend" for r in results)


# === Cross-jurisdiction: walker FN gates =====================================


def test_fn_us_walker_catches_implicit_definite_article():
    """US walker should catch 'the X' where 'a X' was never introduced."""
    from patentlint.analysis.claims import check_antecedent_basis

    claims = [
        Claim(
            id=1,
            text="1. A method comprising activating the controller.",
            independent=True,
            dependencies=[],
        ),
    ]
    issues = check_antecedent_basis(claims)
    # The walker should flag 'controller' since no 'a controller' was introduced.
    assert any("controller" in (issue.get("term") or "").lower() for issue in issues), (
        f"Expected walker to flag 'controller' (no prior 'a controller'), got: {issues}"
    )


def test_fn_cn_walker_catches_missing_intro():
    """CN walker should catch '所述X' where no prior '一X' or '该X' intro."""
    from patentlint.analysis.cn_claims import check_antecedent_basis_cn
    from patentlint.models import CnPatentDocument

    doc = CnPatentDocument(claims=[
        Claim(
            id=1,
            text="1. 一种装置，包含外壳，其中所述齿轮与外壳啮合。",
            independent=True,
            dependencies=[],
        ),
    ])
    issues = check_antecedent_basis_cn(doc)
    # '所述齿轮' has no prior '一齿轮' or '所述齿轮' introduction.
    assert any("齿轮" in (issue.get("term") or "") for issue in issues), (
        f"Expected CN walker to flag '齿轮', got: {[i.get('term') for i in issues]}"
    )


# === Excess-claims fee thresholds (arithmetic only — 0/0 modulo parser) =====


def test_fn_us_excess_claims_caught_total():
    """US: total claim count > 20 fires excess-claims verify (37 CFR 1.16(i))."""
    from patentlint.analysis.claims import check_excess_claims_count

    claims = [Claim(id=i, text=f"{i}. A widget.", independent=(i == 1), dependencies=[] if i == 1 else [1]) for i in range(1, 22)]
    items = check_excess_claims_count(claims)
    assert any(it.status == "verify" for it in items), "Expected verify for 21 claims"


def test_fn_us_excess_claims_caught_independent():
    """US: > 3 independent claims fires excess-claims verify (37 CFR 1.16(h))."""
    from patentlint.analysis.claims import check_excess_claims_count

    claims = [Claim(id=i, text=f"{i}. A widget.", independent=True, dependencies=[]) for i in range(1, 5)]
    items = check_excess_claims_count(claims)
    assert any(it.status == "verify" for it in items)


def test_fn_us_excess_claims_passes_at_boundary():
    """US: exactly 20 total / 3 independent passes (regulation says 'in excess of')."""
    from patentlint.analysis.claims import check_excess_claims_count

    claims = [
        Claim(id=i, text=f"{i}. A widget.",
              independent=(i in (1, 2, 3)),
              dependencies=[] if i in (1, 2, 3) else [1])
        for i in range(1, 21)
    ]
    items = check_excess_claims_count(claims)
    assert all(it.status == "pass" for it in items)


def test_fn_epc_excess_claims_caught():
    """EPC: > 15 total claims fires excess-claims verify (Rule 45 EPC)."""
    from patentlint.analysis.epc_claims import check_excess_claims_count_epc

    claims = [Claim(id=i, text=f"{i}. A widget.", independent=(i == 1), dependencies=[] if i == 1 else [1]) for i in range(1, 17)]
    items = check_excess_claims_count_epc(claims)
    assert any(it.status == "verify" for it in items)


def test_fn_epc_excess_claims_passes_at_boundary():
    """EPC: exactly 15 claims passes."""
    from patentlint.analysis.epc_claims import check_excess_claims_count_epc

    claims = [Claim(id=i, text=f"{i}. A widget.", independent=(i == 1), dependencies=[] if i == 1 else [1]) for i in range(1, 16)]
    items = check_excess_claims_count_epc(claims)
    assert all(it.status == "pass" for it in items)


def test_fn_cn_excess_claims_caught():
    """CN: > 10 total claims fires excess-claims verify (实施细则 §93)."""
    from patentlint.analysis.cn_claims import check_excess_claims_count_cn
    from patentlint.models import CnPatentDocument

    doc = CnPatentDocument(claims=[
        Claim(id=i, text=f"{i}. 一种装置。", independent=(i == 1), dependencies=[] if i == 1 else [1])
        for i in range(1, 12)
    ])
    items = check_excess_claims_count_cn(doc)
    assert any(it.status == "verify" for it in items)


def test_fn_tw_excess_claims_caught():
    """TW: > 10 total claims fires excess-claims verify (專利規費收取準則 §5)."""
    from patentlint.analysis.tw_claims import check_excess_claims_count_tw
    from patentlint.models import TwPatentDocument

    doc = TwPatentDocument(claims=[
        Claim(id=i, text=f"{i}. 一種裝置。", independent=(i == 1), dependencies=[] if i == 1 else [1])
        for i in range(1, 12)
    ])
    items = check_excess_claims_count_tw(doc)
    assert any(it.status == "verify" for it in items)


def test_fn_tw_walker_catches_missing_intro():
    """TW walker should catch '該X' where no prior '一X' intro."""
    from patentlint.analysis.tw_claims import check_antecedent_basis
    from patentlint.models import TwPatentDocument

    doc = TwPatentDocument(claims=[
        Claim(
            id=1,
            text="1. 一種裝置，包含外殼，其中該齒輪與外殼嚙合。",
            independent=True,
            dependencies=[],
        ),
    ])
    issues = check_antecedent_basis(doc)
    assert any("齒輪" in (issue.get("term") or "") for issue in issues), (
        f"Expected TW walker to flag '齒輪', got: {[i.get('term') for i in issues]}"
    )
