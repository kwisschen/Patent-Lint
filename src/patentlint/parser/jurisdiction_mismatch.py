# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
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

# EPC-distinctive surface markers in English. Patent drafters at EPC firms
# pin their work to EPC vocabulary even when the application targets a
# member state national route — these terms are not in normal US drafting
# vocabulary, so a US-selected upload that hits any of them is a real
# mismatch signal (not a stylistic noise signal).
#
# Conservative scope on purpose: only terms that are EPC-specific AND
# unlikely to appear in a US draft. "according to claim" is intentionally
# excluded — too generic; US drafters use it too. British-spelling tells
# like "characterised" are picked up via the case-insensitive match
# because EPC two-part-form preambles almost always include them, and
# US drafters spell with -ize.
_EPC_MARKERS: tuple[str, ...] = (
    "european patent",
    "european patent application",
    "european patent office",
    "epc ",
    " epc",
    "article 84",
    "article 56",
    "article 83",
    "article 78",
    "article 123",
    "rule 43",
    "rule 42",
    "rule 47",
    "characterised in that",
    "characterising portion",
    "any preceding claim",
    "any one of claims",
    "epo guidelines",
)

# US-distinctive surface markers in English. Anchor terms that EPC drafters
# (even British-spelling habituated ones) would not produce: USPTO + MPEP +
# 35 U.S.C. § citations are diagnostic of a US-filed draft. Non-transitory
# CRM boilerplate is § 101-specific. "FIG." in caps is the US convention
# (EPC drafts write "Fig." or "fig."), but case-insensitive matching makes
# that brittle — handled via a separate cased check below.
_US_MARKERS: tuple[str, ...] = (
    "uspto",
    "united states patent and trademark office",
    "35 u.s.c.",
    "35 usc",
    " mpep ",
    "mpep §",
    "mpep section",
    "non-transitory computer-readable",
    "non-transitory computer readable",
    "method of claim",  # US heavily prefers "method of claim N" over EPC "method according to claim N"
    "system of claim",
    "device of claim",
    "apparatus of claim",
)

# How big a marker-count delta we require before suggesting an EPC ↔ US
# switch. Set deliberately high: false-positive suggestions on this axis
# would hit every US drafter who happens to cite an EPC counterpart, or
# every EPC drafter who mentions a US priority document. 2 means: clearly
# one-sided, not just trace appearances.
_EN_MARKER_MIN_DELTA = 2

# Cased "FIG." figure-label convention. US drafters write "FIG. 1"; EPC
# drafters write "Fig. 1" (Guidelines F-V § 1.2). When a draft has many
# capitalized FIG. references and few/no lowercase Fig. references, that's
# a strong US tell that the lowercased marker scan misses. Threshold set
# at 5 so a stray figure-caption in an otherwise-EPC draft doesn't trip.
_FIG_CASED_RE = re.compile(r"\bFIG\.")
_FIG_MIXED_RE = re.compile(r"\bFig\.|\bfig\.")
_FIG_CASED_MIN = 5

# Common German function words + EPÜ-specific terms. Frequency-anchored:
# any EPC draft written in German will hit a handful of these in the first
# few paragraphs (article+noun agreement, common verbs, EPC headings).
_DE_MARKERS: tuple[str, ...] = (
    " der ",
    " die ",
    " das ",
    " den ",
    " dem ",
    " des ",
    " ein ",
    " eine ",
    " einen ",
    " einer ",
    " und ",
    " ist ",
    " sind ",
    " nicht ",
    " auch ",
    " auf ",
    " mit ",
    " für ",
    " wird ",
    " werden ",
    " dadurch gekennzeichnet",
    "patentansprüche",
    "beschreibung",
    "erfindung",
    "ausführungsbeispiel",
    "ansprüche",
    "merkmale",
    "gemäß",
)

# Common French function words + EPC-French-specific terms. Same approach
# as DE: load-bearing function words + EPC-template phrases.
_FR_MARKERS: tuple[str, ...] = (
    " le ",
    " la ",
    " les ",
    " un ",
    " une ",
    " des ",
    " du ",
    " de la ",
    " et ",
    " est ",
    " sont ",
    " dans ",
    " avec ",
    " pour ",
    " que ",
    " qui ",
    " caractérisé en ce que",
    "revendications",
    "revendication",
    "description",
    "invention",
    "abrégé",
    "selon la revendication",
    "mode de réalisation",
)

# How many distinct DE / FR markers must fire before flagging an EPC
# draft as non-English. 6 = clearly non-English-flavored text, not just
# trace foreign-language phrasing (e.g., a French priority citation in
# an otherwise-English EPC draft).
_EPC_NONEN_MARKER_MIN = 6


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


def detect_epc_unsupported_language(text: str) -> str | None:
    """Detect whether an EPC-selected draft is written in DE or FR.

    EPC v1 supports English-input drafts only (DE / FR check engines
    deferred). When a user drops a German or French draft into EPC, the
    pipeline still runs but its findings are not meaningful for that
    language. Returns ``"de"`` / ``"fr"`` so the frontend can render an
    advisory banner explaining the English-only scope. Returns ``None``
    when the language is English or the signal is ambiguous (e.g., short
    docs with no function words yet).
    """

    sample = _sample_text(text)
    if not sample:
        return None
    # Function-word matching is case-insensitive but our marker lists are
    # already lower-case; normalize for cheap whole-word containment.
    sample_lower = " " + re.sub(r"\s+", " ", sample.lower()) + " "
    de_hits = sum(1 for m in _DE_MARKERS if m in sample_lower)
    fr_hits = sum(1 for m in _FR_MARKERS if m in sample_lower)
    if de_hits >= _EPC_NONEN_MARKER_MIN and de_hits > fr_hits:
        return "de"
    if fr_hits >= _EPC_NONEN_MARKER_MIN and fr_hits > de_hits:
        return "fr"
    return None


def detect_jurisdiction_mismatch(
    text: str,
    selected: Jurisdiction,
) -> str | None:
    """Suggest a different supported jurisdiction if the document looks
    mismatched.

    Returns one of ``"US"``, ``"CN"``, ``"TW"``, ``"EPC"`` or ``None``.
    ``None`` means: signal is ambiguous, or the document looks consistent
    with the selected jurisdiction.

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
    # English markers are phrases that frequently straddle .docx paragraph
    # boundaries ("method of claim\n   1, wherein..."), so collapse runs of
    # whitespace before counting so newlines + indentation don't hide hits.
    # CJK marker counts above stay on the unmodified sample (TIPO / CNIPA
    # headers don't straddle whitespace runs).
    sample_lower_norm = re.sub(r"\s+", " ", sample.lower())
    epc_markers = _count_markers(sample_lower_norm, _EPC_MARKERS)
    us_markers = _count_markers(sample_lower_norm, _US_MARKERS)

    # Cased FIG./Fig. count on the WHOLE document (no lowercasing, no sample
    # truncation). Figure references typically appear in the Detailed
    # Description section, well past the first 50 paragraphs the marker scan
    # samples — so we scan the full text for this specific signal. When
    # capitalized FIG. dominates (US convention) over mixed-case Fig./fig.
    # (EPC convention per Guidelines F-V § 1.2), boost us_markers so the
    # detector catches plain US drafts that lack USPTO/MPEP/35 U.S.C. tells.
    fig_cased = len(_FIG_CASED_RE.findall(text))
    fig_mixed = len(_FIG_MIXED_RE.findall(text))
    if fig_cased >= _FIG_CASED_MIN and fig_cased > fig_mixed * 2:
        # Treat as +2 us markers — enough to satisfy the delta gate alone.
        us_markers += 2

    if selected == Jurisdiction.US:
        if cjk > _CJK_HIGH:
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
        # English / Latin-script content with US selected → check for EPC
        # tells. Require a strong delta so US drafts that merely cite an
        # EPC counterpart don't get bumped.
        if epc_markers - us_markers >= _EN_MARKER_MIN_DELTA and epc_markers > 0:
            return Jurisdiction.EPC.value
        return None

    if selected == Jurisdiction.CN:
        if cjk < _CJK_LOW:
            # Latin-script under CN selection → US or EPC. Prefer EPC when
            # the EPC-distinct markers fire; otherwise US (existing default).
            if epc_markers - us_markers >= _EN_MARKER_MIN_DELTA and epc_markers > 0:
                return Jurisdiction.EPC.value
            return Jurisdiction.US.value
        if tipo > cnipa and tipo > 0:
            return Jurisdiction.TW.value
        return None

    if selected == Jurisdiction.TW:
        if cjk < _CJK_LOW:
            if epc_markers - us_markers >= _EN_MARKER_MIN_DELTA and epc_markers > 0:
                return Jurisdiction.EPC.value
            return Jurisdiction.US.value
        if cnipa > tipo and cnipa > 0:
            return Jurisdiction.CN.value
        return None

    if selected == Jurisdiction.EPC:
        if cjk > _CJK_HIGH:
            # Heavy CJK with EPC selected → flag the mismatch with the
            # most-likely-correct CJK jurisdiction.
            if tipo > cnipa:
                return Jurisdiction.TW.value
            if cnipa > tipo:
                return Jurisdiction.CN.value
            return Jurisdiction.CN.value
        # Latin-script EPC: flip to US when US markers clearly dominate.
        # Symmetric to the US-side check above — the previous asymmetric
        # `epc_markers == 0` gate failed on the common case of a US draft
        # whose spec body never types "USPTO" / "MPEP" / "35 U.S.C." but
        # uses US-only phrasings (`method of claim N`, `system of claim N`).
        # If a US draft legitimately cites an EPC counterpart, the delta
        # gate (≥ 2) still keeps the bar high enough to avoid noise.
        if us_markers - epc_markers >= _EN_MARKER_MIN_DELTA and us_markers > 0:
            return Jurisdiction.US.value
        return None

    return None
