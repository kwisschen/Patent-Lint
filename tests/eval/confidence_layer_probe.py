# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# confidence_layer_probe.py - measure the confidence-display-layer lever
# (ADR-159 portfolio, the FN-free path to high user-visible precision).
#
# For each jurisdiction: run the production walker over the corpus, capture
# `confidence_score` per finding, join to the ensemble gold verdict, and
# compute, over a threshold sweep, the "confident bucket" (score >= T):
#   bucket_precision = real_defects / (real_defects + walker_fp)   [in bucket]
#   legit_retention  = legit_in_bucket / total_legit               [recall]
# Demotion is FN-FREE: a demoted finding is still SHOWN (advisory), not deleted.
from __future__ import annotations

import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import round1_corpus_harness as h  # noqa: E402


def collect(juris):
    from patentlint.analysis.claims import check_antecedent_basis as us_ab
    from patentlint.analysis.cn_claims import check_antecedent_basis_cn
    from patentlint.analysis.tw_claims import check_antecedent_basis as tw_ab
    fn = {"CN": check_antecedent_basis_cn, "TW": tw_ab, "US": us_ab}[juris]
    verd = h.load_ensemble_verdicts(juris)
    rows = []  # (score, category)
    for rec in h.load_corpus(juris):
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
            key = (rec["patent_id"], f.get("claim_id"), f.get("term"), f.get("reference_form"))
            cat = verd.get(key, "unjudged")
            sc = f.get("confidence_score")
            if sc is None:
                continue
            rows.append((sc, cat))
    return rows


def analyze(juris, rows):
    judged = [(s, c) for s, c in rows if c in ("walker_fp", "legit_drafting_error", "coverage_gap")]
    total = len(judged)
    wfp = sum(1 for s, c in judged if c == "walker_fp")
    legit = sum(1 for s, c in judged if c == "legit_drafting_error")
    cov = sum(1 for s, c in judged if c == "coverage_gap")
    print(f"\n===== {juris} =====")
    print(f"judged findings: {total} (walker_fp={wfp}  legit={legit}  coverage_gap={cov})"
          f"  | unjudged emitted: {len(rows) - total}")
    if total == 0:
        return
    print(f"baseline confident-everything precision (legit+cov / all judged): "
          f"{100 * (legit + cov) / total:.1f}%")
    print(f"{'T':>4} {'bucket_n':>8} {'bkt_prec%':>9} {'legit_ret%':>10} {'wfp_demoted%':>12}")
    for thr in (30, 40, 45, 50, 55, 60, 65, 70, 75, 80):
        bn = sum(1 for s, c in judged if s >= thr)
        b_legit = sum(1 for s, c in judged if s >= thr and c == "legit_drafting_error")
        b_cov = sum(1 for s, c in judged if s >= thr and c == "coverage_gap")
        b_wfp = sum(1 for s, c in judged if s >= thr and c == "walker_fp")
        prec = 100 * (b_legit + b_cov) / bn if bn else 0
        ret = 100 * b_legit / legit if legit else 0
        demoted = 100 * (wfp - b_wfp) / wfp if wfp else 0
        print(f"{thr:>4} {bn:>8} {prec:>9.1f} {ret:>10.1f} {demoted:>12.1f}")


def main():
    for j in ("US", "TW", "CN"):
        analyze(j, collect(j))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
