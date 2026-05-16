# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""TW specification-support analysis (說明書支持分析).

Implements 專利法 §26 第3項 ("申請專利範圍…必須為說明書所支持") and the
corresponding 專利審查基準 examination guideline. Mirrors the US §112(a)
``check_spec_support`` at ``analysis/claims.py:998`` but swaps the English
word-window machinery for CJK-appropriate matching (ADR-138).

The check emits an ``UnsupportedTerm`` finding for each claim noun phrase
that fails all four tiers:

  Tier 0 (pre-check): symbol-table whitelist — term appears as a
    ``符號說明`` glossary entry (general table ∪ 代表圖之符號說明).
    Glossary entries are spec-supported by definition.
  Tier 1: aggressively-normalized exact substring — claim-side term
    goes through ``_normalize_for_spec_support_tw`` (walker normalizer
    + leading preposition strip 於/到/在/自/由), then tested as a
    substring of spec_text.
  Tier 2: raw-form exact substring — catches over-normalization cases
    where the drafter's literal claim phrasing (quantifier + noun)
    appears verbatim in the spec.
  Tier 3: CJK character-window fallback — normalized term's bigrams
    must all co-occur within a ±30-char sliding window over spec_text.
    Fires on compound assembly patterns.

Spec_text composition (per §2.1 of the plan): ``technical_field +
prior_art + disclosure + embodiment``. Excludes ``drawings_description``
(figure captions → FP risk), ``symbol_table`` (non-prose, handled in
Tier 0), and ``abstract_text`` (not written-description per 專利審查基準).

The claim-side normalizer is INDEPENDENT of walker-tuning flags
(strict_plural_reference_matching, strict_qualifier_matching). Those
flags tune back-reference matching precision — a different semantic
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
    # R67 (2026-05-08) — method-claim listing boilerplate. `下列步驟` /
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
        "相",
        "形",
        "時",
        "連",
        "設",
        # R63 (2026-05-05): garbage patterns surfaced via 神秘黑屏哥.docx
        # method-claim audit. Walker over-captures process descriptions
        # and locative phrases as "intros" then spec-support inventories
        # them as "missing from spec":
        # - `而成` — process-result marker (`X部分而成` = "after X");
        #   never a noun. Strips `膜減少部分而成` → `膜減少部分`.
        # - `部分而成` — longer variant; same pattern.
        # - `面側` — locative-side suffix (`露出面側` = "exposed face side").
        #   Strips to leave residual `露出` which then fails leading reject.
        "部分而成",
        "而成",
        "面側",
        # R67 (2026-05-08): walker over-capture truncated at ordinal-prefix
        # `第` without the trailing ordinal number. Drafter wrote
        # `相配合的第1散熱片` but the F-head/post-process path captured up
        # to `相配合的第` (digit `1` outside _NOUN_CHARS class). Bare `第`
        # at the END of a captured term is always a truncated ordinal —
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
    ),
    key=len,
    reverse=True,
))

# Leading verbal prefixes observed in audit. Multi-char sequences only —
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
    # R63 (2026-05-05) — verb-prefix walker captures from method claims
    # (神秘黑屏哥.docx audit). These are verbs that walker captured as
    # noun heads. Each is multi-char so unlike `有/為` they won't risk
    # blanket-rejecting valid compound nouns starting with the same char.
    # Risk audit: 露出部 (exposed part) is a valid noun — but `露出部` is
    # 3 chars, walker normalize would NOT yield bare `露出` (2 chars,
    # leading-reject below MIN length). So rejecting startswith("露出")
    # only fires on `露出X` where X is the over-capture continuation,
    # which by audit are all process descriptors not element names.
    "露出",        # walker over-capture of process verb
    "膜減少",     # film-reduction process (verb compound)
    "回蝕",        # etch-back process verb
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
)

# Leading prepositions that survive walker normalization (audit #2 found
# 於所述基板 / 到所述第一電子裝置 / 在X 等 as residues). Strip these
# claim-side before the Tier 1 exact check. Spec-side text is unchanged —
# "使用者介面" as a claim term should match both bare "使用者介面" in
# spec and "於該使用者介面上" in spec.
_TW_LEADING_PREPOSITIONS: tuple[str, ...] = ("於", "到", "在", "自", "由")

# Trailing parenthetical reference numerals per 專利法施行細則 §19 — drafters
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
# compound nouns. 12 chars is ~4-6 Chinese morphemes — long enough for
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

    Spec-side text is NOT normalized — the match is asymmetric, so
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
    t = normalize_reference_term(t)
    t = _recover_from_midphrase_prefix(t)
    t = _strip_trailing_conjunction(t)
    t = _strip_spec_support_trailing_tokens(t)
    # Re-strip trailing numerals exposed by the verb strip
    # (栓軸部(2212a)樞接 → 栓軸部(2212a) after 樞接 strip, now the paren
    # is at end and can be removed).
    t = _TRAILING_REF_NUMERAL_RE.sub("", t).strip()
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
    The walker's leading-prefix strip can't help these — it only looks at
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


def _split_on_conjunction(term: str) -> list[str]:
    """Split a walker-captured conjunction phrase into constituent nouns.

    When a normalized intro spans ``X <conj> Y``, returns [X, Y]; for
    multi-conjunction phrases (``A及B以及C``) both sides are recursively
    split so the result is [A, B, C]. Only splits if BOTH sides are at
    least ``_MIN_INVENTORY_LENGTH`` chars — protects compound nouns that
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
        right = term[idx + len(conj):].strip()
        # Right side may carry a leading quantifier (一/複數/一個) that the
        # walker preserved because it started mid-phrase. Re-normalize.
        right = normalize_reference_term(right) if right else right
        if len(left) >= _MIN_INVENTORY_LENGTH and len(right) >= _MIN_INVENTORY_LENGTH:
            return _split_on_conjunction(left) + _split_on_conjunction(right)
    return [term]


def _collect_symbol_names(doc: TwPatentDocument) -> set[str]:
    """Return the union of symbol-table glossary names.

    Per the 2026-04-21 note: ``symbol_table`` is the general 符號說明
    glossary; ``representative_drawing_symbols`` is the 代表圖之符號說明
    cover-page legend. Both are drafter-authored glossary declarations —
    terms listed there are spec-supported by definition.

    R67 (2026-05-08) — Arabic→CJK ordinal normalization applied
    symmetrically with the claim-side normalize chain. Drafter writes
    `第1間隔件` in the symbol table; claim-side `normalize_reference_term`
    converts the dep claim's `前述第二間隔件` to `第一間隔件` / `第二間隔件`
    (CJK). Without the symbol-side normalize, Tier 0 missed every
    Arabic-ordinal-named symbol entry — symmetric to R63's walker fix
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

    R67 (2026-05-08) — Arabic→CJK ordinal normalization applied so the
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
        for orig, norm in extract_introductions_tw(claim):
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
    spec", which is equivalent to Tier 1 — so Tier 3 adds no false-passes
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
        for orig, norm in extract_introductions_tw(claim):
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
