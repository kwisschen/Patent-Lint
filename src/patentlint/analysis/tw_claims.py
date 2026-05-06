# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""TW claims structural checks.

Sixteen pure functions checking Taiwan patent claim formatting
against TIPO rules (專利法施行細則 and 專利審查基準).
"""

from __future__ import annotations

import re
from typing import Any

from patentlint.analysis.cjk_ordinal_guard import (
    normalize_arabic_ordinal_to_cjk,
    ordinal_guard,
)
from patentlint.analysis.cjk_tokenize import jaccard, tokenize_tw
from patentlint.analysis.utils import (
    _dx,
    compute_confidence_score,
    make_document_dedup_key,
)
from patentlint.analysis.connection_relationships import (
    _TW_CONNECTION_CONFIG,
    check_connection_relationships,
)
from patentlint.models import CheckItem, Claim, TwPatentDocument

# Did-you-mean Jaccard threshold (ADR-094). Char-bigram Jaccard at 0.40
# is the calibration v2 sweet spot: high enough to suppress noise pairs,
# low enough to surface morphological/quantifier variants the exact-match
# pass missed. The threshold is fixed at the analysis layer; the strict-
# plural escape hatch in the walker is the only knob exposed to callers.
_DIDYOUMEAN_THRESHOLD = 0.40

# Phase B3 — DYM quality gate (R21-analog port from CN). Filters noisy
# DYM suggestions the Jaccard loop already picked. Non-shifting: walker
# finding count unchanged; only suggested_match is suppressed.
#
# TW adaptations vs CN list: Traditional character forms + TIPO
# reference-prefix vocabulary (該/所述/前述/該等/該些), classical
# possessive 之 alongside 的 in stop-particle set.
_DYM_LEADING_REJECTS_TW: tuple[str, ...] = (
    "能夠由", "響應於", "針對", "基於",
    "對", "從", "向", "為", "在",
    "與", "和", "以", "於", "且", "還", "由", "被",
    "該", "所述", "前述", "該等", "該些",
)

_DYM_STOP_PARTICLES_TW: tuple[str, ...] = (
    "的", "之",
    "於", "在", "為", "對", "從", "向",
    "與", "和", "以", "且", "還", "由", "被",
    "所述", "前述", "該", "該等", "該些",
    "能夠由", "響應於", "針對", "基於",
    "初始化時", "之前", "之後",
)


# Phase F F3 — emit-suppression sets for walker degenerate captures.
# Silence findings whose normalized term is structurally not a noun
# phrase. The pre-capture cleanup (clean_noun_phrase_tw) leaves these
# fragments behind in edge cases; rather than complicate the cleanup
# chain for each edge case, suppress emission at the walker boundary.
_BARE_QUANTIFIER_TERMS_TW: frozenset[str] = frozenset({
    "複數", "多個", "若干", "一些", "至少一", "至少兩",
    # R32 (2026-05-04): bare quantifier-residue terms that survive
    # leading-strip + interior-cut cascades. Empirically attested in the
    # round-1 1073-TW corpus as walker_fp emissions where the head noun
    # was lost during normalization. None form valid §112 claim terms.
    "個", "兩個", "三個", "四個", "五個", "六個", "七個", "八個", "九個", "十個",
    "或多個", "多", "數", "各",
})

# R32 (2026-05-04): bare-ordinal regex — `第N` with no head noun is a
# residue, never a valid §112 reference. Walker emissions of bare 第一/
# 第二/第三 happen when interior-cut truncates `該第一X` past a digit
# boundary or when leading-quantifier strip hits an ordinal-only intro.
_BARE_ORDINAL_RE_TW: re.Pattern[str] = re.compile(
    r'^第[一二三四五六七八九十百0-9]+$'
)

# R32 (2026-05-04): claim-citation boilerplate filter. TIPO multi-dependent
# claim references like `如前述請求項中任一項所述之X` produce reference
# captures of `前述請求項中任一項`/`前述任一請求項`/etc. that are statutory
# dep-citation phrases, NOT noun terms requiring antecedent. Filter at
# emit boundary; the dep-traversal logic already handles the citation
# correctly via _TW_DEP_RE.
_CLAIM_CITATION_RE_TW: re.Pattern[str] = re.compile(
    r'(?:請求項|任一項|申請專利範圍)'
)

# Walker degenerate 2-char fragments observed in Phase F triage. Add
# entries here only with empirical grounding: observed walker output,
# verified as structurally-invalid NP, compound-noun risk audited.
_WALKER_DEGENERATE_FRAGMENTS_TW: frozenset[str] = frozenset({
    # 測量: observed in tw_dym_edge_cases c4 from 該測量到的溫度感測值.
    # Interior-cut truncated past 到的 boundary leaving 2-char verb
    # fragment. 測量 as a standalone noun appears in TIPO claim drafts
    # only as part of compound 測量值/測量模組 (NOT captured as bare
    # term). Safe to suppress bare 測量 emissions.
    "測量",
    # R68 (2026-05-06) — pure-action verbs surfaced via supplement_v2
    # walker_fp mining. `所述確定` / `所述進行` / `所述獲得` etc. captured
    # when drafter wrote `用於進行X` / `根據Y確定Z` / `所述獲得的W` style
    # claim text — the walker regex stops at 的 (or other boundary) and
    # leaves the bare verb. These verbs are NEVER used as standalone
    # noun antecedents in TIPO claim diction; they appear only as
    # compounds (確定值/獲得結果/進行步驟). Safe-suppress bare emissions.
    # Mining counts (n=8366 TW walker_fp): 確定 ~15, 進行 ~3, 獲得 ~5,
    # 判斷 ~4, 執行 (cited in trailing-pattern), 完成 ~3.
    "確定",
    "進行",
    "獲得",
    "判斷",
    "執行",
    "完成",
})


# Phase B4 — R14f-analog conjunction-split. Final-pass splitter over
# supplementary-intro results so `X和Y` / `X與Y` / `X及Y` / `X以及Y` intros
# register each side as its own intro (≥2 CJK chars on each side).
# TW-adapted: 与 → 與 (Traditional character).
_CONJ_SPLIT_RE_TW: re.Pattern[str] = re.compile(r'(.+?)(?:以及|和|與|及)(.+)')


# Phase C2 F12 — copula intros (Tier A/B/C). Ports CN R14d (6745eef).
# Tier A (unconditional): 轉變為/變為/轉為/劃分為/分為 family.
# Tier B (+ADJ_REJECTS):  基於/來自 family.
# Tier C is omitted in TW port as it routinely over-captures "X為Y" /
# "X是Y" forms that are predicates, not intros. If corpus evolution
# surfaces Tier C need, port selectively with per-claim gating.
# R7 (2026-04-30): 作為 added to Tier A — copula construction `將X作為Y`
# is common in TIPO method-claim drafting (`將前述矽鍺層作為p型通道層露出`)
# where Y is a role/function name being introduced. Noun class extended
# to admit ASCII letters/digits so semiconductor identifiers (`p型通道層`,
# `n型通道層`, `RAM控制器`) capture cleanly — same mixed-script class as
# F14. Excludes 之 (U+4E4B) and 的 (U+7684) to prevent capture extending
# into possessive markers.
_F12_TIER_A_RE_TW: re.Pattern[str] = re.compile(
    r'(?:作為|轉變為|變為|轉為|劃分為|分為)'
    r'([A-Za-z0-9\u4e00-\u4e4a\u4e4c-\u7683\u7685-\u9fff]{2,10})'
)
_F12_TIER_B_RE_TW: re.Pattern[str] = re.compile(
    r'(?:基於|來自)([\u4e00-\u9fff]{2,10})'
)


def _dym_quality_reject_tw(ref: str, dym: str) -> bool:
    """True if DYM should be suppressed per Phase B3/F5 filters.

    Four filters:
      1. ``len(dym) > 2 * len(ref)`` — disproportionate expansion.
      2. DYM starts with a token in ``_DYM_LEADING_REJECTS_TW`` — walker
         captured a prep/particle-headed or reference-prefix-headed
         fragment, not a clean NP.
      3. ``ref in dym`` strict substring AND the wrapping chars contain
         any stop-particle — walker captured the ref + noise.
      4. (F5) ``ref in dym`` strict substring AND the non-overlap span
         (before OR after) contains ≥2 CJK chars — DYM is a modifier-
         expanded form of ref (e.g., 圖形使用者介面 ⊃ 使用者介面). Such
         expansions are almost always walker noise or compound-noun
         siblings rather than the drafter's intent. Suppressing allows
         the morphological-prefix fallback to surface a better match
         (e.g., 使用者裝置 sharing 使用者 prefix).
    """
    if len(dym) > 2 * len(ref):
        return True
    for prefix in _DYM_LEADING_REJECTS_TW:
        if dym.startswith(prefix):
            return True
    if len(ref) < len(dym) and ref in dym:
        idx = dym.index(ref)
        before = dym[:idx]
        after = dym[idx + len(ref):]
        if any(p in before or p in after for p in _DYM_STOP_PARTICLES_TW):
            return True
        # F5 — reject modifier-expanded superset DYMs
        before_cjk = sum(1 for c in before if '\u4e00' <= c <= '\u9fff')
        after_cjk = sum(1 for c in after if '\u4e00' <= c <= '\u9fff')
        if before_cjk >= 2 or after_cjk >= 2:
            return True
    return False


def _morphological_prefix_fallback_tw(
    ref: str,
    intros_by_term: dict,
    *,
    min_shared_prefix: int = 2,
    min_term_len: int = 3,
) -> dict | None:
    """Phase F5 — morphological-prefix fallback DYM.

    When the primary Jaccard + quality-gate pipeline produces no DYM,
    look for ancestor intros that share a leading prefix of ≥2 CJK
    chars with the reference. Intuition: drafting errors often produce
    same-stem / different-suffix typos (使用者介面 ↔ 使用者裝置,
    第二控制模組 ↔ 第二通訊模組) where character-bigram Jaccard is
    below threshold but the shared morphological stem makes the intent
    clear.

    Returns ``{"term": intro_term, "claim_id": ancestor_id}`` for the
    longest-shared-prefix match, or ``None`` if no candidate qualifies.
    Ties broken by nearer ancestor (smaller depth), then by insertion
    order.
    """
    if len(ref) < min_term_len:
        return None

    best_prefix_len = 0
    best_depth: int | None = None
    best: dict | None = None
    for intro_term, (ancestor_id, depth) in intros_by_term.items():
        if len(intro_term) < min_term_len:
            continue
        if intro_term == ref:
            continue
        shared = 0
        for a, b in zip(ref, intro_term):
            if a != b:
                break
            if '\u4e00' <= a <= '\u9fff':
                shared += 1
            else:
                break
        if shared < min_shared_prefix:
            continue
        if (
            shared > best_prefix_len
            or (
                shared == best_prefix_len
                and (best_depth is None or depth < best_depth)
            )
        ):
            best_prefix_len = shared
            best_depth = depth
            best = {"term": intro_term, "claim_id": ancestor_id}
    return best


def _symbol_table_dym_fallback_tw(
    ref: str,
    symbol_table_norms: set[str],
    symbol_table_lookup: dict[str, str],
    *,
    min_shared_prefix: int = 3,
    min_term_len: int = 3,
) -> dict | None:
    """R61b (b) — symbol_table did-you-mean enrichment.

    When chain DYM and morphological-prefix fallback both miss, search
    符號說明 entries for a leading-prefix-≥3 match. Returns
    ``{"term": original_st_name, "claim_id": None, "source":
    "symbol_table"}`` for the longest-shared-prefix match, or ``None``.

    The ``source`` discriminator lets the UI render a distinct hint
    ("declared in 符號說明") rather than a normal did-you-mean line —
    symbol_table-sourced suggestions don't satisfy claim-level antecedent;
    the user still needs to add a `一X` intro in the claim.
    Tighter prefix floor (3 vs 2) than morphological fallback because
    symbol_table names are shorter and false-prefix overlaps are higher.
    """
    if len(ref) < min_term_len:
        return None
    best_prefix_len = 0
    best: dict | None = None
    for intro_term in symbol_table_norms:
        if len(intro_term) < min_term_len:
            continue
        if intro_term == ref:
            return {
                "term": symbol_table_lookup.get(intro_term, intro_term),
                "claim_id": None,
                "source": "symbol_table",
            }
        shared = 0
        for a, b in zip(ref, intro_term):
            if a != b:
                break
            if '一' <= a <= '鿿':
                shared += 1
            else:
                break
        if shared < min_shared_prefix:
            continue
        if shared > best_prefix_len:
            best_prefix_len = shared
            best = {
                "term": symbol_table_lookup.get(intro_term, intro_term),
                "claim_id": None,
                "source": "symbol_table",
            }
    return best


# Recognized TW dependency format patterns.
# TIPO 偵錯系統 documentation (2023.5.30 版, Table 1 #20) accepts three
# opening verbs for dependent claims — 如 / 依據 / 根據 — so the prefix is
# unconstrained. In practice TW drafters overwhelmingly use 如請求項 (TIPO's
# canonical), but this keeps us consistent with the authoritative spec and
# matches how CN's dep-format check treats 根据/按照/依照.
# Trailing connective accepts TIPO-standard (所述) + JP-translation variants
# (所記載, less common: 所揭示 / 所描述), plus bare 之/的 (如請求項N之X).
_TW_DEP_CONNECTIVE = r"(?:所(?:述|記載|揭示|描述))?[之的]?"
# R62 (2026-05-05): admit older TIPO form `申請專利範圍第N項` alongside
# modern `請求項N`. Same fix as parser/_TW_DEP_PATTERN — pre-2018 TIPO
# drafts use the older form and were misclassified as independent claims.
_TW_DEP_FORMAT = re.compile(
    r"(?:請求項|申請專利範圍)\s*第?\s*\d+\s*項?"
    r"(?:\s*(?:~|至|到)\s*(?:(?:請求項|申請專利範圍)\s*)?第?\s*\d+\s*項?)?"
    r"(?:\s*(?:或|、)\s*(?:(?:請求項|申請專利範圍)\s*)?第?\s*\d+\s*項?)*"
    r"(?:\s*中\s*任一?項)?"
    r"\s*" + _TW_DEP_CONNECTIVE
)

# Bare reference numeral: CJK char followed by 2-4 digits not in parens.
# Exclude: ordinals (第N), measurements (digits followed by Latin or CJK unit
# tokens like 重量份, 重量百分比, 莫耳, etc.), and dependency refs (請求項N).
_CJK_UNIT_TOKENS = (
    r"重量百分比|重量份|重量比|"
    r"莫耳百分比|莫耳比|莫耳|"
    r"體積百分比|體積比|質量百分比|原子百分比|"
    r"毫克|公克|毫升|公升|微升|微米|奈米|公分|公釐|公尺|"
    r"克|升|倍率|倍|份|個|顆|片|"
    # R-refnum-1 (2026-04-30, issue #25): Miller-index suffixes for
    # crystallography in semiconductor patents. Drafters write `100面` /
    # `110方向` etc. as bare digits because the paren form `(100)面` is
    # also conventional but optional (TIPO/CNIPA accept both). Pre-fix:
    # walker mistook `100面` for an unbracketed element reference numeral
    # (Claire's draft c12 `露出前述矽層之100面的狀態下實施`). Longer
    # multi-char tokens listed first for readability — order doesn't
    # matter for correctness in negative-lookahead alternation.
    r"結晶面|晶面|平面|方向|面"
)
_BARE_NUMERAL = re.compile(
    r"(?<!\()(?<=[\u4e00-\u9fff])"  # preceded by CJK, not by (
    r"(?<!第)(?<!請求項)(?<!至)"     # not ordinal 第N / 請求項N / range 至N
    r"\s?\d{2,4}"                    # 2-4 digit number
    r"(?!\))"                        # not followed by )
    r"(?!\d)"                        # must match full number, no partial
    r"(?!\s*[°℃%a-zA-Z])"           # not followed by Latin unit/measurement
    r"(?!\s*(?:" + _CJK_UNIT_TOKENS + r"))"  # not followed by CJK unit token
)

# Subject extraction: text before 其特徵在於 or first comma
_PREAMBLE_END = re.compile(r"(?:其特徵在於|其改良在於|，|,)")

# Dependent claim subject: text after 所述之/所述的 or bare 之 (如請求項N之)
_DEP_SUBJECT = re.compile(r"(?:所述[之的]|(?<=\d)[之的])(.+?)(?:，|,|其特徵|其改良|$)")

# Dependent-claim preamble (anchored at start) so body-text occurrences of
# 所述的 inside independent claims do not hijack subject extraction.
# Trailing connective must match (not optional) — a dep preamble is
# distinguished from a bare 如請求項N reference by the presence of the
# connective `所述[之的]` / `所記載[之的]` / etc., followed by the subject.
_DEP_PREAMBLE_CONNECTIVE = r"(?:所(?:述|記載|揭示|描述)[之的]|[之的])"
_DEP_PREFIX_RE = re.compile(
    r"^(?:如|根據|依)請求項\s*\d+"
    r"(?:\s*(?:~|至|到)\s*\d+)?"
    r"(?:\s*(?:或|、)\s*\d+)*"
    r"(?:\s*中\s*任一?項)?"
    r"\s*" + _DEP_PREAMBLE_CONNECTIVE
)
_INDEP_PREFIX_RE = re.compile(r"^(?:一種|一個)\s*")
# Subject-end boundary: any clause/sentence terminator stops extraction so
# a realistic claim preamble (with trailing 。 or ；) yields a clean subject.
_SUBJECT_END_RE = re.compile(r"(?:[，,；。]|其特徵在於|其改良在於|其中)")

# Leading quantifier for normalization
_LEADING_QUANTIFIER = re.compile(r"^(?:一種|一個|該|所述|所述的)\s*")

# Transitional phrases (broader set per prompt).
# 具備 / 具有 are added for 引用記載型式 (quoted-reference) independent
# claims that declare a new subject and incorporate claim N's component:
# `一種X，具備如請求項N所述的Y、以及Z。` — 具備 is the standard TIPO
# transition in this drafting form.
_TRANSITION_PHRASES = (
    "其特徵在於", "其改良在於",
    "包含", "包括", "其中包括",
    "具備", "具有",
)

# Spec/drawing reference patterns in claims
_SPEC_REF = re.compile(r"如說明書|如圖|參見說明書|參見圖|參照說明書|參照附圖|如圖所示")


def _extract_subject_with_path(claim_text: str) -> tuple[str, str]:
    """Extract subject matter + provenance tag.

    Returns (subject_text, extraction_path) where path is one of:
      - ``"dep_prefix"``   — matched `_DEP_PREFIX_RE` (clean dep preamble)
      - ``"indep_prefix"`` — matched `_INDEP_PREFIX_RE` (clean indep preamble)
      - ``"fallthrough"``  — no recognized preamble, returned raw text

    Subject-consistency callers use the path tag to distinguish walker
    parse failures (``fallthrough``) from genuine drafter-level subject
    mismatches. The path tag is also surfaced as a diagnostic fingerprint
    in error-report emails so walker regex gaps are self-identifying
    without any claim content leaving the device.
    """
    text = re.sub(r"^\s*\d+\s*[.．]\s*", "", claim_text).strip()
    dep_m = _DEP_PREFIX_RE.match(text)
    if dep_m:
        remainder = text[dep_m.end():]
        end_m = _SUBJECT_END_RE.search(remainder)
        return (
            (remainder[:end_m.start()] if end_m else remainder).strip(),
            "dep_prefix",
        )
    indep_m = _INDEP_PREFIX_RE.match(text)
    if indep_m:
        body = text[indep_m.end():]
        end_m = _SUBJECT_END_RE.search(body)
        return (
            (body[:end_m.start()] if end_m else body).strip(),
            "indep_prefix",
        )
    end_m = _SUBJECT_END_RE.search(text)
    return (
        (text[:end_m.start()] if end_m else text).strip(),
        "fallthrough",
    )


def _extract_subject(claim_text: str) -> str:
    """Back-compat wrapper — returns just the subject text.

    New callers should prefer ``_extract_subject_with_path`` so they can
    distinguish fall-through parse failures from clean extractions.
    """
    subject, _path = _extract_subject_with_path(claim_text)
    return subject


def _normalize_subject(subject: str) -> str:
    """Strip leading quantifiers for comparison."""
    return _LEADING_QUANTIFIER.sub("", subject).strip()


# ── Check 11 ─────────────────────────────────────────────────────────────


def check_claims_sequential(doc: TwPatentDocument) -> list[CheckItem]:
    """Verify claim numbers are sequential from 1."""
    claims = doc.claims
    if not claims:
        return [CheckItem(
            status="pass",
            message="No claims to check.",
            message_key="check.tw.claims.sequential.pass",
            reference="專利審查基準",
        )]

    for i, claim in enumerate(claims):
        expected = i + 1
        if claim.id != expected:
            return [CheckItem(
                status="amend",
                message=f"Claim numbering is not sequential: expected {expected}, found {claim.id}.",
                message_key="check.tw.claims.sequential.amend",
                details_key="details.tw.claimsSequential",
                details_params={"expected": expected, "found": claim.id},
                reference="專利審查基準",
                diagnostics=_dx(
                    expected_id=expected,
                    found_id=claim.id,
                    total_claims=len(claims),
                    gap_position=i,
                    is_backward=claim.id < expected,
                    preamble=(claim.text or "")[:80],
                ),
            )]

    return [CheckItem(
        status="pass",
        message="Claim numbers are sequential.",
        message_key="check.tw.claims.sequential.pass",
        reference="專利審查基準",
    )]


# ── Check 12 ─────────────────────────────────────────────────────────────


def check_dependency_format(doc: TwPatentDocument) -> list[CheckItem]:
    """Check dependent claims use recognized TW dependency format."""
    dependents = [c for c in doc.claims if not c.independent]
    if not dependents:
        return [CheckItem(
            status="pass",
            message="No dependent claims to check.",
            message_key="check.tw.claims.dependencyFormat.pass",
            reference="專利法施行細則 §18",
        )]

    bad_claim_ids: list[int] = []
    for claim in dependents:
        if not _TW_DEP_FORMAT.search(claim.text):
            bad_claim_ids.append(claim.id)

    if bad_claim_ids:
        claims_str = ", ".join(str(i) for i in bad_claim_ids)
        return [CheckItem(
            status="amend",
            message=f"{len(bad_claim_ids)} claim(s) with unrecognized dependency format (claims: {claims_str}).",
            message_key="check.tw.claims.dependencyFormat.amend",
            details=f"{len(bad_claim_ids)} claims",
            details_key="details.tw.dependencyFormat",
            details_params={"count": len(bad_claim_ids), "claims": bad_claim_ids},
            reference="專利法施行細則 §18",
            diagnostics=_dx(
                flagged_count=len(bad_claim_ids),
                total_dependents=len(dependents),
                flagged_claim_id=bad_claim_ids[0] if bad_claim_ids else None,
                findings=[
                    {"claim_id": cid, "preamble": (next((c.text for c in doc.claims if c.id == cid), "") or "")[:80]}
                    for cid in bad_claim_ids[:5]
                ],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="All dependency references use recognized format.",
        message_key="check.tw.claims.dependencyFormat.pass",
        reference="專利法施行細則 §18",
    )]


# Strip the `N. ` / `N．` claim-number prefix before checking the preamble.
_CLAIM_NUM_PREFIX = re.compile(r"^[\s　]*\d+\s*[.．]\s*")


def check_independent_preamble(doc: TwPatentDocument) -> list[CheckItem]:
    """Advisory: flag independent claims not opening with 「一種」.

    TIPO 偵錯系統 (Table 1 #20, 2023.5.30 版 PDF fig 33) flags this as an
    error in its debugger because `一種X` is the practitioner convention
    that lets the 標的名稱 (subject-matter designation) be reliably parsed.
    Note: 專利法施行細則 §18 + 專利審查基準 require the preamble to state
    the subject-matter name but do NOT literally mandate 「一種」 — other
    preambles that still name the subject matter may satisfy the statute.
    Status is therefore VERIFY (advisory), not FIX.

    Dependent-claim openers (如/依據/根據) validated separately by
    ``check_dependency_format``.
    """
    bad: list[int] = []
    for claim in doc.claims:
        if not claim.independent:
            continue
        body = _CLAIM_NUM_PREFIX.sub("", claim.text).lstrip()
        if not body.startswith("一種"):
            bad.append(claim.id)

    if bad:
        bad_sorted = sorted(set(bad))
        claims_str = ", ".join(str(i) for i in bad_sorted)
        return [CheckItem(
            status="verify",
            message=f"Independent claim(s) not opening with 「一種」: {claims_str}.",
            message_key="check.tw.claims.independentPreamble.verify",
            details=claims_str,
            details_key="details.tw.independentPreamble",
            details_params={"count": len(bad_sorted), "claims": bad_sorted},
            reference="專利審查基準 + TIPO 偵錯系統 Table 1 #20",
            diagnostics=_dx(
                flagged_count=len(bad_sorted),
                total_claims=len(doc.claims),
                flagged_claim_id=bad_sorted[0] if bad_sorted else None,
            ),
        )]
    return [CheckItem(
        status="pass",
        message="All independent claims open with 「一種」.",
        message_key="check.tw.claims.independentPreamble.pass",
        reference="專利審查基準 + TIPO 偵錯系統 Table 1 #20",
    )]


# ── Check 13 ─────────────────────────────────────────────────────────────


def check_self_dependent(doc: TwPatentDocument) -> list[CheckItem]:
    """Check if any claim depends on itself."""
    bad = [c.id for c in doc.claims if c.id in c.dependencies]

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Self-dependent claims found: {claims_str}.",
            message_key="check.tw.claims.selfDependent.amend",
            details=claims_str,
            details_key="details.tw.selfDependent",
            details_params={"claims": bad},
            reference="專利法施行細則 §18",
            diagnostics=_dx(
                flagged_count=len(bad),
                total_claims=len(doc.claims),
                flagged_claim_id=bad[0] if bad else None,
                findings=[
                    {"claim_id": cid, "preamble": (next((c.text for c in doc.claims if c.id == cid), "") or "")[:80]}
                    for cid in bad[:5]
                ],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="No self-dependent claims.",
        message_key="check.tw.claims.selfDependent.pass",
        reference="專利法施行細則 §18",
    )]


# ── Check 14 ─────────────────────────────────────────────────────────────


def check_circular_dependency(doc: TwPatentDocument) -> list[CheckItem]:
    """Detect circular dependency chains."""
    claims_by_id = {c.id: c for c in doc.claims}

    def has_cycle(start_id: int) -> list[int] | None:
        visited: set[int] = set()
        path: list[int] = []
        current = start_id
        while current in claims_by_id:
            if current in visited:
                return path
            visited.add(current)
            path.append(current)
            claim = claims_by_id[current]
            if claim.independent or not claim.dependencies:
                return None
            current = claim.dependencies[0]
        return None

    for claim in doc.claims:
        if not claim.independent:
            cycle = has_cycle(claim.id)
            if cycle:
                # R65 (2026-05-05): suppress cycles whose closing edge is
                # itself a self-loop — those are already flagged by
                # check_self_dependent with the same root cause. The cycle
                # detector reports "5 → 4" when c5.deps=[4] and c4.deps=[4]
                # (c4's self-loop), but that's not a true mutual cycle
                # between distinct claims. True multi-hop cycles
                # (c5↔c6 mutual; c7→c8→c9→c7 ring) have last cycle claim's
                # first dep pointing at a DIFFERENT claim already in path.
                terminal_id = cycle[-1]
                terminal_claim = claims_by_id.get(terminal_id)
                if (
                    terminal_claim is not None
                    and terminal_claim.dependencies == [terminal_id]
                ):
                    # Self-loop on the terminal claim → redundant with
                    # selfDependent; skip.
                    continue
                claims_str = " → ".join(str(i) for i in cycle)
                return [CheckItem(
                    status="amend",
                    message=f"Circular dependency chain found: {claims_str}.",
                    message_key="check.tw.claims.circularDependency.amend",
                    details=claims_str,
                    details_key="details.tw.circularDependency",
                    details_params={"claims": claims_str},
                    reference="專利法施行細則 §18",
                    diagnostics=_dx(
                        cycle_length=len(cycle),
                        total_claims=len(doc.claims),
                        flagged_claim_id=cycle[0] if cycle else None,
                        cycle_claim_ids=cycle[:10],
                        findings=[
                            {"claim_id": cid, "preamble": (next((c.text for c in doc.claims if c.id == cid), "") or "")[:80]}
                            for cid in cycle[:5]
                        ],
                    ),
                )]

    return [CheckItem(
        status="pass",
        message="No circular dependencies.",
        message_key="check.tw.claims.circularDependency.pass",
        reference="專利法施行細則 §18",
    )]


# ── Check 15 ─────────────────────────────────────────────────────────────


def _collect_cycle_member_ids(doc: TwPatentDocument) -> set[int]:
    """Return claim IDs that participate in any first-dep cycle.

    Mirrors `check_circular_dependency`'s detection (first-dep walk +
    revisit detection) but returns the set of all involved IDs across
    every cycle. Used by `check_forward_dependency` to exclude
    cycle-induced forward edges from its emit (R66 dedup against
    circularDependency — both flag the same root cause when a multi-hop
    cycle exists).
    """
    claims_by_id = {c.id: c for c in doc.claims}
    cycle_ids: set[int] = set()
    for claim in doc.claims:
        if claim.independent:
            continue
        visited: set[int] = set()
        path: list[int] = []
        current = claim.id
        while current in claims_by_id:
            if current in visited:
                cycle_ids.update(path)
                break
            visited.add(current)
            path.append(current)
            cur_claim = claims_by_id[current]
            if cur_claim.independent or not cur_claim.dependencies:
                break
            current = cur_claim.dependencies[0]
    return cycle_ids


def check_forward_dependency(doc: TwPatentDocument) -> list[CheckItem]:
    """Check if any claim depends on a higher-numbered claim.

    R66 (2026-05-05): exclude claim IDs that participate in any circular
    cycle — those are already flagged by `check_circular_dependency`
    with the same root cause (every multi-hop cycle has at least one
    forward-pointing edge by ordering). Without dedup, a 5↔7 mutual
    cycle emits BOTH `forwardDependency.amend` (claim 5) AND
    `circularDependency.amend` (chain 5→7) for the same defect.
    Pure forward refs (c2 deps=[5] without c5 cycling back) still emit
    here — they're a distinct drafter mistake circularDependency misses.
    """
    cycle_ids = _collect_cycle_member_ids(doc)
    bad = [
        c.id for c in doc.claims
        if any(d > c.id for d in c.dependencies)
        and c.id not in cycle_ids
    ]

    if bad:
        return [CheckItem(
            status="amend",
            message=f"Forward-referencing claims found: {', '.join(str(i) for i in bad)}.",
            message_key="check.tw.claims.forwardDependency.amend",
            details=", ".join(str(i) for i in bad),
            details_key="details.tw.forwardDependency",
            details_params={"claims": bad},
            reference="專利法施行細則 §18",
            diagnostics=_dx(
                flagged_count=len(bad),
                total_claims=len(doc.claims),
                flagged_claim_id=bad[0] if bad else None,
                findings=[
                    {"claim_id": cid, "preamble": (next((c.text for c in doc.claims if c.id == cid), "") or "")[:80]}
                    for cid in bad[:5]
                ],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="No forward dependencies.",
        message_key="check.tw.claims.forwardDependency.pass",
        reference="專利法施行細則 §18",
    )]


# ── Check 16 ─────────────────────────────────────────────────────────────


def check_single_sentence(doc: TwPatentDocument) -> list[CheckItem]:
    """Each claim must have exactly one 。 at the end, no 。 in the middle.

    Two distinct failure modes per §18:
      - missing ending period (claim has zero 。)
      - not a single sentence (claim has 2+ 。, or a single 。 mid-claim)

    Emit separate findings so the amend copy tells the drafter what to fix
    rather than collapsing both into a generic "not a single sentence".
    """
    missing_period: list[int] = []
    multi_sentence: list[int] = []
    # Track last-codepoint per flagged claim so the fingerprint reveals
    # full-width/half-width punctuation variants (e.g. ， U+FF0C vs . U+002E)
    # without surfacing the claim text itself.
    sample_missing_codepoint: int | None = None
    sample_multi_codepoint: int | None = None
    for claim in doc.claims:
        text = claim.text.strip()
        period_count = text.count("。")
        last_cp = ord(text[-1]) if text else None
        if period_count == 0:
            missing_period.append(claim.id)
            if sample_missing_codepoint is None and last_cp is not None:
                sample_missing_codepoint = last_cp
        elif period_count > 1 or not text.endswith("。"):
            multi_sentence.append(claim.id)
            if sample_multi_codepoint is None and last_cp is not None:
                sample_multi_codepoint = last_cp

    items: list[CheckItem] = []
    if missing_period:
        claims_str = ", ".join(str(i) for i in missing_period)
        items.append(CheckItem(
            status="amend",
            message=f"{len(missing_period)} claim(s) missing ending period (claims: {claims_str}).",
            message_key="check.tw.claims.singleSentence.amendMissingPeriod",
            details=f"{len(missing_period)} claims",
            details_key="details.tw.singleSentenceMissingPeriod",
            details_params={"count": len(missing_period), "claims": missing_period},
            reference="專利法施行細則 §18",
            diagnostics=_dx(
                flagged_count=len(missing_period),
                total_claims=len(doc.claims),
                sample_last_codepoint=sample_missing_codepoint,
            ),
        ))
    if multi_sentence:
        claims_str = ", ".join(str(i) for i in multi_sentence)
        items.append(CheckItem(
            status="amend",
            message=f"{len(multi_sentence)} claim(s) not written as a single sentence (claims: {claims_str}).",
            message_key="check.tw.claims.singleSentence.amendMultiSentence",
            details=f"{len(multi_sentence)} claims",
            details_key="details.tw.singleSentenceMultiSentence",
            details_params={"count": len(multi_sentence), "claims": multi_sentence},
            reference="專利法施行細則 §18",
            diagnostics=_dx(
                flagged_count=len(multi_sentence),
                total_claims=len(doc.claims),
                sample_last_codepoint=sample_multi_codepoint,
            ),
        ))
    if items:
        return items

    return [CheckItem(
        status="pass",
        message="All claims are single sentences.",
        message_key="check.tw.claims.singleSentence.pass",
        reference="專利法施行細則 §18",
    )]


# ── Check 17 ─────────────────────────────────────────────────────────────


def _ref_numeral_finding_diag(cid: int, claims: list) -> dict:
    """Build a per-claim diagnostic finding for refNumeralParens.

    Returns ``{claim_id, first_match, context_after}`` where context_after
    is the 8-char window after the matched digits. R-refnum-1 added
    context_after so reports of Miller-index FPs (`100面`) and other
    over-fires arrive self-diagnosing.
    """
    text = next((c.text for c in claims if c.id == cid), "")
    m = _BARE_NUMERAL.search(text)
    if not m:
        return {"claim_id": cid, "first_match": None, "context_after": None}
    return {
        "claim_id": cid,
        "first_match": m.group(0),
        "context_after": text[m.end():m.end() + 8],
    }


def check_ref_numeral_parens(doc: TwPatentDocument) -> list[CheckItem]:
    """Find reference numerals in claims not enclosed in parentheses (FIX).

    施行細則 §19 第3款 mandates parens when ref numerals appear:
    「該符號應附加於對應之技術特徵後，並置於括號內」. Drafter chose
    to use numerals → parens are statutorily required; the check
    fires only when the violation exists.
    """
    bad_claim_ids: list[int] = []
    for claim in doc.claims:
        if _BARE_NUMERAL.search(claim.text):
            bad_claim_ids.append(claim.id)

    if bad_claim_ids:
        claims_str = ", ".join(str(i) for i in bad_claim_ids)
        return [CheckItem(
            status="amend",
            message=f"{len(bad_claim_ids)} claim(s) with reference numerals not in parentheses (claims: {claims_str}).",
            message_key="check.tw.claims.refNumeralParens.amend",
            details=f"{len(bad_claim_ids)} claims",
            details_key="details.tw.refNumeralParens",
            details_params={"count": len(bad_claim_ids), "claims": bad_claim_ids},
            reference="專利法施行細則 §19",
            diagnostics=_dx(
                flagged_count=len(bad_claim_ids),
                total_claims=len(doc.claims),
                flagged_claim_id=bad_claim_ids[0] if bad_claim_ids else None,
                # R-refnum-1 (2026-04-30, issue #25): added `context_after`
                # so future reports of FPs like Miller-index `100面` arrive
                # self-diagnosing without needing the draft. The 8-char
                # window after the match captures the immediately-following
                # context (面的狀態 / 方向上 / etc.) which classifies the
                # bug class on payload inspection alone.
                findings=[
                    _ref_numeral_finding_diag(cid, doc.claims)
                    for cid in bad_claim_ids[:5]
                ],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="All reference numerals in claims are in parentheses.",
        message_key="check.tw.claims.refNumeralParens.pass",
        reference="專利法施行細則 §19",
    )]


# ── Check 18 ─────────────────────────────────────────────────────────────


def check_subject_consistency(doc: TwPatentDocument) -> list[CheckItem]:
    """Check dependent claim subject matter matches parent claim subject matter.

    Emits two distinct finding categories per ADR-145 (check-split for
    parse-failure vs genuine-violation):

      * ``verify`` — both claim preambles parsed cleanly, subjects differ.
      * ``parseUnclear`` — at least one preamble didn't match any recognized
        form. This is a walker parse limit, not a drafter error. Typically
        surfaces on JP-translated drafts with unrecognized preamble forms.

    Each non-pass finding carries a ``diagnostics`` dict with structural
    fingerprints (path tag, char lengths, connective form) so error-report
    emails can identify which code path fired without leaking content.
    """
    claims_by_id = {c.id: c for c in doc.claims}
    dependents = [c for c in doc.claims if not c.independent]

    if not dependents:
        return [CheckItem(
            status="pass",
            message="No dependent claims to check.",
            message_key="check.tw.claims.subjectConsistency.pass",
            reference="專利審查基準",
        )]

    mismatch_ids: list[int] = []
    unclear_ids: list[int] = []
    # Accumulate per-category diagnostic samples — one representative
    # fingerprint per category, compact enough for the email payload.
    mismatch_fp: dict[str, Any] | None = None
    unclear_fp: dict[str, Any] | None = None

    for claim in dependents:
        if not claim.dependencies:
            continue
        parent_id = claim.dependencies[0]
        parent = claims_by_id.get(parent_id)
        if not parent:
            continue

        dep_raw, dep_path = _extract_subject_with_path(claim.text)
        parent_raw, parent_path = _extract_subject_with_path(parent.text)
        dep_subject = _normalize_subject(dep_raw)
        parent_subject = _normalize_subject(parent_raw)

        # Parse-failure category: one side couldn't be resolved to a clean
        # preamble shape. Emit parseUnclear instead of verify.
        if dep_path == "fallthrough" or parent_path == "fallthrough":
            unclear_ids.append(claim.id)
            if unclear_fp is None:
                unclear_fp = {
                    "dep_path": dep_path,
                    "parent_path": parent_path,
                    "dep_subject_charlen": len(dep_subject),
                    "parent_subject_charlen": len(parent_subject),
                }
            continue

        if dep_subject and parent_subject and dep_subject != parent_subject:
            mismatch_ids.append(claim.id)
            if mismatch_fp is None:
                mismatch_fp = {
                    "dep_path": dep_path,
                    "parent_path": parent_path,
                    "dep_subject_charlen": len(dep_subject),
                    "parent_subject_charlen": len(parent_subject),
                }

    results: list[CheckItem] = []
    if mismatch_ids:
        claims_str = ", ".join(str(i) for i in mismatch_ids)
        results.append(CheckItem(
            status="verify",
            message=f"{len(mismatch_ids)} dependent claim(s) with inconsistent subject matter (claims: {claims_str}).",
            message_key="check.tw.claims.subjectConsistency.verify",
            details=f"{len(mismatch_ids)} claims",
            details_key="details.tw.subjectConsistency",
            details_params={"count": len(mismatch_ids), "claims": mismatch_ids},
            reference="專利審查基準",
            diagnostics=mismatch_fp,
        ))
    if unclear_ids:
        claims_str = ", ".join(str(i) for i in unclear_ids)
        results.append(CheckItem(
            status="verify",
            message=f"{len(unclear_ids)} dependent claim(s) with an unrecognized preamble — couldn't verify subject consistency (claims: {claims_str}).",
            message_key="check.tw.claims.subjectConsistencyParseUnclear",
            details=f"{len(unclear_ids)} claims",
            details_key="details.tw.subjectConsistencyParseUnclear",
            details_params={"count": len(unclear_ids), "claims": unclear_ids},
            reference="專利審查基準",
            diagnostics=unclear_fp,
        ))
    if results:
        return results

    return [CheckItem(
        status="pass",
        message="All dependent claim subject matter matches parent.",
        message_key="check.tw.claims.subjectConsistency.pass",
        reference="專利審查基準",
    )]


# ── Check 19 ─────────────────────────────────────────────────────────────


def check_transition_phrase(doc: TwPatentDocument) -> list[CheckItem]:
    """Check independent claims contain a transitional phrase."""
    independents = [c for c in doc.claims if c.independent]
    if not independents:
        return [CheckItem(
            status="pass",
            message="No independent claims to check.",
            message_key="check.tw.claims.transitionPhrase.pass",
            reference="專利法施行細則 §20",
        )]

    bad_claim_ids: list[int] = []
    for claim in independents:
        if not any(phrase in claim.text for phrase in _TRANSITION_PHRASES):
            bad_claim_ids.append(claim.id)

    if bad_claim_ids:
        claims_str = ", ".join(str(i) for i in bad_claim_ids)
        return [CheckItem(
            status="verify",
            message=f"{len(bad_claim_ids)} independent claim(s) missing transitional phrase (claims: {claims_str}).",
            message_key="check.tw.claims.transitionPhrase.verify",
            details=f"{len(bad_claim_ids)} claims",
            details_key="details.tw.transitionPhrase",
            details_params={"count": len(bad_claim_ids), "claims": bad_claim_ids},
            reference="專利法施行細則 §20",
            diagnostics=_dx(
                flagged_count=len(bad_claim_ids),
                total_independent=len(independents),
                flagged_claim_id=bad_claim_ids[0] if bad_claim_ids else None,
                findings=[
                    {"claim_id": cid, "preamble": (next((c.text for c in doc.claims if c.id == cid), "") or "")[:120]}
                    for cid in bad_claim_ids[:5]
                ],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="All independent claims contain a transitional phrase.",
        message_key="check.tw.claims.transitionPhrase.pass",
        reference="專利法施行細則 §20",
    )]


# ── Check 20 ─────────────────────────────────────────────────────────────

# CNIPA simplified Chinese terms that should not appear in TW documents
_CNIPA_TERMS = ["权利要求", "说明书", "背景技术", "具体实施方式", "发明内容", "附图说明", "其特征在于"]


def check_cn_terminology(doc: TwPatentDocument) -> list[CheckItem]:
    """Scan claims for CNIPA simplified Chinese terminology."""
    all_text = " ".join(c.text for c in doc.claims)
    found = [term for term in _CNIPA_TERMS if term in all_text]

    if found:
        return [CheckItem(
            status="amend",
            message=f"CNIPA terminology found: {', '.join(found)}.",
            message_key="check.tw.claims.cnTerminology.amend",
            details=", ".join(found),
            details_key="details.tw.cnTerminology",
            details_params={
                "detail": ", ".join(found),
                "flagged_phrases": {
                    "items": [{"kind": "term", "token": t} for t in found]
                },
            },
            reference=None,
            diagnostics=_dx(
                hit_count=len(found),
                total_terms_scanned=len(_CNIPA_TERMS),
                findings=[
                    {
                        "claim_id": c.id,
                        "token": term,
                    }
                    for term in found[:5]
                    for c in doc.claims if term in c.text
                ][:5],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="Claims use correct TIPO terminology.",
        message_key="check.tw.claims.cnTerminology.pass",
        reference=None,
    )]


# ── Check 21 ─────────────────────────────────────────────────────────────

_SPEC_DRAWING_REF = re.compile(
    r"如說明書所(?:述|記載|揭示|描述)"
    r"|如圖\d*所示|參見說明書|參見圖|見說明書|見圖"
)


def check_spec_drawing_ref(doc: TwPatentDocument) -> list[CheckItem]:
    """Check claims do not reference spec or drawings."""
    found_refs: list[str] = []
    for claim in doc.claims:
        matches = _SPEC_DRAWING_REF.findall(claim.text)
        found_refs.extend(matches)

    if found_refs:
        unique_refs = sorted(set(found_refs))
        detail = "、".join(unique_refs)
        return [CheckItem(
            status="amend",
            message="Claims reference specification or drawings.",
            message_key="check.tw.claims.specDrawingRef.amend",
            details_key="details.tw.specDrawingRef",
            details_params={
                "detail": detail,
                "flagged_phrases": {
                    "items": [{"kind": "reference", "token": r} for r in unique_refs]
                },
            },
            reference="專利法施行細則 §19",
            diagnostics=_dx(
                hit_count=len(found_refs),
                unique_patterns=len(set(found_refs)),
                findings=[
                    {
                        "claim_id": c.id,
                        "matched_phrase": m.group(0)[:80],
                    }
                    for c in doc.claims
                    if (m := _SPEC_DRAWING_REF.search(c.text))
                ][:5],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="No specification or drawing references in claims.",
        message_key="check.tw.claims.specDrawingRef.pass",
        reference="專利法施行細則 §19",
    )]


# ── Check 22 ─────────────────────────────────────────────────────────────


def check_multi_dep_on_multi_dep(doc: TwPatentDocument) -> list[CheckItem]:
    """Multi-dependent claim must not depend on another multi-dependent claim."""
    multi_dep_ids = {c.id for c in doc.claims if c.multiple_dependent}
    if not multi_dep_ids:
        return [CheckItem(
            status="pass",
            message="No multi-dependent-on-multi-dependent claims.",
            message_key="check.tw.claims.multiDepOnMultiDep.pass",
            reference="專利法施行細則 §18",
        )]

    claims_by_id = {c.id: c for c in doc.claims}

    def _get_all_deps(claim_id: int, visited: set[int] | None = None) -> set[int]:
        """Get all transitive dependencies."""
        if visited is None:
            visited = set()
        if claim_id in visited:
            return visited
        visited.add(claim_id)
        claim = claims_by_id.get(claim_id)
        if claim:
            for dep in claim.dependencies:
                _get_all_deps(dep, visited)
        return visited

    bad = []
    for claim in doc.claims:
        if claim.multiple_dependent:
            all_deps = _get_all_deps(claim.id)
            all_deps.discard(claim.id)
            if all_deps & multi_dep_ids:
                bad.append(claim.id)

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Multi-dependent claim depends on another multi-dependent claim: {claims_str}.",
            message_key="check.tw.claims.multiDepOnMultiDep.amend",
            details=claims_str,
            details_key="details.tw.multiDepOnMultiDep",
            details_params={"claims": bad},
            reference="專利法施行細則 §18",
            diagnostics=_dx(
                flagged_count=len(bad),
                total_multi_dep=len(multi_dep_ids),
                total_claims=len(doc.claims),
                flagged_claim_id=bad[0] if bad else None,
                findings=[
                    {"claim_id": cid, "preamble": (next((c.text for c in doc.claims if c.id == cid), "") or "")[:80]}
                    for cid in bad[:5]
                ],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="No multi-dependent-on-multi-dependent claims.",
        message_key="check.tw.claims.multiDepOnMultiDep.pass",
        reference="專利法施行細則 §18",
    )]


# ── Check 23 ─────────────────────────────────────────────────────────────


def check_multi_dep_alternative(doc: TwPatentDocument) -> list[CheckItem]:
    """Multi-dependent claims must use alternative form (或/任一項)."""
    multi_deps = [c for c in doc.claims if c.multiple_dependent]
    if not multi_deps:
        return [CheckItem(
            status="pass",
            message="All multi-dependent claims use alternative form.",
            message_key="check.tw.claims.multiDepAlternative.pass",
            reference="專利法施行細則 §18",
        )]

    bad = []
    for claim in multi_deps:
        if "或" not in claim.text and "任一項" not in claim.text:
            bad.append(claim.id)

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Multi-dependent claim(s) not in alternative form: {claims_str}.",
            message_key="check.tw.claims.multiDepAlternative.amend",
            details=claims_str,
            details_key="details.tw.multiDepAlternative",
            details_params={"claims": bad},
            reference="專利法施行細則 §18",
            diagnostics=_dx(
                flagged_count=len(bad),
                total_multi_dep=len(multi_deps),
                total_claims=len(doc.claims),
                flagged_claim_id=bad[0] if bad else None,
                findings=[
                    {"claim_id": cid, "preamble": (next((c.text for c in doc.claims if c.id == cid), "") or "")[:120]}
                    for cid in bad[:5]
                ],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="All multi-dependent claims use alternative form.",
        message_key="check.tw.claims.multiDepAlternative.pass",
        reference="專利法施行細則 §18",
    )]


# ── Check 24 ─────────────────────────────────────────────────────────────


def check_title_subject_match(doc: TwPatentDocument) -> list[CheckItem]:
    """Check title matches independent claim subjects."""
    if not doc.title or not doc.claims:
        return [CheckItem(
            status="pass",
            message="Title consistent with independent claim subjects.",
            message_key="check.tw.claims.titleSubjectMatch.pass",
            reference="專利審查基準",
        )]

    independents = [c for c in doc.claims if c.independent]
    if not independents:
        return [CheckItem(
            status="pass",
            message="Title consistent with independent claim subjects.",
            message_key="check.tw.claims.titleSubjectMatch.pass",
            reference="專利審查基準",
        )]

    title_norm = _normalize_subject(doc.title)
    subjects = []
    for claim in independents:
        subj = _normalize_subject(_extract_subject(claim.text))
        if subj:
            subjects.append(subj)

    if not subjects:
        return [CheckItem(
            status="pass",
            message="Title consistent with independent claim subjects.",
            message_key="check.tw.claims.titleSubjectMatch.pass",
            reference="專利審查基準",
        )]

    # Check if title overlaps with any subject
    for subj in subjects:
        if subj in title_norm or title_norm in subj:
            return [CheckItem(
                status="pass",
                message="Title consistent with independent claim subjects.",
                message_key="check.tw.claims.titleSubjectMatch.pass",
                reference="專利審查基準",
            )]

    subjects_str = "、".join(subjects)
    return [CheckItem(
        status="verify",
        message=f"Title '{doc.title}' may not match independent claim subjects: {subjects_str}.",
        message_key="check.tw.claims.titleSubjectMatch.verify",
        details_key="details.tw.titleSubjectMatch",
        details_params={
            "title": doc.title,
            "subjects": subjects_str,
            "flagged_phrases": {
                "items": [{"kind": "subject", "token": s} for s in subjects]
            },
        },
        reference="專利審查基準",
        diagnostics=_dx(
            title_charlen=len(title_norm),
            subject_count=len(subjects),
            total_independent=len(independents),
            title_first_30=doc.title[:30],
            subjects_sample=[(s or "")[:32] for s in subjects[:5]],
        ),
    )]


# ── Check 25 ─────────────────────────────────────────────────────────────

# Reference numeral in parentheses in claim text
_CLAIM_NUMERAL = re.compile(r"\((\d+)\)")


def check_claims_symbol_table_consistency(doc: TwPatentDocument) -> list[CheckItem]:
    """Verify reference numerals in claims are defined in 符號說明.

    Per 專利法施行細則 §19, reference numerals in claims are optional.
    When absent, the check passes vacuously. When present, every numeral
    used in claims must be defined in 符號說明; the reverse direction
    (符號說明 entries not used in claims) is NOT a defect — symbol
    tables legitimately cover all figure elements regardless of which
    appear in claim language.

    Emits structured details_params with claim-number locations for
    each undefined numeral, allowing the frontend formatter to render
    "99 (claim 1, claim 3), 100 (claim 5)" in the user's locale.
    """
    if not doc.symbol_table:
        return [CheckItem(
            status="pass",
            message="No 符號說明 entries to check against claims.",
            message_key="check.tw.claims.symbolTableConsistency.pass",
            reference="專利法施行細則 §19",
        )]

    # Collect numerals from claims (parenthesized form only, per §19),
    # tracking which claim numbers contain each numeral.
    numeral_to_claims: dict[str, list[int]] = {}
    for claim in doc.claims:
        for m in _CLAIM_NUMERAL.finditer(claim.text):
            numeral = m.group(1)
            if numeral not in numeral_to_claims:
                numeral_to_claims[numeral] = []
            if claim.id not in numeral_to_claims[numeral]:
                numeral_to_claims[numeral].append(claim.id)

    claim_numerals = set(numeral_to_claims.keys())

    # Early return: claims contain no reference numerals (allowed by §19).
    if not claim_numerals:
        return [CheckItem(
            status="pass",
            message="Claims contain no reference numerals; consistency check not applicable.",
            message_key="check.tw.claims.symbolTableConsistency.noClaimNumerals",
            reference="專利法施行細則 §19",
        )]

    # Collect numerals from symbol table (handle ranges like S21~S25)
    symbol_numerals: set[str] = set()
    for entry in doc.symbol_table:
        nums = re.findall(r"\d+", entry.numeral)
        symbol_numerals.update(nums)

    # Only flag the directionally meaningful case: numerals used in claims
    # but undefined in 符號說明. The reverse is allowed.
    missing_numerals = sorted(claim_numerals - symbol_numerals, key=int)

    if missing_numerals:
        # Build structured payload: list of {numeral, claims} dicts.
        # Frontend formatter will render this as
        # "99 (claim 1, claim 3), 100 (claim 5)" in the user's locale.
        numerals_with_locations = [
            {
                "numeral": n,
                "claims": sorted(numeral_to_claims[n]),
            }
            for n in missing_numerals
        ]
        return [CheckItem(
            status="verify",
            message="Reference numerals in claims undefined in 符號說明.",
            message_key="check.tw.claims.symbolTableConsistency.verify",
            details_key="details.tw.claims.symbolTableConsistency.missingFromTable",
            details_params={"numerals_with_locations": numerals_with_locations},
            reference="專利法施行細則 §19",
            diagnostics=_dx(
                missing_count=len(missing_numerals),
                total_claim_numerals=len(claim_numerals),
                total_symbol_numerals=len(symbol_numerals),
                missing_sample=[n for n in missing_numerals[:10]],
                first_missing=missing_numerals[0] if missing_numerals else None,
            ),
        )]

    return [CheckItem(
        status="pass",
        message="All reference numerals in claims are defined in 符號說明.",
        message_key="check.tw.claims.symbolTableConsistency.pass",
        reference="專利法施行細則 §19",
    )]


# ── Check 26 (連接關係) ──────────────────────────────────────────────────


def check_connection_relationships_tw(doc: TwPatentDocument) -> list[CheckItem]:
    """Flag independent apparatus claims listing components without a
    connection verb (TIPO 專利審查基準 §2.4).

    Thin wrapper over the shared CN/TW helper. Method, CRM, MPF, and
    composition claims are carved out per ``_TW_CONNECTION_CONFIG``.
    """
    return check_connection_relationships(doc.claims, _TW_CONNECTION_CONFIG)


# ── Check 27 ─────────────────────────────────────────────────────────────

# Boundary character class for the noun-phrase regex captures.
#
# Excluded categories (characters that NEVER appear inside a legitimate
# patent reference noun phrase, so the regex can safely terminate at them):
#
# - Whitespace and punctuation: \s ， 。 ； ： 、 (existing)
# - Conjunctions: 及 與 和 (existing)
# - Genitive markers: 之 的 (existing)
# - Reference-form prefix start: 該 (existing — prevents two adjacent
#   references from being captured as one noun span)
# - Auxiliary verbs / adverbs: 將 能 須 應 皆 (added 2026-04-09)
# - Passive marker: 被 (added 2026-04-09)
# - Prepositions: 於 以 在 (在 added 2026-04-09 round 3 — high-frequency
#   preposition that was contaminating findings like 該識別資料在 in
#   110P000868). 用 was added in round 2 (Bug B) but REMOVED in round 5 —
#   it was breaking 使用者 compounds (該多個使用者 captured as 多個使
#   then normalized to 使). See round 5 note below.
# - Connectives: 並 且 其 而 還 另 (或 added in round 2 but REMOVED in
#   round 5 — was breaking 一或多個 quantifier; see round 5 note)
# - Temporal particle: 時 (added 2026-04-09)
#
# Round 2 Bug B note: 用 was originally added because 第二無線通訊模組用
# was capturing past the head noun, defeating the ordinal guard's
# suffix-strict comparison and producing the misleading suggestion
# "所述第二無線通訊模組用 → 第一無線通訊模組".
#
# Round 5 reversal of round 2 Bug B (2026-04-09): 用 removed because the
# round 2 fix had a worse failure mode — it broke 使用者/使用/應用/適用
# compounds. In 110P000368 Claim 7 the regex captured 該多個使 (stopping
# at 用 in 使用者) instead of 該多個使用者. The trailing-strip + residual
# ≥ 3 guard via _NOUNLIKE_SINGLE_CHAR_SUFFIXES handles trailing 用
# contamination instead: 第二無線通訊模組用 → 第二無線通訊模組 (residual
# 7 ≥ 3, strip allowed); 應用 / 適用 / 使用 (2-char compounds, residual
# 1, strip blocked) preserved. Grep confirms 使用者 ×269, 使用 ×364,
# 應用 ×102, 適用 ×9 in the 10-fixture corpus, all preserved.
#
# Round 5 reversal of round 2 連接ive 或 (2026-04-09): 或 removed
# because the round 2 fix terminated 一或多個 quantifier mid-capture in
# references like 該前一或多個主題標籤 (110P000368). Trailing 或
# contamination is handled by _TRAILING_VERB_DENYLIST instead. Grep
# confirms 或門/或物/或非門/或邏輯 all 0 in the 10-fixture corpus, so
# no compound-noun risk and no exception coordination needed.
#
# NOT excluded (would break legitimate compound nouns):
# - 一 (would break 第一X ordinals — handled by _INTRO_PATTERN's negative
#   lookbehind on bare 一; for _REF_PATTERN_CAPTURE the ordinal forms are
#   protected because they don't begin with 一)
# - 中 上 下 內 外 前 後 (positional g-strip layer; 中 and 後 have
#   trailing-strip + residual guard added in round 5 for fragments like
#   該資料庫中 / 該瀏覽程式產生後)
# - 連 編 識 通 傳 旋 接 設 (verb characters that ARE inside compounds
#   like 連接器, 編碼器, 識別碼, 通訊模組, 傳動件 — handled at the
#   interior-cut layer with an exceptions set)
#
# Upper bound reduced from 16 to 12 because real reference noun phrases
# rarely exceed 8 chars (longest plausible: 第二無線通訊模組 = 8 chars,
# 該所述前述 prefix is stripped before this regex applies). 12 leaves
# headroom for ordinal+qualifier+head-noun compounds without permitting
# the runaway captures observed in the 2026-04-09 smoke test.
# R67 (2026-05-05) sweep: added 由 — relational verb ("composed of"); not a
# noun-internal char in patent claim diction. CN-side empirical attestation
# (CN112271269B `结构由可交联配体`); preventatively added to TW for parity.
# Compound nouns containing 由 (緣由/自由/由來/理由) are non-patent-relevant.
_NOUN_CHARS = r"[^\s，。；：、及與和之的該將能須應皆被於以並且其而還另時在更由]{2,12}"
# R62 (2026-05-05): post-match paren-numeral closure.
# When the captured noun ends with `(<alphanumeric>` (no closing paren)
# AND the next char in claim text is `)`, the {2,12} length limit cut
# inside an open paren — extend match by 1 char to include `)`. Targeted
# fix for the 1015+ TW + 386 CN walker bugs where 至少一個第一子區(104
# truncated to `第一子區(104` after normalize, missing the `)`. Closing
# paren is part of the legitimate element identity (符號說明 entry name).
_PAREN_NUM_TRAIL_RE = re.compile(r"[(（][0-9A-Za-z]{1,5}$")

# R68d (2026-05-06): mid-能 noun capture extension.
#
# 能 is excluded from the _NOUN_CHARS regex character class to prevent
# auxiliary-verb 能 ("can/may") over-capture in `<noun>能<verb>` claim
# constructions. But this exclusion cuts compound nouns like 功能 /
# 性能 / 智能 / 換能器 / 官能基 mid-word — the regex stops at 能 and
# leaves a truncated term (e.g., `<X>管理功` from `<X>管理功能`).
#
# Targeted extension: when raw_noun ends with a known 能-precursor
# character (一個 commonly precedes 能 in compound nouns), extend past
# 能 and continue matching noun chars up to the length cap.
#
# Precursor whitelist is conservative — covers the most-frequent
# noun compounds in patent claim diction:
#   功能 (function), 性能 (performance), 效能 (efficacy),
#   智能 (intelligent), 動能 (kinetic energy), 機能 (mechanism),
#   官能 (functional/sensory), 才能 (capability), 本能 (instinct),
#   勢能 (potential energy), 萬能/全能 (universal),
#   異能 (special ability), 燃能 (combustion energy),
#   換能 (transducer prefix in 換能器).
#
# Mining (supplement_v2): 35 TW walker_fp + 52 CN walker_fp end with
# context_after starting at 能, attesting this is a real over-cut
# class. Auxiliary 能 cases (preceded by non-precursor chars like
# 模組能 / 裝置能) leave precursor check unmatched → no extension.
_NENG_PRECURSORS_TW = (
    "功", "性", "效", "智", "動", "機", "官",
    "才", "本", "勢", "萬", "全", "異", "燃", "換",
)
_NOUN_EXT_RE_TW = re.compile(
    r"[^\s，。；：、及與和之的該將能須應皆被於以並且其而還另時在更由]+"
)


def _extend_neng_compound_tw(
    raw_noun: str, raw_noun_end: int, claim_text: str
) -> tuple[str, int]:
    """Extend raw_noun past 能 if last char is a known 能-precursor.

    Returns (possibly-extended-raw_noun, new-end-position). Handles the
    `<noun>能<head>` compound-noun cut left by the _NOUN_CHARS exclusion
    of 能.
    """
    if not raw_noun or raw_noun[-1] not in _NENG_PRECURSORS_TW:
        return raw_noun, raw_noun_end
    if raw_noun_end >= len(claim_text) or claim_text[raw_noun_end] != "能":
        return raw_noun, raw_noun_end
    # Extend by 能
    raw_noun = raw_noun + "能"
    raw_noun_end += 1
    # Continue matching noun chars from new position, capped at total len 12
    if raw_noun_end < len(claim_text):
        ext_m = _NOUN_EXT_RE_TW.match(claim_text, raw_noun_end)
        if ext_m:
            extra = ext_m.group()
            room = 12 - len(raw_noun)
            if room > 0:
                added = extra[:room]
                raw_noun = raw_noun + added
                raw_noun_end += len(added)
    return raw_noun, raw_noun_end


# R66 (revised 2026-05-05): state-modifier capture extension.
#
# When walker captures `前述<X>` and X is a pure state-modifier
# adjective (island-shape, ring-shape, etc.), the captured term is
# meaningless on its own — drafters write `前述島狀` not as a reference
# but as a qualifier on the following head noun (`前述島狀的奈米片積層體`).
# Without extension, the displayed reference_form is just `前述島狀`,
# which doesn't make grammatical sense. With extension, the user sees
# the full phrase they wrote.
#
# Walker resolution proceeds with the extended term — drafter-consistent
# intro+ref form (both `<state>的<head>`) resolves via exact match;
# drafter using only `<head>` as intro but `<state>的<head>` as ref
# emits a real antecedent finding (the 神秘黑屏哥.docx c10 case).
#
# Constraint: 的 in Chinese has multiple roles — state-modifier
# (`島狀的Y` = "island-shaped Y", Y is head), possessive (`A的B` =
# "A's B", both are nouns), adjective. Extending the capture for
# possessive frames would conflate A (the actual reference) with B
# (a separate noun owned by A) — masking legit drafter errors. Gate
# on captured-term suffix: 狀/形 are unambiguous state suffixes
# (球狀, 環狀, 圓形, 矩形, U形). Possessive owners (容納部/電子裝置/
# 識別資料) end in noun-class suffixes (部/置/料) that the gate
# excludes. Verified against TW harness 2026-05-05: 4 protect:true
# legit_drafting_error labels (容納部/電子裝置/識別資料) all retain
# their findings; 神秘黑屏哥 c10 emits with full
# `前述島狀的奈米片積層體` reference_form.
_STATE_MODIFIER_SUFFIXES_TW = ("狀", "形")
_DE_HEAD_NOUN_RE = re.compile(
    r"的(?P<head>[^\s，。；：、及與和之的該將能須應皆被於以並且其而還另時在更由]{2,12})"
)

# R64 (2026-05-05): display-side ordinal restoration. Walker normalizes
# 第1 → 第一 (Arabic→CJK) for matching parity with intros. For UI display
# the drafter's original ordinal form is preferred — showing 前述第一間隔件
# when the draft uses 前述第1間隔件 causes confusion ("the report says
# something different than my draft"). Pure additive — only restores
# when raw has Arabic AND normalized has CJK at the corresponding
# ordinal position.
_ARABIC_TO_CJK_ORDINAL = (
    ("一", "1"), ("二", "2"), ("三", "3"), ("四", "4"), ("五", "5"),
    ("六", "6"), ("七", "7"), ("八", "8"), ("九", "9"), ("十", "10"),
)


def _restore_original_ordinals(normalized: str, raw: str) -> str:
    """If raw drafter text used Arabic ordinals, restore them in display form.

    Walker normalize_reference_term converts 第1 → 第一 (CJK) for symmetric
    matching against intros. This helper maps the normalized form back to
    the drafter's surface form for UI display, so the user sees the same
    ordinal style they wrote.
    """
    out = normalized
    for cjk, ar in _ARABIC_TO_CJK_ORDINAL:
        if f"第{cjk}" in normalized and f"第{ar}" in raw:
            out = out.replace(f"第{cjk}", f"第{ar}")
    return out

# Introduction patterns — ordered longest-first so 至少一個 / 複數個 are
# matched as single tokens before their shorter prefixes (一 / 複數). The
# regex returns the noun via group 1; the (?:...) alternation in group 0
# carries the quantifier prefix (used by the walker only for diagnostic
# purposes).
#
# The bare ``一`` alternative carries a negative lookbehind for ``第``
# so it does NOT match the ordinal ``第一X`` (otherwise ``第一剛輪`` would
# be parsed as quantifier ``一`` + noun ``剛輪`` and the legitimate
# ``一第一剛輪`` introduction would be mis-attributed to ``剛輪``).
#
# It additionally carries a negative lookahead for ``同`` and ``體`` so
# it does NOT match the idiomatic compound prefixes ``一同`` ("together
# with") and ``一體`` ("as one body"), which are adverbial constructions
# rather than element introductions. Without this guard,
# ``與一柔性軸承一同構成一波產生器`` matched at the ``一`` in ``一同`` and
# captured ``同構成一波產生器`` as group 1, producing the contaminated
# intro ``同構成一波產生器`` (Bug C2 from 2026-04-09 phase8b diagnosis).
#
# Other potentially-idiomatic forms (一側, 一端) are NOT excluded
# because they ARE legitimate noun introductions in many claims
# (一第一端, 一第二端, 一側面). Their contaminated forms (一側設置...,
# 一端透過樞軸...) require lazy regex matching and are deferred to
# Phase 9.
_INTRO_MULTI_QUANTIFIERS = (
    # Round 5 addition: multi-char quantifier "one or more X" — common
    # in JP-origin TW translations. Grep confirms 一或多個 ×59 in
    # 110P000368 + 110P000868 (variants 一或更多 / 一或一個以上 /
    # 一或者多個 all 0). Coordinated with the round 5 removal of 或
    # from _NOUN_CHARS exclusion — without that removal, the regex
    # would still terminate at 或 mid-quantifier even with this entry.
    "一或多個",
    # F4: generalized 至少N個? — covers 至少一個, 至少一, 至少三個,
    # 至少四個, etc. Replaces old 至少一個/至少一 literals.
    r"至少[一二三四五六七八九十百千\d]+個?",
    # F4: bare-two quantifier. 兩個X (with counter) is unambiguous.
    # Bare 兩X (without counter) needs a negative lookahead: 兩端 (both
    # ends) and 兩側 (both sides) are body-part compounds, NOT intros.
    # Corpus: 兩曲柄 ×1 (intro), 兩端 ×3, 兩側 ×2 (all non-intro).
    "兩個",
    r"兩(?![端側])",
    # F4b: bare N個 quantifier (CJK numerals only). Arabic digits
    # excluded — 100個 etc. are measurements, not intros. Safe from
    # N個所述X false positives because F3 Rule 1a discards captures
    # starting with 所述.
    r"[二三四五六七八九十]+個",
    "一個", "一種", "一對",
    "複數個", "多個", "數個",
    "複數",
)
# Weight/molar composition intro: N重量份(至M重量份)的X introduces noun X.
# Units: 重量份, 重量百分比, 莫耳, wt%, mol%.  Only 重量份 appears in the
# current 10-fixture corpus; others included for forward-compat.
_WEIGHT_UNITS = r"(?:重量份|重量百分比|莫耳|wt%|mol%)"
_WEIGHT_COMPOSITION_PREFIX = (
    r"\d+(?:\.\d+)?" + _WEIGHT_UNITS
    + r"(?:至\d+(?:\.\d+)?" + _WEIGHT_UNITS + r")?的"
)
# Definitional intro: 定義為X, 稱為X, 記為X, 表示為X — introduces noun X.
# Optional 一 handles both 定義為X and 定義為一X uniformly.
# Corpus attestation: 定義為 ×22 across 110P000158/110P000631/110P000633;
# 稱為/記為/表示為 have 0 corpus occurrences but are standard TIPO drafting
# patterns included for forward-compat.
# R30 mechanism #10 (2026-05-03): extended definitional prefixes.
# CN R30 mirror in Traditional script.
_DEFINITIONAL_PREFIX = r"(?:定義為|稱為|記為|表示為|此處稱為|此處定義為|簡稱為|命名為|標記為|視為|等同於|又稱為|又稱|亦即)一?"
_INTRO_PATTERN = re.compile(
    r"(?:"
    + _WEIGHT_COMPOSITION_PREFIX
    + r"|" + _DEFINITIONAL_PREFIX
    + r"|(?:" + "|".join(_INTRO_MULTI_QUANTIFIERS) + r"|(?<!第)一(?![同體])))"
    + f"({_NOUN_CHARS})"
)

# Reference: 該/所述/前述/該等/該些 + noun (2-16 CJK characters). Captured
# with named groups so the walker can preserve the original prefix when
# constructing finding records.
_REFERENCE_PREFIXES = ("該等", "該些", "所述", "前述", "該")
_REF_PATTERN_CAPTURE = re.compile(
    r"(?P<prefix>" + "|".join(_REFERENCE_PREFIXES) + r")"
    + f"(?P<noun>{_NOUN_CHARS})"
)


# ── Phase 8b TW walker — reference-term normalization (ADR-095) ──────────
#
# Three sequential transformations applied before computing antecedent
# matches or did-you-mean similarity scores:
#
#   1. Trailing-verb strip (parser correctness fix, ADR-095 Rule 1)
#   2. Leading-quantifier strip (ADR-095 Rule 2)
#   3. Number-neutral antecedent matching (implicit in symmetric stripping)
#
# ``normalize_reference_term`` composes all three for the reference side;
# ``normalize_candidate_intro`` applies the same normalization to intro
# candidates. Both sides are stripped symmetrically so number-neutral
# matching works (複數外齒狀結構 ↔ 該外齒狀結構 → both normalize to 外齒狀結構).

# ADR-095 Rule 1: trailing-verb denylist.
# Ordered longest-first so greedy matching strips 還包含 as one token
# before 還 strips as another. Tuple form is required because
# ``sorted(..., key=len, reverse=True)`` is applied once at import time.
_TRAILING_VERB_DENYLIST: tuple[str, ...] = tuple(sorted(
    (
        # === R32 (2026-05-04) — passive trailing residue ===
        # CN parity (added to _TRAILING_VERB_DENYLIST_CN same round).
        # 被: passive marker. Compound nouns ending in 被 are vanishingly
        #   rare in TIPO patent claims; suffix-position is uniformly verb.
        #
        # NOT included: 通訊/通信. Empirically silenced 7 protect:false
        # legit_drafting_error labels in CN115398975B c1-8 where bare
        # `所述側鏈路中繼通訊` is genuinely ambiguous (no Pattern A intro
        # exists); 通訊 is the HEAD noun in compound `側鏈路中繼通訊`,
        # not a verb. Verb-mode vs noun-mode disambiguation is out of
        # R32 scope.
        "被",
        # === R32 (2026-05-04) — verb-suffix trailing residues ===
        # Cluster-mined from round-1 TW corpus: each entry has ≥30
        # walker_fp findings AND 0 legit_drafting_error findings (safe
        # silence per ensemble verdict + Phase 2c noise-floor analysis).
        # Compound-noun risk audited: each verb appears at PREFIX
        # position in noun compounds, not suffix.
        "發送",  # 40 walker_fp / 0 legit. `<noun>發送` over-capture.
        "提供",  # 38 walker_fp / 0 legit.
        "獲得",  # 31 walker_fp / 0 legit.
        "隔開",  # 32 walker_fp / 0 legit. (`<noun>隔開` separator verb)
        "延伸",  # 44 walker_fp / 0 legit. Risk: 延伸線 (extension line)
                # at PREFIX position, suffix-position is uniformly verb.
        "經組態",  # 57 walker_fp / 0 legit. Passive participle ("configured").
        # NOTE: 發光 not added — `發光二極體` (LED) suffix risk too high
        # for confident strip without per-claim context.
        # Verb suffixes
        "包含", "包括", "含有", "具有", "係", "為", "是", "設有", "具備",
        # Preposition-verbs
        "通過", "經由", "藉由", "基於", "透過", "根據", "依據",
        # Conjunction starters (multi-char longest)
        "還包含", "還包括",
        "並且", "以及",
        "並", "且", "其", "其中", "還", "另",
        # Partial captures — single-character fragments that indicate the
        # regex stopped mid-word. Ordered after multi-char tokens.
        "包", "通", "經", "藉",
        # Reference-form prefix fragments stranded by interior cuts.
        # When clean_noun_phrase_tw cuts ``電子組件所包含`` at 包含, the
        # leading-of-the-stripped-prefix character ``所`` is left behind
        # as a stray. Same for 前 (start of 前述). 所-terminated
        # compound nouns (研究所, 場所, 事務所) are protected by the
        # residual ≥ 3 guard in clean_noun_phrase_tw via
        # _NOUNLIKE_SINGLE_CHAR_SUFFIXES below; 前 has no such guard
        # because it appears overwhelmingly as a prefix in patent
        # Chinese, not a suffix (see the comment on the constant).
        "所", "前",
        # Resultative particles (added 2026-04-09)
        "到", "出",
        # === Added 2026-04-10 F2 ===
        # 介: verb particle from 介於 ("falls between"). Corpus
        #     attestation: 第一夾角介於 on 110P000158 c1/c3. Compound
        #     nouns with medial 介 (使用者介面, 操作介面, 介電) have 介
        #     in non-trailing position — unaffected by trailing strip.
        #     中介裝置 (介 at pos 1) has residual 中 (1 char < 3),
        #     protected by general residual guard.
        "介",
        # === Added 2026-04-09 round 4 ===
        # 位 fragment of truncated 位於 verb (regex stopped at 於 which
        # is in the _NOUN_CHARS exclusion class). Compound nouns
        # 位置/位元/數位/第一位/第二位 are protected by the residual ≥ 3
        # guard via _NOUNLIKE_SINGLE_CHAR_SUFFIXES below.
        "位",
        # === Added 2026-04-09 round 5 ===
        # 或: connective ("or"). Removed from _NOUN_CHARS in round 5 to
        #     unblock the 一或多個 quantifier; trailing 或 contamination
        #     (該全世界或) is handled here instead. Grep confirms
        #     或門/或物/或非門/或邏輯 all 0 in the 10-fixture corpus —
        #     no compound-noun risk, no residual guard needed (general
        #     residual ≥ 1 floor suffices).
        "或",
        # 中: positional particle ("inside/within"). Stranded at the
        #     trailing edge of captures like 該資料庫中. Compound forms
        #     中心/中央/中文/中段/中部/中層/中環/中間 are 2-char with 中
        #     at position 0; protected by residual ≥ 3 guard via
        #     _NOUNLIKE_SINGLE_CHAR_SUFFIXES below. Grep: 中心 ×93,
        #     中央 ×10, 中文 ×30 — all preserved.
        "中",
        # 後: positional particle ("after/behind"). Stranded at the
        #     trailing edge of captures like 該瀏覽程式產生後. Compound
        #     forms 後輪/後方/後續 (and the unobserved 後端/後蓋/後座)
        #     are 2-char with 後 at position 0; protected by residual
        #     ≥ 3 guard. Grep: 後輪 ×11, 後方 ×1, 後續 ×14 — all
        #     preserved. Note: 後 also appears as a leading qualifier
        #     in 後一X patterns ("the next X"), handled by
        #     strip_leading_qualifier — different code path, no conflict.
        "後",
        # 用: preposition ("use/for"). Removed from _NOUN_CHARS in
        #     round 5 (reversal of round 2 Bug B fix); trailing 用
        #     contamination (第二無線通訊模組用 → 第二無線通訊模組)
        #     handled here with residual ≥ 3 guard. Compound forms
        #     使用/應用/適用/作用/信用/通用 are 2-char and protected
        #     by the guard (residual after stripping ≤ 1, < 3).
        #     使用者 (3-char) is protected at the regex level —
        #     it doesn't END in 用, so the trailing strip never
        #     applies to it. Grep: 使用 ×364, 應用 ×102, 適用 ×9,
        #     作用 ×2, 使用者 ×269 — all preserved.
        "用",
        # === Round 5 cascade additions ===
        # Surfaced after the round 5 removal of 用/或 from _NOUN_CHARS
        # unblocked the regex to capture longer noun spans that include
        # trailing positional particles 上/內 (previously hidden because
        # the regex stopped at 用 in 使用者介面上 / at 或 in 全世界或地域內).
        #
        # 上: positional particle ("on/above"). Stranded at the trailing
        #     edge of captures like 該使用者介面上 (110P000368). Compound
        #     forms 上方/上端/上述/上層/上部 are 2-char with 上 at
        #     position 0; protected by residual ≥ 3 guard via
        #     _NOUNLIKE_SINGLE_CHAR_SUFFIXES. Grep: 上方 ×20, 上端 ×65,
        #     上述 ×45, 上下 ×3 — all preserved.
        "上",
        # 內: positional particle ("inside/within"). Stranded at the
        #     trailing edge of captures like 該地域內 (110P000368).
        #     Compound forms 內部/內側/內徑/內側面 have 內 at position 0
        #     of a 2- or 3-char compound; protected by residual ≥ 3
        #     guard. Grep: 內部 ×40, 內側 ×76, 內徑 ×3, 內側面 ×2 —
        #     all preserved.
        "內",
        # Adverbs that ended up trailing after interior cut
        "分別", "皆",
        # Positional particle (parallel to 時)
        "處",
        # === Added 2026-04-10 F3 ===
        # 至: preposition ("to/until") from V至 patterns like 解鎖指令至
        #     (110P000868 c8) and 傳送至 (109P001046 c12). Corpus safety:
        #     min residual 6 across 65 occurrences. No compound-noun risk.
        "至",
        # 依序: adverb ("in order") from 第二方向依序 (110P000633 c10/c19).
        #     Corpus safety: min residual 15 across 12 occurrences. No
        #     compound-noun risk.
        "依序",
        # 擷取: verb ("capture/acquire") from 影像擷取裝置擷取
        #     (110P000633 c3 after ref-marker truncation). Corpus safety:
        #     min residual 2 (影像擷取 → 影像). Protected by residual ≥ 3
        #     guard via _NOUNLIKE_GUARDED_SUFFIXES below — 影像擷取 (4 chars,
        #     residual 2 < 3) preserved, 影像擷取裝置擷取 (8 chars, residual
        #     6 ≥ 3) stripped.
        "擷取",
        # === Phase F F2 — Added 2026-04-17 ===
        # 來自一: preposition + quantifier fragment. Observed in
        #     tw_copula_tiers c2 (synthetic) `所述輸入訊號來自一感測器模組`.
        #     Walker over-captures `輸入訊號來自一` as term. No compound-
        #     noun risk: 來自 is always prep-verb in TW drafting; the
        #     trailing 一 quantifier only appears in prepositional phrases.
        "來自一",
        # === Phase 8b R7 — Added 2026-04-30 (Claire-draft audit) ===
        # 較: comparative verb ("compared to"). Observed across c2/c5/c7/
        #     c9 of the semiconductor draft as the head of comparison
        #     clauses (`前述矽鍺層較前述矽層後退`, `較構成前述n型通道層之矽鍺
        #     層的膜厚更厚`). 較 doesn't occur as a noun-position suffix in
        #     any TW patent diction surveyed; corpus grep returns 0
        #     compound-noun hits (比較 / 較量 etc. all have 較 at position
        #     [-1] of a 2-char compound, residual 1 < 3, no protection
        #     needed because they're not flagged as elements anyway).
        "較",
        # 厚膜化: process verb-suffix ("thicken / film-ize"). Observed in
        #     c13 of the Claire draft (`使前述p型通道層厚膜化`). Multi-char
        #     specific token avoids over-stripping the productive 化-suffix
        #     (氧化/文化/變化 unaffected since they don't end in 厚膜化).
        "厚膜化",
        # === R29 (2026-05-03) — round-1 corpus over-capture extensions ===
        # Conservative extension only. Excludes verbs that double as common
        # noun endings (處理/配置/形成/驅動/儲存/傳輸/連接/選擇/標識/識別/
        # 圍繞 — last one removed after tw_adversarial_negatives c2 `機殼圍繞`
        # protect:true label hit). Kept additions are clearly-verb multi-
        # char phrases without noun-suffix ambiguity. Mirror of CN R29
        # trim-verb extensions, adapted to Traditional script. 測量 / 覆蓋
        # already in main set above; not duplicated.
        "代表", "連同", "表示", "移動",
        "檢測", "收集", "輸送",
        "釋放", "操控", "掃描",
        "分離", "比較", "判斷", "決定", "分析",
        # === R63 (2026-05-05) — 神秘黑屏哥.docx audit ===
        # Adverbs / adjectives over-captured at trailing position.
        # Multi-char specific compounds first (longest-first sort):
        # - 不同介電率: modifier+noun (`第一間隔件不同介電率的絕緣膜`).
        #   Walker captured this as part of element-name span; should
        #   strip the modifier+noun suffix to recover element identity.
        # - 不同: pure adjective, never noun-position-suffix in TW patent
        #   diction. 不同點 / 不同處 captured properly via mid-position;
        #   trailing 不同 is uniformly walker over-capture.
        # - 僅: adverb "only/merely", never part of noun.
        # Residual ≥ 2 implicit guard: len < 2 emit-time filter (R32)
        # protects 1-char residuals from leaking through.
        "不同介電率",
        "不同",
        "僅",
        "包括以下", "執行以下", "進行以下",
        "執行以下操作", "執行以下操",
        # R60 (2026-05-05): TW 執行 verb-suffix from cluster TAIL|TW|經量化
        # (TWI890747B 36 wfp on `經量化權重資訊執行...`). 來執行 / 執行一或多
        # / 執行第二推 / 執行 over-captures.
        "來執行", "執行一或多", "執行第二推", "執行",
        # === R30 (2026-05-03) — sample-derived adverbial / adjectival trims
        # 進一步: adverbial fragment of 進一步包括/進一步具有.
        # 相關聯: adjectival fragment of <noun>相關聯的. Existing 相關 + 有關
        # catch 2-char form; 3-char form needs explicit.
        "進一步", "相關聯",
    ),
    key=len,
    reverse=True,
))

# Noun-like single-char trailing suffixes that get the residual ≥ 3 guard
# in clean_noun_phrase_tw. These are the denylist members where the
# 1-char form is itself a productive noun-suffix morpheme rather than a
# verb fragment, so a too-eager strip damages real compound nouns.
#
# 所 stays here because its compound-noun forms (研究所, 場所, 事務所,
# 避難所) are all position-[-1] suffixes of the compound.
#
# 位 added 2026-04-09 round 4: 位 appears as the fragment of a
# truncated 位於 verb when the regex stops at 於 (which is already in
# the _NOUN_CHARS exclusion class). Adding it to trailing strip with
# the residual ≥ 3 guard catches the truncation
# (第二容置空間(225)位 → 第二容置空間(225)) while preserving compound
# forms 位置/位元/數位/第一位/第二位 because their residual after
# stripping 位 would be ≤ 2 (位置 → 1, 第一位 → 2). Grep confirmed
# 位置 ×392, 數位 ×197, 第一位 ×3, 第二位 ×2 in the 10-fixture corpus,
# all preserved by the guard.
#
# 前 is NOT in this set despite being a noun morpheme in 以前/之前,
# because those grammatical adverbs are rare in claim text while 前
# appears overwhelmingly as a PREFIX in mechanical patent terms
# (前端, 前述, 前方, 前蓋, 前緣). Keeping 前 in this set would preserve
# 齒輪前 fragments that should strip to 齒輪. Compound prefixes like
# 前端 are unaffected because they don't end in 前 — only the
# trailing-strip codepath cares about this set. The 以前/之前 over-strip
# (以/之) is accepted as a known limit; a Phase 9 follow-up may
# generalize this set into a compound-noun allowlist that handles
# both 所-suffix and 前-suffix cases without the prefix/suffix conflict.
#
# 中 added 2026-04-09 round 5: positional particle ("inside/within")
# stranded at the trailing edge of captures like 該資料庫中. Compound
# forms 中心/中央/中文 (and the absent-from-corpus 中段/中部/中層/中環/
# 中間) all have 中 at position 0 of a 2-char compound, so residual after
# stripping is ≤ 1 (中心 → 心 → 1, 中央 → 央 → 1) — protected by
# residual ≥ 3 guard. Grep confirms 中心 ×93, 中央 ×10, 中文 ×30 in
# the 10-fixture corpus, all preserved.
#
# 後 added 2026-04-09 round 5: positional particle ("after/behind")
# stranded at the trailing edge of captures like 該瀏覽程式產生後. Compound
# forms 後輪/後方/後續 (and the absent-from-corpus 後端/後蓋/後座/後背/
# 後門) all have 後 at position 0 of a 2-char compound, so residual after
# stripping is ≤ 1 — protected by the same guard. Grep: 後輪 ×11,
# 後方 ×1, 後續 ×14 in the corpus, all preserved. Note that 後 ALSO
# appears as a leading qualifier in patterns like 後一X ("the next X"),
# handled by strip_leading_qualifier on the leading-position codepath
# — different from this trailing-position guard, no conflict.
#
# 用 added 2026-04-09 round 5: preposition ("use/for"). Removed from
# _NOUN_CHARS in round 5 (reversal of round 2 Bug B fix) so that
# 使用者 compounds capture cleanly. Trailing 用 contamination
# (第二無線通訊模組用 → 第二無線通訊模組, residual 7 ≥ 3) handled
# here with the residual ≥ 3 guard. Compound forms 使用/應用/適用/
# 作用/信用/通用 are all 2-char with 用 at position [-1]; residual
# after stripping is 1 → preserved. 使用者 (3 chars) does NOT end
# in 用 so the trailing strip never applies. Grep: 使用 ×364,
# 應用 ×102, 適用 ×9, 作用 ×2, 使用者 ×269 — all preserved.
#
# 上 added 2026-04-09 round 5 cascade: positional particle ("on/
# above") stranded at the trailing edge of captures like 該使用者介面上.
# Surfaced after the round 5 用 removal unblocked the regex past 用
# in 使用者介面上 — pre-cascade the regex stopped at 用 and 該使用者介面上
# was never captured at all. Compound forms 上方/上端/上述/上層/上部
# all have 上 at position 0 of a 2-char compound — protected by the
# trailing-strip's position check (endswith fires only at position -1),
# NOT by the residual guard. Grep: 上方 ×20, 上端 ×65, 上述 ×45, 上下 ×3
# in the corpus, all preserved. Listed in _NOUNLIKE_RELAXED_SUFFIXES
# (residual ≥ 2 instead of ≥ 3) — see below for why.
#
# 內 added 2026-04-09 round 5 cascade: positional particle ("inside/
# within") stranded at the trailing edge of captures like 該地域內.
# Surfaced after the round 5 或 removal unblocked the regex past 或
# in 全世界或地域內. Compound forms 內部/內側/內徑 have 內 at position 0
# of a 2-char compound (protected by position check, not residual guard);
# 內側面 is 3-char with 內 at position 0 (same protection). Listed in
# _NOUNLIKE_RELAXED_SUFFIXES — see below.
_NOUNLIKE_SINGLE_CHAR_SUFFIXES: frozenset[str] = frozenset(
    {"所", "位", "中", "後", "用", "上", "內",
     # F3: 擷取 (2-char) — despite the set name, the residual guard
     # mechanism works with any length. 影像擷取 (4 chars, residual 2)
     # protected; 影像擷取裝置擷取 (8 chars, residual 6) strips correctly.
     "擷取",
     # === Phase 8b R7 — Added 2026-04-30 (Claire-draft audit) ===
     # 作: verb-fragment of 作為 ("treat as") that strands when the noun-
     #     class regex stops before 為 (which is in the _NOUN_CHARS
     #     exclusion list). Observed across c11/c13/c14/c15 of the Claire
     #     draft (`前述半導體通道層作 為n型通道層`, `前述矽鍺層作為p型通道層`).
     #     Compound nouns ending in 作 (操作/工作/動作/作業/作品): 操作/
     #     工作/動作 are 2-char with residual 1 < 3 → protected; 作業 / 作品
     #     end in 業 / 品 not 作 — not affected by the trailing strip.
     #     Grep across TW corpus: 操作 ×high, 工作 ×low, all preserved.
     "作",
     # 使: causative particle / verb fragment. Observed in c15 of the
     #     Claire draft (`以前述閘極電極覆蓋使前述矽層薄膜化`). Claim text
     #     usage is overwhelmingly causative ("cause X to Y"), so trailing
     #     使 is verb-fragment territory. Compound nouns ending in 使
     #     (大使/天使/特使/驅使) are 2-char (residual 1 < 3 → protected) or
     #     end in 使 with productive prefix that residual ≥ 3 still allows
     #     to strip when justified. No corpus collisions in TW or CN
     #     fixture pool.
     "使",
     # === R68 (2026-05-06) — supplement_v2 mining ===
     # 來: verb tail particle in `所述<noun>來自X` ("the <noun> comes from
     #     X") constructions. Walker captures `<noun>來自一` then strips
     #     `自一` quantifier remnant, leaving `<noun>來` as the term.
     #     Bare 來 is never an antecedent-noun ending. Compound nouns
     #     ending in 來 (將來/由來/未來/從來) are temporal/idiomatic and
     #     not typical claim antecedent references. Mining surfaced
     #     25 TW walker_fp findings with this trailing pattern across
     #     supplement_v2 corpus. Added to relaxed-guard set below for
     #     residual ≥ 2 (handles 3-char `影像來` → `影像`).
     "來",
     # 對: preposition ("toward/to/regarding") trailing in `<noun>對X`
     #     constructions. 134 TW walker_fp findings end in 對
     #     (e.g., `驗證模塊對`, `銀行帳務平台對`). Default residual ≥ 3
     #     guard protects 3-char compound nouns where residual is 2
     #     (`所述應對` 等). CN parity already in
     #     _NOUNLIKE_SINGLE_CHAR_SUFFIXES_CN as 对.
     "對",
     # 向: preposition ("toward") trailing. 85 TW walker_fp findings
     #     end in 向 (`消費者操作單元向`, `輸出節點流向`). Default
     #     residual ≥ 3 protects 3-char compounds (所述方向 → residual 2,
     #     not stripped). 方向 / 流向 / 走向 / 趨向 stay safe.
     "向",
     # 自: preposition ("from") / pronoun particle ("self") trailing.
     #     32 TW walker_fp findings end in 自 (`<noun>各自`, `<noun>來自`).
     #     Default residual ≥ 3 protects 3-char compounds. Note 各自
     #     residue further requires 各 strip downstream (not yet covered).
     "自"}
)

# Relaxed-guard subset: members of _NOUNLIKE_SINGLE_CHAR_SUFFIXES that
# get residual ≥ 2 instead of the default ≥ 3. The default ≥ 3 protects
# 3-char compounds where the suffix sits at position -1 of a productive
# noun (研究所, 第一位). The relaxed ≥ 2 lets 3-char positional fragments
# (地域內 → 地域, 範圍內 → 範圍, 基板上 → 基板, 面上 → 面) strip correctly
# while still protecting 2-char productive compounds ending in 上/內
# (室內/國內/海上/桌上 — residual 1, blocked by ≥ 2).
#
# Why 上/內 specifically: their productive 2-char compound forms put the
# particle at position 0 (上方/上端/內側/內部), so the trailing-strip
# never even considers them — the position check alone protects those.
# At position -1 they appear almost exclusively as positional fragments
# in patent claim text ("within the X" / "on the X"), not as standalone
# nouns. Corpus grep for 室內/國內/海上/桌上 etc. on the 10-fixture set
# returned 0 hits; 範圍內 ×3 and 基板上 ×4 are the only 3-char position-(-1)
# matches and both should strip.
#
# 所/位/中/後/用 stay at the strict ≥ 3 guard because they DO have
# productive 3-char compounds ending in the suffix (研究所, 第一位) or
# because the corpus is too small to confidently relax (中/後/用).
# R31 (2026-05-03): added 中 to relaxed (≥2 residual instead of ≥3) to
# match CN parity. Round-1 corpus shows 系統中 / 區段中 / 範圍中 etc. are
# common over-capture shapes where the locative 中 should strip leaving
# 2-char head (系統/區段/範圍). 中 standalone or as 2-char compound prefix
# (中央/中文) is protected by the 0-position check (cut at idx > 1).
_NOUNLIKE_RELAXED_SUFFIXES: frozenset[str] = frozenset({"上", "內", "中", "來"})

# ADR-095 Rule 2: leading quantifiers (stripped from both sides).
# Ordered longest-first so 至少一個 is stripped as a single token before
# 至少一 is stripped.
_LEADING_QUANTIFIER_DENYLIST: tuple[str, ...] = tuple(sorted(
    (
        # Round 5 addition: 一或多個 multi-char quantifier (parallel to
        # _INTRO_MULTI_QUANTIFIERS). Stripped from both reference and
        # intro sides so 該前一或多個主題標籤 ↔ 該主題標籤 normalize to
        # the same head noun.
        "一或多個",
        "至少一個", "至少一",
        "一個", "一種", "一對",
        "複數個", "多個", "數個",
        "複數",
        "一",
        # Round 6 addition: 各 distributive quantifier ("each"). TIPO
        # drafters use 前述各X / 該各X for "each X" references when a
        # parent claim introduces an indexed family (各p型通道層, 各n型
        # 電極). Reference-side normalization must strip 各 so the bare
        # head noun matches the upstream intro. Symmetric strip on the
        # intro side is harmless because 各X intros are unattested at
        # claim-body level (the indexed family is introduced as bare
        # noun, then references add the distributive 各 prefix).
        "各",
        # === R30 (2026-05-03) — extended plural-quantifier bridging ===
        # CN R30 mirror in Traditional script. When a parent claim
        # introduces 多種X / 若干X and a dependent references 該X (singular),
        # symmetric strip bridges per TIPO drafting practice. Multi-char
        # additions only (no single-char to avoid noun-compound collision).
        "若干個", "若干",
        "一些", "某些",
        "多種", "多類", "多組", "多對",
        "至少兩個", "至少兩", "兩個", "兩種",
    ),
    key=len,
    reverse=True,
))

# Reference-form prefixes: stripped from reference terms only. The walker
# strips these before applying the leading-quantifier pass, so 該第一電極
# becomes 第一電極 (quantifier strip leaves 第一電極 since 第一 is not in
# _LEADING_QUANTIFIER_DENYLIST — ordinals are part of the head noun).
_REFERENCE_FORM_PREFIXES: tuple[str, ...] = tuple(sorted(
    ("該等", "該些", "所述", "前述", "該"),
    key=len,
    reverse=True,
))

# Plural reference-form prefixes — a strict subset of reference-form
# prefixes that explicitly mark plural reference. These are used by the
# strict_plural_reference_matching escape hatch (default False per
# ADR-095) and by the ``detect_plural_reference`` helper below.
_PLURAL_REFERENCE_PREFIXES: tuple[str, ...] = tuple(sorted(
    ("該等", "該些", "前述複數", "所述複數", "所述多個"),
    key=len,
    reverse=True,
))


# Interior-boundary tokens — when one of these multi-char tokens appears
# mid-noun the walker truncates the noun at that point. Distinct from
# ``_TRAILING_VERB_DENYLIST`` (suffix stripping); these are interior cuts
# applied BEFORE the trailing-strip pass. Necessary because the regex
# noun capture is greedy: ``該底座設有一孔洞`` captures
# ``底座設有一孔洞``, and the trailing-strip alone cannot recover
# ``底座`` because the trailing token is ``孔洞`` (a real noun, not a
# verb).
#
# Two families:
#   1. Verb tokens (設有/包含/...) — split greedy noun spans at the verb.
#   2. Reference-form prefixes (所述/前述/該等/該些) — split greedy noun
#      spans when a downstream reference begins inside the captured
#      window. The single-char 該 is handled in the regex character
#      class itself; multi-char prefixes need this interior cut because
#      the regex would otherwise consume past them.
#
# In-claim verbs like 驅動/讀取/輸出/連接 are NOT in this set: they
# legitimately appear inside compound nouns (動力輸出系統, 連接器, 數據輸出
# 介面). The walker handles those cases via longest-intro-prefix matching
# instead — see ``check_antecedent_basis``.
#
# Ordered longest-first so 設有/包含 strip before single-char tokens.
_INTERIOR_VERB_BOUNDARIES: tuple[str, ...] = tuple(sorted(
    (
        # === Phase 8b R7 — Added 2026-04-30 (Claire-draft audit) ===
        # 覆蓋: process verb ("cover"). Observed in c10/c13/c15 of the
        #     Claire draft (`被前述閘極電極覆蓋的前述p型通道層`,
        #     `以前述閘極電極覆蓋前述厚膜化之前述p型通道層`,
        #     `以前述閘極電極覆蓋使前述矽層薄膜化`). 覆蓋層 (cover layer) and
        #     覆蓋率 (coverage rate) have 覆蓋 at position 0 of a longer
        #     compound — the interior-cut leaves text BEFORE the verb, so
        #     position-0 occurrences are no-op (idx + offset == 0, fails
        #     the > 1 gate). No compound-noun risk.
        "覆蓋",
        # 夾持: mechanical verb ("clamp / hold"). Observed in c5/c6/c7 of
        #     the Claire draft (`端部被矽層夾持`, `被前述矽層夾持的端部`).
        #     Compound forms 夾持器 / 夾持機構 have the verb at position 0
        #     of a longer compound — same > 1 gate behavior; no risk.
        "夾持",
        # 進行: process verb ("perform / carry out"). Observed in c12 of
        #     the Claire draft (`進行蝕刻`, `前述矽鍺層進行膜厚減少`). CN
        #     walker has 进行 in `_INTERIOR_VERB_BOUNDARIES_CN` since R7;
        #     TW was missing the parity entry. No compound-noun risk:
        #     進行式 / 進行曲 are music/grammar terms, 0 corpus hits in
        #     patent claim text.
        "進行",
        # 作為: copula ("treat as / serve as"). Observed in c11/c13/c14/
        #     c15 of the Claire draft (`將前述矽鍺層作為p型通道層露出`,
        #     `將前述半導體通道層作為n型通道層露出`). Multi-char specific
        #     prevents over-stripping single-char 作 (handled separately
        #     via _NOUNLIKE_SINGLE_CHAR_SUFFIXES residual ≥ 3). 作為 only
        #     appears as the X-作為-Y copula construction in TW patent
        #     drafting; no compound-noun collision.
        "作為",
        # 露出: process verb ("expose"). Observed in c11/c13/c14/c15 of
        #     the Claire draft (`作為p型通道層露出的工程`, `將前述矽鍺層
        #     作為p型通道層露出之工程中`). Required for F12 Tier A's
        #     `作為Y` capture to truncate at 露出 cleanly. 露出層 / 露出器
        #     / 露出口 / 露出面 absent from TW corpus per grep (`露出` is
        #     always V-V compound, not noun-prefix); no compound-noun
        #     collision.
        "露出",
        # === Phase F F2 — Added 2026-04-17 ===
        # 選自由: Markush group verb phrase ("selected from"). Observed in
        #     tw_markush c3 (synthetic) `該模組選自由語音識別模組、...` where
        #     walker over-captures `模組選自由語音` as term. Interior cut at
        #     選自由 reduces capture to 模組 (clean NP). No compound-noun
        #     risk: 選自由 only appears in Markush claim drafting.
        "選自由",
        # 滿足式: verb + formula-reference head. Observed in
        #     tw_formula_reference c4 (synthetic) `所述電容值滿足式(R1)` where
        #     walker captures through the verb+式(N) span. Interior cut at
        #     滿足式 reduces capture to 電容值. No compound-noun risk.
        "滿足式",
        # === Phase F F4 — Added 2026-04-17 (browser-verification retrospective) ===
        # 旋動: rotate/pivot verb. Observed in spec1 claim 1
        #     `一鉸鏈部旋動自如地安裝於所述蓋本體` where _INTRO_PATTERN greedy-
        #     captures `一鉸鏈部旋動自如地安裝` past the noun boundary.
        #     Interior cut at 旋動 reduces intro capture to 鉸鏈部
        #     (clean NP). Corpus scan: 旋動器/旋動軸/旋動件 all 0 across
        #     11 real fixtures — no compound-noun risk.
        "旋動",
        # 自如: adverbial modifier ("freely", as in 旋動自如). TIPO
        #     drafting idiom X-V-自如 means "can V freely". Observed in
        #     spec1 claim 1 and many hinge/mechanical claims. No
        #     compound-noun risk: 自如 only appears as V-complement in
        #     patent drafting.
        "自如",
        # === Existing entries (preserve) ===
        "設有", "包含", "包括", "具有", "含有", "具備",
        "係為", "係於", "為", "是", "係",
        # Reference-form prefixes (multi-char)
        "所述", "前述", "該等", "該些",

        # === Added 2026-04-09 from smoke-test fixtures ===
        # Verb phrases (longest-first; exact tokens observed in fixtures)
        "傳送接收到", "傳送一顯示影像資", "輸出一解鎖指令至",
        "通訊連接時", "電性連接", "被帶動而向", "分別定義",
        "無法存取", "設置有", "拔除時",
        "連接一第一電子裝", "擷取一使用者",

        # 3-char verb phrases
        "電性連", "所施予", "將帶動", "被帶動",

        # 2-char unambiguous verbs (NOT noun-internal in any common
        # compound observed in 2026-04-09 fixtures)
        "對應", "相對", "相反", "響應", "解鎖",
        "讀取", "寫入", "計算", "處理", "感測",
        "偵測", "監控", "監測", "調整", "修改",
        "更新", "刪除", "增加", "減少", "選擇",
        "決定", "判別", "辨識", "驅動",

        # === Added 2026-04-09 round 2 (Bug A1 + C1 from diagnosis) ===
        # Verbs observed in real fixtures during Phase 8b round 1 smoke
        # test that contaminated reference and intro captures. Each was
        # risk-reviewed against _INTERIOR_CUT_EXCEPTIONS membership and
        # against the 10 fixtures' noun compounds:
        #   定義: not interior to any common compound — safe.
        #   啟始: not interior — safe.
        #   判斷: 判斷器 not present in fixtures — safe.
        #   持續: not interior — safe.
        #   涵蓋: not interior — safe.
        #   放大: 放大器 IS present (108P001015 ×1) — added to
        #         exceptions below.
        #   存取: not interior — safe.
        #   構成: not interior to common compounds — safe.
        #   設置: catches cases where 設置有 isn't present — safe.
        #   透過/通過/經由/藉由: preposition-verbs (already in trailing
        #         denylist) — adding to interior boundaries cuts greedy
        #         capture mid-phrase, parallel to 設有/包含 split.
        #   基於/根據/依據: connective preposition-verbs — same.
        #   染色: 染色墨水 IS present (110P000633 ×40) — added to
        #         exceptions below as a coordinated change.
        #   識別: 識別碼/識別資料/識別資訊/識別號/識別子 are already in
        #         _INTERIOR_CUT_EXCEPTIONS from Phase 8b round 1.
        #         Commit 1's prefix-aware protection lets cuts fire on
        #         the remainder past the protected compound, so a
        #         capture like 識別資料識別 preserves 識別資料 via the
        #         exception prefix and cuts at the second 識別 via the
        #         remainder search.
        #   傳送: 傳送器 is already in _INTERIOR_CUT_EXCEPTIONS — same
        #         prefix-aware protection logic applies.
        #   接收: 接收器 is already in _INTERIOR_CUT_EXCEPTIONS — same.
        "定義", "啟始", "判斷", "持續", "涵蓋", "放大", "存取",
        "構成", "設置",
        "透過", "通過", "經由", "藉由",
        "基於", "根據", "依據",
        "染色",
        "識別", "傳送", "接收",

        # === Added 2026-04-09 round 3 (round 2 spot-check residuals) ===
        # Verbs visible in round 2 residual contamination with no
        # compound-noun risk per the 10-fixture grep:
        #   到: resultative particle ("arrive at"). 到器 absent (0).
        #       到達 present (7) but always as verb compound
        #       (狀態到達限制條件, 扭力到達預定扭力時) — cutting at 到
        #       correctly extracts the head noun in those cases.
        #   形成: "to form". 形成器/形成物 absent (0).
        #   鎖合: "to lock". 鎖合器/鎖合件 absent (0).
        #   傳輸: "to transmit". 傳輸器/傳輸線/傳輸帶 absent (0).
        "到", "形成", "鎖合", "傳輸",

        # === Added 2026-04-09 round 4 (round 3 spot-check residuals) ===
        # Each verb risk-reviewed against the 10-fixture grep:
        #   連接: 連接器/連接部/第一連接部/第二連接部/第三連接部
        #         already in _INTERIOR_CUT_EXCEPTIONS (round 1; grep
        #         confirms 連接器 ×4, 連接部 ×72, 第一/第二/第三連接部
        #         ×13/13/21 in 109P001046). Round 2's prefix-aware
        #         protection covers all 連接X compounds — a captured
        #         X連接部連接 preserves X連接部 via the exception
        #         prefix and cuts at the second 連接 via the remainder
        #         search (load-bearing test: 第一連接部連接 → 第一連接部).
        #   旋轉: 旋轉編碼器 already in exceptions (round 1; grep
        #         confirms ×5 in 110P000641). Other 旋轉X compounds
        #         (旋轉軸/件/器/盤/座) absent (0) per grep — no new
        #         exceptions needed.
        #   帶動: 帶動輪 ×2 in 110P000641 per grep — added to
        #         _INTERIOR_CUT_EXCEPTIONS in round 4 block below.
        #         帶動器/帶動件 absent (0).
        #   篩選: 篩選器/篩選件/篩選網 all absent (0) per grep — no
        #         compound-noun risk, no new exceptions needed.
        "連接", "旋轉", "帶動", "篩選",

        # === Added 2026-04-09 round 5 (110P000368 manual review residuals) ===
        # 區分: "to distinguish/divide" verb in method claims. Observed
        #       in 110P000368 Claim 6 contaminating 該地域區分 → should
        #       cut at 區分 to extract 該地域. Risk-reviewed:
        #       區分器/區分件/區分碼 all absent (0) in the 10-fixture
        #       grep — no exception coordination needed.
        "區分",

        # === Added 2026-04-09 round 5 cascade ===
        # Verbs that became visible after the round 5 用/或 removal
        # from _NOUN_CHARS unblocked longer regex captures. Each
        # risk-reviewed against the 10-fixture grep:
        #   顯示: "to display" — 顯示器 ×9, 顯示裝置 ×32, 顯示單元 ×3
        #         all added to _INTERIOR_CUT_EXCEPTIONS in the round 5
        #         cascade block above. Round 2's prefix-aware protection
        #         lets a captured 顯示器顯示 preserve 顯示器 via the
        #         exception prefix and cut at the second 顯示 via the
        #         remainder search.
        #   上傳: "to upload" — 上傳器/件/介面/區/功能/模組 all 0 per
        #         grep, no exception coordination needed.
        #   瀏覽: "to browse" — 瀏覽器 ×2 added to exceptions above;
        #         瀏覽程式 ×56 already present in exceptions from
        #         the original method-claim block. Both compounds
        #         protected by prefix-aware exception logic.
        "顯示", "上傳", "瀏覽",

        # === Added 2026-04-09 round 5 cascade tail ===
        # Surfaced by 110P000368 production smoke test after the
        # initial cascade landed: contamination patterns 瀏覽程式產生
        # (intro side) and 地域內各地 (reference side) needed dedicated
        # cuts to bring the fixture's count below the round 4 baseline.
        #   產生: "to generate/produce" — 110P000368 c1 captures
        #         一瀏覽程式產生的 as the noun span; cut at 產生 leaves
        #         瀏覽程式 (in exceptions). Risk-reviewed: 產生器 ×40
        #         in 110P000641 (波產生器), all naturally protected by
        #         the position-2 check (產生 at position 1 of 波產生器
        #         fails idx > 1). 波產生器 also added to exceptions
        #         above as documented insurance.
        #   各地: "various places" — 110P000368 c6/c10 reference
        #         該地域內各地 normalizes to 地域 only after cutting at
        #         各地. Grep: 各地 ×3 (all in 110P000368, all
        #         contamination patterns). 各地區/各地方 ×0 — safe.
        "產生", "各地",

        # === Added 2026-04-10 F3 ===
        # 依序: adverb ("in order") in V依序V patterns. Needed as
        #       interior cut (not just trailing strip) because the
        #       greedy {2,12} capture extends past 依序 into the
        #       following clause: 第二方向依序對多個所述焊 → should cut
        #       at 依序 to extract 第二方向. Risk: 依序器/依序件 all 0 in
        #       10-fixture corpus, no exception coordination needed.
        "依序",

        # === Added 2026-04-10 F5 ===
        # 相互: adverb "mutually" — 上端邊緣相互銜接 should cut at 相互
        #       to extract 上端邊緣. 相互作用 has 相互 at START, never
        #       interior. Grep: X相互 ×0 as compound noun — safe.
        # 朝向: verb/preposition "face toward" — 底部朝向下方 should cut
        #       at 朝向 to extract 底部. 朝向 as standalone noun
        #       ("orientation") is the head noun, never mid-compound.
        #       Grep: X朝向 as compound noun ×0 — safe.
        "相互", "朝向",

        # NOT added (interior to legitimate noun compounds):
        # 編碼 (編碼器), 識別 (識別碼/識別資料),
        # 通訊 (通訊模組), 傳動 (傳動件),
        # 接收 (接收器), 輸出 (輸出裝置), 輸入 (輸入裝置),
        # 儲存 (儲存器), 認證 (認證單元), 銜接 (第一銜接部)
        # These are caught by their LONGER multi-char forms above
        # (傳送接收到, 連接一第一電子裝, etc.) which are unambiguous.
    ),
    key=len,
    reverse=True,
))


# Exception set: compound nouns containing interior-verb tokens that
# should NOT be cut. When the captured text (or any prefix of it) is
# in this set, clean_noun_phrase_tw skips the interior-cut pass entirely
# and proceeds straight to the trailing-strip phase.
#
# Maintenance philosophy: false negatives (missing exception → walker
# doesn't find an antecedent) are the cheap failure mode. The risk
# of having too few entries is verb-contamination, which is the
# expensive failure mode (visible garbage findings).
#
# Seeded from compound nouns observed in 2026-04-09 fixtures.
_INTERIOR_CUT_EXCEPTIONS: frozenset[str] = frozenset({
    # Connection / connector compounds
    "連接器", "連接部", "連接埠", "連接點", "連接線",
    "第一連接部", "第二連接部", "第三連接部",
    "電連接器", "電性連接部",

    # Encoder / decoder
    "編碼器", "解碼器", "旋轉編碼器", "光學編碼器",

    # Identification compounds
    "識別碼", "識別資料", "識別資訊", "識別號", "識別子",

    # Communication module compounds
    "通訊模組", "通訊埠", "通訊單元", "通訊介面",
    "行動通訊模組", "無線通訊模組", "有線通訊模組",
    "第一通訊模組", "第二通訊模組",
    "第一無線通訊模組", "第二無線通訊模組", "第三無線通訊模組",

    # Transmission compounds
    "傳送器", "接收器", "發射器", "發送器", "收發器",

    # Authentication compounds
    "認證單元", "認證模組", "認證裝置", "認證功能單元",

    # Engagement / connection part compounds (from screenshot 1)
    "銜接部", "第一銜接部", "第二銜接部", "第三銜接部",
    "扣接部", "第一扣接部", "第二扣接部",

    # Wheel / structural compounds (from screenshot 2)
    "後輪", "前輪", "傳動輪", "從動輪", "主動輪",
    "曲柄", "踏板", "弧面", "第一弧面", "第二弧面",
    "輪軸", "傳動件",

    # Misc structural compounds observed in TW patent claims
    "上端邊緣", "下端邊緣", "外側邊緣", "內側邊緣",
    "容納部", "容置部", "容置杯體", "杯體",
    "環形壓接部", "壓接部", "壓接環",
    "開口部", "封閉部",
    "頂壁", "底壁", "側壁", "頂部", "底部", "側部",

    # Method-claim compounds
    "數位內容", "適地性數位內容", "主題標籤",
    "瀏覽程式", "伺服器", "使用者介面",

    # === Added 2026-04-09 round 2 (coordinated with new boundary verbs) ===
    # When 放大 / 染色 are added as interior-cut verbs, these compound
    # nouns must be protected first so the cut doesn't damage them.
    # 放大器: 108P001015 fixture has 1 occurrence.
    # 染色墨水: 110P000633 fixture has 40 occurrences.
    "放大器",
    "染色墨水",

    # === Added 2026-04-09 round 4 (coordinated with new boundary verbs) ===
    # When 帶動 is added as an interior-cut verb, 帶動輪 must be
    # protected first. Grep confirmed 帶動輪 ×2 in 110P000641.
    # Other 帶動X compounds (帶動器, 帶動件) absent (0) per grep —
    # not added speculatively.
    "帶動輪",

    # === Added 2026-04-09 round 5 cascade ===
    # Coordinated with the cascade-added interior boundary verbs
    # 顯示/上傳/瀏覽. Each compound was risk-grepped against the
    # 10-fixture corpus before adding the bare verb to the boundaries:
    #   顯示器 ×9 in 4 fixtures
    #   顯示裝置 ×32 in 2 fixtures
    #   顯示單元 ×3 in 1 fixture
    #   瀏覽器 ×2 in 1 fixture (瀏覽程式 already present above)
    # 上傳器/件/介面/區/功能/模組 all 0 per grep — no exceptions
    # needed for 上傳.
    "顯示器", "顯示裝置", "顯示單元",
    "瀏覽器",

    # === Added 2026-04-09 round 5 cascade tail (產生 boundary) ===
    # Coordinated with the addition of 產生 to interior verbs.
    # 波產生器 ×40 across the corpus (110P000641 harmonic-reducer
    # patent: 波產生器, 一波產生器, 所述波產生器, 成一波產生器, etc.) —
    # the only 產生器 compound observed. Bare 波產生器 is naturally
    # protected by the position-2 check (產生 sits at position 1 of
    # 波產生器, fails the > 1 check), but adding to the exception
    # set is documented insurance for any longer captured spans.
    "波產生器",

    # === Added F4 session: 連接面 (connecting surface) ===
    # 110P000158 has 第一連接面 / 第二連接面 ×4. Without protection,
    # interior verb 連接 truncates 第一連接面 → 第一 (bare ordinal).
    # Root cause of walker_bug.regex_noun_class_narrow — the label
    # name was misleading; the actual bug is interior-verb overcutting.
    "連接面", "第一連接面", "第二連接面",

    # === Phase F F2 — Added 2026-04-17 ===
    # 感測/偵測/監測 are verbs in _INTERIOR_VERB_BOUNDARIES (sense /
    # detect / monitor). Their + 器 suffix forms the compound noun
    # "sensor / detector / monitor device" which is common in TW
    # drafting. Without protection, 感測器 truncates to 感 at the 感測
    # boundary. Quantifier compounds 複數感測器 (synthetic) and future
    # corpus entries with these suffixes are covered here.
    "感測器", "偵測器", "監測器",
    "光感測器", "溫度感測器", "壓力感測器", "影像感測器",
    "複數感測器", "複數控制器", "複數偵測器",
})


def clean_noun_phrase_tw(text: str) -> str:
    """Strip trailing verbs and conjunction fragments from a TW reference term.

    Two-phase cleanup:

    1. Interior-verb truncation — find the first occurrence of any
       ``_INTERIOR_VERB_BOUNDARIES`` token and cut everything from that
       position onward. Recovers ``底座`` from greedy regex captures
       like ``底座設有一孔洞``.

       Skipped if the captured text (or any prefix of it) is in
       ``_INTERIOR_CUT_EXCEPTIONS`` — that means the captured text is a
       known compound noun that contains an interior-verb token as
       part of its identity, not as a clause boundary.

    2. Trailing-verb stripping — iteratively remove the longest matching
       suffix in ``_TRAILING_VERB_DENYLIST``. Handles parser-bug
       captures like ``諧波減速模組還包`` (strips ``包`` → ``諧波減速模組還``
       → strips ``還`` → ``諧波減速模組``).

    Note: the walker MAY leave a leading char of the next clause when
    that char does not match any denylist entry (e.g., ``遊戲控制器通過第``
    strips ``過`` → ``遊戲控制器通第`` → strips ``通`` (single-char
    trailing token) → ``遊戲控制器第``, leaving a stray ``第`` because ``第``
    is not a verb fragment). This is acceptable for the walker: leftover
    fragments produce mismatches at comparison time and are surfaced via
    the did-you-mean hint if similarity is high enough.
    """
    if not text:
        return text

    # Phase 1: interior-verb truncation, with prefix-aware exception
    # protection.
    #
    # If the captured text starts with a protected compound noun (e.g.
    # 容置杯體 in 容置杯體設置有多數孔隙), we PRESERVE the compound but
    # still cut at any verb that appears AFTER the compound. The
    # interior-cut search runs on text[protected_prefix_len:] only, and
    # any cut position is offset back to the original string by adding
    # protected_prefix_len. When the entire captured text is itself a
    # protected compound, protected_prefix_len == len(text) and the
    # remainder is empty, so no cut fires.
    def _longest_protected_prefix(s: str) -> int:
        """Return the length of the longest prefix of ``s`` that is in
        ``_INTERIOR_CUT_EXCEPTIONS``, or 0 if no prefix matches.

        Walks from longest to shortest so the first match returned is
        the longest one. The exact-match case (entire ``s`` is in
        exceptions) is handled by the loop starting at ``len(s)``.
        """
        for i in range(len(s), 1, -1):
            if s[:i] in _INTERIOR_CUT_EXCEPTIONS:
                return i
        return 0

    protected_prefix_len = _longest_protected_prefix(text)
    search_text = text[protected_prefix_len:]
    search_offset = protected_prefix_len

    # R31 (2026-05-03) tight noun-suffix guard: skip the interior cut when
    # the verb is part of a known noun compound. Restricted by:
    #   1. verb in high-collision whitelist (decision/sense/identify class)
    #   2. char immediately after verb is a noun-suffix
    #   3. TOTAL TEXT LENGTH ≤ 8 chars (typical compound noun max — prevents
    #      preserving long over-captures like 輸入訊號來自一感測器模組 which
    #      contains noun-suffix at end but isn't a clean compound)
    _R31_NOUN_COMPOUND_VERBS_TW = {
        '決定', '感測', '偵測', '監測', '辨識', '識別', '解析',
        '處理', '控制', '驅動', '檢出', '判定', '計算', '生成',
        '輸出', '輸入', '儲存', '存取', '讀取', '寫入',
    }
    earliest_idx: int | None = None
    for verb in _INTERIOR_VERB_BOUNDARIES:
        idx = search_text.find(verb)
        # Require ≥1 char before the verb in the search remainder (so
        # the verb isn't at position 0 of the remainder), AND ≥2 chars
        # total before the verb in the absolute original text.
        if idx >= 0 and (idx + search_offset) > 1:
            absolute_idx = idx + search_offset
            # R31 noun-compound guard (length-bounded):
            if (verb in _R31_NOUN_COMPOUND_VERBS_TW
                    and len(text) <= 8):
                next_char_pos = absolute_idx + len(verb)
                if (next_char_pos < len(text)
                        and text[next_char_pos] in _F10_SINGLE_CHAR_SUFFIXES_TW):
                    continue  # 對象決定+部 etc. (text length ≤ 8)
            if earliest_idx is None or absolute_idx < earliest_idx:
                earliest_idx = absolute_idx

    current = text[:earliest_idx] if earliest_idx is not None else text

    # Phase 2: trailing-verb stripping (iterative).
    # Safety bound to prevent pathological iteration.
    for _ in range(16):
        stripped = False
        for verb in _TRAILING_VERB_DENYLIST:
            if not current.endswith(verb):
                continue
            # General floor: never strip to empty.
            if len(current) <= len(verb):
                continue
            # Noun-like single-char suffixes (所) require residual ≥ 3 to
            # preserve 2- and 3-char compound nouns that legitimately end
            # in the suffix: 場所 (2), 研究所 (3), 事務所 (3), 避難所 (3).
            # 前 is NOT in this set — see _NOUNLIKE_SINGLE_CHAR_SUFFIXES
            # for the prefix-vs-suffix rationale. Verb-like single-char
            # fragments (包/通/經/藉/還/並/且/其/另/係/為/是) keep the
            # looser residual ≥ 1 floor — they are statute boilerplate
            # or parser cuts, not noun morphemes, so 齒輪還 → 齒輪 must
            # still strip. Multi-char tokens (包含, 包括) don't need the
            # guard because their over-strip residuals are longer by
            # construction.
            #
            # Relaxed-guard subset (上, 內) uses ≥ 2 instead of ≥ 3 so
            # 3-char positional fragments (地域內 → 地域, 範圍內 → 範圍,
            # 基板上 → 基板) strip while 2-char productive compounds
            # (their corpus count is 0) and position-0 compounds
            # (內側/上方, protected by the endswith position check) are
            # unaffected. See _NOUNLIKE_RELAXED_SUFFIXES for rationale.
            if verb in _NOUNLIKE_SINGLE_CHAR_SUFFIXES:
                min_residual = 2 if verb in _NOUNLIKE_RELAXED_SUFFIXES else 3
                if (len(current) - len(verb)) < min_residual:
                    continue
            current = current[: -len(verb)]
            stripped = True
            break
        if not stripped:
            break

    # R55 (2026-05-05): TW parity of CN R54 — adverbial-verb + 整體呈X
    # over-capture strip. Same architecture, Traditional script.
    # Anchored two-group regex: head noun (≥2 chars) + verb-phrase suffix.
    # Pre-地 portion constrained to 2-3 chars (typical TW adverbials:
    # 軸向, 平穩, 垂直, 自動).
    _R55_OVERALL_DESC_TW = re.compile(
        r'^([一-鿿]{2,})整體呈[一-鿿]{1,8}$'
    )
    _R55_ADVERBIAL_VERB_TW = re.compile(
        r'^([一-鿿]{2,})[一-鿿]{2,3}地[一-鿿]{1,3}$'
    )
    for _ in range(4):
        before = current
        m = _R55_OVERALL_DESC_TW.match(current)
        if m:
            current = m.group(1)
        m = _R55_ADVERBIAL_VERB_TW.match(current)
        if m:
            current = m.group(1)
        if current == before:
            break

    return current


# R32 (2026-05-04): regex-based at-least-N quantifier strip. Existing
# _LEADING_QUANTIFIER_DENYLIST covers 至少一/至少一個/至少兩/至少兩個 only;
# 至少三個X / 至少四個X / 至少五個X / 至少二十個X / 至少100個X all stranded.
# Round-1 corpus + the 110P000641 bearing-patent fixture surfaced this
# bleed into spec-support (`至少三個軸承`/`至少四個軸承`). Symmetric strip
# on both reference and intro sides keeps 該軸承 ↔ `至少三個軸承`-intro
# resolving to the same head noun.
_AT_LEAST_N_PREFIX_RE_TW: re.Pattern[str] = re.compile(
    r'^至少[一二三四五六七八九十百0-9]+個'
)

# R32 (2026-05-04): possessive-pronoun prefix strip. Drafters use 其X
# (its X) as a possessive noun phrase referring back to a prior subject
# — captured as an intro via F-anchor patterns but the canonical intro
# is the bare X (introduced as a feature of the prior subject, not as
# a new element). Lookahead ≥2 CJK ensures we only strip when the tail
# is a substantive noun; protects 其餘 (rest, 2 chars total — fails
# residual since 0 < 2 after strip), 其中 (filter — but `中` standalone
# is already in _BARE_QUANTIFIER_TERMS_TW indirectly).
_POSSESSIVE_其_PREFIX_RE_TW: re.Pattern[str] = re.compile(
    r'^其(?=[一-鿿]{2,})'
)

# R32 (2026-05-04): leading conjunction-residue strip — CN parity. TIPO
# drafts occasionally use `/或X` (and/or X — particularly in JP-translated
# patents). Walker captures `/或<noun>` as leading-residue intro.
_LEADING_CONJ_RESIDUE_RE_TW: re.Pattern[str] = re.compile(
    r'^(?:/或|/和|和/或|或/|/)'
)


def strip_leading_quantifier(text: str) -> str:
    """Strip one matching leading quantifier (ADR-095 Rule 2).

    Applied symmetrically to both reference terms and candidate intros
    so 複數外齒狀結構 ↔ 該外齒狀結構 both normalize to 外齒狀結構. Strip
    is NOT iterative — applied once per term — so compound terms where
    a quantifier-like morpheme is part of the head noun (e.g., 一次性
    starting with 一) are not over-stripped.

    R32 (2026-05-04): regex-based 至少N個 strip applied first (handles
    digit/ordinal-N variants beyond the static denylist); 其-possessive
    strip applied last (only when residual ≥ 2 CJK; fired on intros only
    via the symmetric flow).
    """
    if not text:
        return text
    # R32: leading conjunction-residue strip (`/或`, `和/或`).
    m = _LEADING_CONJ_RESIDUE_RE_TW.match(text)
    if m and len(text) - m.end() >= 2:
        text = text[m.end():]
    # R32: at-least-N regex strip (handles 至少三個/至少四個/至少100個).
    m = _AT_LEAST_N_PREFIX_RE_TW.match(text)
    if m and len(text) - m.end() >= 2:
        text = text[m.end():]
    for q in _LEADING_QUANTIFIER_DENYLIST:
        if text.startswith(q) and len(text) > len(q):
            text = text[len(q):]
            break
    # R32: 其-possessive strip — applied last. Lookahead in the regex
    # ensures the trailing residual is ≥2 CJK so `其餘` (2 chars) is
    # protected (residual would be 1 char `餘` < 2).
    m = _POSSESSIVE_其_PREFIX_RE_TW.match(text)
    if m:
        text = text[m.end():]
    return text


def strip_reference_form_prefix(text: str) -> str:
    """Strip one matching reference-form prefix (該/所述/前述/該等/該些).

    Applied only to reference terms (the walker's flagged side). Intros
    do not carry reference-form prefixes, so
    ``normalize_candidate_intro`` skips this step.
    """
    if not text:
        return text
    for prefix in _REFERENCE_FORM_PREFIXES:
        if text.startswith(prefix) and len(text) > len(prefix):
            return text[len(prefix):]
    return text


# Leading qualifier strip — handles definite-article-plus-qualifier
# patterns where the qualifier is a positional or relational modifier
# that doesn't introduce a new claim element.
#
# Legal basis: US Federal Circuit case law on "the corresponding X" and
# "the previous X" treats these as scope-clarifying qualifiers, not new
# elements requiring their own antecedent. TIPO general principles in
# 專利侵權判斷要點 are consistent with this reading. JP-origin TW
# translations frequently use 對應/前 patterns because Japanese claim
# style standardizes them (対応する, 前記).
#
# The walker strips these qualifiers as part of normalization so the
# bare noun matches the ancestor chain. Strict mode (per
# strict_qualifier_matching config flag) disables this strip and treats
# qualified references as distinct elements requiring their own
# antecedent — for firms with stricter house rules.

# Relational qualifiers: strip unconditionally when they appear at
# the start of a normalized term. Each can have an optional 地 or 的
# adverbial suffix.
_LEADING_RELATIONAL_QUALIFIERS: tuple[str, ...] = (
    "對應地", "對應的", "對應",
    "相應地", "相應的", "相應",
    "相對地", "相對的", "相對",
    "相關地", "相關的", "相關",
)

# Position qualifiers: strip ONLY when followed by a quantifier
# (一/二/.../複數/多個/etc.). 前/後 form compound nouns when followed
# by other characters (前端, 後輪), so the quantifier lookahead is
# what distinguishes qualifier-use (前一X) from compound-use (前端).
_LEADING_POSITION_QUALIFIERS: tuple[str, ...] = ("前", "後")
_QUANTIFIER_AFTER_POSITION: tuple[str, ...] = (
    # Round 5 addition: 一或多個 must come BEFORE bare 一 so the
    # multi-char form is matched as a unit (前一或多個X strips the
    # qualifier+quantifier and leaves X). The strip iterates this tuple
    # in order and uses .startswith(), so longest-first matters.
    "一或多個",
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "複數", "多個", "數個", "至少",
)

# Round 7 (2026-04-30): Leading-verb prefixes stripped from both reference
# and intro sides during normalization. Drafters sometimes refer back to
# a process step's product via the verb-prefixed form (`前述形成p型源極／
# 汲極之工程` references the step that introduced `p型源極／汲極`); the
# walker captures the verb prefix as part of the noun, missing the match
# against the bare-noun intro. The strip applies a residual ≥ 3 guard:
#   `形成p型源極／汲極` (10 chars) → strip → `p型源極／汲極` (8 chars ≥ 3) ✓
#   `形成器`           (3 chars)  → strip → `器`         (1 char  < 3) PROTECT
# Multi-char specific tokens; no compound-noun risk because bare-noun
# claim elements never have these as their literal head morpheme.
_LEADING_VERB_PREFIXES_TW: tuple[str, ...] = tuple(sorted(
    (
        "形成", "製造",
        # R32 (2026-05-04): connective-verb prefixes that frequently bleed
        # into intro captures. Empirical attestation in 110P000368 c6
        # spec-support FPs `即根據各數位內容` / `使得各數位內容關聯`. These
        # are clause-connective verbs ("namely according to" / "such that")
        # that drafters use to connect description to a noun referent.
        # Stripping them symmetrically (intro + reference) preserves
        # antecedent matching while eliminating the over-capture surface
        # in spec-support.
        # Multi-char longest-first so `即根據` is stripped as a unit
        # before `根據` would be tried separately.
        "即根據", "即基於", "即依據", "即依照",
        "根據", "基於", "依據", "依照",
        "為了", "藉以", "藉由",
        "使得", "使其", "從而", "進而", "並且",
        # 用以/用於 — purpose markers; often precede noun-phrase intros
        # (`用以驅動X` / `用於X`) where the canonical intro is the X.
        # Risk audited: 用以 / 用於 do not appear as compound-noun prefixes
        # in patent claims (no 用以X-form noun in TIPO claim corpus).
        "用以", "用於",
        # R67 (2026-05-05) sweep: 具有 — possession verb ("X has Y").
        # CN parity. Drafters write `所述具有X的Y` where the actual
        # antecedent is Y (or X), not `具有X`. Residual ≥ 2 floor
        # protects against trivial 1-char strips.
        "具有",
    ),
    key=len,
    reverse=True,
))
# Residual ≥ 2: `形成p型源極／汲極` (10) → 8 ≥ 2 ✓; `製造方法` (4) → 2 ≥ 2 ✓;
# `形成器`/`形成物` (3) → 1 < 2 PROTECT; `製造商`/`製造廠` (3) → 1 < 2 PROTECT.
_LEADING_VERB_RESIDUAL_FLOOR: int = 2


def strip_leading_qualifier(
    text: str,
    *,
    strict_qualifier_matching: bool = False,
) -> str:
    """Strip leading qualifier modifiers from a normalized reference term.

    Handles two patterns per ADR-095 addendum (2026-04-09):

    1. Relational qualifiers: 對應X, 相應X, 相對X, 相關X (with optional
       adverbial suffix 地/的). Stripped unconditionally — these never
       form compound nouns with the following character in patent claim
       text.

    2. Position qualifiers: 前X, 後X — but ONLY when X starts with a
       quantifier (一/二/.../複數/多個). 前一X = "previous one X" is
       a qualifier; 前端 = "front end" is a compound noun. The
       quantifier lookahead distinguishes the two cases.

    When strict_qualifier_matching is True the strip is disabled entirely
    and qualified references are treated as distinct elements. Default
    is False (lenient). Per ADR-095 the strict mode exists as an escape
    hatch for firms with stricter house rules; the default matches US
    Federal Circuit precedent and TIPO general principles.
    """
    if strict_qualifier_matching or not text:
        return text

    # Try relational qualifiers first (longest-first via the ordering
    # in _LEADING_RELATIONAL_QUALIFIERS).
    for q in _LEADING_RELATIONAL_QUALIFIERS:
        if text.startswith(q) and len(text) > len(q):
            return text[len(q):]

    # Try position qualifiers with quantifier lookahead.
    for q in _LEADING_POSITION_QUALIFIERS:
        if text.startswith(q) and len(text) > len(q):
            remainder = text[len(q):]
            for quant in _QUANTIFIER_AFTER_POSITION:
                if remainder.startswith(quant):
                    return remainder

    return text


def normalize_reference_term(
    text: str,
    *,
    strict_qualifier_matching: bool = False,
) -> str:
    """Normalize a flagged reference term for antecedent matching.

    Composes:
        normalize_arabic_ordinal_to_cjk  (R33 — 第1→第一, 第2→第二)
        → strip_reference_form_prefix    (該/所述/前述/該等/該些)
        → strip_leading_qualifier        (對應/相應/前+quantifier)
        → clean_noun_phrase_tw           (interior cut + trailing strip)
        → strip_leading_quantifier       (一/一個/複數/...)
        → strip_leading_verb             (形成 — R7, residual ≥ 3 guard)
    """
    t = normalize_arabic_ordinal_to_cjk(text)
    t = strip_reference_form_prefix(t)
    t = strip_leading_qualifier(t, strict_qualifier_matching=strict_qualifier_matching)
    t = clean_noun_phrase_tw(t)
    t = strip_leading_quantifier(t)
    t = strip_leading_verb_tw(t)
    return t


def normalize_candidate_intro(
    text: str,
    *,
    strict_qualifier_matching: bool = False,
) -> str:
    """Normalize an introduction candidate for antecedent matching.

    Composes:
        strip_leading_qualifier        (NEW — for symmetry with refs)
        → clean_noun_phrase_tw
        → strip_leading_quantifier
        → strip_reference_form_prefix  (round 3 fix — symmetry with
          ``normalize_reference_term``)

    The trailing ``strip_reference_form_prefix`` is load-bearing for
    intro spans like ``一個所述第一弧面`` (110P000641 c15/c19): the
    ``_INTRO_PATTERN`` greedily matches ``一個`` as the quantifier and
    captures ``所述第一弧面`` as the bare noun group. Without this
    strip, the intro lands in ``intros_by_term`` keyed as
    ``所述第一弧面`` while the corresponding reference normalizes to
    ``第一弧面``, the exact-match path fails, and did-you-mean surfaces
    a structurally meaningless ``所述第一弧面 → 所述第一弧面``
    suggestion. Stripping the reference-form prefix here restores the
    invariant that the intro and reference normalize to the same
    string when they refer to the same entity.
    """
    t = normalize_arabic_ordinal_to_cjk(text)
    t = strip_leading_qualifier(t, strict_qualifier_matching=strict_qualifier_matching)
    t = clean_noun_phrase_tw(t)
    t = strip_leading_quantifier(t)
    t = strip_reference_form_prefix(t)
    t = strip_leading_verb_tw(t)
    return t


def strip_leading_verb_tw(text: str) -> str:
    """Strip a leading verb prefix per Round 7 audit (Claire draft).

    Some drafters refer back to a process step's product via the verb-
    prefixed form (`前述形成p型源極／汲極之工程`); the walker's noun
    capture includes the leading verb, missing the match against a
    bare-noun intro registered without that verb. This pass removes the
    verb prefix when it's followed by a sufficient noun residual.

    Residual guard ≥ 3 protects short compounds where the verb prefix
    coincidentally precedes a 1-2 char tail (`形成器` → `器` would be 1
    char, fails the floor — preserved).
    """
    if not text:
        return text
    for prefix in _LEADING_VERB_PREFIXES_TW:
        if (
            text.startswith(prefix)
            and len(text) - len(prefix) >= _LEADING_VERB_RESIDUAL_FLOOR
        ):
            return text[len(prefix):]
    return text


def detect_plural_reference(text: str) -> bool:
    """Return True iff ``text`` starts with a plural reference-form prefix.

    Used by the strict_plural_reference_matching escape hatch to flag
    plural reference forms even when the underlying antecedent match
    is number-neutral. Default walker behaviour (strict=False) does
    NOT flag these; this helper exists so the strict mode path can
    detect and warn. See ADR-095 for the decision rationale.
    """
    return any(text.startswith(p) for p in _PLURAL_REFERENCE_PREFIXES)


def get_ancestor_chain_tw(claim: Claim, all_claims: list[Claim]) -> list[Claim]:
    """Return [claim, ...ancestors] walking the full multi-parent BFS.

    Mirrors ``claims.get_ancestor_chain`` (US walker) — multi-dependent
    claims (e.g. ``如請求項1或3所述``) collect introductions from every
    ancestor path. Cycle protection via the ``visited`` set means a
    self-referencing or circular dependency cannot loop forever.

    Per ADR-092, the walker uses the FULL ancestor chain (not just the
    immediate parent) to resolve introductions, while preamble checks use
    the immediate parent. This is intentional: 引用記載型式 cross-category
    dependents legitimately reference components introduced in any
    ancestor along the chain.

    The walker traverses BOTH ``dependencies`` (statutory parents) and
    ``quoted_references`` (引用記載型式 incorporation-by-reference in the
    claim body). Statutory dependency checks operate on ``dependencies``
    alone; only the antecedent-basis resolution needs the body-embedded
    references to reach intros defined in the referenced claim.
    """
    claims_by_id = {c.id: c for c in all_claims}
    chain: list[Claim] = [claim]
    visited: set[int] = {claim.id}
    queue: list[int] = list(claim.dependencies) + list(claim.quoted_references)
    while queue:
        parent_id = queue.pop(0)
        if parent_id in visited:
            continue
        visited.add(parent_id)
        parent = claims_by_id.get(parent_id)
        if parent is None:
            continue
        chain.append(parent)
        queue.extend(parent.dependencies)
        queue.extend(parent.quoted_references)
    return chain


# Characters that indicate word-internal 一 (not a separate intro site).
# Corpus-verified list: 第 (ordinal), 另/任/某/唯/同/單/統 (compound
# quantifier prefixes where 一 is bound to the preceding morpheme).
_WORD_INTERNAL_YI_PREDECESSORS = frozenset("第另任某唯同單統")

# Regex for capturing the noun after a split 一 position, using the same
# character class as _NOUN_CHARS but as a standalone pattern.
_SPLIT_YI_NOUN_RE = re.compile(r"一(" + _NOUN_CHARS + r")")


def _postprocess_intro_capture(
    bare_noun: str,
    match: re.Match,  # type: ignore[type-arg]
    claim_text: str,
) -> list[str]:
    """Post-process a greedy _INTRO_PATTERN capture to repair over-captures.

    Returns a list of candidate noun strings, each to be passed through
    ``clean_noun_phrase_tw`` + ``normalize_candidate_intro`` via the
    existing pipeline.

    Three repair rules, applied in order:

    Rule 1 — Reference-marker check:
      If the bare noun starts with a reference-form prefix, the entire
      capture is a false intro.  Discard but re-scan the full matched
      span for embedded 一 positions (Rule 3).
      If the bare noun contains a reference-form prefix at position > 0,
      truncate at that position.

    Rule 2 — Embedded 一 splitting:
      After Rule 1's truncation (if any), check the resulting candidate
      for non-word-internal 一 at positions > 0 and split.

    Rule 3 — Re-scan discarded spans:
      If Rule 1 discarded the entire noun, re-scan the full matched span
      for 一 positions and extract nouns after them.
    """
    # Rule 1a: starts with ref prefix → try re-scan first; if no
    # recovery sites found, strip the prefix and return the remainder
    # (preserves the existing normalize_candidate_intro strip for cases
    # like 一個所述第一弧面 where the 所述 is a greedy-capture artifact
    # and the real intro is 第一弧面).
    for prefix in _REFERENCE_FORM_PREFIXES:
        if bare_noun.startswith(prefix):
            # Re-scan the full matched span for 一 sites
            recovered = _rescan_for_yi(
                match.group(0), match.start(), claim_text,
            )
            if recovered:
                return recovered
            # No 一 recovery sites — strip the ref prefix and return
            # the remainder for normal normalization.
            remainder = bare_noun[len(prefix):]
            return [remainder] if remainder else []

    # Rule 1b: contains ref prefix at position > 0 → truncate
    for prefix in _REFERENCE_FORM_PREFIXES:
        idx = bare_noun.find(prefix)
        if idx > 0:
            bare_noun = bare_noun[:idx]
            break

    # Rule 2: embedded 一 splitting
    candidates: list[str] = []
    yi_positions = [i for i, ch in enumerate(bare_noun) if ch == "一" and i > 0]

    if not yi_positions:
        return [bare_noun]

    # Find the first non-word-internal 一
    split_pos: int | None = None
    for pos in yi_positions:
        preceding_char = bare_noun[pos - 1]
        if preceding_char not in _WORD_INTERNAL_YI_PREDECESSORS:
            split_pos = pos
            break

    if split_pos is None:
        return [bare_noun]

    # The part before the split 一 is one candidate
    leading_part = bare_noun[:split_pos]
    if leading_part:
        candidates.append(leading_part)

    # The noun after 一 — re-extract from claim_text at the absolute
    # position to get the full noun span (the bare_noun may have been
    # truncated by the {2,12} upper bound).
    abs_start = match.start() + (len(match.group(0)) - len(match.group(1))) + split_pos
    remaining_text = claim_text[abs_start:]
    yi_match = _SPLIT_YI_NOUN_RE.match(remaining_text)
    if yi_match:
        candidates.append(yi_match.group(1))
    elif split_pos + 1 < len(bare_noun):
        # Fallback: use what's left in bare_noun after 一
        candidates.append(bare_noun[split_pos + 1:])

    return candidates


def _rescan_for_yi(
    full_span: str,
    span_start: int,
    claim_text: str,
) -> list[str]:
    """Re-scan a full matched span for 一 intro sites.

    Used when Rule 1a discards the entire noun because it starts with
    a reference-form prefix. Recovers intro sites like 旋轉編碼器 from
    spans like ``一個所述感測器為一旋轉編碼器``.

    Skips any extracted noun that starts with a reference-form prefix
    (catches the quantifier-prefix ``一`` at position 0, whose noun
    ``個所述...`` inherits the ref prefix that triggered the discard).
    """
    candidates: list[str] = []
    for i, ch in enumerate(full_span):
        if ch != "一":
            continue
        # Skip the first 一 at position 0 — it is always the quantifier
        # prefix (一/一個/一種/...) that triggered the original match.
        if i == 0:
            continue
        # Skip word-internal 一 (preceded by 第/另/etc.)
        if full_span[i - 1] in _WORD_INTERNAL_YI_PREDECESSORS:
            continue
        # Extract noun after this 一 from the claim text
        abs_pos = span_start + i
        remaining = claim_text[abs_pos:]
        yi_match = _SPLIT_YI_NOUN_RE.match(remaining)
        if yi_match:
            candidates.append(yi_match.group(1))
    return candidates


# --- Supplementary bare-noun intro patterns (F9/F8/F7/F6/F5) ---
# These capture intro sites that _INTRO_PATTERN misses because the noun
# lacks a 一/quantifier prefix. Each pattern is narrowly scoped to
# minimize false positives.

_INSTRUMENTAL_PATTERN = re.compile(
    r'透過([\u4e00-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)(?:連接|連結)',
)

_VP_MODIFIER_PATTERN = re.compile(
    r'相配合的([\u4e00-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)',
)

# CJK char class excluding 的 (U+7684) — prevents captures spanning through 的
_CJK_NO_DE = r'[\u4e00-\u7683\u7685-\u9fff]'

_PARTICIPIAL_YI_DE_PATTERN = re.compile(
    r'一[\u4e00-\u9fff]+?的(' + _CJK_NO_DE + r'{2,}(?:\([A-Za-z0-9]+\))?)'
)

_POST_DE_ORDINAL_PATTERN = re.compile(
    r'的(第[一二三四五六七八九十\d]+' + _CJK_NO_DE + r'+(?:\([A-Za-z0-9]+\))?)'
)

_DE_NOUN_RE = re.compile(
    r'的(' + _CJK_NO_DE + r'{2,}(?:\([A-Za-z0-9]+\))?)'
)

# Phase C6 R-TW-F6-extend — F6 verb set + bare-noun arm.
# Ports CN R14c.1 + R14c.2 (5f650a3 + 25fb3b8). Adds:
#   * Extended F6 verb set (進行/調用/運行/調整/建立/構建/製得/根據/存在/使用/執行
#     + 獲取/獲得/得到/生成/產生/發出/發送/接收/輸出/輸入/傳送/存儲/確定/涉及).
#   * Third arm: bare NP (≥3 CJK chars, no ordinal, no paren).
#     Per-char F6-verb-boundary negative lookahead prevents greedy capture
#     from consuming across consecutive F6 verbs. ADJ_REJECTS emission
#     filter suppresses captures starting with predicate-adjective /
#     verb-phrase heads.
# F6-specific CJK class excludes 的 (U+7684) and 之 (U+4E4B) to prevent
# captures extending into temporal markers (之後/之前) without needing
# (?![的之]) lookahead.
_CJK_NO_DE_ZHI_TW = r'[\u4e00-\u4e4a\u4e4c-\u7683\u7685-\u9fff]'

_F6_VERB_ALT_TW = (
    r'具有|包含|包括|含有|設有|具備'
    r'|設置|配置|安裝|裝設'
    r'|形成|構成'
    r'|提供|連接|連結'
    r'|獲取|獲得|得到|生成|產生|發出'
    r'|發送|接收|輸出|輸入|傳送|存儲|確定|涉及'
    r'|進行|調用|運行|調整|建立|構建|製得|根據|存在|執行'
    # R7 (2026-04-30): 夾持 added — mechanical-clamp verb common in
    # semiconductor process claims (`夾持矽鍺層之n型通道層`,
    # `藉由矽層夾持矽鍺層的半導體通道層`). Captures the object NP via
    # arm 3. 夾持器 / 夾持機構 absent from TW corpus per grep — no
    # compound-noun collision.
    r'|夾持'
    # NOTE: 使用 intentionally omitted from TW port. TW corpus contains
    # compound nouns 使用者介面 (GUI), 使用者, 使用期限 that the CN-ported
    # F6 bare-noun arm incorrectly mis-captures (使用 + 者介面 → registers
    # 者介面 as phantom intro, which then DYMs against real 使用者介面
    # references). Phase F retrospective audit 2026-04-17 confirmed 4
    # walker_fp.* findings on 110P000368 caused by this. CN doesn't have
    # the same risk because 使用 + CN noun compounds (使用场景/使用效果) don't
    # collide with the ref-prefix shape 使用+者X. TW port omits until a
    # safer boundary check is designed.
)

# Phase C2 F12 ADJ rejects — shared between F6 arm3 emission gate and
# F12 Tier B/C emission gates. Suppresses bare-NP captures starting
# with predicate-adjective / verb-phrase heads.
_F12_ADJ_REJECTS_TW: tuple[str, ...] = (
    "可", "具有", "具", "經過", "由", "屬於", "用於", "來自",
    "能夠", "能", "會", "進行", "獲得", "獲取", "接收", "存儲",
    "輸出", "輸入", "基於", "根據",
    # === Phase 8b R7 — Added 2026-04-30 (Claire-draft audit) ===
    # Copula / preposition / verb prefixes that F6 bare-NP arm 3 may
    # capture as the head: `具有較前述矽層在前述...` (F6 verb 具有 + bare
    # NP starting with 較); `進行蝕刻使膜厚減少` (進行 + 蝕刻...);
    # `形成對在前述矽` (形成 + 對在...). Mirror set with _F10_NOUN_REJECTS
    # so all bare-modifier emit sites apply consistent hygiene.
    "係", "是", "為",
    "較", "對", "在",
    "將", "藉", "蝕",
)

_BARE_AFTER_VERB_PATTERN = re.compile(
    r'(?:' + _F6_VERB_ALT_TW + r')'
    r'('
    # Arm 1: ordinal prefix
    r'第[一二三四五六七八九十\d]+' + _CJK_NO_DE_ZHI_TW + r'+(?:\([A-Za-z0-9]+\))?'
    # Arm 2: paren-numeral terminated
    r'|' + _CJK_NO_DE_ZHI_TW + r'+\([A-Za-z0-9]+\)'
    # Arm 3: bare NP ≥3 CJK chars (gated in emit site by ADJ_REJECTS)
    r'|'
    r'(?!第|所述|該|前述|該等|該些)'
    + r'(?:(?!(?:' + _F6_VERB_ALT_TW + r'))' + _CJK_NO_DE_ZHI_TW + r'){3,20}'
    r')'
    # Preserve pre-R14c.2 behavior: reject captures followed by 的/之
    # (attribute modifier form like 具有第一直徑的管道 — 第一直徑 is NOT
    # an intro there, 管道 is). TW diverges from CN R14c.2 here because
    # TW corpus uses this pattern more frequently than CN.
    r'(?![的之])'
)

_CLAUSE_BOUNDARY_RE = re.compile(r'[；，、。]')

_REF_PREFIX_SET = ('所述', '該', '前述')

# F5a: Ref-prefix possessive (所述|該|前述)X的Y
# Split into two variants to prevent verb-contaminated X:
# - With paren-numeral on X: no CJK length limit (numeral anchors boundary)
# - Without paren-numeral: X limited to 2-4 CJK (rejects 框架相配合 etc.)
_REF_POSSESSIVE_WITH_NUM = re.compile(
    r'(?:所述|該|前述)'
    r'[\u4e00-\u7683\u7685-\u9fff]{2,}\([A-Za-z0-9]+\)'
    r'的'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)'
)
_REF_POSSESSIVE_NO_NUM = re.compile(
    r'(?:所述|該|前述)'
    r'[\u4e00-\u7683\u7685-\u9fff]{2,4}'
    r'的'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)'
)

# F5b: 一X(N)的Y — intro with paren-numeral possessive
_YI_NOUN_PAREN_DE_PATTERN = re.compile(
    r'一[\u4e00-\u7683\u7685-\u9fff]{2,}\([A-Za-z0-9]+\)'
    r'的'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)'
)

_POSSESSIVE_VERB_DENYLIST = {
    '包括', '包含', '具有', '是', '為', '大於', '小於', '等於',
    '設置', '形成', '連接', '連結',
}

# F10: Bare-modifier `的NOUN` — JP-translated TW claims frequently introduce
# elements as the head noun of an adjectival/locative clause without a
# preceding 一/quantifier, e.g.
#   「配置在容器本體上部的開口部」              → 開口部
#   「具有從前述內塞的下表面朝下側突出的環狀的嵌合壁部」 → 嵌合壁部
#   「可拆裝地嵌合於前述嵌合壁部的可彈性變形的嵌合部」   → 嵌合部
#   「…外部連通的壓力調節閥」                   → 壓力調節閥
#   「比…更硬質的基材」                         → 基材
# F5a already handles `所述X的Y` (ref-prefixed modifier); F10 is the bare-
# modifier analogue. Emitting extras into `intros_by_term` is safe — intros
# only resolve references, they never manufacture findings.
# Noun charset reuses _CJK_NO_DE_ZHI_TW (excludes 的 U+7684 and 之 U+4E4B)
# so captures don't span through further possessive markers. Upper bound 8
# mirrors _NOUN_CHARS. Trailing CJK negative lookahead anchors the capture
# at a non-CJK boundary (clause punctuation, end of text).
_F10_BARE_DE_NOUN_RE = re.compile(
    r'的'
    r'(?P<noun>' + _CJK_NO_DE_ZHI_TW + r'{2,8}'
    r'(?:\([A-Za-z0-9]+\))?)'
    # R7 (2026-04-30): trailing lookahead uses _CJK_NO_DE_ZHI_TW (the noun
    # class) instead of the full CJK range. The full range mistakenly
    # rejects boundaries at 之 (U+4E4B) / 的 (U+7684), which are valid
    # clause boundaries — those chars are excluded from the noun class.
    # Pre-fix: `的半導體通道層交...` failed because 交 is CJK, so backtrack
    # cascaded to no match. Post-fix: same, but `的奈米片積層體之兩側`
    # captures `奈米片積層體` cleanly because 之 isn't in noun class.
    r'(?!' + _CJK_NO_DE_ZHI_TW + r')'
)

# F11: Locative-possessive bare NOUN. TW/JP-translated drafters introduce
# containing elements as the modifier before a positional suffix:
#   「配置在容器本體上部的開口部」 → 容器本體
# The positional suffix (上部/下部/內部/...) + 的 combination anchors the
# capture. A preceding CJK preposition (於|在|到|至|從|朝) rules out mid-
# word false starts; post-capture filter rejects ref-prefix heads.
_F11_LOCATIVE_SUFFIXES = (
    '上部', '下部', '內部', '外部',
    '上方', '下方', '內側', '外側',
    '頂部', '底部', '前部', '後部',
    '側面', '表面', '內面', '外面',
    '內壁', '外壁', '上端', '下端',
)
_F11_LOCATIVE_POSS_RE = re.compile(
    r'(?:於|在|到|至|從|朝)'
    r'(?P<noun>' + _CJK_NO_DE_ZHI_TW + r'{2,6})'
    r'(?:' + '|'.join(_F11_LOCATIVE_SUFFIXES) + r')'
    r'的'
)

# Round 6: F14 — bare-modifier `之NOUN` intro. Formal-register parallel
# to F10's `的NOUN` for TIPO 專利說明書 register and JP-translated drafts
# where 之 is used for possessive marking instead of the modern 的.
# Triggered by issues #19 + #23 (semiconductor patent drafter introducing
# sub-elements as `具備全周閘極構造之p型電晶體以及n型電晶體`).
#
# Mixed-script noun class: CJK (excluding 的 U+7684 + 之 U+4E4B) plus
# ASCII letters/digits to capture electronics/semiconductor identifiers
# (p型電晶體, n型通道層, RAM控制器). _CJK_NO_DE_ZHI_TW alone would miss
# these — its ranges are CJK-only.
#
# Trailing negative-lookahead anchors the capture at a non-CJK-non-alnum
# boundary (clause punctuation, end of text). Constraints in the emit
# site mirror F10:
#   * Component-suffix gate ensures the captured word names a physical
#     claim element (uses _F10_COMPONENT_SUFFIXES; 體 covers p/n型電晶體,
#     層 covers p/n型通道層, etc.).
#   * Reject ref-prefix heads (所述/該/前述/該等/該些).
#   * Reject ADJ/verb heads via _F10_NOUN_REJECTS.
# Conjunction-split (Phase B4 at end of _extract_supplementary_intros)
# downstream-splits 之X以及Y / 之X和Y / 之X與Y / 之X及Y so each piece is
# registered as its own intro.
# R7 (2026-04-30): U+FF0F (／ fullwidth slash) added to noun class.
# Common in semiconductor / electronics claims for paired-element names
# (`源極／汲極` = source/drain, `輸入／輸出` = I/O). Excluded from generic
# CJK class but legitimate in component-name position. No claim-text
# context where ／ is non-noun (no fractions or pagination markers
# in claim body).
_F14_NOUN_CLASS = r'[A-Za-z0-9／一-乊乌-皃皅-鿿]'
_F14_BARE_ZHI_NOUN_RE = re.compile(
    r'之'
    r'(?P<noun>' + _F14_NOUN_CLASS + r'{2,12}'
    r'(?:\([A-Za-z0-9]+\))?)'
    r'(?!' + _F14_NOUN_CLASS + r')'
)

# Round 7 (2026-04-30): F16 — locative left-side intro `(?:於|在)X之Y`.
# F14 captures the right-side Y; F16 captures the left-side X when used
# in locative constructions where X is the new claim element. Common in
# semiconductor / mechanical drafting:
#   `於半導體基板之一主面側` → register `半導體基板`
#   `在半導體基板之一主面上` → register `半導體基板`
#   `在前述凹槽之內壁` → X = `前述凹槽` rejected (ref-prefix)
# Component-suffix gate ensures X names a physical claim element.
# X length cap of 8 chars matches F10. No clause-boundary anchor — `在`
# / `於` can appear mid-clause when introducing a new element via
# locative construction (`係積層有在矽層之間夾持矽鍺層之n型通道層`).
# `對於X之Y` also matches as `於X之Y` and captures X correctly (no harm).
_F16_LOC_LEFT_INTRO_RE = re.compile(
    r'(?:於|在)'
    r'(?P<noun>' + _F14_NOUN_CLASS + r'{2,8}'
    r'(?:\([A-Za-z0-9]+\))?)'
    r'之'
)

# Round 7 (2026-04-30): F17 — locative-internal intro `在X之間`. Specific
# pattern where X is between two surfaces / volumes. Common in
# semiconductor process claims (`在矽層之間夾持矽鍺層`). Distinguishes
# from F16 by the trailing `之間` anchor (locative-between scope).
# Component-suffix gate via _F10_SINGLE_CHAR_SUFFIXES_TW (one char).
# No clause-boundary anchor — F17 fires whenever the `在X之間` pattern
# appears, which is unambiguous about X's role as a claim element.
_F17_LOC_INTERNAL_INTRO_RE = re.compile(
    r'在'
    r'(?P<noun>' + _F14_NOUN_CLASS + r'{2,8}'
    r'(?:\([A-Za-z0-9]+\))?)'
    r'之間'
)

# Round 7 (2026-04-30): F15 — colon-list bare-noun intros. TW port of
# CN's F11_COLON_LIST_ANCHOR (`包括: X1, X2, ...`). After a recognized
# trigger verb (具有/包括/包含/含有/具備/設有) followed by `:` or `：`,
# capture the list region until the next strong-clause boundary (。) and
# split into bare-NP segments via _F15_LIST_SPLIT (、，,；以及和與及).
# Each segment is registered as an intro after the standard hygiene gate.
# Common in TIPO sub-element listings:
#   `前述p型電晶體具有：p型積層體；以及 閘極電極，係介隔著...`
#     → register `p型積層體`, `閘極電極`
_F15_COLON_LIST_ANCHOR_TW = re.compile(
    r'(?:具有|包括|包含|含有|具備|設有)[：:]\s*([^。]+)'
)
_F15_LIST_SPLIT_TW = re.compile(r'[、，,；和與及]|以及')

# Round 7 (2026-04-30): F19 — `verb + X + 之 + Y` left-side intro.
# Captures X (the verb's object that's also possessor of Y). F14
# captures the right-side Y; F19 captures the left-side X. F6's
# `(?![的之])` trailing lookahead blocks F6 from emitting on this shape
# because the bare-NP arm rejects when followed by 之/的. Common in
# TIPO method-claim drafting:
#   `夾持矽鍺層之n型通道層`         → register `矽鍺層`
#   `具有第一夾角之凸部`             → register `第一夾角`
# Component-suffix gate via _trim_capture_to_clean_noun_tw at emit.
_F19_VERB_NP_ZHI_RE = re.compile(
    r'(?:夾持|包含|包括|具有|含有|具備|設有|設置|配置|安裝|裝設|形成|構成|連接|連結|提供|構建)'
    r'(?P<noun>' + _F14_NOUN_CLASS + r'{2,8}'
    r'(?:\([A-Za-z0-9]+\))?)'
    r'[之的]'  # accept 之 (formal register) OR 的 (modern register)
)

# Round 7 (2026-04-30): F20 — `(以|藉由|透過|經由) X (verb)` instrumental
# intro. Captures X as a new claim element when used as the means in a
# preposition + verb clause. Common in TIPO method-claim drafting:
#   `以閘極電極覆蓋前述p型通道層`     → register `閘極電極`
#   `藉由矽層夾持矽鍺層`             → register `矽層`
# Trailing verb is required to disambiguate from preposition-only uses
# (`以X的Y` would match F10/F19 instead). Component-suffix gate via
# walk-back at emit.
# `以` excluded when followed by `及` (conjunction `以及` = "as well as")
# to prevent mid-conjunction false matches like `以及藉由矽層夾持` where
# `以` would otherwise trigger and capture `及藉由矽層` as junk noun.
# R41 (2026-05-04): added `將` (instrumental object marker, traditional
# CJK; mirror of CN R41 `将`). Extended trailing verb list with
# output/send/transmit/etc. forms to cover `將X輸出/發送/傳輸` shapes
# in JP/CN-translated TW drafts.
_F20_PREP_NP_VERB_RE = re.compile(
    r'(?:以(?!及)|藉由|透過|經由|將)'
    r'(?P<noun>' + _F14_NOUN_CLASS + r'{2,8}'
    r'(?:\([A-Za-z0-9]+\))?)'
    r'(?:夾持|覆蓋|包含|包括|具有|含有|具備|設有|設置|配置|形成|構成|連接|連結|提供|分隔|劃分|實施|分為|構建|測量|蝕刻|除去|裝設|安裝|輸出|輸入|發送|接收|傳輸|傳送|生成|獲取|獲得|確定|存儲|讀取|寫入|執行|處理|計算)'
)

# ADJ/verb heads that must not start a bare-modifier noun capture.
# Mirrors _F12_ADJ_REJECTS_TW with additions for bare-的 context.
_F10_NOUN_REJECTS = (
    '可', '具有', '具', '經過', '由', '屬於', '用於', '來自',
    '能夠', '能', '會', '進行', '獲得', '獲取', '接收', '存儲',
    '輸出', '輸入', '基於', '根據',
    '單一', '唯一',
    # === Phase 8b R7 — Added 2026-04-30 (Claire-draft audit) ===
    # Copula / verb-prefix rejects for F15 colon-list intros and F12
    # Tier A walk-back. F15 splits a colon-list segment that may start
    # with copula 係 (`係積層有由矽鍺所構成之p型通道層`); F12 may
    # over-capture across `為` boundaries (`為主`-style adverbs).
    '係', '是', '為',
    # Comparative / preposition rejects: F6 over-capture (`具有較前述矽層
    # 在前述p型電晶體`) and bare-NP arm 3 produce captures starting with
    # 較/對/在. Also F15 colon-list segments may start with 在 (`在矽層
    # 之間夾持矽鍺層之n型通道層`). 對 covers 對於/對應 / `對在前述矽`.
    '較', '對', '在',
    # Verb-of-action prefix rejects: F15 segments may carry leading
    # verbs (`將犧牲片層`, `藉由矽層夾持`, `蝕刻使膜厚`). 將/藉/蝕 cover
    # the observed corpus cases. Multi-char `藉由` would also work but
    # single-char 藉 is sufficient (藉口 is non-patent; no compound-noun
    # collision in TW patent claim diction).
    '將', '藉', '蝕',
)

# Mechanical-component suffix set. F10 only emits captures whose tail is
# one of these characters — the strong "this word names a physical claim
# element" signal that separates mechanical intros (開口部/壓力調節閥/基材)
# from loose attribute nouns (識別資料, 訊息, 指令) buried in the same
# `的NOUN` syntactic position. Extensions should stay anchored to concrete
# element-like terms; avoid data/signal suffixes (料 for 資料, 號 for 信號,
# 令 for 指令) unless there is fixture evidence of a legit-intro need.
_F10_COMPONENT_SUFFIXES: tuple[str, ...] = (
    '部', '件', '體', '器', '閥', '板', '模', '組', '塊', '片',
    '環', '殼', '膜', '座', '盤', '筒', '軸', '桿', '輪', '帶',
    '管', '架', '框', '壁', '面', '層', '材', '口', '道', '頭',
    '側', '孔', '縫', '邊', '頂', '底', '角', '心', '核', '機',
    '櫃', '室', '槽', '線', '路', '池', '樞', '蓋', '套', '罩',
    '網', '柱', '錐', '球', '球體', '筒體',
    # === Phase 8b R7 — Added 2026-04-30 (Claire-draft audit) ===
    # 域: region/area suffix for semiconductor + electronic claim
    #     elements (n型區域, p型區域, 主動區域, 隔離區域). Observed in
    #     c11/c13/c14/c15 of the Claire draft. F14 captures `中之n型區域`
    #     cleanly but the emit gate rejected because 域 was missing. Risk
    #     audit: TW corpus 0 spurious matches (域 in 領域/場域/流域/海域
    #     are general-domain words rare in claim text; no collision with
    #     the 25 protect:true entries).
    '域',
    # 極: electrode/pole suffix for semiconductor claim elements (閘極
    #     電極, 源極, 汲極, 集極, 射極). Observed in c1/c10/c13/c15 of
    #     the Claire draft. Risk audit: 北極/南極/太極/積極 are
    #     non-patent compounds, 0 corpus collisions; 中極 / 終極 absent.
    '極',
    # NOTE: 法 (method-claim head) intentionally NOT added here — F10's
    # narrow `的Y` capture would misfire on synthetic `一種的方法` (and
    # other 2-char 法 compounds). Walk-back uses the wider set
    # _F10_WALKBACK_SUFFIXES_TW which DOES include 法 so F14/F19/F20
    # can register `製造方法` (then strip_leading_verb_tw produces `方法`).
)


# Round 7 (2026-04-30): Single-char component suffixes derived from
# _F10_COMPONENT_SUFFIXES, used by walk-back-to-last-suffix logic in
# F12/F14 emit. Multi-char items (球體, 筒體) contribute their tail char
# (體) which is already in the single-char set. The walk-back logic only
# needs the single-char tails to identify a clean noun-phrase boundary
# from the right.
_F10_SINGLE_CHAR_SUFFIXES_TW: frozenset[str] = frozenset(
    s for s in _F10_COMPONENT_SUFFIXES if len(s) == 1
) | {
    # Walk-back-only suffixes that aren't in F10's narrow endswith gate
    # (because F10 fires on `的Y` with Y={2,8} chars and short 法-suffix
    # captures like `的方法` would misfire on 想法/做法/算法 cases). F14/
    # F19/F20 walk-back uses this wider set so `之製造方法` registers
    # `製造方法` (then strip_leading_verb_tw produces `方法` as the head).
    '法',
}

# Round 7: walk-back is only allowed to discard a suffix that BEGINS with
# one of these verb-tail-head characters AND has length ≥ 2. This prevents
# false positives where the over-capture ends in a noun-suffix-shaped
# verb-derivative — e.g. `全域厚膜化` (drafter's 厚膜化 = "to thicken")
# would walk back from 化 to 膜 producing `全域厚膜`, which is junk
# (verb's object, not a claim element). The discarded `化` (1 char, not
# in V-head set) → REJECT. Same for `矽鍺層膜厚更厚` discarding `膜厚更厚`
# — starts with 膜 (a noun suffix, not a V-head) → REJECT.
#
# Captures the canonical TW patent-claim trailing-verb-clause shapes:
#   `X之Y所形成`     → walk-back at `所` → Y     (4 findings on Claire draft)
#   `X之Y所構成`     → walk-back at `所` → Y
#   `X作為Y露出`     → walk-back at `露` → Y     (4 findings)
#   `X之Y組成的Z`    → walk-back at `組` → Y
#   `X進行Y`         → covered separately by interior-cut on 進行
_F14_WALKBACK_VERB_HEADS_TW: tuple[str, ...] = (
    '所', '露', '形', '構', '組', '製', '經',
    # R7 extension (2026-04-30): 獲 covers `X獲得Y` / `X獲取Y` walk-back
    # in process-method drafts (`X之Y獲得Z` discards `獲得Z` → truncates
    # to Y). Compound-noun risk: 獲利 (profit) is rare in claim text;
    # 獲得/獲取 are dominant in patent diction as verbs.
    '獲',
)


def _trim_capture_to_clean_noun_tw(text: str) -> str | None:
    """Walk back from end of `text` to the last component-suffix character
    and truncate; return ``None`` if the result fails any hygiene check.

    Used by F12 Tier A and F14 emit sites to recover from over-greedy
    captures that extend past the head noun into a trailing verb clause.
    Hygiene checks (in order):
      1. If `text` already ends in a component-suffix char, walk-back is a
         no-op (just run hygiene checks 4-5 below). Preserves R6 behavior
         for clean captures like `p型電晶體以及n型電晶體`.
      2. Walk-back must find a single-char component suffix in the leading
         12 characters of `text`. Without one, the capture is not a noun
         phrase — reject.
      3. The discarded suffix (`text[clean_end:]`) must (a) be ≥ 2 chars
         AND (b) start with one of `_F14_WALKBACK_VERB_HEADS_TW`. This
         restricts walk-back to known verb-clause tails (所形成 / 露出 /
         構成 / 組成 / etc.) and rejects walk-back that would salvage
         meaningless substrings (`化` from 厚膜化, `膜厚更厚` from
         矽鍺層膜厚更厚).
      4. The truncated form must not contain an embedded reference-form
         prefix (該等/該些/所述/前述/該). Embedded ref-prefixes mean the
         capture spans clauses rather than a single noun phrase.
      5. The truncated form must be ≥ 2 chars and must not start with
         one of `_F10_NOUN_REJECTS` (predicate-adjective / verb-phrase
         heads).

    Returns the truncated form if all checks pass, else ``None``.

    Examples (Round 7 audit on Claire's draft):
      - `p型區域所形成` → discard `所形成` (≥2, starts with 所) → `p型區域` ✓
      - `p型通道層露出` → discard `露出` (≥2, starts with 露) → `p型通道層` ✓
      - `全域厚膜化`   → discard `化` (length 1) → REJECT
      - `矽鍺層膜厚更厚` → discard `膜厚更厚` (starts with 膜, not in V-heads) → REJECT
      - `內壁露出前述矽層` → ends in 層 (no walk-back) → embedded `前述` → REJECT
      - `p型電晶體以及n型電晶體` → ends in 體 → no walk-back → PASS
    """
    if not text or len(text) < 2:
        return None
    # Case 1: already ends in component suffix — no walk-back needed
    if text[-1] in _F10_SINGLE_CHAR_SUFFIXES_TW:
        truncated = text
    else:
        # Walk back to last component-suffix char within leading 12 chars.
        clean_end = None
        for i in range(min(len(text), 12), 0, -1):
            if text[i - 1] in _F10_SINGLE_CHAR_SUFFIXES_TW:
                clean_end = i
                break
        if clean_end is None:
            return None
        # Verb-tail gate: discarded suffix must be a known verb-clause shape
        discarded = text[clean_end:]
        if len(discarded) < 2 or not discarded.startswith(
            _F14_WALKBACK_VERB_HEADS_TW
        ):
            return None
        truncated = text[:clean_end]
    if len(truncated) < 2:
        return None
    # Reject embedded reference-form prefix.
    for prefix in _REFERENCE_PREFIXES:
        if prefix in truncated:
            return None
    # Reject ADJ/verb-phrase heads.
    if truncated.startswith(_F10_NOUN_REJECTS):
        return None
    return truncated


# R7 (2026-04-30): F10b — lazy-suffix-anchored variant of F10. The
# greedy F10 fails when the noun is followed by CJK (e.g.
# `的半導體通道層交互積層`); F10b matches `的(noun{1,7}? + suffix-char)`
# so the capture is bounded by the FIRST component suffix encountered.
# This admits captures with arbitrary trailing CJK context, complementing
# F10's greedy boundary-anchored match.
#
# Risk: lazy match registers the shortest suffix-ending NP; longer
# forms (e.g. `奈米片積層體` vs `奈米片積層`) would prefer greedy F10.
# Both patterns run; F10's greedy emit takes precedence when the trailing
# context permits, otherwise F10b's lazy emit fills the gap. Junk
# captures are filtered by the same hygiene gate as F10.
_F10B_SUFFIX_CHARSET = '[' + ''.join(sorted(_F10_SINGLE_CHAR_SUFFIXES_TW)) + ']'
_F10B_BARE_DE_NOUN_RE = re.compile(
    r'的'
    r'(?P<noun>' + _CJK_NO_DE_ZHI_TW + r'{1,7}?'
    + _F10B_SUFFIX_CHARSET
    + r'(?:\([A-Za-z0-9]+\))?)'
)


def _extract_supplementary_intros(text: str) -> list[tuple[str, str]]:
    """Extract bare-noun introductions from supplementary patterns.

    Returns (original_span, normalized_term) pairs, same contract as
    extract_introductions_tw's main loop.
    """
    results: list[tuple[str, str]] = []

    # F9: 透過Y連接/連結 — instrumental intro
    for m in _INSTRUMENTAL_PATTERN.finditer(text):
        noun = m.group(1)
        original = m.group(0)  # full matched span
        # Normalize: strip paren-numeral for the normalized form
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        results.append((original, normalized))

    # F8: 相配合的Y — VP modifier intro
    # Scoped: Y must start with ordinal 第 OR contain paren-numeral
    for m in _VP_MODIFIER_PATTERN.finditer(text):
        noun = m.group(1)
        # Strip paren-numeral for normalized form
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        # Scoping: Y must start with 第 (ordinal) OR original had paren-numeral
        has_numeral = '(' in noun
        has_ordinal = normalized.startswith('第')
        if not (has_numeral or has_ordinal):
            continue
        # Floor: normalized Y must be ≥3 CJK chars (rejects 圓形, 圓柱 shape descriptors)
        cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
        if cjk_len < 3:
            continue
        results.append((m.group(0), normalized))

    # F7d (R64, 2026-05-05): bare locative `於X的Y` — captures X.
    # User-reported on 神秘黑屏哥.docx c10:
    #   `於半導體基板的一主面上，藉由...`
    # Drafter introduces 半導體基板 via this locative phrase. Walker's
    # main intro pattern misses it (no quantifier prefix). F7a captures
    # the post-的 noun (Y); this complement captures the pre-的 noun (X)
    # which IS the introduced element in `於X的Y` shape.
    #
    # Risk-managed scoping:
    #   1. 於 must follow a clause boundary or claim start (not mid-noun)
    #   2. X must be ≥ 3 CJK chars
    #   3. X must not start with reference prefix (前述/所述/該/該等/該些)
    #   4. X stops at first non-noun char (excluded set + 的)
    # Without (3), `於前述X的Y` would re-register X as a fresh intro.
    _BARE_YU_X_DE_RE = re.compile(
        r"(?:^|[，、。；\n　])"
        r"於([^\s，。；：、及與和之的該將能須應皆被於以並且其而還另時在更前所]{3,12})"
        r"的"
    )
    for m in _BARE_YU_X_DE_RE.finditer(text):
        candidate = m.group(1)
        # Defensive: re-check no ref-prefix (regex char class might admit some)
        if any(candidate.startswith(p) for p in _REF_PREFIX_SET):
            continue
        # Floor: ≥3 CJK chars
        cjk_len = sum(1 for c in candidate if '一' <= c <= '鿿')
        if cjk_len < 3:
            continue
        results.append((m.group(0), candidate))

    # F7a: 形成於X的Y — locative intro (last 的NOUN before clause boundary)
    for pos in (i for i, ch in enumerate(text) if text[i:i + 3] == '形成於'):
        clause_start = pos + 3
        boundary = _CLAUSE_BOUNDARY_RE.search(text, clause_start)
        clause_end = boundary.start() if boundary else len(text)
        clause = text[clause_start:clause_end]
        # Find ALL 的NOUN in the clause, take the last
        last_noun = None
        last_original = None
        for dm in _DE_NOUN_RE.finditer(clause):
            last_noun = dm.group(1)
            last_original = text[clause_start + dm.start():clause_start + dm.end()]
        if last_noun is None:
            continue
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', last_noun)
        # Scoping: ≥3 CJK chars AND no ref prefix
        cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
        if cjk_len < 3:
            continue
        if any(normalized.startswith(p) for p in _REF_PREFIX_SET):
            continue
        results.append((last_original, normalized))

    # F7b: 一V的Y — participial intro
    for m in _PARTICIPIAL_YI_DE_PATTERN.finditer(text):
        noun = m.group(1)
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        has_numeral = '(' in noun
        has_ordinal = normalized.startswith('第')
        cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
        if not (has_ordinal or has_numeral or cjk_len >= 3):
            continue
        results.append((m.group(0), normalized))

    # F7c: 的第Y — post-的 ordinal noun
    for m in _POST_DE_ORDINAL_PATTERN.finditer(text):
        noun = m.group(1)
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        results.append((m.group(0), normalized))

    # F6: 具有/設置/形成/... + Y — bare-after-verb intro
    # R14c.2: arm 3 (bare NP, no ordinal, no paren) is gated by
    # _F12_ADJ_REJECTS_TW startswith to suppress predicate-adjective
    # and verb-phrase heads (可/經過/具有/能夠/用於/基於/根據).
    for m in _BARE_AFTER_VERB_PATTERN.finditer(text):
        noun = m.group(1)
        if (not noun.startswith('第')
                and '(' not in noun
                and noun.startswith(_F12_ADJ_REJECTS_TW)):
            continue
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        results.append((m.group(0), normalized))

    # F12: copula intros (C2, Tier A + Tier B ports).
    # Tier A unconditional (轉變為/變為/分為/作為-family): register Y from
    # X轉變為Y / X作為Y. Round 7 (2026-04-30): 作為 added with mixed-script
    # noun class (in regex def above). Trailing verb-clause cleanup
    # (`作為p型通道層露出` → `p型通道層`) handled by clean_noun_phrase_tw
    # via the interior-cut at 露出 (added to _INTERIOR_VERB_BOUNDARIES in
    # this round). No walk-back here — preserves R2's f12_copula behavior
    # for short captures like `水蒸氣` that don't end in F10 component
    # suffixes (氣 is a chemistry-element tail, intentionally outside the
    # mechanical-element suffix list).
    for m in _F12_TIER_A_RE_TW.finditer(text):
        noun = m.group(1)
        if noun.startswith(('所述', '該', '前述', '該等', '該些')):
            continue
        results.append((m.group(0), noun))
    # Tier B + ADJ_REJECTS (基於/來自): register Y from X基於Y / X來自Y
    # unless Y starts with a predicate-adjective or verb-phrase head.
    for m in _F12_TIER_B_RE_TW.finditer(text):
        noun = m.group(1)
        if noun.startswith(('所述', '該', '前述', '該等', '該些')):
            continue
        if noun.startswith(_F12_ADJ_REJECTS_TW):
            continue
        results.append((m.group(0), noun))

    # F5a: Ref-prefix possessive 所述X的Y (two variants)
    for pattern in (_REF_POSSESSIVE_WITH_NUM, _REF_POSSESSIVE_NO_NUM):
        for m in pattern.finditer(text):
            noun = m.group(1)
            normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
            cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
            if cjk_len < 2:
                continue
            if normalized.startswith(('所述', '該', '前述')):
                continue
            # Check follower — reject if followed by content verb
            end_pos = m.end()
            follower = text[end_pos:end_pos + 2]
            if follower in _POSSESSIVE_VERB_DENYLIST:
                continue
            results.append((m.group(0), normalized))

    # F5b: 一X(N)的Y — intro with paren-numeral possessive
    for m in _YI_NOUN_PAREN_DE_PATTERN.finditer(text):
        noun = m.group(1)
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
        if cjk_len < 2:
            continue
        if normalized.startswith(('所述', '該', '前述')):
            continue
        end_pos = m.end()
        follower = text[end_pos:end_pos + 2]
        if follower in _POSSESSIVE_VERB_DENYLIST:
            continue
        results.append((m.group(0), normalized))

    # F10: Bare-modifier `的NOUN` — broad JP-translated-pattern coverage.
    # Runs after all ref-prefixed and verb-triggered patterns so its extras
    # fill gaps rather than duplicate. Scoped to mechanical-component
    # suffixes so data/attribute nouns buried inside possessive chains
    # (e.g. `所述X的Y的識別資料` in 110P000868 claim 1 where 識別資料 is a
    # loose attribute that was never properly introduced) aren't silently
    # emitted as intros. The component suffix is a strong positive signal
    # that the captured word names a claim element, not an attribute.
    for m in _F10_BARE_DE_NOUN_RE.finditer(text):
        noun = m.group('noun')
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        if not normalized or len(normalized) < 2:
            continue
        if normalized.startswith(_REFERENCE_PREFIXES):
            continue
        if normalized.startswith(_F10_NOUN_REJECTS):
            continue
        if not normalized.endswith(_F10_COMPONENT_SUFFIXES):
            continue
        results.append((m.group(0), normalized))

    # R7 (2026-04-30): F10b — lazy-suffix-anchored fallback of F10. Catches
    # `的(noun)` captures where the trailing context is CJK (greedy F10
    # fails). Same hygiene as F10. Common in process-method drafting
    # where elements are listed in long compound phrases:
    #   `藉由矽層夾持矽鍺層的半導體通道層交互積層` → register `半導體通道層`
    for m in _F10B_BARE_DE_NOUN_RE.finditer(text):
        noun = m.group('noun')
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        if not normalized or len(normalized) < 2:
            continue
        if normalized.startswith(_REFERENCE_PREFIXES):
            continue
        if normalized.startswith(_F10_NOUN_REJECTS):
            continue
        if not normalized.endswith(_F10_COMPONENT_SUFFIXES):
            continue
        results.append((m.group(0), normalized))

    # F11: Locative-possessive bare NOUN (Y+上部/下部/...的).
    for m in _F11_LOCATIVE_POSS_RE.finditer(text):
        noun = m.group('noun')
        if not noun or len(noun) < 2:
            continue
        if noun.startswith(_REFERENCE_PREFIXES):
            continue
        if noun.startswith(_F10_NOUN_REJECTS):
            continue
        results.append((m.group(0), noun))

    # Phase 8b R6 — F14: bare-modifier `之NOUN` intro (formal-register
    # parallel to F10's `的NOUN`). Mixed-script noun class admits ASCII
    # letters/digits for electronics/semiconductor identifiers.
    # Component-suffix gate + ref-prefix rejection + ADJ rejection mirror
    # F10. Conjunction-split downstream handles 之X以及Y / 之X和Y / etc.
    #
    # R7 (2026-04-30): Replace strict endswith-suffix gate with walk-back-
    # to-last-suffix recovery. Greedy regex matches up to 12 chars and
    # often extends past the head noun (`之p型區域所形成` captures
    # `p型區域所形成`); walk-back recovers `p型區域` cleanly. Also rejects
    # captures with embedded ref-prefix (`內壁露出前述矽層` → `前述`-embedded
    # → REJECT) which the old endswith-only gate let through.
    for m in _F14_BARE_ZHI_NOUN_RE.finditer(text):
        noun = m.group('noun')
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        trimmed = _trim_capture_to_clean_noun_tw(normalized)
        if trimmed is None:
            continue
        results.append((m.group(0), trimmed))

    # Phase 8b R7 — F16: locative left-side intro `(於|在)X之Y`. Captures
    # X as a new claim element when the drafter introduces it via a
    # locative phrase (`於半導體基板之一主面側` registers `半導體基板`).
    # Same hygiene gate as F14 — component-suffix tail, no embedded
    # ref-prefix, no ADJ-head.
    for m in _F16_LOC_LEFT_INTRO_RE.finditer(text):
        noun = m.group('noun')
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        trimmed = _trim_capture_to_clean_noun_tw(normalized)
        if trimmed is None:
            continue
        results.append((m.group(0), trimmed))

    # Phase 8b R7 — F17: locative-internal intro `在X之間`. Specific
    # pattern where X is between two surfaces / volumes. Captures X as
    # the new element (`在矽層之間夾持` registers `矽層`).
    for m in _F17_LOC_INTERNAL_INTRO_RE.finditer(text):
        noun = m.group('noun')
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        trimmed = _trim_capture_to_clean_noun_tw(normalized)
        if trimmed is None:
            continue
        results.append((m.group(0), trimmed))

    # Phase 8b R7 — F15: colon-list bare-noun intros. After a trigger
    # verb + colon, register each ；/、/，-separated segment as a bare
    # noun intro. Each segment passes through the same hygiene gate as
    # F14 / F16 / F17 (component-suffix tail, no embedded ref-prefix,
    # no ADJ-head). TIPO sub-element listings often introduce multiple
    # claim elements after a single trigger verb.
    for m in _F15_COLON_LIST_ANCHOR_TW.finditer(text):
        list_text = m.group(1)
        for raw_segment in _F15_LIST_SPLIT_TW.split(list_text):
            seg = raw_segment.strip()
            if not seg or len(seg) < 2:
                continue
            # The segment may carry leading/trailing whitespace plus a
            # short verb-clause tail (like `閘極電極，係介隔...` after
            # comma-split; the `係...` is a separate fragment but if
            # split missed it, walk-back will trim). Run through walk-back.
            seg = re.sub(r'\([A-Za-z0-9]+\)', '', seg)
            trimmed = _trim_capture_to_clean_noun_tw(seg)
            if trimmed is None:
                continue
            results.append((seg, trimmed))
            # R30 mechanism #4 (2026-05-03): sub-noun extraction from
            # `<verb>X的Y` shape inside F15 list elements. Mirror of CN R30.
            # When a Pattern B element captures `處理末端執行器的所有任務`,
            # register both `末端執行器` and `所有任務` as separate intros.
            de_idx = trimmed.find('的')  # 的 (TW also uses 的 in modern register)
            if 0 < de_idx < len(trimmed) - 1:
                head = trimmed[:de_idx]
                tail = trimmed[de_idx + 1:]
                for sub in (head, tail):
                    sub_cjk = sum(1 for c in sub if '\u4e00' <= c <= '\u9fff')
                    if sub_cjk < 2:
                        continue
                    if sub.startswith(_REFERENCE_FORM_PREFIXES):
                        continue
                    sub_trimmed = _trim_capture_to_clean_noun_tw(sub)
                    if sub_trimmed is None:
                        continue
                    results.append((seg, sub_trimmed))

    # Phase 8b R7 — F19: `verb + X + 之 + Y` left-side intro. Register
    # the left-side X (verb's object) when followed by 之. Complements
    # F14 which registers right-side Y. F6 rejects this shape due to
    # the `(?![的之])` trailing lookahead; F19 explicitly handles it.
    for m in _F19_VERB_NP_ZHI_RE.finditer(text):
        noun = m.group('noun')
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        trimmed = _trim_capture_to_clean_noun_tw(normalized)
        if trimmed is None:
            continue
        results.append((m.group(0), trimmed))

    # Phase 8b R7 — F20: `(以|藉由|透過|經由) X (verb)` instrumental intro.
    # Register X as new claim element when used as means in preposition +
    # verb clause (`以閘極電極覆蓋`, `藉由矽層夾持`).
    for m in _F20_PREP_NP_VERB_RE.finditer(text):
        noun = m.group('noun')
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        trimmed = _trim_capture_to_clean_noun_tw(normalized)
        if trimmed is None:
            continue
        results.append((m.group(0), trimmed))

    # Uniform trailing-verb cleanup for all supplementary captures
    cleaned: list[tuple[str, str]] = []
    for orig, norm in results:
        cleaned_norm = clean_noun_phrase_tw(norm)
        if cleaned_norm and len(cleaned_norm) >= 2:
            cleaned.append((orig, cleaned_norm))

    # Phase B4 — R14f-analog conjunction-split: for each cleaned intro
    # containing 以及/和/與/及 with ≥2 CJK chars on each side, register
    # each element as its own intro so downstream 所述X / 所述Y references
    # can resolve when drafting captured the intro as X和Y.
    seen_norms = {norm for _, norm in cleaned}
    extras: list[tuple[str, str]] = []
    for _, norm in cleaned:
        m = _CONJ_SPLIT_RE_TW.match(norm)
        if not m:
            continue
        for piece in (m.group(1), m.group(2)):
            piece_clean = clean_noun_phrase_tw(piece)
            if not piece_clean or len(piece_clean) < 2:
                continue
            cjk = sum(1 for c in piece_clean if '\u4e00' <= c <= '\u9fff')
            if cjk < 2:
                continue
            if piece_clean.startswith(_REFERENCE_PREFIXES):
                continue
            if piece_clean in seen_norms:
                continue
            seen_norms.add(piece_clean)
            extras.append((piece_clean, piece_clean))

    # R31 (2026-05-03): generic 的 sub-noun extraction across all captured intros.
    # CN R31 mirror in Traditional script. Splits each cleaned intro on 的;
    # registers head and tail as separate intros if each is ≥2 CJK chars and
    # doesn't start with reference-prefix or ADJ-reject head.
    cleaned_subs = []
    for orig, norm in cleaned:
        de_idx = norm.find('的')  # 的
        if 0 < de_idx < len(norm) - 1:
            head = norm[:de_idx]
            tail = norm[de_idx + 1:]
            for sub in (head, tail):
                sub_cjk = sum(1 for c in sub if '\u4e00' <= c <= '\u9fff')
                if sub_cjk < 2:
                    continue
                if sub.startswith(_REFERENCE_PREFIXES):
                    continue
                if sub in seen_norms:
                    continue
                seen_norms.add(sub)
                cleaned_subs.append((orig, sub))
    cleaned.extend(cleaned_subs)

    # R31 second 的-split pass — handles X的Y的Z three-way splits.
    cleaned_subs2 = []
    for orig, norm in cleaned_subs:  # only re-split the newly added ones
        de_idx = norm.find('的')
        if 0 < de_idx < len(norm) - 1:
            head = norm[:de_idx]
            tail = norm[de_idx + 1:]
            for sub in (head, tail):
                sub_cjk = sum(1 for c in sub if '\u4e00' <= c <= '\u9fff')
                if sub_cjk < 2:
                    continue
                if sub.startswith(_REFERENCE_PREFIXES):
                    continue
                if sub in seen_norms:
                    continue
                seen_norms.add(sub)
                cleaned_subs2.append((orig, sub))
    cleaned.extend(cleaned_subs2)

    # R30 mechanism #6 (2026-05-03): parenthetical abbreviation bridging.
    # Mirror of CN R30. `<full term>(<Abbr>)` registers both full and Abbr.
    # R34 (2026-05-04): widen to cover two more shapes seen on the
    # post-R34 corpus baseline (Phase A cluster: TW `\u7b2c\u4e00U` 68 wfp /
    # `UE` 57 wfp / `\u4e00UE` 37 wfp, all 0-legit). Subsumes:
    #   1. Full-width \u5168\u89d2 parens \u2014 `\u4f7f\u7528\u8005\u8a2d\u5099\uff08UE\uff09` (JP/CN-translated
    #      drafts default to full-width punctuation; original ASCII-only
    #      regex missed 50 of 98 walker_fp findings in cluster).
    #   2. Lowercase-full-form-then-uppercase-abbrev \u2014 `\u4f7f\u7528\u8005\u8a2d\u5099(user
    #      equipment, UE)` (formal patent style: define foreign term
    #      first, then bracket the acronym; another 11 of 98).
    _PAREN_ABBREV_RE_R30_TW = re.compile(
        r'([\u4e00-\u9fff]{2,12})'
        r'[(\uff08]\s*'
        r'(?:[a-z][A-Za-z0-9\- ]{0,40}[,;\uff0c\uff1b]\s*)?'
        r'([A-Z][A-Za-z0-9\-]{0,15})'
        r'\s*[)\uff09]'
    )
    for pa_m in _PAREN_ABBREV_RE_R30_TW.finditer(text):
        full_noun = pa_m.group(1)
        abbrev = pa_m.group(2)
        if abbrev not in seen_norms and len(abbrev) >= 2:
            seen_norms.add(abbrev)
            extras.append((pa_m.group(0), abbrev))
        if full_noun not in seen_norms:
            seen_norms.add(full_noun)
            extras.append((pa_m.group(0), full_noun))

    # R30 mechanism #7 (2026-05-03): F6c Latin/short-CJK term floor.
    # Mirror of CN R30. <verb><Latin-noun> with right-boundary gate.
    _F6C_VERB_ALT_TW = (
        r'具有|包含|包括|含有|設有|設置|配置|安裝|裝設|形成|構成|提供|連接|連結'
        r'|獲取|獲得|得到|生成|產生|發出|發送|接收|輸出|輸入|傳送|存儲|確定|涉及'
        r'|進行|調用|運行|調整|建立|構建|製得|根據|存在|使用'
    )
    _F6C_LATIN_RE_TW = re.compile(
        r'(?:' + _F6C_VERB_ALT_TW + r')'
        r'(?P<noun>[A-Z][A-Za-z0-9\-]{1,15}[\u4e00-\u9fff]{0,8})'
        r'(?=[，,。；;、 \t\n或與和及])'
    )
    for fc_m in _F6C_LATIN_RE_TW.finditer(text):
        noun = fc_m.group('noun')
        if not noun or len(noun) < 2:
            continue
        if noun in seen_norms:
            continue
        seen_norms.add(noun)
        extras.append((fc_m.group(0), noun))

    # R30 mechanism #11 (2026-05-03): step-label colon intros.
    # Mirror of CN R30. `；以及<step-name>:` / `；<step-name>:`.
    _STEP_LABEL_RE_R30_TW = re.compile(
        r'[；;]\s*(?:以及|及)?\s*([\u4e00-\u9fff]{2,12})\s*[：:]'
    )
    for sl_m in _STEP_LABEL_RE_R30_TW.finditer(text):
        noun = sl_m.group(1)
        if not noun or len(noun) < 2:
            continue
        if noun.startswith(_REFERENCE_PREFIXES):
            continue
        if noun.startswith('第'):
            continue
        if noun in seen_norms:
            continue
        seen_norms.add(noun)
        extras.append((sl_m.group(0), noun))

    # R37 (2026-05-04): F22 — list-item bare-noun extraction WITHOUT
    # a colon trigger. Phase A on the post-R36 corpus surfaced ~85
    # walker_fp findings per 100 patents (extrapolated ~800 across
    # the full TW corpus) where the parent claim introduces multiple
    # ordinal-prefixed components in a comma-list:
    #   `導電端子包括差分訊號端子、第一接地端子以及第二接地端子`
    # F15 requires a `:` colon after the trigger verb; this F22
    # variant accepts a bare comma-list (one or more `、` between
    # nouns) directly after the trigger verb. The presence of `、`
    # is the disambiguating signal for "this is a list" vs the
    # possessive `<noun>的<noun>` or modifier sequence shapes that
    # would otherwise false-fire.
    # R44 (2026-05-04): expand triggers to 具有/具備/設有/含有 BUT only
    # when the captured list has >=2 commas (3+ items) — single-comma
    # lists with these triggers were too noisy on R37 gate-3
    # spec-support test (TW JP-translation fixture +1). 3+ items
    # strongly signal a list (not a possessive or modifier sequence).
    _F22_NO_COLON_LIST_TW = re.compile(
        r'(?:包括|包含)'
        r'((?:[一-鿿]{2,12}[、，])+'
        r'(?:[一-鿿]{2,12}(?:以及|及|和|或))?'
        r'[一-鿿]{2,12})'
        r'|'
        r'(?:具有|具備|設有|含有)'
        r'((?:[一-鿿]{2,12}[、，]){2,}'
        r'(?:[一-鿿]{2,12}(?:以及|及|和|或))?'
        r'[一-鿿]{2,12})'
    )
    _F22_LIST_SPLIT_TW = re.compile(r'[、，]|以及|及|和|或')
    for fl_m in _F22_NO_COLON_LIST_TW.finditer(text):
        list_text = fl_m.group(1) or fl_m.group(2)
        if not list_text:
            continue
        for item_raw in _F22_LIST_SPLIT_TW.split(list_text):
            item = item_raw.strip()
            if not item or len(item) < 2:
                continue
            if item.startswith(_REFERENCE_PREFIXES):
                continue
            if not all('一' <= ch <= '鿿' for ch in item):
                continue
            if item in seen_norms:
                continue
            seen_norms.add(item)
            extras.append((fl_m.group(0), item))

    # R53 (2026-05-05): chemistry formula self-introducer.
    # TW pharmaceutical/chemistry drafters introduce formulas via:
    #   `(b)式(I)的免疫偶聯物` — without `一` quantifier prefix
    # Pattern A regex requires `一` lead-in so misses these. The notation
    # 式(I)/式(II)/化合物(I) etc. is universally chemistry-formula in TW
    # drafts; treat as self-introducing when present.
    #
    # Phase 1 supplement_v2 cluster `TAIL|TW|(I)` residual 44 wfp on
    # TW202502813A claim 1 `(b)式(I)的免疫偶聯物` shape.
    #
    # Match: 式|化合物|化學式 + (Roman numeral 1-3 chars or digit 1-3)
    _R53_FORMULA_RE_TW = re.compile(
        r'(?:式|化合物|化學式|結構式)'
        r'[(（]\s*'
        r'([IVXivx]{1,4}|[a-z]?[0-9]{1,3}[a-z]?)'
        r'\s*[)）]'
    )
    for m in _R53_FORMULA_RE_TW.finditer(text):
        # Use the full matched text as the intro form
        full = m.group(0)
        if full in seen_norms:
            continue
        seen_norms.add(full)
        extras.append((full, full))

    return cleaned + extras


def extract_introductions_tw(
    claim: Claim,
    *,
    strict_qualifier_matching: bool = False,
) -> list[tuple[str, str]]:
    """Extract introductions from a TW claim as (original, normalized) pairs.

    ``original`` is the FULL intro span captured by ``_INTRO_PATTERN``,
    quantifier prefix included (e.g. ``一第一電極`` → original=``一第一電極``,
    ``複數齒輪`` → original=``複數齒輪``). Preserving the quantifier lets
    the walker's strict-plural escape hatch detect whether the intro was
    plural by inspecting the leading characters via
    ``full_ref_starts_with_plural``.

    ``normalized`` is the result of running ``normalize_candidate_intro``
    on the bare noun (group 1), which strips quantifiers and trailing
    verbs so it can be compared symmetrically against normalized
    reference terms.

    Post-processing (F3) repairs three classes of greedy over-capture:
      1. Reference-marker truncation/discard + re-scan
      2. Embedded 一 splitting at non-word-internal positions
      3. Paren-numeral variant registration
    """
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for m in _INTRO_PATTERN.finditer(claim.text):
        original = m.group(0)
        bare_noun = m.group(1)

        # F3 post-processing: may produce multiple candidates from one match
        candidates = _postprocess_intro_capture(bare_noun, m, claim.text)

        for candidate in candidates:
            normalized = normalize_candidate_intro(
                candidate,
                strict_qualifier_matching=strict_qualifier_matching,
            )
            if not normalized:
                continue
            if normalized not in seen:
                seen.add(normalized)
                pairs.append((original, normalized))

    # --- Supplementary patterns (bare-noun intros without 一 prefix) ---
    # Supplementary `_extract_supplementary_intros` already applies its own
    # cleanup pipeline (interior cut + trailing strip + conjunction-split).
    # R7 (2026-04-30): also apply `strip_leading_verb_tw` so a captured
    # `製造方法` (from F14 on `之製造方法`) registers as `方法` after
    # stripping the leading 製造 verb prefix — matching the canonical
    # method-claim head-noun reference `該方法`.
    supplementary = _extract_supplementary_intros(claim.text)
    for orig, norm in supplementary:
        # R63 (2026-05-05): symmetric Arabic-ordinal normalization.
        # The main intro path runs `normalize_candidate_intro` which
        # applies `normalize_arabic_ordinal_to_cjk` first; supplementary
        # intros only ran `strip_leading_verb_tw`, so 第1間隔件 stayed
        # as 第1間隔件 in intros_by_term while reference 前述第1間隔件
        # normalized to 第一間隔件 (Arabic→CJK). Asymmetric → mismatch
        # → spurious walker_fp.
        # User-reported bug on 神秘黑屏哥.docx 2026-05-05 — claim 1
        # uses Arabic ordinals (第1間隔件 / 第2間隔件), all dep claims
        # using 前述第一間隔件 / 前述第二間隔件 emit incorrectly.
        norm = normalize_arabic_ordinal_to_cjk(norm)
        norm = strip_leading_verb_tw(norm)
        if not norm or norm in seen:
            continue
        # R32 (2026-05-04): drop intros with newline/colon — capture
        # crossed paragraph/label boundary. These leak to spec-support
        # (`其包含：\n一` from 110P000641 c4 — F-anchor over-captured
        # across `\n` boundary). Walker filters at emit boundary too,
        # but spec-support reads intros directly so guard here.
        if '\n' in norm or '：' in norm or ':' in norm:
            continue
        seen.add(norm)
        pairs.append((orig, norm))

    # R32 (2026-05-04): F-head-indep — capture the rightmost head noun
    # from `一種<modifier>的<HEAD>，` independent-claim preambles. Default
    # `_INTRO_PATTERN` (line 1432) uses `_NOUN_CHARS` which excludes `的`,
    # so a long preamble noun phrase like
    # `用於一第一無線通訊設備處的無線通訊的裝置`
    # captures only `種用` / `無線通訊` fragments — the head `裝置` is
    # never registered as an intro, and dependent-claim references like
    # `該裝置` flag walker_fp despite being well-formed.
    #
    # Conflict guard skips heads where `<head><positional-suffix>` exists
    # in the claim text (preserves CN115485995B c121-style protect:true
    # legit drafting errors from prefix-match over-resolution).
    for m in _F_HEAD_INDEP_RE_TW.finditer(claim.text):
        head = m.group('head')
        if not head or head in seen:
            continue
        if _f_head_indep_conflict_tw(head, claim.text):
            continue
        seen.add(head)
        pairs.append((m.group(0), head))

    return pairs


# R32 (2026-05-04): F-head-indep regex. Captures rightmost head noun in
# `一種<modifier>的<HEAD>，` independent-claim preambles. Modifier may
# span across embedded `的` (nested possessive); head is bare CJK 2-12
# chars terminated by punctuation lookahead. Conflict guard at
# registration time rejects heads that would create prefix-match
# over-resolution (head + positional-suffix form like 裝置側 collides
# with bare 裝置). CN R32 parity.
_F_HEAD_INDEP_RE_TW: re.Pattern[str] = re.compile(
    r'一種(?:[^，。；,;:：]{4,80})的'
    r'(?P<head>[一-鿿]{2,12})'
    r'(?=[，,。；;:：])'
)

_F_HEAD_POSITIONAL_SUFFIX_RE_TW: re.Pattern[str] = re.compile(
    r'(?:側|端|部|面|段|層|區|際|底|頂|前|後|左|右|內|外|上|下|側面|端面|端部|底部|頂部|前面|後面|左面|右面|內部|外部|上部|下部|內側|外側|內端|外端|內層|外層|內面|外面)'
)


def _f_head_indep_conflict_tw(head: str, claim_text: str) -> bool:
    """True if registering `head` would cause prefix-match over-resolution.

    See cn_claims._f_head_indep_conflict_cn for full reasoning. Mirror
    in Traditional script.
    """
    pattern = re.compile(
        re.escape(head)
        + r'(?:' + _F_HEAD_POSITIONAL_SUFFIX_RE_TW.pattern + r')'
        r'(?:[，,。；;:： \t]|$)'
    )
    return bool(pattern.search(claim_text))


def check_antecedent_basis(
    doc: TwPatentDocument,
    *,
    strict_plural_reference_matching: bool = False,
    strict_qualifier_matching: bool = False,
) -> list[dict]:
    """TW antecedent-basis BFS walker (Phase 8b, ADR-092 + ADR-095).

    Replaces the legacy regex-based check with a per-occurrence walker
    that mirrors the US walker's six-field finding shape:

        {
            "claim_id":       int,
            "term":           str,   # normalized noun (matching key)
            "reference_form": str,   # 該/所述/前述 + original noun
            "claim_text":     str,
            "suggested_match": dict | None,  # filled by Commit 5
            "cross_ref":      None,
        }

    Resolution algorithm:
      1. For each claim C, walk the full ancestor BFS chain
         (``get_ancestor_chain_tw``) per ADR-092.
      2. Collect introductions from every ancestor as a dict
         ``intros_by_term`` keyed on the normalized noun, with the
         shallowest (first-seen) ancestor claim id as the value.
      3. For each definite reference (該/所述/前述 + noun) in C, normalize
         via ``normalize_reference_term`` and look up the normalized term
         in ``intros_by_term``. If the term is absent, emit a finding.
      4. The strict_plural_reference_matching escape hatch (default
         False) additionally flags references that explicitly mark plural
         antecedence (該等/該些/...) when the matched intro was singular.

    Findings are deduped by ``(claim_id, term, reference_form)`` and
    sorted by ``(claim_id, term, reference_form)``.

    The walker is the data source: ``pipeline._run_tw_pipeline``
    populates ``AnalysisResult.antecedent_basis_issues`` with the return
    value, then ``to_report_data`` converts it into a CheckItem in the
    same way as US.
    """
    claims = doc.claims
    if not claims:
        return []

    # R61b (2026-05-05): TIPO-style 符號說明 lookup-table — built once
    # per document, used at emit-time for (a) confidence boost when a
    # finding's term is a declared element name, (b) did-you-mean
    # enrichment as a tertiary fallback when no chain intro matches,
    # (c) sub-categorization flag on the finding payload.
    #
    # NOT a walker silencer — see ``feedback_no_symbol_table_antecedent_bridge.md``.
    # symbol_table presence does not substitute for claim-level antecedent
    # under §26 第3項. Hand-labeled local fixtures show 9/9 in_st findings
    # are legit defects, so the boost direction is empirically validated.
    symbol_table_norms: set[str] = set()
    symbol_table_lookup: dict[str, str] = {}  # normalized → original name
    # R61c (2026-05-05): TIPO-authoritative <numeral, name> anchor.
    # 符號說明 entries map drawing numerals to element names per
    # 專利法施行細則 §17. When a claim reference like 該齒輪(10)
    # exactly matches an ST entry `10:齒輪`, the drafter has
    # explicitly anchored the element via numeral — that's TIPO's
    # authoritative use of 符號說明 (vs the loose presence flag of
    # R61b which was empirically negative).
    #
    # Corpus measurement (tests/eval/measure_tipo_anchor.py):
    #   paren_anchor_ok: 48 walker_fp, 0 legit (n=48 strict-judged) —
    #   100% silencing precision, validated. Strict exact-match rule
    #   protects the 110P000631US c11 第一銜接部銜接(222) legit case.
    symbol_table_pairs: dict[str, str] = {}  # numeral → original name
    # Pull from BOTH 符號說明 and 代表圖符號說明 (representative-drawing
    # symbols) — both are authoritative under TIPO 專利法施行細則 §17.
    # Some firms omit 代表圖符號說明 in working drafts but restore before
    # filing; the parser surfaces both fields independently and the
    # walker treats them as a unified lookup.
    for entry in list(doc.symbol_table or []) + list(
        getattr(doc, "representative_drawing_symbols", None) or []
    ):
        nm = (entry.name or "").strip()
        if len(nm) < 2:
            continue
        norm = normalize_candidate_intro(
            nm,
            strict_qualifier_matching=strict_qualifier_matching,
        )
        if norm and len(norm) >= 2:
            symbol_table_norms.add(norm)
            symbol_table_lookup.setdefault(norm, nm)
        # Numeral-keyed lookup for paren-anchor matching
        numeral = (entry.numeral or "").strip()
        if numeral and nm:
            symbol_table_pairs.setdefault(numeral, nm)

    issues: list[dict] = []

    for claim in claims:
        chain = get_ancestor_chain_tw(claim, claims)

        # R64 (2026-05-05): suppress walker emit when the chain doesn't
        # terminate at an independent claim (chain[-1].dependencies is
        # non-empty after BFS — signals a self-loop / cycle / dangling
        # parent ref upstream). The structural defect is surfaced
        # separately via selfDependent / circularDependency checks; the
        # cascading antecedent findings on every dependent of the broken
        # claim are confusing UX (the user sees "前述X not introduced"
        # for terms that ARE introduced in claim 1 but the chain just
        # can't reach there).
        # Empirical: 神秘黑屏哥.docx c4 deps=[4] (self-loop drafter typo)
        # propagates to c5 deps=[4] producing 7 cascade findings.
        # User-reported bug 2026-05-05.
        if chain and chain[-1].dependencies:
            continue

        # Map normalized intro term → (shallowest ancestor id, BFS depth).
        # Iteration order (chain[0] = current claim @ depth 0, chain[1] =
        # nearest parent @ depth 1, ...) means setdefault preserves the
        # shallowest occurrence. Depth is later used by the did-you-mean
        # tiebreaker so when two candidates score identically the nearer
        # ancestor wins.
        intros_by_term: dict[str, tuple[int, int]] = {}
        for depth, ancestor in enumerate(chain):
            for _, normalized in extract_introductions_tw(
                ancestor,
                strict_qualifier_matching=strict_qualifier_matching,
            ):
                intros_by_term.setdefault(normalized, (ancestor.id, depth))

        # R32 (2026-05-04): Path A equivalent for TW — chain-level
        # ordinal-prefix bridging. When a chain intro starts with `第N`
        # and `X` (the suffix) is not already an intro, register `X` as
        # a separate intro IFF:
        #   1. Multi-modifier ambiguity guard — no other ordinal-prefixed
        #      chain intro shares the same suffix `X` (preserves
        #      `第一X` + `第二X` → bare `X` ambiguous).
        #   2. Prefix-conflict guard — claim text doesn't contain
        #      `X<1-3 CJK>` shape that would create over-resolution via
        #      longest-prefix fallback (preserves `控制電路` ↔
        #      `控制電路A` distinct-element flagging).
        # Same chain-level bridge runs ONCE per walker iteration; uses
        # nearest-ancestor depth for the bridged entry (depth tiebreak
        # preserves did-you-mean ordering).
        _R32_ORDINAL_RE_TW = re.compile(r'^第[一二三四五六七八九十百0-9]+')
        suffix_count_chain: dict[str, int] = {}
        suffix_anchor_chain: dict[str, tuple[int, int]] = {}
        for norm, (ancestor_id, depth) in intros_by_term.items():
            mo = _R32_ORDINAL_RE_TW.match(norm)
            if not mo:
                continue
            suffix = norm[mo.end():]
            if len(suffix) < 2:
                continue
            suffix_count_chain[suffix] = suffix_count_chain.get(suffix, 0) + 1
            existing = suffix_anchor_chain.get(suffix)
            if existing is None or depth < existing[1]:
                suffix_anchor_chain[suffix] = (ancestor_id, depth)
        for suffix, count in suffix_count_chain.items():
            if count > 1:
                continue  # multi-modifier ambiguity
            if suffix in intros_by_term:
                continue
            # Prefix-conflict guard: scan claim text for <suffix><1-3 CJK>
            # which would be a distinct element prefix-matched by the
            # bridge. If present, do not bridge.
            conflict_re = re.compile(re.escape(suffix) + r'[一-鿿]{1,3}')
            has_conflict = False
            for ancestor in chain:
                if conflict_re.search(ancestor.text):
                    # check it's not just the suffix as part of `第N+suffix`
                    # (which is the source intro itself — not a conflict)
                    full = '第' + r'[一二三四五六七八九十百0-9]+' + re.escape(suffix)
                    full_re = re.compile(full)
                    # If conflict_re finds something but full_re consumes
                    # everything, no real conflict
                    text = ancestor.text
                    consumed = full_re.sub('', text)
                    if conflict_re.search(consumed):
                        has_conflict = True
                        break
            if has_conflict:
                continue
            intros_by_term[suffix] = suffix_anchor_chain[suffix]

        # R52 (2026-05-05): head-noun-suffix bridging for compound nouns.
        # When a chain intro is `<modifier><HEAD>` where HEAD is a known
        # compound head-noun suffix (組合物 / 化合物 / 溶液 / ...), register
        # `<HEAD>` separately so dep claims using the bare head can resolve.
        #
        # Phase 1 supplement_v2 cluster `HEAD/TAIL|TW|組合物` (59 wfp / 0
        # legit). Drafters of TW pharmaceutical claims write
        # `一種醫藥組合物` Pattern A but dependent claims back-reference
        # using `該組合物` (head noun only).
        #
        # Guards (mirror of R32 ordinal-bridge architecture):
        #   1. Multi-modifier ambiguity — when 2+ chain intros share the
        #      same HEAD suffix, skip (drafter intends them distinct).
        #   2. Conflict guard — if `<HEAD>` is already an intro, no-op.
        #   3. Suffix allowlist — narrow set of well-known compound
        #      head-nouns. Pharmaceutical/chemistry-heavy. R32's ordinal
        #      bridge handles modifier-of-component case (第一電極 →
        #      電極); R52 handles modifier-of-class case (醫藥組合物 →
        #      組合物).
        _R52_HEAD_SUFFIXES = (
            # Pharma/chemistry (R52 original)
            "組合物", "化合物", "溶液", "溶劑", "配方",
            "混合物", "複合物", "產物", "藥劑", "抗體",
            # R56 (2026-05-05): electronic/circuit head nouns. Phase 1
            # supplement_v2 clusters TAIL|TW|路系統 (46 wfp on
            # 電路系統 family), TAIL|TW|電晶體 (36 wfp), TAIL|TW|管理功能
            # (35 wfp), HEAD|TW|區塊鏈 (35 wfp), HEAD|TW|參考電 (34 wfp on
            # 參考電壓), HEAD|TW|定位輔 (32 wfp on 定位輔助). Drafters
            # introduce `<modifier>電路系統` (Pattern A) but dep claims
            # back-reference using just `電路系統` head.
            "電路系統", "電晶體", "區塊鏈", "管理功能",
            "參考電壓", "定位輔助", "操作單元", "傳送資訊",
        )
        head_count_chain: dict[str, int] = {}
        head_anchor_chain: dict[str, tuple[int, int]] = {}
        for norm, (ancestor_id, depth) in intros_by_term.items():
            for suffix in _R52_HEAD_SUFFIXES:
                if (
                    norm.endswith(suffix)
                    and len(norm) > len(suffix)  # has modifier prefix
                ):
                    head_count_chain[suffix] = (
                        head_count_chain.get(suffix, 0) + 1
                    )
                    existing = head_anchor_chain.get(suffix)
                    if existing is None or depth < existing[1]:
                        head_anchor_chain[suffix] = (ancestor_id, depth)
                    break
        for suffix, count in head_count_chain.items():
            if count > 1:
                continue  # multi-modifier ambiguity
            if suffix in intros_by_term:
                continue
            intros_by_term[suffix] = head_anchor_chain[suffix]

        # Dedup by normalized term within a claim — repeated greedy
        # captures of the same head noun (``該齒輪為金屬, 該齒輪設有齒``)
        # collapse to one finding. The displayable reference_form is
        # ``prefix + normalized_term`` so identical references print
        # identically across the report.
        #
        # Divergence from US walker: claims.py:254 keys dedup on the
        # raw two-tuple ``(term, reference_form)``. The TW walker uses
        # a single-key form on the *normalized* noun because the TW
        # regex captures multi-character noun spans greedily — the same
        # logical reference is captured with different trailing
        # fragments across occurrences (``該齒輪為``, ``該齒輪設``,
        # ``該齒輪所``), and a naive two-key dedup over those raw
        # fragments would inflate the finding count. Synthesizing a
        # canonical reference_form post-normalization (Option C from
        # the 2026-04-09 follow-up session) restores parity with the US
        # shape and is deferred to Phase 9, gated on a measured
        # baseline delta. See docs/architectural-decisions.md ADR-095
        # and the 2026-04-09 follow-up writeup for the decision trail.
        seen_terms: set[str] = set()
        for m in _REF_PATTERN_CAPTURE.finditer(claim.text):
            prefix = m.group("prefix")
            raw_noun = m.group("noun")
            if not raw_noun:
                continue

            # R62 (2026-05-05) paren-numeral closure: when the regex
            # length cap truncates inside an open paren-numeral
            # (e.g., 至少一個第一子區(104 — 12 chars, missing `)`), look
            # ahead in the claim text for the closing paren and extend.
            # Avoids 1015+ TW + 386 CN walker_fp findings caused by the
            # truncated capture failing to match symbol_table entries.
            raw_noun_end = m.end()
            if _PAREN_NUM_TRAIL_RE.search(raw_noun):
                if (
                    raw_noun_end < len(claim.text)
                    and claim.text[raw_noun_end] in (")", "）")
                ):
                    raw_noun = raw_noun + claim.text[raw_noun_end]
                    raw_noun_end += 1

            # R68d (2026-05-06): mid-能 noun extension for compound nouns
            # where 能 is internal (功能/性能/智能/換能器/官能基). See helper
            # _extend_neng_compound_tw above for the precursor whitelist
            # rationale. No-op when raw_noun's last char isn't a precursor
            # (preserves auxiliary-verb 能 behavior for `<X>能<verb>`).
            raw_noun, raw_noun_end = _extend_neng_compound_tw(
                raw_noun, raw_noun_end, claim.text
            )

            # R66 (revised 2026-05-05): state-modifier capture extension.
            # When raw_noun ends in a state-modifier suffix (狀/形 — pure
            # adjective/descriptor on its own) AND claim text continues
            # `的<head_noun>`, extend the capture to include the head.
            #
            # Without extension, walker emits with reference_form like
            # `前述島狀` — meaningless to drafter (`島狀` is "island-shape"
            # adjective, can't be the antecedent on its own). Drafter
            # actually wrote `前述島狀的奈米片積層體`. The extended capture
            # surfaces the full phrase so the finding is intelligible.
            #
            # Resolution proceeds normally with the extended term: if the
            # drafter ALSO introduced the same `<state>的<head>` form
            # (consistent intro+ref), exact-match resolves and walker is
            # silent. If the drafter only introduced the head noun (the
            # 神秘黑屏哥 c10 case — 奈米片積層體 introduced, but reference
            # adds `島狀的` qualifier), walker emits a real antecedent
            # finding showing the user the full state-modifier+head form
            # they wrote. Drafter can then either add the qualified form
            # to claim 1 or simplify the reference.
            #
            # Suffix gate (狀/形) prevents this extension from firing on
            # possessive references like `該電子裝置的一插槽` where 電子裝置
            # is a separate (often undefined) noun — those end in noun-class
            # suffixes (置/部/料), not state suffixes. Verified against TW
            # harness: 4 protect:true legit_drafting_error labels
            # (容納部/電子裝置/識別資料) end in non-state suffixes; gate
            # excludes them; walker emits as before.
            if (
                raw_noun.endswith(_STATE_MODIFIER_SUFFIXES_TW)
                and not raw_noun.startswith("第")
                and raw_noun_end < len(claim.text)
            ):
                m_de = _DE_HEAD_NOUN_RE.match(claim.text, raw_noun_end)
                if m_de:
                    head_raw = m_de.group("head")
                    raw_noun = raw_noun + "的" + head_raw
                    raw_noun_end = raw_noun_end + 1 + len(head_raw)

            full_ref = f"{prefix}{raw_noun}"
            normalized_term = normalize_reference_term(
                full_ref,
                strict_qualifier_matching=strict_qualifier_matching,
            )
            if not normalized_term:
                continue

            # Phase F F3 — Emit-suppression for walker degenerate captures.
            # Reject findings where the normalized term is structurally
            # not a noun phrase: bare reference prefix (該/所述/前述/該等/該些)
            # left behind by single-pass prefix strip on 該所述處理器, bare
            # quantifier (複數/多個/若干) left behind by interior-cut, or
            # common 2-char verb fragments the walker occasionally captures
            # from degenerate intro contexts (測量 from 該測量到的溫度感測值
            # where interior cut truncates past 到的 boundary).
            if normalized_term in _REFERENCE_PREFIXES:
                continue
            if normalized_term in _BARE_QUANTIFIER_TERMS_TW:
                continue
            if normalized_term in _WALKER_DEGENERATE_FRAGMENTS_TW:
                continue
            # R32 (2026-05-04): structural-residue filter — short residues
            # from interior-cut + leading-strip cascade; bare ordinals
            # missing head noun; statutory claim-citation boilerplate;
            # terms containing newlines/colons (capture crossed paragraph
            # or label boundary). Round-1 corpus measured ~1300 walker_fp
            # findings silenced at <2% legit_drafting_error collateral
            # (within LLM noise floor). Length check uses len(normalized_term)
            # directly — 1-char terms emerge from `該複數個` → `個`,
            # `該等相應X` → `相` cascades that pre-emit cleanup misses.
            if len(normalized_term) < 2:
                continue
            if _BARE_ORDINAL_RE_TW.match(normalized_term):
                continue
            if _CLAIM_CITATION_RE_TW.search(normalized_term):
                continue
            if '\n' in normalized_term or '：' in normalized_term or ':' in normalized_term:
                continue

            if normalized_term in seen_terms:
                continue
            seen_terms.add(normalized_term)

            # R64 (2026-05-05): preserve drafter's original ordinal form
            # for display. Walker matches on CJK-normalized term but UI
            # showing 第一 when draft has 第1 confuses the user. Restore
            # Arabic ordinal in displayed reference_form when raw has it.
            display_term = _restore_original_ordinals(normalized_term, raw_noun)
            reference_form = f"{prefix}{display_term}"

            # Resolution order:
            #   1. Exact normalized match against any ancestor intro.
            #   2. Paren-numeral asymmetry (F3 Rule 4): if the reference
            #      has NO trailing (...) but an intro has the same base
            #      noun WITH trailing (...), resolve. Guarded: if the
            #      reference itself has a paren numeral, it must match
            #      exactly (preserves L1/L2 typo detection).
            #   3. Longest-intro-prefix match — handles greedy regex
            #      captures that grabbed an in-claim verb past the head
            #      noun (e.g. captured ``控制器讀取`` vs intro 控制器).
            resolved_intro: str | None = None
            if normalized_term in intros_by_term:
                resolved_intro = normalized_term
            elif not re.search(r"\([^)]+\)$", normalized_term):
                # Reference has no paren numeral — try matching against
                # paren-stripped intro forms.
                for intro in intros_by_term:
                    stripped_intro = re.sub(r"\([^)]+\)$", "", intro)
                    if stripped_intro != intro and stripped_intro == normalized_term:
                        resolved_intro = intro
                        break
            if resolved_intro is None:
                best_len = 0
                for intro in intros_by_term:
                    if (
                        len(intro) >= 2
                        and len(intro) > best_len
                        and normalized_term.startswith(intro)
                    ):
                        best_len = len(intro)
                        resolved_intro = intro

            # R46 (2026-05-04): ordinal-prefix-to-Latin-abbrev bridge.
            # When reference is `第N<X>` where X is a short uppercase
            # Latin abbrev (2-5 chars), and bare `<X>` exists as an
            # intro in the chain, bridge. Common in 5G/wireless TIPO
            # drafts: parent intro `(UE)` paren-abbrev registers `UE`,
            # dep claim references `該第一UE` -> `第一UE`. The first/
            # second UE is a SPECIFIC INSTANCE of the generic UE class,
            # antecedent valid. Cluster Phase A on post-R44 corpus
            # showed TW `第一U` 68 wfp / `一UE` 37 wfp / `UE` 57 wfp
            # all 0-legit safe-silence clusters.
            if resolved_intro is None:
                m_ord = re.match(r'^第[一二三四五六七八九十百0-9]+', normalized_term)
                if m_ord:
                    bare = normalized_term[m_ord.end():]
                    if (
                        bare and 2 <= len(bare) <= 5
                        and bare.isupper() and bare.isascii()
                        and bare in intros_by_term
                    ):
                        resolved_intro = bare

            if resolved_intro is not None:
                # Number-neutral match satisfies the antecedent under
                # default semantics. Strict mode additionally requires
                # the reference's plurality to match the intro's.
                if not strict_plural_reference_matching:
                    continue
                if not detect_plural_reference(full_ref):
                    continue
                ancestor_id, _ = intros_by_term[resolved_intro]
                ancestor_claim = next(
                    (c for c in chain if c.id == ancestor_id), None
                )
                intro_was_plural = False
                if ancestor_claim is not None:
                    for original, normalized in extract_introductions_tw(
                        ancestor_claim,
                        strict_qualifier_matching=strict_qualifier_matching,
                    ):
                        if normalized != resolved_intro:
                            continue
                        if full_ref_starts_with_plural(original):
                            intro_was_plural = True
                            break
                if intro_was_plural:
                    continue

            # Did-you-mean layer (ADR-094): when neither exact match nor
            # longest-prefix fallback resolved the term, try character-
            # bigram Jaccard similarity against every ancestor intro. The
            # ordinal_guard pre-filter blocks pairs that differ only in
            # ordinal/polarity prefix (第一電極 vs 第二電極 score ~0.67 by
            # Jaccard but are intentionally distinct components).
            #
            # Tie-break: highest score wins; on ties the nearer ancestor
            # (smaller depth) wins; on remaining ties the dict insertion
            # order (source order within an ancestor) wins because dict
            # iteration is insertion-ordered in Python 3.7+.
            suggested_match: dict | None = None
            if resolved_intro is None:
                ref_tokens = tokenize_tw(normalized_term)
                best_score = 0.0
                best_depth: int | None = None
                for intro_term, (ancestor_id, depth) in intros_by_term.items():
                    if ordinal_guard(normalized_term, intro_term):
                        continue
                    score = jaccard(ref_tokens, tokenize_tw(intro_term))
                    if score < _DIDYOUMEAN_THRESHOLD:
                        continue
                    if (
                        score > best_score
                        or (
                            score == best_score
                            and (best_depth is None or depth < best_depth)
                        )
                    ):
                        best_score = score
                        best_depth = depth
                        suggested_match = {
                            "term": intro_term,
                            "claim_id": ancestor_id,
                        }

            # Self-suggest filter (round 3 fix): suppress suggestions
            # where the candidate term is byte-identical to the
            # normalized reference term. These are structurally
            # meaningless ("did you mean X? — yes, you wrote X") and
            # surface when the dedup layer can't catch them because
            # the displayed reference_form differs from the normalized
            # term. Architectural correctness fix, not a vocabulary
            # patch — universal across CJK.
            if (
                suggested_match is not None
                and suggested_match["term"] == normalized_term
            ):
                suggested_match = None

            # Phase B3 — DYM quality gate (R21-analog). Suppress DYM
            # candidates that are likely walker-extraction noise rather
            # than legitimate intros (length-ratio, leading-particle,
            # substring-wrap with stop-particle, modifier-expanded
            # superset per F5). Terminal-only.
            if (
                suggested_match is not None
                and _dym_quality_reject_tw(
                    normalized_term, suggested_match["term"]
                )
            ):
                suggested_match = None

            # Phase F5 — morphological-prefix fallback. When primary
            # DYM is absent (including after quality-gate suppression),
            # surface an ancestor intro sharing a leading CJK prefix of
            # ≥2 chars. Catches same-stem / different-suffix typos like
            # 使用者介面 (typo) → 使用者裝置 (intended) that fall below
            # the 0.40 Jaccard threshold due to differing suffix but
            # share a meaningful morphological stem.
            if suggested_match is None and resolved_intro is None:
                fallback = _morphological_prefix_fallback_tw(
                    normalized_term, intros_by_term
                )
                if fallback is not None:
                    suggested_match = fallback

            # R61b (2026-05-05) (b) — symbol_table did-you-mean enrichment.
            # Tertiary fallback after chain DYM + morphological-prefix
            # fallback both miss. Tries to surface a 符號說明 entry that
            # shares ≥3-char prefix with normalized_term. Marked
            # ``source: "symbol_table"`` so the UI can render a distinct
            # "declared in 符號說明 #N" hint instead of a normal
            # did-you-mean line. Empty when no good match found.
            if (
                suggested_match is None
                and resolved_intro is None
                and symbol_table_norms
            ):
                st_match = _symbol_table_dym_fallback_tw(
                    normalized_term, symbol_table_norms, symbol_table_lookup
                )
                if st_match is not None:
                    suggested_match = st_match

            # R61b (2026-05-05) (a)+(c) — symbol_table presence as
            # confidence input + finding payload tag.
            term_in_symbol_table = normalized_term in symbol_table_norms
            is_quoted_reference_format = bool(
                getattr(claim, "quoted_references", None)
            )

            # R61c (2026-05-05) — TIPO-authoritative <numeral, name>
            # anchor. When the original reference contains a paren-numeral
            # AND the symbol_table has matching numeral with name equal to
            # the term (after stripping the paren), this is an explicit
            # drafter anchor — silence by setting confidence to 0 (display
            # tier filters at threshold ≥ 50 will exclude it; the finding
            # remains in walker output for harness label-keyed accounting).
            tipo_authoritative_anchor = False
            paren_match = re.search(
                r"[（(]\s*(\d{1,4}[A-Za-z]{0,2})\s*[）)]",
                full_ref or "",
            )
            if paren_match and symbol_table_pairs:
                numeral = paren_match.group(1).strip()
                st_name = symbol_table_pairs.get(numeral)
                if st_name:
                    # Strip paren + reference-form prefix from term to get
                    # bare element name for exact-match comparison.
                    term_no_paren = re.sub(
                        r"[（(]\s*\d{1,4}[A-Za-z]{0,2}\s*[）)]", "", normalized_term
                    ).strip()
                    st_name_no_paren = re.sub(
                        r"[（(]\s*\d{1,4}[A-Za-z]{0,2}\s*[）)]", "", st_name
                    ).strip()
                    if (
                        term_no_paren
                        and st_name_no_paren
                        and term_no_paren == st_name_no_paren
                    ):
                        tipo_authoritative_anchor = True

            # Structural fingerprint (ADR-145) — surfaces the walker's
            # intro-pool size, whether a did-you-mean fallback fired, and
            # whether the candidate is cross-branch. No claim text, no
            # noun content — all counts and booleans.
            diagnostics = {
                "prefix_charlen": len(prefix),
                "term_charlen": len(normalized_term),
                "intros_pool_size": len(intros_by_term),
                "has_suggested_match": suggested_match is not None,
                "suggested_cross_branch": bool(
                    suggested_match and suggested_match.get("cross_branch")
                ) if suggested_match else False,
                "term_in_symbol_table": term_in_symbol_table,
                "is_quoted_reference_format": is_quoted_reference_format,
            }
            confidence_score = compute_confidence_score(
                term=normalized_term,
                prefix=prefix,
                intros_pool_size=len(intros_by_term),
                has_suggested_match=suggested_match is not None,
                suggested_cross_branch=bool(
                    suggested_match and suggested_match.get("cross_branch")
                ),
                # `best_score` is set inside the `resolved_intro is None`
                # branch above and remains in scope here; it may be 0.0
                # when suggested_match came from the morphological-prefix
                # fallback (which doesn't compute Jaccard).
                suggested_jaccard=(
                    best_score if suggested_match is not None else None
                ),
                suggested_same_claim=bool(
                    suggested_match
                    and suggested_match.get("claim_id") == claim.id
                ),
                term_in_symbol_table=term_in_symbol_table,
                is_quoted_reference_format=is_quoted_reference_format,
                reference_form=reference_form,
                jurisdiction="TW",
            )
            # R61c TIPO-authoritative silencer: drop confidence to 0 when
            # paren numeral + ST entry give explicit drafter anchor.
            # Empirically validated 100% silencing precision (48/48
            # walker_fp, 0/48 legit) on TW supplement_v2 corpus.
            if tipo_authoritative_anchor:
                confidence_score = 0
                diagnostics["tipo_authoritative_anchor"] = True
            issues.append(
                {
                    "claim_id": claim.id,
                    "term": normalized_term,
                    "reference_form": reference_form,
                    "claim_text": claim.text,
                    "suggested_match": suggested_match,
                    "cross_ref": None,
                    "diagnostics": diagnostics,
                    "document_dedup_key": make_document_dedup_key(
                        normalized_term, reference_form
                    ),
                    "confidence_score": confidence_score,
                    "term_in_symbol_table": term_in_symbol_table,
                    "tipo_authoritative_anchor": tipo_authoritative_anchor,
                }
            )

    issues.sort(key=lambda x: (x["claim_id"], x["term"], x["reference_form"]))
    return issues


def full_ref_starts_with_plural(text: str) -> bool:
    """True iff ``text`` begins with a plural quantifier marker.

    Helper for the strict_plural_reference_matching escape hatch. Kept
    module-level (not nested in the walker) so the import surface stays
    flat for tests.
    """
    return text.startswith(("複數", "多個", "數個", "複數個"))
