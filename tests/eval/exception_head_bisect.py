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


def _rebuild(original, members):
    """Rebuild the patched set in the ORIGINAL container's shape.

    The interior-cut exceptions are an unordered frozenset, but other walker
    sets this probe can target are ORDERED and their order is load-bearing:
    ``_TRAILING_VERB_DENYLIST`` is a tuple sorted longest-first because the
    strip loop breaks on the first match, so 重新啟動 must be tried before
    啟動 or the longer collocation is dismantled a character at a time.
    Rebuilding an ordered set as a frozenset silently randomizes that and the
    probe measures a walker nobody would ship. Preserve the container.
    """
    if isinstance(original, tuple):
        return tuple(sorted(members, key=len, reverse=True))
    return frozenset(members)


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
    ap.add_argument("--explain", action="store_true",
                    help="for each BLOCKED member, print the silenced legit keys and "
                         "the unpaired-new keys so the block can be diagnosed as an "
                         "ADR-111 shift, a gold-correction, or a real FN")
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
    original = getattr(mod, attr)
    # Measure against a set that has NONE of the candidates, so each row is that
    # member's own contribution rather than its contribution given the others.
    without = set(original) - set(candidates)

    base = {tuple(x) for x in json.loads(args.baseline.read_text())}
    records = h.load_corpus(args.juris)
    verdicts = h.load_ensemble_verdicts(args.juris)

    detail: dict[str, dict] = {}

    def measure(members, label=None) -> tuple[int, int, int]:
        setattr(mod, attr, _rebuild(original, without | set(members)))
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
        if label is not None:
            detail[label] = {
                "legit": [k for k in base - post
                          if verdicts.get(k) == "legit_drafting_error"],
                "unpaired": [(key[0], key[1], t)
                             for key, v in new_by.items() if key not in sil_by
                             for t in v],
                # paired shifts: same doc+claim silenced AND re-emitted, i.e. a
                # re-keying rather than a resolution (lesson 3 - read silenced
                # MINUS paired shifts, never silenced alone)
                "paired": [(key[0], key[1], t)
                           for key, v in new_by.items() if key in sil_by
                           for t in v],
            }
        return fp, legit, unpaired

    try:
        print(f"=== per-member bisect: {args.juris} / {attr} "
              f"({len(candidates)} candidates, baseline {len(base)} findings) ===")
        results = {}
        for member in candidates:
            results[member] = measure([member], label=member)
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
        if args.explain:
            for m, (fp, lg, up) in results.items():
                d = detail.get(m, {})
                if not (d.get("legit") or d.get("unpaired") or d.get("paired")):
                    continue
                print(f"\n--- {m} ---")
                for k in d.get("legit", []):
                    print(f"  SILENCED-LEGIT  {k[0]} c{k[1]} {k[2]!r}")
                for k in d.get("unpaired", []):
                    print(f"  UNPAIRED-NEW    {k[0]} c{k[1]} {k[2]!r}")
                for k in d.get("paired", []):
                    print(f"  PAIRED-SHIFT    {k[0]} c{k[1]} {k[2]!r}")

        if args.combined and clean:
            fp, legit, unpaired = measure(clean)
            print(f"\nCOMBINED({len(clean)}): fp={fp} legit={legit} unpaired={unpaired}"
                  f"  {'SHIPPABLE' if unpaired == 0 and legit == 0 else 'RE-CHECK'}")
    finally:
        setattr(mod, attr, original)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
