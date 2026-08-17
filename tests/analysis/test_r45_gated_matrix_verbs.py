# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""US R45 - gated matrix verbs `acquires` and `remains`.

Reports kwisschen/patentlint-reports#549, #550.
"""
from __future__ import annotations


def _us(claims: list[str]) -> list[dict]:
    from patentlint.analysis.claims import check_antecedent_basis as us_check
    from patentlint.parser.claims import parse_claims
    return us_check(parse_claims("\n".join(claims)))


def test_us_acquires_and_remains_in_are_stopped() -> None:
    """Reports #549 / #550 - the capture ran into the matrix verb."""
    findings = _us([
        "1. A method comprising: acquiring, by an image capturing device, a "
        "plurality of images; and providing a global motion compensation module.",
        "2. The method according to claim 1, wherein, before the image capturing "
        "device acquires the plurality of images, the global motion compensation "
        "module remains in an activated state.",
    ])
    dirty = [f["term"] for f in findings
             if f["term"].endswith(("acquires", "remains"))]
    assert not dirty, dirty


def test_us_remains_before_an_adjective_is_not_stopped() -> None:
    """The R28 measured FN: `<nodes> remains available` must keep firing, so the
    gate is a locative preposition, never a bare stop."""
    findings = _us([
        "1. A system comprising second computing nodes, wherein the second "
        "computing nodes remains available to the first node.",
    ])
    assert [f for f in findings if f["term"].endswith("remains available")]
