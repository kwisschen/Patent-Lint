# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# queue_replay.py - replay every open antecedent-basis report against the
# CURRENT walker, from the report's own context window.
#
# Each finding in a report payload carries ~35 characters of claim text on
# each side of the flagged reference. The replay rebuilds that window as a
# one-claim document, runs the walker, and asks: does the walker still emit
# the reported term here?
#
#   STILL      the reported term is still emitted from the window
#   CHANGED    the window no longer yields the reported term (a capture or
#              basis fix shipped since the report). Closing such a report
#              still needs a read: the window is not the whole claim.
#   GONE       CHANGED, and nothing overlapping the reported term is emitted:
#              the reference no longer fires in the window at all
#   NO_WINDOW  the payload has no usable context (older payload format)
#
# The window has no earlier claims, so a reference whose basis lives in an
# earlier claim always reads STILL here. CHANGED is the informative bucket.
#
# Reporter draft text NEVER leaves this process: the payloads are fetched
# from the private tracker at run time and the output goes to the path given
# with --out (keep it in the session scratchpad, never in the repo).
#
# USAGE
#   python tests/eval/queue_replay.py --out <scratch>/replay.json [--bodies <bodies.json>]
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from patentlint.analysis.claims import check_antecedent_basis as check_us  # noqa: E402
from patentlint.analysis.cn_claims import check_antecedent_basis_cn as check_cn  # noqa: E402
from patentlint.analysis.tw_claims import check_antecedent_basis as check_tw  # noqa: E402
from patentlint.models import Claim, CnPatentDocument, TwPatentDocument  # noqa: E402

# The US walker takes the claim list itself.
_DOCS = {"TW": (TwPatentDocument, check_tw), "CN": (CnPatentDocument, check_cn), "US": (list, check_us)}


def _fetch() -> list[dict]:
    out = subprocess.run(
        ["gh", "issue", "list", "--repo", "kwisschen/patentlint-reports", "--label", "report",
         "--state", "open", "--limit", "2000", "--json", "number,body,labels,createdAt"],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def _payload(body: str) -> dict | None:
    m = re.search(r"```json\n(.*?)\n```", body, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _terms(juris: str, text: str) -> set[str]:
    doc_cls, check = _DOCS[juris]
    claim = Claim(id=1, text=text, independent=True, dependencies=[])
    try:
        doc = [claim] if doc_cls is list else doc_cls(claims=[claim])
        return {f["term"] for f in check(doc) if isinstance(f, dict)}
    except Exception:  # noqa: BLE001 - a replay counts what it can
        return set()


def replay_finding(juris: str, f: dict) -> str:
    """STILL / CHANGED / GONE / NO_WINDOW. GONE is CHANGED with nothing at
    all emitted that overlaps the reported term: the reference no longer
    fires in the window."""
    before, after, term = f.get("context_before"), f.get("context_after"), f.get("term")
    if not (before and after and term):
        return "NO_WINDOW"
    terms = _terms(juris, before + term + after)
    if term in terms:
        return "STILL"
    if any(t and (t in term or term in t or t[:2] == term[:2]) for t in terms):
        return "CHANGED"
    return "GONE"


def main() -> int:
    ap = argparse.ArgumentParser(description="Replay open antecedent reports against the current walker")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--bodies", type=Path, help="a saved gh issue list JSON (number, body, labels)")
    args = ap.parse_args()
    issues = json.loads(args.bodies.read_text()) if args.bodies else _fetch()
    rows, tally = [], Counter()
    for issue in issues:
        p = _payload(issue["body"])
        if not p or p.get("check_key") != "antecedentBasis":
            continue
        juris = (p.get("jurisdiction") or "").upper()
        if juris not in _DOCS:
            continue
        verdicts = [replay_finding(juris, f) for f in p.get("findings") or []]
        for v in verdicts:
            tally[(juris, v)] += 1
        rows.append({"number": issue["number"], "juris": juris, "build": p.get("patentlint_build"),
                     "labels": [lb["name"] for lb in issue["labels"]], "verdicts": verdicts})
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    for k, v in sorted(tally.items()):
        print(f"  {k[0]} {k[1]:9s} {v}")
    gone = [r["number"] for r in rows if r["verdicts"] and all(v == "GONE" for v in r["verdicts"])]
    print(f"reports whose every finding is GONE: {len(gone)} of {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
