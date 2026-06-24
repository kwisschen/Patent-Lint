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

## Does the spec-presence signal transfer? NO — US-only-mild, CJK-counterproductive. (`spec_presence_probe.py`)

The #1 free-ish hypothesis was "wire spec-presence into the confidence signal." Using the corpus `abstract` as a proxy for `term_in_spec`:

| Juris | base legit | P(legit \| in abstract) | P(legit \| not) | demote-if-in: FP removed / legit lost |
|---|---|---|---|---|
| US | 37.7% | 0.296 | 0.403 | 27.6% / 19.2% (favorable-ish) |
| TW | 23.8% | 0.269 | 0.219 | 36.3% / **42.8%** (losing) |
| CN | 23.0% | 0.285 | 0.199 | 33.8% / **45.0%** (losing) |

On **US** the signal points the right way (a term in the abstract is *less* likely a real defect → demotable), but only mildly. On **TW/CN it points the WRONG way** — an in-abstract term is *more* likely a real defect, so demoting on it loses more real defects than FPs. The spec/abstract-presence signal is **jurisdiction-specific**, not a universal lever; CJK calibration must be independent and is the hardest. (The full specification, vs the abstract proxy, may behave better — but this must be measured per-jurisdiction, not assumed.)

## WS-E1 — the FULL spec, not the abstract proxy: `term_in_spec` is a DEAD signal on US. (`term_in_spec_probe.py`)

The probes above used the corpus `abstract` as a proxy because the corpus was claims-only. WS-E1 closes that gap: the full Google-Patents **specification** (description body) is now scraped for all **705/705** US gold drafts (`us_descriptions.json`, gitignored; median spec 225k chars, min 47k). Re-running the spec-presence test against the *real* spec instead of the abstract:

| Juris | judged findings (w/ spec) | term IN spec | term NOT in spec | P(legit \| in) | P(legit \| out) |
|---|---|---|---|---|---|
| US | 7,888 (100% have spec) | **7,888 (100%)** | **0** | 0.377 (= base) | — (empty) |

**`term_in_spec` is non-discriminating on US: 100% of judged claim terms appear in the specification**, so `P(legit | in spec)` is exactly the base rate (37.7%) and the "NOT in spec" cell — the only place a signal could live — is **empty**. Verified not an integration artifact: the matcher returns False for garbage strings, and every one of the 705 specs is ≥47k chars (a 225k-char-median document contains every claim-element noun phrase whether or not the claim properly introduced its antecedent).

This **retires the "wire `term_in_spec` into runtime confidence" hypothesis for US** (the lower-bound caveat in §"Why" / §"Does spec-presence transfer" was optimistic — the full spec is *worse* than the abstract proxy as a discriminator, not better, because it is exhaustive). It is the empirical confirmation of the campaign's **capstone**: §112(b) antecedent basis is claims-internal; the spec always contains the term, so spec-presence cannot tell a benign reference from a real defect. A usable spec-derived signal would have to be far stricter than boolean presence (e.g. term introduced as `a <term>` near a reference numeral, or semantic entity-identity) — i.e. exactly the judging-funded semantic features below, not a free substring test. **Net: spec is NOT a usable US confidence signal; do not finish-then-mine the US scrape for this purpose.** (The scrape remains useful for spec-support/ref-numeral engines, WS-D.)

## Implication for the path to 80–90%

The confidence layer is the right FN-free lever, but the ceiling experiment proves re-weighting current signals is **not enough** — it needs **new information**:
- **Wire `term_in_spec` and other spec-derived signals into the runtime confidence path.** This is the highest-leverage free step. The strongest known signal is dormant in the claims-only corpus; on real drafts the spec text is present. A with-spec evaluation harness is needed to measure it (the current corpus structurally can't).
- **Judging-funded richer features/labels** (the ADR-159 investment): LLM-derived semantic features (is `the X` the same entity as an earlier element?) + a larger, fresher, less-biased label set feed the ADR-158 distillation pipeline. This is the main payoff of the judging $, beyond validating walker fixes.
- Threshold-tuning / re-weighting alone is proven insufficient (ceiling ≈ base rate on claims-local features).

This corroborates the portfolio decision: free walker fixes alone hit a wall (structural lever exhausted on US; TW/CN remaining FPs are the *uncertain* tail — non-unanimous judge verdicts + delicate single-draft tokenization/ordinal cases), so reliable 80–90% needs judging-funded confidence recalibration + the spec-presence signal at runtime.

## WS-A4 — the authoritative-label test closes the discriminator question (2026-06-24, `us_discriminator_probe.py`)

The recalibration ceiling above used the LLM ensemble gold. The last open question was
whether **authoritative** labels (real USPTO examiner §112 rejections) would reveal signal
the noisy LLM gold hid. They do not. Ran the walker over 1,837 examiner apps (42,982
OCR-surviving findings), labeled by examiner-confirmed real defect (6.9% base rate), and
fit a classifier over the **richest deterministic emit-time feature set** (string shape +
chain context + production `confidence_score` + reference-numeral / repeated-reference
identity signals):

| model | AUC | top-5% bucket precision | lift |
|---|---|---|---|
| Logistic regression | 0.599 | 9.6% | 1.39× |
| Gradient boosting | 0.625 | 12.8% | 1.84× |

Even nonlinear + authoritative labels ≈ base rate. **Fourth independent confirmation**
(recal_ceiling + confidence_layer + this LR + GB) — robust across label source, feature
richness, and model class. The discriminator-by-demotion lever is **dead on deterministic
features**. Since runtime is AI-free, this closes it for US, and by the same mechanism the
CN-flat result above is feature-poverty (not label-poverty) — so **judging-$ will not unlock
a CJK discriminator.** The only remaining FP levers are free + deterministic: over-capture
batches + Engine 2/3 sweeps. (Full writeup: `EXAMINER_GROUND_TRUTH_FINDINGS.md`.)

## Reproduce

```
python tests/eval/us_discriminator_probe.py     # WS-A4 discriminator ceiling (examiner labels)
python tests/eval/confidence_layer_probe.py     # threshold sweep, all 3 corpora (~5 min)
python tests/eval/spec_presence_probe.py         # abstract-proxy presence test
python tests/eval/term_in_spec_probe.py US       # WS-E1: full scraped spec (needs us_descriptions.json)
```
(All run the walker over the local corpus + gold; the `term_in_spec` probe additionally needs the gitignored `us_descriptions.json` scrape.)
