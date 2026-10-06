# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# cn_short_stem_probe.py - size the CN short-stem prefix-fallback class.
#
# The CN walker resolves a reference that matches no introduction exactly by the
# LONGEST registered intro that is a PREFIX of it. That is a safety net for a
# reference whose tail over-captured (`所述支架设置` -> `支架`). It is also a
# false-negative engine when the stem is short and the "tail" completes a
# different element: `电路` resolving `所述电路板`, `电压` resolving
# `所述电压源`, a bare ordinal `第一` resolving `第一芯`. It is why CN 并/而 are
# withheld (a 2-char stem from a cut, or from a later 和 split, resolves a
# longer element), and why the next CN lever is a RESOLUTION-side guard.
#
# Measured 2026-09-29 on main (1,029 CN drafts): 7,062 prefix-fallback
# resolutions, 1,494 via a 2-char stem, 206 of them stem + ONE character, 93
# bare-ordinal stems in 22 drafts. Re-run before designing the guard.
#
#   PYTHONPATH=src python3 tests/eval/cn_short_stem_probe.py [--json OUT] [--show N]
#
# Uses the walker's own `_PREFIX_FALLBACK_OBSERVER` hook, so it measures the
# code that executes rather than a re-implementation of the resolver.
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

_BARE_ORDINAL = re.compile(r"^第[一二三四五六七八九十]$")


def collect() -> list[tuple[str, int, str, str]]:
    import round1_corpus_harness as h
    import patentlint.analysis.cn_claims as C

    rows: list[tuple[str, int, str, str]] = []
    current = {"pid": ""}

    def observe(stem: str, term: str, claim_id: int) -> None:
        rows.append((current["pid"], claim_id, stem, term))

    C._PREFIX_FALLBACK_OBSERVER = observe
    try:
        for rec in h.load_corpus("CN"):
            current["pid"] = rec.get("patent_id") or ""
            h.run_walker([rec], "CN")
    finally:
        C._PREFIX_FALLBACK_OBSERVER = None
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Size the CN short-stem prefix-fallback class")
    ap.add_argument("--json", type=Path, help="write every (pid, claim, stem, term) row here")
    ap.add_argument("--show", type=int, default=20, help="sample stem+1 rows to print")
    args = ap.parse_args()

    rows = collect()
    two = [r for r in rows if len(r[2]) == 2]
    plus_one = [r for r in two if len(r[3]) == 3]
    ordinals = [r for r in two if _BARE_ORDINAL.match(r[2])]
    print(f"prefix-fallback resolutions : {len(rows)}")
    print(f"  via a 2-char stem         : {len(two)}")
    print(f"    stem + one character    : {len(plus_one)} in {len({r[0] for r in plus_one})} drafts")
    print(f"    bare-ordinal stems      : {len(ordinals)} in {len({r[0] for r in ordinals})} drafts")
    third = collections.Counter(r[3][2] for r in plus_one)
    print(f"  stem+1 third character    : {third.most_common(25)}")
    for r in plus_one[: args.show]:
        print("   ", r)
    if args.json:
        args.json.write_text(json.dumps(rows, ensure_ascii=False))
    # Non-vacuity: a corpus with zero fallback resolutions means the hook never fired.
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
