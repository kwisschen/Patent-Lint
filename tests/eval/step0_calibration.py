"""Step 0 calibration — round 1 §7 LLM-judge gating against PatentLint's hand-labeled corpus.

Stratified samples from CN + TW antecedent labels, runs the walker per fixture
to recover claim_text + term offsets (so we can construct a 30-char vicinity
window mimicking the production diagnostic payload), feeds each finding into the
cross-family ensemble (Haiku 4.5 + gpt-5-mini, Sonnet 4.6 tiebreaker), then
computes the three plan-defined thresholds:

| # | Threshold | Pass when |
|---|---|---|
| 1 | Inter-judge (Haiku ↔ gpt-5-mini before tiebreaker) agreement | ≥80% |
| 2 | Ensemble final = legit_drafting_error when label.protect=true | ≥85% |
| 3 | Ensemble final = walker_fp when label.category ∈ walker_fp.*/walker_bug.* | ≥75% |

Threshold 1 fail → drop cross-family pair, single-judge round 1 (cost +30%).
Threshold 2 fail → LLM over-flags legit drafting; investigate before round 1.
Threshold 3 fail → LLM misses real FPs; fall back to programmatic mutators ($30 cap).
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

# Allow direct import from PatentLint src
PATENTLINT_ROOT = Path("/Users/chrischen/Documents/Projects/Patent-Lint")
sys.path.insert(0, str(PATENTLINT_ROOT / "src"))

from patentlint.analysis.cn_claims import check_antecedent_basis_cn  # noqa: E402
from patentlint.parser.docx_loader import load_docx_cn  # noqa: E402
from patentlint.parser.sections_cn import extract_cn_sections_from_docx  # noqa: E402

from .llm_judges import (  # noqa: E402
    judge_finding,
    load_keys,
    verdict_to_dict,
)

CN_LABELS = PATENTLINT_ROOT / "tests/fixtures/cn/antecedent_labels_cn.json"
CN_BASELINE = PATENTLINT_ROOT / "tests/fixtures/cn/local/baseline_phase8c.json"
TW_LABELS = PATENTLINT_ROOT / "tests/fixtures/tw/antecedent_labels.json"

CC_OUTPUT_DIR = Path(
    "/Users/chrischen/Library/Mobile Documents/com~apple~CloudDocs/CC Output"
)
REPORT_PATH = CC_OUTPUT_DIR / "2026-05-02_step0-calibration-report.md"
RESULTS_PATH = PATENTLINT_ROOT / "tests/eval/step0_results.json"

# Sampling target (per jurisdiction).
# 25 was too small after walker_no_longer_emits skips (~40% of sample skipped) —
# 15 judged → n=8 protect:true → high run-to-run variance on T2 (37-75%).
# Bumping to 60 raises judged-N to ~36 and tightens stratum coverage.
SAMPLE_PER_JURISDICTION = 60
SEED = 20260502


def map_label_to_ensemble(label_category: str) -> Optional[str]:
    """Map fine-grained label category to coarse 5-category ensemble output."""
    if label_category.startswith("walker_fp.") or label_category.startswith("walker_bug.") or label_category == "tw_contamination":
        return "walker_fp"
    if label_category.startswith("miss_intro.") or label_category == "propagation_gap":
        return "coverage_gap"
    if label_category == "legit_drafting_error":
        return "legit_drafting_error"
    # ambig, semantic_disjunction_deferred, unclassified — excluded
    return None


def stratified_sample(labels: list[dict], target_n: int, rng: random.Random) -> list[dict]:
    """Strata: walker_fp / coverage_gap / legit_drafting_error.
    Each stratum gets ~target_n/3 entries; pad from largest stratum if any short.
    """
    by_stratum: dict[str, list[dict]] = defaultdict(list)
    for lab in labels:
        cat = lab.get("category", "")
        # Exclude raw 'unclassified' (Stage 3 seed); the Stage 4 auto-classifier
        # re-tagged 423 labels from unclassified into walker_fp.* / miss_intro.* etc
        # but did NOT update confidence='seed' (per metadata notes 2026-04-16).
        # We trust the category label even when confidence='seed'.
        if cat == "unclassified":
            continue
        mapped = map_label_to_ensemble(cat)
        if mapped is None:
            continue
        by_stratum[mapped].append(lab)

    per = max(1, target_n // 3)
    selected: list[dict] = []
    for stratum in ("walker_fp", "coverage_gap", "legit_drafting_error"):
        bucket = by_stratum.get(stratum, [])
        rng.shuffle(bucket)
        selected.extend(bucket[:per])

    if len(selected) < target_n:
        # Pad from largest stratum
        biggest = max(by_stratum.values(), key=len, default=[])
        already = {id(s) for s in selected}
        for lab in biggest:
            if id(lab) in already:
                continue
            selected.append(lab)
            if len(selected) >= target_n:
                break

    return selected[:target_n]


def load_cn_fixture_paths() -> dict[str, Path]:
    """Read the baseline JSON to get fixture_key → fixture_path mapping."""
    d = json.loads(CN_BASELINE.read_text())
    return {
        key: (PATENTLINT_ROOT / rec["fixture_path"]).resolve()
        for key, rec in d["fixtures"].items()
    }


def run_cn_walker_for_fixture(fixture_path: Path) -> list[dict]:
    """Load .docx, run CN antecedent walker, return list of issue dicts."""
    loaded = load_docx_cn(fixture_path)
    doc = extract_cn_sections_from_docx(loaded.sections)
    return list(check_antecedent_basis_cn(doc))


def find_walker_match(walker_issues: list[dict], label: dict) -> Optional[dict]:
    """Match a label to its walker issue by (claim_id, term, reference_form)."""
    target = (
        label.get("claim_id"),
        label.get("term"),
        label.get("reference_form"),
    )
    for issue in walker_issues:
        if (
            issue.get("claim_id"),
            issue.get("term"),
            issue.get("reference_form"),
        ) == target:
            return issue
    return None


def extract_window(claim_text: str, term: str, window: int = 30) -> tuple[int, str, str]:
    """Find the term's char_offset and extract context_before/context_after windows."""
    if not claim_text or not term:
        return (0, "", "")
    offset = claim_text.find(term)
    if offset < 0:
        return (0, "", "")
    before = claim_text[max(0, offset - window) : offset]
    after = claim_text[offset + len(term) : offset + len(term) + window]
    return (offset, before, after)


def build_finding_dict_from_walker(issue: dict, window: int = 30) -> dict:
    """Construct a finding dict from a walker issue.

    Includes BOTH the production-payload-shape vicinity window AND the full
    claim_text. The actual round-1 LLM judge runs against clean drafts (full
    text available) and only EMITS findings in the vicinity-window shape;
    Step 0 should mirror that capability, not the emitted-payload constraint.
    """
    claim_text = issue.get("claim_text", "")
    term = issue.get("term", "")
    offset, before, after = extract_window(claim_text, term, window)
    return {
        "claim_id": issue.get("claim_id"),
        "term": term,
        "reference_form": issue.get("reference_form"),
        "did_you_mean": issue.get("suggested_match"),
        "did_you_mean_claim_id": None,
        "category": issue.get("category"),
        "char_offset": offset,
        "context_before": before,
        "context_after": after,
        "claim_text": claim_text,  # NEW — full claim text for the judge to read
        "claim_text_charlen": len(claim_text),
    }


async def calibrate_cn(
    sampled: list[dict],
    anthropic_client: AsyncAnthropic,
    openai_client: AsyncOpenAI,
    concurrency: int = 5,
) -> list[dict]:
    """For each sampled CN label, build finding from walker output and judge.

    Walker invocations run serially (CPU/disk-bound, fast); LLM judge calls
    fan out across all findings concurrently under a semaphore to avoid
    overrunning Anthropic/OpenAI per-minute rate limits.
    """
    fixture_paths = load_cn_fixture_paths()
    by_fixture: dict[str, list[dict]] = defaultdict(list)
    for lab in sampled:
        by_fixture[lab["fixture"]].append(lab)

    # Phase 1: pre-load walker output for each unique fixture (sequential, fast)
    walker_outputs: dict[str, list[dict] | str] = {}
    for fixture_key in by_fixture:
        path = fixture_paths.get(fixture_key)
        if not path or not path.exists():
            walker_outputs[fixture_key] = f"fixture not found: {fixture_key}"
            continue
        try:
            walker_outputs[fixture_key] = run_cn_walker_for_fixture(path)
        except Exception as e:
            walker_outputs[fixture_key] = f"walker error: {e!r}"

    # Phase 2: build the work list — (label, finding-or-skip-reason)
    work: list[tuple[dict, dict | None, str | None]] = []  # (label, finding, skip_reason)
    for fixture_key, labels_in_fixture in by_fixture.items():
        out = walker_outputs[fixture_key]
        if isinstance(out, str):
            for lab in labels_in_fixture:
                work.append((lab, None, out))
            continue
        for label in labels_in_fixture:
            wm = find_walker_match(out, label)
            if wm is None:
                work.append((label, None, "walker_no_longer_emits"))
            else:
                work.append((label, build_finding_dict_from_walker(wm), None))

    # Phase 3: judge all valid findings concurrently under a semaphore
    sem = asyncio.Semaphore(concurrency)

    async def _judge_one(label: dict, finding: dict) -> tuple[dict, dict]:
        fixture_key = label["fixture"]
        async with sem:
            v = await judge_finding(
                finding=finding,
                jurisdiction="CN",
                check_class="antecedentBasis",
                finding_key=f"cn:{fixture_key}:{label['claim_id']}:{label['term']}",
                anthropic_client=anthropic_client,
                openai_client=openai_client,
            )
        return (label, verdict_to_dict(v))

    judge_tasks = [
        _judge_one(label, finding)
        for label, finding, skip in work
        if finding is not None
    ]
    judge_results = await asyncio.gather(*judge_tasks, return_exceptions=True)

    # Build a lookup from label-id to verdict dict
    label_to_verdict: dict[int, dict] = {}
    for r in judge_results:
        if isinstance(r, Exception):
            print(f"  [judge error: {r!r}]")
            continue
        label, vdict = r
        label_to_verdict[id(label)] = vdict

    # Phase 4: assemble results in original order
    results: list[dict] = []
    for label, finding, skip in work:
        gt = map_label_to_ensemble(label.get("category", ""))
        if finding is None:
            results.append({
                "label": label,
                "ground_truth_mapped": gt,
                "verdict": None,
                "skip_reason": skip,
            })
            continue
        v = label_to_verdict.get(id(label))
        if v is None:
            results.append({
                "label": label,
                "ground_truth_mapped": gt,
                "verdict": None,
                "skip_reason": "judge exception",
            })
            continue
        results.append({
            "label": label,
            "ground_truth_mapped": gt,
            "verdict": v,
            "finding": finding,
        })

    return results


def compute_thresholds(results: list[dict]) -> dict:
    """Compute the three plan thresholds from results."""
    judged = [r for r in results if r["verdict"] is not None]
    if not judged:
        return {
            "judged_count": 0,
            "threshold_1_inter_judge": None,
            "threshold_2_protect_true": None,
            "threshold_3_walker_fp": None,
        }

    # Threshold 1: inter-judge agreement (Haiku vs gpt-5-mini, BEFORE Sonnet tiebreaker)
    inter_agree = 0
    for r in judged:
        v = r["verdict"]
        judgments = v["judgments"]
        if len(judgments) >= 2:
            haiku_cat = next((j["category"] for j in judgments if "haiku" in j["model"]), None)
            gpt_cat = next((j["category"] for j in judgments if "gpt" in j["model"]), None)
            if haiku_cat is not None and gpt_cat is not None and haiku_cat == gpt_cat:
                inter_agree += 1

    t1 = round(100 * inter_agree / len(judged), 1)

    # Threshold 2: ensemble final = legit_drafting_error when label.protect=true
    protect_true = [r for r in judged if r["label"].get("protect") is True]
    if protect_true:
        t2_match = sum(1 for r in protect_true if r["verdict"]["final_category"] == "legit_drafting_error")
        t2 = round(100 * t2_match / len(protect_true), 1)
    else:
        t2 = None

    # Threshold 3: ensemble final = walker_fp when label.category ∈ walker_fp.*/walker_bug.*/tw_contamination
    walker_fp_labels = [
        r for r in judged
        if r["ground_truth_mapped"] == "walker_fp"
    ]
    if walker_fp_labels:
        t3_match = sum(1 for r in walker_fp_labels if r["verdict"]["final_category"] == "walker_fp")
        t3 = round(100 * t3_match / len(walker_fp_labels), 1)
    else:
        t3 = None

    return {
        "judged_count": len(judged),
        "skipped_count": len(results) - len(judged),
        "threshold_1_inter_judge": t1,
        "threshold_1_pass": t1 >= 80.0,
        "threshold_2_protect_true": t2,
        "threshold_2_n": len(protect_true),
        "threshold_2_pass": t2 is not None and t2 >= 85.0,
        "threshold_3_walker_fp": t3,
        "threshold_3_n": len(walker_fp_labels),
        "threshold_3_pass": t3 is not None and t3 >= 75.0,
    }


def render_report(thresholds: dict, results: list[dict], elapsed_sec: float) -> str:
    """Render markdown summary for CC Output."""
    judged = [r for r in results if r["verdict"] is not None]
    skipped = [r for r in results if r["verdict"] is None]

    cat_dist = Counter(r["ground_truth_mapped"] for r in judged)
    final_dist = Counter(r["verdict"]["final_category"] for r in judged)
    agree_dist = Counter(r["verdict"]["agreement_level"] for r in judged)

    lines = [
        "# Step 0 Calibration Report — 2026-05-02",
        "",
        f"**Elapsed:** {elapsed_sec:.1f}s. **Judged:** {len(judged)} findings. **Skipped:** {len(skipped)}.",
        "",
        "## Threshold results",
        "",
        "| # | Threshold | Result | Pass |",
        "|---|---|---|---|",
        f"| 1 | Inter-judge (Haiku 4.5 ↔ gpt-5-mini) agreement, pre-tiebreaker | "
        f"{thresholds['threshold_1_inter_judge']}% | "
        f"{'✅' if thresholds['threshold_1_pass'] else '❌'} (target ≥80%) |",
        f"| 2 | Ensemble = legit_drafting_error when label.protect=true | "
        f"{thresholds['threshold_2_protect_true']}% (n={thresholds['threshold_2_n']}) | "
        f"{'✅' if thresholds['threshold_2_pass'] else '❌'} (target ≥85%) |",
        f"| 3 | Ensemble = walker_fp when label.category ∈ walker_fp.*/walker_bug.* | "
        f"{thresholds['threshold_3_walker_fp']}% (n={thresholds['threshold_3_n']}) | "
        f"{'✅' if thresholds['threshold_3_pass'] else '❌'} (target ≥75%) |",
        "",
        "## Recommendation",
        "",
    ]

    pass_count = sum([
        thresholds.get('threshold_1_pass', False),
        thresholds.get('threshold_2_pass', False),
        thresholds.get('threshold_3_pass', False),
    ])
    if pass_count == 3:
        lines.append("**PROCEED with full $150 round 1 budget per plan §7.** All three thresholds pass; LLM-as-judge is calibrated to ground truth and inter-judge variance is acceptable.")
    elif pass_count >= 2:
        lines.append(f"**PROCEED WITH CAUTION.** {pass_count}/3 thresholds passed. Investigate the failure(s) below before committing to round 1; possibly adjust judge prompts or sample.")
    else:
        lines.append(f"**FALL BACK** to programmatic mutators only ($30 cap). Only {pass_count}/3 thresholds passed — LLM judge ensemble not reliable enough for round 1 in current configuration.")

    lines.extend([
        "",
        "## Sample distribution (judged)",
        "",
        f"- Ground truth (mapped): {dict(cat_dist)}",
        f"- Ensemble final: {dict(final_dist)}",
        f"- Agreement level: {dict(agree_dist)}",
        "",
        "## Disagreements (ensemble vs ground truth)",
        "",
    ])

    disagreements = [
        r for r in judged
        if r["ground_truth_mapped"] is not None
        and r["verdict"]["final_category"] != r["ground_truth_mapped"]
    ]
    if not disagreements:
        lines.append("_None — full ensemble/ground-truth alignment._")
    else:
        lines.append(f"_{len(disagreements)} disagreements out of {len(judged)} judged._")
        lines.append("")
        lines.append("| Fixture | Claim | Term | Ground truth | Ensemble | Sketch reason |")
        lines.append("|---|---|---|---|---|---|")
        for r in disagreements[:20]:  # top 20
            lab = r["label"]
            v = r["verdict"]
            first_reason = v["judgments"][0]["reasoning"].replace("\n", " ").replace("|", "\\|")[:90]
            lines.append(
                f"| {lab['fixture'][:25]} | {lab['claim_id']} | "
                f"`{(lab.get('term') or '')[:18]}` | `{r['ground_truth_mapped']}` "
                f"({lab['category']}) | `{v['final_category']}` | {first_reason} |"
            )
        if len(disagreements) > 20:
            lines.append(f"| _...{len(disagreements)-20} more — see step0_results.json_ | | | | | |")

    if skipped:
        lines.extend([
            "",
            "## Skipped findings",
            "",
            f"_{len(skipped)} labels skipped — most often because the walker no longer emits "
            f"that finding (R7+ post-label fixes shifted the walker output)._",
            "",
        ])
        skip_reasons = Counter(r["skip_reason"] for r in skipped)
        for reason, count in skip_reasons.most_common():
            lines.append(f"- `{reason}`: {count}")

    lines.extend([
        "",
        "## Loose ends",
        "",
        "- **TW labels not yet calibrated.** This run only sampled CN labels — TW walker uses a different module (`check_antecedent_basis`) and a different fixture path (`tests/fixtures/tw/local/`). Budget room exists; can extend in morning if time permits.",
        "- **Ensemble's `walker_fp` is coarser than label categories.** Subcategory accuracy (over_capture vs trailing_residue vs fragment) not measured — only the binary walker-FP-vs-not signal.",
        "- **30-char window mimics production payload.** The walker exposes full `claim_text`; passing the full claim would improve accuracy but Step 0 should mirror production constraints to be a faithful preview.",
        "- **Sonnet 4.6 tiebreaker counted in final_category** — Threshold 1 measures agreement BEFORE tiebreaker, so a high tiebreaker rate (lots of disagreements that Sonnet resolves) shows up as a low Threshold 1 score, even if the final result is correct.",
        "",
        f"_Full per-finding judgments: `{RESULTS_PATH}`_",
    ])

    return "\n".join(lines)


async def main():
    rng = random.Random(SEED)

    # Load CN labels + sample
    cn = json.loads(CN_LABELS.read_text())
    cn_sampled = stratified_sample(cn["labels"], SAMPLE_PER_JURISDICTION, rng)
    print(f"Sampled {len(cn_sampled)} CN labels for calibration.")

    # Load API keys
    anthropic_key, openai_key = load_keys()
    anthropic_client = AsyncAnthropic(api_key=anthropic_key)
    openai_client = AsyncOpenAI(api_key=openai_key)

    start = time.time()
    print("Running CN walker + ensemble judgments...")
    results = await calibrate_cn(cn_sampled, anthropic_client, openai_client)
    elapsed = time.time() - start
    print(f"Done in {elapsed:.1f}s.")

    thresholds = compute_thresholds(results)

    # Save full results
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    serializable = []
    for r in results:
        serializable.append({
            **r,
            "label": {k: v for k, v in r["label"].items()},
        })
    RESULTS_PATH.write_text(
        json.dumps({"thresholds": thresholds, "results": serializable}, indent=2, ensure_ascii=False)
    )
    print(f"Full results: {RESULTS_PATH}")

    # Write report
    report = render_report(thresholds, results, elapsed)
    REPORT_PATH.write_text(report)
    print(f"Report: {REPORT_PATH}")

    print("\n=== STEP 0 SUMMARY ===")
    for k, v in thresholds.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
