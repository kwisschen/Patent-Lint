# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""TW specification-support analysis (說明書支持分析).

Implements 專利法 §26 第3項 ("申請專利範圍…必須為說明書所支持") and the
corresponding 專利審查基準 examination guideline. Mirrors the US §112(a)
``check_spec_support`` at ``analysis/claims.py:998`` but swaps the English
word-window machinery for CJK-appropriate matching (ADR-138).

The check emits an ``UnsupportedTerm`` finding for each claim noun phrase
that fails all four tiers:

  Tier 0 (pre-check): symbol-table whitelist - term appears as a
    ``符號說明`` glossary entry (general table ∪ 代表圖之符號說明).
    Glossary entries are spec-supported by definition.
  Tier 1: aggressively-normalized exact substring - claim-side term
    goes through ``_normalize_for_spec_support_tw`` (walker normalizer
    + leading preposition strip 於/到/在/自/由), then tested as a
    substring of spec_text.
  Tier 2: raw-form exact substring - catches over-normalization cases
    where the drafter's literal claim phrasing (quantifier + noun)
    appears verbatim in the spec.
  Tier 3: CJK character-window fallback - normalized term's bigrams
    must all co-occur within a ±30-char sliding window over spec_text.
    Fires on compound assembly patterns.

Spec_text composition (per §2.1 of the plan): ``technical_field +
prior_art + disclosure + embodiment``. Excludes ``drawings_description``
(figure captions → FP risk), ``symbol_table`` (non-prose, handled in
Tier 0), and ``abstract_text`` (not written-description per 專利審查基準).

The claim-side normalizer is INDEPENDENT of walker-tuning flags
(strict_plural_reference_matching, strict_qualifier_matching). Those
flags tune back-reference matching precision - a different semantic
axis from "is this term in the spec at all".
"""

from __future__ import annotations

import re

from patentlint.analysis.cjk_tokenize import tokenize_tw
from patentlint.analysis.tw_claims import (
    extract_introductions_tw,
    normalize_arabic_ordinal_to_cjk,
    normalize_reference_term,
)
from patentlint.models import Claim, TwPatentDocument, UnsupportedTerm

# --- Stoplists -------------------------------------------------------------

# Generic preamble-category nouns that are too broad to meaningfully check
# against spec text. Conservative seed; grow via hand-classification (§2.4
# of plan). Deliberately excludes 元件/組件/構件/部分/表面/部位/側 because
# audit #2 surfaced real TW claim terms of these shapes (環狀部, 開口部,
# 底部, 第二操作介面) that would be false-negatives if blanket-stripped.
_TW_GENERIC_TERMS: frozenset[str] = frozenset({
    "系統",
    "裝置",
    "方法",
    "手段",
    "步驟",
})

# Boilerplate fragments / back-reference residues that should never flow
# into the spec-support inventory. 如請求項 is an incorporation-by-reference
# marker; 前述/上述 are anaphoric, not terms. Checked both as exact match
# (``final in _TW_BOILERPLATE_TERMS``) and as a prefix
# (``final.startswith(phrase)``) so walker captures like 如請求項4至請求項10
# are also filtered.
_TW_BOILERPLATE_TERMS: frozenset[str] = frozenset({
    "複數",
    "多個",
    "多數",
    "前述",
    "上述",
    "如上所述",
    "如請求項",
    # R67 (2026-05-08) - method-claim listing boilerplate. `下列步驟` /
    # `下列方法` / `下列特徵` are universal "the following <X>" patterns
    # that introduce a list, not a noun being claimed. Walker captures
    # them via the main intro pattern from `其包含下列步驟：...`.
    "下列步驟",
    "下列方法",
    "下列特徵",
    # Reported via issue #44: 如請求項X至Y中任一項所記載 dependency
    # boilerplate. `如請求項` prefix is already filtered, but the walker
    # tokenization sometimes yields the residue `項所記載` (or the
    # 所-less variant `項記載`) as a standalone term. Both are
    # spec-support boilerplate, not a referable noun phrase.
    "項所記載",
    "項記載",
    # #334 - distributive quantifiers 每個 / 每一 ("each one"). Prefix-matched
    # (_is_boilerplate), so the bare residue AND a 每個X / 每一X back-reference
    # compound drop; the real head noun is separately inventoried via its own
    # 一X intro, so this cannot silence a genuine §26第3項 finding.
    "每個",
    "每一",
})

# Trailing clause tokens observed in audit as walker-captured verbal tails
# that ``clean_noun_phrase_tw`` (walker close-out tuned for antecedent
# matching, not spec-support) doesn't strip. Applied iteratively
# (longest-first) after the walker normalizer so 間距介於 → 間距,
# 最低點位於 → 最低點, 第一凹槽彼此間隔地設 → 第一凹槽.
_TW_SPEC_SUPPORT_TRAILING_TOKENS: tuple[str, ...] = tuple(sorted(
    (
        "彼此間隔地設",
        "可向下方移動",
        "共同形",
        "介於",
        "位於",
        "地設",
        "所開",
        "選擇",
        "移動",
        "樞接",
        "超過",
        # R7 trailing comparison verbs - mirror of 超過 (exceeds).
        # Issues #106 (`有通道寬度大於`), #108 (`通道寬度大於`),
        # #130 (`寬度小於`), #133 (`最大外徑大於`) - `大於`/`小於`
        # are unambiguous comparison verbs in TIPO drafting, never
        # noun-phrase termini. 專利法 §26 第3項 spec-support is for
        # noun phrases only.
        "大於",
        "小於",
        # #343 - `達成` (achieve/accomplish), a predicate verb never a noun
        # terminus. 2-char, so (key=len desc) it is tried before the 1-char
        # `成`, which would otherwise leave the residual `導電材料達`.
        "達成",
        # R10 (2026-06-01): trailing process / locative verbs from issues
        # #111 (`主面側蝕刻` → strip `蝕刻`) and #129 (`位部沿` → strip `沿`).
        # 蝕刻 (etching) is a process verb, 沿 is a locative preposition
        # ("along") - neither is a noun-phrase terminus in TIPO drafting.
        # Anti-corpus checked: zero baseline findings on _spec_support_harness
        # end with either token.
        "蝕刻",
        "沿",
        # R34 (#440) - `相鄰` ("adjacent to", a mutual-relation verb) trailing
        # tail (第二次級繞組層相鄰設置 → 第二次級繞組層相鄰 after 設置 strip → strip
        # 相鄰). 2-char, tried before the 1-char `相` (which only fires when the
        # term ends in a bare `相`). FN-safe: no TIPO element name ends in 相鄰
        # (a positional element carries 相鄰區/相鄰面 ending in 區/面).
        "相鄰",
        "相",
        "形",
        "時",
        "連",
        "設",
        # R63 (2026-05-05): garbage patterns surfaced via 神秘黑屏哥.docx
        # method-claim audit. Walker over-captures process descriptions
        # and locative phrases as "intros" then spec-support inventories
        # them as "missing from spec":
        # - `而成` - process-result marker (`X部分而成` = "after X");
        #   never a noun. Strips `膜減少部分而成` → `膜減少部分`.
        # - `部分而成` - longer variant; same pattern.
        # - `面側` - locative-side suffix (`露出面側` = "exposed face side").
        #   Strips to leave residual `露出` which then fails leading reject.
        "部分而成",
        # 2026-06-01 - issue #110. Drafter wrote `膜厚而成膜` (film
        # thickness, formed by depositing film). Walker captured the
        # whole thing because the existing `而成` trailing-token doesn't
        # fire when extra chars follow (`而成` is interior here, not
        # trailing). Adding `而成膜` as a specific 4-char trailing token
        # strips the verb-phrase tail cleanly → `膜厚`.
        "而成膜",
        "而成",
        "面側",
        # R67 (2026-05-08): walker over-capture truncated at ordinal-prefix
        # `第` without the trailing ordinal number. Drafter wrote
        # `相配合的第1散熱片` but the F-head/post-process path captured up
        # to `相配合的第` (digit `1` outside _NOUN_CHARS class). Bare `第`
        # at the END of a captured term is always a truncated ordinal -
        # 第 alone is never a legitimate noun-phrase terminus.
        "的第",
        "第",
        # Reported via issue #45: trailing 以 captured into the noun phrase
        # at clause boundaries (`第二狀態以進行調整` → walker captures
        # `第二狀態以` before the next-clause-introducing 進行). `以` here
        # is the verbal connector "in order to / by way of", never a
        # noun-phrase terminus in TIPO drafting. Single-char, applied
        # last in the longest-first iteration order.
        "以",
        # Issues #77 / #69 (2026-05-21): method-claim over-capture.
        # - `各` - distributive quantifier ("each"); `電壓各到達門檻` →
        #   walker captures `電壓各`. `各` is never a noun terminus; strip
        #   leaves the clean head noun `電壓`.
        # - `減薄` - process verb ("thin / reduce"); `兩端減薄` is a
        #   predicate clause, never an element name.
        "減薄",
        "各",
        # 2026-06-01 - issues #109 (`下部成` → strip `成`) and #132
        # (`軸上` → strip `上`). 成 = formation verb suffix
        # (`形成`/`構成`/`組成`); 上 = locative preposition ("on/above").
        # Both are single-char clause-boundary tokens that never form
        # the noun-phrase head in TIPO drafting. Anti-corpus checked:
        # zero spec_support_baseline findings end with either token.
        # Trailing tokens iterate longest-first, so 成 / 上 only fire
        # as standalone trailing strips (won't break 成膜/上方-style
        # interior matches because those are part of longer compounds).
        "成",
        "上",
        # 2026-06-01 - cross-jurisdiction parity with CN spec_support
        # (CN PR #181 added 抵靠 / 穿设 / 穿過 / 分别穿过 from real CN
        # reports #174 / #175 / #176). All four are Traditional-form-
        # compatible perforation / abutment verbs commonly used in
        # mechanical TIPO drafting; risk audit shows none appear as
        # noun-suffix in TIPO patent diction (抵靠 is purely "abut
        # against"; 穿設 / 穿過 are perforation verbs; 分別穿過 is the
        # respectively-quantified verb phrase). Cross-jurisdiction
        # parity per standing instruction - TW corpus doesn't have a
        # current report of this exact class, but generalizing now
        # closes the gap before it surfaces.
        "分別穿過",
        "穿設",
        "穿過",
        "抵靠",
        # 2026-06-05 batch (battery-pack / JP-translated mechanical drafts,
        # report queue #187 / #193 / #194). Trailing verbal / adverbial
        # tails the walker over-captured past the head noun:
        # - `共同地` / `可通訊地` - manner adverbs (X + 地 adverbial particle);
        #   never noun termini (`夾持部共同地` → `夾持部`, `檢體採集支援系統
        #   可通訊地` → `檢體採集支援系統`, which then matches the spec via
        #   substring even with an embedded reference numeral). Multi-char
        #   so they only fire on the exact adverb, not on any noun ending
        #   in 地 (土地/基地/場地 stay inventoried).
        # - `緊靠` - abutment verb, same family as the existing `抵靠`
        #   (`夾持部緊靠` → `夾持部`). Fires only when the term ENDS in 緊靠
        #   (verb usage); a real `緊靠部`/`緊靠面` noun ends in 部/面 and is
        #   untouched.
        # - `不平行` - negation + adjective predicate (`第一外側壁不平行` →
        #   `第一外側壁`); never a noun's name.
        # CN (Simplified) mirror deferred per DR-1 - no CN report of these
        # tokens yet; CN↔TW spec-support mirroring has been report-driven
        # in both directions (CN #174/#175/#176 → TW 抵靠/穿設/穿過).
        "可通訊地",
        "共同地",
        "不平行",
        "緊靠",
        # 2026-06-29 batch (super-sonic transducer draft, report #302/#303/
        # #304). Trailing tails the walker over-captured past the head noun
        # in 透過一<noun>電性連接 / X與Y之間 clauses:
        # - `電性` - the leading bound morpheme of the verb phrase 電性連接
        #   ("electrically connect") / 電性耦接; the walker stops at 電性
        #   before the excluded 連 (`導電膠體電性` → `導電膠體`,
        #   `另一導電膠體電性` → `另一導電膠體`). 電性 is never a noun-phrase
        #   terminus in TIPO drafting - a conductivity noun is 導電性
        #   (導電+性), not a bare trailing 電性. Anti-corpus: zero
        #   spec_support_baseline phrases end in or contain 電性.
        # - `之間` - locative postposition ("between"); `第二表面之間` →
        #   `第二表面`. Never a noun terminus. Anti-corpus clean.
        # `部分` (#305 `延伸部部分`) is handled by the verb-gated strip in
        # _build_inventory (NOT here) - a real `X部分` portion-element would
        # FN-drop in a blanket trailing strip; the FN-safe discriminator is
        # the FOLLOWING verb (部分延伸 = "partly extends"), visible only with
        # claim context.
        "電性",
        "之間",
        # 2026-06-29 (report #294) - `的<positional-generic>` possessive tail.
        # `壓電材料層的周邊` → `壓電材料層` (環繞該壓電材料層的周邊 = "surround
        # the periphery of the piezo layer"; the element is 壓電材料層, 周邊 is
        # a generic position). 的+{周邊/周圍/外圍/邊緣/周緣/周側} are possessive
        # + generic-positional nouns - never the claimed element themselves.
        # Conservative: only the clearly-positional generics (NOT 的表面/的底部
        # which can be claimed sub-elements). Anti-corpus: 0/77 baseline.
        "的周邊", "的周圍", "的外圍", "的邊緣", "的周緣", "的周側",
        # 2026-07-01 (#315): 的末端 - possessive + positional generic ("the end
        # of X"; 鎖定部的末端 → 鎖定部). 末端 is a location point, never the
        # claimed element itself (those carry 端部/端子). Anti-corpus 0/77.
        # `的外表面` (#317) NOT added - a surface can be a claimed structural
        # element; deferred as a maintainer call.
        "的末端",
        # 2026-06-30 batch (screen-bracket draft, reports #314/#317). FN-safe
        # subset of the over-capture cluster:
        # - `連通於` / `固定於` - verb+於 predicate phrases (`外側且連通於`→外側,
        #   `有固定於`→ dropped as <2-char noise). Never a noun-phrase terminus.
        # - `且` - the conjunction "and/also" (`外側且` → 外側). Never ends an
        #   element name; mirror of the existing 及/與/和 conjunction handling.
        # Anti-corpus: 0/77 baseline end in any. The rest of the cluster
        # (鄰近/轉動 noun-gray, 受/自/排 single-char needing residual guards,
        # 的末端/的外表面 possessive, 有/桿定 leading-clause) is FN-delicate →
        # queued for a TW spec-support /walker-round (#315/#318/#319 + residuals).
        "連通於", "固定於", "且",
        # 2026-07-01 (#315): 分別 ("respectively/separately") is a pure manner
        # adverb - never an element-name terminus. Anti-corpus 0/77. (The verb
        # it modifies - 鄰近 etc. - is stripped first by the predicate verb-gate
        # in _build_inventory, leaving 坡面分別 → strip 分別 here → 坡面.)
        "分別",
    ),
    key=len,
    reverse=True,
))

# Leading verbal prefixes observed in audit. Multi-char sequences only -
# single-char leads like 有/為 appear in legitimate compound nouns
# (有機/為主) and can't be blanket-rejected without FN risk.
_TW_SPEC_SUPPORT_LEADING_REJECTS: tuple[str, ...] = (
    "有多",
    "有一",
    "為可",
    "以控",
    "以從",
    "經選",
    "個所",
    "完所",
    "至該",
    "顯示",
    "描述",
    "解鎖",
    "對該",
    # R63 (2026-05-05) - verb-prefix walker captures from method claims
    # (神秘黑屏哥.docx audit). These are verbs that walker captured as
    # noun heads. Each is multi-char so unlike `有/為` they won't risk
    # blanket-rejecting valid compound nouns starting with the same char.
    # Risk audit: 露出部 (exposed part) is a valid noun - but `露出部` is
    # 3 chars, walker normalize would NOT yield bare `露出` (2 chars,
    # leading-reject below MIN length). So rejecting startswith("露出")
    # only fires on `露出X` where X is the over-capture continuation,
    # which by audit are all process descriptors not element names.
    "露出",        # walker over-capture of process verb
    "膜減少",     # film-reduction process (verb compound)
    "回蝕",        # etch-back process verb
    # Issues #69 / #78 (2026-05-21):
    # - `介由` - prepositional connector ("by way of / using");
    #   `介由使用半導體材料的犧牲膜` over-captured as an intro.
    # - `中一` - stranded `其中一(個)` connective fragment; the walker
    #   dropped the leading `其`, leaving `中一個`. `中一` never leads a
    #   real TIPO noun (中央/中心 do not start `中一`).
    "介由",
    "中一",
    # 2026-06-05 - issue #194. `其中兩個` with the leading `其` dropped by
    # the walker leaves `中兩個` (`相鄰的其中兩個第二外側壁` → walker captured
    # `中兩個`). Mirror of `中一` above - `中兩` never leads a real TIPO noun
    # (中央/中心 do not start `中兩`).
    "中兩",
    # 2026-06-11 - issue #246 (JP-translated 對位裝置 draft). `朝往` is an
    # adverb ("toward / heading to"), captured standalone from
    # `朝往前述基板吸引前述光罩的吸引機構`. Never a noun; no real TIPO noun
    # starts `朝往` (朝向角度 starts 朝向, not 朝往).
    "朝往",
    # 2026-07 batch:
    # - #333 `另外` - adverb/determiner ("besides / the other"), captured
    #   standalone (`另外兩個`). Never leads a TIPO element name; the real head
    #   noun is separately inventoried.
    # - #348 `以向` - 以-purpose + 向-coverb clause fragment (`以向一水體樣本`),
    #   mirror of the existing 以控 / 以從. FN-safe: 以太網路 (Ethernet, 以太…)
    #   and 向量 (vector, 向…) are unaffected - the reject is the 2-char lead.
    "另外",
    "以向",
)

# Characters that appear ONLY as noun suffixes in TW patent diction
# (開口部, 頂端, 端面, USB埠). When one appears at position 0 of a
# normalized term, the walker captured a fragment starting mid-compound.
# Reject these single-char leads.
_TW_SUFFIX_ONLY_LEADS: frozenset[str] = frozenset({"部", "端", "埠"})

# Clause markers that signal the captured text is a comparison/relation
# clause, not a noun phrase. Reject any term containing these as an
# interior substring.
# R67 (2026-05-08): added `相配合` (mutually-fitting). Verb-phrase
# describing inter-component relationship, never part of a noun's name
# in TIPO drafting. Walker over-capture from
# `與前述X相配合的第N<NOUN>` (F-head supplementary) leaks `X相配合`
# residue after trailing-strip; interior reject closes the loop.
_TW_SPEC_SUPPORT_INTERIOR_REJECTS: tuple[str, ...] = (
    "超過",
    "超出",
    "彼此",
    # `相配` covers the verb-phrase root: 相配合 / 相配對 / 相配置 are
    # all relational verbs, never part of a noun's name in TIPO drafting.
    # Walker over-captures from `與X相配合的Y` shapes that survive
    # trailing-token stripping because the 合/對/置 suffix may be
    # truncated mid-capture.
    "相配",
    # Issue #76 (2026-05-21): a coupling/connection verb taking an
    # indefinite object (`<verb>一<NOUN>`) is a relational predicate,
    # never a noun's name - `第一端耦接一輸入電壓` over-captured whole.
    # Gated on the `一` so a real noun compound (耦接器 / 連接部) whose
    # verb root is NOT followed by `一` stays inventoried.
    "耦接一",
    "耦合一",
    "連接一",
    "連結一",
    # 2026-06-11 - issue #248. `面且互相正交` is a predicate clause
    # ("...face, and mutually orthogonal..."); `互相` ("mutually") is an
    # adverb, never part of a noun's name. 互鎖 / 相互 are different
    # 2-char sequences, so a noun like 互鎖機構 / 相互作用 is unaffected.
    "互相",
)

# Leading prepositions that survive walker normalization (audit #2 found
# 於所述基板 / 到所述第一電子裝置 / 在X 等 as residues). Strip these
# claim-side before the Tier 1 exact check. Spec-side text is unchanged -
# "使用者介面" as a claim term should match both bare "使用者介面" in
# spec and "於該使用者介面上" in spec.
_TW_LEADING_PREPOSITIONS: tuple[str, ...] = ("於", "到", "在", "自", "由")

# Trailing parenthetical reference numerals per 專利法施行細則 §19 - drafters
# inline element numerals like 容器本體(100), 第一長度(L1), 栓軸部(2212a)
# directly in claim intros. These break exact-match against spec text where
# the component is either bare (容器本體) or uses a different numeral
# notation. Strip both full-width and half-width parens, with alnum / dash /
# CJK dash inside.
_TRAILING_REF_NUMERAL_RE = re.compile(r"[（(][\w\d\-—–]+[）)]\s*$")

# Coordinating conjunctions that signal a walker-captured phrase spanning
# multiple nouns. When an intro matches `X <conj> Y` shape, both X and Y
# are enrolled as separate inventory entries (the drafter likely
# introduced them as co-ordinate elements).
_TW_CONJUNCTIONS: tuple[str, ...] = ("以及", "及", "與", "和")

# Sliding-window size (in CJK characters) for Tier 3 proximity matching.
# Chinese noun phrases are typically 2-4 chars; ±30 spans ~5-8 clauses of
# context, matching the granularity at which a drafter would reasonably
# declare support for a compound term.
_CHAR_WINDOW_SIZE: int = 30

# Minimum bare-noun length for a term to enter the inventory. Filters
# single-char residues like capture artifacts. Two chars is the floor
# for meaningful Chinese noun phrases.
_MIN_INVENTORY_LENGTH: int = 2

# Maximum length (chars) for an inventory term. Captures beyond this
# length are almost always walker clause artifacts (e.g.
# ``應用程式上設定其他該行動裝置或帳號``, 17 chars) rather than genuine
# compound nouns. 12 chars is ~4-6 Chinese morphemes - long enough for
# legitimate compound terms (第二外齒狀結構 = 7; 帶蓋容器 = 4) and short
# enough to reject full clauses. Findings longer than this are silently
# dropped from the inventory rather than emitted (the walker's antecedent
# check will catch semantic issues; spec-support is a clarity/support
# proxy, not a clause-level coverage check).
_MAX_INVENTORY_LENGTH: int = 12


# --- Normalization helpers -------------------------------------------------


def _normalize_for_spec_support_tw(text: str) -> str:
    """Normalize a claim-side term for spec-support matching.

    Order:
        1. Strip trailing parenthetical reference numeral 專利法施行細則 §19
           (容器本體(100) → 容器本體).
        2. Strip leading preposition (於/到/在/自/由).
        3. Run the walker normalizer (strip reference-form prefix +
           qualifier + quantifier + clean_noun_phrase_tw).

    Spec-side text is NOT normalized - the match is asymmetric, so
    "使用者介面" (claim) matches both "使用者介面" (bare) and
    "該使用者介面" (prefixed) in the spec.
    """
    if not text:
        return text
    t = _TRAILING_REF_NUMERAL_RE.sub("", text).strip()
    for prep in _TW_LEADING_PREPOSITIONS:
        if t.startswith(prep) and len(t) > len(prep):
            t = t[len(prep):]
            break
    # #344 - leading method-step verb 提供一X / 設置一X: drop the verb so the
    # 一-quantifier normalizer below recovers the head noun (提供一導線框架 →
    # 導線框架). Gated on the following 一 (the indefinite-article intro marker)
    # so the coverb 設置於 (→於) and genuine nouns 設置面 / 提供者 are untouched.
    # The head noun is independently inventoried via its own 一X intro, so this
    # only removes a redundant duplicate entry - zero coverage loss.
    for verb in ("提供", "設置"):
        if t.startswith(verb + "一") and len(t) > len(verb):
            t = t[len(verb):]
            break
    # R34 (#439/#442) - leading transitional verb 包括/包含 ("comprising/
    # including"), a 連接詞 per TIPO §2.3.3 and never part of a noun's name. A
    # sub-element enumeration `一磁芯，包括一第一平板` over-captures the transition
    # into the term. Strip it so the 一-quantifier normalizer below recovers the
    # head noun (包括一第一平板 → 第一平板); the head is independently inventoried
    # via its own 一X intro, so this only removes a redundant duplicate (zero
    # coverage loss). FN-safe: a real element name never opens with the 2-char
    # 包括/包含 (包覆層 cladding-layer / 包裝 packaging start with 包 but not these).
    for verb in ("包括", "包含"):
        if t.startswith(verb) and len(t) > len(verb):
            t = t[len(verb):]
            break
    t = normalize_reference_term(t)
    # #351 - strip a leading reference marker that survived normalize (a leading
    # distributive quantifier can block the position-0 reference-form strip,
    # stranding 所述 / 該 / 前述). A noun name never opens with a reference marker.
    for pfx in ("前述", "所述", "該"):
        if t.startswith(pfx) and len(t) > len(pfx):
            t = t[len(pfx):]
            break
    # #342 (1) - de-yi possessive: X的一Y → Y (the head noun after 的一). The
    # walker over-captured the possessor + 的一; the claimed element is Y. Only
    # exposes the real head - if Y were truly unsupported it would still flag.
    if "的一" in t:
        suffix = t.rsplit("的一", 1)[1].strip()
        if len(suffix) >= _MIN_INVENTORY_LENGTH:
            t = normalize_reference_term(suffix)
    t = _recover_from_midphrase_prefix(t)
    t = _strip_trailing_locative_clause(t)
    t = _strip_trailing_conjunction(t)
    t = _strip_spec_support_trailing_tokens(t)
    # #321 - re-run the trailing-conjunction strip AFTER the trailing-token
    # strip: a token strip can remove an intervening predicate/preposition
    # (位於) and re-expose a dangling coordinating conjunction (鎖定部及位於 →
    # 鎖定部及) that the earlier pass could not reach. Collapses 鎖定部及 → 鎖定部,
    # which dedups against the head-noun entry already in the inventory.
    t = _strip_trailing_conjunction(t)
    # Re-strip trailing numerals exposed by the verb strip
    # (栓軸部(2212a)樞接 → 栓軸部(2212a) after 樞接 strip, now the paren
    # is at end and can be removed).
    t = _TRAILING_REF_NUMERAL_RE.sub("", t).strip()
    # #342 (2) - trailing cardinal measure: X<cardinal>個 → X (垂直堆疊晶粒組二個
    # → 垂直堆疊晶粒組). A measure-word count is never part of an element name.
    # Guarded so the head remains an inventory-length noun (spares 整個/十字…
    # which do not end in <cardinal>個).
    measure_stripped = re.sub(r"[一二兩三四五六七八九十]+個$", "", t)
    if measure_stripped != t and len(measure_stripped) >= _MIN_INVENTORY_LENGTH:
        t = measure_stripped
    return t


def _strip_spec_support_trailing_tokens(term: str) -> str:
    """Iteratively strip trailing clause tokens (longest-first)."""
    for _ in range(8):
        stripped = False
        for token in _TW_SPEC_SUPPORT_TRAILING_TOKENS:
            if term.endswith(token) and len(term) > len(token):
                term = term[: -len(token)]
                stripped = True
                break
        if not stripped:
            break
    return term


def _has_leading_reject(term: str) -> bool:
    """True if the term starts with a known verbal/clause-fragment prefix."""
    if not term:
        return False
    if term[0] in _TW_SUFFIX_ONLY_LEADS:
        return True
    return any(term.startswith(p) for p in _TW_SPEC_SUPPORT_LEADING_REJECTS)


def _has_interior_reject(term: str) -> bool:
    """True if the term contains a clause marker (comparison/relation)."""
    return any(marker in term for marker in _TW_SPEC_SUPPORT_INTERIOR_REJECTS)


def _is_boilerplate(term: str) -> bool:
    """True if term matches a boilerplate phrase exactly or as a prefix.

    Substring check catches walker-captured extensions of boilerplate
    phrases (如請求項4至請求項10 starts with 如請求項).
    """
    if term in _TW_BOILERPLATE_TERMS:
        return True
    return any(term.startswith(phrase) for phrase in _TW_BOILERPLATE_TERMS)


def _recover_from_midphrase_prefix(term: str) -> str:
    """Recover a clean noun from a walker-captured phrase with stranded
    reference-form prefix in the middle.

    Walker captures sometimes land with 所述/該/前述 at an interior
    position (e.g. 有所述高亮度區域, 個所述電子元件, 解鎖指令至該通訊模組).
    The walker's leading-prefix strip can't help these - it only looks at
    position 0. Here we split at the LAST occurrence of a reference-form
    prefix and take the suffix (the noun that was being referenced).

    Longest-prefix first so 前述 matches before 述. Position 0 matches
    are ignored (already handled upstream by
    ``strip_reference_form_prefix``).
    """
    for prefix in ("前述", "所述", "該"):
        idx = term.rfind(prefix)
        if idx > 0:
            suffix = term[idx + len(prefix):].strip()
            if suffix and len(suffix) >= _MIN_INVENTORY_LENGTH:
                return normalize_reference_term(suffix)
    return term


def _strip_trailing_conjunction(term: str) -> str:
    """Strip a dangling trailing conjunction (X與, X及, X以及).

    Walker captures sometimes end on a conjunction when the following
    clause boundary confused the intro pattern. ``顏色與`` → ``顏色``.
    """
    for conj in _TW_CONJUNCTIONS:
        if term.endswith(conj) and len(term) > len(conj):
            return term[:-len(conj)]
    return term


# R34 (#443) - determiners that open a trailing locative predicate after an
# interior preposition 於/在. A noun's name never contains 於一/於該/在一/在該…;
# such a span is always the locative clause `於一次側` / `在該表面上`.
_TW_LOCATIVE_CLAUSE_DETERMINERS: frozenset[str] = frozenset(
    {"一", "該", "其", "前", "所", "此", "各"}
)


def _strip_trailing_locative_clause(term: str) -> str:
    """Strip a trailing interior-locative clause `X於<det>…` / `X在<det>…`.

    (#443: 第二電源轉換器於一次側 → 第二電源轉換器.) An interior 於/在 followed
    by a determiner/quantifier opens a locative predicate, never continues a
    noun's name, so everything from the preposition is clause tail. Gated on the
    head before the preposition being inventory-length so a leading-preposition
    residue (位於一表面 → 位, sub-_MIN) is left for the length filter, not emitted.
    """
    for prep in ("於", "在"):
        idx = term.find(prep)
        if (
            idx >= _MIN_INVENTORY_LENGTH
            and idx + len(prep) < len(term)
            and term[idx + len(prep)] in _TW_LOCATIVE_CLAUSE_DETERMINERS
        ):
            return term[:idx]
    return term


# #350 - bare quantifiers that, on the right of a conjunction with no noun
# after them, mark a walker-over-captured clause boundary (X 及 一個).
_TW_BARE_QUANTIFIERS: frozenset[str] = frozenset({
    "一", "一個", "一種", "一對", "兩", "二", "兩個",
    "複數", "複數個", "多個", "若干", "一些", "各", "至少一",
})


def _split_on_conjunction(term: str) -> list[str]:
    """Split a walker-captured conjunction phrase into constituent nouns.

    When a normalized intro spans ``X <conj> Y``, returns [X, Y]; for
    multi-conjunction phrases (``A及B以及C``) both sides are recursively
    split so the result is [A, B, C]. Only splits if BOTH sides are at
    least ``_MIN_INVENTORY_LENGTH`` chars - protects compound nouns that
    happen to contain 及/和 as morphemes (rare in TW patent diction but
    possible).

    The recursion is length-bounded: each split reduces term length, and
    the base case returns [term] unchanged when no qualifying conjunction
    is found.
    """
    for conj in _TW_CONJUNCTIONS:
        idx = term.find(conj)
        if idx < 0:
            continue
        left = term[:idx].strip()
        raw_right = term[idx + len(conj):].strip()
        # Right side may carry a leading quantifier (一/複數/一個) that the
        # walker preserved because it started mid-phrase. Re-normalize.
        right = normalize_reference_term(raw_right) if raw_right else raw_right
        if len(left) >= _MIN_INVENTORY_LENGTH and len(right) >= _MIN_INVENTORY_LENGTH:
            return _split_on_conjunction(left) + _split_on_conjunction(right)
        # R34 (#441) - stranded SHORT left fragment: `區及一第二次級繞組` - the
        # walker stripped the verb `設置` from the element name `設置區`, stranding
        # a bare `區` before the coordinating `及`. A sub-_MIN left can never be a
        # real inventory term (the ≥2-char floor drops it regardless), so keep the
        # clean right noun. Mirror of #350 (which drops a stranded short RIGHT
        # quantifier); FN-safe because dropping a 1-char left loses no inventoriable
        # term while recovering the coordinate noun the drafter actually wrote.
        if len(right) >= _MIN_INVENTORY_LENGTH and 0 < len(left) < _MIN_INVENTORY_LENGTH:
            return _split_on_conjunction(right)
        # #350 - stranded leading-quantifier tail: `X及一個` / `X與複數` - the
        # walker over-captured a clause boundary, leaving a bare quantifier with
        # no noun on the right. Keep the left noun, drop the tail. Gated on an
        # EXACT bare-quantifier set (NOT a blanket right<MIN test): a short
        # non-quantifier residue like `組件及A` (model letter) must stay whole.
        if len(left) >= _MIN_INVENTORY_LENGTH and raw_right in _TW_BARE_QUANTIFIERS:
            return _split_on_conjunction(left)
    return [term]


def _collect_symbol_names(doc: TwPatentDocument) -> set[str]:
    """Return the union of symbol-table glossary names.

    Per the 2026-04-21 note: ``symbol_table`` is the general 符號說明
    glossary; ``representative_drawing_symbols`` is the 代表圖之符號說明
    cover-page legend. Both are drafter-authored glossary declarations -
    terms listed there are spec-supported by definition.

    R67 (2026-05-08) - Arabic→CJK ordinal normalization applied
    symmetrically with the claim-side normalize chain. Drafter writes
    `第1間隔件` in the symbol table; claim-side `normalize_reference_term`
    converts the dep claim's `前述第二間隔件` to `第一間隔件` / `第二間隔件`
    (CJK). Without the symbol-side normalize, Tier 0 missed every
    Arabic-ordinal-named symbol entry - symmetric to R63's walker fix
    on the supplementary-intro path.
    """
    names: set[str] = set()
    for entry in doc.symbol_table:
        if entry.name:
            names.add(normalize_arabic_ordinal_to_cjk(entry.name))
    for entry in doc.representative_drawing_symbols:
        if entry.name:
            names.add(normalize_arabic_ordinal_to_cjk(entry.name))
    return names


def _collect_spec_text(doc: TwPatentDocument) -> str:
    """Concatenate the body subsections used for spec-support matching.

    Per §2.1 of the plan: technical_field + prior_art + disclosure +
    embodiment. Excludes drawings_description + symbol_table (handled
    separately) + abstract_text.

    R67 (2026-05-08) - Arabic→CJK ordinal normalization applied so the
    Tier 1 / Tier 3 substring checks see the same ordinal form the
    claim-side normalize produces. Without this, drafter's `第1散熱片`
    in spec body misses against claim's normalized `第一散熱片`.
    """
    parts: list[str] = []
    parts.extend(doc.technical_field)
    parts.extend(doc.prior_art)
    parts.extend(doc.disclosure)
    parts.extend(doc.embodiment)
    return normalize_arabic_ordinal_to_cjk("\n".join(parts))


# Content verbs that commonly follow the adverbial 部分 ("partly V"). When a
# captured span ending in 部分 is immediately followed by one of these in the
# claim text, the 部分 is the adverb, not a "portion" noun, so the head noun
# ends before it. Position/motion/formation verbs from TIPO claim diction.
_BUFEN_FOLLOWING_VERBS: tuple[str, ...] = (
    "延伸", "延展", "覆蓋", "包覆", "包圍", "圍繞", "環繞", "突出", "凸出",
    "伸出", "重疊", "交疊", "暴露", "外露", "露出", "貼附", "抵接", "抵靠",
    "嵌入", "穿過", "穿設", "凹陷", "凸起", "顯露", "夾持", "插入",
)


def _strip_trailing_bufen_before_verb(term: str, claim_text: str) -> str:
    """Strip a trailing adverbial 部分 when the claim text shows 部分 + verb.

    `延伸部部分延伸至…` → the captured `延伸部部分` is `延伸部` (head) + adverbial
    `部分` ("partly") before the verb `延伸`. FN-safe by the verb-gate: a genuine
    `X部分` portion-element (第二外殼部分, 最外側部分) is followed in the claim by a
    particle / noun / clause-end, not a verb, so it is left intact. (#292/#305.)
    """
    if not term or not term.endswith("部分") or len(term) <= 3:
        return term
    pos = claim_text.find(term)
    if pos < 0:
        return term
    after = claim_text[pos + len(term):]
    if any(after.startswith(v) for v in _BUFEN_FOLLOWING_VERBS):
        return term[:-2]
    return term


# Gray predicate tokens (noun OR verb/coverb) that over-capture into the
# spec-support inventory when used verbally (#315/#317/#318/#319: 阻力墊片受…,
# 位置轉動至…, 坡面…鄰近於…, 局部自…). A blanket strip would FN-drop a real
# `X轉動` / `各自` noun, so we strip ONLY when the claim continues with a
# preposition / coverb / 所述-reference - the unambiguous verbal signature.
# A genuine noun ending in one of these is followed by a particle (的/，/。)
# or another noun, never these markers, so it is left intact.
# #335 - 內凹 ("recessed inward") is a stative verb in `…第二擋牆內凹形成`
# ("formed by … being recessed inward"), not part of the noun phrase.
_TW_PREDICATE_TAILS: tuple[str, ...] = ("轉動", "鄰近", "連通", "內凹", "受", "自")
_TW_PREDICATE_FOLLOW_MARKERS: tuple[str, ...] = (
    "至", "於", "到", "向", "在", "沿", "所述", "該", "予", "與", "和",
)
# #335 - formation verbs. A trailing predicate tail followed by one of these is
# verbal (`…內凹形成` = "formed by being recessed"). Kept as a dedicated tuple
# (not merged into the preposition/coverb markers) to bound the strip's reach.
_TW_FORMATION_FOLLOW_MARKERS: tuple[str, ...] = ("形成", "而成", "構成")


def _strip_trailing_predicate_before_marker(term: str, claim_text: str) -> str:
    """Strip a trailing gray predicate token when the claim continues with a
    preposition / coverb / formation marker (the verbal signature). Iterative so
    a stacked `坡面…鄰近` (then `分別` via the plain trailing strip) fully unwinds.
    FN-safe: a nominal `馬達轉動的` / `各自的` / `X內凹的` is followed by 的, not a
    marker.
    """
    markers = _TW_PREDICATE_FOLLOW_MARKERS + _TW_FORMATION_FOLLOW_MARKERS
    for _ in range(4):
        if not claim_text:
            break
        hit = next((t for t in _TW_PREDICATE_TAILS if term.endswith(t)), None)
        if hit is None or len(term) - len(hit) < 2:
            break
        pos = claim_text.find(term)
        if pos < 0:
            break
        after = claim_text[pos + len(term):]
        if not any(after.startswith(m) for m in markers):
            break
        term = term[: -len(hit)]
    return term


def _build_inventory(claims: list[Claim]) -> list[tuple[str, str]]:
    """Build deduped claim-term inventory from intros across all claims.

    Returns a list of ``(claim_id_proxy, normalized_term)`` pairs where
    claim_id_proxy is the id of the FIRST claim where the term was
    introduced (so an emission reports the original site, not a
    back-reference site).

    Back-references (該X/所述X) point at terms already introduced
    elsewhere; they inherit the intro's spec-support outcome. Orphan
    back-references are flagged by ``check_antecedent_basis`` and
    linked via ``attach_cross_references_tw``.

    Hygiene passes (applied per intro before stoplist + dedup):
      - Parenthetical reference numerals stripped by
        ``_normalize_for_spec_support_tw``
      - Conjunction-bearing captures (X 及 Y) split into [X, Y]
      - Length cap ``_MAX_INVENTORY_LENGTH`` rejects full-clause captures
    """
    seen: dict[str, int] = {}
    inventory: list[tuple[str, str]] = []
    for claim in claims:
        for orig, norm in extract_introductions_tw(
            claim, suppress_dep_preamble=True
        ):
            # 部分 verb-gate (#292/#305): an over-capture ending in 部分 that is
            # immediately FOLLOWED by a content verb in the claim text is the
            # adverbial 部分 ("partly", e.g. 延伸部部分延伸 = "the extension partly
            # extends") - strip it to recover the head noun (延伸部). FN-safe by
            # the verb-gate: a genuine `X部分` portion-element (第二外殼部分,
            # 最外側部分) is followed by a particle/noun/clause-end, NOT a verb,
            # so it is untouched (a blanket trailing strip would FN-drop those).
            orig = _strip_trailing_bufen_before_verb(orig, claim.text)
            norm = _strip_trailing_bufen_before_verb(norm, claim.text)
            # Gray-predicate verb-gate (#315/#317/#318/#319): strip a trailing
            # 受/自/轉動/鄰近/連通 when the claim continues with a preposition/
            # coverb marker (verbal signature); nominal forms (followed by 的)
            # survive.
            orig = _strip_trailing_predicate_before_marker(orig, claim.text)
            norm = _strip_trailing_predicate_before_marker(norm, claim.text)
            # Apply spec-support normalization (adds preposition +
            # parenthetical-numeral strip over the walker's intro
            # normalization).
            root = _normalize_for_spec_support_tw(norm or orig)
            if not root:
                continue
            for final in _split_on_conjunction(root):
                if not final or len(final) < _MIN_INVENTORY_LENGTH:
                    continue
                if len(final) > _MAX_INVENTORY_LENGTH:
                    continue
                if _has_leading_reject(final) or _has_interior_reject(final):
                    continue
                if final in _TW_GENERIC_TERMS or _is_boilerplate(final):
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
    """True if any raw (unnormalized) intro candidate for this term
    appears verbatim in spec_text.

    Catches over-normalization cases where the drafter's literal
    quantifier+noun span (e.g. "一上壁部") appears as-is in the spec
    but the normalized form strips the quantifier and mismatches.
    """
    return any(raw and raw in spec_text for raw in raw_candidates)


def _tier3_char_window(norm_term: str, spec_text: str) -> bool:
    """True if all normalized-term bigrams co-occur within a ±_CHAR_WINDOW_SIZE
    character window somewhere in spec_text.

    Uses ``tokenize_tw`` (ADR-094 bigram contract). For single-char terms
    (tokenize_tw unigram fallback) this degrades to "unigram anywhere in
    spec", which is equivalent to Tier 1 - so Tier 3 adds no false-passes
    for short terms.
    """
    term_tokens = set(tokenize_tw(norm_term))
    if not term_tokens:
        return False
    # Early exit: every bigram must appear somewhere in spec_text at all.
    for tok in term_tokens:
        if tok not in spec_text:
            return False
    # Window scan: find a position where all bigrams occur within
    # ±_CHAR_WINDOW_SIZE chars of each other.
    window = _CHAR_WINDOW_SIZE
    spec_len = len(spec_text)
    if spec_len < window:
        return True  # entire spec shorter than window, all tokens present → match
    for i in range(0, spec_len - window + 1):
        slice_ = spec_text[i:i + window]
        if all(tok in slice_ for tok in term_tokens):
            return True
    return False


# --- Public API ------------------------------------------------------------


def check_spec_support_tw(doc: TwPatentDocument) -> list[UnsupportedTerm]:
    """Check that claim noun phrases have support in the TIPO specification.

    Per 專利法 §26 第3項 + 專利審查基準. Four tiers (see module docstring).

    Emits ``UnsupportedTerm`` only when all tiers fail. The
    ``tiers_checked`` field records which tiers ran, useful for
    downstream diagnostics and A/B measurement of tier contribution.
    """
    if not doc.claims:
        return []

    spec_text = _collect_spec_text(doc)
    symbol_names = _collect_symbol_names(doc)
    inventory = _build_inventory(doc.claims)

    # Pre-collect raw intro candidates per normalized term, so Tier 2 can
    # test every original span that produced this normalized form (one
    # normalized term may come from multiple intros across claims).
    raw_by_norm: dict[str, list[str]] = {}
    for claim in doc.claims:
        for orig, norm in extract_introductions_tw(
            claim, suppress_dep_preamble=True
        ):
            final = _normalize_for_spec_support_tw(norm or orig)
            if not final:
                continue
            raw_by_norm.setdefault(final, []).append(orig)

    unsupported: list[UnsupportedTerm] = []

    for claim_id, norm_term in inventory:
        tiers: list[str] = []

        # Tier 0: symbol-table glossary whitelist
        tiers.append("symbol_table")
        if norm_term in symbol_names:
            continue

        # Tier 1: normalized exact substring
        tiers.append("normalized_exact")
        if _tier1_normalized_exact(norm_term, spec_text):
            continue

        # Tier 2: raw exact substring (any original intro span)
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


def attach_cross_references_tw(
    antecedent_findings: list[dict],
    unsupported_terms: list[UnsupportedTerm],
) -> None:
    """Cross-link TW antecedent and spec-support findings on the same term.

    Supersedes ADR-091's "TW cross_ref expected to remain null" clause
    (now ADR-138). When the same ``(claim_id, normalized_term)`` pair
    appears in both lists, each finding is annotated with a ``cross_ref``
    pointing at the sibling check so the frontend can render a hint line:

    - ``cross_ref="spec_support"`` on antecedent findings → "Also flagged
      in the specification-support review."
    - ``cross_ref="antecedent"`` on spec-support findings → "Also flagged
      in the antecedent-basis review."

    Mutates both lists in place. Matching key is the normalized term
    (walker's ``reference_form`` is already normalized; spec-support
    ``phrase`` is already normalized by ``_normalize_for_spec_support_tw``).
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
