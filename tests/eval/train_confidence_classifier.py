# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Path 5 ML — train classifier to identify discriminating walker signals.

Trains a sklearn DecisionTreeClassifier on the Phase 1 supplement_v2
verdicts to identify which emit-time features best discriminate legit
drafting errors from walker FPs. Outputs:

1. Feature importances (which signals matter)
2. Top decision-tree splits (which thresholds matter)
3. A recommendation block for `compute_confidence_score` updates

CRITICAL — NEVER deploy the trained model at runtime. PatentLint's
trust promise is "No upload / No cloud processing / No AI" — any
ML inference at runtime would violate it. This script is OFFLINE
TOOLING only. Output is human-reviewed walker code patches that
encode learned thresholds as deterministic emit-time signals.

Usage:
    python -m tests.eval.train_confidence_classifier
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

PATENTLINT_ROOT = Path("/Users/chrischen/Documents/Projects/Patent-Lint")
sys.path.insert(0, str(PATENTLINT_ROOT / "src"))
sys.path.insert(0, str(PATENTLINT_ROOT))

from sklearn.tree import DecisionTreeClassifier, export_text  # noqa: E402
from sklearn.ensemble import GradientBoostingClassifier  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.metrics import classification_report  # noqa: E402

from tests.eval.phase2b_judging import (  # noqa: E402
    CORPUS_PARQUET_DIR,
    load_corpus_records,
    run_walker_on_draft,
)


def _extract_features(iss: dict, juris: str) -> dict:
    """Compute deterministic features from walker finding state."""
    diag = iss.get("diagnostics") or {}
    sm = iss.get("suggested_match") or {}
    term = iss.get("term", "") or ""
    ref_form = iss.get("reference_form", "") or ""

    return {
        "term_len": len(term),
        "ref_len": len(ref_form),
        "intros_pool_size": diag.get("intros_pool_size", 0),
        "has_suggested_match": int(diag.get("has_suggested_match", False)),
        "suggested_cross_branch": int(diag.get("suggested_cross_branch", False)),
        "suggested_same_claim": int(
            bool(sm and sm.get("claim_id") == iss.get("claim_id"))
        ),
        "has_paren_num": int(bool(re.search(r'\(\d+\)|（\d+）', term))),
        "has_paren_any": int("(" in term or "（" in term),
        "has_cjk": int(any('一' <= c <= '鿿' for c in term)),
        "has_latin": int(any('A' <= c <= 'z' for c in term)),
        "has_latin_upper_short": int(
            len(term) <= 3
            and term.isascii()
            and term.replace(' ', '').isalpha()
            and term.isupper()
        ),
        "very_short": int(0 < len(term) <= 2),
        "long_term": int(len(term) >= 8),
        "has_ordinal_zh": int(bool(re.match(r'^第[一二三四五六七八九十百0-9]+', term))),
        "term_in_spec": int(iss.get("term_in_spec", False)),
        "is_us": int(juris == "US"),
        "is_cn": int(juris == "CN"),
        "is_tw": int(juris == "TW"),
        "current_score": int(iss.get("confidence_score", 50)),
    }


def main() -> int:
    print("Loading verdicts ...")
    data = json.loads(
        (PATENTLINT_ROOT / "tests/eval/phase2b_results_supplement_v2.json").read_text()
    )
    verdict_drafts = data["verdicts"]

    print("Loading corpus ...")
    records = load_corpus_records(CORPUS_PARQUET_DIR)
    rec_by_pid = {r["patent_id"]: r for r in records}

    print("Re-running walker for fresh per-finding metadata ...")
    walker_by_pid: dict[str, list[dict]] = {}
    for vd in verdict_drafts:
        pid = vd["patent_id"]
        rec = rec_by_pid.get(pid)
        if not rec:
            continue
        try:
            issues, _ = run_walker_on_draft(rec)
            walker_by_pid[pid] = issues
        except Exception as exc:
            print(f"  walker error on {pid}: {exc!r}", file=sys.stderr)

    # Build feature matrix + labels
    X_rows: list[dict] = []
    y_rows: list[int] = []
    for vd in verdict_drafts:
        pid = vd["patent_id"]
        juris = vd.get("jurisdiction", "")
        if pid not in walker_by_pid:
            continue
        by_key = {}
        for iss in walker_by_pid[pid]:
            k = (iss["claim_id"], iss["term"])
            if k not in by_key:
                by_key[k] = iss
        for fv in vd["ensemble"].get("final_verdicts", []):
            cat = fv.get("category")
            if cat not in ("walker_fp", "legit_drafting_error"):
                continue
            iss = by_key.get((fv["claim_id"], fv["term"]))
            if iss is None:
                continue
            X_rows.append(_extract_features(iss, juris))
            y_rows.append(1 if cat == "legit_drafting_error" else 0)

    feat_names = list(X_rows[0].keys())
    X = np.array([[row[f] for f in feat_names] for row in X_rows])
    y = np.array(y_rows)
    print(f"\nDataset: {X.shape[0]} samples ({sum(y)} legit / {len(y)-sum(y)} wfp)")
    print(f"Features ({len(feat_names)}): {feat_names}")

    # Train / val split
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    # 1. Decision tree (interpretable splits)
    print("\n=== Decision Tree (depth 5) ===")
    dt = DecisionTreeClassifier(max_depth=5, min_samples_leaf=50, random_state=42)
    dt.fit(X_tr, y_tr)
    y_pred = dt.predict(X_te)
    print(classification_report(y_te, y_pred, target_names=["wfp", "legit"]))
    print("Feature importances:")
    for f, imp in sorted(zip(feat_names, dt.feature_importances_), key=lambda x: -x[1])[:8]:
        print(f"  {f:<25}: {imp:.3f}")
    print("\nTree rules (first 40 lines):")
    rules = export_text(dt, feature_names=feat_names)
    for ln in rules.split('\n')[:40]:
        print(f"  {ln}")

    # 2. Gradient boosting (probability output for tier calibration)
    print("\n=== Gradient Boosting (depth 4, 100 estimators) ===")
    gb = GradientBoostingClassifier(max_depth=4, n_estimators=100, random_state=42)
    gb.fit(X_tr, y_tr)
    y_proba = gb.predict_proba(X_te)[:, 1]
    print("Bucket precision by predicted-probability threshold:")
    for thr in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        mask = y_proba >= thr
        if mask.sum() < 5:
            continue
        bucket_precision = y_te[mask].mean()
        bucket_size = mask.sum()
        print(f"  thr={thr:.1f}: bucket_size={bucket_size:4d}, "
              f"precision={bucket_precision:.3f} ({100*bucket_size/len(y_te):.0f}% of test)")
    print("Feature importances:")
    for f, imp in sorted(zip(feat_names, gb.feature_importances_), key=lambda x: -x[1])[:8]:
        print(f"  {f:<25}: {imp:.3f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
