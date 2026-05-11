# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Measure term_in_description signal direction on TW supplement_v2 corpus.

Path 1 of TIPO-style hybrid measurement (2026-05-05). Joins:
  1. fetch_tw_descriptions output (patent_id → description text)
  2. supplement_v2 ensemble verdicts (per-finding category)
  3. walker run on the corpus (re-run via round1_corpus_harness)

For each TW walker finding, computes three signals:
  - term_in_description: bool — does the normalized term appear in the
    fetched description body? (broad)
  - term_in_inline_symbol_table: bool — does the term appear as the
    name half of an inline `<numeral>：<name>` symbol-table-style
    pattern in the description? (narrow proxy for 符號說明 entries)
  - term_in_symbol_table_section: bool — appears in an explicitly
    extracted 符號說明 section (rare — Google Patents flattens)

Then groups by ensemble category (walker_fp / legit / ...) and reports:
  - precision-by-presence rate per signal
  - implied bucket precision lift if we use the signal as a
    confidence boost (push in_X findings to higher bucket)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Inline symbol-table pattern: <numeral><sep><name>
# Numerals: 1-4 digit groups optionally suffixed by 1-2 letters (100, 100a)
# Separators: ASCII colon, full-width colon, comma, em-dash, en-dash, dot
_INLINE_ST_RE = re.compile(
    r"\b(\d{1,4}[A-Za-z]{0,2})\s*[：:．、,，\-—–]\s*"
    r"([一-鿿][一-鿿A-Za-z0-9（）\(\)]{1,15})"
)


def extract_inline_symbol_table_names(text: str) -> set[str]:
    """Mine inline `<numeral>：<name>` patterns from flattened description.

    TIPO drafters often write symbol tables as a comma-separated inline
    list when the docx structure is preserved, but Google Patents
    flattens it. We can recover most entries by greedy regex match on
    the `<digit-group>：<short-CJK-noun>` shape. Numerals must be 1-4
    digits ± letter suffix (matches 100, 100a, 1000A).
    """
    names: set[str] = set()
    for m in _INLINE_ST_RE.finditer(text):
        name = m.group(2).strip()
        if 2 <= len(name) <= 16:
            names.add(name)
    return names

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tests.eval.round1_corpus_harness import (  # noqa: E402
    load_corpus,
    run_walker,
)

DESCRIPTIONS = PROJECT_ROOT / "tests/eval/tw_descriptions.json"


def load_sv2_verdicts() -> dict[tuple, str]:
    """Load supplement_v2 verdicts directly (round1 harness loads other files)."""
    sv2 = json.loads(
        (PROJECT_ROOT / "tests/eval/phase2b_results_supplement_v2.json").read_text()
    )
    out: dict[tuple, str] = {}
    for v in sv2.get("verdicts", []):
        if v.get("jurisdiction") != "TW":
            continue
        ens = v.get("ensemble") or {}
        findings = ens.get("findings") or []
        final_verdicts = ens.get("final_verdicts") or []
        for idx, f in enumerate(findings):
            ver = final_verdicts[idx] if idx < len(final_verdicts) else None
            if not ver:
                continue
            key = (v["patent_id"], f.get("claim_id"), f.get("term"), f.get("reference_form"))
            out[key] = ver.get("category", "unjudged")
    return out


def main() -> int:
    descs = json.loads(DESCRIPTIONS.read_text())
    print(f"Loaded {len(descs)} cached descriptions")

    # Load corpus + walker findings
    records = load_corpus("TW")
    print(f"TW corpus records: {len(records)}")
    findings_set = run_walker(records, "TW")
    print(f"Walker findings (TW): {len(findings_set)}")

    # Load ensemble verdicts — supplement_v2 specifically (the 250-patent set)
    verdicts = load_sv2_verdicts()
    print(f"Verdicts available (supplement_v2): {len(verdicts)}")

    # Restrict to supplement_v2 patent IDs (those we have descriptions for)
    sv2 = json.loads(
        (PROJECT_ROOT / "tests/eval/phase2b_results_supplement_v2.json").read_text()
    )
    sv2_pids = {v["patent_id"] for v in sv2["verdicts"] if v.get("jurisdiction") == "TW"}
    print(f"supplement_v2 TW patent IDs: {len(sv2_pids)}")

    # Pre-compute inline symbol-table names per patent (cache)
    inline_st_cache: dict[str, set[str]] = {}
    for pid, rec in descs.items():
        text = (rec or {}).get("description") or ""
        if text:
            inline_st_cache[pid] = extract_inline_symbol_table_names(text)
    n_with_inline_st = sum(1 for s in inline_st_cache.values() if s)
    avg_st_size = (
        sum(len(s) for s in inline_st_cache.values()) / max(n_with_inline_st, 1)
    )
    print("\nInline symbol-table mining:")
    print(f"  patents with ≥1 mined inline-ST entry: {n_with_inline_st}/{len(descs)}")
    print(f"  avg ST size (where present): {avg_st_size:.1f}")

    # For each finding in supplement_v2 set, compute three signals.
    in_desc_by_cat: dict[bool, Counter] = defaultdict(Counter)
    in_inline_st_by_cat: dict[bool, Counter] = defaultdict(Counter)
    in_section_st_by_cat: dict[bool, Counter] = defaultdict(Counter)
    for key in findings_set:
        pid, cid, term, ref = key
        if pid not in sv2_pids:
            continue
        if pid not in descs:
            continue
        desc_text = (descs[pid] or {}).get("description") or ""
        if not desc_text:
            continue
        section_st = (descs[pid] or {}).get("symbol_table_text") or ""
        in_desc = bool(term) and term in desc_text
        in_inline_st = bool(term) and term in inline_st_cache.get(pid, set())
        in_section_st = bool(term) and bool(section_st) and term in section_st
        verdict = verdicts.get(key, "unjudged")
        in_desc_by_cat[in_desc][verdict] += 1
        in_inline_st_by_cat[in_inline_st][verdict] += 1
        in_section_st_by_cat[in_section_st][verdict] += 1

    # Compute precision-by-presence:
    # legit_drafting_error = TP, walker_fp = FP, others ignored for strict precision
    print()
    print("Distribution by term_in_description × verdict:")
    print(f"  {'in_desc':9} {'legit':>8} {'walker_fp':>10} {'coverage':>9} {'mis_attr':>9} {'ambig':>7} {'unjudged':>9}  total")
    for in_desc in (True, False):
        c = in_desc_by_cat[in_desc]
        legit = c.get("legit_drafting_error", 0)
        wfp = c.get("walker_fp", 0)
        cov = c.get("coverage_gap", 0)
        misa = c.get("diagnostic_mis_attribution", 0)
        ambig = c.get("ambig", 0)
        unj = c.get("unjudged", 0)
        tot = sum(c.values())
        print(f"  {str(in_desc):9} {legit:>8} {wfp:>10} {cov:>9} {misa:>9} {ambig:>7} {unj:>9}  {tot}")

    # Strict precision (legit / (legit + walker_fp)) by group, per signal
    def _print_strict_precision(label: str, by_cat: dict[bool, Counter]) -> None:
        print()
        print(f"Strict §112(b) precision by {label} (legit / legit+walker_fp):")
        all_legit = 0
        all_wfp = 0
        for v in (True, False):
            c = by_cat[v]
            legit = c.get("legit_drafting_error", 0)
            wfp = c.get("walker_fp", 0)
            all_legit += legit
            all_wfp += wfp
            denom = legit + wfp
            n_judged = sum(c.get(k, 0) for k in (
                "legit_drafting_error", "walker_fp", "coverage_gap",
                "ambig", "diagnostic_mis_attribution",
            ))
            if denom == 0:
                print(f"  {label}={v}: 0/0 (no labeled TP+FP, n={n_judged} judged)")
                continue
            prec = legit / denom * 100
            print(f"  {label}={v}: {legit}/{denom} = {prec:.1f}%  (n={n_judged} judged)")
        if all_legit + all_wfp:
            baseline = all_legit / (all_legit + all_wfp) * 100
            print(f"  baseline (combined): {all_legit}/{all_legit+all_wfp} = {baseline:.1f}%")

    _print_strict_precision("term_in_description", in_desc_by_cat)
    _print_strict_precision("term_in_inline_symbol_table", in_inline_st_by_cat)
    _print_strict_precision("term_in_section_symbol_table", in_section_st_by_cat)

    return 0


if __name__ == "__main__":
    sys.exit(main())
