# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""CN specification-support analysis (说明书支持分析).

Implements 专利法 §26 第4款 ("权利要求书应当以说明书为依据") and the
corresponding 审查指南 第二部分第二章 §3.2.1 examination guideline.
Mirrors the TW spec-support walker at ``tw_spec_support.py`` (ADR-138)
with three CN-specific adaptations:

  1. **No Tier 0 symbol-table whitelist.** CN drafters do not maintain
     a standalone 符号说明 section (that surface is TIPO-unique); CN
     reference numerals appear inline in 具体实施方式, already inside
     the Tier 1-3 search surface. Dropping the tier simplifies the
     matcher without precision cost.
  2. **Excludes 背景技术 from spec_text.** 审查指南 §2.2.3 defines
     背景技术 as prior-art context, not disclosure of the invention.
     §3.2.1 grounds support in "充分公开的内容" — sufficiently
     disclosed content. A claim term supported *only* by 背景技术 is
     not drafted as disclosed by the inventor; flagging it is the
     correct §26 第4款 behavior.
  3. **Native-CN-drafting-grounded stoplists.** Seeds for conjunctions,
     prepositions, boilerplate, leading-rejects, trailing tokens,
     suffix-only leads, and interior rejects are grounded in 审查指南
     drafting conventions + CN practitioner style rather than
     TW-corpus artifacts.

Emits ``UnsupportedTerm`` findings for each claim noun phrase that fails
all three tiers:

  Tier 1: aggressively-normalized exact substring — claim-side term
    goes through ``_normalize_for_spec_support_cn`` (walker normalizer
    + leading preposition strip 于/到/在/自/由/从/向/对 + both paren
    and bare-numeral ref-numeral strip), then tested as a substring
    of spec_text.
  Tier 2: raw-form exact substring — catches over-normalization cases
    where the drafter's literal claim phrasing appears verbatim in
    the spec.
  Tier 3: CJK character-window fallback — normalized term's bigrams
    must all co-occur within a ±30-char sliding window over spec_text.

Spec_text composition: ``technical_field + summary + detailed_description``.
Excludes ``background`` (prior-art context, not disclosure),
``drawings_description`` (figure captions, FP risk), and ``abstract_text``
(not written-description).

Claim-side inventory hygiene additionally skips terms flagged by the
antecedent walker as ``category: "tw_contamination"`` (该等/该些 residue
from 繁转简 conversion — those are parser-level artifacts, not native
CN terms worth spec-support analysis).
"""

from __future__ import annotations

import re

from patentlint.analysis.cjk_tokenize import tokenize_cn
from patentlint.analysis.cn_claims import (
    extract_introductions_cn,
    normalize_reference_term_cn,
)
from patentlint.models import Claim, CnPatentDocument, UnsupportedTerm

# --- Stoplists -------------------------------------------------------------

# Generic preamble-category nouns too broad to meaningfully check against
# spec text. Exact-match only (walker inventory uses ``final in``). Grounded
# in 审查指南 §3.1.1 canonical genus forms (一种X where X is 方法/装置/系统/
# 设备/手段/步骤) + 技术方案 (the generic term 审查指南 uses throughout for
# "the claimed invention"). Deliberately excludes 元件/组件/构件/部分/表面/
# 部位/侧/面/结构 — these form legitimate compound terms (开口部, 底部,
# 第一表面, 连接结构) per TW audit #2 lesson.
_CN_GENERIC_TERMS: frozenset[str] = frozenset({
    "系统",
    "装置",
    "方法",
    "设备",
    "手段",
    "步骤",
    "技术方案",
    # 单元 is bare-genus in CN drafting (drafters write 处理单元 / 存储单元
    # as compounds). Bare 单元 in inventory is walker stranding from
    # patterns like 单元在第二X / 单元能够X — after interior reject + verb
    # strip, the residue lands as bare 单元, which we reject here as too
    # broad to meaningfully spec-check (CN115485995B).
    "单元",
})

# Boilerplate fragments / back-reference residues that should never flow
# into the spec-support inventory. Checked both as exact match
# (``final in _CN_BOILERPLATE_TERMS``) and as a prefix
# (``final.startswith(phrase)``) so walker captures like
# 根据权利要求4至权利要求10 are also filtered.
#
# Excluded deliberately:
#   - 所述 / 其中 — these are reference particles, not standalone noun
#     phrases; walker should never emit them bare, and including here
#     would mask a walker bug.
_CN_BOILERPLATE_TERMS: frozenset[str] = frozenset({
    # CN plural quantifiers (若干 / 一些 are CN-only; TIPO drafters don't
    # use them). Walker should strip via strip_leading_quantifier_cn, but
    # defense-in-depth against leakage.
    "多个",
    "若干",
    "一些",
    "数个",
    "复数",
    "复数个",
    "两个",
    "三个",
    # Anaphoric markers (parallel to TW 前述/上述/如上所述).
    "前述",
    "上述",
    "如上所述",
    # CN claim-reference prefixes (parallel to TW 如请求项).
    # Bare 权利要求 catches walker leakage where 如/根据 was stripped
    # upstream — appears in 5+ publication fixtures (CN112271269B,
    # CN114357105B, CN115485995B, CN117427144B, CN120266060A).
    "如权利要求",
    "根据权利要求",
    "权利要求",
    # Walker over-strip of 非瞬时性 (non-transitory) — drops 时性 leaving
    # bare 非瞬 (CN115952274B). Length-2 fragment, never a real term.
    "非瞬",
})

# Trailing clause tokens from native-CN drafting conventions. Applied
# iteratively (longest-first) after the walker normalizer. Grounded in
# CN practitioner verbal habits per 审查指南 §3.3 claim-drafting
# conventions + 专利代理人 training materials.
#
# Rationale by token family:
#   - Spatial suffixes (之间/之上/之下/之内/之外): CN drafters strand
#     these when walker captures positional clauses like
#     "X之间设置有Y" → capture lands as "X之间".
#   - Locative copulas (位于/设于/置于/处于): "X位于Y" stranding.
#   - Action-verb residues (构成/组成/形成): "由X构成Y" strand-shape.
#   - Relational pair predicates (相连/相接/相对/相邻): CN claim idiom.
#   - Comparison verbs (超过/介于/大于/小于/等于): direct TW parallel
#     plus CN-specific comparisons.
#   - Generic stranding (时/设置/配置): direct TW parallel (TW 時 → 时;
#     TW 設 → 设置/配置 since CN uses the longer compound).
_CN_SPEC_SUPPORT_TRAILING_TOKENS: tuple[str, ...] = tuple(sorted(
    (
        # Spatial
        "之间", "之上", "之下", "之内", "之外",
        # Locative copulas
        "位于", "设于", "置于", "处于",
        # Action verbs (manufacturing / construction)
        "构成", "组成", "形成", "制造",
        # Relational pairs
        "相连", "相接", "相对", "相邻",
        # Comparison
        "超过", "介于", "大于", "小于", "等于",
        # Generic verbal residues. 配 catches 避让组件配 (CN213655447U)
        # where walker truncated 配置.
        "设置", "配置", "配",
        "时",
    ),
    key=len,
    reverse=True,
))

# Leading verbal / clause-fragment prefixes. CN drafters use existential
# verbs (设有/装有/备有/配置有/设置有) heavily for "is provided" /
# "comprises" — pattern `在所述X上设置有Y` is canonical per 审查指南
# §3.3 examples. Walker capture strand-shapes land at capture *start*;
# stripping at leading-reject layer prevents inventory pollution.
#
# TW has nothing analogous because TIPO drafting prefers 具有/包含 over
# existential 設有 constructions. Multi-char sequences only — single-char
# leads can't be blanket-rejected without FN risk on compound nouns.
_CN_SPEC_SUPPORT_LEADING_REJECTS: tuple[str, ...] = (
    # CN existential-verb prefixes (审查指南 §3.3 drafting conventions)
    "装设有",
    "配置有",
    "设置有",
    "安装有",
    "存储有",
    "形成有",
    "设有",
    "装有",
    "备有",
    # Relational (noun dropped, prep+ref stranded)
    "对该",
    "至该",
    "向该",
    "与该",
    # Verbal prefixes (CN claim-drafting idioms)
    "用以",
    "用于",
    "能够",
    "以使",
    "以控",
    "以从",
    # Direct parallels to TW audit tokens
    "有多",
    "有一",
    "有可",  # 有可被X (CN115952274B)
    "有计",  # 有计算机指令 (CN115952274B)
    "显示",
    "描述",
    # Walker fragment from 如权利要求N项所述 — `项所` strands when 述
    # gets cut by interior boundary detection (CN114357105B claim 6).
    "项所",
)

# Characters that appear ONLY as noun suffixes in CN patent diction
# (开口部, 顶端). When one appears at position 0 of a normalized term,
# the walker captured a fragment starting mid-compound. Reject these
# single-char leads. Dropped TW's 埠 — TIPO-specific for USB-shaped Latin
# loanwords; CN uses 口 which has too many legitimate compound uses
# (开口, 出口) to blanket-reject.
_CN_SUFFIX_ONLY_LEADS: frozenset[str] = frozenset({"部", "端"})

# Structural interior markers — substrings that, if present anywhere in
# a captured term, indicate it's a clause / verb-phrase / boilerplate
# fragment, not a noun phrase. Comprehensive list grounded in CN claim-
# drafting conventions (审查指南 §3) plus walker-fragment audit across the
# 10 CN publication fixtures. Each entry has near-zero FN risk on
# legitimate compound nouns: these are particles, modal/auxiliary verbs,
# manner adverbs, locative+ordinal phrases, and passive-marker
# constructions that don't appear in real claim-element names.
_CN_SPEC_SUPPORT_INTERIOR_REJECTS: tuple[str, ...] = (
    # Comparison clauses (TW parallel)
    "超过",
    "超出",
    "彼此",
    # Claim reference particles — 权利要求 anywhere in a captured term is
    # walker meta-reference leakage (e.g., "通信设备执行如权利要求",
    # "采用如权利要求1-9中任", "介质所在设备执行权利要求"). Affects 4+
    # fixtures (CN115485995B, CN112271269B, CN116662522B, CN114357105B).
    "权利要求",
    # Modal / auxiliary verbs
    "能够",
    # Adverbs (manner, sequence, intensity)
    "进一步",
    "依次",
    "相向地",
    "相背地",
    "相对地",
    # Purposive verb phrases
    "用于",
    "以使",
    "以控",
    # Locative + ordinal — CN drafters write "在第二起始时刻" etc.
    "在第",
    # Genus + preposition stranding — walker capture lands on bare-genus
    # plus stranded 在 (CN115485995B `单元在`). Each pattern catches the
    # walker artifact without affecting compound nouns.
    "单元在",
    "装置在",
    "组件在",
    # Preposition phrases (sequential / proximal)
    "沿远离",
    "沿靠近",
    # Passive-marker constructions — `被进一步`, `被进行`, `被执行`. Bare
    # `被` excluded: too common in legitimate compound nouns
    # (e.g., 被覆层 / 被加热部).
    "被进",
    "被执行",
)

# Leading prepositions that survive walker normalization. Strip these
# claim-side before the Tier 1 exact check. Spec-side text is unchanged.
# TW's 於/到/在/自/由 direct-converted, plus CN-specific 从/向/对 (CN
# drafters use 从所述X frequently where TW uses 自; 向所述 and 对所述
# are CN-native prepositions absent from TW practice).
_CN_LEADING_PREPOSITIONS: tuple[str, ...] = ("于", "到", "在", "自", "由", "从", "向", "对")

# Reference numerals per 专利法实施细则 §21 — drafters inline element
# numerals like 底座(10). NON-ANCHORED to handle:
#   (a) Trailing parens (底座(10) → 底座)
#   (b) Interior parens when walker capture has trailing text
#       (屏幕支撑组件(100)的Y → 屏幕支撑组件 after 的Y also strips)
#   (c) Walker-truncated unbalanced parens (屏幕支撑组件(100 → 屏幕支撑组件)
# Restricted inside-content to ASCII alnum + dashes — never CJK — so we
# don't accidentally strip parenthesized noun phrases like (展开状态).
_PAREN_REF_NUMERAL_RE = re.compile(r"[（(]\s*[A-Za-z0-9\-—–]+\s*[）)]?")

# Bare-numeral reference per CN-specific drafting. CN drafters sometimes
# write 底座10 without parentheses (vs. TW's universal parenthesization
# per 施行细则 §19). NON-ANCHORED — strips numerals after any CJK char
# that isn't 第 (lookbehind gates against ordinals 第一/第二). Handles
# both trailing (底座10 → 底座) and interior (底座10的位置 → 底座的位置).
# Also handles bibliographic chemistry ranges 碳数～20 / X~30 by stripping
# optional [～~-] separators between the CJK char and digit run
# (CN120266060A claim 1).
_BARE_REF_NUMERAL_CN_RE = re.compile(
    r"(?<=[一-鿿])[～~\-—–]?(?<!第)\d+[a-zA-Z'′]?"
)

# Coordinating conjunctions. TW's 以及/及/與/和 direct-converted (與 → 与,
# Simplified) plus 或. CN claims use `包括A或B` (disjunctive alternative)
# more often than TW; both A and B should enter the inventory because
# both are within claim scope. TW audit didn't surface 或-split because
# TIPO drafters prefer the word 或者 which is distinct.
_CN_CONJUNCTIONS: tuple[str, ...] = ("以及", "及", "和", "与", "或")

# Sliding-window size (in CJK characters) for Tier 3 proximity matching.
# Same ±30-char width as TW — Chinese noun phrases are 2-4 chars; ±30
# spans ~5-8 clauses of context, matching the granularity at which a
# drafter would declare support for a compound term.
_CHAR_WINDOW_SIZE: int = 30

# Minimum bare-noun length for a term to enter the inventory. Filters
# single-char residues.
_MIN_INVENTORY_LENGTH: int = 2

# Maximum length (chars) for an inventory term. Captures beyond this
# length are almost always walker clause artifacts rather than genuine
# compound nouns. 10 chars is ~3-5 Chinese morphemes — long enough for
# legitimate compound terms and short enough to reject full clauses.
# CN tightened from TW's 12 because publication-fixture audit showed
# 9-12-char clause leakage (法律知识领域中的知识内容 = 11,
# 介质所在设备执行权利要求 = 12 — CN116662522B).
_MAX_INVENTORY_LENGTH: int = 10


# --- Normalization helpers -------------------------------------------------


def _normalize_for_spec_support_cn(
    text: str,
    *,
    strict_qualifier_matching: bool = False,
) -> str:
    """Normalize a claim-side term for CN spec-support matching.

    Order:
        1. Strip trailing parenthetical reference numeral 专利法实施细则 §21
           (底座(10) → 底座).
        2. Strip trailing bare reference numeral (底座10 → 底座) —
           CN-specific; TW doesn't need this because TIPO drafters
           universally parenthesize per 施行细则 §19.
        3. Strip leading preposition (于/到/在/自/由/从/向/对).
        4. Run the walker normalizer (strip_reference_form_prefix_cn +
           strip_leading_qualifier_cn + clean_noun_phrase_cn +
           strip_leading_quantifier_cn).
        5. Mid-phrase reference-prefix recovery (catches stranded
           该/所述/前述 at interior positions).
        6. Trailing conjunction strip (顔色与 → 顔色).
        7. Trailing CN-drafting-specific token strip (iterative,
           longest-first).
        8. Re-strip trailing numerals exposed by the verb strip.

    Spec-side text is NOT normalized — the match is asymmetric, so
    "使用者界面" (claim) matches both "使用者界面" (bare) and
    "所述使用者界面" (prefixed) in the spec.
    """
    if not text:
        return text
    t = _PAREN_REF_NUMERAL_RE.sub("", text).strip()
    t = _BARE_REF_NUMERAL_CN_RE.sub("", t).strip()
    for prep in _CN_LEADING_PREPOSITIONS:
        if t.startswith(prep) and len(t) > len(prep):
            t = t[len(prep):]
            break
    t = normalize_reference_term_cn(
        t,
        strict_qualifier_matching=strict_qualifier_matching,
    )
    t = _recover_from_midphrase_prefix_cn(
        t,
        strict_qualifier_matching=strict_qualifier_matching,
    )
    t = _strip_trailing_conjunction_cn(t)
    t = _strip_spec_support_trailing_tokens_cn(t)
    # Re-strip trailing numerals exposed by the verb strip.
    t = _PAREN_REF_NUMERAL_RE.sub("", t).strip()
    t = _BARE_REF_NUMERAL_CN_RE.sub("", t).strip()
    return t


def _strip_spec_support_trailing_tokens_cn(term: str) -> str:
    """Iteratively strip trailing CN clause tokens (longest-first)."""
    for _ in range(8):
        stripped = False
        for token in _CN_SPEC_SUPPORT_TRAILING_TOKENS:
            if term.endswith(token) and len(term) > len(token):
                term = term[: -len(token)]
                stripped = True
                break
        if not stripped:
            break
    return term


def _has_leading_reject_cn(term: str) -> bool:
    """True if the term starts with a known verbal/clause-fragment prefix."""
    if not term:
        return False
    if term[0] in _CN_SUFFIX_ONLY_LEADS:
        return True
    return any(term.startswith(p) for p in _CN_SPEC_SUPPORT_LEADING_REJECTS)


def _has_interior_reject_cn(term: str) -> bool:
    """True if the term contains a structural interior marker.

    See ``_CN_SPEC_SUPPORT_INTERIOR_REJECTS`` for the full marker
    catalog: comparison clauses, claim-reference particles, modals,
    manner/sequence adverbs, purposive phrases, locative+ordinal,
    preposition phrases, and passive-marker constructions.
    """
    return any(marker in term for marker in _CN_SPEC_SUPPORT_INTERIOR_REJECTS)


def _has_leading_conjunction_cn(term: str) -> bool:
    """True if the term starts with a CN conjunction.

    Walker-capture artifact: when claim text uses `X或Y`, `X与Y`, `X和Y`,
    walker may strand `或所述`, `与所述`, `和X` as the entire intro. These
    are clause-fragments, not noun phrases. Affects CN115485995B
    (`或所述`), CN115952274B (`与所述`).

    Multi-char conjunctions checked first (以及 before 及).
    """
    for conj in sorted(_CN_CONJUNCTIONS, key=len, reverse=True):
        if term.startswith(conj) and len(term) > len(conj):
            return True
    return False


def _is_boilerplate_cn(term: str) -> bool:
    """True if term matches a boilerplate phrase exactly or as a prefix."""
    if term in _CN_BOILERPLATE_TERMS:
        return True
    return any(term.startswith(phrase) for phrase in _CN_BOILERPLATE_TERMS)


def _recover_from_midphrase_prefix_cn(
    term: str,
    *,
    strict_qualifier_matching: bool = False,
) -> str:
    """Recover a clean noun from a walker-captured phrase with stranded
    reference-form prefix in the middle.

    CN equivalent of TW's ``_recover_from_midphrase_prefix``. Splits at
    the LAST occurrence of 前述/所述/该 and takes the suffix (the noun
    being referenced). Position 0 matches are ignored (already handled
    upstream by ``strip_reference_form_prefix_cn``).
    """
    for prefix in ("前述", "所述", "该"):
        idx = term.rfind(prefix)
        if idx > 0:
            suffix = term[idx + len(prefix):].strip()
            if suffix and len(suffix) >= _MIN_INVENTORY_LENGTH:
                return normalize_reference_term_cn(
                    suffix,
                    strict_qualifier_matching=strict_qualifier_matching,
                )
    return term


def _strip_trailing_conjunction_cn(term: str) -> str:
    """Strip a dangling trailing conjunction (X及, X和, X与, X或)."""
    for conj in _CN_CONJUNCTIONS:
        if term.endswith(conj) and len(term) > len(conj):
            return term[:-len(conj)]
    return term


def _split_on_conjunction_cn(
    term: str,
    *,
    strict_qualifier_matching: bool = False,
) -> list[str]:
    """Split a walker-captured conjunction phrase into constituent nouns.

    When a normalized intro spans ``X <conj> Y``, returns [X, Y]. Both
    sides must be ≥ ``_MIN_INVENTORY_LENGTH`` chars — protects compound
    nouns that happen to contain 及/和/与 as morphemes (rare in CN
    patent diction but possible).
    """
    for conj in _CN_CONJUNCTIONS:
        idx = term.find(conj)
        if idx < 0:
            continue
        left = term[:idx].strip()
        right = term[idx + len(conj):].strip()
        # Right side may carry a leading quantifier the walker preserved
        # because it started mid-phrase. Re-normalize.
        right = (
            normalize_reference_term_cn(
                right,
                strict_qualifier_matching=strict_qualifier_matching,
            )
            if right
            else right
        )
        if len(left) >= _MIN_INVENTORY_LENGTH and len(right) >= _MIN_INVENTORY_LENGTH:
            return (
                _split_on_conjunction_cn(
                    left,
                    strict_qualifier_matching=strict_qualifier_matching,
                )
                + _split_on_conjunction_cn(
                    right,
                    strict_qualifier_matching=strict_qualifier_matching,
                )
            )
    return [term]


def _collect_spec_text_cn(doc: CnPatentDocument) -> str:
    """Concatenate the body subsections used for CN spec-support matching.

    Includes: technical_field + summary + detailed_description.
    Excludes: background (审查指南 §2.2.3 — prior-art context, not
    disclosure of the invention; a claim term supported only by
    背景技术 is itself a §26 第4款 violation), drawings_description
    (figure captions, FP risk), abstract_text (not written-description).
    """
    parts: list[str] = []
    parts.extend(doc.technical_field)
    parts.extend(doc.summary)
    parts.extend(doc.detailed_description)
    return "\n".join(parts)


def _build_inventory_cn(
    claims: list[Claim],
    *,
    contamination_terms: frozenset[str],
    strict_qualifier_matching: bool = False,
) -> list[tuple[int, str]]:
    """Build deduped claim-term inventory from intros across all claims.

    Returns a list of ``(claim_id, normalized_term)`` pairs. Terms
    flagged by the antecedent walker as ``category="tw_contamination"``
    (该等/该些 residue from 繁转简 conversion) are skipped — they're
    parser-level artifacts, not native CN terms worth checking.
    """
    seen: dict[str, int] = {}
    inventory: list[tuple[int, str]] = []
    for claim in claims:
        for orig, norm in extract_introductions_cn(
            claim,
            strict_qualifier_matching=strict_qualifier_matching,
        ):
            root = _normalize_for_spec_support_cn(
                norm or orig,
                strict_qualifier_matching=strict_qualifier_matching,
            )
            if not root:
                continue
            for final in _split_on_conjunction_cn(
                root,
                strict_qualifier_matching=strict_qualifier_matching,
            ):
                if not final or len(final) < _MIN_INVENTORY_LENGTH:
                    continue
                if len(final) > _MAX_INVENTORY_LENGTH:
                    continue
                if _has_leading_reject_cn(final) or _has_interior_reject_cn(final):
                    continue
                if _has_leading_conjunction_cn(final):
                    continue
                if final in _CN_GENERIC_TERMS or _is_boilerplate_cn(final):
                    continue
                if final in contamination_terms:
                    continue
                if final in seen:
                    continue
                seen[final] = claim.id
                inventory.append((claim.id, final))
    return inventory


# --- Tier matchers ---------------------------------------------------------


def _tier1_normalized_exact(norm_term: str, spec_text: str) -> bool:
    return norm_term in spec_text


def _tier2_raw_exact(raw_candidates: list[str], spec_text: str) -> bool:
    """True if any raw (unnormalized) intro candidate appears verbatim."""
    return any(raw and raw in spec_text for raw in raw_candidates)


def _tier3_char_window(norm_term: str, spec_text: str) -> bool:
    """True if all normalized-term bigrams co-occur within a ±window."""
    term_tokens = set(tokenize_cn(norm_term))
    if not term_tokens:
        return False
    for tok in term_tokens:
        if tok not in spec_text:
            return False
    window = _CHAR_WINDOW_SIZE
    spec_len = len(spec_text)
    if spec_len < window:
        return True
    for i in range(0, spec_len - window + 1):
        slice_ = spec_text[i:i + window]
        if all(tok in slice_ for tok in term_tokens):
            return True
    return False


# --- Public API ------------------------------------------------------------


def check_spec_support_cn(
    doc: CnPatentDocument,
    *,
    antecedent_findings: list[dict] | None = None,
    strict_qualifier_matching: bool = False,
) -> list[UnsupportedTerm]:
    """Check that claim noun phrases have support in the CNIPA specification.

    Per 专利法 §26 第4款 + 审查指南 第二部分第二章 §3.2.1. Three tiers
    (see module docstring). Tier 0 (symbol-table whitelist) intentionally
    absent — CN has no 符号说明 surface.

    When ``antecedent_findings`` is provided, terms flagged with
    ``category="tw_contamination"`` are skipped from the inventory so
    spec_support doesn't double-report parser-level 繁转简 artifacts.
    """
    if not doc.claims:
        return []

    contamination_terms: frozenset[str] = frozenset(
        item.get("term", "")
        for item in (antecedent_findings or [])
        if item.get("category") == "tw_contamination"
    )

    spec_text = _collect_spec_text_cn(doc)
    inventory = _build_inventory_cn(
        doc.claims,
        contamination_terms=contamination_terms,
        strict_qualifier_matching=strict_qualifier_matching,
    )

    # Pre-collect raw intro candidates per normalized term so Tier 2
    # can test every original span that produced this normalized form.
    raw_by_norm: dict[str, list[str]] = {}
    for claim in doc.claims:
        for orig, norm in extract_introductions_cn(
            claim,
            strict_qualifier_matching=strict_qualifier_matching,
        ):
            final = _normalize_for_spec_support_cn(
                norm or orig,
                strict_qualifier_matching=strict_qualifier_matching,
            )
            if not final:
                continue
            raw_by_norm.setdefault(final, []).append(orig)

    unsupported: list[UnsupportedTerm] = []

    for claim_id, norm_term in inventory:
        tiers: list[str] = []

        # Tier 1: normalized exact substring
        tiers.append("normalized_exact")
        if _tier1_normalized_exact(norm_term, spec_text):
            continue

        # Tier 2: raw exact substring
        tiers.append("raw_exact")
        if _tier2_raw_exact(raw_by_norm.get(norm_term, []), spec_text):
            continue

        # Tier 3: CJK character-window fallback
        tiers.append("char_window")
        if _tier3_char_window(norm_term, spec_text):
            continue

        unsupported.append(UnsupportedTerm(
            claim_number=claim_id,
            phrase=norm_term,
            tiers_checked=tiers,
        ))

    return unsupported


def attach_cross_references_cn(
    antecedent_findings: list[dict],
    unsupported_terms: list[UnsupportedTerm],
) -> None:
    """Cross-link CN antecedent and spec-support findings on the same term.

    Mirrors ``attach_cross_references_tw``. When the same
    ``(claim_id, normalized_term)`` pair appears in both lists, each
    finding is annotated with a ``cross_ref`` pointing at the sibling
    check so the frontend renders a hint line.

    Mutates both lists in place.
    """
    ab_pairs: set[tuple[int, str]] = {
        (item["claim_id"], item.get("term", ""))
        for item in antecedent_findings
    }
    spec_pairs: set[tuple[int, str]] = {
        (ut.claim_number, ut.phrase) for ut in unsupported_terms
    }

    for item in antecedent_findings:
        if (item["claim_id"], item.get("term", "")) in spec_pairs:
            item["cross_ref"] = "spec_support"

    for ut in unsupported_terms:
        if (ut.claim_number, ut.phrase) in ab_pairs:
            ut.cross_ref = "antecedent"
