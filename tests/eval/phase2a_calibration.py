"""Phase 2a calibration — round 1 §4 prompt R&D against the 21 hand-labeled
fixtures.

Per `2026-05-02_cn-tw-small-corpus-design.md` §4:

- Per-draft mode (Sonnet 4.6 primary + gpt-5-mini cross + Opus 4.7 tiebreaker)
- One LLM call per fixture, judging ALL current walker emits
- Compare verdicts to ground-truth labels (where available)
- Compute three thresholds:
    T1 (inter-judge Sonnet ↔ gpt-5-mini, pre-tiebreaker): ≥80%
    T2 (ensemble = legit_drafting_error when label.protect=true): ≥85%
    T3 (ensemble = walker_fp when label.category ∈ walker_fp.* / walker_bug.*): ≥75%
- Identify disagreement clusters for next-iteration prompt tuning

Iter 1 uses `per_draft_judge.SYSTEM_PROMPT_V2` (Phase 2a baseline). Subsequent
iterations swap in revised prompt text; the harness keeps the same calibration
substrate so threshold metrics are directly comparable across iterations.
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
from typing import Optional

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

PATENTLINT_ROOT = Path("/Users/chrischen/Documents/Projects/Patent-Lint")
sys.path.insert(0, str(PATENTLINT_ROOT / "src"))

from patentlint.analysis.cn_claims import check_antecedent_basis_cn  # noqa: E402
from patentlint.analysis.tw_claims import check_antecedent_basis  # noqa: E402
from patentlint.parser.docx_loader import load_docx_cn, load_docx_tw  # noqa: E402
from patentlint.parser.sections_cn import extract_cn_sections_from_docx  # noqa: E402
from patentlint.parser.sections_tw import extract_tw_sections  # noqa: E402

from .per_draft_judge import (  # noqa: E402
    DraftEnsembleVerdict,
    FindingInput,
    SYSTEM_PROMPT_V2,
    _pair_verdict_to_finding,
    ensemble_to_dict,
    judge_draft,
    load_keys,
)

CN_LABELS = PATENTLINT_ROOT / "tests/fixtures/cn/antecedent_labels_cn.json"
CN_BASELINE = PATENTLINT_ROOT / "tests/fixtures/cn/local/baseline_phase8c.json"
TW_LABELS = PATENTLINT_ROOT / "tests/fixtures/tw/antecedent_labels.json"
TW_FIXTURES_DIR = PATENTLINT_ROOT / "tests/fixtures/tw/local"

CC_OUTPUT_DIR = Path(
    "/Users/chrischen/Library/Mobile Documents/com~apple~CloudDocs/CC Output"
)


# ---------- label utilities ----------


def map_label_to_ensemble(label_category: str) -> Optional[str]:
    """Coarse-grain label → ensemble category. Returns None for entries that
    don't map (excludes 'unclassified' Stage 3 seeds, 'ambig', 'semantic_*').
    """
    if (
        label_category.startswith("walker_fp.")
        or label_category.startswith("walker_bug.")
        or label_category == "tw_contamination"
    ):
        return "walker_fp"
    if (
        label_category.startswith("miss_intro.")
        or label_category == "propagation_gap"
    ):
        return "coverage_gap"
    if label_category == "legit_drafting_error":
        return "legit_drafting_error"
    return None


def load_labels(path: Path) -> list[dict]:
    """Read a labels file's `labels` array, dropping unclassified seeds."""
    data = json.loads(path.read_text())
    return [
        lab
        for lab in data.get("labels", [])
        if lab.get("category") not in (None, "", "unclassified")
    ]


# ---------- fixture loaders ----------


def load_cn_fixture_paths() -> dict[str, Path]:
    d = json.loads(CN_BASELINE.read_text())
    return {
        key: (PATENTLINT_ROOT / rec["fixture_path"]).resolve()
        for key, rec in d["fixtures"].items()
    }


def discover_tw_fixture_paths(labels: list[dict]) -> dict[str, Path]:
    """Map fixture_key (from label) → .docx path under tests/fixtures/tw/local/.

    TW labels reference fixtures by basename (e.g.,
    '110P000158US.JP.EPC派譯版-FV'). We look for .docx or .DOCX with that name.
    Synthetic fixtures (tw_*) are not real .docx — skip them in the calibration.
    """
    out: dict[str, Path] = {}
    fixture_keys = {lab.get("fixture") for lab in labels if lab.get("fixture")}
    for key in fixture_keys:
        if not key or key.startswith("tw_") or key == "spec1":
            # Synthetic / spec-only; not real claim-text drafts
            continue
        for ext in (".docx", ".DOCX"):
            candidate = TW_FIXTURES_DIR / f"{key}{ext}"
            if candidate.exists():
                out[key] = candidate
                break
    return out


# ---------- walker runners ----------


def _collect_all_claim_texts(doc) -> dict[int, str]:
    """Pull every claim's text from a parsed CnPatentDocument or
    TwPatentDocument. Cross-branch sibling antecedents (e.g., `第一训练信号`
    introduced in claim 80 and referenced in claim 82) are only visible to
    the LLM when ALL claims are passed, not just the ones with findings.
    """
    out: dict[int, str] = {}
    claims_attr = getattr(doc, "claims", None)
    if not claims_attr:
        return out
    for claim in claims_attr:
        cid = getattr(claim, "claim_id", None) or getattr(claim, "id", None)
        text = getattr(claim, "text", None) or getattr(claim, "body", None)
        if cid is not None and text:
            out[int(cid)] = text
    return out


def run_cn_walker_for_fixture(fixture_path: Path) -> tuple[list[dict], dict[int, str]]:
    """Run CN antecedent walker; return (issues, claim_text_by_id).

    `claim_text_by_id` keys are claim_ids; values are the verbatim claim
    body for EVERY claim in the fixture. Used as the per-draft prompt's
    "Claim chain" section so cross-branch sibling references are visible.
    Falls back to walker-emitted claim_text when doc-level extraction is
    empty (e.g., synthetic fixtures).
    """
    loaded = load_docx_cn(fixture_path)
    doc = extract_cn_sections_from_docx(loaded.sections)
    issues = list(check_antecedent_basis_cn(doc))
    claim_text_by_id = _collect_all_claim_texts(doc)
    if not claim_text_by_id:
        for issue in issues:
            cid = issue.get("claim_id")
            ct = issue.get("claim_text")
            if cid is not None and ct and cid not in claim_text_by_id:
                claim_text_by_id[cid] = ct
    return issues, claim_text_by_id


def run_tw_walker_for_fixture(fixture_path: Path) -> tuple[list[dict], dict[int, str]]:
    """Run TW antecedent walker; matches `_phase8b_harness.py`'s call pattern."""
    loaded = load_docx_tw(fixture_path)
    doc = extract_tw_sections(loaded.paragraphs)
    issues = list(check_antecedent_basis(doc))
    claim_text_by_id = _collect_all_claim_texts(doc)
    if not claim_text_by_id:
        for issue in issues:
            cid = issue.get("claim_id")
            ct = issue.get("claim_text")
            if cid is not None and ct and cid not in claim_text_by_id:
                claim_text_by_id[cid] = ct
    return issues, claim_text_by_id


# ---------- finding builders ----------


def issue_to_finding(issue: dict, window: int = 30) -> FindingInput:
    """Convert a walker issue dict to a per-draft FindingInput."""
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


def find_label_for_finding(
    labels_by_fixture: dict[str, list[dict]],
    fixture_key: str,
    finding: FindingInput,
) -> Optional[dict]:
    """Match a finding to its ground-truth label (if any)."""
    candidates = labels_by_fixture.get(fixture_key, [])
    for lab in candidates:
        if (
            lab.get("claim_id") == finding.claim_id
            and lab.get("term") == finding.term
            and lab.get("reference_form") == finding.reference_form
        ):
            return lab
    return None


# ---------- threshold computation ----------


def compute_thresholds(
    labeled_results: list[dict],
) -> dict:
    """Compute T1/T2/T3 from per-fixture results.

    Inter-judge agreement (T1) is computed at the per-FINDING level: for each
    judged finding, did Sonnet and gpt-5-mini agree on category (BEFORE Opus
    tiebreaker)?
    """
    if not labeled_results:
        return {
            "judged_count": 0,
            "threshold_1_inter_judge": None,
            "threshold_1_pass": False,
            "threshold_2_protect_true": None,
            "threshold_2_n": 0,
            "threshold_2_pass": False,
            "threshold_3_walker_fp": None,
            "threshold_3_n": 0,
            "threshold_3_pass": False,
        }

    # T1: inter-judge agreement (Sonnet vs gpt-5-mini, pre-Opus)
    inter_pairs = 0
    inter_agree = 0
    for r in labeled_results:
        s_cat = r.get("sonnet_category")
        g_cat = r.get("gpt_category")
        if s_cat and g_cat:
            inter_pairs += 1
            if s_cat == g_cat:
                inter_agree += 1
    t1 = round(100 * inter_agree / inter_pairs, 1) if inter_pairs else None

    # T2: ensemble = legit_drafting_error when label.protect=true
    protect_true = [r for r in labeled_results if r["label"].get("protect") is True]
    if protect_true:
        match = sum(
            1 for r in protect_true if r["final_category"] == "legit_drafting_error"
        )
        t2 = round(100 * match / len(protect_true), 1)
    else:
        t2 = None

    # T3: ensemble = walker_fp when ground_truth_mapped == walker_fp
    walker_fp_labels = [
        r for r in labeled_results if r["ground_truth_mapped"] == "walker_fp"
    ]
    if walker_fp_labels:
        match = sum(
            1 for r in walker_fp_labels if r["final_category"] == "walker_fp"
        )
        t3 = round(100 * match / len(walker_fp_labels), 1)
    else:
        t3 = None

    return {
        "judged_count": len(labeled_results),
        "threshold_1_inter_judge": t1,
        "threshold_1_pass": t1 is not None and t1 >= 80.0,
        "threshold_2_protect_true": t2,
        "threshold_2_n": len(protect_true),
        "threshold_2_pass": t2 is not None and t2 >= 85.0,
        "threshold_3_walker_fp": t3,
        "threshold_3_n": len(walker_fp_labels),
        "threshold_3_pass": t3 is not None and t3 >= 75.0,
    }


def cluster_disagreements(labeled_results: list[dict]) -> list[dict]:
    """Group labeled cases where ground_truth ≠ final_category. Returns
    cluster summaries sorted by frequency."""
    clusters: Counter = Counter()
    examples: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in labeled_results:
        gt = r.get("ground_truth_mapped")
        fc = r.get("final_category")
        if gt and fc and gt != fc:
            key = (gt, fc)
            clusters[key] += 1
            if len(examples[key]) < 3:
                examples[key].append({
                    "fixture": r["fixture_key"],
                    "claim_id": r["finding"]["claim_id"],
                    "term": r["finding"]["term"],
                    "label_category": r["label"].get("category"),
                    "protect": r["label"].get("protect"),
                    "sonnet_reasoning": r.get("sonnet_reasoning", "")[:200],
                    "gpt_reasoning": r.get("gpt_reasoning", "")[:200],
                })
    out = []
    for (gt, fc), n in clusters.most_common():
        out.append({
            "ground_truth": gt,
            "final_category": fc,
            "count": n,
            "examples": examples[(gt, fc)],
        })
    return out


# ---------- main calibration loop ----------


async def run_calibration(
    iteration_label: str,
    *,
    skip_synthetic_cn: bool = True,
    fetch_concurrency: int = 4,
) -> dict:
    """Run the calibration once. Returns a serializable result dict."""
    anth_key, oai_key = load_keys()
    anth = AsyncAnthropic(api_key=anth_key)
    oai = AsyncOpenAI(api_key=oai_key)

    # Load labels
    cn_labels = load_labels(CN_LABELS)
    tw_labels = load_labels(TW_LABELS)

    cn_labels_by_fixture: dict[str, list[dict]] = defaultdict(list)
    for lab in cn_labels:
        cn_labels_by_fixture[lab["fixture"]].append(lab)
    tw_labels_by_fixture: dict[str, list[dict]] = defaultdict(list)
    for lab in tw_labels:
        tw_labels_by_fixture[lab["fixture"]].append(lab)

    # Resolve fixture paths
    cn_paths = load_cn_fixture_paths()
    tw_paths = discover_tw_fixture_paths(tw_labels)

    print(f"CN fixtures: {len(cn_paths)} | TW fixtures: {len(tw_paths)}")

    # Run walker per fixture (sequential, fast)
    fixtures_to_judge: list[tuple[str, str, list[FindingInput], dict[int, str], list[dict]]] = []
    skipped_synth_cn = 0

    for fixture_key, path in cn_paths.items():
        if skip_synthetic_cn and fixture_key.startswith("tw_contamination"):
            skipped_synth_cn += 1
            continue
        try:
            issues, claim_texts = run_cn_walker_for_fixture(path)
        except Exception as exc:
            print(f"  [CN walker error: {fixture_key}: {exc!r}]")
            continue
        findings = [issue_to_finding(i) for i in issues]
        if findings:
            fixtures_to_judge.append((
                fixture_key, "CN", findings, claim_texts,
                cn_labels_by_fixture.get(fixture_key, []),
            ))

    for fixture_key, path in tw_paths.items():
        try:
            issues, claim_texts = run_tw_walker_for_fixture(path)
        except Exception as exc:
            print(f"  [TW walker error: {fixture_key}: {exc!r}]")
            continue
        findings = [issue_to_finding(i) for i in issues]
        if findings:
            fixtures_to_judge.append((
                fixture_key, "TW", findings, claim_texts,
                tw_labels_by_fixture.get(fixture_key, []),
            ))

    print(
        f"Walker run: {len(fixtures_to_judge)} fixtures with ≥1 finding | "
        f"skipped {skipped_synth_cn} synthetic CN"
    )

    # Judge each fixture (concurrent across fixtures)
    sem = asyncio.Semaphore(fetch_concurrency)

    async def _judge_one(args):
        fixture_key, jur, findings, claim_texts, _labels = args
        async with sem:
            return await judge_draft(
                fixture_key=fixture_key,
                jurisdiction=jur,
                claim_chain_texts=claim_texts,
                findings=findings,
                anthropic_client=anth,
                openai_client=oai,
                system_prompt=SYSTEM_PROMPT_V2,
            )

    print(f"Judging {len(fixtures_to_judge)} drafts (concurrency={fetch_concurrency})...")
    t0 = time.monotonic()
    ensemble_results: list[DraftEnsembleVerdict] = await asyncio.gather(
        *[_judge_one(a) for a in fixtures_to_judge]
    )
    elapsed = time.monotonic() - t0
    print(f"All drafts judged in {elapsed:.1f}s")

    # Build labeled-result table for threshold computation
    labeled_results: list[dict] = []
    used_opus_count = 0
    total_findings_judged = 0

    for ensemble, (fixture_key, jur, findings, _claim_texts, fixture_labels) in zip(
        ensemble_results, fixtures_to_judge
    ):
        if ensemble.used_opus:
            used_opus_count += 1
        labels_by_key = (
            cn_labels_by_fixture if jur == "CN" else tw_labels_by_fixture
        )
        for finding_index, (finding, final) in enumerate(
            zip(ensemble.findings, ensemble.final_verdicts)
        ):
            total_findings_judged += 1
            label = find_label_for_finding(
                labels_by_key, fixture_key, finding
            )
            if label is None:
                continue
            gt = map_label_to_ensemble(label.get("category", ""))
            if gt is None:
                continue
            sonnet_v = (
                _pair_verdict_to_finding(finding, finding_index, ensemble.sonnet)
                if ensemble.sonnet
                else None
            )
            gpt_v = (
                _pair_verdict_to_finding(finding, finding_index, ensemble.gpt_mini)
                if ensemble.gpt_mini
                else None
            )
            labeled_results.append({
                "fixture_key": fixture_key,
                "jurisdiction": jur,
                "label": label,
                "ground_truth_mapped": gt,
                "finding": asdict(finding),
                "final_category": final.category,
                "final_confidence": final.confidence,
                "final_reasoning": final.reasoning,
                "sonnet_category": sonnet_v.category if sonnet_v else None,
                "sonnet_reasoning": sonnet_v.reasoning if sonnet_v else "",
                "gpt_category": gpt_v.category if gpt_v else None,
                "gpt_reasoning": gpt_v.reasoning if gpt_v else "",
            })

    thresholds = compute_thresholds(labeled_results)
    disagreements = cluster_disagreements(labeled_results)

    return {
        "iteration_label": iteration_label,
        "elapsed_sec": elapsed,
        "fixtures_judged": len(fixtures_to_judge),
        "total_findings_judged": total_findings_judged,
        "labeled_findings": len(labeled_results),
        "drafts_escalated_to_opus": used_opus_count,
        "thresholds": thresholds,
        "disagreement_clusters": disagreements,
        "labeled_results": labeled_results,
        "ensemble_dumps": [ensemble_to_dict(e) for e in ensemble_results],
    }


# ---------- report rendering ----------


def render_iteration_report(result: dict) -> str:
    t = result["thresholds"]
    lines: list[str] = []

    def line(s: str = "") -> None:
        lines.append(s)

    line(f"# Phase 2a Calibration — {result['iteration_label']}")
    line()
    line(f"**Elapsed:** {result['elapsed_sec']:.1f}s. "
         f"**Fixtures judged:** {result['fixtures_judged']}. "
         f"**Findings judged total:** {result['total_findings_judged']}. "
         f"**Findings with ground-truth labels:** {result['labeled_findings']}. "
         f"**Drafts escalated to Opus:** {result['drafts_escalated_to_opus']}.")
    line()

    line("## Threshold results")
    line()
    line("| # | Threshold | Result | Pass | Target |")
    line("|---|---|---|---|---|")
    line(
        f"| 1 | Inter-judge (Sonnet ↔ gpt-5-mini, pre-Opus) | "
        f"{t['threshold_1_inter_judge']}% | "
        f"{'✅' if t['threshold_1_pass'] else '❌'} | ≥80% |"
    )
    line(
        f"| 2 | Ensemble = legit_drafting_error \\| label.protect=true | "
        f"{t['threshold_2_protect_true']}% (n={t['threshold_2_n']}) | "
        f"{'✅' if t['threshold_2_pass'] else '❌'} | ≥85% |"
    )
    line(
        f"| 3 | Ensemble = walker_fp \\| walker_fp.* / walker_bug.* | "
        f"{t['threshold_3_walker_fp']}% (n={t['threshold_3_n']}) | "
        f"{'✅' if t['threshold_3_pass'] else '❌'} | ≥75% |"
    )
    line()

    pass_count = sum([
        t.get("threshold_1_pass", False),
        t.get("threshold_2_pass", False),
        t.get("threshold_3_pass", False),
    ])
    line("## Recommendation")
    line()
    if pass_count == 3:
        line(
            "**SHIP — proceed to Phase 2b.** All three thresholds clear. "
            "Lock the system prompt; run Phase 2b on the 757-record corpus."
        )
    elif pass_count >= 1:
        line(
            f"**ITERATE.** {pass_count}/3 thresholds passed. Review the "
            "top disagreement cluster below and revise the system prompt "
            "before next iteration."
        )
    else:
        line(
            "**ESCALATE.** 0/3 thresholds passed. Review per-fixture "
            "results to determine root cause; per DP-2 default (Option A), "
            "lower thresholds + heavier Phase 2c is the fallback. May "
            "indicate the prompt fundamentally doesn't match the labels' "
            "rule set."
        )
    line()

    line("## Top disagreement clusters")
    line()
    if not result["disagreement_clusters"]:
        line("No labeled-vs-ensemble disagreements found. (Surprising — check the harness.)")
    else:
        line("| Ground truth | Final verdict | Count | Sample fixture/term |")
        line("|---|---|---|---|")
        for c in result["disagreement_clusters"][:10]:
            example = c["examples"][0] if c["examples"] else {}
            line(
                f"| {c['ground_truth']} | {c['final_category']} | {c['count']} | "
                f"{example.get('fixture', '?')} / {example.get('term', '?')} |"
            )
    line()

    line("### Cluster examples (top 5 clusters, up to 3 cases each)")
    line()
    for c in result["disagreement_clusters"][:5]:
        line(f"#### {c['ground_truth']} → {c['final_category']} (×{c['count']})")
        line()
        for ex in c["examples"]:
            line(f"- **{ex['fixture']}** claim {ex['claim_id']} term `{ex['term']}` "
                 f"(label.category={ex['label_category']}, protect={ex['protect']})")
            line(f"  - Sonnet: {ex['sonnet_reasoning']}")
            line(f"  - gpt-5-mini: {ex['gpt_reasoning']}")
        line()

    return "\n".join(lines)


# ---------- CLI ----------


async def _main_async(args: argparse.Namespace) -> int:
    iteration_label = args.label or f"iter-{int(time.time())}"

    result = await run_calibration(iteration_label)

    # Persist results
    results_path = (
        PATENTLINT_ROOT / "tests/eval"
        / f"phase2a_results_{iteration_label}.json"
    )
    results_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Results written to {results_path}")

    # Persist report
    report_path = (
        CC_OUTPUT_DIR
        / f"2026-05-02_phase2a-{iteration_label}-report.md"
    )
    report = render_iteration_report(result)
    report_path.write_text(report, encoding="utf-8")
    print(f"Report written to {report_path}")

    t = result["thresholds"]
    print(
        f"\nT1 inter-judge: {t['threshold_1_inter_judge']}% "
        f"({'✅' if t['threshold_1_pass'] else '❌'} ≥80)"
    )
    print(
        f"T2 protect:true: {t['threshold_2_protect_true']}% n={t['threshold_2_n']} "
        f"({'✅' if t['threshold_2_pass'] else '❌'} ≥85)"
    )
    print(
        f"T3 walker_fp: {t['threshold_3_walker_fp']}% n={t['threshold_3_n']} "
        f"({'✅' if t['threshold_3_pass'] else '❌'} ≥75)"
    )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 2a calibration runner (per-draft mode)."
    )
    parser.add_argument(
        "--label",
        type=str,
        default=None,
        help="Iteration label (e.g., 'iter1'). Used in result + report filenames.",
    )
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    sys.exit(main())
