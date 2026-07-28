# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# validate_fix.py - the FN-guarded self-audit harness for class fixes (ADR-159).
#
# A walker mechanism fix ends an FP class only if it (a) SILENCES the walker_fp
# findings and (b) drops ZERO gold-`legit_drafting_error` findings - silencing a
# real defect is a false negative, the thing we must never do.
#
# Workflow per fix (all deterministic - NO LLM spend):
#   python tests/eval/validate_fix.py --juris TW --snapshot /tmp/pre_tw.json   # BEFORE edit
#   ... edit the walker ...
#   python tests/eval/validate_fix.py --juris TW --compare  /tmp/pre_tw.json   # AFTER edit
#
# The compare run prints the AccuracyReport. The RELIABILITY GATE is:
#   silenced_legit == 0   AND   silenced_walker_fp > 0
# If silenced_legit > 0 the fix injected FNs - revert and narrow.
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent


def _walker_keys(jurisdiction: str) -> set:
    sys.path.insert(0, str(THIS_DIR))
    import round1_corpus_harness as h
    records = h.load_corpus(jurisdiction)
    return h.run_walker(records, jurisdiction), h


def main() -> int:
    ap = argparse.ArgumentParser(description="FN-guarded before/after validator for class fixes")
    ap.add_argument("--juris", required=True, choices=["CN", "TW", "US"])
    ap.add_argument("--snapshot", type=Path, help="write current walker finding-keys here (run BEFORE the edit)")
    ap.add_argument("--compare", type=Path, help="compare current walker against this snapshot (run AFTER the edit)")
    args = ap.parse_args()

    keys, h = _walker_keys(args.juris)

    if args.snapshot:
        args.snapshot.write_text(json.dumps([list(k) for k in keys]))
        print(f"snapshot: {len(keys)} walker findings → {args.snapshot}")
        return 0

    if args.compare:
        pre = {tuple(x) for x in json.loads(args.compare.read_text())}
        post = keys
        verdicts = h.load_ensemble_verdicts(args.juris)
        rep = h.classify_findings(pre, post, verdicts)
        print(rep)
        print("=== RELIABILITY GATE ===")
        gate_ok = rep.silenced_legit == 0 and rep.silenced_walker_fp > 0
        print(f"  silenced_walker_fp (FPs ended) : {rep.silenced_walker_fp}")
        print(f"  silenced_coverage  (FPs ended) : {rep.silenced_coverage}")
        print(f"  silenced_legit     (FNs!! ==0) : {rep.silenced_legit}")
        print(f"  silenced_ambig/unjudged        : {rep.silenced_ambig + rep.silenced_unjudged}")
        print(f"  false_fires_legit  (new TPs ok): {rep.false_fires_legit}")
        print(f"  GATE: {'PASS ✓ (ship)' if gate_ok else 'FAIL ✗ (revert/narrow)' if rep.silenced_legit else 'no FPs silenced (no-op)'}")
        return 0 if rep.silenced_legit == 0 else 1

    ap.error("pass --snapshot or --compare")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
