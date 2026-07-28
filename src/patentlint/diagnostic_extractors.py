# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""Per-check diagnostic extractors.

Each function in this module produces a detailed-but-bounded
fingerprint dict for one check family. The fingerprint is what the
modal previews to the user before they consent to send, what lands in
the GitHub issue body, and what scheduled triage automation reads via
`gh issue list` to propose fixes.

Design principles
-----------------
- **Pinpoint, not panorama**: per-finding fields tell us what term /
  phrase / paragraph caused the check to fire - enough to reproduce
  locally without the user's draft.
- **Top-N sample**: at most 5 findings per report. A check with 100
  matches sends 5 representatives + the aggregate count.
- **Bounded fragments**: terms ≤80 chars, regex matches ≤120 chars,
  context windows sized per script (Latin 30 / Japanese 22 / Hangul
  18 / Han 12) so the linguistic content shown is roughly equivalent
  across scripts. Han chars carry ~4x the morpheme density of Latin
  chars; Japanese mixes Han with kana inflection and long katakana
  technical terms (closer to Latin than Han); Hangul is syllabic.
  The ancestor-introduction excerpt uses a deliberately smaller second
  tier (Latin 16 / JA 12 / Hangul 10 / Han 7) - it only needs to show
  the introduction's grammatical shape, and it exposes a second
  claim's prose, so the window is held to the minimum. Never the whole
  claim text or paragraph. The user sees every fragment in the modal
  preview and can decline.
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
- `_excerpt_around(text, target)`: returns the `(context_before,
  context_after, char_offset)` triple for the first occurrence of
  `target` in `text`. Window size is auto-picked from the script of
  `text` via `_context_window_for`. Returns `(None, None, None)` if
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

# 2026-06-01: context windows widened (30/22/18/12 → 60/45/35/25) to
# enable autonomous triage of reports without asking the user for
# additional draft context. The previous narrow windows frequently
# truncated surrounding verb/possessive/Markush boundaries that
# determine walker-FP vs legit-defect classification. Mirror of the
# client-side change in frontend/src/lib/feedback.js so server-side
# and client-side report payloads agree.
CONTEXT_WINDOW_LATIN = 80
CONTEXT_WINDOW_JA = 60
CONTEXT_WINDOW_HANGUL = 45
CONTEXT_WINDOW_HAN = 35

# Ancestor-introduction excerpt windows - deliberately ~half the
# child-claim context window above. The ancestor excerpt exists only to
# reveal the *shape* of the introduction: the token immediately before
# the term (an article → recognized intro / back-ref; a verb → bare
# verb-object intro; a preposition / compound interior → mis-token).
# It is NOT meant to show full vicinity. A second claim's prose appears
# in the payload here, so the window is held to the minimum that still
# answers "what shape is this introduction?", keeping the modal-preview
# trust surface small. Same four script tiers as the child window.
ANCESTOR_WINDOW_LATIN = 16
ANCESTOR_WINDOW_JA = 12
ANCESTOR_WINDOW_HANGUL = 10
ANCESTOR_WINDOW_HAN = 7

TERM_MAX = 80
MATCH_MAX = 120
EXCERPT_MAX = 60
PREAMBLE_MAX = 60
SAMPLE_SIZE = 5

_ANCESTOR_WINDOW_BY_BASE = {
    CONTEXT_WINDOW_LATIN: ANCESTOR_WINDOW_LATIN,
    CONTEXT_WINDOW_JA: ANCESTOR_WINDOW_JA,
    CONTEXT_WINDOW_HANGUL: ANCESTOR_WINDOW_HANGUL,
    CONTEXT_WINDOW_HAN: ANCESTOR_WINDOW_HAN,
}


def _context_window_for(text: str) -> int:
    """Pick a per-script context window so the modal preview shows
    roughly equivalent linguistic content regardless of script.

    Widths were widened twice for richer self-sufficient trails (latest
    #337, 2026-06-23); current values are the module constants below
    (Han 35 / JA 60 / Hangul 45 / Latin 80), tuned so each script holds
    roughly equivalent linguistic content:
    - Han (zh-TW / zh-CN): 35 - each char ≈ 1 morpheme, very dense.
    - Japanese: 60 - kana inflection + long katakana technical terms
      (e.g. インターフェース = 8 chars for one concept) inflate token
      count well beyond pure Han or Hangul, so JA needs more chars to
      hold the same semantic content. Detected via kana presence -
      CN/TW drafts virtually never contain hiragana/katakana, so even
      a few kana chars are a near-perfect Japanese signal.
    - Hangul: 45 - syllabic blocks, denser than JA's mixed scripts.
    - Latin (en/de): 80 - ~5 chars/word.

    Detection is content-driven (reads ``text``), not UI-locale-driven:
    a US user analyzing a TW patent still gets the Han window because
    the claim text itself is Han-dominant. Kana uses an absolute
    count ≥ 3 (real JP claims always have lots of hiragana particles
    の/を/に/で/は; a stray katakana product name in a CN claim won't
    cross 3). Han/Hangul use a 0.3 ratio matching the threshold in
    ``parser/jurisdiction_mismatch.py``."""
    if not text:
        return CONTEXT_WINDOW_LATIN
    n = len(text)
    kana = sum(1 for c in text if "぀" <= c <= "ヿ")
    if kana >= 3:
        return CONTEXT_WINDOW_JA
    han = sum(1 for c in text if "一" <= c <= "鿿")
    if han / n > 0.3:
        return CONTEXT_WINDOW_HAN
    hangul = sum(1 for c in text if "가" <= c <= "힯")
    if hangul / n > 0.3:
        return CONTEXT_WINDOW_HANGUL
    return CONTEXT_WINDOW_LATIN


def _ancestor_window_for(text: str) -> int:
    """Half-size sibling of ``_context_window_for`` for the ancestor-
    introduction excerpt. Reuses the same content-driven script
    detection, then maps each script's child window onto its smaller
    ancestor window (see ``ANCESTOR_WINDOW_*`` rationale)."""
    return _ANCESTOR_WINDOW_BY_BASE.get(
        _context_window_for(text), ANCESTOR_WINDOW_LATIN
    )


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


def _excerpt_around(text: str, target: str, before: int | None = None, after: int | None = None, case_insensitive: bool = False) -> tuple[str | None, str | None, int | None]:
    """Return (context_before, context_after, char_offset) for the first
    occurrence of ``target`` inside ``text``. Window size is picked from
    the script of ``text`` when ``before``/``after`` are not given.
    ``case_insensitive`` locates the match without regard to case but
    still slices the windows from the original-cased ``text`` - used for
    the ancestor excerpt, where the walker's normalized (lowercased)
    term may not case-match the raw ancestor claim text.
    Returns all-None if not found or if either input is empty."""
    if not text or not target:
        return None, None, None
    idx = text.lower().find(target.lower()) if case_insensitive else text.find(target)
    if idx < 0:
        return None, None, None
    window = _context_window_for(text)
    if before is None:
        before = window
    if after is None:
        after = window
    ctx_before = text[max(0, idx - before): idx] or None
    end = idx + len(target)
    ctx_after = text[end: end + after] or None
    return ctx_before, ctx_after, idx


def _excerpt_around_reference(
    text: str, term: str, reference_form: str | None,
    before: int | None = None, after: int | None = None,
) -> tuple[str | None, str | None, int | None]:
    """Return (context_before, context_after, char_offset) anchored on the
    FLAGGED REFERENCE occurrence of ``term`` - not its first mention.

    The §112(b) walker flags a *reference* (`所述X` / `the X`) that lacks an
    introduction. Anchoring the diagnostic on ``text.find(term)`` (the FIRST
    occurrence) is wrong: the first mention is frequently the introduction
    itself, so the trail showed the term being properly introduced while the
    card claimed it was missing - confusing, and it hid that the flag was on a
    later occurrence (reported on issues #265/#266/#267, all jurisdictions).

    Resolution order, jurisdiction-agnostic:
      1. locate ``reference_form`` (e.g. `所述預設方向` / `the skin`); anchor on
         the ``term`` inside it (the reference form ends with the bare term);
      2. else fall back to the term's LAST occurrence (`rfind`) - the reference
         is the later mention, never the first;
      3. else all-None.
    """
    if not text or not term:
        return None, None, None
    idx = -1
    if reference_form:
        ref_idx = text.lower().find(reference_form.lower())
        if ref_idx >= 0:
            # term sits at the tail of the reference form (prefix + term)
            inner = reference_form.lower().rfind(term.lower())
            idx = ref_idx + (inner if inner >= 0 else max(0, len(reference_form) - len(term)))
    if idx < 0:
        # no verbatim reference form → the flagged occurrence is the LAST one
        idx = text.lower().rfind(term.lower())
    if idx < 0:
        return None, None, None
    window = _context_window_for(text)
    if before is None:
        before = window
    if after is None:
        after = window
    ctx_before = text[max(0, idx - before): idx] or None
    end = idx + len(term)
    ctx_after = text[end: end + after] or None
    return ctx_before, ctx_after, idx


def _claim_preamble(claim_text: str | None, n: int = PREAMBLE_MAX) -> str | None:
    """First ``n`` chars of a claim. Useful for showing the user 'this
    is the claim you flagged' without dumping the whole claim."""
    return _truncate(claim_text, n)


# ---------------------------------------------------------------------------
# Category A - Walker §112
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
    # Body cross-references in this finding-set's claims - list of cited
    # claim numbers extracted from `the X according to claim N` /
    # `如請求項N所述的Y` body shapes. Surfaces #124 / #143-class cases
    # autonomously: triage can see whether the term has a possible
    # cross-claim incorporation source without needing the draft.
    import re as _ab_re
    body_cross_refs_per_claim = {}
    for f in findings:
        cid = f.get("claim_id")
        if cid is None or cid in body_cross_refs_per_claim:
            continue
        ct = f.get("claim_text") or ""
        # Match `claim N` cross-references regardless of language
        # (Latin `claim N`, CJK `請求項N` / `权利要求N`).
        refs = set()
        for m in _ab_re.finditer(r"\bclaims?\s+(\d+)\b", ct, _ab_re.IGNORECASE):
            refs.add(int(m.group(1)))
        for m in _ab_re.finditer(r"(?:請求項|权利要求|权利要求)\s*(\d+)", ct):
            refs.add(int(m.group(1)))
        # Exclude self-references
        body_cross_refs_per_claim[cid] = sorted(r for r in refs if r != cid)
    for f in sample:
        term = f.get("term") or ""
        claim_text = f.get("claim_text") or ""
        # Anchor the trail on the FLAGGED REFERENCE (所述X / the X), not the
        # first mention (which is often the introduction) - issues #265/266/267.
        ctx_before, ctx_after, offset = _excerpt_around_reference(
            claim_text, term, f.get("reference_form"))
        suggested = f.get("suggested_match") or {}
        # NP-boundary char: the single char IMMEDIATELY after the matched
        # term in claim text. Tells me what stopped the NP capture and
        # whether a stop-word / boundary-set extension would fix it
        # (e.g., if next char is 又 / 從 / 之 / 'comprises' that's a
        # missing exclusion). Privacy-safe - single CJK or ASCII char.
        np_boundary_char = None
        if offset is not None and isinstance(offset, int):
            end_pos = offset + len(term)
            if 0 <= end_pos < len(claim_text):
                np_boundary_char = claim_text[end_pos]
        # Leading reference-marker presence - surfaces 所述/前述/該/the/said
        # immediately preceding the term, which informs whether the
        # walker captured a reference vs an article-less intro. Helps
        # classify possessive-intro (#134) / chain-inheritance (#124)
        # cases without the draft.
        ref_marker_before = None
        if offset is not None and isinstance(offset, int) and offset > 0:
            for marker in ("所述", "前述", "該等", "該些", "該", "前述",
                            "said ", "the "):
                start = offset - len(marker)
                if start >= 0 and claim_text[start:offset].lower().endswith(marker.lower()):
                    ref_marker_before = marker.strip()
                    break
        # 2026-06-01 (issue #178/#179): NP-stop diagnostic. For Latin-script
        # findings, `term_word_count` + `next_word_after_term` together
        # surface over-stop bugs autonomously: a term of 1-2 words with
        # a stop-word-class next word (preposition/conjunction/verb) is
        # the signature of _NP_CORE truncating mid-compound. Combined
        # with the existing `np_boundary_char`, future triage can tell
        # an over-stop apart from a legit missing-antecedent without
        # seeing the draft. Privacy-safe: just the head of one word.
        term_word_count = len(term.split()) if term else 0
        next_word_after_term = None
        if offset is not None and isinstance(offset, int):
            end_pos = offset + len(term)
            tail = claim_text[end_pos:end_pos + 32] if end_pos < len(claim_text) else ""
            tail_match = _ab_re.match(r"\s*([A-Za-z一-鿿]{1,20})", tail)
            if tail_match:
                next_word_after_term = tail_match.group(1)[:20]
        # Same-claim earlier-introduction signal. Independent of the
        # walker's intro-validity guards (has_bare_noun_introduction_*
        # etc.): a plain check for whether the flagged term's string
        # appears in the claim text BEFORE the flagged reference. When
        # True, the term was almost certainly introduced earlier in the
        # SAME claim (article-less / bare-noun, or a verb-object intro)
        # but in a shape the intro extractor missed - a walker FP, not a
        # genuine §112 gap. This is the same-claim sibling of
        # `term_in_ancestor_text` (which covers the parent/ancestor case),
        # and together they let triage classify the bare-noun /
        # ancestor-chain FP family from the payload alone. Reported users
        # said "same claim introduces X already" (#206/#207 US,
        # #221/#224/#225 CN) - exactly this signal. Jurisdiction-agnostic:
        # a substring scan over the de-identified claim_text the walker
        # already supplies (no new draft content reaches the payload).
        term_earlier_in_claim = False
        if term and claim_text:
            ref_form = f.get("reference_form") or ""
            haystack = claim_text.lower()
            ref_pos = haystack.find(ref_form.lower()) if ref_form else -1
            if ref_pos < 0:
                # reference_form not located verbatim (the walker may have
                # normalized it); fall back to the term's own LAST
                # occurrence as the reference proxy so the "before"
                # window excludes the flagged reference itself.
                ref_pos = haystack.rfind(term.lower())
            if ref_pos > 0:
                term_earlier_in_claim = term.lower() in haystack[:ref_pos]
        # Candidate-introduction excerpt (the self-sufficiency upgrade,
        # 2026-06-25). `term_earlier_in_claim` only says the term appears
        # earlier - but the FP-vs-legit call hinges on HOW: an article-less
        # earlier mention (`attached to skin` / `貼附於人體`) is a missed
        # bare-noun introduction (walker FP), whereas an earlier mention that
        # is ITSELF a reference (`the X` / `所述X`) or sits only inside a verb
        # phrase (`collecting information`) is a genuine §112 gap. So when the
        # term occurs earlier, emit a SECOND bounded excerpt anchored on that
        # earliest occurrence + the marker immediately preceding it, so a
        # report self-classifies without the draft. Marker is reported as a
        # FACT (not a verdict) - the article-less-vs-intro-quantifier-vs-
        # reference distinction is the classifier; the excerpt shows whether
        # the earliest mention is a bare noun or buried in a verb phrase.
        # Privacy §6: uses the smaller ancestor-sized window; same in-claim
        # text the walker already supplies (no new draft content).
        intro_candidate_marker = None
        intro_ctx_before = intro_ctx_after = intro_candidate_offset = None
        if term_earlier_in_claim and claim_text:
            early_idx = claim_text.lower().find(term.lower())
            if 0 <= early_idx < (ref_pos if ref_pos > 0 else len(claim_text)):
                w = _ancestor_window_for(claim_text)
                intro_ctx_before = claim_text[max(0, early_idx - w): early_idx] or None
                e_end = early_idx + len(term)
                intro_ctx_after = claim_text[e_end: e_end + w] or None
                intro_candidate_offset = early_idx
                # Classify the leading marker. Reference markers (該/所述/the)
                # mean the earliest mention is itself a reference → term never
                # introduced (legit-leaning); intro quantifiers (一/a/an) mean
                # an explicit introduction (FP-leaning); neither → article-less
                # bare noun (read the excerpt: bare-noun intro vs verb-phrase).
                _REF_MARKERS = ("所述", "前述", "該等", "該些", "該", "said ", "the ")
                _INTRO_MARKERS = ("一種", "一個", "一", "每一", "至少一", "複數", "多個",
                                  "at least one ", "an ", "a ")
                marker = "article_less"
                for grp in (_REF_MARKERS, _INTRO_MARKERS):
                    for mk in grp:
                        s = early_idx - len(mk)
                        if s >= 0 and claim_text[s:early_idx].lower().endswith(mk.lower()):
                            marker = mk.strip()
                            break
                    if marker != "article_less":
                        break
                intro_candidate_marker = marker
        out = {
            "claim_id": f.get("claim_id"),
            "term": _truncate(term, TERM_MAX),
            "reference_form": _truncate(f.get("reference_form"), 40),
            "did_you_mean": _truncate(suggested.get("term") if isinstance(suggested, dict) else None, TERM_MAX),
            "did_you_mean_claim_id": suggested.get("claim_id") if isinstance(suggested, dict) else None,
            "np_boundary_char": np_boundary_char,
            "next_word_after_term": next_word_after_term,
            "term_word_count": term_word_count,
            "term_earlier_in_claim": term_earlier_in_claim,
            "intro_candidate_marker": intro_candidate_marker,
            "intro_candidate_offset": intro_candidate_offset,
            "intro_candidate_context_before": intro_ctx_before,
            "intro_candidate_context_after": intro_ctx_after,
            "ref_marker_before": ref_marker_before,
            "body_cross_refs": body_cross_refs_per_claim.get(f.get("claim_id"), [])[:10],
            # Issue #70: which lookup produced the did-you-mean. A null
            # `did_you_mean_claim_id` is ambiguous on its own - it means
            # either a chain/morphological hit whose id wasn't threaded,
            # OR a 符號說明 (symbol-table) hit which has no claim id by
            # design. `did_you_mean_source` disambiguates: "symbol_table"
            # ⇒ the term is a declared element but has no claim-level
            # intro (a legitimate §26 flag, not a walker FP - 符號說明 is
            # a lookup, never an antecedent-basis silencer); null ⇒
            # chain/morphological (and `did_you_mean_claim_id` is set).
            "did_you_mean_source": suggested.get("source") if isinstance(suggested, dict) else None,
            "category": _truncate(f.get("category"), 40),
            "char_offset": offset,
            "context_before": ctx_before,
            "context_after": ctx_after,
            "claim_text_charlen": len(claim_text) if claim_text else 0,
        }
        # Issue #70: TW walker tags each finding with `term_in_symbol_table`
        # - whether the flagged term is a declared 符號說明 element. For a
        # parent-claim FP report this is the decisive classifier: a
        # declared element with no ancestor intro is a legitimate
        # claim-drafting flag, not a walker bug. TW-only (CN/US have no
        # 符號說明) - surfaced only when the walker supplied it.
        if "term_in_symbol_table" in f:
            out["term_in_symbol_table"] = bool(f.get("term_in_symbol_table"))
        # Parent-claim diagnostic. Emitted only when the walker supplied
        # ancestor data (US + TW antecedent walkers as of 2026-05-21).
        # `term_in_ancestor_text` is the bit that splits a walker FP
        # (term IS introduced in a parent claim but in a shape the intro
        # extractor missed) from a genuine §112 gap (term in no
        # ancestor) - without it, an anonymous child-claim report cannot
        # be classified. The ancestor excerpt uses the deliberately
        # smaller _ancestor_window_for window; the full ancestor text
        # stays in-process and never reaches the payload.
        if "ancestor_claim_ids" in f:
            anc_text = f.get("ancestor_match_text") or ""
            anc_before = anc_after = anc_offset = None
            if anc_text:
                w = _ancestor_window_for(anc_text)
                anc_before, anc_after, anc_offset = _excerpt_around(
                    anc_text, term, before=w, after=w, case_insensitive=True
                )
            out["ancestor_claim_ids"] = f.get("ancestor_claim_ids")
            out["term_in_ancestor_text"] = bool(anc_text)
            out["ancestor_match_claim_id"] = f.get("ancestor_match_claim_id")
            out["ancestor_char_offset"] = anc_offset
            out["ancestor_context_before"] = anc_before
            out["ancestor_context_after"] = anc_after
        out_findings.append(out)
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
        phrase = ut_dict.get("phrase") or ""
        # Phrase shape markers - surfacing without draft access whether
        # the captured phrase shows leading-qualifier retention (so_shu)
        # or terminal compound-noun-suffix presence (so we can tell
        # whether normalize chain stripped the qualifier vs failed to,
        # and whether the trailing chars belong to a known suffix class).
        first_chars = phrase[:2] if phrase else ""
        last_char = phrase[-1] if phrase else ""
        has_leading_ref_marker = any(
            phrase.startswith(m) for m in ("所述", "前述", "該等", "該些", "該", "said ", "the ")
        )
        # Token-shape hints for triage without draft access.
        out_findings.append({
            "claim_id": ut_dict.get("claim_number"),
            "phrase": _truncate(phrase, TERM_MAX),
            "tiers_checked": ut_dict.get("tiers_checked"),
            "cross_ref": ut_dict.get("cross_ref"),
            "phrase_charlen": len(phrase),
            "phrase_first_chars": first_chars,
            "phrase_last_char": last_char,
            "has_leading_ref_marker": has_leading_ref_marker,
        })
    return {
        "issue_count": len(unsupported_terms),
        "claim_count": len({getattr(ut, "claim_number", None) if not isinstance(ut, dict) else ut.get("claim_number") for ut in unsupported_terms}),
        "total_claims": total_claims,
        "spec_paragraph_count": spec_paragraph_count,
        "findings": out_findings,
    }


# ---------------------------------------------------------------------------
# Category B - Regex match
# ---------------------------------------------------------------------------


def extract_regex_matches(pairs, claims, what: str = "match") -> dict[str, Any]:
    """Generic regex-match extractor for checks that return list of
    (claim_id, matched_string) tuples or list of claim_id ints with
    related claim_text lookup.

    ``pairs`` may be:
      - list[tuple[int, str]] - claim_id + matched fragment
      - list[int] - claim IDs only (we look up text from ``claims``)
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
            # No specific match string - fall back to preamble excerpt.
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
    Omnibus / wherein-comma - these emit per-claim, not aggregated)."""
    text = getattr(claim, "text", "") or ""
    return {
        "flagged_claim_id": getattr(claim, "id", None),
        "kind": kind,
        "preamble": _claim_preamble(text),
        "claim_text_charlen": len(text),
    }


# ---------------------------------------------------------------------------
# Category C - Parser boundary
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
    list of section header strings the parser actually saw - useful for
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
# Category D - Closed-set state
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
# Category E - Claim-level structural
# ---------------------------------------------------------------------------


def extract_connection_relationships(
    flagged: list[tuple[int, int, list[str]]],
    claims,
) -> dict[str, Any]:
    """Per-issue diagnostic fingerprint for connectionRelationships
    (TW + CN). Issue #48 (2026-05-15) surfaced the gap - the check was
    emitting bare top-level CheckItems with no `findings[]` payload, so
    reports landed with empty diagnostic trails and could not be
    triaged from the issue body alone.

    Each entry in ``flagged`` is the ``(claim_id, total_component_count,
    sample_component_names)`` tuple that ``check_connection_relationships``
    builds. ``sample_component_names`` is the pre-computed short-noun-
    phrase list (head before first separator) from ``_component_name``.

    The diagnostic shape mirrors ``extract_antecedent_basis``:
      - top-level: flagged_count + total_claims + per-claim findings
      - per finding: claim_id, component_count, sample_count,
        sample_name_charlens, claim_text_charlen, plus the short
        sample_names (capped at 3, each truncated to MATCH_MAX) so
        triage can quickly see WHAT was captured - drafter-real
        components (drafter error) vs sub-clause fragments
        (walker over-capture).
    """
    if not flagged:
        return {}
    claims_by_id = {c.id: c for c in claims}
    sample = flagged[:SAMPLE_SIZE]
    out_findings = []
    for claim_id, component_count, sample_names in sample:
        claim = claims_by_id.get(claim_id)
        claim_text = (claim.text if claim is not None else "") or ""
        # Cap the names list (so a 30-component claim doesn't ship 30
        # entries) and truncate each name for length-safety. The
        # _component_name helper already returns the short head, so
        # most names are 2-15 CJK chars - MATCH_MAX is generous.
        sample_names_capped = list(sample_names[:3])
        out_findings.append({
            "claim_id": claim_id,
            "component_count": component_count,
            "sample_count": len(sample_names_capped),
            "sample_names": [_truncate(n, MATCH_MAX) for n in sample_names_capped],
            "sample_name_charlens": [len(n or "") for n in sample_names_capped],
            "claim_text_charlen": len(claim_text),
        })
    return {
        "flagged_count": len(flagged),
        "total_claims": len(claims),
        "findings": out_findings,
    }


def extract_claim_id_list(claim_ids: list[int], claims, reason_code: str | None = None) -> dict[str, Any]:
    """Generic claim-ID-list extractor - multipleDependent, selfDependent,
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
