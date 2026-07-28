# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# parse_examiner_112.py - turn EdgeXpert's real examiner §112 office-action prose
# into term-level antecedent-basis LEGIT labels (ADR-159, WS-A1). Examiner
# rejections name the exact limitation ("insufficient antecedent basis for the
# limitation 'the X'") - version-robust ground truth that sidesteps claim-number
# alignment. Restricted to the/said references (genuine antecedent-basis defects;
# a/an are introductions). Output: tests/eval/us_examiner_legit.json (gitignored):
#   { application_source_key: ["the x", "said y", ...] }
# Run with the Patent-Analyst venv (has psycopg2); reads ANALYST_CORPUS_DATABASE_URL
# from ~/Documents/Projects/Patent-Analyst/.env.
from __future__ import annotations

import json
import re
from pathlib import Path

PA_ENV = Path.home() / "Documents/Projects/Patent-Analyst/.env"
OUT = Path(__file__).resolve().parent / "us_examiner_legit.json"

_Q = r'["“‘’”\']'
_QC = r'[^"“‘’”\']'
_PATS = [
    re.compile(r"(?:insufficient|lack(?:s|ing)?|no|improper|without|proper)\s+(?:proper\s+|adequate\s+|clear\s+)?"
               r"antecedent basis for\s+(?:the\s+(?:limitation|term|recitation|phrase|element|expression|word|feature)s?\s*)?"
               + _Q + "(" + _QC + r"{2,50})" + _Q, re.I),
    re.compile(_Q + "(" + _QC + r"{2,50})" + _Q + r"[^.]{0,70}?(?:insufficient|lacks?|no|improper|without)\s+"
               r"(?:proper\s+|adequate\s+)?antecedent basis", re.I),
    re.compile(r"(?:the\s+(?:limitation|term|recitation|phrase)s?\s*)" + _Q + "(" + _QC + r"{2,50})" + _Q
               + r"[^.]{0,90}antecedent basis", re.I),
]
_THIS = re.compile(r"antecedent basis for this limitation", re.I)
_QUOTE = re.compile(_Q + "(" + _QC + r"{2,50})" + _Q)


def parse(text: str) -> set[str]:
    found = set()
    for p in _PATS:
        for m in p.finditer(text):
            found.add(m.group(1).strip().strip(".").lower())
    for m in _THIS.finditer(text):
        qs = _QUOTE.findall(text[max(0, m.start() - 160):m.start()])
        if qs:
            found.add(qs[-1].strip().strip(".").lower())
    # Keep only genuine antecedent references (the/said), <=7 words.
    return {f for f in found if (f.startswith("the ") or f.startswith("said ")) and len(f.split()) <= 7}


def _db_url() -> str:
    for line in PA_ENV.read_text().splitlines():
        if line.startswith("ANALYST_CORPUS_DATABASE_URL"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("ANALYST_CORPUS_DATABASE_URL not found")


def main() -> int:
    import psycopg2
    conn = psycopg2.connect(_db_url(), connect_timeout=30)
    cur = conn.cursor()
    cur.execute("SELECT source_key, section_112_text FROM corpus_oa_actions "
                "WHERE section_112_text ILIKE '%antecedent basis%'")
    rows = [(k, t) for k, t in cur.fetchall() if t]
    conn.close()
    labels: dict[str, set] = {}
    hit = 0
    for k, t in rows:
        f = parse(t)
        if f:
            hit += 1
            labels.setdefault(k, set()).update(f)
    OUT.write_text(json.dumps({k: sorted(v) for k, v in labels.items()}, ensure_ascii=False, indent=1))
    insts = sum(len(v) for v in labels.values())
    print(f"antecedent OAs: {len(rows)} | with extracted term: {hit} ({100*hit/max(len(rows),1):.0f}%)")
    print(f"apps with labels: {len(labels)} | term instances: {insts} | distinct terms: "
          f"{len({x for v in labels.values() for x in v})}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
