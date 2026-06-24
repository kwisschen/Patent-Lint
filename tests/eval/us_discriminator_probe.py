# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# us_discriminator_probe.py — WS-A4 (ADR-159 Path-to-80). The decisive FREE
# experiment for the confidence DISCRIMINATOR: can ANY deterministic,
# runtime-available feature set separate a benign antecedent reference from a
# REAL §112 defect, using AUTHORITATIVE examiner labels (not the LLM gold)?
#
# Why this matters: PatentLint runtime is AI-free (ADR-158 — LLM at dev-time,
# distilled to deterministic Python). So the discriminator MUST be deterministic
# runtime features. The recal-ceiling probe (LLM gold, 7 string features) and the
# confidence-layer probe (full production confidence_score) both came out ≈ base
# rate. This probe closes the loop with the strongest labels available (real
# USPTO examiner §112 antecedent-basis rejections) AND the richest deterministic
# features (string + contextual chain signals + reference-numeral attachment).
#
# Label: positive = examiner-confirmed real defect (us_examiner_legit.json,
#        term-level join, version-robust per WS-A3). negative = walker finding on
#        an examiner-reviewed app the examiner did NOT flag (benign signal; PU
#        caveat — examiner-absence != benign, so the negatives are noisy, which
#        only makes a real signal HARDER to hide: if features can't separate the
#        clean positive subset from the rest, they carry no usable signal).
# Restricted to OCR-surviving findings (a term OCR destroyed can't be matched).
#
# DATA: /tmp/odp_examiner_claims.json (EdgeXpert claims dump — see
#       ws_a3_examiner_join.py header to regenerate from the PA venv).
#
#   python3 tests/eval/us_discriminator_probe.py [--limit N]
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS.parent.parent / "src"))

from patentlint.analysis.claims import check_antecedent_basis as us_ab  # noqa: E402
from patentlint.parser.claims import parse_claims  # noqa: E402

from odp_claims_parser import clean_odp_claims  # noqa: E402

GENERIC = {
    "device", "system", "unit", "portion", "member", "element", "surface",
    "layer", "region", "section", "part", "area", "side", "end", "direction",
    "axis", "value", "signal", "data", "module", "assembly", "structure",
    "body", "material", "line", "point", "circuit", "component", "means",
}

FEAT_NAMES = [
    "term_len", "ref_len", "term_words", "has_paren", "short_acronym",
    "ordinal_led", "single_word", "generic_head", "head_len",
    "intros_pool_size", "has_suggested_match", "suggested_cross_branch",
    "confidence_score", "has_ancestor_match", "num_ancestors",
    "head_has_refnumeral", "repeat_ref_count",
]


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _head(term: str) -> str:
    return re.sub(r"^(the|said|a|an)\s+", "", (term or "").lower()).strip()


def features(f: dict, claim_text: str) -> list:
    t = (f.get("term") or "").lower()
    r = (f.get("reference_form") or "").lower()
    words = t.split()
    head = words[-1] if words else ""
    diag = f.get("diagnostics") or {}
    ct = claim_text.lower()
    # Does the head noun appear adjacent to a reference numeral (patent element
    # identity signal — real elements get reference numbers; abstract refs don't)?
    head_refnum = 1 if head and re.search(
        re.escape(head) + r"\s+\(?\d{1,4}\)?\b", ct
    ) else 0
    repeat_ref = len(re.findall(r"\b(?:the|said)\s+" + re.escape(head), ct)) if head else 0
    return [
        len(t), len(r), len(words),
        1 if "(" in t else 0,
        1 if (t.isascii() and t.isupper() and len(t) <= 3) else 0,
        1 if re.match(r"^(first|second|third|fourth|fifth)\b", t) else 0,
        1 if len(words) == 1 else 0,
        1 if head in GENERIC else 0,
        len(head),
        int(diag.get("intros_pool_size") or 0),
        1 if diag.get("has_suggested_match") else 0,
        1 if diag.get("suggested_cross_branch") else 0,
        int(f.get("confidence_score") or 50),
        1 if f.get("ancestor_match_claim_id") else 0,
        len(f.get("ancestor_claim_ids") or []),
        head_refnum,
        repeat_ref,
    ]


def build(dump_path: Path, limit: int | None):
    exam = json.loads((THIS / "us_examiner_legit.json").read_text())
    rows = json.loads(dump_path.read_text())
    if limit:
        rows = rows[:limit]
    X, y = [], []
    for sk, ct in rows:
        eterms = {_norm(t) for t in exam.get(sk, [])}
        if not eterms:
            continue
        cleaned = clean_odp_claims(ct)
        ct_norm = _norm(cleaned)
        try:
            claims = parse_claims(cleaned)
            if not claims:
                continue
            findings = us_ab(claims)
        except Exception:
            continue
        eheads = {_head(e) for e in eterms}
        for f in findings:
            if not isinstance(f, dict):
                continue
            ref_n = _norm(f.get("reference_form", ""))
            term_n = _norm(f.get("term", ""))
            if not ref_n and not term_n:
                continue
            # OCR-survival gate: only score findings whose ref text survives.
            if ref_n not in ct_norm and term_n not in ct_norm:
                continue
            confirmed = (
                ref_n in eterms
                or term_n in eheads
                or any(term_n == eh or eh.endswith(" " + term_n) or term_n.endswith(" " + eh)
                       for eh in eheads if eh)
            )
            X.append(features(f, f.get("claim_text", "")))
            y.append(1 if confirmed else 0)
    return np.array(X, dtype=float), np.array(y)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", type=Path, default=Path("/tmp/odp_examiner_claims.json"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cache", action="store_true",
                    help="reuse cached feature matrix (skip 3.5-min walker run)")
    a = ap.parse_args()
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_predict
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    cache = THIS / "_us_discriminator_cache.npz"
    if a.cache and cache.exists():
        z = np.load(cache)
        X, y = z["X"], z["y"]
    else:
        X, y = build(a.dump, a.limit)
        np.savez(cache, X=X, y=y)
    print(f"n findings={len(y)}  examiner-confirmed base rate={y.mean():.4f}")
    Xs = StandardScaler().fit_transform(X)

    def report(name, proba):
        auc = roc_auc_score(y, proba)
        order = np.argsort(-proba)
        top5 = y[order[: int(len(y) * 0.05)]].mean()
        print(f"{name:>20}: AUC={auc:.4f}  top5%-precision={top5 * 100:.1f}%  "
              f"lift={top5 / max(1e-9, y.mean()):.2f}")
        return auc

    lr = LogisticRegression(max_iter=2000, class_weight="balanced")
    report("LogReg", cross_val_predict(lr, Xs, y, cv=5, method="predict_proba")[:, 1])
    try:
        from sklearn.ensemble import GradientBoostingClassifier
        gb = GradientBoostingClassifier(n_estimators=200, max_depth=3)
        report("GradientBoosting", cross_val_predict(gb, X, y, cv=5, method="predict_proba")[:, 1])
    except Exception as e:  # pragma: no cover
        print("GB skipped:", e)
    lr.fit(Xs, y)
    coefs = sorted(zip(FEAT_NAMES, lr.coef_[0]), key=lambda kv: -abs(kv[1]))
    print("\ntop standardized LR coefficients (|coef|):")
    for nm, c in coefs[:8]:
        print(f"  {nm:>22}: {c:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
