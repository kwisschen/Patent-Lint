# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# unpaired_new_probe.py - the UNPAIRED-NEW gate for a walker round (ADR-159).
#
# WHY THIS EXISTS
#
# `validate_fix` answers "did this fix silence a gold-legit finding?" It does
# NOT answer "did this fix MANUFACTURE findings?", and its raw false-fire count
# cannot answer it either, because a fix that merely CLEANS a term relocates a
# finding: the old key disappears and a new one appears on the same claim. That
# is an ADR-111 SHIFT and it is fine. What is not fine is a NEW key on a claim
# where nothing was silenced - that is a finding conjured out of nothing.
#
# So the number that matters is UNPAIRED-NEW: new finding keys whose (doc,
# claim) had no silenced key. Every round is supposed to compute it, and until
# now every round recomputed it ad hoc.
#
# IT IS NOT OPTIONAL, and the campaign has the scar to prove it (TW #525,
# 2026-08-13): a fix that suppressed a mid-word truncation reported
# `silenced_legit == 0` and `GATE: PASS` from validate_fix while manufacturing
# a finding, because the dirty capture it removed had been covering a real
# reference BY PREFIX. Only UNPAIRED-NEW caught it. An UNDER-capture fix
# removes an intro and is FN-shaped exactly like a permissive matcher.
#
# Note the corollary the runner prints for you: when false-fires is 0,
# UNPAIRED-NEW is 0 by construction, so a fix that silences and adds nothing
# needs no further argument.
#
# USAGE (the snapshot is the SAME file validate_fix writes - take it BEFORE the
# edit, with the edit stashed)
#   python tests/eval/validate_fix.py        --juris TW --snapshot /tmp/pre_tw.json
#   ... edit the walker ...
#   python tests/eval/validate_fix.py        --juris TW --compare  /tmp/pre_tw.json
#   python tests/eval/unpaired_new_probe.py  --juris TW --compare  /tmp/pre_tw.json
#
# These runs take several minutes over the corpus - launch them in the
# background rather than chaining, or a 10-minute tool timeout kills the pass.
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(
        description="UNPAIRED-NEW gate: did this fix MANUFACTURE findings?"
    )
    ap.add_argument("--juris", required=True, choices=["CN", "TW", "US"])
    ap.add_argument(
        "--compare",
        required=True,
        type=Path,
        help="the pre-edit snapshot written by validate_fix --snapshot",
    )
    ap.add_argument(
        "--show",
        type=int,
        default=25,
        help="how many unpaired keys / paired shifts to print",
    )
    args = ap.parse_args()

    sys.path.insert(0, str(THIS_DIR))
    import round1_corpus_harness as h

    records = h.load_corpus(args.juris)
    post = h.run_walker(records, args.juris)
    pre = {tuple(x) for x in json.loads(args.compare.read_text())}
    verdicts = h.load_ensemble_verdicts(args.juris)

    silenced = pre - post
    new = post - pre
    # A finding is PAIRED when something was silenced on the same doc+claim -
    # i.e. the fix relocated it rather than inventing it.
    silenced_sites = {(k[0], k[1]) for k in silenced}
    unpaired = sorted(k for k in new if (k[0], k[1]) not in silenced_sites)
    paired = sorted(k for k in new if (k[0], k[1]) in silenced_sites)

    print(f"=== UNPAIRED-NEW gate ({args.juris}) ===")
    print(f"  silenced        : {len(silenced)}")
    print(f"  new             : {len(new)}")
    print(f"    ├─ paired shifts (same doc+claim, ADR-111): {len(paired)}")
    print(f"    └─ UNPAIRED (HARD GATE, MUST be 0)        : {len(unpaired)}")

    for key in unpaired[: args.show]:
        print(f"     UNPAIRED + [{verdicts.get(key)}] {key}")

    if paired and args.show:
        print("  --- paired shifts (relocations, not manufactures) ---")
        for key in paired[: args.show]:
            olds = [s for s in silenced if (s[0], s[1]) == (key[0], key[1])]
            print(
                f"     {key[2]!r}  <-  {[o[2] for o in olds]}  "
                f"(old verdicts: {[verdicts.get(o) for o in olds]})"
            )
        print(
            "  NOTE: a paired shift whose OLD key was gold-legit needs an "
            "ADR-111 dual-label in phase2b_results_*_corrections.json - and "
            "READ THE CLAIM before asserting the shift is benign."
        )

    print(f"  GATE: {'PASS' if not unpaired else 'FAIL - findings were manufactured'}")
    return 0 if not unpaired else 1


if __name__ == "__main__":
    raise SystemExit(main())
