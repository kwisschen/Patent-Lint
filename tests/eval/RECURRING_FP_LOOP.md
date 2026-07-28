# Stopping recurring walker false positives - the dev-time AI loop (ADR-159)

**Status:** foundation built + validated end-to-end (this PR). Standing-run + harness-feed are the next increments.
**Constraint:** dev-time only. PatentLint's runtime stays 100% AI-free - the "No AI" badge is about runtime; this is the same posture as ADR-158.

## The problem, precisely

You keep feeding error reports and keep seeing the **same FP classes** come back. That isn't sloppiness - it's a structural gap:

1. A walker FP fires on a real firm draft.
2. The fix lives in `/walker-round`, whose safety is the **ephemeral-sim drift gate**: it replays the proposed relaxation over the *labeled fixture corpus* and refuses to ship if any `protect:true`/`legit` finding disappears (an FN).
3. **But the draft that triggered the FP is never stored** (Privacy §6) and is **not in the fixture corpus**. So the gate has nothing to validate the fix against → the fix is deferred, or shipped blind → the class recurs on the next draft.

This is **corpus isolation**. The 69 walker reports triaged this run are all corpus-isolated. The fix is not "try harder on each report" - it's to **grow the labeled corpus and judge it with AI** so fixes can be validated and *stick*.

## What already existed (don't rebuild)

PatentLint's `tests/eval/` (ADR-158) already had ~70% of the machinery, already wired to PatentNode's infra:

| Seam | File | Role |
|---|---|---|
| Corpus load + production walker | `round1_corpus_harness.py` (`load_corpus`, `run_walker`, `_build_doc`, `load_ensemble_verdicts`) | Run the **real** walker over real CN/TW/US Google-Patents drafts |
| CJK-calibrated LLM judge | `llm_judges.py` (`judge_finding`: Haiku 4.5 + gpt-5-mini, Sonnet 4.6 tiebreaker) / `per_draft_judge.py` (Sonnet-primary, full-chain, Opus tiebreaker) | Classify each finding: `walker_fp` / `coverage_gap` / `legit_drafting_error` / `diagnostic_mis_attribution` / `ambig` |
| Fixture synthesis | `gate1_reproducer.py` (`make_claim`/`make_doc`) | Build a minimal privacy-safe fixture from a report's context window |
| Ground truth | `phase2b_results*.json` | Seed gold set of judged findings |
| Keys + corpus | `Patent-Analyst/.env`, `Patent-Analyst-corpus/parquet/cn_tw_drafts` | Already read by the eval scripts |

The **missing piece** was a *standing orchestrator* - the existing scripts were one-off "round-1" batches.

## What this PR adds: `recurring_fp_loop.py`

A single orchestrator that chains the seams into a repeatable pipeline, with two modes:

### Mode `corpus` - the durable recurrence fix
`load_corpus` → `run_walker` (production walker on real public drafts) → drop findings already in gold → **LLM-judge the new ones** → emit **proposed labels**. Growing the judged-label set gives `/walker-round`'s drift gate the coverage it lacked, so a relaxation can finally be proven not to regress. *Proposes, never auto-applies* - the ADR-111 harness gate + your sign-off stay authoritative.

### Mode `reports` - triage assist
Read the open `report` queue (private tracker) → synthesize a privacy-safe fixture from each de-identified window → reproduce through the walker → judge it → automatic FP/legit classification for the triage comment.

### Validated this run (real, not stubbed)
- `corpus --jurisdiction TW --limit 10` → 82 walker findings, 73 already-gold, **9 judged by the live Haiku+gpt-5-mini+Sonnet ensemble**, **$0.108** (cap was $2; nightly budget ~$20).
- It already surfaced a real walker bug: `豬瘟病毒可溶性E2重組抗` - the `_CN_NOUN_GROUP{2,12}` 12-char truncation cutting `重組抗原` → `重組抗`.
- `--dry-run` runs the whole chain with **zero spend** (deterministic stub verdicts) - CI-safe; 7 smoke tests lock it.

## Hard constraints honored
- **Dev-time only** - SDKs are an opt-in `[eval]` extra, never a runtime dep; the wheel/runtime is untouched.
- **No raw draft content persisted** - `reports` mode uses only the de-identified window; `corpus` mode uses only public Google-Patents drafts. Proposed labels carry head-noun terms + verdicts, never user claim text.
- **Proposes, never applies** - output is `proposed_labels/*.json` (gitignored); `/walker-round` + human gate the entry into `antecedent_labels_*.json`.
- **Budget-capped** - hard `--cost-cap`; estimate intentionally high so the cap is a real ceiling.

## Update 2026-06-23 - #1/#2/#3 shipped
- **#1 per-draft judge (DONE):** `corpus` mode now defaults to `per_draft_judge` (full claim-chain, Sonnet-primary, Opus tiebreaker). Far more decisive than the per-finding judge - a TW generation run (limit 150, **$4.06**) judged **148 new findings → 134 `walker_fp` / 11 `legit_drafting_error` / 3 other**, vs the per-finding judge's all-`ambig`. Each proposal carries the draft's ensemble `agreement` (`unanimous` when both cross-family judges agreed, no Opus).
- **#2 automated labels feed (DONE):** `apply_proposed_labels.py` auto-applies **unanimous `walker_fp`** into a separate, reversible gold (`phase2b_results_<juris>_autoapply.json`, wired into `round1_corpus_harness.PHASE2B_RESULTS`), queues the rest (`legit`/split → `needs_review_*.json`, human-gated), and GATES by reloading the merged gold. First run auto-applied **28** unanimous FP labels (corpus verdicts 31,552 → 31,580). Like all the gold, the file is **local-only (gitignored)**; the committed harness map skips it gracefully where absent.
- **#3 pre-`/walker-round` step (DONE):** the `walker-round` skill now runs the loop + apply as a mandatory Phase-0.0 so a round always validates against a freshly-judged corpus.

## Roadmap (remaining)
- **Judge-calibration guard** - before any model swap, re-score against the curated `phase2b_results*.json` gold (≥75% agreement, mirroring `frontier_baseline_eval.py`) so judge drift can't launder regressions into the labels.
- **Auto-cluster `/walker-round` input** - group `walker_fp` proposals by mechanism (over-capture / trailing-residue / bare-noun-intro) and emit a round plan.
- **Nightly standing run** - once fire-execution auth is restored (currently broken), schedule `corpus` mode per-jurisdiction; until then it's a manual CLI / the walker-round pre-step.
- **Human-fold the `legit` candidates** - the `needs_review` queue's `legit_drafting_error` verdicts are `protect:true` candidates; fold them into `antecedent_labels_*.json` by hand (they're the FN-guards that let aggressive FP fixes ship safely).

## Why this ends the recurrence
Each `corpus`-mode run converts unlabeled real-draft walker findings into judged labels. Over a few runs the labeled corpus stops being a thin slice of hand-picked fixtures and becomes a broad, AI-judged map of how the walker behaves on real drafts - including the `protect:true` legit findings that the drift gate needs to guarantee a fix doesn't introduce an FN. At that point `/walker-round` can ship the over-capture/bare-noun-intro fixes that currently defer, and they stay fixed.

## The "Zero-FP Sweep" campaign plan (2026-06-23)

Scale: the antecedent walker alone emits ~20,600 confirmed FPs (~70% of its flags) across US/TW/CN; spec-support and ref-numeral are two more engines. The maintainer cannot review fix-by-fix, so **the FN-guard is the reviewer** and the human approves per-*sweep* aggregates.

**Autonomy contract - a fix auto-ships iff ALL hold (deterministic, free):**
1. `validate_fix.py --compare`: `silenced_legit == 0` (corpus FN-guard).
2. fixture harness: `protect_violations == 0`.
3. `pytest tests/analysis tests/test_integration.py tests/test_cross_jurisdiction_discipline.py` green.
4. fix-shape FN-safe: trailing-trim / additive intro-recognition / non-shifting denylist add. Matching-loosening or shifting fixes that can't prove FN-safety → **defer to human**.
5. CI green after push.

A gate-failing fix is auto-narrowed (drop the offending sub-pattern) or deferred + logged - never shipped.

**Deterministic gold-corrector (autonomy keystone, build in Sweep 1A).** When `silenced_legit > 0`, don't subjectively judge FN vs gold-error - run a deterministic Pattern-A intro-presence check on the claim/ancestor text. Exact match → verified gold error → `phase2b_results_<j>_corrections.json`. Otherwise → treat as a real FN → narrow. **Safety cap:** if >5% of a fix's silenced-legit auto-correct as gold errors, HALT - the fix is wrong, not the gold.

**Sweeps (one fresh session each; never carry >1 sweep in a context):** each sweep = (engine, jurisdiction). The session loops over every class autonomously - cluster → probe → minimal fix → FN-guard → auto-ship/narrow/defer → reconcile ADR-111 labels - and emits one aggregate report.

| order | engine | jurisdictions | machinery |
|---|---|---|---|
| 1 | antecedent-basis (~20,600 FPs) | US (finish) → TW → CN | READY |
| 2 | ref-numeral (`specification.py`/`cn_specification.py`) | US → TW → CN | build a refnum `run_walker` variant; FN-guard likely deterministic (FP = name over-capture) → maybe $0 |
| 3 | spec-support (`claims.py`/`tw_spec_support.py`/`cn_spec_support.py`) | US → TW → CN | build a spec-support `run_walker` variant + gold; partial free crossover via shared `clean_noun_phrase` |

**Budget:** fixes + `validate_fix` are free; fresh judging (to extend the per-engine gold) costs ~$3-5/run and the session must ASK first. The full campaign needs more than the initial $20 - funded incrementally per sweep.

**Per-session protocol:** read `project_fp_class_campaign.md` (the durable state) → AUDIT the plan vs current code → run the sweep → aggregate report → update the memory → hand off the next sweep. Keeps context bounded so quality never degrades.
