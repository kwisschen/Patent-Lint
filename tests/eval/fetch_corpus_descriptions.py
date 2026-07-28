# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# fetch_corpus_descriptions.py - pull Google-Patents description bodies for the
# FULL round-1 corpus (not just the supplement_v2 subset), so spec-support and
# ref-numeral can be probed at corpus scale and `term_in_spec` activates for the
# antecedent confidence signal. Reuses fetch_tw_descriptions' polite fetcher;
# resumable; writes the same per-jurisdiction cache files (gitignored).
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import httpx  # noqa: E402

import round1_corpus_harness as h  # noqa: E402
from fetch_tw_descriptions import fetch_one, output_path_for  # noqa: E402

LANG = {"TW": "zh", "CN": "zh", "US": "en"}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
    )
}


def run(juris, sleep=1.5):
    pids = sorted({r["patent_id"] for r in h.load_corpus(juris)})
    out = output_path_for(juris)
    cache = json.loads(out.read_text()) if out.exists() else {}
    need = [p for p in pids if not (cache.get(p) or {}).get("description")]
    print(f"[{juris}] corpus={len(pids)} need={len(need)}", flush=True)
    with httpx.Client(headers=HEADERS) as client:
        for i, pid in enumerate(need):
            cache[pid] = fetch_one(client, pid, lang=LANG[juris])
            if (i + 1) % 20 == 0:
                out.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
                print(f"  [{juris} {i+1}/{len(need)}] {pid} "
                      f"chars={len(cache[pid].get('description') or '')}", flush=True)
            time.sleep(sleep)
    out.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    have = sum(1 for p in pids if (cache.get(p) or {}).get("description"))
    print(f"[{juris}] DONE - corpus coverage {have}/{len(pids)}", flush=True)


def main():
    jurs = sys.argv[1:] or ["CN", "TW", "US"]
    for j in jurs:
        run(j)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
