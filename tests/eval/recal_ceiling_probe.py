# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# recal_ceiling_probe.py - the recalibration-CEILING experiment (ADR-159).
#
# Question: could RE-WEIGHTING compute_confidence_score (free, no new data)
# reach the precision needed to demote FPs without dumping real defects? Fit an
# OPTIMAL logistic regression per jurisdiction on the signals available at
# walker emit-time over a claims-only corpus, 5-fold cross-validated, and read
# the precision/legit-retention ceiling. If even the optimal model ≈ base rate,
# the information is NOT in the available features → recalibration alone cannot
# work; new information (spec-presence at runtime, richer judged features) is
# required. (Empirically: US/TW/CN all ≈ base rate - see CONFIDENCE_LAYER_FINDINGS.md.)
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import round1_corpus_harness as h  # noqa: E402


def feats(f):
    t = f.get("term") or ""
    r = f.get("reference_form") or ""
    L = len(t)
    return [
        L, 1 if L <= 2 else 0, 1 if L >= 8 else 0, len(r),
        1 if f.get("suggested_match") else 0,
        1 if f.get("cross_ref") else 0,
        len(f.get("claim_text") or "") // 50,
    ]


def run(juris, fn):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_predict
    verd = h.load_ensemble_verdicts(juris)
    X, y = [], []
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
            c = verd.get(key)
            if c not in ("walker_fp", "legit_drafting_error"):
                continue
            X.append(feats(f))
            y.append(1 if c == "legit_drafting_error" else 0)
    X, y = np.array(X), np.array(y)
    clf = LogisticRegression(max_iter=1000)
    proba = cross_val_predict(clf, X, y, cv=5, method="predict_proba")[:, 1]
    print(f"\n== {juris} ==  n={len(y)} base_legit={y.mean():.3f}")
    print(f"{'keep_top%':>9} {'precision%':>10} {'legit_ret%':>10}")
    order = np.argsort(-proba)
    for frac in (0.05, 0.1, 0.2, 0.3, 0.5):
        idx = order[: int(len(y) * frac)]
        print(f"{frac * 100:>8.0f}% {y[idx].mean() * 100:>10.1f} {y[idx].sum() / y.sum() * 100:>10.1f}")


def main():
    from patentlint.analysis.claims import check_antecedent_basis as us_ab
    from patentlint.analysis.cn_claims import check_antecedent_basis_cn as cn_ab
    from patentlint.analysis.tw_claims import check_antecedent_basis as tw_ab
    for j, fn in (("US", us_ab), ("TW", tw_ab), ("CN", cn_ab)):
        run(j, fn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
