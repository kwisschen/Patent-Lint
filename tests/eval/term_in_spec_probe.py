# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# term_in_spec_probe.py — WS-E1 (ADR-159 Path-to-80). The proper version of
# spec_presence_probe.py: instead of the weak `abstract` proxy, use the full
# scraped SPECIFICATION (description body) on the 705-draft US gold corpus to
# answer: does `term_in_spec` discriminate antecedent FPs from real §112(b)
# defects? Decides whether spec-presence is a usable US confidence signal.
#
# Reads tests/eval/us_descriptions.json (gitignored, 705/705 scraped).
from __future__ import annotations

import json
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import round1_corpus_harness as h  # noqa: E402


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def run(juris="US"):
    desc_path = THIS / f"{juris.lower()}_descriptions.json"
    descs = json.loads(desc_path.read_text())
    verd = h.load_ensemble_verdicts(juris)
    from patentlint.analysis.claims import check_antecedent_basis as us_ab

    # cnt[(in_spec, category)] = count ; also track spec availability
    cnt: dict[tuple, int] = {}
    no_spec = 0
    judged = 0
    pids_seen = set()
    pids_with_spec = set()
    for rec in h.load_corpus(juris):
        pid = rec["patent_id"]
        pids_seen.add(pid)
        spec = _norm((descs.get(pid) or {}).get("description") or "")
        spec_ns = spec.replace(" ", "")
        has_spec = bool(spec)
        if has_spec:
            pids_with_spec.add(pid)
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
            judged += 1
            if not has_spec:
                no_spec += 1
                continue
            ins = (term in spec) or (term.replace(" ", "") in spec_ns)
            cnt[(ins, c)] = cnt.get((ins, c), 0) + 1

    def split(b):
        legit = cnt.get((b, "legit_drafting_error"), 0)
        wfp = cnt.get((b, "walker_fp"), 0)
        tot = legit + wfp
        return legit, wfp, tot, (legit / tot if tot else 0.0)

    l_in, w_in, n_in, p_in = split(True)
    l_out, w_out, n_out, p_out = split(False)
    base_l = l_in + l_out
    base_w = w_in + w_out
    base_t = base_l + base_w

    print(f"\n== {juris} term_in_SPEC (full scraped description) ==")
    print(f"  corpus drafts: {len(pids_seen)}  with spec: {len(pids_with_spec)} "
          f"({100 * len(pids_with_spec) / max(1, len(pids_seen)):.1f}%)")
    print(f"  judged findings (wfp|legit): {judged}   no-spec dropped: {no_spec}")
    if not base_t:
        print("  NO judged findings with spec — cannot measure.")
        return
    print(f"  base P(legit) = {base_l}/{base_t} = {base_l / base_t:.3f}")
    print(f"  term     IN spec: n={n_in:5}  P(legit)={p_in:.3f}  (legit={l_in} wfp={w_in})")
    print(f"  term NOT in spec: n={n_out:5}  P(legit)={p_out:.3f}  (legit={l_out} wfp={w_out})")
    # The product-relevant trade: a term NOT in spec is the candidate "real defect"
    # signal (typo / never-written element). Measure promote-if-absent precision.
    if n_out:
        print(f"  --> term-NOT-in-spec as a 'likely real defect' flag: "
              f"precision={p_out:.3f} vs base {base_l / base_t:.3f}; "
              f"captures {100 * l_out / max(1, base_l):.1f}% of all legit")
    # And the demote-if-in trade (mirror of spec_presence_probe).
    if base_w and base_l:
        print(f"  --> DEMOTE-if-in-spec: removes {100 * w_in / base_w:.1f}% of walker_fp, "
              f"costs {100 * l_in / base_l:.1f}% of legit")


def main():
    for j in sys.argv[1:] or ["US"]:
        run(j)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
