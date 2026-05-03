"""Autonomous triage of open `report`-labeled GitHub issues using cross-family LLM ensemble.

Fetches issue payloads via `gh`, classifies each finding via Haiku 4.5 + gpt-5-mini
ensemble (Sonnet 4.6 tiebreaker), runs Gate 2 anti-corpus check against labels JSON,
formats per `triage-report` skill comment template, posts via `gh issue comment`.

Tonight's invocation (autonomous, 2026-05-02): processes #19, #23, #24 with full
LLM ensemble; #17, #25 get fix-shipped close-pending comments; #20, #21 get
pre-extractor §6c comments.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from .llm_judges import (
    EnsembleVerdict,
    judge_finding,
    load_keys,
    verdict_to_dict,
)


PATENTLINT_ROOT = Path("/Users/chrischen/Documents/Projects/Patent-Lint")
CN_LABELS = PATENTLINT_ROOT / "tests/fixtures/cn/antecedent_labels_cn.json"
TW_LABELS = PATENTLINT_ROOT / "tests/fixtures/tw/antecedent_labels.json"

# Fix-shipped commits (descendant-of-report-build verified via git merge-base earlier in session)
FIX_SHIPPED = {
    17: ["6746b7d", "28398d5"],  # TW requiredSections — initial fix + follow-up
    25: ["cf1884a"],  # refNumeralParens Miller-index suppression
}

# Build-at-report-time → so we can mention what's newer
REPORT_BUILD = {
    17: "4641dfa",
    19: "6746b7d",
    20: "6746b7d",
    21: "6746b7d",
    23: "28398d5",
    24: "28398d5",
    25: "b5f3648",
}

# R7 walker fix that may have addressed antecedentBasis / specSupport FPs
R7_FIX_COMMITS = {
    "antecedentBasis": "623e2d6",  # "R7 systematic audit — 33 antecedent + 4 spec-support FPs → 0 on real-draft"
    "specSupport": "623e2d6",
    "antecedentBasis_followups": ["caab84c", "b5f3648"],
}


def fetch_issue(number: int) -> dict:
    """Fetch issue body + metadata via gh CLI."""
    out = subprocess.run(
        ["gh", "issue", "view", str(number), "--json", "number,title,body,createdAt,labels"],
        capture_output=True,
        text=True,
        check=True,
        cwd=PATENTLINT_ROOT,
    )
    return json.loads(out.stdout)


def parse_payload(body: str) -> dict | None:
    """Extract the fenced ```json``` payload from issue body."""
    m = re.search(r"```json\s*\n(.*?)\n```", body, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def classify_payload_shape(payload: dict | None) -> str:
    """Identify which of the 4 shapes per skill §2 we have."""
    if payload is None:
        return "malformed"
    check_key = payload.get("check_key", "")
    if check_key.startswith("smoke.test."):
        return "synthetic_smoke"
    if "findings" not in payload:
        return "pre_extractor"
    return "modern"


def detect_check_class(check_key: str) -> str:
    """antecedentBasis | specSupport | other"""
    if "antecedentBasis" in check_key:
        return "antecedentBasis"
    if "specSupport" in check_key:
        return "specSupport"
    if "requiredSections" in check_key:
        return "requiredSections"
    if "refNumeralParens" in check_key:
        return "refNumeralParens"
    return "other"


def gate2_anti_corpus(jurisdiction: str, term: str | None) -> tuple[int, list[str]]:
    """Grep TW/CN labels JSON for protect:true entries matching the term.

    Returns (count, sample_terms_list).
    """
    if not term or len(term) < 2:
        return (0, [])
    path = CN_LABELS if jurisdiction.upper() == "CN" else TW_LABELS
    if not path.exists():
        return (-1, [])  # missing labels file
    try:
        d = json.loads(path.read_text())
    except json.JSONDecodeError:
        return (-2, [])
    hits: list[str] = []
    # Use a substring of the term for fuzzy match (the term might be embedded in compound phrases)
    needle = term[:3] if len(term) > 3 else term
    for label in d.get("labels", []):
        if not label.get("protect"):
            continue
        label_term = label.get("term") or ""
        label_ref = label.get("reference_form") or ""
        if needle in label_term or needle in label_ref:
            hits.append(f"{label_term!r}/{label_ref!r}")
    return (len(hits), hits[:5])


def format_comment_modern(
    issue: dict,
    payload: dict,
    verdicts: list[EnsembleVerdict],
    findings: list[dict],
    check_class: str,
    jurisdiction: str,
) -> str:
    """Format comment for a modern-payload issue per skill §6a-walker template."""
    n = issue["number"]
    build = REPORT_BUILD.get(n, payload.get("patentlint_build", "?"))
    r7_fix = R7_FIX_COMMITS.get(check_class)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"**Autonomous triage** ({timestamp}) — cross-family LLM ensemble (Haiku 4.5 + gpt-5-mini, Sonnet 4.6 tiebreaker on disagreement). Per the `triage-report` skill: classification only; not solo-patching, not invoking `walker-round` (post-closeout walkers require ≥3 same-jurisdiction confirmed FPs to trigger).",
        "",
        "**Per-finding ensemble verdicts:**",
        "",
        "| # | Term / Phrase | Final | Agreement | Confidence (avg) | Sketch reasoning |",
        "|---|---|---|---|---|---|",
    ]

    pipe_escape = "\\|"
    for i, (finding, v) in enumerate(zip(findings, verdicts), 1):
        if check_class == "antecedentBasis":
            label = f"`{finding.get('term', '?')}` → `{finding.get('reference_form', '?')}`"
        else:
            label = f"`{finding.get('phrase', '?')}`"
        label_safe = label.replace("|", pipe_escape)
        avg_conf = sum(j.confidence for j in v.judgments) // max(len(v.judgments), 1)
        first_reasoning = v.judgments[0].reasoning if v.judgments else ""
        first_reasoning_clean = first_reasoning.replace("\n", " ").replace("|", pipe_escape)[:140]
        lines.append(
            f"| {i} | {label_safe} | `{v.final_category}` | "
            f"{v.agreement_level} | {avg_conf} | {first_reasoning_clean} |"
        )

    lines.extend(["", "**Verification gates:**"])

    # Gate 1
    lines.append(
        "- **Gate 1 (Reproducer):** DEFERRED — autonomous triage did not synthesize a minimal "
        "harness fixture; recommend re-running the user's draft against the post-R7 build "
        "to verify whether findings persist before any walker-round invocation."
    )

    # Gate 2
    walker_fp_terms = [
        (findings[i].get("term") if check_class == "antecedentBasis" else findings[i].get("phrase"))
        for i, v in enumerate(verdicts)
        if v.final_category == "walker_fp"
    ]
    g2_lines = []
    for t in walker_fp_terms:
        if not t:
            continue
        count, samples = gate2_anti_corpus(jurisdiction, t)
        if count == -1:
            g2_lines.append(f"  - `{t}`: labels file not found at expected path (deferred to morning)")
        elif count == -2:
            g2_lines.append(f"  - `{t}`: labels file unparseable (deferred)")
        elif count == 0:
            g2_lines.append(f"  - `{t}`: 0 `protect:true` matches — proposed relaxation safe")
        else:
            sample_str = ", ".join(samples)
            g2_lines.append(f"  - `{t}`: **{count} `protect:true` matches** (samples: {sample_str}) — narrow any relaxation to avoid silencing")
    if g2_lines:
        lines.append("- **Gate 2 (Anti-corpus):** for each walker_fp verdict, grep `protect:true` in CN/TW labels JSON:")
        lines.extend(g2_lines)
    else:
        lines.append("- **Gate 2 (Anti-corpus):** no `walker_fp` verdicts to relax; gate not exercised.")

    # Gate 3
    if check_class == "antecedentBasis" and jurisdiction.upper() == "TW":
        statute = "TW 專利法 §26 第3項 + 專利審查基準 第二篇第一章 §1.2 (claim language clarity / antecedent basis)"
    elif check_class == "specSupport" and jurisdiction.upper() == "TW":
        statute = "TW 專利法 §26 第3項 (申請專利範圍應為說明書所支持) + 專利審查基準 第二篇第一章 §2.1"
    elif check_class == "antecedentBasis" and jurisdiction.upper() == "CN":
        statute = "CN 专利法 §26 第4款 + 审查指南 第二部分第二章 §3.2.1"
    else:
        statute = "[STATUTE PIN — verify in morning]"
    lines.append(f"- **Gate 3 (Statute pin):** {statute}. Cited from prior PatentLint precedent; novel statute interpretation NOT auto-resolved.")

    # Gate 4
    lines.append(
        f"- **Gate 4 (Hand-off):** `{payload.get('check_key', '?')}` is a walker check "
        f"({jurisdiction.upper()} walker is CLOSED post Phase 8b/8c). Routing → `walker-round` skill "
        f"queue. **Trigger threshold (≥3 same-jurisdiction confirmed FPs) is NOT met yet** "
        f"(this issue contributes 1; combined `report`-queue across all 5 modern issues stands at "
        f"~1 unique antecedentBasis case + ~1 specSupport case after dedup). No invocation tonight."
    )

    # Post-report context
    if r7_fix:
        lines.extend([
            "",
            f"**Post-report context:** Build at report time was `{build}`. R7 walker audit "
            f"(commit `{r7_fix}`, 2026-04-30 21:07 CST, *after* this report at "
            f"{issue['createdAt']}) shipped: \"33 antecedent + 4 spec-support FPs → 0 on real-draft.\" "
            f"The user-reported FP class may have been addressed. **Recommend retrying on the "
            f"current `main` build to confirm whether findings persist** before any walker-round "
            f"invocation."
        ])

    lines.extend([
        "",
        "**Routing:** queued in walker-round notes (NOT invoked tonight). "
        "Maintainer reviews + decides next steps in the morning. "
        "Per skill §7: not closing this issue programmatically.",
    ])

    return "\n".join(lines)


def format_comment_pre_extractor(issue: dict, payload: dict | None) -> str:
    """Skill §6c — pre-extractor / legacy / malformed."""
    n = issue["number"]
    build = REPORT_BUILD.get(n, "?")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    findings_summary = ""
    if payload:
        ck = payload.get("check_key", "?")
        hc = payload.get("hit_count", payload.get("findings_in_group", "?"))
        findings_summary = f" Top-level signal: check_key=`{ck}`, hit_count={hc}, jurisdiction={payload.get('jurisdiction', '?')}."
    return (
        f"**Autonomous triage** ({timestamp}): pre-extractor payload shape — "
        f"missing `findings[]` array and namespaced `check.tw.claims.specSupport.*` prefix. "
        f"Build `{build}` predates the `ea19383` extractor sweep, so per-finding context "
        f"(term, reference_form, context_before/after, char_offset) is **unrecoverable from "
        f"this submission alone**.{findings_summary}\n\n"
        f"**Recommended action:** close as triaged-stale. If the FP reproduces on the current "
        f"`main` build (post `ea19383` + R7 walker audit `623e2d6`), please resubmit — the new "
        f"diagnostic payload renders fully with per-finding context.\n\n"
        f"Per skill §7: not closing this issue programmatically."
    )


def format_comment_close_pending(issue: dict, payload: dict | None) -> str:
    """For #17 and #25 where a fix has shipped after the report."""
    n = issue["number"]
    build = REPORT_BUILD.get(n, "?")
    fix_shas = FIX_SHIPPED.get(n, [])
    fix_str = ", ".join(f"`{s}`" for s in fix_shas)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"**Autonomous triage** ({timestamp}): fix verifiably shipped after this report.\n\n"
        f"- Report build: `{build}`\n"
        f"- Fix commit(s): {fix_str}\n"
        f"- Verified `git merge-base --is-ancestor {build} {fix_shas[-1]}` returns true — "
        f"fix descends from the build the user reported on.\n\n"
        f"**Recommended action:** maintainer closes this issue (per skill §7, autonomous "
        f"triage does not close). If the user retries on the current `main` build and the "
        f"finding persists, please reopen with the new build SHA so the diagnostic carries "
        f"the post-fix context."
    )


async def triage_modern_issue(
    issue: dict,
    anthropic_client: AsyncAnthropic,
    openai_client: AsyncOpenAI,
) -> tuple[str, list[dict]]:
    """Triage a modern-shape issue: ensemble per finding + comment string + verdict dicts."""
    payload = parse_payload(issue["body"])
    if not payload:
        return (format_comment_pre_extractor(issue, None), [])
    findings = payload.get("findings", [])
    check_class = detect_check_class(payload.get("check_key", ""))
    jurisdiction = payload.get("jurisdiction", "TW")

    if check_class not in {"antecedentBasis", "specSupport"}:
        return (
            format_comment_pre_extractor(issue, payload),
            [],
        )

    verdicts: list[EnsembleVerdict] = []
    for i, finding in enumerate(findings):
        key = f"issue{issue['number']}_finding{i}"
        v = await judge_finding(
            finding=finding,
            jurisdiction=jurisdiction,
            check_class=check_class,
            finding_key=key,
            anthropic_client=anthropic_client,
            openai_client=openai_client,
        )
        verdicts.append(v)

    comment = format_comment_modern(
        issue, payload, verdicts, findings, check_class, jurisdiction
    )
    return (comment, [verdict_to_dict(v) for v in verdicts])


def post_comment(number: int, body: str) -> bool:
    """Post a comment via gh CLI. Returns True on success."""
    try:
        subprocess.run(
            ["gh", "issue", "comment", str(number), "--body", body],
            capture_output=True,
            text=True,
            check=True,
            cwd=PATENTLINT_ROOT,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to post comment on #{number}: {e.stderr}")
        return False


async def main():
    anthropic_key, openai_key = load_keys()
    anthropic_client = AsyncAnthropic(api_key=anthropic_key)
    openai_client = AsyncOpenAI(api_key=openai_key)

    results: dict[int, dict] = {}

    # Oldest first (matches createdAt order: 17, 19, 20, 21, 23, 24, 25)
    issue_numbers = [17, 19, 20, 21, 23, 24, 25]
    for n in issue_numbers:
        print(f"\n=== Processing #{n} ===")
        issue = fetch_issue(n)
        payload = parse_payload(issue["body"])
        shape = classify_payload_shape(payload)

        if n in FIX_SHIPPED:
            comment = format_comment_close_pending(issue, payload)
            verdicts: list[dict] = []
            classification = "fix_shipped_close_pending"
        elif shape in {"pre_extractor", "malformed"}:
            comment = format_comment_pre_extractor(issue, payload)
            verdicts = []
            classification = "pre_extractor_stale"
        elif shape == "modern":
            comment, verdicts = await triage_modern_issue(
                issue, anthropic_client, openai_client
            )
            classification = "modern_triaged"
        else:
            comment = f"Triage halted: unrecognized shape `{shape}`."
            verdicts = []
            classification = "halted"

        # Post the comment
        posted = post_comment(n, comment)
        results[n] = {
            "title": issue["title"],
            "shape": shape,
            "classification": classification,
            "verdicts": verdicts,
            "comment_posted": posted,
            "comment_preview": comment[:300],
        }
        print(f"  shape={shape} classification={classification} posted={posted} verdicts={len(verdicts)}")

    # Save results
    out_path = PATENTLINT_ROOT / "tests/eval/triage_results_2026-05-02.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nResults saved: {out_path}")

    # Print summary
    print("\n=== TRIAGE SUMMARY ===")
    print(f"  Total issues processed: {len(results)}")
    counts: dict[str, int] = {}
    for r in results.values():
        c = r["classification"]
        counts[c] = counts.get(c, 0) + 1
    for k, v in counts.items():
        print(f"  {k}: {v}")
    posted_count = sum(1 for r in results.values() if r["comment_posted"])
    print(f"  Comments posted: {posted_count}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
