# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""TW-specific ML retrain with R61c features (2026-05-05).

Earlier attempt found zero generalizable paths on TW under strict CV
(train+test ≥50% precision, n≥50 in both). Re-running with new features:

  - term_in_description (Path 1: True 13.2% / False 0.8% legit)
  - term_in_inline_symbol_table (Path 1: True 9.7% / False 13.1%)
  - tipo_authoritative_anchor (R61c: 100% wfp on True)
  - paren_anchor_name_mismatch + paren_no_st_entry buckets

Trains DecisionTree + GradientBoosting on TW supplement_v2 verdicts,
splits by patent_id (no in-draft leakage), reports any leaves with
≥50% precision in BOTH train and test (the strict CV gate that earlier
filtered ZERO paths for TW).

Output is HUMAN-REVIEWED. ML never ships at runtime — distilled paths
are encoded as deterministic Python in compute_confidence_score.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

PATENTLINT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PATENTLINT_ROOT / "src"))
sys.path.insert(0, str(PATENTLINT_ROOT))

from sklearn.ensemble import GradientBoostingClassifier  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.tree import DecisionTreeClassifier, export_text  # noqa: E402

from tests.eval.measure_term_in_desc import (  # noqa: E402
    extract_inline_symbol_table_names,
    load_sv2_verdicts,
)
from tests.eval.measure_tipo_anchor import (  # noqa: E402
    extract_inline_symbol_pairs,
    has_paren_numeral,
)
from tests.eval.round1_corpus_harness import load_corpus  # noqa: E402

DESCRIPTIONS = PATENTLINT_ROOT / "tests/eval/tw_descriptions.json"


def _strip_paren(text: str) -> str:
    return re.sub(r"[（(]\s*\d{1,4}[A-Za-z]{0,2}\s*[）)]", "", text or "").strip()


def _extract_features(iss: dict, st_pairs: dict[str, str], st_names: set[str], desc: str) -> dict:
    """Compute features for one finding using corpus-fetched signals."""
    diag = iss.get("diagnostics") or {}
    sm = iss.get("suggested_match") or {}
    term = iss.get("term", "") or ""
    ref_form = iss.get("reference_form", "") or ""

    # Anchor classification
    numeral = has_paren_numeral(ref_form)
    anchor_class = 0  # bare
    if numeral:
        st_name = st_pairs.get(numeral)
        if not st_name:
            anchor_class = 1  # paren_no_st_entry
        else:
            tnp = _strip_paren(term)
            for prefix in ("該", "所述", "前述", "該等", "該些"):
                if tnp.startswith(prefix):
                    tnp = tnp[len(prefix):]
                    break
            snp = _strip_paren(st_name)
            anchor_class = 3 if tnp == snp else 2  # 3=ok, 2=mismatch

    return {
        "term_len": len(term),
        "ref_len": len(ref_form),
        "intros_pool_size": diag.get("intros_pool_size", 0),
        "has_suggested_match": int(diag.get("has_suggested_match", False)),
        "suggested_cross_branch": int(diag.get("suggested_cross_branch", False)),
        "suggested_same_claim": int(
            bool(sm and sm.get("claim_id") == iss.get("claim_id"))
        ),
        "has_paren_num": int(bool(re.search(r"\(\d+\)|（\d+）", term))),
        "has_paren_any": int("(" in term or "（" in term),
        "has_cjk": int(any("一" <= c <= "鿿" for c in term)),
        "has_latin": int(any("A" <= c <= "z" for c in term)),
        "has_latin_upper_short": int(
            len(term) <= 3 and term.isascii() and term.replace(" ", "").isalpha() and term.isupper()
        ),
        "very_short": int(0 < len(term) <= 2),
        "long_term": int(len(term) >= 8),
        "very_long": int(len(term) >= 12),
        "has_ordinal_zh": int(bool(re.match(r"^第[一二三四五六七八九十百0-9]+", term))),
        # NEW corpus-fetched features
        "term_in_description": int(bool(term) and term in desc),
        "term_in_inline_st_name": int(bool(term) and term in st_names),
        "anchor_class": anchor_class,  # 0 bare, 1 no_st, 2 mismatch, 3 ok
        "is_anchor_ok": int(anchor_class == 3),
        "is_anchor_mismatch": int(anchor_class == 2),
        "is_quoted_reference_format": int(diag.get("is_quoted_reference_format", False)),
    }


def main() -> int:
    print("Loading verdicts ...")
    verdicts = load_sv2_verdicts()
    print(f"  TW supplement_v2 verdicts: {len(verdicts)}")

    descs = json.loads(DESCRIPTIONS.read_text())
    print(f"  cached descriptions: {len(descs)}")

    print("Loading corpus + running walker ...")
    from patentlint.analysis.tw_claims import check_antecedent_basis
    from patentlint.models import SymbolEntry, TwPatentDocument
    from patentlint.parser.claims_tw import parse_tw_claims

    records = load_corpus("TW")
    sv2 = json.loads(
        (PATENTLINT_ROOT / "tests/eval/phase2b_results_supplement_v2.json").read_text()
    )
    sv2_pids = {v["patent_id"] for v in sv2["verdicts"] if v.get("jurisdiction") == "TW"}

    X_rows: list[dict] = []
    y_rows: list[int] = []
    pid_rows: list[str] = []  # for grouped CV split

    for rec in records:
        pid = rec.get("patent_id")
        if pid not in sv2_pids or pid not in descs:
            continue
        claims_text = rec.get("claims") or []
        if not claims_text:
            continue
        paragraphs = [f"{i+1}. {c}" for i, c in enumerate(claims_text)]
        parsed = parse_tw_claims(paragraphs)
        if not parsed:
            continue

        desc = (descs.get(pid) or {}).get("description") or ""
        st_pairs = extract_inline_symbol_pairs(desc)
        st_names = extract_inline_symbol_table_names(desc)
        st_entries = [SymbolEntry(numeral=n, name=v) for n, v in st_pairs.items()]
        doc = TwPatentDocument(
            claims=parsed,
            symbol_table=st_entries,
            input_format="google_patents_html",
        )
        try:
            results = check_antecedent_basis(doc)
        except Exception:
            continue
        for f in results:
            if f.get("category") == "tw_contamination":
                continue
            key = (pid, f.get("claim_id"), f.get("term"), f.get("reference_form"))
            verdict = verdicts.get(key)
            if verdict not in ("walker_fp", "legit_drafting_error"):
                continue
            X_rows.append(_extract_features(f, st_pairs, st_names, desc))
            y_rows.append(1 if verdict == "legit_drafting_error" else 0)
            pid_rows.append(pid)

    if not X_rows:
        print("No labeled features extracted — abort.")
        return 1

    feat_names = list(X_rows[0].keys())
    X = np.array([[row[f] for f in feat_names] for row in X_rows])
    y = np.array(y_rows)
    print(f"\nDataset: {X.shape[0]} samples ({sum(y)} legit / {len(y)-sum(y)} wfp)")
    print(f"Features ({len(feat_names)}): {feat_names}")

    # Strict CV: split BY patent_id to prevent same-draft leakage
    unique_pids = sorted(set(pid_rows))
    train_pids, test_pids = train_test_split(unique_pids, test_size=0.30, random_state=42)
    train_pids_set = set(train_pids)
    train_mask = np.array([p in train_pids_set for p in pid_rows])
    X_tr, X_te = X[train_mask], X[~train_mask]
    y_tr, y_te = y[train_mask], y[~train_mask]
    print(f"\nTrain: {X_tr.shape[0]} samples on {len(train_pids)} patents "
          f"({sum(y_tr)} legit / {len(y_tr)-sum(y_tr)} wfp)")
    print(f"Test:  {X_te.shape[0]} samples on {len(test_pids)} patents "
          f"({sum(y_te)} legit / {len(y_te)-sum(y_te)} wfp)")

    # Decision Tree
    print("\n=== DecisionTree depth 6, min_leaf 30 ===")
    dt = DecisionTreeClassifier(max_depth=6, min_samples_leaf=30, random_state=42)
    dt.fit(X_tr, y_tr)
    print(f"Train accuracy: {dt.score(X_tr, y_tr):.3f}")
    print(f"Test accuracy:  {dt.score(X_te, y_te):.3f}")
    print("\nFeature importances:")
    for f, imp in sorted(zip(feat_names, dt.feature_importances_), key=lambda x: -x[1])[:10]:
        print(f"  {f:<28}: {imp:.3f}")

    # Per-leaf precision analysis with strict CV gate
    print("\n--- Per-leaf strict CV (train≥50% AND test≥50% AND n≥30 in both) ---")
    train_leaves = dt.apply(X_tr)
    test_leaves = dt.apply(X_te)
    keep_paths = []
    for leaf_id in sorted(set(train_leaves)):
        train_mask_l = train_leaves == leaf_id
        test_mask_l = test_leaves == leaf_id
        n_tr = train_mask_l.sum()
        n_te = test_mask_l.sum()
        if n_tr < 30 or n_te < 30:
            continue
        prec_tr = y_tr[train_mask_l].mean()
        prec_te = y_te[test_mask_l].mean()
        if prec_tr >= 0.50 and prec_te >= 0.50:
            keep_paths.append((leaf_id, n_tr, prec_tr, n_te, prec_te))
            print(f"  leaf {leaf_id}: train n={n_tr} prec={prec_tr:.3f} | test n={n_te} prec={prec_te:.3f}")
    if not keep_paths:
        print("  (no paths satisfy strict CV)")

    # Bucket-precision report at multiple thresholds
    print("\n=== GradientBoosting depth 4, 200 estimators ===")
    gb = GradientBoostingClassifier(max_depth=4, n_estimators=200, random_state=42)
    gb.fit(X_tr, y_tr)
    y_proba = gb.predict_proba(X_te)[:, 1]
    print("Bucket precision by predicted-prob threshold (test set):")
    for thr in [0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80]:
        mask = y_proba >= thr
        if mask.sum() < 5:
            print(f"  thr={thr:.2f}: bucket_size={mask.sum():4d} (skipped — too small)")
            continue
        bp = y_te[mask].mean()
        print(f"  thr={thr:.2f}: bucket_size={mask.sum():4d}  precision={bp:.3f} "
              f"({100*mask.sum()/len(y_te):.1f}% of test)")
    print("\nFeature importances (GB):")
    for f, imp in sorted(zip(feat_names, gb.feature_importances_), key=lambda x: -x[1])[:10]:
        print(f"  {f:<28}: {imp:.3f}")

    # Render decision tree text
    print("\n--- Full decision tree text ---")
    rules = export_text(dt, feature_names=feat_names, max_depth=6)
    print(rules)

    return 0


if __name__ == "__main__":
    sys.exit(main())
