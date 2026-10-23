"""US spec-support, wave B: a stem match must be an inflection, and four
phrase shapes that name no element. Synthetic shapes only."""

from patentlint.analysis import claims as us
from patentlint.analysis.claims import check_spec_support
from patentlint.models import Claim

_SPEC = (
    "A routing unit has an input pin and a first output pin. A connection unit "
    "having an input terminal routes the signal. Transistors are chained, and "
    "a controller runs instructions. A circuit is chosen from a graphics unit "
    "or a vector unit, and a driver turns on a third switch."
)


def _phrases(text: str) -> list[str]:
    return [u.phrase for u in check_spec_support([Claim(id=1, text=text, independent=True)], _SPEC)]


def test_a_derived_word_does_not_support_its_stem():
    # `connection` is not a form of `connect`: the term is genuinely unsupported.
    assert "connect terminal" in _phrases(
        "1. A routing unit having an input pin, a first output pin, and a connect terminal.")


def test_an_inflection_still_supports():
    assert "input terminals" not in _phrases(
        "1. A connection unit having input terminals.")


def test_markush_group_head_is_not_a_term():
    assert "group" not in _phrases(
        "1. A device wherein a circuit is selected from the group consisting of a graphics unit and a vector unit.")


def test_positional_partitive_is_not_a_term():
    phrases = _phrases(
        "1. A chain comprising transistors, wherein each is connected to a preceding one of the "
        "transistors, and a last one of the transistors is grounded.")
    assert "last" not in phrases and "preceding one" not in phrases


def test_trailing_only_and_midphrase_further():
    assert us._trim_spec_support_predicate_tail("third switch only") == "third switch"
    assert us._trim_spec_support_predicate_tail("instructions further cause") == "instructions"
    assert us._trim_spec_support_predicate_tail("further layer") == "further layer"
    assert us._trim_spec_support_predicate_tail("memory read only") == "memory read only"
