# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""CN claims analysis checks.

Twelve pure functions checking Chinese patent claim formatting
against CNIPA rules (专利法实施细则 and 审查指南).
"""

from __future__ import annotations

import re
from typing import Any

from patentlint.analysis.cjk_ordinal_guard import (
    normalize_arabic_ordinal_to_cjk,
    ordinal_guard,
)
from patentlint.analysis.cjk_tokenize import jaccard, tokenize_cn
from patentlint.analysis.utils import (
    _dx,
    compute_confidence_score,
    make_document_dedup_key,
)
from patentlint.analysis.connection_relationships import (
    _CN_CONNECTION_CONFIG,
    check_connection_relationships,
)
from patentlint.models import CheckItem, Claim, CnPatentDocument

# ADR-107 (Phase 8c Stage 2): CN antecedent walker adopts tuple dedup
# (normalized_term, normalized_reference_form) from day 1. TW uses single-key
# dedup pending Phase 9 parity migration. See CLAUDE.md Phase 8c locked
# decision Q3 and Phase 9 follow-up #2.

# Did-you-mean Jaccard threshold (ADR-094). Char-bigram Jaccard at 0.40
# is the calibration v2 sweet spot from the TW walker; inherited for CN.
_DIDYOUMEAN_THRESHOLD_CN = 0.40


def _dedupe_claim_ids(ids: list[int]) -> list[int]:
    """Drop duplicate claim IDs while preserving first-seen order.

    A malformed draft can print two distinct claim bodies under the same
    printed number (e.g., two "44."s in CN115952274B). The parser keeps
    both so ``check_claims_sequential`` can flag the duplication, but
    downstream emit sites should surface each claim ID at most once so
    the report does not render "claims: 44, 44".
    """
    return list(dict.fromkeys(ids))

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
            return [CheckItem(
                status="amend",
                message=f"Claim numbering is not sequential: expected {expected}, found {claim.id}.",
                message_key="check.cn.claims.sequential.amend",
                details_key="details.cn.claimsSequential",
                details_params={"expected": expected, "found": claim.id},
                reference="审查指南",
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
        message_key="check.cn.claims.sequential.pass",
        reference="审查指南",
    )]


# ── Check 10 ─────────────────────────────────────────────────────────────

# CN dependent-claim preamble connective.
# CNIPA-standard is 所述 (per 专利法实施细则 §25 + CNIPA drafting examples).
# JP-translation variants 所记载/所揭示/所描述 surface in CN patents translated
# from Japanese originals; parse them tolerantly rather than flag them.
# The trailing 的 is optional — CN drafters sometimes write 所述X (without 的)
# when X starts with a measure word or complex noun phrase.
_CN_DEP_CONNECTIVE = r"所(?:述|记载|揭示|描述)的?"

# The introducing verb is NOT constrained: CNIPA drafting commonly uses
# 根据/如/按照/依照/依/依据/基于 + 权利要求N + 所述的, or even the bare
# 权利要求N所述的 form. 审查指南 第二部分第二章 §3.3.1 uses 根据 in its
# canonical example; 如 is equally valid. Requiring a specific verb
# false-positives on nearly all real CN drafts. The actually-enforced
# structure is: 权利要求 + digit + ... + 所述.
_DEP_FORMAT_SINGLE = re.compile(r"权利要求\s*\d+[\s\S]*?" + _CN_DEP_CONNECTIVE)

# Multi-dep alternative-reference forms (per 专利法实施细则 §25 第3款 —
# multi-dep claims must use 择一方式 / alternative reference):
#   (a) `权利要求1或2所述的` — 或 alternative
#   (b) `权利要求1、2或3所述的` — 、 + 或 alternative
#   (c) `权利要求1至3中任一项所述的` — range + 中任一项
#   (d) `权利要求1至3任一项所述的` — range + 任一项 (no 中)
#   (e) `权利要求10至12中任意一项所述的` — range + 中任意一项
#   (f) `权利要求1-3任一项所述的` / `1~3` / `1‑5` (U+2010–U+2015 dashes)
# At least one alternative-reference marker (range-form OR or-form) is required.
_CN_RANGE_SEPARATOR = r"(?:~|至|到|[‐-―\-])"
_CN_ANY_ITEM_QUANTIFIER = r"任\s*(?:意\s*)?(?:一|何)?\s*项"
_DEP_FORMAT_MULTI = re.compile(
    r"权利要求\s*\d+"
    r"(?:"
    #   Range form: `N至M[中[的]任[意][一|何]项]`
    r"\s*" + _CN_RANGE_SEPARATOR + r"\s*(?:权利要求\s*)?\d+"
    r"(?:\s*(?:中(?:\s*的)?\s*)?" + _CN_ANY_ITEM_QUANTIFIER + r")?"
    r"|"
    #   Or/comma form: `或 N`, `、N`, possibly repeated
    r"(?:\s*(?:或|、)\s*(?:权利要求\s*)?\d+)+"
    r"(?:\s*(?:中(?:\s*的)?\s*)?" + _CN_ANY_ITEM_QUANTIFIER + r")?"
    r")"
    r"[\s\S]*?" + _CN_DEP_CONNECTIVE
)


def check_dependency_format(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check dependent claims use the 如权利要求N所述的 format."""
    dependents = [c for c in cn_doc.claims if not c.independent]
    if not dependents:
        return [CheckItem(
            status="pass",
            message="No dependent claims to check.",
            message_key="check.cn.claims.dependencyFormat.pass",
            reference="专利法实施细则 §25",
        )]

    bad_claim_ids: list[int] = []
    for claim in dependents:
        if claim.multiple_dependent:
            if not _DEP_FORMAT_MULTI.search(claim.text):
                bad_claim_ids.append(claim.id)
        else:
            if not _DEP_FORMAT_SINGLE.search(claim.text):
                bad_claim_ids.append(claim.id)

    if bad_claim_ids:
        bad_claim_ids = _dedupe_claim_ids(bad_claim_ids)
        claims_str = ", ".join(str(i) for i in bad_claim_ids)
        return [CheckItem(
            status="amend",
            message=f"{len(bad_claim_ids)} dependent claim(s) lack proper dependency format (claims: {claims_str}).",
            message_key="check.cn.claims.dependencyFormat.amend",
            details=f"{len(bad_claim_ids)} claims",
            details_key="details.cn.dependencyFormat",
            details_params={"count": len(bad_claim_ids), "claims": bad_claim_ids},
            reference="专利法实施细则 §25",
            diagnostics=_dx(
                flagged_count=len(bad_claim_ids),
                total_dependents=len(dependents),
                total_claims=len(cn_doc.claims),
                flagged_claim_id=bad_claim_ids[0] if bad_claim_ids else None,
                findings=[
                    {"claim_id": cid, "preamble": (next((c.text for c in cn_doc.claims if c.id == cid), "") or "")[:80]}
                    for cid in bad_claim_ids[:5]
                ],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="All dependent claims use proper dependency format.",
        message_key="check.cn.claims.dependencyFormat.pass",
        reference="专利法实施细则 §25",
    )]


# ── Check 11 ─────────────────────────────────────────────────────────────


def check_self_dependent(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check if any claim depends on itself."""
    bad = _dedupe_claim_ids([c.id for c in cn_doc.claims if c.id in c.dependencies])

    if bad:
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Self-dependent claims found: {claims_str}.",
            message_key="check.cn.claims.selfDependent.amend",
            details=claims_str,
            details_key="details.cn.selfDependent",
            details_params={"claims": bad},
            reference="专利法实施细则 §25",
            diagnostics=_dx(
                flagged_count=len(bad),
                total_claims=len(cn_doc.claims),
                flagged_claim_id=bad[0] if bad else None,
                findings=[
                    {"claim_id": cid, "preamble": (next((c.text for c in cn_doc.claims if c.id == cid), "") or "")[:80]}
                    for cid in bad[:5]
                ],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="No self-dependent claims.",
        message_key="check.cn.claims.selfDependent.pass",
        details_key="details.cn.pass.selfDependent",
        reference="专利法实施细则 §25",
    )]


# Strip the ``N. `` / ``N．`` claim-number prefix before checking preamble.
_CN_CLAIM_NUM_PREFIX = re.compile(r"^[\s　]*\d+\s*[.．。]\s*")


def check_independent_preamble(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Advisory: flag independent claims not opening with 「一种」.

    审查指南 第二部分第二章 §3.1.1 uses 一种X as the canonical preamble
    form in its examples, and CNIPA practitioner convention follows this.
    Note: 专利法实施细则 §24 (independent claim format) requires the
    preamble to state the 主题名称 (subject-matter name) but does NOT
    literally mandate 一种 — other preambles that still name the
    subject matter may satisfy the statute.
    Status is therefore VERIFY (advisory), not FIX.

    Dependent-claim opener set (根据/如/按照 etc.) is validated separately
    by ``check_dependency_format``.
    """
    bad: list[int] = []
    for claim in cn_doc.claims:
        if not claim.independent:
            continue
        body = _CN_CLAIM_NUM_PREFIX.sub("", claim.text).lstrip()
        if not body.startswith("一种"):
            bad.append(claim.id)

    if bad:
        bad_sorted = _dedupe_claim_ids(bad)
        claims_str = ", ".join(str(i) for i in bad_sorted)
        return [CheckItem(
            status="verify",
            message=f"Independent claim(s) not opening with 「一种」: {claims_str}.",
            message_key="check.cn.claims.independentPreamble.verify",
            details=claims_str,
            details_key="details.cn.independentPreamble",
            details_params={"count": len(bad_sorted), "claims": bad_sorted},
            reference="审查指南 第二部分第二章 §3.1.1 (canonical example form)",
            diagnostics=_dx(
                flagged_count=len(bad_sorted),
                total_claims=len(cn_doc.claims),
                flagged_claim_id=bad_sorted[0] if bad_sorted else None,
            ),
        )]
    return [CheckItem(
        status="pass",
        message="All independent claims open with 「一种」.",
        message_key="check.cn.claims.independentPreamble.pass",
        reference="审查指南 第二部分第二章 §3.1.1 (canonical example form)",
    )]


# ── Check 12 ─────────────────────────────────────────────────────────────


def check_forward_dependency(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check if any claim depends on a higher-numbered claim."""
    bad = _dedupe_claim_ids(
        [c.id for c in cn_doc.claims if any(d > c.id for d in c.dependencies)]
    )

    if bad:
        return [CheckItem(
            status="amend",
            message=f"Forward-referencing claims found: {', '.join(str(i) for i in bad)}.",
            message_key="check.cn.claims.forwardDependency.amend",
            details=", ".join(str(i) for i in bad),
            details_key="details.cn.forwardDependency",
            details_params={"claims": bad},
            reference="专利法实施细则 §25",
            diagnostics=_dx(
                flagged_count=len(bad),
                total_claims=len(cn_doc.claims),
                flagged_claim_id=bad[0] if bad else None,
                findings=[
                    {"claim_id": cid, "preamble": (next((c.text for c in cn_doc.claims if c.id == cid), "") or "")[:80]}
                    for cid in bad[:5]
                ],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="No forward-referencing dependencies.",
        message_key="check.cn.claims.forwardDependency.pass",
        details_key="details.cn.pass.forwardDependency",
        reference="专利法实施细则 §25",
    )]


# ── Check 13 ─────────────────────────────────────────────────────────────


def check_single_sentence(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Each claim must have exactly one 。 at the end."""
    bad_claim_ids: list[int] = []
    sample_last_cp: int | None = None
    for claim in cn_doc.claims:
        text = claim.text.strip()
        period_count = text.count("。")
        if period_count != 1 or not text.endswith("。"):
            bad_claim_ids.append(claim.id)
            if sample_last_cp is None and text:
                sample_last_cp = ord(text[-1])

    if bad_claim_ids:
        bad_claim_ids = _dedupe_claim_ids(bad_claim_ids)
        claims_str = ", ".join(str(i) for i in bad_claim_ids)
        return [CheckItem(
            status="amend",
            message=f"{len(bad_claim_ids)} claim(s) have invalid sentence structure (claims: {claims_str}).",
            message_key="check.cn.claims.singleSentence.amend",
            details=f"{len(bad_claim_ids)} claims",
            details_key="details.cn.singleSentence",
            details_params={"count": len(bad_claim_ids), "claims": bad_claim_ids},
            reference="审查指南 第二部分第二章",
            diagnostics=_dx(
                flagged_count=len(bad_claim_ids),
                total_claims=len(cn_doc.claims),
                sample_last_codepoint=sample_last_cp,
            ),
        )]

    return [CheckItem(
        status="pass",
        message="All claims are single sentences ending with 。.",
        message_key="check.cn.claims.singleSentence.pass",
        details_key="details.cn.pass.singleSentence",
        reference="审查指南 第二部分第二章",
    )]


# ── Check 14 ─────────────────────────────────────────────────────────────

# CJK char followed by optional space then 2-4 digits, not in parentheses.
# Exclude CJK unit tokens like 重量份, 重量百分比 etc. to avoid chemistry
# false positives (mirror of tw_claims._BARE_NUMERAL CJK unit exclusion).
_CJK_UNIT_TOKENS_CN = (
    r"重量百分比|重量份|重量比|"
    r"摩尔百分比|摩尔比|摩尔|"
    r"体积百分比|体积比|质量百分比|原子百分比|"
    r"毫克|公克|毫升|公升|微升|微米|纳米|公分|公釐|公尺|"
    r"克|升|倍率|倍|份|个|颗|片|"
    # R-refnum-1 (2026-04-30, cross-port from TW issue #25): Miller-index
    # suffixes for crystallography in semiconductor patents. CNIPA
    # drafters write `100面` / `110方向` identically to TIPO; same
    # FP risk applies. Cross-port is symmetric per ADR-095.
    r"结晶面|晶面|平面|方向|面"
)
_BARE_NUMERAL = re.compile(
    r"(?<!\()(?<=[\u4e00-\u9fff])\s?\d{2,4}(?!\))"
    r"(?!\s*(?:" + _CJK_UNIT_TOKENS_CN + r"))"
)


def _ref_numeral_finding_diag_cn(cid: int, claims: list) -> dict:
    """CN parallel of _ref_numeral_finding_diag_tw — adds context_after
    for self-diagnosing reports per R-refnum-1.
    """
    text = next((c.text for c in claims if c.id == cid), "") or ""
    m = _BARE_NUMERAL.search(text)
    if not m:
        return {"claim_id": cid, "first_match": None, "context_after": None}
    return {
        "claim_id": cid,
        "first_match": m.group(0),
        "context_after": text[m.end():m.end() + 8],
    }


def check_reference_numeral_parentheses(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Find reference numerals in claims not enclosed in parentheses."""
    bad_claim_ids: list[int] = []
    for claim in cn_doc.claims:
        if _BARE_NUMERAL.search(claim.text):
            bad_claim_ids.append(claim.id)

    if bad_claim_ids:
        bad_claim_ids = _dedupe_claim_ids(bad_claim_ids)
        claims_str = ", ".join(str(i) for i in bad_claim_ids)
        return [CheckItem(
            status="verify",
            message=f"{len(bad_claim_ids)} claim(s) have unparenthesized reference numerals (claims: {claims_str}).",
            message_key="check.cn.claims.refNumeralParens.verify",
            details=f"{len(bad_claim_ids)} claims",
            details_key="details.cn.refNumeralParens",
            details_params={"count": len(bad_claim_ids), "claims": bad_claim_ids},
            reference="审查指南",
            diagnostics=_dx(
                flagged_count=len(bad_claim_ids),
                total_claims=len(cn_doc.claims),
                flagged_claim_id=bad_claim_ids[0] if bad_claim_ids else None,
                # R-refnum-1 (2026-04-30): added context_after so future
                # reports of FPs like Miller-index `100面` arrive self-
                # diagnosing without needing the draft. Cross-port from TW.
                findings=[
                    _ref_numeral_finding_diag_cn(cid, cn_doc.claims)
                    for cid in bad_claim_ids[:5]
                ],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="All reference numerals in claims are parenthesized.",
        message_key="check.cn.claims.refNumeralParens.pass",
        reference="审查指南",
    )]


# ── Check 15 ─────────────────────────────────────────────────────────────

# Extract subject matter: text after the last 所述的 (or 的) before 。
_SUBJECT_RE = re.compile(r"所述的(.+?)(?:[，,]|$)")
_LEADING_QUANTIFIER = re.compile(r"^(?:一种|一个|该|所述|所述的)\s*")

# Dependent-claim preamble anchored at start (CN mirror of TW fix): prevents
# body-text 所述的 inside independent claims from hijacking extraction.
# Trailing connective accepts 所(述|记载|揭示|描述)[的] + bare 的 (older form
# 权利要求N的X). JP-translated CN patents keep 所记载 even though CNIPA-standard
# is 所述 — parse the dep preamble tolerantly so subject extraction succeeds.
_DEP_PREAMBLE_CONNECTIVE_CN = r"(?:所(?:述|记载|揭示|描述)的?|的)?"
_DEP_PREFIX_RE_CN = re.compile(
    r"^(?:如|根据|依)权利要求\s*\d+"
    r"(?:\s*(?:~|至|到)\s*\d+)?"
    r"(?:\s*(?:或|、)\s*\d+)*"
    r"(?:\s*中\s*任一?项)?"
    r"\s*" + _DEP_PREAMBLE_CONNECTIVE_CN
)
_INDEP_PREFIX_RE_CN = re.compile(r"^(?:一种|一个)\s*")
# Subject-end boundary: any clause/sentence terminator stops extraction so
# realistic claim preambles (with trailing 。 or ；) yield a clean subject.
_SUBJECT_END_RE_CN = re.compile(r"(?:[，,；。]|其特征在于|其改良在于|其中)")


def _extract_subject_with_path(claim_text: str) -> tuple[str, str]:
    """Extract subject matter + provenance tag (CN mirror of TW helper).

    Returns (subject_text, extraction_path) where path is one of:
      - ``"dep_prefix"``    — matched `_DEP_PREFIX_RE_CN`
      - ``"indep_prefix"``  — matched `_INDEP_PREFIX_RE_CN`
      - ``"subject_re"``    — legacy body-scan `所述的` match path
      - ``"fallthrough"``   — no recognized preamble, returned raw text

    Subject-consistency callers use the path to split genuine mismatches
    from parse-limit fall-throughs (see ADR-145).
    """
    text = re.sub(r"^\s*\d+\s*[.．]\s*", "", claim_text).strip()
    dep_m = _DEP_PREFIX_RE_CN.match(text)
    if dep_m:
        remainder = text[dep_m.end():]
        end_m = _SUBJECT_END_RE_CN.search(remainder)
        return (
            (remainder[:end_m.start()] if end_m else remainder).strip(),
            "dep_prefix",
        )
    indep_m = _INDEP_PREFIX_RE_CN.match(text)
    if indep_m:
        body = text[indep_m.end():]
        end_m = _SUBJECT_END_RE_CN.search(body)
        return (
            (body[:end_m.start()] if end_m else body).strip(),
            "indep_prefix",
        )
    end_m = _SUBJECT_END_RE_CN.search(text)
    if end_m:
        return text[:end_m.start()].strip(), "fallthrough"
    # Legacy 所述的 body scan for claims that don't match preamble shapes
    match = _SUBJECT_RE.search(claim_text)
    if match:
        return match.group(1).strip(), "subject_re"
    return text.strip(), "fallthrough"


def _extract_subject(claim_text: str) -> str:
    """Back-compat wrapper — returns just the subject text."""
    subject, _path = _extract_subject_with_path(claim_text)
    return subject


def _normalize_subject(subject: str) -> str:
    """Strip leading quantifiers for comparison."""
    return _LEADING_QUANTIFIER.sub("", subject).strip()


def check_subject_name_consistency(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Check dependent claim subject matter matches parent claim subject matter.

    Extract both subjects with the same ``_extract_subject`` helper so a
    descriptive independent-claim preamble like
    ``一种基于深度学习模型的数据生成方法`` does not spuriously diverge from
    a dependent's short-form ``如权利要求1所述的数据生成方法``. Consistency
    allows equality, or either side being a suffix of the other, since
    CN drafters commonly drop qualifier phrases (``基于...的``) when
    re-referencing the parent subject matter.
    """
    claims_by_id = {c.id: c for c in cn_doc.claims}
    dependents = [c for c in cn_doc.claims if not c.independent]

    if not dependents:
        return [CheckItem(
            status="pass",
            message="No dependent claims to check.",
            message_key="check.cn.claims.subjectConsistency.pass",
            reference="审查指南 第二部分第二章",
        )]

    mismatch_ids: list[int] = []
    unclear_ids: list[int] = []
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

        # Parse-limit category — preamble didn't match a recognized shape.
        # ADR-145: emit parseUnclear instead of verify, so bug reports can
        # distinguish walker gaps from drafter-level mismatches.
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

        if not dep_subject or not parent_subject:
            continue
        if dep_subject == parent_subject:
            continue
        if parent_subject.endswith(dep_subject) or dep_subject.endswith(parent_subject):
            continue
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
        mismatch_ids = _dedupe_claim_ids(mismatch_ids)
        claims_str = ", ".join(str(i) for i in mismatch_ids)
        results.append(CheckItem(
            status="verify",
            message=f"{len(mismatch_ids)} dependent claim(s) have inconsistent subject matter (claims: {claims_str}).",
            message_key="check.cn.claims.subjectConsistency.verify",
            details=f"{len(mismatch_ids)} claims",
            details_key="details.cn.subjectConsistency",
            details_params={"count": len(mismatch_ids), "claims": mismatch_ids},
            reference="审查指南 第二部分第二章",
            diagnostics=mismatch_fp,
        ))
    if unclear_ids:
        unclear_ids = _dedupe_claim_ids(unclear_ids)
        claims_str = ", ".join(str(i) for i in unclear_ids)
        results.append(CheckItem(
            status="verify",
            message=f"{len(unclear_ids)} dependent claim(s) with an unrecognized preamble — couldn't verify subject consistency (claims: {claims_str}).",
            message_key="check.cn.claims.subjectConsistencyParseUnclear",
            details=f"{len(unclear_ids)} claims",
            details_key="details.cn.subjectConsistencyParseUnclear",
            details_params={"count": len(unclear_ids), "claims": unclear_ids},
            reference="审查指南 第二部分第二章",
            diagnostics=unclear_fp,
        ))
    if results:
        return results

    return [CheckItem(
        status="pass",
        message="Dependent claim subject matter is consistent.",
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

    bad_claim_ids: list[int] = []
    for claim in independents:
        if not _TRANSITION_PHRASES.search(claim.text):
            bad_claim_ids.append(claim.id)

    if bad_claim_ids:
        bad_claim_ids = _dedupe_claim_ids(bad_claim_ids)
        claims_str = ", ".join(str(i) for i in bad_claim_ids)
        return [CheckItem(
            status="verify",
            message=f"{len(bad_claim_ids)} independent claim(s) lack a transition phrase (claims: {claims_str}).",
            message_key="check.cn.claims.transitionPhrase.verify",
            details=f"{len(bad_claim_ids)} claims",
            details_key="details.cn.transitionPhrase",
            details_params={"count": len(bad_claim_ids), "claims": bad_claim_ids},
            reference="审查指南",
            diagnostics=_dx(
                flagged_count=len(bad_claim_ids),
                total_independent=len(independents),
                total_claims=len(cn_doc.claims),
                flagged_claim_id=bad_claim_ids[0] if bad_claim_ids else None,
                findings=[
                    {"claim_id": cid, "preamble": (next((c.text for c in cn_doc.claims if c.id == cid), "") or "")[:120]}
                    for cid in bad_claim_ids[:5]
                ],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="All independent claims contain a transition phrase.",
        message_key="check.cn.claims.transitionPhrase.pass",
        details_key="details.cn.pass.transitionPhrase",
        reference="审查指南",
    )]


# ── Check 17 ─────────────────────────────────────────────────────────────

_TW_TERMS = re.compile(r"请求项|請求項")


def check_tw_terminology(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Scan claims for Taiwan-specific terminology."""
    hits: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()
    for claim in cn_doc.claims:
        for m in _TW_TERMS.finditer(claim.text):
            token = m.group(0)
            key = (claim.id, token)
            if key in seen:
                continue
            seen.add(key)
            hits.append((claim.id, token))

    if hits:
        return [CheckItem(
            status="amend",
            message="Taiwan-specific terminology found in claims.",
            message_key="check.cn.claims.twTerminology.amend",
            details_key="details.cn.twTerminology",
            details_params={
                "flagged_phrases": {
                    "items": [{"kind": "term", "token": token, "location": cid} for cid, token in hits]
                },
            },
            reference="",
            diagnostics=_dx(
                flagged_claim_id=hits[0][0],
                hit_count=len(hits),
                total_claims=len(cn_doc.claims),
                findings=[
                    {"claim_id": cid, "token": token}
                    for cid, token in hits[:5]
                ],
            ),
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
    bad_claim_ids: list[int] = []
    ref_hits: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()
    for claim in cn_doc.claims:
        for m in _SPEC_REF.finditer(claim.text):
            token = m.group(0)
            key = (claim.id, token)
            if key in seen:
                continue
            seen.add(key)
            ref_hits.append((claim.id, token))
            if claim.id not in bad_claim_ids:
                bad_claim_ids.append(claim.id)

    if bad_claim_ids:
        bad_claim_ids = _dedupe_claim_ids(bad_claim_ids)
        claims_str = ", ".join(str(i) for i in bad_claim_ids)
        return [CheckItem(
            status="amend",
            message=f"{len(bad_claim_ids)} claim(s) reference the specification or drawings (claims: {claims_str}).",
            message_key="check.cn.claims.specReference.amend",
            details=f"{len(bad_claim_ids)} claims",
            details_key="details.cn.claimsSpecReference",
            details_params={
                "count": len(bad_claim_ids),
                "claims": bad_claim_ids,
                "flagged_phrases": {
                    "items": [{"kind": "reference", "token": token, "location": cid} for cid, token in ref_hits]
                },
            },
            reference="审查指南 第二部分第二章",
            diagnostics=_dx(
                flagged_count=len(bad_claim_ids),
                total_claims=len(cn_doc.claims),
                hit_count=len(ref_hits),
            ),
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
        bad = _dedupe_claim_ids(bad)
        claims_str = ", ".join(str(i) for i in bad)
        return [CheckItem(
            status="amend",
            message=f"Multiple-dependent claim(s) depend on other multiple-dependent claims: {claims_str}.",
            message_key="check.cn.claims.multiMultiDep.amend",
            details=claims_str,
            details_key="details.cn.multiMultiDep",
            details_params={"claims": bad},
            reference="专利法实施细则 §25",
            diagnostics=_dx(
                flagged_count=len(bad),
                total_multi_dep=len(multi_dep_ids),
                total_claims=len(cn_doc.claims),
                flagged_claim_id=bad[0] if bad else None,
                findings=[
                    {"claim_id": cid, "preamble": (next((c.text for c in cn_doc.claims if c.id == cid), "") or "")[:80]}
                    for cid in bad[:5]
                ],
            ),
        )]

    return [CheckItem(
        status="pass",
        message="No chained multiple dependencies.",
        message_key="check.cn.claims.multiMultiDep.pass",
        details_key="details.cn.pass.multiMultiDep",
        reference="专利法实施细则 §25",
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
                        diagnostics=_dx(
                            total_claims=len(claims),
                            total_independent=len(indep_positions),
                            stranded_claim_id=c.id,
                            expected_after_independent_id=current_indep_id,
                            actual_position=j,
                            stranded_preamble=(c.text or "")[:80],
                        ),
                    )]

    return [CheckItem(
        status="pass",
        message="Dependent claim ordering is correct.",
        message_key="check.cn.claims.dependentOrdering.pass",
        reference="审查指南 第二部分第二章",
    )]


# ── Check 21 (连接关系) ──────────────────────────────────────────────────


def check_connection_relationships_cn(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Flag independent apparatus claims listing components without a
    connection verb (CNIPA 审查指南 §3.2.1 + 专利法 §26.4).

    Thin wrapper over the shared CN/TW helper. Method, CRM, MPF, and
    composition claims are carved out per ``_CN_CONNECTION_CONFIG``.
    """
    return check_connection_relationships(cn_doc.claims, _CN_CONNECTION_CONFIG)


# ── Check 22 (omnibus / 如说明书所述) ─────────────────────────────────────

# Mirrors US ``_OMNIBUS_LANG``; CN-practitioner phrasings that reference
# the description or drawings instead of reciting features. 审查指南
# 第二部分第二章 §3.3 — claims must recite technical features, not
# reference the specification.
_OMNIBUS_LANG_CN = re.compile(
    r"如说明书(?:及附图)?(?:所述|所描述|所记载)"
    r"|如说明书和附图(?:所述|所描述|所示|所描述的)"
    r"|如(?:附图|图)\s*\d*(?:所示|所述|所描述)"
    r"|基本上如说明书(?:所述|所描述)"
    r"|如(?:前述|前文)(?:所述|所描述)说明书"
)


def detect_omnibus_claims_cn(cn_doc: CnPatentDocument) -> list[int]:
    """Return IDs of CN claims that reference 说明书/附图 without reciting features.

    Mirrors :func:`patentlint.analysis.claims.check_special_claim_formats`
    omnibus branch, with CN practitioner patterns. Length threshold (<40
    CJK chars) guards against false positives on long detailed claims that
    incidentally mention 说明书.
    """
    out: list[int] = []
    for claim in cn_doc.claims:
        text = claim.text or ""
        cjk_count = sum(1 for ch in text if "一" <= ch <= "鿿")
        if cjk_count < 40 and _OMNIBUS_LANG_CN.search(text):
            out.append(claim.id)
    return out


def check_omnibus_claims(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Emit CheckItem for CN omnibus claims (FIX) — 审查指南 §3.3."""
    ids = detect_omnibus_claims_cn(cn_doc)
    if ids:
        claims_str = ", ".join(str(i) for i in ids)
        return [CheckItem(
            status="amend",
            message=f"Omnibus claim(s) reference the specification or drawings instead of reciting features: {claims_str}.",
            message_key="check.cn.claims.omnibus.amend",
            details=claims_str,
            details_key="details.cn.omnibusClaims",
            details_params={"claims": ids},
            reference="审查指南 第二部分第二章 §3.3",
            diagnostics=_dx(
                flagged_count=len(ids),
                total_claims=len(cn_doc.claims),
                flagged_claim_id=ids[0] if ids else None,
                findings=[
                    {"claim_id": cid, "preamble": (next((c.text for c in cn_doc.claims if c.id == cid), "") or "")[:80]}
                    for cid in ids[:5]
                ],
            ),
        )]
    return [CheckItem(
        status="pass",
        message="No omnibus claims found.",
        message_key="check.cn.claims.omnibus.pass",
        reference="审查指南 第二部分第二章 §3.3",
    )]


# ── Check 23 (Markush group open transition) ─────────────────────────────

# CNIPA 审查指南 第二部分第十章 §9.3 — a Markush claim must use the closed
# transition 组成的 (e.g. 选自由...所组成的群组 / 选自由X、Y、Z组成的群组).
# Open-ended variants (包括/具有/含有) are suspect.
_MARKUSH_OPEN_CN = re.compile(
    r"选自由[^，。；]{0,80}?(包括|具有|含有)"
)
_MARKUSH_CLOSED_CN = re.compile(r"选自由[^，。；]{0,80}?组成")


def detect_markush_open_transition_cn(cn_doc: CnPatentDocument) -> list[tuple[int, str]]:
    """Return (claim_id, open_transition) pairs for Markush claims using 包括/具有/含有."""
    out: list[tuple[int, str]] = []
    for claim in cn_doc.claims:
        text = claim.text or ""
        m = _MARKUSH_OPEN_CN.search(text)
        if m and not _MARKUSH_CLOSED_CN.search(text):
            out.append((claim.id, m.group(1)))
    return out


def check_markush_open_transition(cn_doc: CnPatentDocument) -> list[CheckItem]:
    """Emit CheckItem for CN Markush claims using open transition (FIX).

    Improper Markush is a substantive rejection per 审查指南 第二部分第十章
    §9.3 (Markush requires 选自由...组成的 closed group), not a formal
    correction — open transition triggers an examiner rejection on the
    merits.
    """
    pairs = detect_markush_open_transition_cn(cn_doc)
    if pairs:
        ids = [cid for cid, _ in pairs]
        transitions = sorted({t for _, t in pairs})
        claims_str = ", ".join(str(i) for i in ids)
        return [CheckItem(
            status="amend",
            message=f"Markush claim(s) use open-ended transition instead of 组成的: {claims_str}.",
            message_key="check.cn.claims.markushOpenTransition.amend",
            details=claims_str,
            details_key="details.cn.markushOpenTransition",
            details_params={"claims": ids, "transitions": transitions},
            reference="审查指南 第二部分第十章 §9.3",
            diagnostics=_dx(
                flagged_count=len(ids),
                total_claims=len(cn_doc.claims),
                flagged_claim_id=ids[0] if ids else None,
                transitions=transitions,
                findings=[
                    {
                        "claim_id": cid,
                        "open_transition": tw_word,
                        "preamble": (next((c.text for c in cn_doc.claims if c.id == cid), "") or "")[:120],
                    }
                    for cid, tw_word in pairs[:5]
                ],
            ),
        )]
    return [CheckItem(
        status="pass",
        message="Markush groups use closed transition 组成的.",
        message_key="check.cn.claims.markushOpenTransition.pass",
        reference="审查指南 第二部分第十章 §9.3",
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
#       day 1 (ADR-107). TW uses single-key; parity migration is a
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
# R30 mechanism #10 (2026-05-03): extended definitional prefixes.
# Common CN patent drafting introduces a term via 定义为/称为/记为/表示为
# already; corpus shows additional shapes: 此处称为, 此处定义为, 简称为
# (abbreviation marker), 命名为 (named as), 标记为 (marked as), 视为
# (deemed/treated as), 等同于 (equivalent to). Anti-pattern guard: the
# `一?` allows optional 一 prefix (drafter writes either form).
_DEFINITIONAL_PREFIX_CN = r"(?:定义为|称为|记为|表示为|此处称为|此处定义为|简称为|命名为|标记为|视为|等同于|又称为|又称|亦即)一?"

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
        # Phase 8c close-out R-CO-2 WQ1a — multi-char trailing verbs
        # Walker false positives where capture trails into a verb phrase.
        # Length-desc strip order: 联合训练 / 恢复运行 fire before bare 训练 / 运行.
        "联合训练", "恢复运行",
        "存储有",
        "进行", "接收", "发送", "输入", "来自", "需要",
        "运行", "执行", "确定", "提供", "匹配", "表征",
        "生成", "获取", "获得",
        "向",
        # Phase 8c R9 — additional trailing verbs from re-sampling analysis
        "针对", "支持", "调用", "采用", "作为",
        "对",
        # Phase 8c R22 — single-char preposition residues from BYD-style
        # paren-numeral terms (从动凸轮(320)由, 凹部(322)沿, 辅助层沿).
        "由", "沿",
        # Phase 8c R23 — multi-char trailing verbs from over_capture pool
        # (77-active stratification). Compound-noun risk audited per token
        # against full corpus V+CJK matches; all dominated by particle/
        # determiner suffixes (所/时/的/方) that don't form noun compounds.
        "录入", "推荐", "导入", "提取", "转动", "重复",
        "体外培养", "胰蛋白酶消化", "铰接", "选自", "代替", "交联",
        "检查", "查询", "保存", "固定", "回复", "消化",
        "恢复",
        # Phase 8c R24 — single-char trailing residues from over_capture
        # pool (16 active labels post-R23). Compound-noun risk audited:
        # all noun compounds (作用/不良/相应/均匀/得到) appear at PREFIX
        # position in corpus; suffix-position usage is uniformly verb/
        # particle. All 16 emit-terms ending in these chars match the
        # 16 targets exactly (zero collateral).
        "作", "不", "相", "均", "得",
        # === Phase 8c R7-port (2026-04-30) — TW Round 7 cross-port ===
        # 较 (comparative verb), 厚膜化 (process verb-suffix). CN parity
        # for TW additions; CNIPA semiconductor drafters use these
        # identically. 0 active CN-label collisions; 比较/较量 etc.
        # protected via the existing residual ≥ 1 floor (2-char compounds
        # with 较 at position [-1] strip to 1 char, blocked).
        "较", "厚膜化",
        # === R29 (2026-05-03) — round-1 corpus over-capture extensions ===
        # Conservative extension only. Excludes verbs that double as common
        # noun endings (处理, 配置, 形成, 驱动, 存储, 传输, 连接, 选择,
        # 标识, 识别) — those silenced legacy `处理器配置` protect:true
        # label on tw_contamination_simple synthetic. Kept additions are
        # clearly-verb multi-char phrases without noun-suffix ambiguity.
        "围绕", "代表", "连同", "表示", "移动",
        "检测", "测量", "收集", "输送",
        "释放", "操控", "扫描",
        "覆盖", "分离", "比较", "判断", "决定", "分析",
        "包括以下", "执行以下", "进行以下",
        "执行以下操作", "执行以下操",
        # === R32 (2026-05-04) — passive trailing residue ===
        # 被: passive marker (`<noun>被<verb>`). Compound nouns ending in
        #   `被` are vanishingly rare in CN patent claims (棉被/被服 are
        #   household items, not patent terms). Empirically: walker emits
        #   `单元被`/`子单元被` from CN114357105B c12/c15 spec-support FPs
        #   where bare `单元`/`子单元` is the canonical intro.
        #
        # NOT included: 通信/通讯. Initially considered, but corpus audit
        # showed compound NOUNS like `侧链路中继通信` / `无线通信` use
        # 通信 as HEAD noun at suffix position; symmetric strip would
        # bridge legit-flagged refs to bare `侧链路中继` and silence 7
        # protect:false legit-drafting-error labels in CN115398975B c1-8
        # (LLM ensemble Phase 2c verified). Reserved for a context-aware
        # mechanism (verb-mode vs noun-mode) outside R32 scope.
        '被',
        # === R32 (2026-05-04) — verb-suffix trailing residues (CN parity) ===
        # Cluster-mined from round-1 CN corpus.
        '延伸',  # 51 walker_fp / 0 legit. (Risk audited per TW.)
        '指示',  # 42 walker_fp / 0 legit. Verb form ("indicate").
                # NOTE: 指示牌 / 指示灯 noun compounds at PREFIX position.
        # === R30 (2026-05-03) — sample-derived adverbial / adjectival trims
        # 进一步: adverbial ("further"), fragment of 进一步包括/进一步具有.
        #   Multi-char so safe against noun compounds (第一步/一步走 unaffected).
        # 相关联: adjectival ("related/associated"), fragment of <noun>相关联的.
        #   Existing 相关 + 有关 catch 2-char form; 3-char form needs explicit.
        "进一步", "相关联",
    ),
    key=len,
    reverse=True,
))

# Noun-like single-char trailing suffixes with residual ≥ 3 guard.
# R22 adds 由/沿; R24 adds 作/不/相/均/得 with relaxed-residual subset
# participation below.
_NOUNLIKE_SINGLE_CHAR_SUFFIXES_CN: frozenset[str] = frozenset(
    {"所", "位", "中", "后", "用", "上", "内", "撷取", "对", "由", "沿",
     "作", "不", "相", "均", "得",
     # === R7-port (2026-04-30) — TW R7 parity ===
     # 使 (causative particle / verb fragment): residual ≥ 3 protects
     # 大使/天使/特使/使用 (all 2-char compounds, residual 1 < 3).
     "使"}
)

# Relaxed-guard subset (residual ≥ 2 instead of ≥ 3).
# Stage 4 R1 D4a — relaxed residual ≥ 2 guard for 2-char-stem residue strip.
# R22 adds 由/沿; R24 adds 作/不/相/均/得 (mirrors trailing-verb registration).
_NOUNLIKE_RELAXED_SUFFIXES_CN: frozenset[str] = frozenset(
    {"上", "内", "后", "中", "用", "对", "由", "沿",
     "作", "不", "相", "均", "得"}
)

# Phase 8c R22 — `中` very-relaxed (residual ≥ 1) for 2-char locative
# phrases like 组中. The post-strip 1-char residual is then filtered by
# the `len(normalized_term) == 1` emit guard. Empirically scoped: only
# 2 corpus terms (组中 ×2 in CN115952274B) hit this path.
_NOUNLIKE_VERY_RELAXED_SUFFIXES_CN: frozenset[str] = frozenset({"中"})

# Phase 8c R10 — char-exclusion residue map.
# Keys: residue chars left at end of terms because _NOUN_CHARS_CN excludes
# the following char (于→基, 能→功, 应→响).  Values: minimum residual
# length after stripping the residue char.
_CHAR_EXCLUSION_RESIDUE_CN: dict[str, int] = {
    '\u57fa': 3,  # 基 (from 基于) — guard ≥3 protects 培养基
    '\u54cd': 2,  # 响 (from 响应)
    '\u529f': 2,  # 功 (from 功能)
    '\u8f93': 2,  # 输 (from 输出 where 出 is in trailing denylist)
}

# Chemistry chars that legitimately precede 基 (functional-group suffix).
# When the char before 基 is in this set, 基 is a noun, not a verb residue.
_CHEMISTRY_BEFORE_JI_CN: frozenset[str] = frozenset(
    '性酸碱甲乙丙丁养氨羟羧磷烷烯烃硫氧氮氯氢苯胺酮醛酯醇酚'
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
        # Cross-jurisdiction parity with TW R6 (ce91d2b): 各 distributive
        # quantifier ("each"). CNIPA drafters use 前述各X / 所述各X / 该各X
        # for "each X" references when a parent claim introduces an indexed
        # family. Reference-side normalization must strip 各 so the bare
        # head noun matches the upstream intro. Symmetric strip on the
        # intro side is harmless because 各X intros are unattested at
        # claim-body level (the indexed family is introduced as bare noun,
        # then references add the distributive 各 prefix). Audit confirmed
        # 0 active CN labels collide; 3 resolved entries have mid-string
        # 各 (compound noun usage like 各样本数据) which startswith() leaves
        # untouched.
        "各",
        # === R30 (2026-05-03) — extended plural-quantifier bridging ===
        # Phase 2c Refinement C: when a parent claim introduces `多个X` /
        # `若干X` and a dependent references `所述X` (singular), bridging via
        # symmetric strip is the right move per CN drafting practice. The
        # original set covered 复数/多个/数个; this round adds the rest of
        # the common CNIPA quantifier vocabulary. All multi-char so safe
        # against compound nouns (无 single-char additions).
        "若干个", "若干",
        "一些", "某些",
        "多种", "多类", "多组", "多对",
        "至少两个", "至少两", "两个", "两种",
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
        # Phase 8c R8 — 进行 (carry out) appears mid-term in overcaptures
        # like 第一设备进行第一信号 → should split to 第一设备.
        "进行",
        # Phase 8c R12 — additional interior verb overcaptures
        "需要", "发出", "符合",
        # Phase 8c R23 — interior verb cuts from over_capture pool
        # (像素界定层限定有X, 处理单元周期性地或非周期, 滑块(230)可移动地设,
        # 初始地理预训练模型按照预, 处理器核运行客户端进程, 目标预训练模型采用预训练,
        # 实线边表征不同节点). Compound-noun risk audited per token.
        "限定有", "周期性地", "可移动地", "按照", "运行", "采用", "表征",
        # === Phase 8c R7-port (2026-04-30) — TW Round 7 cross-port ===
        # Process verbs that split mid-string captures cleanly in
        # semiconductor / mechanical claims. CN parity for the TW
        # additions in R7; same drafter conventions across jurisdictions.
        # Compound-noun risk: 夹持器/覆盖层/露出口 absent from CN corpus
        # per grep (verbs only, no compound-noun collision).
        "夹持", "覆盖", "露出",
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

    # R31 (2026-05-03) tight noun-suffix guard for compound nouns where
    # the verb is part of a real noun compound (verb + noun-suffix). Mirror
    # of TW R31. Restricted by:
    #   1. verb in high-collision whitelist (decision/sense/identify class)
    #   2. char immediately after verb is a noun-suffix
    #   3. TOTAL TEXT LENGTH ≤ 8 chars (typical compound noun max)
    _R31_NOUN_COMPOUND_VERBS_CN = {
        '决定', '感测', '侦测', '监测', '辨识', '识别', '解析',
        '处理', '控制', '驱动', '检出', '判定', '计算', '生成',
        '输出', '输入', '存储', '存取', '读取', '写入',
    }
    earliest_idx: int | None = None
    for verb in _INTERIOR_VERB_BOUNDARIES_CN:
        idx = search_text.find(verb)
        if idx >= 0 and (idx + search_offset) >= min_absolute_idx:
            absolute_idx = idx + search_offset
            # R31 noun-compound guard (length-bounded): skip cut if verb is
            # in whitelist, char after is noun-suffix, total len ≤ 8.
            if (verb in _R31_NOUN_COMPOUND_VERBS_CN
                    and len(text) <= 8):
                next_char_pos = absolute_idx + len(verb)
                if (next_char_pos < len(text)
                        and text[next_char_pos] in _F10_SINGLE_CHAR_SUFFIXES_CN):
                    continue  # 对象决定+部 etc. (text length ≤ 8)
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
                if verb in _NOUNLIKE_VERY_RELAXED_SUFFIXES_CN:
                    min_residual = 1
                elif verb in _NOUNLIKE_RELAXED_SUFFIXES_CN:
                    min_residual = 2
                else:
                    min_residual = 3
                if (len(current) - len(verb)) < min_residual:
                    continue
            current = current[: -len(verb)]
            stripped = True
            break
        if not stripped:
            break

    # Phase 8c R10 — char-exclusion residue repair.
    # _NOUN_CHARS_CN excludes 于/能/应 etc., leaving half-compound residues
    # at the end of captured terms (e.g., 第一设备基 from 基于, 第一功 from
    # 功能, 第N响 from 响应).  Strip the residue char when it is NOT part
    # of a legitimate chemistry suffix (培养基, 酸解离性基, 碱基 …).
    if len(current) >= 3 and current[-1] in _CHAR_EXCLUSION_RESIDUE_CN:
        guard = _CHAR_EXCLUSION_RESIDUE_CN[current[-1]]
        if len(current) - 1 >= guard:
            if current[-1] != '\u57fa' or current[-2] not in _CHEMISTRY_BEFORE_JI_CN:
                current = current[:-1]

    return current


# R32 (2026-05-04): regex-based at-least-N strip + 其-possessive strip
# (CN parity with TW R32). Existing _LEADING_QUANTIFIER_DENYLIST_CN
# covers 至少一/至少一个/至少两/至少两个 only; 至少三个X / 至少100个X
# stranded. 其X (its X) possessive captured by F-anchor patterns when
# the canonical intro is bare X (introduced as feature of prior subject).
_AT_LEAST_N_PREFIX_RE_CN: re.Pattern[str] = re.compile(
    r'^至少[一二三四五六七八九十百0-9]+个'
)
_POSSESSIVE_其_PREFIX_RE_CN: re.Pattern[str] = re.compile(
    r'^其(?=[一-鿿]{2,})'
)


# R32 (2026-05-04): leading conjunction-residue strip. CN drafters use
# `和/或X` (and/or X) constructions in lists. Walker captures `/或X` as
# leading residue when the conjunction-split mechanism fails on the
# slash. Empirical: `/或第二功能模块` from CN115485995B c12 spec-support FP
# where canonical intro is `第二功能模块`.
_LEADING_CONJ_RESIDUE_RE_CN: re.Pattern[str] = re.compile(
    r'^(?:/或|/和|和/或|或/|/)'
)


def strip_leading_quantifier_cn(text: str) -> str:
    """Strip one matching leading quantifier (ADR-095 Rule 2).

    R32 (2026-05-04): regex-based 至少N个 strip applied first; 其-possessive
    strip applied last with ≥2 CJK lookahead so 其余 (2 chars) is protected.
    """
    if not text:
        return text
    # R32: leading conjunction residue (`/或`, `和/或`) strip
    m = _LEADING_CONJ_RESIDUE_RE_CN.match(text)
    if m and len(text) - m.end() >= 2:
        text = text[m.end():]
    m = _AT_LEAST_N_PREFIX_RE_CN.match(text)
    if m and len(text) - m.end() >= 2:
        text = text[m.end():]
    for q in _LEADING_QUANTIFIER_DENYLIST_CN:
        if text.startswith(q) and len(text) > len(q):
            text = text[len(q):]
            break
    m = _POSSESSIVE_其_PREFIX_RE_CN.match(text)
    if m:
        text = text[m.end():]
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
    """Normalize a flagged reference term for antecedent matching.

    R7 (2026-04-30): + strip_leading_verb_cn for `所述形成p型源极／漏极`
    style references that carry a leading verb prefix (符号见 ADR-095
    addendum / TW R7 commit).

    R33 (2026-05-04): + normalize_arabic_ordinal_to_cjk at the head so
    JP-translated drafts using `第1` / `第2` collapse with canonical
    `第一` / `第二` intros for matching purposes.
    """
    t = normalize_arabic_ordinal_to_cjk(text)
    t = strip_reference_form_prefix_cn(t)
    t = strip_leading_qualifier_cn(t, strict_qualifier_matching=strict_qualifier_matching)
    t = clean_noun_phrase_cn(t)
    t = strip_leading_quantifier_cn(t)
    t = strip_leading_verb_cn(t)
    # R31 (2026-05-03): re-run reference-prefix strip after verb strip,
    # because the new 有 prefix entry can expose a hidden 所述/该/前述
    # underneath (e.g., 有所述高亮度区域 → 所述高亮度区域 after 有 strip
    # → 高亮度区域 after re-prefix-strip). Without this, spec_support
    # mid-phrase recovery test failed.
    t = strip_reference_form_prefix_cn(t)
    t = strip_leading_qualifier_cn(t, strict_qualifier_matching=strict_qualifier_matching)
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
    t = normalize_arabic_ordinal_to_cjk(text)
    t = strip_leading_qualifier_cn(t, strict_qualifier_matching=strict_qualifier_matching)
    t = clean_noun_phrase_cn(t)
    t = strip_leading_quantifier_cn(t)
    t = strip_reference_form_prefix_cn(t)
    t = strip_leading_verb_cn(t)
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


# ── Supplementary bare-noun intro patterns (F5/F6/F7b/F7c/F7d/F11/F12/F13) ─
#
# F7a/F8/F9 removed 2026-04-16: the R14 investigation confirmed zero matches
# across the 10-fixture corpus. Their shapes (形成于X的Y, 相配合的Y, 透过Y连接)
# are TW-specific drafting patterns; CN tends toward 位于/设于 (now covered
# by F13) and 包括/包含 (covered by F11). If future fixtures surface any of
# these shapes, re-add with empirical grounding.

# CJK char class excluding 的 (U+7684); jurisdiction-invariant.
_CJK_NO_DE_CN = r'[\u4e00-\u7683\u7685-\u9fff]'
# F6-specific: also excludes 之 (U+4E4B) to prevent captures extending into
# temporal markers like 之后/之前. Removes the need for (?![的之]) lookahead
# which caused backtracking truncation before 的.
_CJK_NO_DE_ZHI_CN = r'[\u4e00-\u4e4a\u4e4c-\u7683\u7685-\u9fff]'

_PARTICIPIAL_YI_DE_PATTERN_CN = re.compile(
    r'一[\u4e00-\u9fff]+?的(' + _CJK_NO_DE_CN + r'{2,}(?:\([A-Za-z0-9]+\))?)'
)

_POST_DE_ORDINAL_PATTERN_CN = re.compile(
    r'的(第[一二三四五六七八九十\d]+' + _CJK_NO_DE_CN + r'+(?:\([A-Za-z0-9]+\))?)'
)

# Phase 8c R14c.2 — F6 bare-noun relax.
# Adds a third capture arm: bare NP (≥3 CJK chars, no ordinal, no paren).
# Gated by:
#   - negative lookahead against _F12_ADJ_REJECTS_CN (rejects predicate-
#     adjective / verb-phrase heads like 经/可/具有/能够/用于/基于)
#   - negative lookahead against 第/所述/该/前述 (arm1 or ref-prefix)
#   - per-CJK-char negative lookahead against F6 verbs, so arm3's greedy
#     CJK{3,20} stops at the next F6-verb start rather than consuming
#     across `进行处理得到第N信号` and blocking arm1 at 得到第N信号.
# See docs/8c/r14c2-f6-bare-noun.md.
_F6_VERB_ALT_CN = (
    r'具有|包含|包括|含有|设有'
    r'|设置|配置|安装|装设'
    r'|形成|构成'
    r'|提供|连接|连结'
    r'|获取|获得|得到|生成|产生|发出'
    r'|发送|接收|输出|输入|传送|存储|确定|涉及'
    r'|进行|调用|运行|调整|建立|构建|制得|根据|存在|使用'
)

_BARE_AFTER_VERB_PATTERN_CN = re.compile(
    r'(?:' + _F6_VERB_ALT_CN + r')'
    r'('
    r'第[一二三四五六七八九十\d]+' + _CJK_NO_DE_ZHI_CN + r'+(?:\([A-Za-z0-9]+\))?'
    r'|' + _CJK_NO_DE_ZHI_CN + r'+\([A-Za-z0-9]+\)'
    r'|'
    r'(?!第|所述|该|前述)'
    + r'(?:(?!(?:' + _F6_VERB_ALT_CN + r'))' + _CJK_NO_DE_ZHI_CN + r'){3,20}'
    r')'
)

# F11: colon-anchored list-after-包括/包含/含有 (WQ8 / R3).
# R31 (2026-05-03): F11 anchor verb set extended to cover broader Pattern B
# trigger vocabulary observed in round-1 corpus. CNIPA drafters use 具有
# /具备/设有/设置/包括以下/还包括/进一步包括/还具有 as Pattern B intro
# anchors, not just 包括/包含/含有. Each addition gated separately against
# protect:true labels.
_F11_COLON_LIST_ANCHOR_CN: re.Pattern[str] = re.compile(
    r'(?:包括以下|还包括|还包含|进一步包括|进一步包含|包括|包含|含有|具有|具备|设有)[：:]\s*([^。]+)'
)
# R29 (2026-05-03): regex no longer excludes `；` so the capture spans the
# whole list (bounded by `。`). Caller in _extract_supplementary_intros_cn
# splits the captured text on `；` and processes each segment as its own
# F11 list-element source. Pattern B claims like `<system>包括: A; B; 以及 C`
# previously dropped B and C because the capture stopped at first `；`.
_F11_LIST_SPLIT_CN: re.Pattern[str] = re.compile(r'[、，,和与及]')

# Phase 8c R14e — F11 no-colon extension. Matches no-colon enum lists
# `(?:包括|包含|含有)(Y(?:、Y)+)` where ≥2 `、`-separated CJK elements
# follow the verb directly. Mutually exclusive with the colon anchor
# because the character after the verb must be CJK (not `：:`), and
# requires the enum-list shape so single-noun `包括Y` doesn't fire
# (that case belongs to F6 / elsewhere).
_F11_NO_COLON_LIST_ANCHOR_CN: re.Pattern[str] = re.compile(
    # R31 (2026-05-03): mirror of F11_COLON anchor verb extension.
    r'(?:包括以下|还包括|还包含|进一步包括|进一步包含|包括|包含|含有|具有|具备|设有)'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,}(?:、[\u4e00-\u7683\u7685-\u9fff]{2,})+)'
)

# Phase 8c R14f — conjunction-split pass. Splits captured intros on
# 和/与/及/以及 with ≥2 CJK chars each side, registering each element as
# its own intro so downstream `所述X` / `所述Y` references can resolve
# when the drafting captured the intro as `X和Y`. Applied as a final
# pass over _extract_supplementary_intros_cn results after the uniform
# trailing-verb cleanup.
_CONJ_SPLIT_RE_CN: re.Pattern[str] = re.compile(r'(.+?)(?:以及|和|与|及)(.+)')

# F13: locative-verb + bare noun (+ optional locative suffix). Phase 8c R14a.
# Registers Y from `X应用于Y侧` / `X位于Y` as an intro, stripping a trailing
# locative suffix (侧/端/方/处/面/内/外/上/下/中) when present. The locative
# strip is required because walker resolution is reference.startswith(intro);
# a reference to `第一设备` cannot resolve to a longer intro `第一设备侧`.
_F13_LOCATIVE_VERB_PATTERN_CN: re.Pattern[str] = re.compile(
    r'(?:应用于|作用于|位于|置于|设于|布置于|设置于|固定于)'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,12}(?:\([A-Za-z0-9]+\))?)'
)
_F13_LOCATIVE_SUFFIXES_CN: tuple[str, ...] = (
    '侧', '端', '方', '处', '面', '内', '外', '上', '下', '中',
)

# F14: V+有 noun-of-existence intro (Phase 9 #61).
# Registers Y from `X形成有Y` / `X安装有Y` / `X存储有Y` as an intro. Gated on
# a narrow verb set with empirically-clean captures — broader verbs (设置,
# 包含) add compound-noun FPs that the ADJ_REJECTS filter does not cover.
# Reuses _F12_ADJ_REJECTS_CN (rejects 可/由/能 etc.) + _REF_PREFIX_SET_CN +
# _BARE_ORDINAL_RE_CN + leading-conjunction reject (与/和/或).
_F14_V_YOU_PATTERN_CN: re.Pattern[str] = re.compile(
    r'(?:形成|安装|存储)有'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,12}(?:\([A-Za-z0-9]+\))?)'
)
_F14_LEADING_CONJ_CN: frozenset[str] = frozenset({'与', '和', '或'})

# F12: copula + 基于/来自 intro family. Phase 8c R14d.
# Three tiers to balance coverage vs. predicate-adjective false positives:
#  - Tier A (unconditional): 转变为|变为|转为|划分为|分为 — always register RHS
#    as intro. Risk is minimal — these verbs are only used for noun transitions.
#  - Tier B (noun-gated): 基于|来自 — register RHS if ≥2 CJK and doesn't start
#    with an adjectival/verb-phrase prefix (_F12_ADJ_REJECTS_CN).
#  - Tier C (two-branch 为|是): (1) ordinal-prefix or paren-numeral RHS
#    (unconditional); (2) bare-noun RHS ≥4 CJK with the same ADJ reject filter.
#    Splits because `A为可光照交联` (adjectival predicate) and `A是经过...`
#    (verb phrase) must be rejected; ordinal-prefix RHS is safe regardless.
_F12_TIER_A_RE_CN: re.Pattern[str] = re.compile(
    r'(?:转变为|变为|转为|划分为|分为)'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,12}(?:\([A-Za-z0-9]+\))?)'
)
_F12_TIER_B_RE_CN: re.Pattern[str] = re.compile(
    r'(?:基于|来自)'
    r'([\u4e00-\u7683\u7685-\u9fff]{2,12}(?:\([A-Za-z0-9]+\))?)'
)
_F12_TIER_C_ORDINAL_RE_CN: re.Pattern[str] = re.compile(
    r'(?:为|是)'
    r'(第[一二三四五六七八九十\d]+[\u4e00-\u7683\u7685-\u9fff]{1,10}'
    r'(?:\([A-Za-z0-9]+\))?'
    r'|[\u4e00-\u7683\u7685-\u9fff]{2,10}\([A-Za-z0-9]+\))'
)
_F12_TIER_C_BARE_RE_CN: re.Pattern[str] = re.compile(
    r'(?:为|是)'
    r'([\u4e00-\u7683\u7685-\u9fff]{4,12}(?:\([A-Za-z0-9]+\))?)'
)
_F12_ADJ_REJECTS_CN: tuple[str, ...] = (
    '可', '具有', '具', '经过', '由', '属于', '用于', '来自',
    '能够', '能', '会',
    '进行', '获得', '获取', '接收', '存储', '输出', '输入',
    '基于', '根据',
    # === Phase 8c R7-port (2026-04-30) — TW R7 parity ===
    # Copula / preposition / verb-prefix rejects for F6 bare-NP arm 3
    # and F12 Tier B emit. CN equivalents of TW's 係/是/為/較/對/在/將/
    # 藉/蝕. Mirror set with TW _F12_ADJ_REJECTS_TW so semiconductor /
    # process-method drafts surface clean noun heads on CN side.
    '系', '是', '为',
    '较', '对', '在',
    '将', '借', '蚀',
)

# F7d: participial `<tail>的Y` intro family. Phase 8c R14b.
# Stative-participle tails that introduce a new noun Y after 的. Intentionally
# narrow allowlist — DE_POSSESSIVE is heterogeneous and a broad `V的Y` regex
# would over-fire. Post-capture cleanup via clean_noun_phrase_cn handles
# trailing-verb overcaptures (e.g., 训练目标进行训练 → 训练目标 via interior-verb
# truncation at 进行 from R8).
_F7D_PARTICIPIAL_TAILS_CN: tuple[str, ...] = (
    '所对应', '按照预设', '相对应', '接收到',
    '预设', '所需', '相关', '对应', '匹配',
    '得到', '制得', '执行', '制造', '相连',
    '生成', '连接', '形成', '组成',
    # === R30 (2026-05-03) — extended participial tails from corpus ===
    # Round-1 corpus walker_fps include patterns like
    # `<X>覆盖的Y`, `<X>构成的Y`, `<X>设置的Y`, `<X>包含的Y` that the
    # original F7d allowlist doesn't catch. Adding them is safe because:
    # (a) each is clearly a participial verb (not a noun), (b) the trailing
    # 的 ensures Y is an attribute of X — registering Y as intro is correct
    # under §112(b) when X is in the chain.
    '覆盖', '构成', '设置', '配置', '安装',
    '提供', '获取', '获得', '产生',
    '所述包括', '所述包含', '所述具有',
    '附加', '增加', '减少', '改变', '修改',
    '包括', '包含', '具有',
)
_F7D_PATTERN_CN: re.Pattern[str] = re.compile(
    r'(?:' + '|'.join(re.escape(t) for t in _F7D_PARTICIPIAL_TAILS_CN) + r')'
    r'的([\u4e00-\u7683\u7685-\u9fff]{2,12}(?:\([A-Za-z0-9]+\))?)'
)
# Reuses _F12_ADJ_REJECTS_CN.

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


# ── R7-port (2026-04-30) — CN architectural buildout for F14/F16/F17/F19/F20 ──
# Mirror of TW R7's bare-modifier intro infrastructure. CN drafters use the
# same structural patterns (locative left-side, verb-X-之/的-Y, instrumental
# clauses) as TIPO drafters; the architectural divergence between CN and
# TW walkers prior to R7 meant CN had no equivalent of these mechanisms.
# This block adds them in advance — without waiting for a CN-side report —
# so CNIPA semiconductor / process-method drafts get the same protection.

# Component-suffix tail set for bare-noun intro emit gates. Mirrors TW
# _F10_COMPONENT_SUFFIXES with CN-specific items (域 region, 极 electrode).
# Single-char only — multi-char composites contribute their tail char which
# is already covered.
_F10_COMPONENT_SUFFIXES_CN: tuple[str, ...] = (
    '部', '件', '体', '器', '阀', '板', '模', '组', '块', '片',
    '环', '壳', '膜', '座', '盘', '筒', '轴', '杆', '轮', '带',
    '管', '架', '框', '壁', '面', '层', '材', '口', '道', '头',
    '侧', '孔', '缝', '边', '顶', '底', '角', '心', '核', '机',
    '柜', '室', '槽', '线', '路', '池', '枢', '盖', '套', '罩',
    '网', '柱', '锥', '球',
    # R7 (2026-04-30) — semiconductor + electronic claim element suffixes:
    # 域 (region: n型区域, p型区域, 主动区域); 极 (electrode pole: 栅极,
    # 源极, 漏极, 集极, 射极)
    '域', '极',
)

# Single-char component-suffix set for walk-back logic. F10's narrow
# endswith gate uses _F10_COMPONENT_SUFFIXES_CN; walk-back uses this
# wider set which includes 法 (method-claim head — `制造方法`).
_F10_SINGLE_CHAR_SUFFIXES_CN: frozenset[str] = frozenset(
    _F10_COMPONENT_SUFFIXES_CN
) | {
    # Walk-back-only: 法 lets `之制造方法` register as `制造方法` (then
    # strip_leading_verb_cn produces `方法`). F10's narrow gate excludes
    # 法 to avoid 想法/做法/算法 misfire on `一种的方法`-style synthetic.
    '法',
}

# Walk-back's discarded-suffix gate — only allow walk-back when the
# discarded portion starts with one of these verb-tail-head characters
# AND has length ≥ 2. Mirrors TW _F14_WALKBACK_VERB_HEADS_TW. CN
# zh-Hans equivalents: 制 (制成, 所制), 经 (经由 — also covers traditional
# 經 in mixed-script).
_F14_WALKBACK_VERB_HEADS_CN: tuple[str, ...] = (
    '所', '露', '形', '构', '组', '制', '经',
    # R7 extension (2026-04-30): 获 covers `X获得Y` / `X获取Y` walk-back
    # in CN process-method drafts. Mirror TW addition; 获利 is rare in
    # claim text, 获得/获取 dominant as verbs.
    '获',
)

# Mixed-script noun class for CN F14/F16/F17/F19/F20. Admits ASCII
# letters/digits + ／ (paired-element separator). Excludes 之 (U+4E4B)
# and 的 (U+7684) so captures don't span possessive markers.
_F14_NOUN_CLASS_CN = r'[A-Za-z0-9／一-乊乌-皃皅-鿿]'

# ADJ/verb heads that must not start a bare-modifier noun capture.
# Mirrors TW _F10_NOUN_REJECTS plus CN-specific copula / preposition /
# verb-prefix rejects.
_F10_NOUN_REJECTS_CN: tuple[str, ...] = (
    '可', '具有', '具', '经过', '由', '属于', '用于', '来自',
    '能够', '能', '会', '进行', '获得', '获取', '接收', '存储',
    '输出', '输入', '基于', '根据',
    '单一', '唯一',
    # R7 — copula / preposition / verb-prefix rejects (zh-Hans equivalents
    # of TW's 系/是/为/较/对/在/将/借/蚀)
    '系', '是', '为',
    '较', '对', '在',
    '将', '借', '蚀',
)

# Leading-verb prefix strip (`形成X`/`制造X` → `X`). Symmetric on intro
# and reference sides per ADR-095. Residual ≥ 2 protects 形成器/形成物
# (3 chars, residual 1 < 2) while admitting 制造方法 (4 chars, residual 2).
# R31 (2026-05-03): added 有 prefix. F-family captures of `设置有X` style
# Pattern B intros leave `有X` after 设置 strip; the leading 有 should be
# stripped to surface bare X. Residual ≥ 2 protects compound nouns
# starting with 有 (有限/有机/有效) — those are 2-char with residual 0/1
# after strip, so still protected.
_LEADING_VERB_PREFIXES_CN: tuple[str, ...] = tuple(sorted(
    (
        '形成', '制造', '有',
        # R32 (2026-05-04): connective-verb prefixes — TW parity.
        # Empirical: `即根据各数字内容` / `使得各数字内容关联` shape leaks
        # into spec-support via shared extract_introductions_cn helper.
        # Multi-char longest-first.
        '即根据', '即基于', '即依据', '即依照',
        '根据', '基于', '依据', '依照',
        '为了', '借以', '借由', '通过',
        '使得', '使其', '从而', '进而', '并且',
        '用以', '用于',
    ),
    key=len,
    reverse=True,
))
_LEADING_VERB_RESIDUAL_FLOOR_CN: int = 2


def strip_leading_verb_cn(text: str) -> str:
    """R7 (2026-04-30): strip leading verb prefix (形成/制造) when followed
    by a sufficient noun residual. Used in normalize_*_cn pipelines so
    `所述形成p型源极／漏极` references resolve against bare-noun
    `p型源极／漏极` intros.
    """
    if not text:
        return text
    for prefix in _LEADING_VERB_PREFIXES_CN:
        if (
            text.startswith(prefix)
            and len(text) - len(prefix) >= _LEADING_VERB_RESIDUAL_FLOOR_CN
        ):
            return text[len(prefix):]
    return text


def _trim_capture_to_clean_noun_cn(text: str) -> str | None:
    """R7 (2026-04-30): walk back from end of `text` to the last component-
    suffix character and truncate; return ``None`` if hygiene gates fail.
    Mirror of _trim_capture_to_clean_noun_tw — see that function for full
    contract documentation.
    """
    if not text or len(text) < 2:
        return None
    if text[-1] in _F10_SINGLE_CHAR_SUFFIXES_CN:
        truncated = text
    else:
        clean_end = None
        for i in range(min(len(text), 12), 0, -1):
            if text[i - 1] in _F10_SINGLE_CHAR_SUFFIXES_CN:
                clean_end = i
                break
        if clean_end is None:
            return None
        discarded = text[clean_end:]
        if len(discarded) < 2 or not discarded.startswith(
            _F14_WALKBACK_VERB_HEADS_CN
        ):
            return None
        truncated = text[:clean_end]
    if len(truncated) < 2:
        return None
    for prefix in _REFERENCE_FORM_PREFIXES_CN:
        if prefix in truncated:
            return None
    if truncated.startswith(_F10_NOUN_REJECTS_CN):
        return None
    return truncated


# F14 — bare-modifier `之NOUN` intro (formal-register parallel to F10's
# `的NOUN`). Less common in modern CN claims but appears in formal-register
# / JP-translated CN drafts. Mixed-script noun class for semiconductor.
_F14_BARE_ZHI_NOUN_RE_CN = re.compile(
    r'之'
    r'(?P<noun>' + _F14_NOUN_CLASS_CN + r'{2,12}'
    r'(?:\([A-Za-z0-9]+\))?)'
    r'(?!' + _F14_NOUN_CLASS_CN + r')'
)

# F16 — locative left-side intro `(?:于|在)X[之的]Y`. Captures left-side X
# (the new claim element introduced via locative phrase). CN uses both
# 之 (formal) and 的 (modern) for the possessive marker.
_F16_LOC_LEFT_INTRO_RE_CN = re.compile(
    r'(?:于|在)'
    r'(?P<noun>' + _F14_NOUN_CLASS_CN + r'{2,8}'
    r'(?:\([A-Za-z0-9]+\))?)'
    r'[之的]'
)

# F17 — locative-internal `在X之间` / `在X之间` intro (zh-Hans uses 间).
_F17_LOC_INTERNAL_INTRO_RE_CN = re.compile(
    r'在'
    r'(?P<noun>' + _F14_NOUN_CLASS_CN + r'{2,8}'
    r'(?:\([A-Za-z0-9]+\))?)'
    r'之间'
)

# F19 — `verb + X + [之的] + Y` left-side intro. F6 rejects this shape
# via its `(?![的之])` trailing lookahead; F19 explicitly catches it.
_F19_VERB_NP_ZHI_RE_CN = re.compile(
    r'(?:夹持|包含|包括|具有|含有|具备|设有|设置|配置|安装|装设|形成|构成|连接|连结|提供|构建)'
    r'(?P<noun>' + _F14_NOUN_CLASS_CN + r'{2,8}'
    r'(?:\([A-Za-z0-9]+\))?)'
    r'[之的]'
)

# F20 — `(以|借由|透过|经由|将) X (verb)` instrumental/object intro.
# `以` excluded when followed by `及` (conjunction `以及`).
# R41 (2026-05-04): added `将` (instrumental object marker, very
# common in CN claims for `将<noun><verb>` constructions like
# `将第一激发光输出`/`将信号发送`/`将数据传输`). Extended trailing-
# verb list with output/send/transmit/etc. to cover the most common
# 将-shape cases. Phase A on post-R36 corpus showed CN `发光` cluster
# 48 wfp / 0 legit (top: `第二激发光` 14, `第一激发光` 13) — parent
# claim 1 introduces 第一激发光 via `将第一激发光输出` shape that
# F20 didn't recognize.
_F20_PREP_NP_VERB_RE_CN = re.compile(
    r'(?:以(?!及)|借由|透过|经由|将)'
    r'(?P<noun>' + _F14_NOUN_CLASS_CN + r'{2,8}'
    r'(?:\([A-Za-z0-9]+\))?)'
    r'(?:夹持|覆盖|包含|包括|具有|含有|具备|设有|设置|配置|形成|构成|连接|连结|提供|分隔|划分|实施|分为|构建|测量|蚀刻|除去|装设|安装|输出|输入|发送|接收|传输|传送|生成|获取|获得|确定|存储|读取|写入|执行|处理|计算)'
)


def _extract_supplementary_intros_cn(text: str) -> list[tuple[str, str]]:
    """Extract bare-noun introductions from supplementary CN patterns.

    Returns (original_span, normalized_term) pairs. Active families:
    F5a/F5b, F6, F7b/F7c/F7d, F11 (colon + no-colon), F12, F13. Uniform
    ``clean_noun_phrase_cn`` cleanup. See tw_claims.py lines 1982–2099
    for per-family rationale. F7a/F8/F9 removed after zero-coverage
    R14 investigation confirmed CN corpus never exercises them.
    """
    results: list[tuple[str, str]] = []

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
        # R14c.2: bare-NP arm (no ordinal, no paren) is gated by
        # _F12_ADJ_REJECTS_CN startswith to suppress predicate-adjective
        # and verb-phrase heads like 可/经过/具有/能够/用于/基于/根据.
        if (not noun.startswith('第')
                and '(' not in noun
                and noun.startswith(_F12_ADJ_REJECTS_CN)):
            continue
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        results.append((m.group(0), normalized))
        # Also split conjunctions (和/与/及/、) into individual intros
        parts = _F11_LIST_SPLIT_CN.split(normalized)
        if len(parts) > 1:
            for part in parts:
                part = part.strip()
                if part:
                    results.append((m.group(0), part))

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

    # F11: list-after-包括 — colon-anchored preamble lists register each
    # element as a bare-noun intro. WQ8 / Phase 8c close-out R3.
    # R14e extends with a no-colon sibling pattern gated on ≥2 `、`-
    # separated elements.
    for anchor_re in (_F11_COLON_LIST_ANCHOR_CN, _F11_NO_COLON_LIST_ANCHOR_CN):
        for m in anchor_re.finditer(text):
            # R29 (2026-05-03): iterate ；-segments instead of truncating
            # at first; strip leading 以及/及 from each segment.
            full_list = m.group(1).split('。')[0]
            for segment in full_list.split('；'):
                segment = segment.strip()
                if not segment:
                    continue
                segment = re.sub(r'^(?:以及|及)\s*', '', segment)
                if not segment:
                    continue
                for element in _F11_LIST_SPLIT_CN.split(segment):
                    element = element.strip()
                    if not element:
                        continue
                    normalized = re.sub(r'\([A-Za-z0-9]+\)', '', element)
                    cjk_len = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff')
                    if cjk_len < 2:
                        continue
                    if normalized.startswith(_REF_PREFIX_SET_CN):
                        continue
                    results.append((element, normalized))
                    # R30 mechanism #4 (2026-05-03): sub-noun extraction from
                    # `<verb>X\u7684Y` shape inside the captured element. Pattern B
                    # often introduces multiple terms via possessive constructs:
                    # `\u5904\u7406\u672b\u7aef\u6267\u884c\u5668\u7684\u6240\u6709\u4efb\u52a1` should register both `\u672b\u7aef\u6267\u884c\u5668`
                    # and `\u6240\u6709\u4efb\u52a1`. Find the FIRST \u7684 (avoid deep nesting),
                    # split into head/tail, register each if valid noun phrase.
                    de_idx = normalized.find('\u7684')  # \u7684
                    if 0 < de_idx < len(normalized) - 1:
                        head = normalized[:de_idx]
                        tail = normalized[de_idx + 1:]
                        for sub in (head, tail):
                            sub_cjk = sum(1 for c in sub if '\u4e00' <= c <= '\u9fff')
                            if sub_cjk < 2:
                                continue
                            if sub.startswith(_REF_PREFIX_SET_CN):
                                continue
                            if sub.startswith(_F12_ADJ_REJECTS_CN):
                                continue
                            # Strip leading verb prefix (creation-verb subset)
                            # to unwrap `<verb><noun>` head into bare noun.
                            stripped = sub
                            for verb in ('\u63d0\u4f9b', '\u914d\u7f6e', '\u8bbe\u7f6e', '\u5f62\u6210', '\u6784\u6210',
                                          '\u6784\u5efa', '\u83b7\u53d6', '\u83b7\u5f97', '\u5f97\u5230', '\u751f\u6210',
                                          '\u4ea7\u751f', '\u8fde\u63a5', '\u8fde\u7ed3', '\u5b89\u88c5', '\u88c5\u8bbe',
                                          '\u5904\u7406'):
                                if stripped.startswith(verb) and len(stripped) > len(verb) + 1:
                                    rest = stripped[len(verb):]
                                    rest_cjk = sum(1 for c in rest if '\u4e00' <= c <= '\u9fff')
                                    if rest_cjk >= 2:
                                        stripped = rest
                                        break
                            if stripped != sub:
                                results.append((element, stripped))
                            results.append((element, sub))

    # F13: locative-verb + bare noun (+ optional locative suffix). R14a.
    for m in _F13_LOCATIVE_VERB_PATTERN_CN.finditer(text):
        raw = m.group(1)
        if raw.startswith(_REF_PREFIX_SET_CN):
            continue
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', raw)
        if (
            normalized
            and normalized[-1] in _F13_LOCATIVE_SUFFIXES_CN
            and len(normalized) >= 3
        ):
            normalized = normalized[:-1]
        if len(normalized) < 2:
            continue
        if normalized.startswith(_REF_PREFIX_SET_CN):
            continue
        results.append((m.group(0), normalized))

    # F14: V+有 noun-of-existence intro. Phase 9 #61.
    for m in _F14_V_YOU_PATTERN_CN.finditer(text):
        raw = m.group(1)
        if raw.startswith(_REF_PREFIX_SET_CN):
            continue
        if raw.startswith(_F12_ADJ_REJECTS_CN):
            continue
        if raw and raw[0] in _F14_LEADING_CONJ_CN:
            continue
        if _BARE_ORDINAL_RE_CN.match(raw):
            continue
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', raw)
        if len(normalized) < 2:
            continue
        results.append((m.group(0), normalized))

    # F12: copula + 基于/来自 intro family. R14d.
    for m in _F12_TIER_A_RE_CN.finditer(text):
        raw = m.group(1)
        if raw.startswith(_REF_PREFIX_SET_CN):
            continue
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', raw)
        if len(normalized) < 2:
            continue
        results.append((m.group(0), normalized))

    for m in _F12_TIER_B_RE_CN.finditer(text):
        raw = m.group(1)
        if raw.startswith(_REF_PREFIX_SET_CN):
            continue
        if raw.startswith(_F12_ADJ_REJECTS_CN):
            continue
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', raw)
        if len(normalized) < 2:
            continue
        results.append((m.group(0), normalized))

    for m in _F12_TIER_C_ORDINAL_RE_CN.finditer(text):
        raw = m.group(1)
        if raw.startswith(_REF_PREFIX_SET_CN):
            continue
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', raw)
        if len(normalized) < 2:
            continue
        results.append((m.group(0), normalized))

    for m in _F12_TIER_C_BARE_RE_CN.finditer(text):
        raw = m.group(1)
        if raw.startswith(_REF_PREFIX_SET_CN):
            continue
        if raw.startswith(_F12_ADJ_REJECTS_CN):
            continue
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', raw)
        if len(normalized) < 4:
            continue
        results.append((m.group(0), normalized))

    # F7d: participial <tail>的Y. R14b.
    for m in _F7D_PATTERN_CN.finditer(text):
        raw = m.group(1)
        if raw.startswith(_REF_PREFIX_SET_CN):
            continue
        if raw.startswith(_F12_ADJ_REJECTS_CN):
            continue
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', raw)
        if len(normalized) < 2:
            continue
        results.append((m.group(0), normalized))

    # === Phase 8c R7-port (2026-04-30) — TW R7 architectural buildout ===
    # F14 (V之Y), F16 (locative left-side), F17 (locative-internal),
    # F19 (verb-X-之/的), F20 (instrumental). Mirror of TW R7 mechanisms.
    # All use _trim_capture_to_clean_noun_cn for hygiene.

    # F14: bare-modifier `之NOUN` intro (formal-register parallel to F10).
    for m in _F14_BARE_ZHI_NOUN_RE_CN.finditer(text):
        noun = m.group('noun')
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        trimmed = _trim_capture_to_clean_noun_cn(normalized)
        if trimmed is None:
            continue
        results.append((m.group(0), trimmed))

    # F16: locative left-side intro `(于|在)X[之的]`.
    for m in _F16_LOC_LEFT_INTRO_RE_CN.finditer(text):
        noun = m.group('noun')
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        trimmed = _trim_capture_to_clean_noun_cn(normalized)
        if trimmed is None:
            continue
        results.append((m.group(0), trimmed))

    # F17: locative-internal `在X之间`.
    for m in _F17_LOC_INTERNAL_INTRO_RE_CN.finditer(text):
        noun = m.group('noun')
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        trimmed = _trim_capture_to_clean_noun_cn(normalized)
        if trimmed is None:
            continue
        results.append((m.group(0), trimmed))

    # F19: `verb + X + [之的] + Y` left-side intro.
    for m in _F19_VERB_NP_ZHI_RE_CN.finditer(text):
        noun = m.group('noun')
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        trimmed = _trim_capture_to_clean_noun_cn(normalized)
        if trimmed is None:
            continue
        results.append((m.group(0), trimmed))

    # F20: `(以|借由|透过|经由) X (verb)` instrumental intro.
    for m in _F20_PREP_NP_VERB_RE_CN.finditer(text):
        noun = m.group('noun')
        normalized = re.sub(r'\([A-Za-z0-9]+\)', '', noun)
        trimmed = _trim_capture_to_clean_noun_cn(normalized)
        if trimmed is None:
            continue
        results.append((m.group(0), trimmed))

    # Uniform trailing-verb cleanup
    cleaned: list[tuple[str, str]] = []
    for orig, norm in results:
        cleaned_norm = clean_noun_phrase_cn(norm)
        if not cleaned_norm or len(cleaned_norm) < 2:
            continue
        if cleaned_norm.startswith('第') and len(cleaned_norm) < 4:
            continue
        cleaned.append((orig, cleaned_norm))

    # R14f conjunction-split: for each cleaned intro containing 和/与/及/以及
    # with ≥2 CJK chars on each side, register each element as its own intro.
    seen_norms = {norm for _, norm in cleaned}
    extras: list[tuple[str, str]] = []
    for _, norm in cleaned:
        m = _CONJ_SPLIT_RE_CN.match(norm)
        if not m:
            continue
        for piece in (m.group(1), m.group(2)):
            piece_clean = clean_noun_phrase_cn(piece)
            if not piece_clean or len(piece_clean) < 2:
                continue
            cjk = sum(1 for c in piece_clean if '\u4e00' <= c <= '\u9fff')
            if cjk < 2:
                continue
            if piece_clean.startswith(_REF_PREFIX_SET_CN):
                continue
            if piece_clean in seen_norms:
                continue
            seen_norms.add(piece_clean)
            extras.append((piece_clean, piece_clean))

    # R31 (2026-05-03): generic 的-substring sub-noun extraction across ALL
    # captured intros. R30's F11 sub-noun was F11-only; round-1 mining
    # showed F12/F13/F14 captures also benefit (e.g., F13 locative-verb
    # intros like `位於連接器之間的耦合介面` should register both 連接器
    # and 耦合介面). Apply post-pass over `cleaned` (which contains all
    # F-family results after trim). Single-的 split only.
    # Anti-pattern: skip if both halves < 2 CJK chars OR start with reject prefix.
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
                if sub.startswith(_REF_PREFIX_SET_CN):
                    continue
                if sub.startswith(_F12_ADJ_REJECTS_CN):
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
                if sub.startswith(_REF_PREFIX_SET_CN):
                    continue
                if sub in seen_norms:
                    continue
                seen_norms.add(sub)
                cleaned_subs2.append((orig, sub))
    cleaned.extend(cleaned_subs2)

    # R30 mechanism #11 (2026-05-03): step-label colon intros for method claims.
    # Pattern: `；以及<step-name>:<step-content>` or `；<step-name>:<content>`
    # where the step-name (multi-char CJK before colon) is the new claim element.
    # Common in CN method claims: `；以及印刷步骤：在所述陶瓷块...`. Anti-pattern:
    # the noun must NOT start with reference-prefix or 第N (those are existing
    # references / ordinals, not new step labels).
    _STEP_LABEL_RE_R30 = re.compile(
        r'[；;]\s*(?:以及|及)?\s*([\u4e00-\u9fff]{2,12})\s*[：:]'
    )
    for sl_m in _STEP_LABEL_RE_R30.finditer(text):
        noun = sl_m.group(1)
        if not noun or len(noun) < 2:
            continue
        if noun.startswith(_REF_PREFIX_SET_CN):
            continue
        if noun.startswith('第'):
            continue
        if noun.startswith(_F12_ADJ_REJECTS_CN):
            continue
        if noun in seen_norms:
            continue
        seen_norms.add(noun)
        extras.append((sl_m.group(0), noun))

    # R30 mechanism #7 (2026-05-03): F6c Latin/short-CJK term floor.
    # F6 arms 1-3 require CJK-only nouns. Walker_fps on Latin acronyms
    # (UE, DCI, LHT, CU-CP) and Latin-CJK mixed terms (PWM信号, DCI格式,
    # RAM控制器) need an explicit arm. Pattern: <F6 verb>(<Latin-noun>)
    # where Latin-noun is uppercase Latin chars optionally followed by CJK
    # suffix. Anti-pattern: must be at a clear boundary (followed by
    # punctuation, conjunction, or end-of-clause) to avoid mid-word matches.
    _F6C_VERB_ALT = (
        r'具有|包含|包括|含有|设有|设置|配置|安装|装设|形成|构成|提供|连接|连结'
        r'|获取|获得|得到|生成|产生|发出|发送|接收|输出|输入|传送|存储|确定|涉及'
        r'|进行|调用|运行|调整|建立|构建|制得|根据|存在|使用'
    )
    _F6C_LATIN_RE = re.compile(
        r'(?:' + _F6C_VERB_ALT + r')'
        r'(?P<noun>[A-Z][A-Za-z0-9\-]{1,15}[\u4e00-\u9fff]{0,8})'
        r'(?=[，,。；;、 \t\n或与和及])'
    )
    for fc_m in _F6C_LATIN_RE.finditer(text):
        noun = fc_m.group('noun')
        if not noun or len(noun) < 2:
            continue
        if noun in seen_norms:
            continue
        seen_norms.add(noun)
        extras.append((fc_m.group(0), noun))

    # R30 mechanism #6 (2026-05-03): parenthetical abbreviation bridging.
    # Pattern B intros like `<full term>(<Abbr>)` should register both
    # full and abbrev so later `所述<Abbr>` references resolve.
    # Phase 2c Refinement B (Christopher: LHT/VH-region pattern is common).
    # CN form: `中心单元-控制面(CU-CP)`, `超参数自适应选择策略单元(HASS)`.
    # R34 (2026-05-04): mirror of TW R34 widening \u2014 accept full-width
    # \u5168\u89d2 parens AND lowercase-full-form-then-uppercase-abbrev shape
    # (`\u7528\u6237\u8bbe\u5907(user equipment, UE)`). Cross-jurisdiction parity.
    _PAREN_ABBREV_RE_R30 = re.compile(
        r'([\u4e00-\u9fff]{2,12})'
        r'[(\uff08]\s*'
        r'(?:[a-z][A-Za-z0-9\- ]{0,40}[,;\uff0c\uff1b]\s*)?'
        r'([A-Z][A-Za-z0-9\-]{0,15})'
        r'\s*[)\uff09]'
    )
    for pa_m in _PAREN_ABBREV_RE_R30.finditer(text):
        full_noun = pa_m.group(1)
        abbrev = pa_m.group(2)
        if abbrev not in seen_norms and len(abbrev) >= 2:
            seen_norms.add(abbrev)
            extras.append((pa_m.group(0), abbrev))
        if full_noun not in seen_norms:
            seen_norms.add(full_noun)
            extras.append((pa_m.group(0), full_noun))

    # R37 (2026-05-04): mirror of TW R37 F22 — list-item bare-noun
    # extraction WITHOUT colon trigger. CN parity: parent claim
    # introduces multiple components in `<verb><N1>、<N2>以及<N3>`
    # comma-list shape:
    #   `导电端子包括差分信号端子、第一接地端子以及第二接地端子`
    # Trigger verbs limited to `包括`/`包含` (most reliable list verbs).
    # Each item must be 2-12 pure CJK chars (filters out fragments
    # with embedded Latin/digit/punctuation). Reference-prefix items
    # are skipped (they're not new intros).
    # R44 (2026-05-04): expand triggers to 具有/具备/设有/含有 BUT only
    # when the captured list has >=2 commas (3+ items) — single-comma
    # lists with these triggers were too noisy on R37/R38 gate-3
    # spec-support test. 3+ items strongly signal a list (not a
    # possessive or modifier sequence).
    _F22_NO_COLON_LIST_CN = re.compile(
        r'(?:包括|包含)'
        r'((?:[一-鿿]{2,12}[、，])+'
        r'(?:[一-鿿]{2,12}(?:以及|及|和|或))?'
        r'[一-鿿]{2,12})'
        r'|'
        r'(?:具有|具备|设有|含有)'
        r'((?:[一-鿿]{2,12}[、，]){2,}'
        r'(?:[一-鿿]{2,12}(?:以及|及|和|或))?'
        r'[一-鿿]{2,12})'
    )
    _F22_LIST_SPLIT_CN = re.compile(r'[、，]|以及|及|和|或')
    for fl_m in _F22_NO_COLON_LIST_CN.finditer(text):
        # Either group 1 (包括/包含 with >=1 comma) or group 2
        # (具有/具备/设有/含有 with >=2 commas) captures the list.
        list_text = fl_m.group(1) or fl_m.group(2)
        if not list_text:
            continue
        for item_raw in _F22_LIST_SPLIT_CN.split(list_text):
            item = item_raw.strip()
            if not item or len(item) < 2:
                continue
            if item.startswith(_REF_PREFIX_SET_CN):
                continue
            if not all('一' <= ch <= '鿿' for ch in item):
                continue
            if item in seen_norms:
                continue
            seen_norms.add(item)
            extras.append((fl_m.group(0), item))

    return cleaned + extras


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

    # R7 (2026-04-30): also apply strip_leading_verb_cn to supplementary
    # intros so a captured `制造方法` (from F14 on `之制造方法`) registers
    # as `方法` after stripping the leading 制造 verb prefix — matching
    # the canonical method-claim head-noun reference `所述方法`.
    supplementary = _extract_supplementary_intros_cn(claim.text)
    for orig, norm in supplementary:
        norm = strip_leading_verb_cn(norm)
        if not norm or norm in seen:
            continue
        # R32 (2026-05-04): TW parity — drop intros with newline/colon
        # (capture crossed paragraph or label boundary). Spec-support
        # reads intros directly so guard at extraction time.
        if '\n' in norm or '：' in norm or ':' in norm:
            continue
        seen.add(norm)
        pairs.append((orig, norm))

    # R32 (2026-05-04): F-head-indep — capture rightmost head noun from
    # `一种<modifier>的<HEAD>，` independent-claim preambles. CN parity
    # with TW R32. Default `_INTRO_PATTERN_CN` excludes `的` from the
    # noun class, so a long preamble like `用于X的Y的装置` only captures
    # fragment intros, leaving the canonical head `装置` unregistered
    # for downstream `所述装置` references in dependent claims.
    #
    # Conflict guard: skip registration when claim text contains a
    # `<head><positional-suffix>` form (装置侧, 处理器端) that would be
    # a distinct §112 entity. Without this, prefix-match resolves
    # `所述装置侧` → `装置` and masks legit drafting errors (CN115485995B
    # c121 protect:true label).
    for m in _F_HEAD_INDEP_RE_CN.finditer(claim.text):
        head = m.group('head')
        if not head or head in seen:
            continue
        if _f_head_indep_conflict_cn(head, claim.text):
            continue
        seen.add(head)
        pairs.append((m.group(0), head))

    return pairs


# R32 (2026-05-04): F-head-indep regex (CN parity with TW). Captures
# rightmost head noun in `一种<modifier>的<HEAD>，` preambles.
# Conflict guard applied at registration time (not in regex): the head
# is rejected if `<head><1-3 CJK>` appears elsewhere in the claim text,
# since prefix-match resolution would over-resolve longer references
# onto the captured head (CN115485995B c121: `装置 + 装置侧` collision
# masks legit drafting error). The narrower regex (lookahead trailing
# verbs) was tried but lost ~95 walker_fp silences in CN, ~135 in TW;
# the conflict-guard approach preserves silence yield while protecting
# protect:true labels.
_F_HEAD_INDEP_RE_CN: re.Pattern[str] = re.compile(
    r'一种(?:[^，。；,;:：]{4,80})的'
    r'(?P<head>[一-鿿]{2,12})'
    r'(?=[，,。；;:：])'
)


_F_HEAD_POSITIONAL_SUFFIX_RE_CN: re.Pattern[str] = re.compile(
    r'(?:侧|端|部|面|段|层|区|际|际面|底|顶|前|后|左|右|内|外|上|下|侧面|端面|端部|底部|顶部|前面|后面|左面|右面|内部|外部|上部|下部|内侧|外侧|内端|外端|内层|外层|内面|外面)'
)


def _f_head_indep_conflict_cn(head: str, claim_text: str) -> bool:
    """True if registering `head` would cause prefix-match over-resolution.

    R32 (2026-05-04): scan for `<head><positional-suffix>` patterns where
    the suffix indicates a DIFFERENT entity (装置侧 vs 装置, 处理器端 vs
    处理器). Positional suffixes (侧/端/部/面/段/底/顶/前/后/左/右/内/外/上/下
    + compounds) frequently create distinct claim elements; prefix-match
    would wrongly resolve them. Compound-noun patterns (装置中的, 装置包括)
    don't trigger because they require additional non-suffix CJK after.
    """
    pattern = re.compile(re.escape(head) + r'(?:' + _F_HEAD_POSITIONAL_SUFFIX_RE_CN.pattern + r')(?:[，,。；;:： \t]|$)')
    return bool(pattern.search(claim_text))


def full_ref_starts_with_plural_cn(text: str) -> bool:
    """True iff text begins with a plural quantifier marker."""
    return text.startswith(("复数", "多个", "数个", "复数个"))


_BARE_GENUS_NOUNS_CN: frozenset[str] = frozenset({
    "方法", "装置", "系统", "设备", "组件",
    "模块", "单元", "电路", "部件", "芯片",
})

_GENUS_PREAMBLE_RE_CN: re.Pattern[str] = re.compile(
    r"(?:(?:如|根据)权利要求[^，。\n]*?" + _CN_DEP_CONNECTIVE + r"[^，。\n]*?|一种[^，。\n]*?)"
    r"(?:方法|装置|系统|设备|组件|模块|单元|电路|部件|芯片)[，,\s]"
)


# Phase 8c R22 — chemistry formula reference like 式(1) / 式(L-4) / 式(I).
# These are bibliographic-style references to formulae defined elsewhere in
# the spec, not noun terms; missing-antecedent doesn't apply.
_FORMULA_REFERENCE_RE_CN: re.Pattern[str] = re.compile(r"^式\([^)]+\)$")

# Phase 8c R22 — verb-predicate term suppression. Walker captured a bare
# verbal idiom (e.g., 安装有 from 使得安装有X的Y); the trailing-strip already
# eliminated the noun head, leaving the pure predicate as the term.
# R23 extends with cascade-product predicates from over_capture round
# (加入胰蛋白酶消化 → 加入; 加热沸腾提取 → 加热沸腾).
_VERB_PREDICATE_TERMS_CN: frozenset[str] = frozenset({
    "安装有", "存储有", "形成有", "设置有",
    "加入", "加热沸腾",
})


_FORMULA_ORDINAL_RE_CN: re.Pattern[str] = re.compile(r"^第[A-Za-z]")
_BARE_ORDINAL_RE_CN: re.Pattern[str] = re.compile(
    r"^第[一二三四五六七八九十\d]+$"
)


# Phase 8c R21 — DYM quality gate. Audit (docs/8c/suggested-match-audit.md,
# Phase 9 #57) showed 85% of corpus DYMs have substring-relationship with
# the reference; ~30% of those are over-captured garbage the walker's intro
# extraction pool emitted as legitimate intros. These filters reject DYM
# candidates the Jaccard loop already picked, without changing the finding
# pool. Non-shifting — `suggested_match` is terminal-only.
_DYM_LEADING_REJECTS_CN: tuple[str, ...] = (
    "能够由", "响应于", "针对", "基于",
    "对", "从", "向", "为", "在",
    "与", "和", "以", "于", "且", "还", "由", "被",
)

_DYM_STOP_PARTICLES_CN: tuple[str, ...] = (
    "的", "于", "在", "为", "对", "从", "向",
    "与", "和", "以", "且", "还", "由", "被",
    "所述", "前述", "该",
    "能够由", "响应于", "针对", "基于",
    "初始化时", "之前", "之后",
)


def _dym_quality_reject_cn(ref: str, dym: str) -> bool:
    """True if DYM should be suppressed.

    Three filters:
      1. `len(dym) > 2 * len(ref)` — disproportionate expansion.
      2. DYM starts with a token in `_DYM_LEADING_REJECTS_CN` — walker
         captured a prep/particle-headed fragment, not a clean NP.
      3. `ref in dym` strict substring AND the wrapping chars contain any
         stop-particle — walker captured the ref + noise.
    """
    if len(dym) > 2 * len(ref):
        return True
    for prefix in _DYM_LEADING_REJECTS_CN:
        if dym.startswith(prefix):
            return True
    if len(ref) < len(dym) and ref in dym:
        idx = dym.index(ref)
        before = dym[:idx]
        after = dym[idx + len(ref):]
        if any(p in before or p in after for p in _DYM_STOP_PARTICLES_CN):
            return True
    return False


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
        (ADR-107). TW uses single-key dedup pending Phase 9 parity.

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

        # R32 (2026-05-04): Path A equivalent for CN — chain-level
        # ordinal-prefix bridging. Mirror of TW R32. Two guards:
        #   1. Multi-modifier ambiguity (no other 第N+suffix in chain).
        #   2. Prefix-conflict (suffix not followed by 1-3 CJK in claim
        #      text outside the ordinal-prefixed source intro itself).
        _R32_ORDINAL_RE_CN = re.compile(r'^第[一二三四五六七八九十百0-9]+')
        suffix_count_chain_cn: dict[str, int] = {}
        suffix_anchor_chain_cn: dict[str, tuple[int, int]] = {}
        for norm, (ancestor_id, depth) in intros_by_term.items():
            mo = _R32_ORDINAL_RE_CN.match(norm)
            if not mo:
                continue
            suffix = norm[mo.end():]
            if len(suffix) < 2:
                continue
            suffix_count_chain_cn[suffix] = suffix_count_chain_cn.get(suffix, 0) + 1
            existing = suffix_anchor_chain_cn.get(suffix)
            if existing is None or depth < existing[1]:
                suffix_anchor_chain_cn[suffix] = (ancestor_id, depth)
        for suffix, count in suffix_count_chain_cn.items():
            if count > 1:
                continue
            if suffix in intros_by_term:
                continue
            conflict_re = re.compile(re.escape(suffix) + r'[一-鿿]{1,3}')
            has_conflict = False
            for ancestor in chain:
                full_re = re.compile(r'第[一二三四五六七八九十百0-9]+' + re.escape(suffix))
                consumed = full_re.sub('', ancestor.text)
                if conflict_re.search(consumed):
                    has_conflict = True
                    break
            if has_conflict:
                continue
            intros_by_term[suffix] = suffix_anchor_chain_cn[suffix]


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
                "document_dedup_key": make_document_dedup_key(
                    normalized_term or raw_noun, prefix
                ),
                # Q1 path is a rule-based detection of TC-plural prefixes
                # (该等/该些) on a CN doc. Not pattern-based — the prefix
                # alone is the violation under CNIPA审查指南 guidance to
                # use 所述. Very rarely a false positive in practice;
                # ship a fixed high confidence so the tier-display knob
                # treats these as high-confidence by default.
                "confidence_score": 90,
            }
            if not normalized_term:
                finding["note"] = "cleanup_empty"
            issues.append(finding)

        # Q3 tuple dedup (ADR-107): the key is the pair
        # (normalized_term, normalized_reference_form). See the
        # module-header ADR-107 comment for the parity rationale.
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

            # R46 (2026-05-04): mirror of TW R46 — ordinal-prefix-to-
            # Latin-abbrev bridge. Reference `第N<X>` where X is short
            # uppercase Latin abbrev (2-5 chars) and `<X>` is registered
            # as an intro -> bridge. Common in CN 5G/wireless drafts.
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

            # R29 (2026-05-03) — Resolution-side architectural mechanisms
            # (forward-prefix with boundary, symmetric clean, cross-branch
            # sibling, substring) all silenced protect:true legit_drafting
            # _error labels (parallel-invention drafter errors on
            # CN115485995B / CN113939805B / CN110276410B). §112(b) is
            # strict: references must resolve to SAME-CHAIN antecedents,
            # not sibling-claim intros or substring matches. Round 29
            # restricted to the capture-side fix (F11 ;-segment continuation
            # in _extract_supplementary_intros_cn) plus conservative trim-
            # verb extensions, both of which respect the chain invariant.

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

            # Phase 8c R21 — DYM quality gate
            if (
                suggested_match is not None
                and _dym_quality_reject_cn(
                    normalized_term, suggested_match["term"]
                )
            ):
                suggested_match = None

            if _is_bare_genus_self_reference_cn(normalized_term, claim.text):
                continue

            if "权利要求" in normalized_term:
                continue

            # R32 (2026-05-04): TW parity — citation boilerplate filter
            # (任一项 stranded after `权利要求` substring removal would
            # otherwise pass — but multi-dep refs like `任一项所述的X`
            # produce term=`任一项` directly when the dep regex misses).
            if "任一项" in normalized_term or "申请专利范围" in normalized_term:
                continue

            if len(normalized_term) == 1:
                continue

            # R32 (2026-05-04): TW parity — newline/colon filter. F-anchor
            # captures crossing paragraph or label boundaries leak garbage
            # into spec-support too via shared extract_introductions_cn.
            if '\n' in normalized_term or '：' in normalized_term or ':' in normalized_term:
                continue

            if _FORMULA_ORDINAL_RE_CN.match(normalized_term):
                continue

            if _BARE_ORDINAL_RE_CN.match(normalized_term):
                continue

            # Phase 8c R22 — chemistry formula reference + verb-predicate suppression
            if _FORMULA_REFERENCE_RE_CN.match(normalized_term):
                continue

            if normalized_term in _VERB_PREDICATE_TERMS_CN:
                continue

            # Structural fingerprint (ADR-145) — mirror of TW walker.
            # No claim content; counts + booleans only.
            diagnostics = {
                "prefix_charlen": len(prefix),
                "term_charlen": len(normalized_term),
                "intros_pool_size": len(intros_by_term),
                "has_suggested_match": suggested_match is not None,
                "suggested_cross_branch": bool(
                    suggested_match and suggested_match.get("cross_branch")
                ) if suggested_match else False,
            }
            confidence_score = compute_confidence_score(
                term=normalized_term,
                prefix=prefix,
                intros_pool_size=len(intros_by_term),
                has_suggested_match=suggested_match is not None,
                suggested_cross_branch=bool(
                    suggested_match and suggested_match.get("cross_branch")
                ),
                suggested_jaccard=best_score if suggested_match else None,
                suggested_same_claim=bool(
                    suggested_match
                    and suggested_match.get("claim_id") == claim.id
                ),
            )
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
                }
            )

    issues.sort(key=lambda x: (x["claim_id"], x["term"], x["reference_form"]))
    return issues
