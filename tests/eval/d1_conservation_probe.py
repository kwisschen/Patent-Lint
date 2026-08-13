# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# d1_conservation_probe.py - a TOTAL argument for an Engine-3 extractor change.
#
# WHY THIS EXISTS (2026-08-13, reports #445 / #447).
#
# `refnum_corpus_runner` keys conflicts on `pid|numeral`, so a change that makes
# a previously-INVISIBLE designator visible CHANGES THE KEY and reads as a
# removal even though nothing was lost. Recognising primed designators (`110'`
# is a distinct element from `110`) SPLITS conflicts rather than deleting them,
# and the gate duly reported `strong_real removed = 20` on CN for a change that
# provably loses nothing. That is the D1 analogue of an ADR-111 shift.
#
# The runner was taught the shape (it now recognises PRIME SPLITS), but a guard
# that has just been re-taught cannot also be the evidence that re-teaching it
# was correct. This probe is the independent check: it works on RAW pair
# occurrences rather than on conflict keys, so it is blind to how conflicts are
# grouped, and it answers the only question that matters - did any
# `(numeral, name)` occurrence get DROPPED?
#
# METHOD
#   1. Run once BEFORE the edit, once AFTER (git stash in between).
#   2. `--fold` names a set of characters to strip off the numeral in the AFTER
#      set, collapsing the new distinction back out.
#   3. The folded AFTER multiset must reproduce the BEFORE multiset with ZERO
#      lost keys. Gains are fine and expected (a fix can RECOVER occurrences -
#      `(25')` never matched the parens patterns at all, so +7 CN / +147 TW
#      pair-occurrences came back); losses are not.
#
# Scope it with --docs to the affected documents (from the runner's changed
# conflict keys) - a whole-corpus pass takes far longer than the 10-minute
# tool budget and adds nothing, since unaffected documents are identical by
# construction.
#
# USAGE
#   python tests/eval/d1_conservation_probe.py --juris TW --out /tmp/after.json
#   git stash push -u
#   python tests/eval/d1_conservation_probe.py --juris TW --out /tmp/before.json
#   git stash pop
#   python tests/eval/d1_conservation_probe.py --juris TW \
#       --compare /tmp/before.json /tmp/after.json --fold "'’"
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent


def _extractor(juris: str):
    if juris == "US":
        from patentlint.analysis.specification import extract_numeral_name_pairs
        return extract_numeral_name_pairs
    from patentlint.analysis.cn_specification import _cn_extract_numeral_name_pairs
    return _cn_extract_numeral_name_pairs


def _doc_text(value) -> str:
    """The scraped corpora store either a bare string or a section dict."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(v for v in value.values() if isinstance(v, str))
    return "\n".join(map(str, value))


def _dump(juris: str, docs: list[str] | None, out: Path) -> int:
    sys.path.insert(0, str(THIS_DIR))
    import refnum_corpus_runner as runner

    extract = _extractor(juris)
    descs = runner._load_descs(juris)
    pids = docs if docs is not None else sorted(descs)

    counts: Counter = Counter()
    for pid in pids:
        if pid not in descs:
            continue
        for numeral, name in extract(_doc_text(descs[pid])):
            counts[f"{pid}\t{numeral}\t{name}"] += 1
    out.write_text(json.dumps(counts))
    print(
        f"{juris}: {len(pids)} docs, {sum(counts.values())} pair-occurrences, "
        f"{len(counts)} distinct -> {out}"
    )
    return 0


def _compare(before: Path, after: Path, fold: str) -> int:
    pre = Counter(json.loads(before.read_text()))
    post = Counter(json.loads(after.read_text()))

    folded: Counter = Counter()
    for key, n in post.items():
        pid, numeral, name = key.split("\t")
        if fold:
            numeral = "".join(ch for ch in numeral if ch not in fold)
        folded[f"{pid}\t{numeral}\t{name}"] += n

    lost = {k: (pre[k], folded.get(k, 0)) for k in pre if folded.get(k, 0) < pre[k]}
    gained = {k: (pre.get(k, 0), folded[k]) for k in folded if folded[k] > pre.get(k, 0)}

    print("=== D1 conservation probe ===")
    print(f"  fold characters       : {fold!r}")
    print(f"  BEFORE occurrences    : {sum(pre.values())}")
    print(f"  AFTER (folded)        : {sum(folded.values())}")
    print(f"  >>> keys LOST (HARD GATE, MUST be 0): {len(lost)}")
    print(f"  keys gained (recovered occurrences) : {len(gained)}")
    for key, (was, now) in list(lost.items())[:20]:
        print(f"     LOST   {key.replace(chr(9), ' | ')}  {was} -> {now}")
    for key, (was, now) in list(gained.items())[:10]:
        print(f"     gained {key.replace(chr(9), ' | ')}  {was} -> {now}")
    print(f"  GATE: {'PASS' if not lost else 'FAIL - occurrences were dropped'}")
    return 0 if not lost else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Total-conservation proof for an Engine-3 extractor change"
    )
    ap.add_argument("--juris", choices=["US", "CN", "TW"])
    ap.add_argument("--out", type=Path, help="dump pair-occurrences here")
    ap.add_argument(
        "--docs",
        type=Path,
        help="JSON list of patent ids to scope to (default: whole corpus, slow)",
    )
    ap.add_argument(
        "--compare",
        nargs=2,
        type=Path,
        metavar=("BEFORE", "AFTER"),
        help="compare two dumps",
    )
    ap.add_argument(
        "--fold",
        default="",
        help="characters to strip off the numeral in AFTER before comparing",
    )
    args = ap.parse_args()

    if args.compare:
        return _compare(args.compare[0], args.compare[1], args.fold)
    if args.out:
        if not args.juris:
            ap.error("--out needs --juris")
        docs = json.loads(args.docs.read_text()) if args.docs else None
        return _dump(args.juris, docs, args.out)
    ap.error("pass --out (to dump) or --compare (to check)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
