# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# audit_autoapply.py - FN-guard for the recurring-FP loop (ADR-159).
#
# The auto-apply (apply_proposed_labels.py) accepts a finding when the two
# cross-family judges (Sonnet + gpt-5-mini) UNANIMOUSLY call it a walker_fp.
# But "two judges agreed" is not "two judges were right" - if BOTH mis-read a
# real §112 antecedent-basis defect as a false positive, auto-applying it as
# walker_fp would teach a future /walker-round to SILENCE a real defect. That
# is a false NEGATIVE injected into the walker - the exact failure the
# maintainer asked to guard against.
#
# This audit re-judges every auto-applied finding with an ADVERSARIAL SKEPTICAL
# prompt (Sonnet 4.6 by default - the FN-guard's power is the inverted framing,
# not model tier, so Opus would be ~5x the cost for no added value). The prompt
# flips the prior: "two judges called these false positives; your job is to find
# any that are actually REAL §112 defects - err toward flagging real defects."
# Any finding the audit does NOT also confirm as walker_fp is an FN risk and is
# PULLED from the autoapply gold into a reversible quarantine.
#   --model opus  is available for a stronger (costlier) pass when warranted.
#
# Usage:
#   python tests/eval/audit_autoapply.py --jurisdiction TW --cost-cap 1.5
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
EST_PER_DRAFT = 0.02  # conservative Sonnet per-draft estimate for the cap

# Adversarial framing - appended to the calibrated base prompt. Flips the prior
# so the re-judge actively hunts FN risks instead of rubber-stamping the FP call.
_ADVERSARIAL_SUFFIX = """

--- ADVERSARIAL FN-AUDIT MODE ---
Each finding below was already classified as a FALSE POSITIVE (walker_fp) by two
other judges who agreed. Your job is the OPPOSITE check: scrutinise each one for
whether it is actually a REAL §112 / §26 antecedent-basis DEFECT that the walker
correctly caught. Err toward flagging a real defect - wrongly silencing a real
defect (a false negative) is worse than retaining an over-cautious label. Only
output category "walker_fp" if you can point to the term's genuine introduction
(Pattern A/B) earlier in the same claim or an ancestor; otherwise output
"legit_drafting_error" (or coverage_gap / ambig as the rules dictate)."""


def autoapply_path(jurisdiction: str) -> Path:
    return THIS_DIR / f"phase2b_results_{jurisdiction.lower()}_autoapply.json"


def _import():
    sys.path.insert(0, str(THIS_DIR))
    import per_draft_judge as J  # noqa: E402
    import round1_corpus_harness as h  # noqa: E402
    return J, h


def audit(jurisdiction: str, cost_cap: float, model: str = "sonnet") -> dict:
    J, h = _import()
    gold_path = autoapply_path(jurisdiction)
    if not gold_path.exists():
        return {"error": f"no autoapply gold for {jurisdiction}"}
    gold = json.loads(gold_path.read_text())

    # claim texts per draft (needed to re-judge with full chain context)
    claims_by_pid = {r.get("patent_id"): (r.get("claims") or []) for r in h.load_corpus(jurisdiction)}
    from anthropic import AsyncAnthropic
    anth_key, _ = J.load_keys()
    judge_model = J.OPUS if model == "opus" else J.SONNET
    base = J.SYSTEM_PROMPT_US_V1 if jurisdiction == "US" else J.SYSTEM_PROMPT_V2
    system_prompt = base + _ADVERSARIAL_SUFFIX

    # collect (pid, [findings]) from the gold's verdict entries
    drafts = []
    for v in gold.get("verdicts", []):
        if v.get("source") != "adr159-autoapply":
            continue
        ens = v.get("ensemble") or {}
        fs = ens.get("findings") or []
        if fs:
            drafts.append((v.get("patent_id"), fs))

    flips: list[dict] = []   # FN risks - Opus says NOT walker_fp
    confirmed = 0
    spent = 0.0

    async def run():
        nonlocal confirmed, spent
        anth = AsyncAnthropic(api_key=anth_key)
        try:
            for pid, fs in drafts:
                if cost_cap and spent >= cost_cap:
                    break
                claims = claims_by_pid.get(pid) or []
                if not claims:
                    continue
                chain = {i + 1: claims[i] for i in range(len(claims))}
                finputs = [
                    J.FindingInput(claim_id=int(f.get("claim_id") or 0), term=f.get("term") or "",
                                   reference_form=f.get("reference_form") or "", char_offset=0,
                                   context_before="", context_after="")
                    for f in fs
                ]
                user = J._format_user_prompt(str(pid), jurisdiction, chain, finputs)
                try:
                    judgment = await J._judge_draft_anthropic(anth, judge_model, system_prompt, user, len(finputs))
                except Exception as e:
                    flips.append({"patent_id": pid, "error": type(e).__name__})
                    continue
                spent += J.estimate_cost(judgment) or EST_PER_DRAFT
                opus_cat = {(v.claim_id, v.term): v.category for v in judgment.verdicts}
                for f in fs:
                    key = (int(f.get("claim_id") or 0), f.get("term") or "")
                    cat = opus_cat.get(key)
                    if cat == "walker_fp":
                        confirmed += 1
                    else:  # FN risk - Opus disagrees with the unanimous FP call
                        flips.append({"patent_id": pid, "claim_id": f.get("claim_id"),
                                      "term": f.get("term"), "opus_verdict": cat or "missing"})
        finally:
            close = getattr(anth, "close", None)
            if close:
                try:
                    await close()
                except Exception:
                    pass
    asyncio.run(run())

    # Pull FN-risk findings from the gold (reversible: they go to a quarantine file).
    pull_keys = {(x["patent_id"], x.get("claim_id"), x.get("term"))
                 for x in flips if "opus_verdict" in x}
    if pull_keys:
        kept_verdicts = []
        for v in gold.get("verdicts", []):
            ens = v.get("ensemble") or {}
            fs = ens.get("findings") or []
            fvs = ens.get("final_verdicts") or []
            keep_f, keep_v = [], []
            for i, f in enumerate(fs):
                if (v.get("patent_id"), f.get("claim_id"), f.get("term")) in pull_keys:
                    continue
                keep_f.append(f)
                keep_v.append(fvs[i] if i < len(fvs) else {"category": "walker_fp"})
            if keep_f:
                v["ensemble"]["findings"] = keep_f
                v["ensemble"]["final_verdicts"] = keep_v
                kept_verdicts.append(v)
        gold["verdicts"] = kept_verdicts
        gold_path.write_text(json.dumps(gold, ensure_ascii=False, indent=2))
        quarantine = THIS_DIR / f"fn_quarantine_{jurisdiction.lower()}.json"
        prior = json.loads(quarantine.read_text()) if quarantine.exists() else []
        prior.extend(flips)
        quarantine.write_text(json.dumps(prior, ensure_ascii=False, indent=2))

    return {
        "jurisdiction": jurisdiction,
        "drafts_audited": len(drafts),
        "findings_confirmed_fp": confirmed,
        "fn_risks_pulled": len([x for x in flips if "opus_verdict" in x]),
        "errors": len([x for x in flips if "error" in x]),
        "flips": [x for x in flips if "opus_verdict" in x][:20],
        "est_cost_usd": round(spent, 4),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Adversarial Opus FN-audit of auto-applied walker_fp (ADR-159)")
    ap.add_argument("--jurisdiction", choices=["CN", "TW", "US"], required=True)
    ap.add_argument("--cost-cap", type=float, default=1.0)
    ap.add_argument("--model", choices=["sonnet", "opus"], default="sonnet")
    args = ap.parse_args()
    print(json.dumps(audit(args.jurisdiction, args.cost_cap, args.model), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
