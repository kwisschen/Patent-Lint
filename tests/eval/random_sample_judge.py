# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Random uniform-sample judging for apples-to-apples corpus precision.

Phase 2b's `phase2b_judging.py` samples weighted by walker-finding count
(picks heavy-FP drafts preferentially) — useful for cluster discovery
but produces worst-case precision numbers. This script samples uniformly
at random to match the CLAUDE.md baseline measurement methodology.

No exclude-judged filter (full corpus pool), no min-findings filter
(includes light drafts that drafters typically check), no weighting.

Usage:
    python -m tests.eval.random_sample_judge \\
        --target-per-jurisdiction 100 \\
        --random-seed 20260505
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

PATENTLINT_ROOT = Path("/Users/chrischen/Documents/Projects/Patent-Lint")
sys.path.insert(0, str(PATENTLINT_ROOT / "src"))

from .phase2b_judging import (  # noqa: E402
    CORPUS_PARQUET_DIR,
    DraftEnsembleVerdict,
    SYSTEM_PROMPT_US_V1,
    SYSTEM_PROMPT_V2,
    ensemble_to_dict,
    issue_to_finding,
    load_corpus_records,
    run_walker_on_draft,
)
from .per_draft_judge import judge_draft, load_keys  # noqa: E402


async def _run(
    *,
    target_per_jurisdiction: int,
    random_seed: int,
    no_opus: bool,
    cost_cap: float,
    output_path: Path,
) -> dict:
    print(f"Loading corpus from {CORPUS_PARQUET_DIR} ...")
    records = load_corpus_records(CORPUS_PARQUET_DIR)
    print(f"Loaded {len(records)} corpus records")

    rng = random.Random(random_seed)
    by_juris: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        j = r.get("jurisdiction")
        if j in ("CN", "TW", "US"):
            by_juris[j].append(r)

    sampled: list[dict] = []
    for juris, recs in sorted(by_juris.items()):
        if target_per_jurisdiction >= len(recs):
            print(f"  {juris}: target {target_per_jurisdiction} >= {len(recs)}; taking all")
            sampled.extend(recs)
        else:
            picks = rng.sample(recs, target_per_jurisdiction)
            sampled.extend(picks)
            print(f"  {juris}: random sample {target_per_jurisdiction}/{len(recs)}")

    drafts_to_judge = []
    for rec in sampled:
        try:
            issues, claim_texts = run_walker_on_draft(rec)
        except Exception as exc:
            print(f"  walker error on {rec.get('patent_id')}: {exc!r}")
            continue
        if not issues:
            continue
        findings = [issue_to_finding(i) for i in issues]
        drafts_to_judge.append((rec, findings, claim_texts))

    print(f"Walker pass: {len(drafts_to_judge)} drafts with ≥1 finding")
    if not drafts_to_judge:
        return {"verdicts": []}

    anth_key, oai_key = load_keys()
    anth = AsyncAnthropic(api_key=anth_key, timeout=240.0, max_retries=3)
    oai = AsyncOpenAI(api_key=oai_key, timeout=240.0, max_retries=3)
    sem = asyncio.Semaphore(4)

    def _system_prompt_for(juris: str) -> str:
        return SYSTEM_PROMPT_US_V1 if juris == "US" else SYSTEM_PROMPT_V2

    async def _judge_one(args):
        rec, findings, claim_texts = args
        if not findings:
            return rec, None
        async with sem:
            try:
                ensemble = await judge_draft(
                    fixture_key=rec["patent_id"],
                    jurisdiction=rec["jurisdiction"],
                    claim_chain_texts=claim_texts,
                    findings=findings,
                    anthropic_client=anth,
                    openai_client=oai,
                    system_prompt=_system_prompt_for(rec["jurisdiction"]),
                    no_opus=no_opus,
                )
                return rec, ensemble
            except Exception as exc:
                print(f"  judge error on {rec['patent_id']}: {exc!r}")
                return rec, None

    print(f"Judging {len(drafts_to_judge)} drafts (concurrency=4)...")
    t0 = time.monotonic()
    all_results: list[tuple[dict, DraftEnsembleVerdict | None]] = []
    cost_actual = 0.0
    halted = False
    for chunk_start in range(0, len(drafts_to_judge), 25):
        chunk = drafts_to_judge[chunk_start : chunk_start + 25]
        chunk_results = await asyncio.gather(*[_judge_one(a) for a in chunk])
        all_results.extend(chunk_results)
        for _rec, ensemble in chunk_results:
            if ensemble is not None:
                cost_actual += ensemble.total_cost()
        n_done = len(all_results)
        elapsed = time.monotonic() - t0
        per_draft = cost_actual / max(1, n_done)
        proj = per_draft * len(drafts_to_judge)
        print(
            f"  progress: {n_done}/{len(drafts_to_judge)} "
            f"elapsed={elapsed:.0f}s cost=${cost_actual:.2f} "
            f"per-draft=${per_draft:.4f} projected=${proj:.2f}"
        )
        if cost_actual > cost_cap or proj > cost_cap:
            print(f"  HALT at ${cost_actual:.2f} (cap ${cost_cap:.2f})")
            halted = True
            break

    elapsed = time.monotonic() - t0
    print(f"\nJudging complete: {len(all_results)} drafts in {elapsed:.0f}s")

    verdict_dump = []
    for rec, ensemble in all_results:
        if ensemble is None:
            continue
        verdict_dump.append({
            "patent_id": rec["patent_id"],
            "jurisdiction": rec["jurisdiction"],
            "applicant_type": rec.get("applicant_type"),
            "filing_year": rec.get("filing_year"),
            "ensemble": ensemble_to_dict(ensemble),
        })

    return {
        "drafts_judged": len(verdict_dump),
        "elapsed_sec": elapsed,
        "actual_cost": cost_actual,
        "halted": halted,
        "random_seed": random_seed,
        "verdicts": verdict_dump,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-per-jurisdiction", type=int, default=100)
    parser.add_argument("--random-seed", type=int, default=20260505)
    parser.add_argument("--no-opus", action="store_true", default=True)
    parser.add_argument("--cost-cap", type=float, default=25.0)
    parser.add_argument("--output", type=str,
                        default=str(PATENTLINT_ROOT / "tests/eval/phase2b_results_random_v1.json"))
    args = parser.parse_args()

    out = asyncio.run(_run(
        target_per_jurisdiction=args.target_per_jurisdiction,
        random_seed=args.random_seed,
        no_opus=args.no_opus,
        cost_cap=args.cost_cap,
        output_path=Path(args.output),
    ))
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nResults written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
