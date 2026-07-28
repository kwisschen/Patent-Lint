# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# ws_a3_examiner_join.py - WS-A3 (ADR-159 Path-to-80). Run the US antecedent
# walker on EdgeXpert ODP claims and join its findings to REAL examiner §112
# antecedent-basis labels (tests/eval/us_examiner_legit.json, WS-A1) at the
# TERM level (app, normalized-term) - version-robust, avoids the claim-number
# 0%-overlap artifact.
#
# Two numbers come out:
#   - true RECALL: of examiner-flagged terms that SURVIVE OCR in the claim text,
#     how many did the walker also flag? (Did the walker catch real defects?)
#   - examiner-confirmed RATE: of all walker findings on these apps, how many
#     match an examiner term? (A benign-rate *signal* - but examiner-absence is
#     NOT proof of benign: examiners miss things / issues get amended out, so
#     this BOUNDS rather than measures the FP rate. See PATH_TO_80_PLAN.md.)
#
# The OCR-survival ceiling is reported because a term the OCR destroyed
# (`sul fu ric acid`) can never be matched - recall is measured against the
# surviving subset, not the raw examiner set.
#
# DATA: claims_text lives in EdgeXpert Postgres (psycopg2, PA venv only). Pull a
# cached dump from the Patent-Analyst venv first:
#
#   cd ~/Documents/Projects/Patent-Analyst && python3 - <<'PY'
#   import json; from pathlib import Path; import psycopg2
#   envp=Path.home()/"Documents/Projects/Patent-Analyst/.env"
#   url=[l.split('=',1)[1].strip().strip('"').strip("'") for l in envp.read_text().splitlines()
#        if l.startswith('ANALYST_CORPUS_DATABASE_URL')][0]
#   exam=json.loads((Path.home()/"Documents/Projects/Patent-Lint/tests/eval/us_examiner_legit.json").read_text())
#   cur=psycopg2.connect(url, connect_timeout=30).cursor()
#   cur.execute("select source_key, claims_text from corpus_application_text "
#               "where source_key = any(%s) and claims_text is not null", (list(exam),))
#   json.dump([[k,c] for k,c in cur.fetchall()], open('/tmp/odp_examiner_claims.json','w'))
#   PY
#
# then (PL venv):  python3 tests/eval/ws_a3_examiner_join.py [--limit N] [--dump /tmp/odp_examiner_claims.json]
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS.parent.parent / "src"))

from patentlint.analysis.claims import check_antecedent_basis as us_ab  # noqa: E402
from patentlint.parser.claims import parse_claims  # noqa: E402

from odp_claims_parser import clean_odp_claims  # noqa: E402


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _head(term: str) -> str:
    return re.sub(r"^(the|said)\s+", "", term)


def run(dump_path: Path, limit: int | None) -> dict:
    exam = json.loads((THIS / "us_examiner_legit.json").read_text())
    rows = json.loads(dump_path.read_text())
    if limit:
        rows = rows[:limit]
    tot = surv = rec = apps = wtot = wmatch = 0
    examples: list[tuple[str, str]] = []
    for sk, ct in rows:
        eterms = {_norm(t) for t in exam.get(sk, [])}
        if not eterms:
            continue
        cleaned = clean_odp_claims(ct)
        ct_norm = _norm(cleaned)
        try:
            claims = parse_claims(cleaned)
            if not claims:
                continue
            findings = us_ab(claims)
        except Exception:
            continue
        apps += 1
        wrefs = {_norm(f.get("reference_form", "")) for f in findings if isinstance(f, dict)}
        wterms = {_norm(f.get("term", "")) for f in findings if isinstance(f, dict)}
        wtot += len(wrefs)
        for et in eterms:
            tot += 1
            if et in ct_norm:
                surv += 1
            h = _head(et)
            if (et in wrefs) or (h in wterms) or any(
                h == w or h.endswith(" " + w) or w.endswith(" " + h) for w in wterms if w
            ):
                rec += 1
                if len(examples) < 10:
                    examples.append((sk, et))
        for wr in wrefs:
            if any(wr == e or _head(wr) in e for e in eterms):
                wmatch += 1
    return {
        "apps_run": apps, "rows": len(rows), "examiner_terms": tot,
        "survive_ocr": surv, "recalled": rec,
        "walker_findings": wtot, "walker_examiner_confirmed": wmatch,
        "examples": examples,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", type=Path, default=Path("/tmp/odp_examiner_claims.json"))
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    r = run(a.dump, a.limit)
    t, s, rc = r["examiner_terms"], r["survive_ocr"], r["recalled"]
    w, wm = r["walker_findings"], r["walker_examiner_confirmed"]
    print(f"apps run: {r['apps_run']}/{r['rows']}")
    print(f"examiner terms: {t}")
    print(f"  survive OCR in claim text (recall CEILING): {s} ({100*s/max(1,t):.0f}%)")
    print(f"  walker RECALLED: {rc} ({100*rc/max(1,t):.0f}% of all; "
          f"{100*rc/max(1,s):.0f}% of surviving)")
    print(f"walker findings: {w}; examiner-confirmed: {wm} ({100*wm/max(1,w):.1f}%)")
    print("spot-check matches:")
    for sk, et in r["examples"]:
        print(f"  {sk}: {et!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
