# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Per-check diagnostic extractors.

Each function in this module produces a detailed-but-bounded
fingerprint dict for one check family. The fingerprint is what the
modal previews to the user before they consent to send, what lands in
the GitHub issue body, and what Claude Code reads via `gh issue list`
to propose fixes.

Design principles
-----------------
- **Pinpoint, not panorama**: per-finding fields tell us what term /
  phrase / paragraph caused the check to fire — enough to reproduce
  locally without the user's draft.
- **Top-N sample**: at most 5 findings per report. A check with 100
  matches sends 5 representatives + the aggregate count.
- **Bounded fragments**: terms ≤80 chars, regex matches ≤120 chars,
  context windows 30 chars before + 30 after. Never the whole claim
  text or paragraph. The user sees every fragment in the modal preview
  and can decline.
- **No identity, no link to identity**: no email, no IP, no file path,
  no session ID, no OS user info ever appears in any extractor output.

Categories
----------
A. Walker §112 (`extract_antecedent_basis`, `extract_spec_support`)
B. Regex match (`extract_markush_open`, `extract_omnibus`,
   `extract_special_format`, `extract_restrictive_phrases`)
C. Parser boundary (`extract_paragraph_sequential`,
   `extract_required_sections`, `extract_section_ordering`,
   `extract_dependency_format`)
D. Closed-set state (`extract_tracked_changes`,
   `extract_no_paragraph_numbering`, `extract_single_figure_label`)
E. Claim-level structural (`extract_claim_id_list`)

Helper conventions
------------------
- `_excerpt_around(text, target, before=30, after=30)`: returns the
  `(context_before, context_after, char_offset)` triple for the first
  occurrence of `target` in `text`. Returns `(None, None, None)` if
  not found.
- `_truncate(s, n)`: shortens a string to ≤n chars without splitting
  CJK characters in the middle (Python str slicing on codepoints, so
  this is naturally codepoint-safe).
- `_sample(items, n=5)`: returns first `n` items, plus the original
  count via the wrapper's `len()` call.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Helper primitives
# ---------------------------------------------------------------------------

CONTEXT_WINDOW = 30
TERM_MAX = 80
MATCH_MAX = 120
EXCERPT_MAX = 60
PREAMBLE_MAX = 60
SAMPLE_SIZE = 5


def _truncate(s: Any, n: int) -> str | None:
    """Return ``s`` cast to str and truncated to ``n`` codepoints, or
    None if ``s`` is None/empty. CJK chars are 1 codepoint each in
    Python, so this is naturally safe."""
    if s is None:
        return None
    text = str(s)
    if not text:
        return None
    return text[:n]


def _excerpt_around(text: str, target: str, before: int = CONTEXT_WINDOW, after: int = CONTEXT_WINDOW) -> tuple[str | None, str | None, int | None]:
    """Return (context_before, context_after, char_offset) for the first
    occurrence of ``target`` inside ``text``. Returns all-None if not
    found or if either input is empty."""
    if not text or not target:
        return None, None, None
    idx = text.find(target)
    if idx < 0:
        return None, None, None
    ctx_before = text[max(0, idx - before): idx] or None
    end = idx + len(target)
    ctx_after = text[end: end + after] or None
    return ctx_before, ctx_after, idx


def _claim_preamble(claim_text: str | None, n: int = PREAMBLE_MAX) -> str | None:
    """First ``n`` chars of a claim. Useful for showing the user 'this
    is the claim you flagged' without dumping the whole claim."""
    return _truncate(claim_text, n)


# ---------------------------------------------------------------------------
# Category A — Walker §112
# ---------------------------------------------------------------------------


def extract_antecedent_basis(findings: list[dict], total_claims: int) -> dict[str, Any]:
    """Per-finding pinpoint data for the antecedent-basis walker.

    ``findings`` is the list returned by ``check_antecedent_basis_*``;
    each item carries claim_id, term, reference_form, claim_text,
    suggested_match (did-you-mean), cross_ref, and optionally category
    (e.g. 'tw_contamination').
    """
    if not findings:
        return {}
    sample = findings[:SAMPLE_SIZE]
    out_findings = []
    for f in sample:
        term = f.get("term") or ""
        claim_text = f.get("claim_text") or ""
        ctx_before, ctx_after, offset = _excerpt_around(claim_text, term)
        suggested = f.get("suggested_match") or {}
        out_findings.append({
            "claim_id": f.get("claim_id"),
            "term": _truncate(term, TERM_MAX),
            "reference_form": _truncate(f.get("reference_form"), 40),
            "did_you_mean": _truncate(suggested.get("term") if isinstance(suggested, dict) else None, TERM_MAX),
            "did_you_mean_claim_id": suggested.get("claim_id") if isinstance(suggested, dict) else None,
            "category": _truncate(f.get("category"), 40),
            "char_offset": offset,
            "context_before": ctx_before,
            "context_after": ctx_after,
            "claim_text_charlen": len(claim_text) if claim_text else 0,
        })
    return {
        "issue_count": len(findings),
        "claim_count": len({f.get("claim_id") for f in findings if f.get("claim_id") is not None}),
        "total_claims": total_claims,
        "findings": out_findings,
    }


def extract_spec_support(unsupported_terms, total_claims: int, spec_paragraph_count: int | None = None) -> dict[str, Any]:
    """Spec-support walker fingerprint.

    ``unsupported_terms`` is a list of UnsupportedTerm Pydantic models
    (or dict-likes) with: claim_number, phrase, tiers_checked, cross_ref.
    """
    if not unsupported_terms:
        return {}
    sample = unsupported_terms[:SAMPLE_SIZE]
    out_findings = []
    for ut in sample:
        # Support both Pydantic models and dicts for flexibility.
        if hasattr(ut, "model_dump"):
            ut_dict = ut.model_dump()
        elif isinstance(ut, dict):
            ut_dict = ut
        else:
            ut_dict = {
                "claim_number": getattr(ut, "claim_number", None),
                "phrase": getattr(ut, "phrase", None),
                "tiers_checked": getattr(ut, "tiers_checked", None),
                "cross_ref": getattr(ut, "cross_ref", None),
            }
        out_findings.append({
            "claim_id": ut_dict.get("claim_number"),
            "phrase": _truncate(ut_dict.get("phrase"), TERM_MAX),
            "tiers_checked": ut_dict.get("tiers_checked"),
            "cross_ref": ut_dict.get("cross_ref"),
        })
    return {
        "issue_count": len(unsupported_terms),
        "claim_count": len({getattr(ut, "claim_number", None) if not isinstance(ut, dict) else ut.get("claim_number") for ut in unsupported_terms}),
        "total_claims": total_claims,
        "spec_paragraph_count": spec_paragraph_count,
        "findings": out_findings,
    }


# ---------------------------------------------------------------------------
# Category B — Regex match
# ---------------------------------------------------------------------------


def extract_regex_matches(pairs, claims, what: str = "match") -> dict[str, Any]:
    """Generic regex-match extractor for checks that return list of
    (claim_id, matched_string) tuples or list of claim_id ints with
    related claim_text lookup.

    ``pairs`` may be:
      - list[tuple[int, str]] — claim_id + matched fragment
      - list[int] — claim IDs only (we look up text from ``claims``)
    ``claims`` is the analysis result's claims list (Pydantic Claim
    objects with .id and .text).
    """
    if not pairs:
        return {}
    claims_by_id = {c.id: c for c in claims}
    sample = pairs[:SAMPLE_SIZE]
    out_findings = []
    for item in sample:
        if isinstance(item, tuple) and len(item) >= 2:
            claim_id = item[0]
            matched = item[1]
        else:
            claim_id = item if isinstance(item, int) else getattr(item, "id", None)
            matched = None
        claim = claims_by_id.get(claim_id) if claim_id is not None else None
        claim_text = claim.text if claim is not None else ""
        if matched is None and claim_text:
            # No specific match string — fall back to preamble excerpt.
            preamble = _claim_preamble(claim_text)
            out_findings.append({
                "claim_id": claim_id,
                "preamble": preamble,
                "claim_text_charlen": len(claim_text),
            })
        else:
            ctx_before, ctx_after, offset = _excerpt_around(claim_text, matched or "")
            out_findings.append({
                "claim_id": claim_id,
                "matched_phrase": _truncate(matched, MATCH_MAX),
                "context_before": ctx_before,
                "context_after": ctx_after,
                "char_offset": offset,
                "claim_text_charlen": len(claim_text) if claim_text else 0,
            })
    out: dict[str, Any] = {
        "flagged_count": len(pairs),
        "total_claims": len(claims),
        "findings": out_findings,
    }
    if what:
        out["what"] = what
    return out


def extract_special_format(claim, kind: str) -> dict[str, Any]:
    """Single-claim special format detector (Jepson / CRM / Markush /
    Omnibus / wherein-comma — these emit per-claim, not aggregated)."""
    text = getattr(claim, "text", "") or ""
    return {
        "flagged_claim_id": getattr(claim, "id", None),
        "kind": kind,
        "preamble": _claim_preamble(text),
        "claim_text_charlen": len(text),
    }


# ---------------------------------------------------------------------------
# Category C — Parser boundary
# ---------------------------------------------------------------------------


def extract_paragraph_sequential(numbers: list[int], gap_index: int | None = None) -> dict[str, Any]:
    """Paragraph-numbering gap fingerprint.

    ``numbers`` is the parsed sequence (e.g., [1, 2, 4, 5] missing 3).
    ``gap_index`` is the index in ``numbers`` BEFORE the gap (i.e.,
    numbers[gap_index] and numbers[gap_index+1] differ by ≠1).
    """
    if not numbers:
        return {"total_paragraphs": 0}
    out: dict[str, Any] = {
        "total_paragraphs": len(numbers),
        "first_5_numbers": numbers[:5],
        "last_5_numbers": numbers[-5:] if len(numbers) > 5 else None,
    }
    if gap_index is not None and 0 <= gap_index < len(numbers) - 1:
        before = numbers[gap_index]
        after = numbers[gap_index + 1]
        out["gap_at_index"] = gap_index
        out["expected_after"] = before + 1
        out["found_after"] = after
        out["gap_size"] = after - before - 1
    return out


def extract_required_sections(missing: list[str], detected_headers: list[str], canonical_order: list[str]) -> dict[str, Any]:
    """Required-sections check fingerprint. ``detected_headers`` is the
    list of section header strings the parser actually saw — useful for
    spotting misnormalized headers (e.g. CN check seeing TW header)."""
    return {
        "missing_count": len(missing),
        "missing_sections": missing[:SAMPLE_SIZE],
        "detected_count": len(detected_headers),
        "detected_headers_sample": [_truncate(h, 40) for h in detected_headers[:SAMPLE_SIZE]],
        "canonical_count": len(canonical_order),
    }


def extract_section_ordering(seen_indices: list[int], canonical_order: list[str]) -> dict[str, Any]:
    """Section-ordering check fingerprint."""
    return {
        "sections_seen": len(seen_indices),
        "seen_indices": seen_indices,
        "canonical_count": len(canonical_order),
        "is_increasing": all(seen_indices[i] < seen_indices[i + 1] for i in range(len(seen_indices) - 1)) if len(seen_indices) > 1 else True,
    }


def extract_dependency_format(bad_claims: list[int], claims) -> dict[str, Any]:
    """Dependency-format check fingerprint."""
    if not bad_claims:
        return {}
    claims_by_id = {c.id: c for c in claims}
    sample = bad_claims[:SAMPLE_SIZE]
    return {
        "flagged_count": len(bad_claims),
        "total_claims": len(claims),
        "findings": [
            {
                "claim_id": cid,
                "preamble": _claim_preamble(claims_by_id[cid].text) if cid in claims_by_id else None,
            }
            for cid in sample
        ],
    }


# ---------------------------------------------------------------------------
# Category D — Closed-set state
# ---------------------------------------------------------------------------


def extract_tracked_changes(paragraph_count: int, sample_paragraph_ids: list[int] | None = None) -> dict[str, Any]:
    """Tracked-changes fingerprint."""
    return {
        "reason_code": "tracked_changes_present",
        "total_paragraphs": paragraph_count,
        "sample_paragraph_ids": (sample_paragraph_ids or [])[:SAMPLE_SIZE],
    }


def extract_no_paragraph_numbering(input_format: str, paragraph_count: int) -> dict[str, Any]:
    """Paragraph-numbering missing fingerprint."""
    return {
        "reason_code": "no_paragraph_numbering",
        "input_format": input_format,
        "total_paragraphs": paragraph_count,
    }


# ---------------------------------------------------------------------------
# Category E — Claim-level structural
# ---------------------------------------------------------------------------


def extract_claim_id_list(claim_ids: list[int], claims, reason_code: str | None = None) -> dict[str, Any]:
    """Generic claim-ID-list extractor — multipleDependent, selfDependent,
    chainedMultiDep, meansFunction, etc. Surfaces the IDs plus a short
    preamble excerpt of each flagged claim so a maintainer can see what
    the regex matched on."""
    if not claim_ids:
        return {}
    claims_by_id = {c.id: c for c in claims}
    sample = claim_ids[:SAMPLE_SIZE]
    out: dict[str, Any] = {
        "flagged_count": len(claim_ids),
        "total_claims": len(claims),
        "findings": [
            {
                "claim_id": cid,
                "preamble": _claim_preamble(claims_by_id[cid].text) if cid in claims_by_id else None,
            }
            for cid in sample
        ],
    }
    if reason_code:
        out["reason_code"] = reason_code
    return out
