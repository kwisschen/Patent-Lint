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

## The recalibration ceiling — can free re-weighting fix it? NO. (`recal_ceiling_probe.py`)

Could we just *re-weight* `compute_confidence_score` (free, no new data) to separate FPs from real defects? An **optimal logistic regression** per jurisdiction on the emit-time signals (term length, ref length, has-suggested-match, cross-ref, claim length), 5-fold cross-validated, gives the achievable ceiling:

| Juris | base legit rate | precision at top-10% | at top-30% |
|---|---|---|---|
| US | 37.7% | 39.0% | 36.7% |
| TW | 23.4% | 31.3% | 30.8% |
| CN | 23.0% | 29.6% | 26.8% |

**Even the optimal model is essentially at base rate — ~zero discrimination.** The information needed to tell an FP from a real §112 defect is simply **not present in the claim-local features.** So no recalibration on the current feature set can work. This is the deepest reason the problem is hard: the walker fires with local context, but the disambiguating evidence (does the term appear in the *specification*? is it the same entity as an earlier element, semantically?) lives outside those features.

## Implication for the path to 80–90%

The confidence layer is the right FN-free lever, but the ceiling experiment proves re-weighting current signals is **not enough** — it needs **new information**:
- **Wire `term_in_spec` and other spec-derived signals into the runtime confidence path.** This is the highest-leverage free step. The strongest known signal is dormant in the claims-only corpus; on real drafts the spec text is present. A with-spec evaluation harness is needed to measure it (the current corpus structurally can't).
- **Judging-funded richer features/labels** (the ADR-159 investment): LLM-derived semantic features (is `the X` the same entity as an earlier element?) + a larger, fresher, less-biased label set feed the ADR-158 distillation pipeline. This is the main payoff of the judging $, beyond validating walker fixes.
- Threshold-tuning / re-weighting alone is proven insufficient (ceiling ≈ base rate on claims-local features).

This corroborates the portfolio decision: free walker fixes alone hit a wall (structural lever exhausted on US; TW/CN remaining FPs are the *uncertain* tail — non-unanimous judge verdicts + delicate single-draft tokenization/ordinal cases), so reliable 80–90% needs judging-funded confidence recalibration + the spec-presence signal at runtime.

## Reproduce

```
python tests/eval/confidence_layer_probe.py
```
(Runs the walker over all three corpora; ~5 min. Requires the local gold + corpus.)
