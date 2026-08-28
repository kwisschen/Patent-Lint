# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# campaign_scorecard.py - honest cumulative FP reduction for the Path-to-80
# campaign (ADR-159), measured END TO END rather than summed per round.
#
# WHY THIS EXISTS (2026-08-28)
# ---------------------------
# The campaign scorecard summed each round's `validate_fix silenced_walker_fp`.
# That sum is a RAW OVERCOUNT, because validate_fix keys findings on
# (doc, claim, term, reference_form): any fix that CHANGES a term reads as
# "silenced" even though the finding still fires under the new term. The
# per-round correction is `unpaired_new_probe`'s paired-shift count.
#
# The obvious repair - go back and run a paired-shift pass per round - is NOT
# executable, and that was checked before being abandoned: of 39 TW rounds in
# round_history, only TWO ever recorded a paired count (R44, R45). The data
# does not exist for R8-R43, and re-deriving it would mean replaying ~154
# rounds across three jurisdictions against entangled later edits.
#
# So measure the thing the scorecard is actually trying to say, in ONE
# comparison: run the walker at the campaign-start commit and at HEAD over the
# same corpus with the same gold verdicts, and ask how many gold-confirmed
# walker_fp findings that fired THEN do not fire NOW. Re-keying cannot inflate
# this, because a re-keyed finding is still present in the "now" set.
#
# ⚠️ THE PROVENANCE ASSERTION IS LOAD-BEARING - DO NOT REMOVE IT.
# `round1_corpus_harness.run_walker` imports the walker lazily, INSIDE the
# function. When this script runs from a git worktree, that lazy import is
# resolved by the editable-install finder (PEP 660) to the MAIN repo's
# `src/patentlint`, NOT the worktree's - so the "campaign start" run silently
# measures HEAD and every number comes back as zero change. That is exactly
# what happened on the first attempt here: US/TW/CN all reported an identical
# start and now, and a flat 0 FPs ended. Importing the walker EXPLICITLY while
# `src` is at sys.path[0], then asserting `__file__` sits under the intended
# checkout, is what binds it correctly. A measurement that reports "no change"
# is the single most important place to prove which code you actually ran.
#
# USAGE
#   git worktree add /tmp/wt-start <campaign-start-sha>
#   python tests/eval/campaign_scorecard.py --start-checkout /tmp/wt-start
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent.parent

# The commit that locked the ADR-159 campaign plan.
CAMPAIGN_START_SHA = "75dc0aeb"

_RUNNER = r'''
import sys, os, json
sys.path.insert(0, "tests/eval")
sys.path.insert(0, "src")
# Bind the walker BEFORE the harness can lazily import it from elsewhere.
import patentlint.analysis.tw_claims as _T
import round1_corpus_harness as h
_want = os.path.abspath("src")
if not _T.__file__.startswith(_want):
    raise SystemExit(
        f"PROVENANCE FAIL: walker loaded from {_T.__file__}, expected under {_want}. "
        "The editable-install finder resolved patentlint to another checkout; "
        "this run would silently measure the wrong code."
    )
j, out = sys.argv[1], sys.argv[2]
keys = h.run_walker(h.load_corpus(j), j)
json.dump([list(k) for k in keys], open(out, "w"))
print(f"{j}: {len(keys)} findings   [from {_T.__file__}]", file=sys.stderr)
'''


def _run(checkout: Path, juris: str, out: Path, python: str) -> None:
    script = out.parent / "_scorecard_runner.py"
    script.write_text(_RUNNER)
    subprocess.run([python, str(script), juris, str(out)], cwd=checkout, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Honest cumulative campaign FP reduction")
    ap.add_argument("--start-checkout", type=Path, required=True,
                    help=f"a worktree at the campaign-start commit ({CAMPAIGN_START_SHA})")
    ap.add_argument("--now-checkout", type=Path, default=REPO_ROOT)
    ap.add_argument("--workdir", type=Path, default=Path("/tmp/campaign_scorecard"))
    ap.add_argument("--python", default=sys.executable,
                    help="pyenv shims resolve per-directory; pass an explicit "
                         "interpreter so the worktree does not pick a different one")
    args = ap.parse_args()
    args.workdir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(THIS_DIR))
    import round1_corpus_harness as h  # noqa: E402

    rows, tot = [], {"s": 0, "n": 0, "e": 0, "r": 0, "l": 0}
    for j in ("US", "TW", "CN"):
        s_out, n_out = args.workdir / f"start_{j}.json", args.workdir / f"now_{j}.json"
        _run(args.start_checkout, j, s_out, args.python)
        _run(args.now_checkout, j, n_out, args.python)
        pre = {tuple(x) for x in json.loads(s_out.read_text())}
        now = {tuple(x) for x in json.loads(n_out.read_text())}
        v = h.load_ensemble_verdicts(j)
        gone = pre - now
        fp_gone = {k for k in gone if v.get(k) == "walker_fp"}
        legit_gone = {k for k in gone if v.get(k) == "legit_drafting_error"}
        # A silenced FP whose (doc, claim) still carries SOME finding is very
        # likely a re-key, not a resolution - the same doc+claim pairing rule
        # unpaired_new_probe uses. This OVER-counts re-keys when the claim has
        # an unrelated finding, so `ended` is a LOWER bound. That is the right
        # direction for a number the campaign has been overstating.
        live = {(a, b) for a, b, _, _ in now}
        rekey = {k for k in fp_gone if (k[0], k[1]) in live}
        ended = len(fp_gone) - len(rekey)
        rows.append((j, len(pre), len(now), ended, len(rekey), len(legit_gone)))
        tot["s"] += len(pre)
        tot["n"] += len(now)
        tot["e"] += ended
        tot["r"] += len(rekey)
        tot["l"] += len(legit_gone)

    print(f"\n{'juris':6}{'start':>8}{'now':>8}{'net':>8}{'FP ENDED':>10}"
          f"{'re-keyed':>10}{'LEGIT lost':>12}")
    for jur, start, now_n, ended, rekeyed, lost in rows:
        print(f"{jur:6}{start:>8}{now_n:>8}{now_n - start:>8}"
              f"{ended:>10}{rekeyed:>10}{lost:>12}")
    print(f"{'TOTAL':6}{tot['s']:>8}{tot['n']:>8}{tot['n'] - tot['s']:>8}"
          f"{tot['e']:>10}{tot['r']:>10}{tot['l']:>12}")
    print(f"\n  RAW gold walker_fp silenced (old scorecard method) : {tot['e'] + tot['r']}")
    print(f"  of which RE-KEYED (claim still carries a finding)   : {tot['r']}")
    print(f"  HONEST gold-confirmed FPs ENDED                     : {tot['e']}")
    print(f"  gold legit_drafting_error LOST (FN check, want 0)   : {tot['l']}")
    print("\n  Scope: the ADR-159 window only. Rounds shipped BEFORE "
          f"{CAMPAIGN_START_SHA} are not covered by this comparison.")
    return 0 if tot["l"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
