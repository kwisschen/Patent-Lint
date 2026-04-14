# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""CN claims analysis checks.

Twelve pure functions checking Chinese patent claim formatting
against CNIPA rules (专利法实施细则 and 审查指南).
"""

from __future__ import annotations

import re

from patentlint.analysis.cjk_ordinal_guard import ordinal_guard
from patentlint.analysis.cjk_tokenize import jaccard, tokenize_cn
from patentlint.models import CheckItem, Claim, CnPatentDocument

# ADR-103 (Phase 8c Stage 2): CN antecedent walker adopts tuple dedup
# (normalized_term, normalized_reference_form) from day 1. TW uses single-key
# dedup pending Phase 9 parity migration. See CLAUDE.md Phase 8c locked
# decision Q3 and Phase 9 follow-up #2.

# Did-you-mean Jaccard threshold (ADR-094). Char-bigram Jaccard at 0.40
# is the calibration v2 sweet spot from the TW walker; inherited for CN.
_DIDYOUMEAN_THRESHOLD_CN = 0.40

# ── Check 9 ──────────────────────────────────────────────────────────────


def check_claims_sequential(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Verify claim IDs are 1, 2, 3, ... N with no gaps."""
    claims = cn_doc.claims
    if not claims:
        return [CheckItem(
            status="pass",
            message="No claims to check.",
            message_key="check.cn.claims.sequential.pass",
            reference="审查指南",
        )]

    for i, claim in enumerate(claims):
        expected = i + 1
        if claim.id != expected:
            detail = f"expected {expected}, found {claim.id}"
            return [CheckItem(
                status="amend",
                message=f"Claim numbering is not sequential: {detail}.",
                message_key="check.cn.claims.sequential.amend",
                details=detail,
                details_key="details.cn.claimsSequential",
                details_params={"detail": detail},
                reference="审查指南",
            )]

    return [CheckItem(
        status="pass",
        message="Claim numbers are sequential.",
        message_key="check.cn.claims.sequential.pass",
        reference="审查指南",
    )]


# ── Check 10 ─────────────────────────────────────────────────────────────

_DEP_FORMAT_SINGLE = re.compile(r"如权利要求\s*\d+[\s\S]*?所述的")
_DEP_FORMAT_MULTI = re.compile(
    r"如权利要求\s*\d+[\s\S]*?中\s*任[一意]\s*项\s*所述的"
)


def check_dependency_format(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check dependent claims use the 如权利要求N所述的 format."""
    dependents = [c for c in cn_doc.claims if not c.independent]
    if not dependents:
        return [CheckItem(
            status="pass",
            message="No dependent claims to check.",
            message_key="check.cn.claims.dependencyFormat.pass",
            reference="专利法实施细则 §22",
        )]

    bad_count = 0
    for claim in dependents:
        if claim.multiple_dependent:
            if not _DEP_FORMAT_MULTI.search(claim.text):
                bad_count += 1
        else:
            if not _DEP_FORMAT_SINGLE.search(claim.text):
                bad_count += 1

    if bad_count:
        return [CheckItem(
            status="amend",
            message=f"{bad_count} dependent claim(s) lack proper dependency format.",
            message_key="check.cn.claims.dependencyFormat.amend",
            details=f"{bad_count} claims",
            details_key="details.cn.dependencyFormat",
            details_params={"count": str(bad_count)},
            reference="专利法实施细则 §22",
        )]

    return [CheckItem(
        status="pass",
        message="All dependent claims use proper dependency format.",
        message_key="check.cn.claims.dependencyFormat.pass",
        reference="专利法实施细则 §22",
    )]


# ── Check 11 ─────────────────────────────────────────────────────────────


def check_self_dependent(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check if any claim depends on itself."""
    bad = [c.id for c in cn_doc.claims if c.id in c.dependencies]

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Self-dependent claims found: {claims_str}.",
            message_key="check.cn.claims.selfDependent.amend",
            details=claims_str,
            details_key="details.cn.selfDependent",
            details_params={"claims": claims_str},
            reference="专利法实施细则 §22",
        )]

    return [CheckItem(
        status="pass",
        message="No self-dependent claims.",
        message_key="check.cn.claims.selfDependent.pass",
        reference="专利法实施细则 §22",
    )]


# ── Check 12 ─────────────────────────────────────────────────────────────


def check_forward_dependency(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check if any claim depends on a higher-numbered claim."""
    bad = [c.id for c in cn_doc.claims if any(d > c.id for d in c.dependencies)]

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Forward-referencing claims found: {claims_str}.",
            message_key="check.cn.claims.forwardDependency.amend",
            details=claims_str,
            details_key="details.cn.forwardDependency",
            details_params={"claims": claims_str},
            reference="专利法实施细则 §22",
        )]

    return [CheckItem(
        status="pass",
        message="No forward-referencing dependencies.",
        message_key="check.cn.claims.forwardDependency.pass",
        reference="专利法实施细则 §22",
    )]


# ── Check 13 ─────────────────────────────────────────────────────────────


def check_single_sentence(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Each claim must have exactly one 。 at the end."""
    bad_count = 0
    for claim in cn_doc.claims:
        text = claim.text.strip()
        period_count = text.count("。")
        if period_count != 1 or not text.endswith("。"):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="amend",
            message=f"{bad_count} claim(s) have invalid sentence structure.",
            message_key="check.cn.claims.singleSentence.amend",
            details=f"{bad_count} claims",
            details_key="details.cn.singleSentence",
            details_params={"count": str(bad_count)},
            reference="审查指南 第二部分第二章",
        )]

    return [CheckItem(
        status="pass",
        message="All claims are single sentences ending with 。.",
        message_key="check.cn.claims.singleSentence.pass",
        reference="审查指南 第二部分第二章",
    )]


# ── Check 14 ─────────────────────────────────────────────────────────────

# CJK char followed by optional space then 2-4 digits, not in parentheses
_BARE_NUMERAL = re.compile(
    r"(?<!\()(?<=[\u4e00-\u9fff])\s?\d{2,4}(?!\))"
)


def check_reference_numeral_parentheses(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Find reference numerals in claims not enclosed in parentheses."""
    bad_count = 0
    for claim in cn_doc.claims:
        if _BARE_NUMERAL.search(claim.text):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="verify",
            message=f"{bad_count} claim(s) have unparenthesized reference numerals.",
            message_key="check.cn.claims.refNumeralParens.verify",
            details=f"{bad_count} claims",
            details_key="details.cn.refNumeralParens",
            details_params={"count": str(bad_count)},
            reference="审查指南",
        )]

    return [CheckItem(
        status="pass",
        message="All reference numerals in claims are parenthesized.",
        message_key="check.cn.claims.refNumeralParens.pass",
        reference="审查指南",
    )]


# ── Check 15 ─────────────────────────────────────────────────────────────

# Extract subject name: text after the last 所述的 (or 的) before 。
_SUBJECT_RE = re.compile(r"所述的(.+?)(?:[，,]|$)")
_LEADING_QUANTIFIER = re.compile(r"^(?:一种|一个|该|所述|所述的)\s*")


def _extract_subject(claim_text: str) -> str:
    """Extract the subject name from a claim — text after last 所述的 before comma/end."""
    match = _SUBJECT_RE.search(claim_text)
    if match:
        return match.group(1).strip()
    return ""


def _normalize_subject(subject: str) -> str:
    """Strip leading quantifiers for comparison."""
    return _LEADING_QUANTIFIER.sub("", subject).strip()


def check_subject_name_consistency(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check dependent claim subjects match their parent claim subjects."""
    claims_by_id = {c.id: c for c in cn_doc.claims}
    dependents = [c for c in cn_doc.claims if not c.independent]

    if not dependents:
        return [CheckItem(
            status="pass",
            message="No dependent claims to check.",
            message_key="check.cn.claims.subjectConsistency.pass",
            reference="审查指南 第二部分第二章",
        )]

    bad_count = 0
    for claim in dependents:
        dep_subject = _extract_subject(claim.text)
        if not dep_subject or not claim.dependencies:
            continue
        parent_id = claim.dependencies[0]
        parent = claims_by_id.get(parent_id)
        if not parent:
            continue
        # For independent parent, extract the subject from preamble
        # (text before 其特征在于 or before first ，)
        parent_text = parent.text
        preamble_match = re.search(r"[.．。]\s*(.+?)(?:，|,|其特征)", parent_text)
        if preamble_match:
            parent_subject = preamble_match.group(1).strip()
        else:
            parent_subject = ""

        if (dep_subject and parent_subject
                and _normalize_subject(dep_subject) != _normalize_subject(parent_subject)):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="verify",
            message=f"{bad_count} dependent claim(s) have inconsistent subject names.",
            message_key="check.cn.claims.subjectConsistency.verify",
            details=f"{bad_count} claims",
            details_key="details.cn.subjectConsistency",
            details_params={"count": str(bad_count)},
            reference="审查指南 第二部分第二章",
        )]

    return [CheckItem(
        status="pass",
        message="Dependent claim subject names are consistent.",
        message_key="check.cn.claims.subjectConsistency.pass",
        reference="审查指南 第二部分第二章",
    )]


# ── Check 16 ─────────────────────────────────────────────────────────────

_TRANSITION_PHRASES = re.compile(r"其特征在于|其特征是|其改进在于")


def check_transition_phrase(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check independent claims contain a characterizing transition."""
    independents = [c for c in cn_doc.claims if c.independent]
    if not independents:
        return [CheckItem(
            status="pass",
            message="No independent claims to check.",
            message_key="check.cn.claims.transitionPhrase.pass",
            reference="审查指南",
        )]

    bad_count = 0
    for claim in independents:
        if not _TRANSITION_PHRASES.search(claim.text):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="verify",
            message=f"{bad_count} independent claim(s) lack a transition phrase.",
            message_key="check.cn.claims.transitionPhrase.verify",
            details=f"{bad_count} claims",
            details_key="details.cn.transitionPhrase",
            details_params={"count": str(bad_count)},
            reference="审查指南",
        )]

    return [CheckItem(
        status="pass",
        message="All independent claims contain a transition phrase.",
        message_key="check.cn.claims.transitionPhrase.pass",
        reference="审查指南",
    )]


# ── Check 17 ─────────────────────────────────────────────────────────────

_TW_TERMS = re.compile(r"请求项|請求項")


def check_tw_terminology(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Scan claims for Taiwan-specific terminology."""
    for claim in cn_doc.claims:
        if _TW_TERMS.search(claim.text):
            return [CheckItem(
                status="verify",
                message="Taiwan-specific terminology found in claims.",
                message_key="check.cn.claims.twTerminology.verify",
                details_key="details.cn.twTerminology",
                reference="",
            )]

    return [CheckItem(
        status="pass",
        message="No Taiwan-specific terminology found.",
        message_key="check.cn.claims.twTerminology.pass",
        reference="",
    )]


# ── Check 18 ─────────────────────────────────────────────────────────────

_SPEC_REF = re.compile(r"如说明书|如图|参见说明书|参见图|参照说明书|参照附图")


def check_claims_spec_reference(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check if claims reference the specification or drawings for scope."""
    bad_count = 0
    for claim in cn_doc.claims:
        if _SPEC_REF.search(claim.text):
            bad_count += 1

    if bad_count:
        return [CheckItem(
            status="amend",
            message=f"{bad_count} claim(s) reference the specification or drawings.",
            message_key="check.cn.claims.specReference.amend",
            details=f"{bad_count} claims",
            details_key="details.cn.claimsSpecReference",
            details_params={"count": str(bad_count)},
            reference="审查指南 第二部分第二章",
        )]

    return [CheckItem(
        status="pass",
        message="No claims reference the specification or drawings.",
        message_key="check.cn.claims.specReference.pass",
        reference="审查指南 第二部分第二章",
    )]


# ── Check 19 ─────────────────────────────────────────────────────────────


def check_multi_multi_dependency(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Find claims that multiply-depend on another multiple-dependent claim."""
    multi_dep_ids = {c.id for c in cn_doc.claims if c.multiple_dependent}
    bad = []
    for claim in cn_doc.claims:
        if claim.multiple_dependent:
            if any(d in multi_dep_ids for d in claim.dependencies):
                bad.append(claim.id)

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Multiple-dependent claim(s) depend on other multiple-dependent claims: {claims_str}.",
            message_key="check.cn.claims.multiMultiDep.amend",
            details=claims_str,
            details_key="details.cn.multiMultiDep",
            details_params={"claims": claims_str},
            reference="专利法实施细则 §22",
        )]

    return [CheckItem(
        status="pass",
        message="No chained multiple dependencies.",
        message_key="check.cn.claims.multiMultiDep.pass",
        reference="专利法实施细则 §22",
    )]


# ── Check 20 ─────────────────────────────────────────────────────────────


def check_dependent_ordering(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check dependents of each independent claim appear consecutively."""
    claims = cn_doc.claims
    if not claims:
        return [CheckItem(
            status="pass",
            message="No claims to check.",
            message_key="check.cn.claims.dependentOrdering.pass",
            reference="审查指南 第二部分第二章",
        )]

    # Build map: for each independent claim, find the last position of
    # any dependent that references it (directly or transitively via chain).
    # Then check no dependent of an earlier independent appears after a later
    # independent.

    # Find independent claim positions
    indep_positions = []
    for i, c in enumerate(claims):
        if c.independent:
            indep_positions.append(i)

    if len(indep_positions) < 2:
        return [CheckItem(
            status="pass",
            message="Dependent claim ordering is correct.",
            message_key="check.cn.claims.dependentOrdering.pass",
            reference="审查指南 第二部分第二章",
        )]

    # For each independent claim, find the "group boundary" — the position
    # of the next independent claim. Any dependent that references the
    # earlier independent but appears after the next independent is out of order.
    claims_by_id = {c.id: c for c in claims}

    def root_independent(claim_id: int, visited: set | None = None) -> int | None:
        """Trace dependency chain to find the root independent claim."""
        if visited is None:
            visited = set()
        if claim_id in visited:
            return None
        visited.add(claim_id)
        c = claims_by_id.get(claim_id)
        if not c:
            return None
        if c.independent:
            return c.id
        if c.dependencies:
            return root_independent(c.dependencies[0], visited)
        return None

    # Check: after each independent claim, all claims until the next
    # independent should depend (transitively) on the current or a
    # preceding independent claim, not on a later one.
    for idx in range(len(indep_positions) - 1):
        current_indep_pos = indep_positions[idx]
        next_indep_pos = indep_positions[idx + 1]

        # Check claims after next_indep_pos to see if any reference
        # the current independent
        current_indep_id = claims[current_indep_pos].id
        for j in range(next_indep_pos + 1, len(claims)):
            c = claims[j]
            if not c.independent:
                root = root_independent(c.id)
                if root == current_indep_id:
                    return [CheckItem(
                        status="amend",
                        message="Dependent claims are not grouped with their independent claim.",
                        message_key="check.cn.claims.dependentOrdering.amend",
                        details_key="details.cn.dependentOrdering",
                        reference="审查指南 第二部分第二章",
                    )]

    return [CheckItem(
        status="pass",
        message="Dependent claim ordering is correct.",
        message_key="check.cn.claims.dependentOrdering.pass",
        reference="审查指南 第二部分第二章",
    )]


# ─────────────────────────────────────────────────────────────────────────
# Phase 8c Stage 2 — CN antecedent-basis BFS walker
# ─────────────────────────────────────────────────────────────────────────
#
# Mechanical port of the TW walker (tw_claims.py lines 771–2390) with
# TC→SC character swap per v2 swap table. Historical tuning rationale
# lives in tw_claims.py; see ADR-095/096/097/098/099/100/101 for the
# invariants preserved here. Phase 8c audit-locked divergences:
#
#   Q1: 该等 strict-rejected (tw_contamination finding category). The
#       SC reference-prefix tuples omit 该等/该些 entirely — see Step 1
#       exception 4 of the Stage 2 port prompt.
#   Q2: 朝向 retained in _INTERIOR_VERB_BOUNDARIES_CN (carried over by
#       construction — already in TW set at tw_claims.py line 1319).
#   Q3: tuple dedup (normalized_term, normalized_reference_form) from
#       day 1 (ADR-103). TW uses single-key; parity migration is a
#       Phase 9 follow-up.
#   Q4: 独 added to _WORD_INTERNAL_YI_PREDECESSORS_CN defensively.
#
# Constants and functions carry `_CN` / `_cn` suffixes. The walker
# returns list[dict] like TW; _run_cn_pipeline wraps a summary CheckItem.

# ── Walker normalization constants ───────────────────────────────────────

# Noun exclusion class (mechanical TC→SC swap per v2 § 4).
_NOUN_CHARS_CN = r"[^\s，。；：、及与和之的该将能须应皆被于以并且其而还另时在]{2,12}"

# Introduction multi-char quantifiers (TC→SC glyph swap).
_INTRO_MULTI_QUANTIFIERS_CN = (
    "一或多个",
    r"至少[一二三四五六七八九十百千\d]+个?",
    "两个",
    r"两(?![端侧])",
    r"[二三四五六七八九十]+个",
    "一个", "一种", "一对",
    "复数个", "多个", "数个",
    "复数",
)

# Weight/molar composition intro (TC→SC).
_WEIGHT_UNITS_CN = r"(?:重量份|重量百分比|摩尔|wt%|mol%)"
_WEIGHT_COMPOSITION_PREFIX_CN = (
    r"\d+(?:\.\d+)?" + _WEIGHT_UNITS_CN
    + r"(?:至\d+(?:\.\d+)?" + _WEIGHT_UNITS_CN + r")?的"
)

# Definitional intro (mechanical TC→SC swap per v2 § 4).
_DEFINITIONAL_PREFIX_CN = r"(?:定义为|称为|记为|表示为)一?"

_INTRO_PATTERN_CN = re.compile(
    r"(?:"
    + _WEIGHT_COMPOSITION_PREFIX_CN
    + r"|" + _DEFINITIONAL_PREFIX_CN
    + r"|(?:" + "|".join(_INTRO_MULTI_QUANTIFIERS_CN) + r"|(?<!第)一(?![同体])))"
    + f"({_NOUN_CHARS_CN})"
)

# Reference prefixes — Q1 strips 该等/该些 from CN tuples entirely.
# The TC-contamination prefixes live only in check_antecedent_basis_cn
# (see the Q1 tw_contamination rejection branch); no module-level
# constant names them.
_REFERENCE_PREFIXES_CN = ("所述", "前述", "该")
# Negative lookahead on bare 该: suppress matches on 该等/该些 so the
# Q1 tw_contamination rejection (in check_antecedent_basis_cn) is the
# sole handler of those forms. 所述/前述 have no collision.
_REF_PATTERN_CAPTURE_CN = re.compile(
    r"(?P<prefix>所述|前述|该(?![等些]))"
    + f"(?P<noun>{_NOUN_CHARS_CN})"
)

# Trailing-verb denylist (mechanical TC→SC swap; historical rationale in
# tw_claims.py lines 869–990).
_TRAILING_VERB_DENYLIST_CN: tuple[str, ...] = tuple(sorted(
    (
        "包含", "包括", "含有", "具有", "系", "为", "是", "设有", "具备",
        "通过", "经由", "借由", "基于", "透过", "根据", "依据",
        "还包含", "还包括",
        "并且", "以及",
        "并", "且", "其", "其中", "还", "另",
        "包", "通", "经", "借",
        "所", "前",
        "到", "出",
        "介",
        "位",
        "或",
        "中",
        "后",
        "用",
        "上",
        "内",
        "分别", "皆",
        "处",
        "至",
        "依序",
        "撷取",
        # Stage 4 R1 D4a — ADR-100 pattern, CN-specific extensions
        "相关", "有关",
    ),
    key=len,
    reverse=True,
))

# Noun-like single-char trailing suffixes with residual ≥ 3 guard.
_NOUNLIKE_SINGLE_CHAR_SUFFIXES_CN: frozenset[str] = frozenset(
    {"所", "位", "中", "后", "用", "上", "内", "撷取"}
)

# Relaxed-guard subset (residual ≥ 2 instead of ≥ 3).
# Stage 4 R1 D4a — relaxed residual ≥ 2 guard for 2-char-stem residue strip
_NOUNLIKE_RELAXED_SUFFIXES_CN: frozenset[str] = frozenset(
    {"上", "内", "后", "中", "用"}
)

# Leading quantifier denylist (TC→SC).
_LEADING_QUANTIFIER_DENYLIST_CN: tuple[str, ...] = tuple(sorted(
    (
        "一或多个",
        "至少一个", "至少一",
        "一个", "一种", "一对",
        "复数个", "多个", "数个",
        "复数",
        "一",
    ),
    key=len,
    reverse=True,
))

# Reference-form prefixes stripped from reference terms only (Q1: 该等/
# 该些 excluded per Step 1 exception 4 of the port prompt).
_REFERENCE_FORM_PREFIXES_CN: tuple[str, ...] = tuple(sorted(
    ("所述", "前述", "该"),
    key=len,
    reverse=True,
))

# Plural reference-form prefixes — Q1 excludes 该等/该些 from CN;
# the strict_plural_reference_matching escape hatch fires on the
# remaining 前述/所述 plural markers.
_PLURAL_REFERENCE_PREFIXES_CN: tuple[str, ...] = tuple(sorted(
    ("前述复数", "所述复数", "所述多个"),
    key=len,
    reverse=True,
))

# Interior-boundary tokens (mechanical TC→SC swap). See tw_claims.py
# lines 1138–1331 for the historical risk-review rationale per verb.
_INTERIOR_VERB_BOUNDARIES_CN: tuple[str, ...] = tuple(sorted(
    (
        "设有", "包含", "包括", "具有", "含有", "具备",
        "系为", "系于", "为", "是", "系",
        "所述", "前述", "该等", "该些",
        "传送接收到", "传送一显示影像资", "输出一解锁指令至",
        "通讯连接时", "电性连接", "被带动而向", "分别定义",
        "无法存取", "设置有", "拔除时",
        "连接一第一电子装", "撷取一使用者",
        "电性连", "所施予", "将带动", "被带动",
        "对应", "相对", "相反", "响应", "解锁",
        "读取", "写入", "计算", "处理", "感测",
        "侦测", "监控", "监测", "调整", "修改",
        "更新", "删除", "增加", "减少", "选择",
        "决定", "判别", "辨识", "驱动",
        "定义", "启始", "判断", "持续", "涵盖", "放大", "存取",
        "构成", "设置",
        "透过", "通过", "经由", "借由",
        "基于", "根据", "依据",
        "染色",
        "识别", "传送", "接收",
        "到", "形成", "锁合", "传输",
        "连接", "旋转", "带动", "筛选",
        "区分",
        "显示", "上传", "浏览",
        "产生", "各地",
        "依序",
        "相互", "朝向",
        # Stage 4 R2' D1a — 调出 cuts after 处理器指令 prefix (Huawei c3)
        "调出",
    ),
    key=len,
    reverse=True,
))

# Stage 4 R2' D3 — 1-char noun prefixes get a relaxed position gate
# (>= 1 instead of > 1) so interior-verb cuts can fire at idx 1. Without
# this, captures like 边包括实线边 / L具有选自 can never be truncated.
_ONE_CHAR_NOUN_PREFIXES_CN: frozenset[str] = frozenset(
    {"边", "面", "体", "键", "L", "X", "Y", "Z", "M", "N", "R"}
)

# Interior-cut exception set — mechanical TC→SC swap per v2 swap table;
# compound-level re-seeding deferred to Stage 4.
_INTERIOR_CUT_EXCEPTIONS_CN: frozenset[str] = frozenset({
    "连接器", "连接部", "连接端口", "连接点", "连接线",
    "第一连接部", "第二连接部", "第三连接部",
    "电连接器", "电性连接部",
    "编码器", "解码器", "旋转编码器", "光学编码器",
    "识别码", "识别资料", "识别信息", "识别号", "识别子",
    "通讯模块", "通讯端口", "通讯单元", "通讯接口",
    "行动通讯模块", "无线通讯模块", "有线通讯模块",
    "第一通讯模块", "第二通讯模块",
    "第一无线通讯模块", "第二无线通讯模块", "第三无线通讯模块",
    "传送器", "接收器", "发射器", "发送器", "收发器",
    "认证单元", "认证模块", "认证装置", "认证功能单元",
    "衔接部", "第一衔接部", "第二衔接部", "第三衔接部",
    "扣接部", "第一扣接部", "第二扣接部",
    "后轮", "前轮", "传动轮", "从动轮", "主动轮",
    "曲柄", "踏板", "弧面", "第一弧面", "第二弧面",
    "轮轴", "传动件",
    "上端边缘", "下端边缘", "外侧边缘", "内侧边缘",
    "容纳部", "容置部", "容置杯体", "杯体",
    "环形压接部", "压接部", "压接环",
    "开口部", "封闭部",
    "顶壁", "底壁", "侧壁", "顶部", "底部", "侧部",
    "数位内容", "适地性数位内容", "主题标签",
    "浏览程式", "伺服器", "用户界面",
    "放大器",
    "染色墨水",
    "带动轮",
    "显示器", "显示装置", "显示单元",
    "浏览器",
    "波产生器",
    "连接面", "第一连接面", "第二连接面",
    # Stage 4 R2' D1a — Huawei CN113939805B 处理器指令 compound
    "第一处理器指令", "第二处理器指令",
})


# ── Walker normalization functions ───────────────────────────────────────


def clean_noun_phrase_cn(text: str) -> str:
    """Strip trailing verbs and conjunction fragments from a CN reference term.

    Two-phase cleanup mirroring ``clean_noun_phrase_tw``:
      1. Interior-verb truncation with prefix-aware exception protection.
      2. Trailing-verb stripping (iterative, with residual guards).

    See tw_claims.py::clean_noun_phrase_tw for the full rationale.
    """
    if not text:
        return text

    def _longest_protected_prefix(s: str) -> int:
        for i in range(len(s), 1, -1):
            if s[:i] in _INTERIOR_CUT_EXCEPTIONS_CN:
                return i
        return 0

    protected_prefix_len = _longest_protected_prefix(text)
    search_text = text[protected_prefix_len:]
    search_offset = protected_prefix_len

    # Stage 4 R2' D3 (ADR-112): 1-char noun prefixes (边/L/etc.) relax the
    # position gate from > 1 to >= 1 so interior-verb cuts at idx 1 can
    # fire. Without this, a capture like 边包括实线边 cannot be truncated
    # because 包括 sits at idx 1 and the original gate blocks it.
    is_one_char_noun_prefix = (
        len(text) > 0
        and text[0] in _ONE_CHAR_NOUN_PREFIXES_CN
        and protected_prefix_len == 0
    )
    min_absolute_idx = 1 if is_one_char_noun_prefix else 2

    earliest_idx: int | None = None
    for verb in _INTERIOR_VERB_BOUNDARIES_CN:
        idx = search_text.find(verb)
        if idx >= 0 and (idx + search_offset) >= min_absolute_idx:
            absolute_idx = idx + search_offset
            if earliest_idx is None or absolute_idx < earliest_idx:
                earliest_idx = absolute_idx

    current = text[:earliest_idx] if earliest_idx is not None else text

    for _ in range(16):
        stripped = False
        for verb in _TRAILING_VERB_DENYLIST_CN:
            if not current.endswith(verb):
                continue
            if len(current) <= len(verb):
                continue
            if verb in _NOUNLIKE_SINGLE_CHAR_SUFFIXES_CN:
                min_residual = 2 if verb in _NOUNLIKE_RELAXED_SUFFIXES_CN else 3
                if (len(current) - len(verb)) < min_residual:
                    continue
            current = current[: -len(verb)]
            stripped = True
            break
        if not stripped:
            break
    return current


def strip_leading_quantifier_cn(text: str) -> str:
    """Strip one matching leading quantifier (ADR-095 Rule 2)."""
    if not text:
        return text
    for q in _LEADING_QUANTIFIER_DENYLIST_CN:
        if text.startswith(q) and len(text) > len(q):
            return text[len(q):]
    return text


def strip_reference_form_prefix_cn(text: str) -> str:
    """Strip one matching reference-form prefix (该/所述/前述)."""
    if not text:
        return text
    for prefix in _REFERENCE_FORM_PREFIXES_CN:
        if text.startswith(prefix) and len(text) > len(prefix):
            return text[len(prefix):]
    return text


# Leading qualifier strip (relational + position qualifiers with
# quantifier lookahead). See tw_claims.py lines 1580–1666 for rationale.
_LEADING_RELATIONAL_QUALIFIERS_CN: tuple[str, ...] = (
    "对应地", "对应的", "对应",
    "相应地", "相应的", "相应",
    "相对地", "相对的", "相对",
    "相关地", "相关的", "相关",
)

_LEADING_POSITION_QUALIFIERS_CN: tuple[str, ...] = ("前", "后")
_QUANTIFIER_AFTER_POSITION_CN: tuple[str, ...] = (
    "一或多个",
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "复数", "多个", "数个", "至少",
)


def strip_leading_qualifier_cn(
    text: str,
    *,
    strict_qualifier_matching: bool = False,
) -> str:
    """Strip leading qualifier modifiers from a normalized reference term.

    Relational qualifiers stripped unconditionally; position qualifiers
    (前/后) only when followed by a quantifier. Strict mode disables
    the strip entirely. See tw_claims.py::strip_leading_qualifier.
    """
    if strict_qualifier_matching or not text:
        return text

    for q in _LEADING_RELATIONAL_QUALIFIERS_CN:
        if text.startswith(q) and len(text) > len(q):
            return text[len(q):]

    for q in _LEADING_POSITION_QUALIFIERS_CN:
        if text.startswith(q) and len(text) > len(q):
            remainder = text[len(q):]
            for quant in _QUANTIFIER_AFTER_POSITION_CN:
                if remainder.startswith(quant):
                    return remainder

    return text


def normalize_reference_term_cn(
    text: str,
    *,
    strict_qualifier_matching: bool = False,
) -> str:
    """Normalize a flagged reference term for antecedent matching."""
    t = strip_reference_form_prefix_cn(text)
    t = strip_leading_qualifier_cn(t, strict_qualifier_matching=strict_qualifier_matching)
    t = clean_noun_phrase_cn(t)
    t = strip_leading_quantifier_cn(t)
    return t


def normalize_candidate_intro_cn(
    text: str,
    *,
    strict_qualifier_matching: bool = False,
) -> str:
    """Normalize an introduction candidate for antecedent matching.

    Symmetric with normalize_reference_term_cn per ADR-098; the trailing
    strip_reference_form_prefix_cn is load-bearing for intros where
    the _INTRO_PATTERN_CN captures a reference-prefix artifact as part
    of the bare noun group.
    """
    t = strip_leading_qualifier_cn(text, strict_qualifier_matching=strict_qualifier_matching)
    t = clean_noun_phrase_cn(t)
    t = strip_leading_quantifier_cn(t)
    t = strip_reference_form_prefix_cn(t)
    return t


def detect_plural_reference_cn(text: str) -> bool:
    """Return True iff text starts with a plural reference-form prefix."""
    return any(text.startswith(p) for p in _PLURAL_REFERENCE_PREFIXES_CN)


def get_ancestor_chain_cn(claim: Claim, all_claims: list[Claim]) -> list[Claim]:
    """Return [claim, ...ancestors] walking the full multi-parent BFS.

    Per ADR-092, the walker uses the FULL ancestor chain. Stage 1.5
    invariant: trusts ``parse_cn_claims_docx`` dependency shape verbatim
    — no self-ref stripping, no spec expansion. Both already handled
    upstream at claims_cn.py:40-59 and claims_cn.py:90.
    """
    claims_by_id = {c.id: c for c in all_claims}
    chain: list[Claim] = [claim]
    visited: set[int] = {claim.id}
    queue: list[int] = list(claim.dependencies)
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
    return chain


# Q4 (defensive): 独 added to the CN predecessor set. Confirm in Stage 4
# corpus tuning whether it surfaces 独一X patterns as word-internal.
_WORD_INTERNAL_YI_PREDECESSORS_CN = frozenset("第另任某唯同单统独")

_SPLIT_YI_NOUN_RE_CN = re.compile(r"一(" + _NOUN_CHARS_CN + r")")


def _postprocess_intro_capture_cn(
    bare_noun: str,
    match: re.Match,  # type: ignore[type-arg]
    claim_text: str,
) -> list[str]:
    """Post-process a greedy _INTRO_PATTERN_CN capture to repair over-captures.

    Same three-rule repair pipeline as the TW walker's
    ``_postprocess_intro_capture``: ref-marker check + truncation,
    embedded 一 splitting, re-scan for discarded spans.
    """
    # Rule 1a
    for prefix in _REFERENCE_FORM_PREFIXES_CN:
        if bare_noun.startswith(prefix):
            recovered = _rescan_for_yi_cn(
                match.group(0), match.start(), claim_text,
            )
            if recovered:
                return recovered
            remainder = bare_noun[len(prefix):]
            return [remainder] if remainder else []

    # Rule 1b
    for prefix in _REFERENCE_FORM_PREFIXES_CN:
        idx = bare_noun.find(prefix)
        if idx > 0:
            bare_noun = bare_noun[:idx]
            break

    # Rule 2: embedded 一 splitting
    candidates: list[str] = []
    yi_positions = [i for i, ch in enumerate(bare_noun) if ch == "一" and i > 0]

    if not yi_positions:
        return [bare_noun]

    split_pos: int | None = None
    for pos in yi_positions:
        preceding_char = bare_noun[pos - 1]
        if preceding_char not in _WORD_INTERNAL_YI_PREDECESSORS_CN:
            split_pos = pos
            break

    if split_pos is None:
        return [bare_noun]

    leading_part = bare_noun[:split_pos]
    if leading_part:
        candidates.append(leading_part)

    abs_start = match.start() + (len(match.group(0)) - len(match.group(1))) + split_pos
    remaining_text = claim_text[abs_start:]
    yi_match = _SPLIT_YI_NOUN_RE_CN.match(remaining_text)
    if yi_match:
        candidates.append(yi_match.group(1))
    elif split_pos + 1 < len(bare_noun):
        candidates.append(bare_noun[split_pos + 1:])

    return candidates


def _rescan_for_yi_cn(
    full_span: str,
    span_start: int,
    claim_text: str,
) -> list[str]:
    """Re-scan a full matched span for 一 intro sites."""
    candidates: list[str] = []
    for i, ch in enumerate(full_span):
        if ch != "一":
            continue
        if i == 0:
            continue
        if full_span[i - 1] in _WORD_INTERNAL_YI_PREDECESSORS_CN:
            continue
        abs_pos = span_start + i
        remaining = claim_text[abs_pos:]
        yi_match = _SPLIT_YI_NOUN_RE_CN.match(remaining)
        if yi_match:
            candidates.append(yi_match.group(1))
    return candidates


# ── Supplementary bare-noun intro patterns (F9/F8/F7/F6/F5) ──────────────

_INSTRUMENTAL_PATTERN_CN = re.compile(
    r'透过([\u4e00-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)(?:连接|连结)',
)

_VP_MODIFIER_PATTERN_CN = re.compile(
    r'相配合的([\u4e00-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)',
)

# CJK char class excluding 的 (U+7684); jurisdiction-invariant.
_CJK_NO_DE_CN = r'[\u4e00-\u7683\u7685-\u9fff]'

_PARTICIPIAL_YI_DE_PATTERN_CN = re.compile(
    r'一[\u4e00-\u9fff]+?的(' + _CJK_NO_DE_CN + r'{2,}(?:\([A-Za-z0-9]+\))?)'
)

_POST_DE_ORDINAL_PATTERN_CN = re.compile(
    r'的(第[一二三四五六七八九十\d]+' + _CJK_NO_DE_CN + r'+(?:\([A-Za-z0-9]+\))?)'
)

_DE_NOUN_RE_CN = re.compile(
    r'的(' + _CJK_NO_DE_CN + r'{2,}(?:\([A-Za-z0-9]+\))?)'
)

_BARE_AFTER_VERB_PATTERN_CN = re.compile(
    r'(?:'
    r'具有|包含|包括|含有|设有'
    r'|'
    r'设置|配置|安装|装设'
    r'|'
    r'形成|构成'
    r'|'
    r'提供|连接|连结'
    r')'
    r'(第[一二三四五六七八九十\d]+' + _CJK_NO_DE_CN + r'+(?:\([A-Za-z0-9]+\))?'
    r'|' + _CJK_NO_DE_CN + r'+\([A-Za-z0-9]+\))'
    r'(?![的之])'
)

_CLAUSE_BOUNDARY_RE_CN = re.compile(r'[；，、。]')

# F5a ref-prefix set (Q1: 该等/该些 excluded).
_REF_PREFIX_SET_CN = ('所述', '该', '前述')

_REF_POSSESSIVE_WITH_NUM_CN = re.compile(
    r'(?:所述|该|前述)'
    r'[\u4e00-\u7683\u7685-\u9fff]{2,}\([A-Za-z0-9]+\)'
    r'的'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)'
)
_REF_POSSESSIVE_NO_NUM_CN = re.compile(
    r'(?:所述|该|前述)'
    r'[\u4e00-\u7683\u7685-\u9fff]{2,4}'
    r'的'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)'
)

_YI_NOUN_PAREN_DE_PATTERN_CN = re.compile(
    r'一[\u4e00-\u7683\u7685-\u9fff]{2,}\([A-Za-z0-9]+\)'
    r'的'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,}(?:\([A-Za-z0-9]+\))?)'
)

_POSSESSIVE_VERB_DENYLIST_CN = {
    '包括', '包含', '具有', '是', '为', '大于', '小于', '等于',
    '设置', '形成', '连接', '连结',
}


def _extract_supplementary_intros_cn(text: str) -> list[tuple[str, str]]:
    """Extract bare-noun introductions from supplementary CN patterns.

    Returns (original_span, normalized_term) pairs. Eight pattern
    families (F5a/F5b/F6/F7a/F7b/F7c/F8/F9) with uniform
    ``clean_noun_phrase_cn`` cleanup. See tw_claims.py lines 1982–2099
    for per-family rationale.
    """
    results: list[tuple[str, str]] = []

    # F9: 透过Y连接/连结 — instrumental
    for m in _INSTRUMENTAL_PATTERN_CN.finditer(text):
        noun = m.group(1)
        original = m.group(0)
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        results.append((original, normalized))

    # F8: 相配合的Y — VP modifier
    for m in _VP_MODIFIER_PATTERN_CN.finditer(text):
        noun = m.group(1)
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        has_numeral = '(' in noun
        has_ordinal = normalized.startswith('第')
        if not (has_numeral or has_ordinal):
            continue
        cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
        if cjk_len < 3:
            continue
        results.append((m.group(0), normalized))

    # F7a: 形成于X的Y — locative
    for pos in (i for i, ch in enumerate(text) if text[i:i + 3] == '形成于'):
        clause_start = pos + 3
        boundary = _CLAUSE_BOUNDARY_RE_CN.search(text, clause_start)
        clause_end = boundary.start() if boundary else len(text)
        clause = text[clause_start:clause_end]
        last_noun = None
        last_original = None
        for dm in _DE_NOUN_RE_CN.finditer(clause):
            last_noun = dm.group(1)
            last_original = text[clause_start + dm.start():clause_start + dm.end()]
        if last_noun is None:
            continue
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', last_noun)
        cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
        if cjk_len < 3:
            continue
        if any(normalized.startswith(p) for p in _REF_PREFIX_SET_CN):
            continue
        results.append((last_original, normalized))

    # F7b: 一V的Y — participial
    for m in _PARTICIPIAL_YI_DE_PATTERN_CN.finditer(text):
        noun = m.group(1)
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        has_numeral = '(' in noun
        has_ordinal = normalized.startswith('第')
        cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
        if not (has_ordinal or has_numeral or cjk_len >= 3):
            continue
        results.append((m.group(0), normalized))

    # F7c: 的第Y — post-的 ordinal noun
    for m in _POST_DE_ORDINAL_PATTERN_CN.finditer(text):
        noun = m.group(1)
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        results.append((m.group(0), normalized))

    # F6: verb + Y — bare-after-verb
    for m in _BARE_AFTER_VERB_PATTERN_CN.finditer(text):
        noun = m.group(1)
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        results.append((m.group(0), normalized))

    # F5a: ref-prefix possessive (two variants)
    for pattern in (_REF_POSSESSIVE_WITH_NUM_CN, _REF_POSSESSIVE_NO_NUM_CN):
        for m in pattern.finditer(text):
            noun = m.group(1)
            normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
            cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
            if cjk_len < 2:
                continue
            if normalized.startswith(_REF_PREFIX_SET_CN):
                continue
            end_pos = m.end()
            follower = text[end_pos:end_pos + 2]
            if follower in _POSSESSIVE_VERB_DENYLIST_CN:
                continue
            results.append((m.group(0), normalized))

    # F5b: 一X(N)的Y — intro with paren-numeral possessive
    for m in _YI_NOUN_PAREN_DE_PATTERN_CN.finditer(text):
        noun = m.group(1)
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
        if cjk_len < 2:
            continue
        if normalized.startswith(_REF_PREFIX_SET_CN):
            continue
        end_pos = m.end()
        follower = text[end_pos:end_pos + 2]
        if follower in _POSSESSIVE_VERB_DENYLIST_CN:
            continue
        results.append((m.group(0), normalized))

    # Uniform trailing-verb cleanup
    cleaned: list[tuple[str, str]] = []
    for orig, norm in results:
        cleaned_norm = clean_noun_phrase_cn(norm)
        if cleaned_norm and len(cleaned_norm) >= 2:
            cleaned.append((orig, cleaned_norm))
    return cleaned


def extract_introductions_cn(
    claim: Claim,
    *,
    strict_qualifier_matching: bool = False,
) -> list[tuple[str, str]]:
    """Extract introductions from a CN claim as (original, normalized) pairs."""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for m in _INTRO_PATTERN_CN.finditer(claim.text):
        original = m.group(0)
        bare_noun = m.group(1)
        candidates = _postprocess_intro_capture_cn(bare_noun, m, claim.text)
        for candidate in candidates:
            normalized = normalize_candidate_intro_cn(
                candidate,
                strict_qualifier_matching=strict_qualifier_matching,
            )
            if not normalized:
                continue
            if normalized not in seen:
                seen.add(normalized)
                pairs.append((original, normalized))

    supplementary = _extract_supplementary_intros_cn(claim.text)
    for orig, norm in supplementary:
        if norm not in seen:
            seen.add(norm)
            pairs.append((orig, norm))

    return pairs


def full_ref_starts_with_plural_cn(text: str) -> bool:
    """True iff text begins with a plural quantifier marker."""
    return text.startswith(("复数", "多个", "数个", "复数个"))


_BARE_GENUS_NOUNS_CN: frozenset[str] = frozenset({
    "方法", "装置", "系统", "设备", "组件",
    "模块", "单元", "电路", "部件", "芯片",
})

_GENUS_PREAMBLE_RE_CN: re.Pattern[str] = re.compile(
    r"(?:(?:如|根据)权利要求[^，。\n]*?所述的[^，。\n]*?|一种[^，。\n]*?)"
    r"(?:方法|装置|系统|设备|组件|模块|单元|电路|部件|芯片)[，,\s]"
)


def _is_bare_genus_self_reference_cn(term: str, claim_text: str) -> bool:
    """Suppress bare-genus self-references in claim preambles (WQ5).

    When the claim's preamble declares the genus as its subject — either
    the dependent form ``(如|根据)权利要求N所述的<genus>`` or the independent
    form ``一种...<genus>，`` — a bare ``所述<genus>`` later in the body is
    a trivial self-reference, not a missing antecedent. Phase 8c close-out
    R1.
    """
    if term not in _BARE_GENUS_NOUNS_CN:
        return False
    return bool(_GENUS_PREAMBLE_RE_CN.search(claim_text))


def check_antecedent_basis_cn(
    doc: CnPatentDocument,
    *,
    strict_plural_reference_matching: bool = False,
    strict_qualifier_matching: bool = False,
) -> list[dict]:
    """CN antecedent-basis BFS walker (Phase 8c Stage 2).

    Mirrors the TW walker's resolution algorithm (tw_claims.py
    ``check_antecedent_basis``) with the Q1/Q3 divergences:

      * Q1: references using the TC-contamination prefixes 该等 / 该些
        are rejected with a ``category: "tw_contamination"`` finding
        and bypass normal resolution.
      * Q3: dedup key is the tuple
        ``(normalized_term, normalized_reference_form)`` from day 1
        (ADR-103). TW uses single-key dedup pending Phase 9 parity.

    Returns a list of dicts, 6-field ``{claim_id, term, reference_form,
    claim_text, suggested_match, cross_ref}`` for normal findings; the
    ``category`` key is added only on the Q1 path.
    """
    claims = doc.claims
    if not claims:
        return []

    issues: list[dict] = []

    for claim in claims:
        chain = get_ancestor_chain_cn(claim, claims)

        intros_by_term: dict[str, tuple[int, int]] = {}
        for depth, ancestor in enumerate(chain):
            for _, normalized in extract_introductions_cn(
                ancestor,
                strict_qualifier_matching=strict_qualifier_matching,
            ):
                intros_by_term.setdefault(normalized, (ancestor.id, depth))

        # Q1 tw_contamination rejection pre-pass. The TC-plural prefixes
        # 该等 / 该些 are not valid in CN drafting (CNIPA审查指南 uses 所述).
        # Their detection regex is local to this function so the only
        # module occurrence of these literals is this rejection apparatus.
        _tw_contamination_re = re.compile(
            r"(?P<prefix>该等|该些)" + f"(?P<noun>{_NOUN_CHARS_CN})"
        )
        for m in _tw_contamination_re.finditer(claim.text):
            prefix = m.group("prefix")
            raw_noun = m.group("noun")
            if not raw_noun:
                continue
            # Run the captured tail through the same cleanup pipeline as
            # the normal path (strip_reference_form_prefix →
            # strip_leading_qualifier → clean_noun_phrase →
            # strip_leading_quantifier), skipping resolution. The Q1
            # regex already split prefix (该等/该些) from noun, so we
            # normalize raw_noun directly.
            normalized_term = normalize_reference_term_cn(
                raw_noun,
                strict_qualifier_matching=strict_qualifier_matching,
            )
            finding: dict = {
                "claim_id": claim.id,
                "term": normalized_term or raw_noun,
                "reference_form": prefix,
                "claim_text": claim.text,
                "suggested_match": None,
                "cross_ref": None,
                "category": "tw_contamination",
            }
            if not normalized_term:
                finding["note"] = "cleanup_empty"
            issues.append(finding)

        # Q3 tuple dedup (ADR-103): the key is the pair
        # (normalized_term, normalized_reference_form). See the
        # module-header ADR-103 comment for the parity rationale.
        seen_terms: set[tuple[str, str]] = set()
        for m in _REF_PATTERN_CAPTURE_CN.finditer(claim.text):
            prefix = m.group("prefix")
            raw_noun = m.group("noun")
            if not raw_noun:
                continue

            full_ref = f"{prefix}{raw_noun}"
            normalized_term = normalize_reference_term_cn(
                full_ref,
                strict_qualifier_matching=strict_qualifier_matching,
            )
            if not normalized_term:
                continue

            normalized_reference_form = f"{prefix}{normalized_term}"
            dedup_key = (normalized_term, normalized_reference_form)
            if dedup_key in seen_terms:
                continue
            seen_terms.add(dedup_key)

            reference_form = normalized_reference_form

            resolved_intro: str | None = None
            if normalized_term in intros_by_term:
                resolved_intro = normalized_term
            elif not re.search(r"\([^)]+\)$", normalized_term):
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

            if resolved_intro is not None:
                if not strict_plural_reference_matching:
                    continue
                if not detect_plural_reference_cn(full_ref):
                    continue
                ancestor_id, _ = intros_by_term[resolved_intro]
                ancestor_claim = next(
                    (c for c in chain if c.id == ancestor_id), None
                )
                intro_was_plural = False
                if ancestor_claim is not None:
                    for original, normalized in extract_introductions_cn(
                        ancestor_claim,
                        strict_qualifier_matching=strict_qualifier_matching,
                    ):
                        if normalized != resolved_intro:
                            continue
                        if full_ref_starts_with_plural_cn(original):
                            intro_was_plural = True
                            break
                if intro_was_plural:
                    continue

            suggested_match: dict | None = None
            if resolved_intro is None:
                ref_tokens = tokenize_cn(normalized_term)
                best_score = 0.0
                best_depth: int | None = None
                for intro_term, (ancestor_id, depth) in intros_by_term.items():
                    if ordinal_guard(normalized_term, intro_term):
                        continue
                    score = jaccard(ref_tokens, tokenize_cn(intro_term))
                    if score < _DIDYOUMEAN_THRESHOLD_CN:
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

            if (
                suggested_match is not None
                and suggested_match["term"] == normalized_term
            ):
                suggested_match = None

            if _is_bare_genus_self_reference_cn(normalized_term, claim.text):
                continue

            issues.append(
                {
                    "claim_id": claim.id,
                    "term": normalized_term,
                    "reference_form": reference_form,
                    "claim_text": claim.text,
                    "suggested_match": suggested_match,
                    "cross_ref": None,
                }
            )

    issues.sort(key=lambda x: (x["claim_id"], x["term"], x["reference_form"]))
    return issues
