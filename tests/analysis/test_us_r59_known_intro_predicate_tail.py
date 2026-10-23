# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""US R59 - a reference that ran on into a predicate resolves against the
drafter's own introduction of its head, when the tail is a predicate.

Every claim here is synthetic; the shapes are the reported ones.
"""
import pytest

from patentlint.models import Claim
from patentlint.analysis.claims import check_antecedent_basis


def _terms(*texts):
    claims = [
        Claim(id=i + 1, text=t, independent=(i == 0), dependencies=([] if i == 0 else [1]))
        for i, t in enumerate(texts)
    ]
    return [f["term"] for f in check_antecedent_basis(claims)]


@pytest.mark.parametrize("text", [
    # lone 3rd-person verb before a preposition
    "1. A panel comprising a plurality of gate lines and a driver circuit, wherein "
    "the driver circuit determines that one of the gate lines drops from a first level.",
    "1. A device comprising a timer circuit, wherein after a key is pressed the "
    "timer circuit returns from a sleep mode to a normal mode.",
    # lone 3rd-person verb before its object
    "1. A drive comprising a controller and a firmware module, wherein the firmware "
    "module writes a flag to a register.",
    "1. A method comprising monitoring an executable entity, wherein the executable "
    "entity issues an access request to a container.",
    # adverb tails
    "1. A converter comprising a high-side switch and a low-side switch, wherein a "
    "driver turns on the low-side switch only when the high-side switch is off.",
    "1. A terminal comprising a processor and instructions, wherein the instructions "
    "further cause the processor to store a value.",
    # base-form verb after a coordinated or plural subject
    "1. A system comprising a repeater unit and a peripheral device, wherein the "
    "repeater unit and the peripheral device communicate with each other.",
    "1. A connector comprising a pin and two interference portions, wherein the two "
    "interference portions clamp the pin.",
])
def test_predicate_tail_resolves(text):
    assert _terms(text) == []


@pytest.mark.parametrize("text, expected", [
    # A longer compound naming another element still fires.
    ("1. A device comprising a control circuit, wherein the control circuit board "
     "carries a sensor.", ["control circuit board"]),
    # A base form after a singular subject reads as a compound noun: withheld.
    ("1. A system comprising a user, wherein the user device stores a record.",
     ["user device"]),
    # A head introduced only later in the same claim is not a basis.
    ("1. A method comprising: wherein the gate driver writes the flag; and providing "
     "a gate driver.", None),
])
def test_controls_still_fire(text, expected):
    terms = _terms(text)
    if expected is None:
        assert terms, "a reference before its own introduction must still fire"
    else:
        assert terms == expected
