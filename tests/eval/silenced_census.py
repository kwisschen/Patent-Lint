# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# silenced_census.py - list WHICH findings a walker change silenced or added.
#
# validate_fix prints counts; reading a silenced_legit means knowing which key
# it was and what the claim says around it. This prints every silenced key
# (optionally only one gold category) with ~40 chars of claim text either side
# of each occurrence of the reference form, and every new key.
#
# USAGE (snapshot taken with validate_fix --snapshot BEFORE the edit)
#   python tests/eval/silenced_census.py --juris TW --compare /tmp/pre_tw.json \
#       --only legit_drafting_error
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent


def _windows(text: str, needle: str, width: int = 40) -> list[str]:
    out, i = [], text.find(needle)
    while i != -1 and len(out) < 3:
        out.append(text[max(0, i - width):i] + "[" + needle + "]" + text[i + len(needle):i + len(needle) + width])
        i = text.find(needle, i + 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="List silenced / new walker findings with claim context")
    ap.add_argument("--juris", required=True, choices=["CN", "TW", "US"])
    ap.add_argument("--compare", required=True, type=Path, help="validate_fix snapshot taken before the edit")
    ap.add_argument("--only", help="only silenced keys with this gold category (e.g. legit_drafting_error)")
    ap.add_argument("--post", type=Path, help="also write the post-change snapshot here")
    args = ap.parse_args()

    sys.path.insert(0, str(THIS_DIR))
    import round1_corpus_harness as h

    records = h.load_corpus(args.juris)
    post = h.run_walker(records, args.juris)
    if args.post:
        args.post.write_text(json.dumps([list(k) for k in post]))
    pre = {tuple(x) for x in json.loads(args.compare.read_text())}
    verdicts = h.load_ensemble_verdicts(args.juris)
    claims_of = {}
    for rec in records:
        doc = h._build_doc(rec, args.juris)
        if doc is not None:
            claims_of[rec["patent_id"]] = {c.id: c.text for c in doc.claims}

    def show(tag: str, k: tuple) -> None:
        pid, cid, term, ref = k
        text = claims_of.get(pid, {}).get(cid, "")
        print(f"{tag} {verdicts.get(k, 'unjudged')} {pid} c{cid} term={term} ref={ref}")
        for w in _windows(text, ref or term):
            print("    " + w.replace("\n", " "))

    silenced = sorted(pre - post)
    added = sorted(post - pre)
    print(f"silenced {len(silenced)}  new {len(added)}")
    for k in silenced:
        if args.only and verdicts.get(k) != args.only:
            continue
        show("SILENCED", k)
    if not args.only:
        for k in added:
            show("NEW", k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
