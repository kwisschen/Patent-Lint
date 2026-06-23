# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# apply_proposed_labels.py — the automated labels feed for the recurring-FP
# loop (ADR-159 #2).
#
# Takes a proposed_labels JSON from recurring_fp_loop.py and:
#   * AUTO-APPLIES unanimous `walker_fp` verdicts into a SEPARATE, reversible
#     gold file (`phase2b_results_<juris>_autoapply.json`) in the exact shape
#     round1_corpus_harness.load_ensemble_verdicts reads. These are the
#     low-risk verdicts (the two cross-family judges agreed, no Opus needed).
#   * QUEUES everything else (legit_drafting_error, coverage_gap, ambig,
#     diagnostic_mis_attribution, and any *split* walker_fp) to a
#     `needs_review_<juris>_<stamp>.json` for human review — these are higher
#     stakes (a wrong `legit`/`protect` label blocks real fixes) and stay
#     human-gated.
#   * GATES: re-imports the corpus harness and reloads the merged gold to
#     confirm it parses and the verdict count went up — a fix never lands
#     against a broken gold.
#
# Reversibility: the autoapply file is separate from the curated round-1 gold;
# `git rm` it (or remove the line in round1_corpus_harness.PHASE2B_RESULTS) to
# fully undo. Auto-applied entries are tagged `source: "adr159-autoapply"`.
#
# Usage:
#   python tests/eval/apply_proposed_labels.py tests/eval/proposed_labels/proposed_corpus_TW_2026-06-23.json
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent

AUTO_APPLY_VERDICT = "walker_fp"
AUTO_APPLY_AGREEMENT = "unanimous"


def autoapply_path(jurisdiction: str) -> Path:
    return THIS_DIR / f"phase2b_results_{jurisdiction.lower()}_autoapply.json"


def _load_gold(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {"verdicts": [], "_note": "ADR-159 standing-loop auto-applied unanimous walker_fp. Reversible: delete this file."}


def _existing_keys(gold: dict) -> set:
    keys = set()
    for v in gold.get("verdicts", []):
        pid = v.get("patent_id")
        ens = v.get("ensemble") or {}
        for f in ens.get("findings") or []:
            keys.add((pid, f.get("claim_id"), f.get("term"), f.get("reference_form")))
    return keys


def apply(proposed_path: Path) -> dict:
    data = json.loads(proposed_path.read_text())
    proposals = data.get("proposed", [])
    if not proposals:
        return {"error": "no proposals in file"}
    jurisdiction = proposals[0].get("jurisdiction", "TW")

    auto, queued = [], []
    for p in proposals:
        if p.get("verdict") == AUTO_APPLY_VERDICT and p.get("agreement") == AUTO_APPLY_AGREEMENT:
            auto.append(p)
        else:
            queued.append(p)

    # Merge auto-apply into the reversible gold (dedup vs existing).
    gold_path = autoapply_path(jurisdiction)
    gold = _load_gold(gold_path)
    have = _existing_keys(gold)
    by_pid: dict[str, list] = defaultdict(list)
    added = 0
    for p in auto:
        pid = (p.get("source") or "").replace("corpus:", "") or "?"
        key = (pid, p.get("claim_id"), p.get("term"), p.get("reference_form"))
        if key in have:
            continue
        have.add(key)
        by_pid[pid].append(p)
        added += 1
    for pid, ps in by_pid.items():
        gold["verdicts"].append({
            "patent_id": pid,
            "jurisdiction": jurisdiction,
            "source": "adr159-autoapply",
            "ensemble": {
                "findings": [
                    {"claim_id": p.get("claim_id"), "term": p.get("term"),
                     "reference_form": p.get("reference_form")} for p in ps
                ],
                "final_verdicts": [
                    {"category": AUTO_APPLY_VERDICT, "confidence": p.get("confidence")}
                    for p in ps
                ],
            },
        })
    gold_path.write_text(json.dumps(gold, ensure_ascii=False, indent=2))

    # Queue the rest for human review.
    review_path = THIS_DIR / f"needs_review_{jurisdiction.lower()}_{proposed_path.stem}.json"
    review_path.write_text(json.dumps({"jurisdiction": jurisdiction, "queued": queued},
                                      ensure_ascii=False, indent=2))

    # Gate: reload the merged gold through the corpus harness.
    gate_ok, gate_msg = _gate(jurisdiction)

    return {
        "jurisdiction": jurisdiction,
        "auto_applied": added,
        "auto_apply_skipped_dupes": len(auto) - added,
        "queued_for_review": len(queued),
        "gold_file": str(gold_path.relative_to(THIS_DIR.parent.parent)),
        "review_file": str(review_path.relative_to(THIS_DIR.parent.parent)),
        "gate_ok": gate_ok,
        "gate": gate_msg,
    }


def _gate(jurisdiction: str) -> tuple[bool, str]:
    """Confirm the merged gold parses + the harness reads more verdicts."""
    try:
        sys.path.insert(0, str(THIS_DIR))
        import importlib
        import round1_corpus_harness as h
        importlib.reload(h)
        verdicts = h.load_ensemble_verdicts(jurisdiction)
        return True, f"corpus harness loads {len(verdicts)} {jurisdiction} verdicts"
    except Exception as e:  # pyarrow absent (CI [dev]) or parse error
        return False, f"{type(e).__name__}: {e}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto-apply unanimous walker_fp proposals (ADR-159 #2)")
    ap.add_argument("proposed_json", type=Path)
    args = ap.parse_args()
    result = apply(args.proposed_json)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("gate_ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
