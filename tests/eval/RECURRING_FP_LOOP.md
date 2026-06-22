# Stopping recurring walker false positives — the dev-time AI loop (ADR-159)

**Status:** foundation built + validated end-to-end (this PR). Standing-run + harness-feed are the next increments.
**Constraint:** dev-time only. PatentLint's runtime stays 100% AI-free — the "No AI" badge is about runtime; this is the same posture as ADR-158.

## The problem, precisely

You keep feeding error reports and keep seeing the **same FP classes** come back. That isn't sloppiness — it's a structural gap:

1. A walker FP fires on a real firm draft.
2. The fix lives in `/walker-round`, whose safety is the **ephemeral-sim drift gate**: it replays the proposed relaxation over the *labeled fixture corpus* and refuses to ship if any `protect:true`/`legit` finding disappears (an FN).
3. **But the draft that triggered the FP is never stored** (Privacy §6) and is **not in the fixture corpus**. So the gate has nothing to validate the fix against → the fix is deferred, or shipped blind → the class recurs on the next draft.

This is **corpus isolation**. The 69 walker reports triaged this run are all corpus-isolated. The fix is not "try harder on each report" — it's to **grow the labeled corpus and judge it with AI** so fixes can be validated and *stick*.

## What already existed (don't rebuild)

PatentLint's `tests/eval/` (ADR-158) already had ~70% of the machinery, already wired to PatentNode's infra:

| Seam | File | Role |
|---|---|---|
| Corpus load + production walker | `round1_corpus_harness.py` (`load_corpus`, `run_walker`, `_build_doc`, `load_ensemble_verdicts`) | Run the **real** walker over real CN/TW/US Google-Patents drafts |
| CJK-calibrated LLM judge | `llm_judges.py` (`judge_finding`: Haiku 4.5 + gpt-5-mini, Sonnet 4.6 tiebreaker) / `per_draft_judge.py` (Sonnet-primary, full-chain, Opus tiebreaker) | Classify each finding: `walker_fp` / `coverage_gap` / `legit_drafting_error` / `diagnostic_mis_attribution` / `ambig` |
| Fixture synthesis | `gate1_reproducer.py` (`make_claim`/`make_doc`) | Build a minimal privacy-safe fixture from a report's context window |
| Ground truth | `phase2b_results*.json` | Seed gold set of judged findings |
| Keys + corpus | `Patent-Analyst/.env`, `Patent-Analyst-corpus/parquet/cn_tw_drafts` | Already read by the eval scripts |

The **missing piece** was a *standing orchestrator* — the existing scripts were one-off "round-1" batches.

## What this PR adds: `recurring_fp_loop.py`

A single orchestrator that chains the seams into a repeatable pipeline, with two modes:

### Mode `corpus` — the durable recurrence fix
`load_corpus` → `run_walker` (production walker on real public drafts) → drop findings already in gold → **LLM-judge the new ones** → emit **proposed labels**. Growing the judged-label set gives `/walker-round`'s drift gate the coverage it lacked, so a relaxation can finally be proven not to regress. *Proposes, never auto-applies* — the ADR-111 harness gate + your sign-off stay authoritative.

### Mode `reports` — triage assist
Read the open `report` queue (private tracker) → synthesize a privacy-safe fixture from each de-identified window → reproduce through the walker → judge it → automatic FP/legit classification for the triage comment.

### Validated this run (real, not stubbed)
- `corpus --jurisdiction TW --limit 10` → 82 walker findings, 73 already-gold, **9 judged by the live Haiku+gpt-5-mini+Sonnet ensemble**, **$0.108** (cap was $2; nightly budget ~$20).
- It already surfaced a real walker bug: `豬瘟病毒可溶性E2重組抗` — the `_CN_NOUN_GROUP{2,12}` 12-char truncation cutting `重組抗原` → `重組抗`.
- `--dry-run` runs the whole chain with **zero spend** (deterministic stub verdicts) — CI-safe; 7 smoke tests lock it.

## Hard constraints honored
- **Dev-time only** — SDKs are an opt-in `[eval]` extra, never a runtime dep; the wheel/runtime is untouched.
- **No raw draft content persisted** — `reports` mode uses only the de-identified window; `corpus` mode uses only public Google-Patents drafts. Proposed labels carry head-noun terms + verdicts, never user claim text.
- **Proposes, never applies** — output is `proposed_labels/*.json` (gitignored); `/walker-round` + human gate the entry into `antecedent_labels_*.json`.
- **Budget-capped** — hard `--cost-cap`; estimate intentionally high so the cap is a real ceiling.

## Roadmap (next increments, not in this PR)
1. **Upgrade `corpus` mode to `per_draft_judge`** (full claim-chain context, Sonnet-primary) — higher CJK accuracy than the per-finding `llm_judges`; the ensemble called many of this run's findings `ambig` precisely because per-finding context is thin.
2. **Auto-propose `/walker-round` input** — cluster the `walker_fp` proposals by mechanism (over-capture vs trailing-residue vs bare-noun-intro) and emit a round plan.
3. **Feed the harness** — a reviewed pathway from `proposed_labels` → `antecedent_labels_*.json` with `resolved_by`/`protect`/`round` per ADR-111.
4. **Judge-calibration guard** — before any model swap, re-score against `phase2b_results*.json` gold (≥75% agreement, mirroring `frontier_baseline_eval.py`) so judge drift can't launder regressions into the labels.
5. **Nightly standing run** — once fire-execution auth is restored (currently broken), schedule `corpus` mode per-jurisdiction; until then, run as a manual CLI (canonical, like the rest of `tests/eval/`).

## Why this ends the recurrence
Each `corpus`-mode run converts unlabeled real-draft walker findings into judged labels. Over a few runs the labeled corpus stops being a thin slice of hand-picked fixtures and becomes a broad, AI-judged map of how the walker behaves on real drafts — including the `protect:true` legit findings that the drift gate needs to guarantee a fix doesn't introduce an FN. At that point `/walker-round` can ship the over-capture/bare-noun-intro fixes that currently defer, and they stay fixed.
