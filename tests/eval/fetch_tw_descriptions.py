# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Fetch description bodies for TW supplement_v2 patents from Google Patents.

Path 1 of the TIPO-style hybrid antecedent measurement (2026-05-05).
Earlier probe established Google Patents serves description body for TW
patents under /zh and /en mode (we saw 14K-39K Chinese chars per page).
Strict 符號說明 section markup is rare (only 1 of 6 sample patents had
any marker) — we extract whole description text and let downstream
analysis compute term_in_description as the corpus-measurable signal.

Output: ``tests/eval/tw_descriptions.json`` keyed by patent_id with
``{"description": str, "symbol_table_text": str | None}``. Resumable —
existing entries are skipped.

Usage::

    python tests/eval/fetch_tw_descriptions.py [--limit N] [--sleep SEC]

Polite defaults: 1.5 sec per request, single concurrent connection.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SUPPLEMENT_V2 = PROJECT_ROOT / "tests/eval/phase2b_results_supplement_v2.json"
OUTPUT = PROJECT_ROOT / "tests/eval/tw_descriptions.json"


def output_path_for(jurisdiction: str) -> Path:
    """Per-jurisdiction cache file path."""
    return PROJECT_ROOT / f"tests/eval/{jurisdiction.lower()}_descriptions.json"


def extract_description(html: str) -> tuple[str, str | None]:
    """Return (description_text, symbol_table_text|None) from raw HTML.

    Strategy: strip all tags, collapse whitespace, return as-is.
    Symbol-table extraction tries to isolate the section between
    `符號說明` (or variants) heading and the next section break.
    """
    plain = re.sub(r"<[^>]+>", " ", html)
    plain = re.sub(r"\s+", " ", plain).strip()

    # Try to isolate symbol table — common headings.
    symbol_text: str | None = None
    for marker in (
        "【符號說明】",
        "符號說明",
        "主要元件符號",
        "附圖標記說明",
        "元件代號說明",
    ):
        idx = plain.find(marker)
        if idx >= 0:
            tail = plain[idx + len(marker):]
            # Cap at next strong section boundary or end of description.
            stop_re = re.compile(
                r"【(?:申請專利範圍|摘要|圖式|實施方式|發明|技術領域)】"
                r"|專利申請範圍|請求項\s*1"
            )
            m = stop_re.search(tail)
            if m:
                symbol_text = tail[: m.start()].strip()
            else:
                symbol_text = tail[:5000].strip()
            break

    return plain, symbol_text


def fetch_one(client: httpx.Client, patent_id: str, lang: str = "zh") -> dict | None:
    url = f"https://patents.google.com/patent/{patent_id}/{lang}"
    try:
        r = client.get(url, follow_redirects=True, timeout=25)
        if r.status_code != 200:
            return {"error": f"http_{r.status_code}", "description": "", "symbol_table_text": None}
        desc, st = extract_description(r.text)
        return {
            "description": desc,
            "symbol_table_text": st,
            "html_size": len(r.text),
        }
    except Exception as e:
        return {"error": str(e)[:120], "description": "", "symbol_table_text": None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="Cap fetch count for testing")
    ap.add_argument("--sleep", type=float, default=1.5, help="Seconds between requests")
    ap.add_argument(
        "--jurisdiction",
        choices=["TW", "CN", "US"],
        default="TW",
        help="Which jurisdiction's supplement_v2 patents to fetch",
    )
    args = ap.parse_args()

    verdicts = json.loads(SUPPLEMENT_V2.read_text())["verdicts"]
    pids = sorted({v["patent_id"] for v in verdicts if v.get("jurisdiction") == args.jurisdiction})
    if args.limit:
        pids = pids[: args.limit]

    output = output_path_for(args.jurisdiction)
    lang = {"TW": "zh", "CN": "zh", "US": "en"}[args.jurisdiction]

    cache: dict[str, dict] = {}
    if output.exists():
        cache = json.loads(output.read_text())
        print(f"Loaded cache ({output.name}): {len(cache)} entries")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
        )
    }
    with httpx.Client(headers=headers) as client:
        n_new = 0
        n_st = 0
        for i, pid in enumerate(pids):
            if pid in cache and "description" in cache[pid] and cache[pid]["description"]:
                # Already fetched — re-extract symbol_table if missing
                continue
            rec = fetch_one(client, pid, lang=lang)
            cache[pid] = rec
            n_new += 1
            if rec and rec.get("symbol_table_text"):
                n_st += 1
            if n_new % 10 == 0:
                output.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
                desc_len = len(rec.get("description") or "") if rec else 0
                print(f"  [{i+1}/{len(pids)}] {pid} desc_chars={desc_len} st={'Y' if rec.get('symbol_table_text') else '-'}")
            time.sleep(args.sleep)

    output.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    total_with_st = sum(1 for v in cache.values() if v.get("symbol_table_text"))
    total_with_desc = sum(1 for v in cache.values() if v.get("description"))
    print()
    print(f"Done. Total in cache: {len(cache)}")
    print(f"  with description body: {total_with_desc}")
    print(f"  with extracted 符號說明 section: {total_with_st}")
    print(f"  fetched this run: {n_new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
