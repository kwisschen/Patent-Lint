# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# exception_head_bisect.py - measure each CANDIDATE MEMBER of a walker set
# INDIVIDUALLY instead of measuring the set in bulk (TW R43, 2026-08-17).
#
# WHY THIS EXISTS. The device-noun interior-cut class (reports #537/#538) was
# withheld once at "24 UNPAIRED-NEW", which reads as a dead class. Running the
# 26 candidate heads as 26 SEPARATE measurements split it cleanly instead:
# 21 heads at 0-unpaired/0-legit each, the collateral concentrated in 5, and the
# head the REPORTS actually name (處理器) the single worst of the 26. That turned
# "withhold the class" into "ship 21, withhold 5 each with its own number" -
# which is a far better handoff, because the next round can attack them one at a
# time instead of re-deriving the whole measurement.
#
# The per-member run is cheap when the corpus gate is fast (~30s per run here),
# so budget for it BEFORE declaring a candidate set unshippable.
#
# USAGE
#   # 1. snapshot the CURRENT walker (before any edit)
#   python tests/eval/validate_fix.py --juris TW --snapshot /tmp/base_tw.json
#
#   # 2. bisect a candidate list against that baseline
#   python tests/eval/exception_head_bisect.py --juris TW \
#       --baseline /tmp/base_tw.json \
#       --candidates 處理器,產生器,傳輸器,驅動器
#
#   # ...or re-check the five heads TW R43 withheld:
#   python tests/eval/exception_head_bisect.py --juris TW \
#       --baseline /tmp/base_tw.json --withheld-r43
#
# Each row reports, for that ONE member added to the set:
#   fp       gold walker_fp findings silenced      (the win)
#   legit    gold legit_drafting_error silenced    (MUST be 0, or it is an FN)
#   unpaired new findings with no silenced finding on the same doc+claim
#            (the HARD GATE - manufactured findings; MUST be 0)
#
# NOTE the numbers are per-member IN ISOLATION. Members can interact, so always
# re-run --combined on the subset you intend to ship before committing.
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent

# The five heads TW R43 measured and WITHHELD, with the number that blocked each
# (fp ended / unpaired manufactured), so a later round can re-check them after
# fixing the trailing-residue captures they are actually blocked on.
R43_WITHHELD_HEADS = ("處理器", "驅動器", "顯示驅動器", "夾持器", "產生器")

_SET_ATTR = {
    "TW": "_INTERIOR_CUT_EXCEPTIONS",
    "CN": "_INTERIOR_CUT_EXCEPTIONS_CN",
}


def _walker_module(juris: str):
    if juris == "TW":
        from patentlint.analysis import tw_claims as mod
    elif juris == "CN":
        from patentlint.analysis import cn_claims as mod
    else:
        raise SystemExit(f"unsupported jurisdiction for this probe: {juris}")
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Per-member measurement of a walker exception set")
    ap.add_argument("--juris", required=True, choices=["TW", "CN"])
    ap.add_argument("--baseline", type=Path, required=True,
                    help="snapshot written by validate_fix --snapshot BEFORE the edit")
    ap.add_argument("--candidates",
                    help="comma-separated members to test one at a time")
    ap.add_argument("--withheld-r43", action="store_true",
                    help=f"use the TW R43 withheld set: {', '.join(R43_WITHHELD_HEADS)}")
    ap.add_argument("--set-attr", default=None,
                    help="walker attribute to patch (default: the interior-cut exceptions)")
    ap.add_argument("--combined", action="store_true",
                    help="also measure every 0-unpaired member together")
    args = ap.parse_args()

    if args.withheld_r43:
        candidates = list(R43_WITHHELD_HEADS)
    elif args.candidates:
        candidates = [c.strip() for c in args.candidates.split(",") if c.strip()]
    else:
        ap.error("pass --candidates or --withheld-r43")

    sys.path.insert(0, str(THIS_DIR))
    import round1_corpus_harness as h  # noqa: E402

    mod = _walker_module(args.juris)
    attr = args.set_attr or _SET_ATTR[args.juris]
    original = frozenset(getattr(mod, attr))
    # Measure against a set that has NONE of the candidates, so each row is that
    # member's own contribution rather than its contribution given the others.
    without = original - set(candidates)

    base = {tuple(x) for x in json.loads(args.baseline.read_text())}
    records = h.load_corpus(args.juris)
    verdicts = h.load_ensemble_verdicts(args.juris)

    def measure(members) -> tuple[int, int, int]:
        setattr(mod, attr, frozenset(without | set(members)))
        post = h.run_walker(records, args.juris)
        new_by, sil_by = collections.defaultdict(list), collections.defaultdict(list)
        for k in post - base:
            new_by[(k[0], k[1])].append(k[2])
        for k in base - post:
            sil_by[(k[0], k[1])].append(k[2])
        unpaired = sum(len(v) for key, v in new_by.items() if key not in sil_by)
        fp = sum(1 for k in base - post if verdicts.get(k) == "walker_fp")
        legit = sum(1 for k in base - post
                    if verdicts.get(k) == "legit_drafting_error")
        return fp, legit, unpaired

    try:
        print(f"=== per-member bisect: {args.juris} / {attr} "
              f"({len(candidates)} candidates, baseline {len(base)} findings) ===")
        results = {}
        for member in candidates:
            results[member] = measure([member])
            fp, legit, unpaired = results[member]
            verdict = ("CLEAN" if unpaired == 0 and legit == 0
                       else f"BLOCKED (unpaired={unpaired}, legit={legit})")
            print(f"  {member:12s} fp={fp:3d} legit={legit:2d} "
                  f"unpaired={unpaired:3d}  {verdict}", flush=True)

        clean = [m for m, (_, lg, up) in results.items() if up == 0 and lg == 0]
        print(f"\nCLEAN members ({len(clean)}): {clean}")
        blocked = {m: r for m, r in results.items() if m not in clean}
        if blocked:
            print("WITHHOLD with the measurement:")
            for m, (fp, lg, up) in blocked.items():
                print(f"  {m}: {fp} FPs ended / {up} UNPAIRED-NEW / {lg} legit")
        if args.combined and clean:
            fp, legit, unpaired = measure(clean)
            print(f"\nCOMBINED({len(clean)}): fp={fp} legit={legit} unpaired={unpaired}"
                  f"  {'SHIPPABLE' if unpaired == 0 and legit == 0 else 'RE-CHECK'}")
    finally:
        setattr(mod, attr, original)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
