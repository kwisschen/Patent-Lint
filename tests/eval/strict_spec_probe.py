# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# strict_spec_probe.py — the "most FPs?" experiment (ADR-159 Path-to-80).
#
# WS-E1 proved BOOLEAN term-in-spec is dead on US (100% of claim terms appear
# somewhere in the 225k-char spec → no signal). This tests the STRICTER,
# untested hypothesis: a benign antecedent reference is one whose element is
# *properly defined* in the specification — introduced with an indefinite
# article AND/OR bound to a reference numeral (the patent-drafting marker of a
# real, defined element). A genuine §112 defect is an element undefined
# EVERYWHERE. If the strict signal separates them, demoting findings whose
# element is strictly-defined-in-spec is a free, deterministic, AI-free lever
# that could end MOST FPs (not a few %).
#
# Signals tested (deterministic, runtime-derivable from claim + spec):
#   refnum_spec   : head noun H appears in spec bound to a reference numeral
#                   (`... H 120` / `... H (120)`)
#   article_spec  : H is introduced in spec with an article (`a/an ... H`)
#   strict        : article_spec AND refnum_spec  (properly-defined element)
#
# For each: P(legit | signal) vs base, and the DEMOTE-if-signal trade
# (% walker_fp removed / % legit lost). A usable lever needs the signal present
# on MOST walker_fp while costing little legit.
#
#   python3 tests/eval/strict_spec_probe.py [US]
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import round1_corpus_harness as h  # noqa: E402


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _head(term: str) -> str:
    t = re.sub(r"^(the|said|a|an|each|one|first|second|third|fourth|fifth)\s+", "", term)
    words = t.split()
    return words[-1] if words else t


def run(juris="US"):
    descs = json.loads((THIS / f"{juris.lower()}_descriptions.json").read_text())
    verd = h.load_ensemble_verdicts(juris)
    from patentlint.analysis.claims import check_antecedent_basis as us_ab

    SIGNALS = ("refnum_spec", "article_spec", "strict", "fullterm_refnum")
    # cnt[signal][(present, category)] = count
    cnt = {s: {} for s in SIGNALS}
    judged = 0
    for rec in h.load_corpus(juris):
        pid = rec["patent_id"]
        spec = _norm((descs.get(pid) or {}).get("description") or "")
        if not spec:
            continue
        doc = h._build_doc(rec, juris)
        if doc is None:
            continue
        try:
            res = us_ab(doc)
        except Exception:
            continue
        for f in res:
            if not isinstance(f, dict) or f.get("category") == "tw_contamination":
                continue
            c = verd.get((pid, f.get("claim_id"), f.get("term"), f.get("reference_form")))
            if c not in ("walker_fp", "legit_drafting_error"):
                continue
            term = _norm(f.get("term") or "")
            if not term:
                continue
            head = _head(term)
            he = re.escape(head)
            te = re.escape(term)
            judged += 1
            sig = {}
            # H bound to a reference numeral anywhere in spec: "... H 120" / "H (120)"
            sig["refnum_spec"] = bool(re.search(rf"\b{he}\s*\(?\d{{1,4}}\)?(?!\d)", spec))
            # H introduced with an article in spec: "a/an [up to 3 words] H"
            sig["article_spec"] = bool(re.search(rf"\b(?:a|an)\s+(?:\w+\s+){{0,3}}{he}\b", spec))
            sig["strict"] = sig["refnum_spec"] and sig["article_spec"]
            # full multiword term bound to a reference numeral (stricter identity)
            sig["fullterm_refnum"] = bool(re.search(rf"\b{te}\s*\(?\d{{1,4}}\)?(?!\d)", spec))
            for s in SIGNALS:
                key = (sig[s], c)
                cnt[s][key] = cnt[s].get(key, 0) + 1

    print(f"\n== {juris} STRICT spec-presence signals ==  judged findings (wfp|legit): {judged}")
    base_l = sum(v for (p, c), v in cnt["strict"].items() if c == "legit_drafting_error")
    base_w = sum(v for (p, c), v in cnt["strict"].items() if c == "walker_fp")
    base_t = base_l + base_w
    if not base_t:
        print("  no judged findings with spec.")
        return
    print(f"  base P(legit) = {base_l}/{base_t} = {base_l / base_t:.3f}  (walker_fp={base_w})")
    print(f"\n  {'signal':>16} {'present%':>9} {'P(legit|y)':>11} {'P(legit|n)':>11} "
          f"{'wfp_removed%':>13} {'legit_lost%':>12}")
    for s in SIGNALS:
        ly = cnt[s].get((True, "legit_drafting_error"), 0)
        wy = cnt[s].get((True, "walker_fp"), 0)
        ln = cnt[s].get((False, "legit_drafting_error"), 0)
        wn = cnt[s].get((False, "walker_fp"), 0)
        ny, nn = ly + wy, ln + wn
        present = ny / max(1, ny + nn)
        py = ly / ny if ny else 0.0
        pn = ln / nn if nn else 0.0
        wfp_removed = wy / max(1, base_w)   # demote-if-present: removes these wfp
        legit_lost = ly / max(1, base_l)    # ... at this legit cost
        print(f"  {s:>16} {present * 100:>8.1f}% {py:>11.3f} {pn:>11.3f} "
              f"{wfp_removed * 100:>12.1f}% {legit_lost * 100:>11.1f}%")
    print("\n  reading: a usable DEMOTE lever needs high wfp_removed% with low legit_lost%")
    print("  (and P(legit|present) well below base). If present% ~100%, the signal is")
    print("  saturated/dead like boolean term_in_spec.")


def main():
    for j in sys.argv[1:] or ["US"]:
        run(j)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
