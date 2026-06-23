# Confidence-display-layer prototype — findings (ADR-159 portfolio)

**Question:** can we reliably reach 80–90% false-positive reduction *user-visible* without FN risk, by demoting low-confidence antecedent findings out of the confident ("FIX") bucket into an advisory tier? Demotion is FN-free — a demoted finding is still shown, just not asserted.

**Method:** `confidence_layer_probe.py` runs the production antecedent walker over the full US/TW/CN Google-Patents corpus, reads `confidence_score` on each finding, joins to the ensemble gold verdict, and sweeps a confidence threshold T. For the confident bucket (score ≥ T): `bucket_precision = (legit + coverage_gap) / all-in-bucket`; `legit_retention = legit_in_bucket / total_legit`.

## Results (2026-06-24)

| Juris | baseline prec | best prec reachable | at that T | legit retention there | verdict |
|---|---|---|---|---|---|
| US | 43.1% | ~71–77% | T≥65 | **7% (catastrophic)** | score reaches target only by dumping 93% of real defects |
| TW | 29.7% | ~42% | T=70 | 1% | never reaches useful precision |
| CN | 28.1% | ~28% (FLAT) | any T | — | **score does not discriminate at all** |

**The current `compute_confidence_score` (v3/v4) is too weak a discriminator to deliver 80–90% precision by threshold-demotion alone.** On CN it is effectively flat (bucket precision ≈ baseline at every threshold); on TW nearly so; on US it can hit 70%+ but only by demoting almost all real defects with the FPs.

## Why — two structural reasons (both fixable)

1. **The score is compressed in 50–65 with no discrimination inside that band.** It only separates at the extreme low end (CN: `score<50` → 7.6% legit, a strong signal — but only 409 of 8,214 findings score that low). The raw signals *do* carry information (CN: term-length ≥8 → 10.7% legit; ≤2 → 31.6%; base 23.0%) — they are just under-weighted / clipped, so most findings pile up in a non-discriminating middle.

2. **The strongest known signal — `term_in_spec` (±15) — is DORMANT in this corpus.** The corpus is **claims-only** (no specification text), so `term_in_spec` is always False and contributes zero lift here. On **real drafts** (which carry the full spec), an antecedent term that *does* appear in the written description is strong evidence the reference is resolvable — so the demotion lever is materially **stronger in production than this prototype can show.** The prototype is a lower bound.

## Implication for the path to 80–90%

The confidence layer is the right FN-free lever, but it needs **recalibration**, not just threshold-tuning:
- Re-weight to spread the score (term-length and pool signals are under-used; the middle band must be broken up).
- Ensure `term_in_spec` (and other spec-derived signals) are wired through at runtime so the production lever exceeds this claims-only floor.
- A larger, fresher, less-biased labeled set (the ADR-159 judging investment) lets the ADR-158 distillation pipeline learn a stronger discriminator — this is the main payoff of the judging $, beyond validating walker fixes.

This corroborates the portfolio decision: free walker fixes alone hit a wall (structural lever exhausted on US; TW/CN remaining FPs are the *uncertain* tail — non-unanimous judge verdicts + delicate single-draft tokenization/ordinal cases), so reliable 80–90% needs judging-funded confidence recalibration + the spec-presence signal at runtime.

## Reproduce

```
python tests/eval/confidence_layer_probe.py
```
(Runs the walker over all three corpora; ~5 min. Requires the local gold + corpus.)
