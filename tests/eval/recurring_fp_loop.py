# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# recurring_fp_loop.py — the standing dev-time AI loop that stops walker
# false positives from recurring (ADR-159).
#
# WHY THIS EXISTS
# ---------------
# Walker FPs keep recurring because fixes can't be regression-validated:
# the real drafts that trigger an FP are NEVER stored (Privacy §6), so they
# are not in the fixture corpus, so /walker-round's ephemeral-sim gate has
# nothing to validate a relaxation against ("corpus isolation"). The same FP
# class therefore re-surfaces on the next draft.
#
# This module closes that gap by reusing machinery that already exists in
# tests/eval/ (ADR-158) and wiring it into a STANDING, repeatable pipeline
# (the one-off "round 1" scripts never were). It has two modes:
#
#   corpus  — Grow the labeled fixture corpus. Run the production walker over
#             PatentNode's real CN/TW/US Google-Patents drafts, LLM-judge each
#             NEW finding (FP vs legit vs coverage-gap), and emit PROPOSED
#             labels. More judged labels => /walker-round's drift gate finally
#             has coverage => a fix provably sticks. This is the durable fix
#             for recurrence.
#   reports — Triage assist. For each open `report`, synthesize a minimal
#             privacy-safe fixture from the de-identified context window,
#             reproduce the finding through the walker, and LLM-judge it so
#             the triage classification is automatic.
#
# HARD CONSTRAINTS (do not violate)
#   * Dev-time only. Nothing here ships to PatentLint's runtime — the "No AI"
#     trust badge is about runtime; this is the same posture as ADR-158.
#   * Never persist raw user-draft content. `reports` mode works only from the
#     de-identified payload window; `corpus` mode works only on PUBLIC
#     Google-Patents drafts. Proposed labels carry head-noun terms + verdicts,
#     never a user's claim text.
#   * Proposes, never auto-applies. Output is a proposed-labels JSON for the
#     maintainer / `/walker-round` to review. The ADR-111 harness gate +
#     human sign-off remain the authority on what enters antecedent_labels_*.
#   * Budget-capped. Honors --cost-cap; --dry-run runs the whole chain with
#     ZERO LLM spend (deterministic stub verdicts) so the scaffold is
#     CI-testable and free to smoke.
#
# REUSED SEAMS (built ON, not duplicated)
#   tests/eval/round1_corpus_harness.py : load_corpus, run_walker, _build_doc,
#                                         load_ensemble_verdicts (gold)
#   tests/eval/llm_judges.py            : judge_finding (Haiku+gpt-5-mini,
#                                         Sonnet tiebreaker), Category taxonomy
#   tests/eval/gate1_reproducer.py      : make_claim/make_doc (fixture synth)
#   Patent-Analyst/.env                 : ANTHROPIC_API_KEY + OPENAI_API_KEY
#
# USAGE
#   python tests/eval/recurring_fp_loop.py corpus  --jurisdiction TW --limit 40 --dry-run
#   python tests/eval/recurring_fp_loop.py corpus  --jurisdiction TW --limit 40 --cost-cap 5
#   python tests/eval/recurring_fp_loop.py reports --limit 20 --dry-run
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# ── Path resolution (de-hardcoded; ADR-159 §gaps) ──────────────────────────
# The legacy eval scripts hardcode these two paths. Resolve via env var first
# so the loop runs on other machines / CI, falling back to the established
# local defaults so nothing breaks for the current setup.
THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent.parent

DEFAULT_ANALYST_ENV = Path("/Users/chrischen/Documents/Projects/Patent-Analyst/.env")
DEFAULT_CORPUS_ROOT = Path(
    "/Users/chrischen/Documents/Projects/Patent-Analyst-corpus/parquet/cn_tw_drafts"
)


def analyst_env_path() -> Path:
    return Path(os.environ.get("PATENTLINT_ANALYST_ENV", DEFAULT_ANALYST_ENV))


def corpus_root() -> Path:
    return Path(os.environ.get("PATENTLINT_CORPUS_ROOT", DEFAULT_CORPUS_ROOT))


REPORT_TRACKER = os.environ.get("PATENTLINT_REPORT_REPO", "kwisschen/patentlint-reports")
PROPOSED_LABELS_DIR = THIS_DIR / "proposed_labels"

# ── Data model ─────────────────────────────────────────────────────────────
WALKER_FP = "walker_fp"
PROTECT_CATEGORIES = {"legit_drafting_error"}  # → protect:true candidates
SILENCE_CATEGORIES = {"walker_fp"}             # → FP-silence candidates
NEEDS_HUMAN = {"coverage_gap", "diagnostic_mis_attribution", "ambig"}


@dataclass
class ProposedLabel:
    """A judged finding proposed for the labels file."""
    jurisdiction: str
    source: str            # 'corpus:<patent_id>' or 'report:#<n>'
    claim_id: int | None
    term: str | None
    reference_form: str | None
    verdict: str           # Category
    confidence: str        # 'per-draft-ensemble' | 'per-finding-ensemble' | 'dry-run-stub'
    proposed_action: str   # 'silence_fp' | 'protect' | 'needs_human'
    agreement: str = "unknown"  # 'unanimous' | 'split' | 'unknown' — gates auto-apply (#2)
    rationale: str = ""


@dataclass
class LoopResult:
    mode: str
    jurisdiction: str | None
    findings_seen: int = 0
    already_labeled: int = 0
    judged: int = 0
    proposed: list[ProposedLabel] = field(default_factory=list)
    est_cost_usd: float = 0.0
    notes: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        by_action: dict[str, int] = {}
        for p in self.proposed:
            by_action[p.proposed_action] = by_action.get(p.proposed_action, 0) + 1
        # #2 auto-apply gate: unanimous walker_fp verdicts are eligible for the
        # automated labels feed; everything else queues for human review.
        auto = sum(1 for p in self.proposed
                   if p.verdict == "walker_fp" and p.agreement == "unanimous")
        return {
            "mode": self.mode,
            "jurisdiction": self.jurisdiction,
            "findings_seen": self.findings_seen,
            "already_labeled": self.already_labeled,
            "judged": self.judged,
            "proposed_total": len(self.proposed),
            "by_action": by_action,
            "auto_applyable_unanimous_fp": auto,
            "est_cost_usd": round(self.est_cost_usd, 4),
            "notes": self.notes,
        }


# ── Verdict → action mapping ───────────────────────────────────────────────
def action_for(verdict: str) -> str:
    if verdict in SILENCE_CATEGORIES:
        return "silence_fp"
    if verdict in PROTECT_CATEGORIES:
        return "protect"
    return "needs_human"


# ── Seam imports (lazy: keep --help / --dry-run cheap, avoid heavy deps) ────
def _import_harness():
    sys.path.insert(0, str(THIS_DIR))
    import round1_corpus_harness as h  # noqa: E402
    # Honor the de-hardcoded corpus root.
    h.CORPUS_ROOT = corpus_root()
    return h


def _import_judges():
    sys.path.insert(0, str(THIS_DIR))
    import llm_judges as j  # noqa: E402
    j.ANALYST_ENV = analyst_env_path()
    return j


# Conservative per-finding cost estimate for the budget cap. The ensemble is
# Haiku 4.5 (~$0.001) + gpt-5-mini (~$0.002), plus a Sonnet 4.6 tiebreaker
# (~$0.01) on the ~30% of findings where the two disagree. EnsembleVerdict
# does not expose token usage, so we cap on this estimate (intentionally high
# so --cost-cap is a real ceiling, not an under-count).
EST_PER_FINDING_USD = 0.012


def _make_clients(judges):
    from anthropic import AsyncAnthropic
    from openai import AsyncOpenAI
    anth_key, oai_key = judges.load_keys()
    return AsyncAnthropic(api_key=anth_key), AsyncOpenAI(api_key=oai_key)


async def _judge_batch(judges, items, cost_cap, start_cost):
    """items: list of (finding_dict, jurisdiction, check_class, finding_key).
    Returns list of (final_category, est_cost) aligned to items; stops early
    (remaining → None) once the running estimate would exceed cost_cap."""
    anth, oai = _make_clients(judges)
    out, running = [], start_cost
    try:
        for finding, juris, check_class, key in items:
            if cost_cap and running >= cost_cap:
                out.append((None, 0.0))
                continue
            try:
                v = await judges.judge_finding(finding, juris, check_class, key, anth, oai)
                cat = v.final_category
            except Exception:  # one bad finding shouldn't abort the batch
                cat = "ambig"
                out.append((cat, 0.0))
                continue
            running += EST_PER_FINDING_USD
            out.append((cat, EST_PER_FINDING_USD))
    finally:
        for c in (anth, oai):
            close = getattr(c, "close", None)
            if close:
                try:
                    await close()
                except Exception:
                    pass
    return out


# ── Stage C: judge (real or dry-run stub) ──────────────────────────────────
def _stub_verdict(term: str | None, reference_form: str | None) -> tuple[str, str]:
    """Deterministic offline heuristic standing in for the LLM ensemble in
    --dry-run. NOT a substitute for the real judge — it just exercises the
    chain end-to-end for free. Heuristic mirrors the triage 'critical move':
    a captured term that looks like a verb-clause/over-capture (long, or the
    reference form embeds a quantifier/ref-prefix that the head noun
    shouldn't) leans walker_fp; otherwise needs_human."""
    t = term or ""
    # Over-long capture or quantifier/ref-prefix bleed → likely over-capture FP.
    overcap_markers = ("所述", "兩個", "多條", "每條", "perform", "傾向", "鄰近於")
    if len(t) >= 8 or any(m in t for m in overcap_markers):
        return WALKER_FP, "dry-run heuristic: over-capture shape"
    return "ambig", "dry-run heuristic: undetermined (needs real judge)"


# ── Mode: corpus (the durable recurrence fix) ──────────────────────────────
def run_corpus_mode(jurisdiction: str, limit: int, cost_cap: float, dry_run: bool,
                    judge_mode: str = "per-draft") -> LoopResult:
    res = LoopResult(mode="corpus", jurisdiction=jurisdiction)
    # Check corpus presence BEFORE importing the harness — the harness pulls
    # pyarrow (the [eval] extra), which CI's [dev] install doesn't have. When
    # the corpus is absent there's nothing to do anyway, so bail first. (This
    # is what failed PR #296's `test` job.)
    if not corpus_root().exists():
        res.notes.append(f"corpus root absent: {corpus_root()} — skipping")
        return res
    h = _import_harness()
    records = h.load_corpus(jurisdiction)[: max(limit, 0) or None]
    claims_by_pid = {r.get("patent_id"): (r.get("claims") or []) for r in records}
    gold = {}
    try:
        gold = h.load_ensemble_verdicts(jurisdiction)
    except Exception as e:  # gold is optional
        res.notes.append(f"gold verdicts unavailable: {e}")

    # Stage B: run the production walker over real public drafts. Keep only
    # findings NOT already in the gold/labels (those are the "new" work).
    findings = _collect_finding_dicts(h, records, jurisdiction)
    res.findings_seen = len(findings)
    new = []
    for f in findings:
        key = (f.get("patent_id"), f.get("claim_id"), f.get("term"), f.get("reference_form"))
        if key in gold:
            res.already_labeled += 1
        else:
            new.append(f)

    # Stage C+D: judge the new findings, then emit proposed labels.
    if not dry_run and judge_mode == "per-draft":
        # Per-DRAFT judge (per_draft_judge.py): Sonnet-primary, full claim-chain
        # context, Opus tiebreaker. ~3x more decisive on CJK reference forms
        # than the per-finding judge. Carries per-finding agreement so #2's
        # auto-apply can gate on unanimity.
        _judge_per_draft(new, claims_by_pid, jurisdiction, cost_cap, res)
    else:
        verdicts = _judge_findings(
            new, lambda f: (jurisdiction, "antecedentBasis"), dry_run, cost_cap, res,
        )
        for f, (verdict, rationale) in zip(new, verdicts):
            if verdict is None:  # skipped by cost cap
                continue
            res.proposed.append(ProposedLabel(
                jurisdiction=jurisdiction,
                source=f"corpus:{f.get('patent_id')}",
                claim_id=f.get("claim_id"),
                term=f.get("term"),
                reference_form=f.get("reference_form"),
                verdict=verdict,
                confidence="dry-run-stub" if dry_run else "per-finding-ensemble",
                proposed_action=action_for(verdict),
                agreement="unknown",
                rationale=rationale,
            ))
    return res


def _judge_per_draft(findings, claims_by_pid, jurisdiction, cost_cap, res):
    """Judge findings grouped by draft via per_draft_judge (full claim-chain
    context). Sets per-finding agreement from the draft's ensemble disagreement
    (0 disagreements → 'unanimous' → eligible for #2 auto-apply)."""
    if not findings:
        return
    sys.path.insert(0, str(THIS_DIR))
    import per_draft_judge as J  # noqa: E402
    J.ANALYST_ENV = analyst_env_path()
    from anthropic import AsyncAnthropic
    from openai import AsyncOpenAI

    by_pid: dict = {}
    for f in findings:
        by_pid.setdefault(f.get("patent_id"), []).append(f)
    anth_key, oai_key = J.load_keys()
    # Per-jurisdiction system prompt. judge_draft DEFAULTS to the CN/TW prompt
    # (該/所述/前述); US §112(b) needs the English a/an/the prompt. Selecting the
    # wrong one silently mis-judges every US draft — caught in the pre-run probe.
    system_prompt = J.SYSTEM_PROMPT_US_V1 if jurisdiction == "US" else J.SYSTEM_PROMPT_V2

    async def run():
        anth, oai = AsyncAnthropic(api_key=anth_key), AsyncOpenAI(api_key=oai_key)
        try:
            for pid, fs in by_pid.items():
                if cost_cap and res.est_cost_usd >= cost_cap:
                    res.notes.append("cost cap reached; remaining drafts unjudged")
                    break
                claims = claims_by_pid.get(pid) or []
                chain = {i + 1: claims[i] for i in range(len(claims))}
                finputs = [
                    J.FindingInput(
                        claim_id=int(f.get("claim_id") or 0), term=f.get("term") or "",
                        reference_form=f.get("reference_form") or "", char_offset=0,
                        context_before="", context_after="",
                    ) for f in fs
                ]
                try:
                    v = await J.judge_draft(
                        str(pid), jurisdiction, chain, finputs,
                        anthropic_client=anth, openai_client=oai,
                        system_prompt=system_prompt,
                    )
                except Exception as e:  # one bad draft shouldn't abort the run
                    res.notes.append(f"draft {pid} judge failed: {type(e).__name__}")
                    continue
                res.est_cost_usd += v.total_cost()
                # PER-FINDING agreement (not draft-level): a finding is
                # 'unanimous' only when Sonnet AND gpt-5-mini independently gave
                # the SAME category that became final. A draft-level proxy
                # (disagreement_count==0) is too coarse — one disagreement on a
                # 14-finding US draft would wrongly taint all 14. Caught in probe.
                def _cats(j):
                    return {(fv.claim_id, fv.term): fv.category for fv in (j.verdicts if j else [])}
                s_cats, g_cats = _cats(v.sonnet), _cats(v.gpt_mini)
                vmap = {(fv.claim_id, fv.term): fv for fv in v.final_verdicts}
                for f in fs:
                    fkey = (int(f.get("claim_id") or 0), f.get("term") or "")
                    fv = vmap.get(fkey)
                    cat = fv.category if fv else "ambig"
                    s, g = s_cats.get(fkey), g_cats.get(fkey)
                    agreement = "unanimous" if (s is not None and s == g == cat) else "split"
                    res.judged += 1
                    res.proposed.append(ProposedLabel(
                        jurisdiction=jurisdiction,
                        source=f"corpus:{pid}",
                        claim_id=f.get("claim_id"),
                        term=f.get("term"),
                        reference_form=f.get("reference_form"),
                        verdict=cat,
                        confidence="per-draft-ensemble",
                        proposed_action=action_for(cat),
                        agreement=agreement,
                        rationale=(fv.reasoning[:200] if fv else ""),
                    ))
        finally:
            for c in (anth, oai):
                close = getattr(c, "close", None)
                if close:
                    try:
                        await close()
                    except Exception:
                        pass
    asyncio.run(run())


def _judge_findings(findings, ctx, dry_run, cost_cap, res):
    """Judge a list of finding dicts. ctx(f) -> (jurisdiction, check_class).
    Returns [(verdict|None, rationale)] aligned to findings. Updates
    res.judged / res.est_cost_usd. None verdict = skipped (cost cap)."""
    if dry_run:
        out = []
        for f in findings:
            v, r = _stub_verdict(f.get("term"), f.get("reference_form"))
            res.judged += 1
            out.append((v, r))
        return out
    judges = _import_judges()
    items = []
    for f in findings:
        juris, check_class = ctx(f)
        key = f"{f.get('patent_id','?')}|{f.get('claim_id')}|{f.get('term')}"
        items.append((f, juris, check_class, key))
    results = asyncio.run(_judge_batch(judges, items, cost_cap, res.est_cost_usd))
    out = []
    for (cat, cost) in results:
        if cat is None:
            res.notes.append("cost cap reached; remaining findings unjudged")
            out.append((None, ""))
            continue
        res.judged += 1
        res.est_cost_usd += cost
        out.append((cat, "llm-ensemble"))
    return out


def _collect_finding_dicts(h, records, jurisdiction) -> list[dict]:
    """Re-run the walker collecting full finding dicts (run_walker returns only
    keys). Mirrors run_walker's dispatch."""
    from patentlint.analysis.cn_claims import check_antecedent_basis_cn
    from patentlint.analysis.tw_claims import check_antecedent_basis as tw_fn
    from patentlint.analysis.claims import check_antecedent_basis as us_fn
    fn = {"CN": check_antecedent_basis_cn, "TW": tw_fn, "US": us_fn}.get(jurisdiction)
    if fn is None:
        return []
    out = []
    for rec in records:
        doc = h._build_doc(rec, jurisdiction)
        if doc is None:
            continue
        try:
            for f in fn(doc):
                if isinstance(f, dict) and f.get("category") != "tw_contamination":
                    f = dict(f)
                    f["patent_id"] = rec.get("patent_id")
                    out.append(f)
        except Exception:
            pass
    return out


# ── Mode: reports (triage assist) ──────────────────────────────────────────
def iter_open_reports(limit: int) -> list[dict]:
    """Read the open `report` queue from the private tracker via gh."""
    try:
        raw = subprocess.run(
            ["gh", "issue", "list", "-R", REPORT_TRACKER, "--label", "report",
             "--state", "open", "--limit", str(limit), "--json", "number,body"],
            capture_output=True, text=True, check=True,
        ).stdout
        return json.loads(raw)
    except Exception:
        return []


def parse_payload(body: str) -> dict | None:
    m = re.search(r"```json\s*(.*?)```", body or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def run_reports_mode(limit: int, cost_cap: float, dry_run: bool) -> LoopResult:
    res = LoopResult(mode="reports", jurisdiction=None)
    findings: list[dict] = []
    for issue in iter_open_reports(limit):
        payload = parse_payload(issue.get("body", ""))
        if not payload:
            continue
        for f in (payload.get("findings") or [])[:5]:
            f = dict(f)
            f["_issue"] = issue.get("number")
            f["_jurisdiction"] = payload.get("jurisdiction", "TW")
            findings.append(f)
    res.findings_seen = len(findings)
    verdicts = _judge_findings(
        findings, lambda f: (f.get("_jurisdiction", "TW"), "antecedentBasis"),
        dry_run, cost_cap, res,
    )
    for f, (verdict, rationale) in zip(findings, verdicts):
        if verdict is None:
            continue
        res.proposed.append(ProposedLabel(
            jurisdiction=f.get("_jurisdiction", "?"),
            source=f"report:#{f.get('_issue')}",
            claim_id=f.get("claim_id"),
            term=f.get("term"),
            reference_form=f.get("reference_form"),
            verdict=verdict,
            confidence="dry-run-stub" if dry_run else "llm-ensemble",
            proposed_action=action_for(verdict),
            rationale=rationale,
        ))
    return res


# ── Output ─────────────────────────────────────────────────────────────────
def write_proposed(res: LoopResult, stamp: str) -> Path:
    PROPOSED_LABELS_DIR.mkdir(exist_ok=True)
    out = PROPOSED_LABELS_DIR / f"proposed_{res.mode}_{res.jurisdiction or 'reports'}_{stamp}.json"
    out.write_text(json.dumps(
        {"summary": res.summary(), "proposed": [asdict(p) for p in res.proposed]},
        ensure_ascii=False, indent=2,
    ))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Standing dev-time walker-FP loop (ADR-159)")
    ap.add_argument("mode", choices=["corpus", "reports"])
    ap.add_argument("--jurisdiction", choices=["CN", "TW", "US"], default="TW")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--cost-cap", type=float, default=5.0, help="USD hard cap on LLM spend")
    ap.add_argument("--dry-run", action="store_true", help="no LLM spend; deterministic stub verdicts")
    ap.add_argument("--judge", choices=["per-draft", "per-finding"], default="per-draft",
                    help="per-draft = full claim-chain Sonnet ensemble (more accurate, default)")
    ap.add_argument("--stamp", default="run", help="output filename stamp (pass a date)")
    args = ap.parse_args()

    if args.mode == "corpus":
        res = run_corpus_mode(args.jurisdiction, args.limit, args.cost_cap, args.dry_run,
                              judge_mode=args.judge)
    else:
        res = run_reports_mode(args.limit, args.cost_cap, args.dry_run)

    out = write_proposed(res, args.stamp)
    print(json.dumps(res.summary(), ensure_ascii=False, indent=2))
    print(f"\nProposed labels written to: {out}")
    print("Auto-applyable (unanimous walker_fp) feed via apply_proposed_labels.py; "
          "the ADR-111 harness gate + you stay authoritative.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
