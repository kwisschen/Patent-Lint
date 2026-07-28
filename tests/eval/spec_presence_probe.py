# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# spec_presence_probe.py - does the spec/abstract-presence signal discriminate
# antecedent FPs from real defects? (ADR-159, the #1 confidence-layer hypothesis.)
#
# Uses the corpus `abstract` as a (weaker) proxy for the dormant `term_in_spec`
# signal: for each judged finding, is the term present in the abstract? Measures
# P(legit | in) vs P(legit | out) and the demote-if-in trade. FINDING: the
# signal does NOT transfer across jurisdictions - mildly right-direction on US,
# COUNTERPRODUCTIVE on TW/CN. See CONFIDENCE_LAYER_FINDINGS.md.
from __future__ import annotations

import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import round1_corpus_harness as h  # noqa: E402


def run(juris, fn):
    verd = h.load_ensemble_verdicts(juris)
    cnt = {}
    for rec in h.load_corpus(juris):
        ab = (rec.get("abstract") or "").lower()
        if not ab:
            continue
        ab_ns = ab.replace(" ", "")
        doc = h._build_doc(rec, juris)
        if doc is None:
            continue
        try:
            res = fn(doc)
        except Exception:
            continue
        for f in res:
            if not isinstance(f, dict) or f.get("category") == "tw_contamination":
                continue
            c = verd.get((rec["patent_id"], f.get("claim_id"), f.get("term"), f.get("reference_form")))
            if c not in ("walker_fp", "legit_drafting_error"):
                continue
            t = (f.get("term") or "").lower()
            if not t:
                continue
            ins = (t in ab) or (t.replace(" ", "") in ab_ns)
            cnt[(ins, c)] = cnt.get((ins, c), 0) + 1

    def p_legit(b):
        legit = cnt.get((b, "legit_drafting_error"), 0)
        wfp = cnt.get((b, "walker_fp"), 0)
        tot = legit + wfp
        return tot, (legit / tot if tot else 0)

    n_in, p_in = p_legit(True)
    n_out, p_out = p_legit(False)
    base_l = sum(cnt.get((b, "legit_drafting_error"), 0) for b in (True, False))
    base_t = sum(cnt.values())
    wfp_in = cnt.get((True, "walker_fp"), 0)
    wfp = sum(cnt.get((b, "walker_fp"), 0) for b in (True, False))
    lg_in = cnt.get((True, "legit_drafting_error"), 0)
    print(f"\n== {juris} ==  judged w/ abstract: {base_t}  base_legit={base_l / base_t:.3f}")
    print(f"  term IN abstract    : n={n_in:5} P(legit)={p_in:.3f}")
    print(f"  term NOT in abstract: n={n_out:5} P(legit)={p_out:.3f}")
    if wfp and base_l:
        print(f"  DEMOTE-if-in-abstract: removes {100 * wfp_in / wfp:.1f}% of walker_fp, "
              f"costs {100 * lg_in / base_l:.1f}% of legit")


def main():
    from patentlint.analysis.claims import check_antecedent_basis as us_ab
    from patentlint.analysis.cn_claims import check_antecedent_basis_cn as cn_ab
    from patentlint.analysis.tw_claims import check_antecedent_basis as tw_ab
    for j, fn in (("US", us_ab), ("TW", tw_ab), ("CN", cn_ab)):
        run(j, fn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
