"""Phase 2b judging — round 1 §5 production pass.

Reads the 757-record CN+TW corpus from
`/Users/chrischen/Documents/Projects/Patent-Analyst-corpus/parquet/cn_tw_drafts/`,
constructs minimal CnPatentDocument / TwPatentDocument objects from the
Parquet-stored claim lists, runs the antecedent walker per draft, then
calls per_draft_judge.judge_draft() on every draft with ≥1 walker finding.

Mid-run halt: every 250 drafts judged, log progress + cost trajectory; if
projected cost exceeds 80% of cap by midpoint, halt cleanly with a partial
results artifact for user review.

Outputs:
- `tests/eval/phase2b_results.json`: full ensemble verdicts per draft
- `CC Output/2026-05-02_phase2b-judge-report.md`: aggregate metrics +
  cluster summaries for Phase 2c routing

Cost target: ~$45 mid (post-Opus-threshold-tweak 3→2). Cap: $60. Mid-run
halt at $48 trajectory.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

import pyarrow.parquet as pq
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

PATENTLINT_ROOT = Path("/Users/chrischen/Documents/Projects/Patent-Lint")
sys.path.insert(0, str(PATENTLINT_ROOT / "src"))

from patentlint.analysis.cn_claims import check_antecedent_basis_cn  # noqa: E402
from patentlint.analysis.tw_claims import check_antecedent_basis as check_antecedent_basis_tw  # noqa: E402
from patentlint.analysis.claims import check_antecedent_basis as check_antecedent_basis_us  # noqa: E402
from patentlint.models import Claim, CnPatentDocument, TwPatentDocument  # noqa: E402

from .per_draft_judge import (  # noqa: E402
    DraftEnsembleVerdict,
    FindingInput,
    SYSTEM_PROMPT_US_V1,
    SYSTEM_PROMPT_V2,
    ensemble_to_dict,
    judge_draft,
    load_keys,
)

CORPUS_PARQUET_DIR = Path(
    "/Users/chrischen/Documents/Projects/Patent-Analyst-corpus/parquet/cn_tw_drafts"
)
RESULTS_PATH = PATENTLINT_ROOT / "tests/eval/phase2b_results.json"
REPORT_PATH = Path(
    "/Users/chrischen/Library/Mobile Documents/com~apple~CloudDocs/CC Output"
    "/2026-05-02_phase2b-judge-report.md"
)

# Mid-run cost guard. Per-draft cost projection (post-2026-05-03 with
# proportional Opus + min_findings filter):
# Sonnet ~$0.045, gpt-5-mini ~$0.005, Opus on ~30% of drafts ~$0.03
# (proportional threshold = max(2, ceil(findings * 0.15)) — escalates only
# on substantive disagreement, not noise). Net ~$0.08/draft.
COST_PER_DRAFT_EST = 0.08
# Per Christopher's 2026-05-02 directive: do not cost-halt as long as
# cumulative round-1 spend stays under $200. This threshold is per-run;
# total round-1 spend is tracked in the closeout MD.
COST_HALT_THRESHOLD = 150.0
PROGRESS_LOG_EVERY = 25


# ---------- claim parsing (from raw text → Claim objects) ----------


import re

_CN_CLAIM_NUM_RE = re.compile(r"^\s*(\d+)\s*[\.、．]")
_CN_DEP_RE = re.compile(r"如?权利要求(\d+)|根据权利要求(\d+)")
_TW_CLAIM_NUM_RE = re.compile(r"^\s*(\d+)\s*[\.、．]")
_TW_DEP_RE = re.compile(r"如(?:申請專利範圍第)?[第]?(\d+)[項所]|根據[第]?(\d+)項")


def _parse_claim_text(
    raw: str, claim_id: int, jurisdiction: str
) -> Claim | None:
    """Parse a single claim string into a Claim object.

    `claim_id` is supplied by position in the input list (1-indexed) AS
    FALLBACK. Where the claim text begins with a `N.` prefix (most CN/US
    patents), we extract the actual claim number from the text — handles
    cases where the patent has gaps in numbering (cancelled / withdrawn
    claims that Google Patents skips). Verified 2026-05-03 against
    US20210105435A1 which has actual claim 14 at list position 13.

    For TW patents (bare-noun starts like `一種...`) and any other case
    without a numeric prefix, falls back to the supplied position-based
    `claim_id`.
    """
    if not raw or not raw.strip():
        return None

    # Try to extract actual patent claim number from leading "N." prefix.
    # Falls back to position-based claim_id when no prefix present.
    actual_id_match = re.match(r"^\s*(\d+)\s*[\.、．]", raw)
    if actual_id_match:
        claim_id = int(actual_id_match.group(1))

    if jurisdiction == "CN":
        dep_re = _CN_DEP_RE
    else:
        dep_re = _TW_DEP_RE

    deps: list[int] = []
    for dm in dep_re.finditer(raw):
        for g in dm.groups():
            if g:
                try:
                    deps.append(int(g))
                except ValueError:
                    pass
                break
    deps = list(dict.fromkeys(deps))  # dedup, preserve order

    return Claim(
        id=claim_id,
        text=raw.strip(),
        independent=(len(deps) == 0),
        multiple_dependent=(len(deps) > 1),
        method_claim=False,
        dependencies=deps,
    )


def build_doc_from_claims(
    claims_list: list[str], jurisdiction: str
) -> CnPatentDocument | TwPatentDocument | list[Claim] | None:
    """Construct a jurisdiction-appropriate doc from a raw claims list.

    - CN → `CnPatentDocument(claims=...)`
    - TW → `TwPatentDocument(claims=...)`
    - US → bare `list[Claim]` (US walker `check_antecedent_basis` takes a
      claim list directly, not a Document wrapper)
    - else → None

    claim_id is assigned by 1-based position in the input list; this matches
    Google Patents' rendering order which preserves the source claim sequence.
    """
    parsed: list[Claim] = []
    for idx, raw in enumerate(claims_list, 1):
        c = _parse_claim_text(raw, idx, jurisdiction)
        if c is not None:
            parsed.append(c)
    if not parsed:
        return None
    if jurisdiction == "CN":
        return CnPatentDocument(claims=parsed, input_format="google_patents_html")
    if jurisdiction == "TW":
        return TwPatentDocument(claims=parsed, input_format="google_patents_html")
    if jurisdiction == "US":
        return parsed
    return None


# ---------- corpus loader ----------


def load_corpus_records(parquet_dir: Path) -> list[dict]:
    """Load all corpus records from the partitioned Parquet directory,
    deduped by patent_id (keeping first occurrence — earliest ingest wins).

    Reads each Parquet file directly via `ParquetFile().read()` to avoid
    pyarrow.dataset's Hive-partition auto-discovery — the `jurisdiction`
    field is stored both in the Hive partition path AND in the row data,
    which collides on dataset merge.

    Multi-batch ingests (v1 + v2 + supplements) write separate parquet
    files; the same patent_id can appear in multiple files. Postgres
    `corpus_records` is UPSERT-deduped, but parquet just appends. This
    loader applies the same dedup at read time so judging doesn't waste
    LLM cost on duplicate patents.

    Returns list of dicts (one per unique draft) sorted by (jurisdiction,
    patent_id) for deterministic ordering.
    """
    raw_records: list[dict] = []
    for path in sorted(parquet_dir.glob("**/*.parquet")):
        table = pq.ParquetFile(path).read()
        rows = table.to_pylist()
        for row in rows:
            raw_records.append(row)

    # Dedup by patent_id, keep first occurrence
    seen_ids: set[str] = set()
    deduped: list[dict] = []
    for row in raw_records:
        pid = row.get("patent_id") or ""
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)
        deduped.append(row)
    deduped.sort(
        key=lambda r: (r.get("jurisdiction", ""), r.get("patent_id", ""))
    )
    return deduped


# ---------- walker invocation ----------


def run_walker_on_draft(record: dict) -> tuple[list[dict], dict[int, str]]:
    """Run the antecedent walker on one corpus record; return findings + claim
    text by id."""
    jurisdiction = record.get("jurisdiction", "")
    claims_list = record.get("claims") or []
    if not claims_list:
        return [], {}
    doc = build_doc_from_claims(claims_list, jurisdiction)
    if doc is None:
        return [], {}

    if jurisdiction == "CN":
        issues = list(check_antecedent_basis_cn(doc))
        claim_texts = {c.id: c.text for c in doc.claims}
    elif jurisdiction == "TW":
        issues = list(check_antecedent_basis_tw(doc))
        claim_texts = {c.id: c.text for c in doc.claims}
    elif jurisdiction == "US":
        # US walker takes list[Claim] directly; doc IS the claim list here.
        issues = list(check_antecedent_basis_us(doc))
        claim_texts = {c.id: c.text for c in doc}
    else:
        return [], {}

    return issues, claim_texts


def issue_to_finding(issue: dict, window: int = 30) -> FindingInput:
    claim_text = issue.get("claim_text") or ""
    term = issue.get("term") or ""
    offset = claim_text.find(term) if term else -1
    if offset < 0:
        offset = 0
        before = ""
        after = ""
    else:
        before = claim_text[max(0, offset - window) : offset]
        after = claim_text[offset + len(term) : offset + len(term) + window]
    return FindingInput(
        claim_id=int(issue.get("claim_id", 0)),
        term=term,
        reference_form=issue.get("reference_form") or "",
        char_offset=offset,
        context_before=before,
        context_after=after,
    )


# ---------- main loop ----------


async def _run(
    *,
    limit: int | None = None,
    fetch_concurrency: int = 4,
    skip_walker_zero: bool = True,
    jurisdictions: list[str] | None = None,
    min_findings: int = 3,
    output_results: Path = RESULTS_PATH,
    output_report: Path = REPORT_PATH,
    exclude_judged: list[Path] | None = None,
) -> dict:
    print(f"Loading corpus from {CORPUS_PARQUET_DIR} ...")
    records = load_corpus_records(CORPUS_PARQUET_DIR)
    print(f"Loaded {len(records)} corpus records")

    if jurisdictions:
        records = [r for r in records if r.get("jurisdiction") in jurisdictions]
        print(f"Filtered to jurisdictions={jurisdictions}: {len(records)} records")

    # Exclude already-judged records (from one or more prior results JSONs)
    # to enable supplemental Phase 2b runs that don't re-judge work already
    # done. Patent_ids in any provided JSON's `verdicts[].patent_id` are skipped.
    if exclude_judged:
        already: set[str] = set()
        for ej_path in exclude_judged:
            if not ej_path.exists():
                print(f"  exclude-judged: skip missing {ej_path}")
                continue
            try:
                ej_data = json.loads(ej_path.read_text())
            except json.JSONDecodeError as exc:
                print(f"  exclude-judged: skip invalid JSON at {ej_path}: {exc}")
                continue
            for v in ej_data.get("verdicts", []):
                pid = v.get("patent_id")
                if pid:
                    already.add(pid)
        before = len(records)
        records = [r for r in records if r.get("patent_id") not in already]
        print(
            f"Excluded {before - len(records)} already-judged records "
            f"(from {len(exclude_judged)} prior results files); "
            f"{len(records)} remaining"
        )

    if limit:
        records = records[:limit]
        print(f"Limited to first {limit} records")

    # Phase A: walker pass (sequential, fast — the LLM calls dominate wall-clock)
    drafts_to_judge: list[tuple[dict, list[FindingInput], dict[int, str]]] = []
    walker_zero_count = 0
    walker_error_count = 0
    walker_below_min_count = 0
    for rec in records:
        try:
            issues, claim_texts = run_walker_on_draft(rec)
        except Exception as exc:
            walker_error_count += 1
            if walker_error_count <= 5:
                print(f"  walker error on {rec.get('patent_id')}: {exc!r}")
            continue
        if not issues:
            walker_zero_count += 1
            if not skip_walker_zero:
                drafts_to_judge.append((rec, [], claim_texts))
            continue
        # Lever 2: skip drafts with too few walker findings — low cluster
        # signal at high per-draft cost. Drafts contribute weakly to walker-
        # round trigger evidence; trim cleanly.
        if len(issues) < min_findings:
            walker_below_min_count += 1
            continue
        findings = [issue_to_finding(i) for i in issues]
        drafts_to_judge.append((rec, findings, claim_texts))

    print(
        f"Walker pass: {len(drafts_to_judge)} drafts with ≥{min_findings} findings, "
        f"{walker_zero_count} skipped (0 findings), "
        f"{walker_below_min_count} skipped (<{min_findings} findings, low signal), "
        f"{walker_error_count} skipped (walker error)"
    )

    if not drafts_to_judge:
        print("No drafts to judge; exiting.")
        return {"drafts_judged": 0, "verdicts": []}

    # Phase B: LLM judging with mid-run halt
    anth_key, oai_key = load_keys()
    anth = AsyncAnthropic(api_key=anth_key)
    oai = AsyncOpenAI(api_key=oai_key)

    sem = asyncio.Semaphore(fetch_concurrency)

    def _system_prompt_for(jurisdiction: str) -> str:
        # US claim language = English antecedent rules (Pattern A: a/an;
        # Pattern B: comprising-listing). CN+TW share iter2b's prompt because
        # both use 所述/該/前述 reference markers + 一/一個/一種 introducers.
        return SYSTEM_PROMPT_US_V1 if jurisdiction == "US" else SYSTEM_PROMPT_V2

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
                )
                return rec, ensemble
            except Exception as exc:
                print(f"  judge error on {rec['patent_id']}: {exc!r}")
                return rec, None

    print(
        f"Judging {len(drafts_to_judge)} drafts (concurrency={fetch_concurrency})..."
    )

    # Run all in chunks of PROGRESS_LOG_EVERY for periodic progress + cost-halt
    t0 = time.monotonic()
    all_results: list[tuple[dict, DraftEnsembleVerdict | None]] = []
    halted = False
    cost_actual = 0.0  # accumulated from API usage telemetry
    for chunk_start in range(0, len(drafts_to_judge), PROGRESS_LOG_EVERY):
        chunk = drafts_to_judge[chunk_start : chunk_start + PROGRESS_LOG_EVERY]
        chunk_results = await asyncio.gather(*[_judge_one(a) for a in chunk])
        all_results.extend(chunk_results)
        # Accumulate ACTUAL cost from API token-usage (replaces stale
        # COST_PER_DRAFT_EST constant; verified accurate against
        # platform.claude.com billing within ~5% per 2026-05-03 reconciliation).
        for _rec, ensemble in chunk_results:
            if ensemble is not None:
                cost_actual += ensemble.total_cost()
        n_done = len(all_results)
        elapsed = time.monotonic() - t0
        per_draft_actual = elapsed / max(1, n_done)
        eta = per_draft_actual * (len(drafts_to_judge) - n_done)
        print(
            f"  progress: {n_done}/{len(drafts_to_judge)} drafts "
            f"({100*n_done/len(drafts_to_judge):.0f}%), "
            f"elapsed {elapsed:.0f}s, ETA {eta:.0f}s, "
            f"cost=${cost_actual:.2f} (actual from API usage)"
        )
        # Cost halt — extrapolated from actual telemetry.
        projected_total = (cost_actual / max(1, n_done)) * len(drafts_to_judge)
        if projected_total > COST_HALT_THRESHOLD:
            print(
                f"  HALT — projected total ${projected_total:.2f} exceeds "
                f"halt threshold ${COST_HALT_THRESHOLD:.2f}. "
                f"Stopping at {n_done} drafts judged."
            )
            halted = True
            break

    elapsed = time.monotonic() - t0
    print(f"\nJudging complete: {len(all_results)} drafts in {elapsed:.0f}s")

    # Aggregate metrics
    verdict_dump: list[dict] = []
    used_opus = 0
    findings_total = 0
    final_cat_counts: Counter = Counter()
    per_jurisdiction_findings: dict[str, Counter] = defaultdict(Counter)
    per_jurisdiction_drafts: Counter = Counter()
    per_applicant_type: dict[str, Counter] = defaultdict(Counter)

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
        if ensemble.used_opus:
            used_opus += 1
        per_jurisdiction_drafts[rec["jurisdiction"]] += 1
        for v in ensemble.final_verdicts:
            findings_total += 1
            final_cat_counts[v.category] += 1
            per_jurisdiction_findings[rec["jurisdiction"]][v.category] += 1
            apt = rec.get("applicant_type") or "unknown"
            per_applicant_type[apt][v.category] += 1

    return {
        "drafts_loaded": len(records),
        "drafts_with_findings": len(drafts_to_judge),
        "drafts_judged": len(verdict_dump),
        "drafts_escalated_to_opus": used_opus,
        "findings_total": findings_total,
        "halted": halted,
        "elapsed_sec": elapsed,
        "actual_cost": cost_actual,  # from API usage telemetry
        "estimated_cost": cost_actual,  # alias for backward compat with old reports
        "final_category_distribution": dict(final_cat_counts),
        "per_jurisdiction_drafts": dict(per_jurisdiction_drafts),
        "per_jurisdiction_findings": {
            k: dict(v) for k, v in per_jurisdiction_findings.items()
        },
        "per_applicant_type": {
            k: dict(v) for k, v in per_applicant_type.items()
        },
        "verdicts": verdict_dump,
    }


def render_report(result: dict) -> str:
    lines: list[str] = []

    def line(s: str = "") -> None:
        lines.append(s)

    line("# Phase 2b Judging Report — 2026-05-02")
    line()
    if result["halted"]:
        line("**STATUS: HALTED MID-RUN (cost trajectory exceeded threshold).**")
    else:
        line("**STATUS: complete.**")
    line()
    line(f"- Corpus loaded: {result['drafts_loaded']}")
    line(f"- Drafts with ≥1 walker finding: {result['drafts_with_findings']}")
    line(f"- Drafts judged: {result['drafts_judged']}")
    line(f"- Drafts escalated to Opus: {result['drafts_escalated_to_opus']} "
         f"({100*result['drafts_escalated_to_opus']/max(1,result['drafts_judged']):.0f}%)")
    line(f"- Total findings classified: {result['findings_total']}")
    line(f"- Wall-clock: {result['elapsed_sec']:.0f}s")
    line(f"- Estimated cost: ${result['estimated_cost']:.2f}")
    line()

    line("## Final category distribution (all jurisdictions)")
    line()
    total = result["findings_total"] or 1
    for cat, n in sorted(
        result["final_category_distribution"].items(),
        key=lambda x: -x[1],
    ):
        line(f"- {cat}: {n} ({100*n/total:.0f}%)")
    line()

    line("## Per-jurisdiction breakdown")
    line()
    for jur, drafts in result["per_jurisdiction_drafts"].items():
        line(f"### {jur} (drafts: {drafts})")
        cat_dist = result["per_jurisdiction_findings"].get(jur, {})
        sub_total = sum(cat_dist.values()) or 1
        for cat, n in sorted(cat_dist.items(), key=lambda x: -x[1]):
            line(f"- {cat}: {n} ({100*n/sub_total:.0f}%)")
        line()

    line("## Per-applicant-type breakdown")
    line()
    for apt, cat_dist in sorted(
        result["per_applicant_type"].items(),
        key=lambda x: -sum(x[1].values()),
    ):
        sub_total = sum(cat_dist.values()) or 1
        line(f"- **{apt}** (n={sub_total}): "
             + ", ".join(f"{k}={v}" for k, v in sorted(cat_dist.items(), key=lambda x: -x[1])))
    line()

    line("## Recommendation for Phase 2c (Claire spot-check)")
    line()
    walker_fp_n = result["final_category_distribution"].get("walker_fp", 0)
    legit_n = result["final_category_distribution"].get("legit_drafting_error", 0)
    line(f"- Pass 1 (~30 min): sample 15 unanimous walker_fp verdicts "
         f"(out of {walker_fp_n} total walker_fp findings; sampling "
         f"stratified by jurisdiction × applicant_type). Confirm walker "
         f"FP rate before any walker-round trigger evidence ships.")
    line(f"- Pass 2 (~50-75 min): sample 10-15 disagreement cases — "
         f"prioritize Opus-resolved drafts where Opus disagreed with "
         f"both Sonnet and gpt-5-mini, and any case where the verdict "
         f"would silence a `protect:true` ground-truth label "
         f"(post-2026-05-02 demotions, the protect:true cluster is "
         f"smaller and validates faster).")
    line()

    return "\n".join(lines)


async def _main_async(args: argparse.Namespace) -> int:
    output_results = (
        Path(args.output_results) if args.output_results else RESULTS_PATH
    )
    output_report = (
        Path(args.output_report) if args.output_report else REPORT_PATH
    )

    exclude_judged_paths = (
        [Path(p) for p in args.exclude_judged] if args.exclude_judged else None
    )
    result = await _run(
        limit=args.limit,
        fetch_concurrency=args.fetch_concurrency,
        jurisdictions=args.jurisdictions,
        min_findings=args.min_findings,
        output_results=output_results,
        output_report=output_report,
        exclude_judged=exclude_judged_paths,
    )

    output_results.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nResults written to {output_results}")

    report = render_report(result)
    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text(report, encoding="utf-8")
    print(f"Report written to {output_report}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 2b judging on the 757-record CN+TW corpus."
    )
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit to first N drafts for smoke test.")
    parser.add_argument("--fetch-concurrency", type=int, default=8,
                        help="Per-draft LLM call concurrency.")
    parser.add_argument("--jurisdictions", nargs="+", default=None,
                        choices=["CN", "TW", "US"],
                        help="Filter corpus to specific jurisdictions only.")
    parser.add_argument("--min-findings", type=int, default=3,
                        help="Skip drafts with fewer than N walker findings "
                             "(Lever 2 — low cluster signal at high per-draft "
                             "cost).")
    parser.add_argument("--output-results", type=str, default=None,
                        help="Override results JSON output path.")
    parser.add_argument("--output-report", type=str, default=None,
                        help="Override report MD output path.")
    parser.add_argument("--exclude-judged", nargs="+", default=None,
                        help="One or more prior results JSON files; their "
                             "patent_ids are skipped (avoids re-judging).")
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    sys.exit(main())
