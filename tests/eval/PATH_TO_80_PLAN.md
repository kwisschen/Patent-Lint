# Path to 80% — locked plan (ADR-159, 2026-06-24)

## Thesis (proven this session)
The antecedent walker over-flags (~70% FP) because it **cannot distinguish a benign reference from a real §112 defect using claim-local features.** Proven three ways: recalibration ceiling ≈ base rate (`recal_ceiling_probe.py`); the missed-linkage fix silenced 17–36 real defects (un-shippable); the confidence score is flat on CN (`confidence_layer_probe.py`). **The bottleneck is LABELS** — every route to 80% (aggressive walker fixes *or* confidence demotion) needs a labeled set to validate against / train on. So: **get authoritative labels cheapest-first**, and run free FN-safe over-capture fixes in parallel.

## Two audited corrections to the v1 framing
1. **EdgeXpert mainly yields authoritative LEGIT labels** (examiner-flagged terms = confirmed real defects), NOT a clean FP/legit oracle — examiner *absence* ≠ benign (examiners miss things, or the issue was amended out pre-exam). Those legit labels are exactly the **FN-guards** the missed-linkage fix needs; the "this is benign" (walker_fp) side still leans on judging/heuristics. Frame EdgeXpert as the **protect-label / recall oracle**, not a precision oracle.
2. **80% is the target the label investment makes *attainable*, not a guaranteed outcome.** The discriminator ceiling on claim-local features is ≈ base rate; whether spec + authoritative labels lift it to 80% must be *measured*, not assumed.

## Workstreams (each WS-x.n is a session-sized chunk)

### WS-A — US examiner ground truth (EdgeXpert) · free · autonomous
- **A1** §112 prose parser → term-level examiner-flagged-legit labels. Target ≥50% extraction coverage of antecedent OAs. Out: `tests/eval/us_examiner_legit.json` (gitignored). *(STARTED this session.)*
- **A2** ODP amended-claims parser (handle `(Currently Amended)`, canceled claims, non-sequential numbering) → run the walker on EdgeXpert's 86k apps.
- **A3** Join walker findings ↔ examiner-flagged terms (term-level, version-robust) → true recall (did walker catch examiner-flagged?) + a benign-rate signal (terms walker flags that NO examiner ever flags across the corpus → likely benign). Identify real FP classes.
- **A4** Use examiner-legit as authoritative FN-guards → re-attempt the missed-linkage fix safely; calibrate/train a US confidence discriminator (spec + examiner labels).

### WS-B — Over-capture extraction fixes · free · autonomous · all 3
- **B1** CJK tokenization-truncation (CN+TW) — the largest survivor class (`各別機器學習功能`→`…功能性`; `重組抗`→`重組抗原`). FN-guard (silenced_legit==0) + measure win vs proposed labels.
- **B2** spec-support trailing-strips (shared machinery, cross-CHECK) + US residual verb-stops. FN-guard each.

### WS-C — CN/TW labels via judging · COSTS $ → ASK FIRST
- **C1** judging run CN (~$3-5) → grow gold. **C2** TW (~$3-5). **C3** apply → validate CJK fixes + train CJK discriminator. (No examiner data exists for CNIPA/TIPO — judging is the only label path.)

### WS-D — spec-support / ref-numeral probing (uses scraped spec) · free · autonomous · after scrape
- **D1** spec-support corpus runner (scraped CN/TW spec) → probe spec-support FPs at scale (expect over-capture-dominant per code read).
- **D2** ref-numeral runner → probe; test the deterministic-FN-guard hypothesis ($0, name-cleaning).

### WS-E — term_in_spec discrimination test (US, scraped spec on OUR 705 gold corpus) · free · autonomous · after US scrape
- **E1** With real spec + real gold, measure whether term_in_spec discriminates FP from legit on US (the test the claims-only corpus + abstract proxy couldn't do properly). Decides if spec is a usable US confidence signal.

## Sequencing across sessions
- **This session:** lock plan; wait for scrape; **WS-A1** (§112 parser); **WS-E1** when US scrape lands.
- **Next:** WS-B1 (immediate FN-safe FP reduction) ∥ WS-A2→A3→A4 (the strategic build). Then WS-D1/D2. WS-C only after surfacing the $ ask.
- US scraping is NOT a separate need — EdgeXpert dominates for US labels; the scrape's US value is only WS-E1 (term_in_spec on our gold corpus).

## Self-audit / correction loops (mandatory every chunk)
- Every fix: FN-guard `silenced_legit==0` + fixture harness `protect_violations==0` + targeted pytest + CI green. Auto-narrow/defer on FN.
- Every measurement: sanity-check against known cases before trusting a number (e.g. the 0%-overlap artifact was a version-misalignment, not a result — always ask "is this real or an integration bug?").
- Every turn/session: commit + push everything, update `project_fp_class_campaign.md`, leave a next-session handoff message.
- Adjust course on new findings; surface anything significant or $-spending BEFORE acting.

## Reliability × efficiency (why this ordering)
| | best path | reliability | efficiency | 80%? |
|---|---|---|---|---|
| US | EdgeXpert examiner §112 + over-capture | highest (authoritative) | highest (one build, then free) | attainable |
| CN/TW | judging + over-capture | medium (LLM proxy) | lower (recurring $) | attainable, costlier |
