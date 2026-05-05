# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Measure TIPO-authoritative <numeral, name> anchor signal on TW corpus.

R61c follow-up — user pushback on R61b: 符號說明 should be used the way
TIPO uses it (authoritative anchor on <numeral, name> pairs), not as a
loose name-presence flag.

TIPO 偵錯系統 logic for antecedent (per 施行細則 §17 + 審查基準):
  - 符號說明 enumerates <numeral>:<name> declared elements
  - A claim reference like 該齒輪(10) anchors the element via numeral
  - Drafter has explicitly identified the element → presumption of
    existence is much stronger than for a bare 該齒輪 reference

Two signals computed per walker finding:

1. ref_has_paren_numeral: reference_form contains `(<numeral>)` or
   `（<numeral>）` — drafter attached an explicit numeric anchor.
2. anchored_in_symbol_table: ref has paren numeral AND
   <numeral, term-tail> matches a symbol_table entry.

Then group findings by these signals × ensemble verdict and report
per-group strict precision (legit / legit+walker_fp).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tests.eval.measure_term_in_desc import (  # noqa: E402
    load_sv2_verdicts,
)
from tests.eval.round1_corpus_harness import load_corpus, run_walker  # noqa: E402

DESCRIPTIONS = PROJECT_ROOT / "tests/eval/tw_descriptions.json"

# Inline ST mining helper that ALSO returns numerals (not just names).
# Mirrors _INLINE_ST_RE in measure_term_in_desc but exposes the full pair.
_INLINE_ST_PAIR_RE = re.compile(
    r"\b(\d{1,4}[A-Za-z]{0,2})\s*[：:．、,，\-—–]\s*"
    r"([一-鿿][一-鿿A-Za-z0-9（）\(\)]{1,15})"
)


def extract_inline_symbol_pairs(text: str) -> dict[str, str]:
    """Return {numeral: name} pairs mined from flattened description body."""
    out: dict[str, str] = {}
    for m in _INLINE_ST_PAIR_RE.finditer(text):
        numeral = m.group(1).strip()
        name = m.group(2).strip()
        if 2 <= len(name) <= 16:
            out.setdefault(numeral, name)
    return out


# Paren-numeral pattern from finding's reference_form
_PAREN_NUMERAL_RE = re.compile(
    r"[（(]\s*(\d{1,4}[A-Za-z]{0,2})\s*[）)]"
)


def has_paren_numeral(reference_form: str) -> str | None:
    """Return the numeral string if reference contains a paren-numeral, else None."""
    if not reference_form:
        return None
    m = _PAREN_NUMERAL_RE.search(reference_form)
    return m.group(1) if m else None


def _strip_paren(text: str) -> str:
    return _PAREN_NUMERAL_RE.sub("", text or "").strip()


def main() -> int:
    descs = json.loads(DESCRIPTIONS.read_text())
    print(f"Loaded {len(descs)} cached descriptions")

    records = load_corpus("TW")
    print(f"TW corpus records: {len(records)}")
    findings_set = run_walker(records, "TW")
    print(f"Walker findings (TW): {len(findings_set)}")

    verdicts = load_sv2_verdicts()
    print(f"Verdicts available: {len(verdicts)}")

    # Pre-compute inline pairs per patent
    pairs_cache: dict[str, dict[str, str]] = {}
    for pid, rec in descs.items():
        text = (rec or {}).get("description") or ""
        pairs_cache[pid] = extract_inline_symbol_pairs(text)
    print(f"Patents with ≥1 numeral pair: "
          f"{sum(1 for p in pairs_cache.values() if p)}/{len(pairs_cache)}")

    # Restrict to supplement_v2 set
    sv2 = json.loads(
        (PROJECT_ROOT / "tests/eval/phase2b_results_supplement_v2.json").read_text()
    )
    sv2_pids = {v["patent_id"] for v in sv2["verdicts"] if v.get("jurisdiction") == "TW"}

    # Bucket each finding into one of:
    #  bare        — reference has no paren numeral
    #  paren_anchor_ok — reference has paren numeral AND it matches an ST entry
    #                   (numeral matches AND name shares ≥2 chars with term)
    #  paren_anchor_mismatch — reference has paren numeral but no matching ST entry
    by_bucket: dict[str, Counter] = defaultdict(Counter)

    for key in findings_set:
        pid, cid, term, ref = key
        if pid not in sv2_pids:
            continue
        if pid not in descs:
            continue
        verdict = verdicts.get(key, "unjudged")
        numeral = has_paren_numeral(ref or "")
        if numeral is None:
            by_bucket["bare"][verdict] += 1
            continue
        st_pairs = pairs_cache.get(pid, {})
        st_name = st_pairs.get(numeral)
        if not st_name:
            by_bucket["paren_no_st_entry"][verdict] += 1
            continue
        # Compare st_name to term — STRICT exact match after paren strip.
        # Looser matching (substring containment) caught a known legit
        # drafting error on 110P000631US c11 (`第一銜接部銜接(222)` vs
        # ST `222:銜接部` — drafter misplaced numeral after verb), so
        # we use exact equality only. Authoritative TIPO use of 符號說明
        # is "drafter wrote `該X(N)` and ST says `N: X`" — that's strict.
        term_no_paren = _strip_paren(term)
        st_name_no_paren = _strip_paren(st_name)
        # Strip optional reference-form prefix (該/所述/前述) when present
        # at start of term — walker emits raw extracted text.
        for prefix in ("該", "所述", "前述", "該等", "該些"):
            if term_no_paren.startswith(prefix):
                term_no_paren = term_no_paren[len(prefix):]
                break
        ok = (
            term_no_paren
            and st_name_no_paren
            and term_no_paren == st_name_no_paren
        )
        if ok:
            by_bucket["paren_anchor_ok"][verdict] += 1
        else:
            by_bucket["paren_anchor_name_mismatch"][verdict] += 1

    # Reporting
    print()
    print("Bucket × verdict distribution:")
    print(f"  {'bucket':30} {'legit':>7} {'walker_fp':>10} {'coverage':>9} {'mis_attr':>9} {'ambig':>7} {'unjudged':>9}  total")
    order = [
        "bare",
        "paren_no_st_entry",
        "paren_anchor_name_mismatch",
        "paren_anchor_ok",
    ]
    for b in order:
        c = by_bucket.get(b, Counter())
        legit = c.get("legit_drafting_error", 0)
        wfp = c.get("walker_fp", 0)
        cov = c.get("coverage_gap", 0)
        misa = c.get("diagnostic_mis_attribution", 0)
        ambig = c.get("ambig", 0)
        unj = c.get("unjudged", 0)
        tot = sum(c.values())
        print(f"  {b:30} {legit:>7} {wfp:>10} {cov:>9} {misa:>9} {ambig:>7} {unj:>9}  {tot}")

    print()
    print("Strict §112(b) precision per bucket (legit / legit+walker_fp):")
    for b in order:
        c = by_bucket.get(b, Counter())
        legit = c.get("legit_drafting_error", 0)
        wfp = c.get("walker_fp", 0)
        denom = legit + wfp
        if not denom:
            print(f"  {b:30} 0/0 (no labeled TP+FP)")
            continue
        prec = legit / denom * 100
        print(f"  {b:30} {legit}/{denom} = {prec:.1f}%")

    # Headline question: if we silence paren_anchor_ok findings,
    # how many walker_fps disappear vs how many legit defects we hide?
    pao = by_bucket.get("paren_anchor_ok", Counter())
    legit_silenced = pao.get("legit_drafting_error", 0)
    wfp_silenced = pao.get("walker_fp", 0)
    print()
    print("Authoritative-anchor silencer impact (paren_anchor_ok bucket):")
    print(f"  walker_fp silenced (GOOD): {wfp_silenced}")
    print(f"  legit silenced (BAD recall loss): {legit_silenced}")
    if wfp_silenced + legit_silenced:
        ratio = wfp_silenced / (wfp_silenced + legit_silenced) * 100
        print(f"  silencing precision: {ratio:.1f}% (>50% → net positive)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
