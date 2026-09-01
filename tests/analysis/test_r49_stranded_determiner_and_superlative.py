# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""TW R49 stranded-determiner tail + US R47 positional-superlative tail.

Reports kwisschen/patentlint-reports#691 (TW), #683 (US).
"""
from __future__ import annotations

import pytest


def _tw_spec_support(claim_text: str, spec: str):
    from patentlint.analysis.tw_spec_support import check_spec_support_tw
    from patentlint.models import Claim, TwPatentDocument, TwPatentType
    doc = TwPatentDocument(
        patent_type=TwPatentType.INVENTION, title="x", technical_field=[],
        prior_art=[], disclosure=[], drawings_description=[], embodiment=[spec],
        symbol_table=[], claims=[Claim(id=1, text=claim_text, independent=True)],
        abstract_text="",
    )
    return check_spec_support_tw(doc)


def _us(claims: list[str]) -> list[dict]:
    from patentlint.analysis.claims import check_antecedent_basis as us_check
    from patentlint.parser.claims import parse_claims
    return us_check(parse_claims("\n".join(claims)))


# --- TW R49 ---------------------------------------------------------------

def test_tw_stranded_determiner_capture_is_rejected() -> None:
    """Report #691 - `經配置以擷取一輸入影像` emitted the term `以擷取一`."""
    findings = _tw_spec_support(
        "一種影像優化裝置，包括：\n一影像擷取電路，經配置以擷取一輸入影像；\n"
        "一儲存器，儲存多個指令；以及\n一處理器，連接所述影像擷取電路與所述儲存器。",
        "本發明的影像優化裝置包括影像擷取電路、儲存器與處理器。影像擷取電路用以擷取輸入影像。"
        "儲存器儲存多個指令。處理器連接影像擷取電路與儲存器，並存取所述指令。輸入影像為彩色影像。",
    )
    assert [u.phrase for u in findings] == []


@pytest.mark.parametrize("term", ["以擷取一", "執行一", "訊號至一", "提供一", "沿著一"])
def test_tw_fragment_tails_are_rejected(term: str) -> None:
    from patentlint.analysis.tw_claims import _has_stranded_determiner_tail_tw
    assert _has_stranded_determiner_tail_tw(term) is True


@pytest.mark.parametrize("term", [
    # Ordinals - R43 proved a truncated 第一 is accidentally load-bearing.
    "第一", "第二", "第三", "所述第一",
    # Quantifier idioms - held as a separate class, not swept in with fragments.
    "至少一", "唯一", "每一", "另一", "任一", "之一",
    # Numbered step labels - the CN corpus attests this convention 17 times.
    "步驟一", "步驟二",
    # Ordinary element names must be untouched.
    "輸入影像", "第一電極",
])
def test_tw_protected_shapes_are_not_rejected(term: str) -> None:
    from patentlint.analysis.tw_claims import _has_stranded_determiner_tail_tw
    assert _has_stranded_determiner_tail_tw(term) is False


# --- US R47 ---------------------------------------------------------------

def test_us_trailing_superlative_unblocks_the_strip_cascade() -> None:
    """Report #683 [1] - `outermost` blocked `located` and `radially` behind it."""
    from patentlint.analysis.utils import clean_noun_phrase
    assert clean_noun_phrase(
        "edge band region located radially outermost") == "edge band region"


def test_us_683_finding_1_resolves_end_to_end() -> None:
    findings = _us([
        "1. An image optimization device, comprising: an image capturing circuit; "
        "and a processor configured to convert an input image into a dark channel map.",
        "2. The image optimization device according to claim 1, wherein the processor "
        "is configured to: perform a brightness check on an edge band region located "
        "radially outermost in the input image, thereby identifying a peripheral "
        "region to be tested; and identify a central region to be tested that is "
        "surrounded by the edge band region in the input image.",
    ])
    assert "edge band region" not in [f["term"] for f in findings]


def test_us_attributive_superlative_is_preserved() -> None:
    """The gate is POSITIONAL: attributive `-most` is followed by its head noun."""
    from patentlint.analysis.utils import extract_introductions
    intros = sorted(extract_introductions(
        "a topmost conductive coil and a bottommost conductive coil"))
    assert intros == ["bottommost conductive coil", "topmost conductive coil"]


def test_us_cataphoric_list_intro_stays_WITHHELD() -> None:
    """Report #683 [2] is a MEASURED WITHHOLD - pin it so it cannot ship silently.

    Registering `the following <noun>:` as an introduction silences 17 gold-legit
    findings on US20190318433A1, where the drafter writes `the following steps of:`
    and then adds BRAND-NEW steps with a definite article. `the step` must keep
    flagging when the ancestor never recited that step - this is the shape reports
    #684 / #685 / #687 attest as a real defect.
    """
    findings = _us([
        "1. A method, comprising the following steps: converting an input image "
        "into a dark channel map; and identifying a dense-haze center region.",
        "2. The method according to claim 1, comprising the step of generating a "
        "smart contract as the real estate process agreement.",
    ])
    assert "step" in [f["term"] for f in findings]
