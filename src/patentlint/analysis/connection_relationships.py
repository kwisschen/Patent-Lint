# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Connection-relationship clarity check (TW + CN parity).

TIPO 專利審查基準 第二篇第一章 §2.4 and CNIPA 审查指南 第二部分 第二章
§3.2.1 + 专利法 §26.4 require independent apparatus/device/system claims
to teach how their components are arranged structurally — listing parts
without naming a connection between them is a clarity defect.

This module implements the check once and exposes per-jurisdiction
configuration so ``tw_claims`` and ``cn_claims`` can wrap it with the
appropriate Traditional/Simplified vocabularies and legal citations.

Scope (carve-outs applied in order):
  1. Independent claims only (preamble starts with 一種/一個 or 一种/一个).
  2. Method claims excluded (preamble ends with 方法).
  3. Computer-readable medium / program claims excluded (TIPO/CNIPA
     practice — non-structural subject matter).
  4. Means-plus-function claims excluded (drafter intentionally omits
     structural detail; §112(f)-equivalent practice).
  5. Composition / mixture claims excluded (chemistry compositions list
     constituents rather than assembled parts; standard 重量份 format).

Emit: ``status='verify'`` (clarity flag, not a hard rejection — drafter
may have intended composition-style enumeration that PatentLint cannot
infer without the spec). One CheckItem per in-scope claim that lists
≥2 components without a connection verb anywhere in the body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from patentlint.diagnostic_extractors import extract_connection_relationships
from patentlint.models import CheckItem, Claim


@dataclass(frozen=True)
class ConnectionRelationshipsConfig:
    """Per-jurisdiction lexicon and patterns for the connection check.

    All regex fields are pre-compiled. Verb sets are frozensets of
    surface forms; matching is membership-based on a sliding character
    window (handled inside ``_has_connection_verb``).
    """

    # Preamble + carve-out patterns
    indep_preamble_re: re.Pattern[str]
    method_preamble_re: re.Pattern[str]
    crm_preamble_re: re.Pattern[str]
    composition_genus_re: re.Pattern[str]
    mpf_marker_re: re.Pattern[str]

    # Component-list detection
    transition_re: re.Pattern[str]
    component_splitter_re: re.Pattern[str]

    # Connection verbs — primary set is empirically grounded on the
    # current real-corpus; extended set is the TIPO/CNIPA spec lexicon
    # (zero-hit on this corpus but legally grounded, retained
    # defensively against drafter style variation).
    primary_verbs: frozenset[str]
    extended_verbs: frozenset[str]

    # Output
    reference: str
    message_key_prefix: str
    details_key: str


# ── TW config ────────────────────────────────────────────────────────────

_TW_CONNECTION_CONFIG = ConnectionRelationshipsConfig(
    indep_preamble_re=re.compile(r"^[\s\u3000]*(?:一種|一個)"),
    method_preamble_re=re.compile(r"^[\s\u3000]*(?:一種|一個)[^，,。\n]{0,40}方法[，,。 \u3000]"),
    crm_preamble_re=re.compile(r"^[\s\u3000]*(?:一種|一個)[^，,。\n]{0,40}(?:儲存媒體|存儲媒體|電腦程式|電腦程序|電腦可讀)"),
    composition_genus_re=re.compile(r"^[\s\u3000]*(?:一種|一個)[^，,。\n]{0,40}(?:組成物|組合物|混合物|樹脂組成物|藥劑組成物)"),
    # MPF requires explicit 手段 token; bare 用以/用於 is purpose-clause,
    # not structural carve-out (e.g., "...用以儲存資料" appears in many
    # apparatus claims that DO have connection verbs elsewhere).
    mpf_marker_re=re.compile(r"手段"),
    transition_re=re.compile(r"包括|包含|含有|具備|具有"),
    # Splits component-list tail. ；is the dominant separator in TIPO
    # practice; 、 / 及 / 與 / 和 / 以及 catch in-line lists. We
    # deliberately exclude ， / , — those are intra-component clause
    # separators in TIPO drafting (e.g., "一第二手柄主體，與所述第
    # 一手柄主體互相連接").
    component_splitter_re=re.compile(r"；|;|、|及|與|和|以及"),
    primary_verbs=frozenset({
        # Connection verbs (empirically grounded against real TW corpus)
        "連接", "互相連接", "相連接", "設置於", "設置在",
        "設有", "安裝於", "安裝在", "安裝有",
        # Construction / disposition (post-implementation audit additions)
        "形成於", "形成有", "被構造為", "構造為", "構造成",
        "容納",
        # Kinematic structural verbs (utility-model / mechanical claims)
        "旋轉", "轉動", "移動", "滑動",
        # Spatial / dispositional
        "對應設置", "對應於", "延伸於", "延伸至",
    }),
    extended_verbs=frozenset({
        "耦接", "接觸", "連結", "附接", "固定於", "配置於",
        "嵌合", "鄰接", "貫穿", "橫跨", "平行於", "垂直於",
        "焊接", "鉚接", "卡接", "扣合", "鎖固", "黏接",
        "樞接於", "樞接", "鉸接於", "鉸接", "貼合", "貼附於",
        "圍繞", "環繞", "支撐", "夾持", "突出於", "突出",
        "電性連接", "通信連接", "通訊連接", "連通",
    }),
    reference="專利審查基準 第二篇第一章 §2.4",
    message_key_prefix="check.tw.claims.connectionRelationships",
    details_key="details.tw.connectionRelationships",
)


# ── CN config ────────────────────────────────────────────────────────────

_CN_CONNECTION_CONFIG = ConnectionRelationshipsConfig(
    indep_preamble_re=re.compile(r"^[\s\u3000]*(?:一种|一個|一种|一个)"),
    method_preamble_re=re.compile(r"^[\s\u3000]*(?:一种|一个)[^，,。\n]{0,40}方法[，,。 \u3000]"),
    crm_preamble_re=re.compile(r"^[\s\u3000]*(?:一种|一个)[^，,。\n]{0,40}(?:存储介质|存储媒介|计算机程序|计算机可读)"),
    composition_genus_re=re.compile(r"^[\s\u3000]*(?:一种|一个)[^，,。\n]{0,40}(?:组合物|混合物|树脂组合物|药剂组合物|组成物)"),
    mpf_marker_re=re.compile(r"手段"),
    transition_re=re.compile(r"包括|包含|含有|具备|具有"),
    component_splitter_re=re.compile(r"；|;|、|及|与|和|以及"),
    primary_verbs=frozenset({
        # Connection verbs (empirically grounded against real CN corpus)
        "连接", "互相连接", "相连接", "设置于", "设置在",
        "设有", "安装于", "安装在", "安装有",
        # Construction / disposition (post-implementation audit additions)
        "形成于", "形成有", "被构造为", "构造为", "构造成",
        "容纳",
        # Kinematic structural verbs (utility-model / mechanical claims)
        "旋转", "转动", "移动", "滑动",
        # Spatial / dispositional
        "对应设置", "对应于", "延伸于", "延伸至",
    }),
    extended_verbs=frozenset({
        "耦接", "接触", "连结", "附接", "固定于", "配置于",
        "嵌合", "邻接", "贯穿", "横跨", "平行于", "垂直于",
        "焊接", "铆接", "卡扣", "卡接", "锁固", "粘接",
        "枢接于", "枢接", "铰接于", "铰接", "贴合", "贴附于",
        "围绕", "环绕", "支撑", "夹持", "突出于", "突出",
        "电性连接", "通信连接", "通讯连接", "连通",
    }),
    reference="审查指南 第二部分 第二章 §3.2.1",
    message_key_prefix="check.cn.claims.connectionRelationships",
    details_key="details.cn.connectionRelationships",
)


# ── Internal helpers ─────────────────────────────────────────────────────

# Strip simple whitespace + leading paren-numerals from component
# fragments before counting/sampling. Drafters wrap component intros in
# (1) / (a) / 1. / etc. — the leading marker is not part of the noun.
_LEADING_MARK_RE = re.compile(r"^[\s\u3000]*(?:[\(（][^\)）]{1,4}[\)）]|\d+[\.．、])\s*")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# Newline + semicolon are the canonical TIPO/CNIPA component separators
# in formatted claims. Falling back to the broader splitter only when
# the tail has no newlines avoids over-counting sub-clause `、`/`以及`
# inside a single component description.
_NEWLINE_SEMI_SPLIT_RE = re.compile(r"[\n\r]+|；|;")

# Sub-clause prefixes that mark a fragment as continuation/qualification
# rather than a top-level component. Top-level components in CN/TW
# claims start with `一/第N/<bare-noun>`, NOT with these particles.
_CONTINUATION_PREFIXES = (
    "其中", "以及", "并且", "并", "或者", "或",
    "响应于", "響應於", "基于", "基於", "根据", "根據",
    "为", "為", "能够", "能夠", "被", "包括", "包含", "含有",
    "在所述", "当所述", "當所述",
)

# Functional clauses describing a previously-introduced component:
# `所述X用于...`, `所述X还用于...`, `所述X被...`. These describe what an
# existing component does, not a new component. Real component intros
# start with `一/第N/<bare-noun>`, never `所述` (which is referential).
_FUNCTIONAL_CLAUSE_RE = re.compile(
    # Subject portion allows CJK + ASCII alnum to handle technical
    # acronyms (IPC, DDR, OLED, 2D, 5G) common in CN claim drafting.
    r"^所述[\u4e00-\u9fffA-Za-z0-9]{1,20}(?:还|還)?(?:用于|用於|用以|被|位于|位於)"
)

# Strip a trailing clause introducer like `，其中` / `，且` / `，并` /
# `，或` from a sub-list intro before splitting it into inline components.
_TRAILING_CLAUSE_INTRO_RE = re.compile(
    r"[，,]\s*(?:其中|且|并(?:且)?|或(?:者)?)\s*$"
)

# Strip the claim-number prefix (e.g., ``1.`` or ``1．``) before
# matching preamble/carve-out regexes. ``Claim.text`` carries the raw
# numbered string from the parser.
_CLAIM_NUM_PREFIX_RE = re.compile(r"^\s*\d+\s*[\.．、]\s*")


def _strip_claim_prefix(text: str) -> str:
    return _CLAIM_NUM_PREFIX_RE.sub("", text or "", count=1)


def _is_in_scope(claim: Claim, config: ConnectionRelationshipsConfig) -> bool:
    """Return True iff ``claim`` is an apparatus/device/system claim that
    should be checked. Method, CRM, MPF, and composition claims are out
    of scope per the carve-out rationale documented at the module top.
    """
    if not claim.independent:
        return False

    text = _strip_claim_prefix(claim.text or "")
    if not config.indep_preamble_re.search(text):
        return False
    if config.method_preamble_re.search(text):
        return False
    if config.crm_preamble_re.search(text):
        return False
    if config.composition_genus_re.search(text):
        return False
    if config.mpf_marker_re.search(text):
        return False
    return True


def _extract_components(text: str, config: ConnectionRelationshipsConfig) -> list[str]:
    """Locate the transition phrase, split the tail, and return cleaned
    component fragments. A fragment counts when it has ≥2 CJK characters
    after leading-mark stripping; shorter fragments are line noise
    (single particles, stray punctuation, ordinal markers).
    """
    match = config.transition_re.search(text)
    if not match:
        return []

    tail = text[match.end():]
    # Prefer newline+semicolon split when newlines are present; fall back
    # to the broader inline-list splitter only for unformatted claims.
    if "\n" in tail or "\r" in tail:
        raw = _NEWLINE_SEMI_SPLIT_RE.split(tail)
    else:
        raw = config.component_splitter_re.split(tail)
    components: list[str] = []
    for fragment in raw:
        # Strip the colon/semicolon that often follows the transition
        # phrase (e.g., "包括：" leaves a leading ":" on the first
        # fragment) plus any leading whitespace.
        cleaned = fragment.lstrip(":：；; \t\u3000")
        cleaned = _LEADING_MARK_RE.sub("", cleaned).strip()
        # Cut at the first sentence-ending mark — components are clauses,
        # not whole paragraphs, and we don't want trailing 其中/wherein
        # discussion to merge into a "component".
        for sentinel in ("。", "．"):
            idx = cleaned.find(sentinel)
            if idx >= 0:
                cleaned = cleaned[:idx]
        # Skip continuation/qualification fragments — these are sub-clauses
        # describing function or context, not new components.
        if cleaned.startswith(_CONTINUATION_PREFIXES):
            continue
        # Skip functional descriptions of existing components.
        if _FUNCTIONAL_CLAUSE_RE.match(cleaned):
            continue
        # Sub-list introducers (e.g., `所述装置还包括：` /
        # `处理器核、IPC引擎硬件和存储器，其中：`). When the intro itself
        # contains a 、/和/与-separated list of bare noun phrases, expand
        # each into its own component before discarding the wrapper.
        if cleaned.endswith(("：", ":")):
            inner = cleaned.rstrip("：:")
            inner = _TRAILING_CLAUSE_INTRO_RE.sub("", inner)
            inline_parts = config.component_splitter_re.split(inner)
            inline_components = [
                p.strip() for p in inline_parts
                if len(_CJK_RE.findall(p.strip())) >= 2
            ]
            if len(inline_components) >= 2:
                components.extend(inline_components)
            continue
        if len(_CJK_RE.findall(cleaned)) >= 2:
            # Drop fragments whose noun-phrase head is implausibly long.
            # Real component names are short (`处理单元`, `第一获取模块`,
            # `IPC引擎硬件`); when there's no internal comma to truncate at
            # AND the head exceeds ~20 CJK chars, the fragment is almost
            # always a docx-loader artifact (e.g., `第四神经网\n络` split
            # mid-word) or a runaway sub-clause, not a real component.
            if "，" not in cleaned and "," not in cleaned:
                if len(_CJK_RE.findall(cleaned)) > 20:
                    continue
            components.append(cleaned)
    return components


_NAME_TERMINATORS = ("，", ",", "。", "．", "；", ";", "(", "（", " ", "\n", "\t")


def _component_name(component_text: str) -> str:
    """Return the noun-phrase head of a component clause.

    Components in CN/TW claims usually have the shape `<noun>，<purpose>`
    (e.g., `抽取模块，用于X`) or just `<noun>` (e.g., `处理器核`). The
    head is everything before the first internal punctuation, parenthesis,
    or whitespace. Used to surface concrete component names in the
    finding's verify message and details so drafters can quickly locate
    what was flagged.
    """
    text = component_text.strip()
    cut = len(text)
    for sep in _NAME_TERMINATORS:
        idx = text.find(sep)
        if 0 < idx < cut:
            cut = idx
    return text[:cut].strip()


def _has_connection_verb(text: str, config: ConnectionRelationshipsConfig) -> bool:
    """Return True iff the claim body contains any primary or extended
    connection verb. Multi-character verbs are searched as substrings
    (no tokenization needed — TIPO/CNIPA structural verbs are
    well-bounded surface forms).
    """
    for verb in config.primary_verbs:
        if verb in text:
            return True
    for verb in config.extended_verbs:
        if verb in text:
            return True
    return False


# ── Public entry point ───────────────────────────────────────────────────


def check_connection_relationships(
    claims: list[Claim],
    config: ConnectionRelationshipsConfig,
) -> list[CheckItem]:
    """Flag in-scope independent claims that enumerate ≥2 components
    without a connection verb anywhere in the body.

    Returns one ``CheckItem`` per flagged claim plus an aggregate ``pass``
    item when no claim trips the check (so the report always includes
    the row). Out-of-scope claims contribute nothing — the pass tile
    stays single regardless of how many compositions/method claims the
    document contains.
    """
    flagged: list[tuple[int, int, list[str]]] = []

    for claim in claims:
        if not _is_in_scope(claim, config):
            continue
        components = _extract_components(claim.text or "", config)
        if len(components) < 2:
            continue
        if _has_connection_verb(claim.text or "", config):
            continue
        flagged.append((claim.id, len(components), components[:3]))

    if not flagged:
        return [CheckItem(
            status="pass",
            message="All independent apparatus claims describe component connections.",
            message_key=f"{config.message_key_prefix}.pass",
            reference=config.reference,
        )]

    # Pre-compute the per-flag short-name tuple once so we can both
    # render the per-claim CheckItem message AND feed the diagnostic
    # extractor without recomputing component-name heads.
    flagged_with_names: list[tuple[int, int, list[str], list[str]]] = [
        (claim_id, count, sample_components, [_component_name(c) for c in sample_components])
        for claim_id, count, sample_components in flagged
    ]
    # The extractor surfaces a per-claim `findings[]` so ReportModal
    # payloads carry actionable detail (issue #48 — previously emitted
    # empty diagnostic trails). It takes the (claim_id, count, names)
    # triples; rebuild that view.
    extractor_input = [
        (claim_id, count, sample_names)
        for claim_id, count, _, sample_names in flagged_with_names
    ]
    diagnostics_payload = extract_connection_relationships(extractor_input, claims)

    items: list[CheckItem] = []
    for claim_id, count, sample_components, sample_names in flagged_with_names:
        # English fallback message — locale templates render sample_names
        # via the JS detailsFormatter for proper list-separator handling.
        names_inline = ", ".join(sample_names)
        if count > len(sample_names):
            names_inline += ", etc."
        # Per-claim CheckItem carries the slice of the aggregate findings
        # list belonging to THIS claim, so a per-claim Report click ships
        # only the relevant finding (mirrors how antecedent + spec-support
        # cards filter their findings before send).
        per_claim_diag = dict(diagnostics_payload)
        if per_claim_diag.get("findings"):
            per_claim_diag["findings"] = [
                f for f in per_claim_diag["findings"]
                if f.get("claim_id") == claim_id
            ]
        items.append(CheckItem(
            status="verify",
            message=(
                f"Independent claim {claim_id} lists {names_inline} "
                f"without a structural connection verb."
            ),
            message_key=f"{config.message_key_prefix}.verify",
            details_key=config.details_key,
            details_params={
                "claim_id": claim_id,
                "component_count": count,
                "sample_components": sample_components,
                "sample_names": sample_names,
            },
            diagnostics=per_claim_diag,
            reference=config.reference,
        ))
    return items


__all__ = [
    "ConnectionRelationshipsConfig",
    "_TW_CONNECTION_CONFIG",
    "_CN_CONNECTION_CONFIG",
    "check_connection_relationships",
]
