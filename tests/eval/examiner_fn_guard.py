# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# examiner_fn_guard.py - the AUTHORITATIVE US FN-guard (ADR-159 Path-to-80).
#
# WHY THIS EXISTS: validate_fix.py guards against silencing LLM-gold
# `legit_drafting_error` labels. This guards against silencing a defect a REAL
# USPTO EXAMINER actually rejected under §112 - authoritative ground truth, and
# a strictly stronger bar. Two US classes (R33-gerund #336/#337 and
# R34-switches #386/#401) sat blocked for weeks specifically because a
# TERM-LEVEL check could not clear them and no runnable claim-level guard
# existed. This is that guard.
#
# It snapshots the set of examiner-confirmed terms the walker RECALLS, so a
# candidate fix can be proven not to drop any of them.
#
#   python tests/eval/examiner_fn_guard.py --snapshot /tmp/pre_exam.json
#   ... edit the walker ...
#   python tests/eval/examiner_fn_guard.py --compare  /tmp/pre_exam.json
#
# GATE: recalled_lost == 0. Exit code 1 on failure.
#
# PREREQ - the EdgeXpert claims dump (gitignored, local-only). EdgeXpert is a
# Tailscale-reachable Postgres box. NOTE THE HOSTNAME TRAP: `edgexpert-ts` is an
# ~/.ssh/config Host ALIAS, NOT a DNS name, so socket.create_connection on it
# always fails with gaierror and reads as "box is down". The box answers on
# its Tailscale IP (set PATENTLINT_EXAMINER_DB_HOST; the MagicDNS name also resolves). Probe the IP, never the alias.
#
#   cd ~/Documents/Projects/Patent-Analyst && python3 -c "
#   import json,psycopg2
#   from pathlib import Path
#   url=[l.split('=',1)[1].strip().strip('\"').strip(\"'\") for l in open('.env')
#        if l.startswith('ANALYST_CORPUS_DATABASE_URL')][0]
#   exam=json.loads((Path.home()/'Documents/Projects/Patent-Lint/tests/eval/us_examiner_legit.json').read_text())
#   cur=psycopg2.connect(url, connect_timeout=30).cursor()
#   cur.execute('select source_key, claims_text from corpus_application_text '
#               'where source_key = any(%s) and claims_text is not null',(list(exam),))
#   json.dump([[k,c] for k,c in cur.fetchall()], open('/tmp/odp_examiner_claims.json','w'))"
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS.parent.parent / "src"))
sys.path.insert(0, str(THIS))

from patentlint.analysis.claims import check_antecedent_basis as us_ab  # noqa: E402
from patentlint.parser.claims import parse_claims  # noqa: E402

from odp_claims_parser import clean_odp_claims  # noqa: E402


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _head(term: str) -> str:
    return re.sub(r"^(the|said)\s+", "", term)


def recalled_set(dump_path: Path, limit: int | None = None) -> set[tuple[str, str]]:
    """The (app, examiner_term) pairs the walker currently flags.

    Matching mirrors ws_a3_examiner_join.run() exactly so the two report the
    same population; only the return shape differs (set, not counts).
    """
    exam = json.loads((THIS / "us_examiner_legit.json").read_text())
    rows = json.loads(dump_path.read_text())
    if limit:
        rows = rows[:limit]
    out: set[tuple[str, str]] = set()
    for sk, ct in rows:
        eterms = {_norm(t) for t in exam.get(sk, [])}
        if not eterms:
            continue
        try:
            claims = parse_claims(clean_odp_claims(ct))
            if not claims:
                continue
            findings = us_ab(claims)
        except Exception:
            continue
        wrefs = {_norm(f.get("reference_form", "")) for f in findings if isinstance(f, dict)}
        wterms = {_norm(f.get("term", "")) for f in findings if isinstance(f, dict)}
        for et in eterms:
            h = _head(et)
            if (et in wrefs) or (h in wterms) or any(
                h == w or h.endswith(" " + w) or w.endswith(" " + h) for w in wterms if w
            ):
                out.add((sk, et))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Authoritative US examiner FN-guard")
    ap.add_argument("--dump", type=Path, default=Path("/tmp/odp_examiner_claims.json"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--snapshot", type=Path)
    ap.add_argument("--compare", type=Path)
    args = ap.parse_args()

    if not args.dump.exists():
        print(f"FATAL: claims dump not found at {args.dump} - see the header for the pull.")
        return 2

    cur = recalled_set(args.dump, args.limit)

    if args.snapshot:
        args.snapshot.write_text(json.dumps(sorted(cur)))
        print(f"snapshot: {len(cur)} examiner-confirmed terms recalled → {args.snapshot}")
        return 0

    if args.compare:
        pre = {tuple(x) for x in json.loads(args.compare.read_text())}
        lost = sorted(pre - cur)
        gained = sorted(cur - pre)
        print("=== EXAMINER FN-GUARD ===")
        print(f"  recalled pre  : {len(pre)}")
        print(f"  recalled post : {len(cur)}")
        print(f"  GAINED (new real defects caught): {len(gained)}")
        print(f"  >>> LOST (HARD GATE, MUST be 0) : {len(lost)}")
        for sk, t in lost[:25]:
            print(f"        FN  {sk}  {t!r}")
        ok = not lost
        print(f"  GATE: {'PASS' if ok else 'FAIL - do not ship'}")
        return 0 if ok else 1

    ap.error("pass --snapshot or --compare")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
