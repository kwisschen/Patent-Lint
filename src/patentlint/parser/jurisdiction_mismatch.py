# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Jurisdiction-mismatch detection (Issue #9 / ADR-082 revisited).

When a user selects jurisdiction A but uploads a draft from jurisdiction B,
the existing :class:`patentlint.parser.detection.DetectionReason` machinery
short-circuits to ``content_missing`` because B's structural markers are
absent under A's classifier. That's correct, but the resulting NonPatent
banner forces the drafter to reverse-engineer the mismatch themselves.

This module adds a *suggestion*: a cheap pre-pipeline pass that looks at
the document's script ratio plus jurisdiction-distinct surface markers,
and returns a Jurisdiction code if the upload looks like a different
supported jurisdiction than the one the user selected. The frontend
turns this into a soft-warning banner with a "Switch to [X]" button that
re-runs analysis under the suggested jurisdiction without re-uploading.

Heuristic — kept deliberately simple:

* CJK ratio over the first ~10k chars / ~50 paragraphs of body text.
* Marker counts: 【】 + 請求項 + 符號說明 (TIPO) vs 权利要求 + 技术领域 +
  附图说明 (CNIPA). Marker counts disambiguate TW vs CN; pure traditional
  vs simplified character ratios are unreliable on translation drafts.

The detector returns ``None`` whenever the signal is ambiguous; the
NonPatent banner remains the safety net for those cases.
"""

from __future__ import annotations

import re

from patentlint.models import Jurisdiction

# How much text we look at. Sample windows are chosen to keep this cheap
# on long docs while still capturing enough section headers to count
# markers reliably.
_SAMPLE_CHAR_LIMIT = 10_000
_SAMPLE_PARA_LIMIT = 50

# Han ideograph block (CJK Unified + Extension A). CJK punctuation +
# whitespace are treated as neutral so trace mixed content (a US patent
# transliterating one CJK glyph) doesn't trip the CJK gate.
_CJK_RE = re.compile(r"[一-鿿㐀-䶿]")

# CJK ratio above this strongly implies the document is NOT a US draft.
_CJK_HIGH = 0.30
# CJK ratio below this strongly implies the document IS a US draft (or at
# least not a CN/TW draft as filed).
_CJK_LOW = 0.10

# TIPO surface markers that are unique to TW drafts. 【】 bracket headers
# are the load-bearing TIPO convention; 請求項 + 符號說明 are TW-only check
# anchors. We deliberately avoid traditional-only character lists like
# 發/權/應/書 — translation drafts mix scripts and would inflate noise.
_TIPO_MARKERS: tuple[str, ...] = (
    "【中文發明名稱】",
    "【中文新型名稱】",
    "【發明摘要】",
    "【新型摘要】",
    "【申請專利範圍】",
    "【發明申請專利範圍】",
    "【新型申請專利範圍】",
    "【發明說明】",
    "【技術領域】",
    "【先前技術】",
    "【發明內容】",
    "【實施方式】",
    "【圖式簡單說明】",
    "【符號說明】",
    "【摘要】",
    "請求項",
    "符號說明",
)

# CNIPA surface markers — 五书 section names + claims-book header. Pure
# simplified, no brackets. Don't add 发/权/应 — same reasoning as the TW
# side.
_CNIPA_MARKERS: tuple[str, ...] = (
    "权利要求书",
    "权利要求",
    "技术领域",
    "背景技术",
    "发明内容",
    "具体实施方式",
    "附图说明",
    "实用新型内容",
)


def _sample_text(text: str) -> str:
    """Return at most the first ~50 paragraphs / ~10k chars of ``text``.

    Document parsers hand us joined paragraph bodies that can run into
    the megabytes on big patents. The mismatch heuristic only needs
    enough text to estimate script ratio and catch the first few
    section headers — keep it bounded.
    """

    if not text:
        return ""
    paragraphs = text.split("\n")
    if len(paragraphs) > _SAMPLE_PARA_LIMIT:
        text = "\n".join(paragraphs[:_SAMPLE_PARA_LIMIT])
    return text[:_SAMPLE_CHAR_LIMIT]


def _cjk_ratio(text: str) -> float:
    """Han-ideograph share of non-whitespace characters."""

    if not text:
        return 0.0
    nonspace = sum(1 for c in text if not c.isspace())
    if nonspace == 0:
        return 0.0
    han = len(_CJK_RE.findall(text))
    return han / nonspace


def _count_markers(text: str, markers: tuple[str, ...]) -> int:
    return sum(text.count(m) for m in markers)


def detect_jurisdiction_mismatch(
    text: str,
    selected: Jurisdiction,
) -> str | None:
    """Suggest a different supported jurisdiction if the document looks
    mismatched.

    Returns one of ``"US"``, ``"CN"``, ``"TW"`` or ``None``. ``None``
    means: signal is ambiguous, or the document looks consistent with
    the selected jurisdiction.

    The detector is intentionally conservative — when in doubt it
    returns ``None`` and lets the existing NonPatent banner handle the
    case. A false-positive suggestion is more disruptive than no
    suggestion (the user clicks Switch, sees the same NonPatent banner
    on the other jurisdiction, and now distrusts the tool).
    """

    sample = _sample_text(text)
    if not sample:
        return None

    cjk = _cjk_ratio(sample)
    tipo = _count_markers(sample, _TIPO_MARKERS)
    cnipa = _count_markers(sample, _CNIPA_MARKERS)

    if selected == Jurisdiction.US:
        if cjk <= _CJK_HIGH:
            return None
        # Heavy CJK content with US selected → suggest TW or CN.
        if tipo > cnipa:
            return Jurisdiction.TW.value
        if cnipa > tipo:
            return Jurisdiction.CN.value
        # Marker tie (or both zero — possible on a CJK doc lacking the
        # specific surface markers we look for, e.g., a JP-translated
        # draft that has had its headers normalized). Fall back to CN —
        # it's the larger filing volume of the two, so the suggestion is
        # more often right; if it isn't, the user can still pick TW from
        # the home picker after switching back.
        return Jurisdiction.CN.value

    if selected == Jurisdiction.CN:
        if cjk < _CJK_LOW:
            return Jurisdiction.US.value
        if tipo > cnipa and tipo > 0:
            return Jurisdiction.TW.value
        return None

    if selected == Jurisdiction.TW:
        if cjk < _CJK_LOW:
            return Jurisdiction.US.value
        if cnipa > tipo and cnipa > 0:
            return Jurisdiction.CN.value
        return None

    return None
