# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# trailing_token_miner.py - regenerate the over-capture cluster (ADR-159
# Path-to-80). Run the antecedent walker over the full corpus, join each finding
# to the ensemble gold verdict, and cluster gold-`walker_fp` findings by their
# TRAILING token (last CJK char / last whitespace word). The trailing-token
# clusters with a high walker_fp:legit ratio are the FN-safe over-capture batch
# candidates (a trailing VERB that the walker grabbed past the noun head).
#
#   python3 tests/eval/trailing_token_miner.py CN [--min 6]
#
# (ephemeral mining tool - the /tmp dumps it replaces were one-offs.)
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import round1_corpus_harness as h  # noqa: E402


def trailing(term: str, juris: str, n: int) -> str:
    t = (term or "").strip()
    if not t:
        return ""
    if juris in ("CN", "TW"):
        return t[-n:]  # last n CJK chars
    return t.split()[-1] if t.split() else ""


def collect(juris: str) -> list:
    """Run the walker over the corpus, return [(term, gold_category), ...].
    Cached to tests/eval/_trailing_<juris>.json (re-cluster instantly)."""
    cache = THIS / f"_trailing_{juris}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    fns = {
        "US": "patentlint.analysis.claims.check_antecedent_basis",
        "CN": "patentlint.analysis.cn_claims.check_antecedent_basis_cn",
        "TW": "patentlint.analysis.tw_claims.check_antecedent_basis",
    }
    mod, _, name = fns[juris].rpartition(".")
    fn = getattr(__import__(mod, fromlist=[name]), name)
    verd = h.load_ensemble_verdicts(juris)
    out = []
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
            out.append([f.get("term", ""), verd.get(key)])
    cache.write_text(json.dumps(out))
    return out


def run(juris: str, mincount: int, n: int) -> None:
    pairs = collect(juris)
    clusters: dict[str, dict] = defaultdict(lambda: {"wfp": 0, "legit": 0, "other": 0, "samples": []})
    tot_wfp = 0
    for term, cat in pairs:
        tt = trailing(term, juris, n)
        if not tt:
            continue
        c = clusters[tt]
        if cat == "walker_fp":
            c["wfp"] += 1
            tot_wfp += 1
            if len(c["samples"]) < 6:
                c["samples"].append(term)
        elif cat == "legit_drafting_error":
            c["legit"] += 1
        else:
            c["other"] += 1
    print(f"== {juris} ==  total gold walker_fp (by {n}-char trailing): {tot_wfp}")
    print(f"{'tok':>6} {'wfp':>6} {'legit':>6} {'other':>6}  samples (FN-safe iff legit==0)")
    rows = sorted(clusters.items(), key=lambda kv: -kv[1]["wfp"])
    for tok, c in rows:
        if c["wfp"] < mincount:
            continue
        flag = "  <-- CLEAN" if c["legit"] == 0 else ""
        print(f"{tok:>6} {c['wfp']:>6} {c['legit']:>6} {c['other']:>6}  "
              f"{', '.join(c['samples'][:4])}{flag}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("juris", choices=["US", "CN", "TW"])
    ap.add_argument("--min", type=int, default=6)
    ap.add_argument("--n", type=int, default=1, help="trailing N chars (CJK)")
    a = ap.parse_args()
    run(a.juris, a.min, a.n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
