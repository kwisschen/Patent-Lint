# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""US R46 - the connector-less dependency preamble.

Reports kwisschen/patentlint-reports#603-#608.

A drafter wrote ``The command message exchanging method claim 10, further
comprising ...``, dropping ``according to``. ``_DEP_PREAMBLE`` required a
connector, so the preamble was never excluded from the body-reference scan
and the walker emitted ``the command message exchanging method claim 10`` -
a string that appears nowhere in the draft. Six reports, one root cause.
"""
from __future__ import annotations

import pytest

from patentlint.analysis.claims import _DEP_PREAMBLE, check_antecedent_basis
from patentlint.parser.claims import parse_claims


def _findings(*claims: str) -> list[dict]:
    return check_antecedent_basis(parse_claims("\n".join(claims)))


# ------------------------------------------------- the connector is optional

@pytest.mark.parametrize("preamble,head,parent", [
    # The reported shape - no connector at all.
    ("The command message exchanging method claim 10, further comprising:",
     "command message exchanging method", "10"),
    # Every pre-existing connector must still be CONSUMED, not swallowed into
    # the head group. This is what a bare `?` on the alternation could break.
    ("The apparatus of claim 1, wherein", "apparatus", "1"),
    ("The method according to claim 3, wherein", "method", "3"),
    ("The system as claimed in claim 7, wherein", "system", "7"),
    ("The device as recited in claim 2, wherein", "device", "2"),
    ("The assembly as set forth in claim 5, wherein", "assembly", "5"),
    ("The module as in claim 4, wherein", "module", "4"),
])
def test_dep_preamble_head_and_parent(preamble, head, parent):
    m = _DEP_PREAMBLE.match(preamble)
    assert m is not None, f"preamble did not match: {preamble}"
    assert m.group(2) == head
    assert m.group(3) == parent


def test_connectorless_preamble_is_not_scanned_as_body_text():
    """#603-#607: the preamble must stop producing a bogus reference."""
    findings = _findings(
        "10. A command message exchanging method, comprising: configuring a "
        "host control circuit to output a plurality of command messages.",
        "11. The command message exchanging method claim 10, further "
        "comprising processes of: configuring each of a plurality of "
        "storage devices.",
    )
    assert findings == [], f"expected no findings, got {findings}"


def test_the_dependency_itself_was_never_broken():
    """NOT the R40 diagnostic - _DEP_REF already matched bare `claim 10`.

    Only the preamble EXCLUSION failed. Pinning this keeps a later round from
    misreading the class as a broken dependency link.
    """
    claims = parse_claims(
        "10. A method, comprising: providing a widget.\n"
        "11. The method claim 10, further comprising: adjusting the widget.\n"
    )
    dep = [c for c in claims if (c.id if hasattr(c, "id") else c.number) == 11][0]
    deps = getattr(dep, "dependencies", None)
    assert deps == [10], f"expected dependency on claim 10, got {deps}"
    assert getattr(dep, "independent", None) is False


# ------------------------------------------------------------------ FN guard

def test_entity_mismatch_is_still_flagged():
    """The entity-consistency guard is UNCHANGED and must still fire.

    A dependent preamble naming a DIFFERENT entity than its parent is a real
    §112(b) drafting error (MPEP §2173.05(e)), not a preamble to skip. If
    widening the connector had also widened the exclusion, this would go
    silent - which is the FN this test exists to catch.
    """
    findings = _findings(
        "1. An image capturing system, comprising: a lens module.",
        "9. The energy harvesting system claim 1, wherein the energy "
        "harvesting system includes a coil.",
    )
    terms = {f.get("term") for f in findings}
    assert "energy harvesting system" in terms, (
        f"entity mismatch went silent; got {terms}")
