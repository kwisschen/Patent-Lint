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

## Status (updated 2026-06-25)
- ✅ **WS-A1** §112 parser → `us_examiner_legit.json` (1,843 apps / 2,964 terms).
- ✅ **WS-E1** (#305) — `term_in_spec` is a DEAD US signal (100% of judged terms in-spec; retires the spec-confidence hypothesis for US).
- ✅ **WS-B1** (#306, CN R40) — CJK direction-noun `向` guard, −121 CN walker_fp / 0 FN. (TW had no analogous bug; deferred-with-evidence.)
- ✅ **WS-A2/A3** (#307) — ODP claims parser (92% parse) + walker↔examiner term-level join (56% recall of surviving examiner defects; 6.9% examiner-confirmed).
- ✅ **WS-A3-at-scale + WS-A4 (in action) + US R18** (#308/#309) — full 1,837-app examiner mining proved US antecedent over-capture is EXHAUSTED except the comparative `than` class (201); shipped US R18 with a DUAL FN-guard (LLM gold + 0/2,965 examiner-confirmed altered). Examiner labels caught a real intro-side FN (US7811436B2 c18) → reference-side-only design.
- ❌ **WS-A4 discriminator — TESTED AND DEAD (2026-06-24, `us_discriminator_probe.py`).** Walker over 1,837 examiner apps (42,982 OCR-surviving findings), authoritative examiner labels, richest deterministic feature set: LR AUC 0.599 / GB AUC 0.625, top-5% bucket precision ~10-13% (need ~70%). **Fourth independent confirmation** (recal_ceiling + confidence_layer + this LR + GB) that no deterministic runtime feature discriminates FP from real §112 defect — the *feature space*, not the labels, is the wall, and runtime is AI-free. **Examiner labels are an FN-guard (shipped US R18), NOT a discriminator signal; CN/TW judging-$ will NOT unlock a CJK discriminator either (labels were never the limit).** See EXAMINER_GROUND_TRUTH_FINDINGS.md.
- ❌ **WS-A4 missed-linkage (cross-branch antecedent resolution) — RE-ATTEMPTED WITH THE EXAMINER GUARD, MEASURED WITHHOLD (2026-07-22).** The June "un-shippable, silenced 17-36 real defects" verdict was against a small LLM-gold sample; the hypothesis was that the authoritative examiner guard might show the true FN count is shippably small. It is the opposite. Running the walker over the 1,837-app examiner corpus and joining recalled examiner-confirmed defects to their `suggested_match.cross_branch` flag: **994 of 2,961 recalled examiner-confirmed §112(b) defects (34%) carry a cross-branch suggestion** (`the test module` 18375168, `the first bit-line` 18368678, `the memory` 19005557, `the single-port ram` 19000081, …). A missed-linkage fix that RESOLVED cross-branch references would silence all 994 — real defects an examiner actually rejected. This is statutorily sound: a claim's `the X` needs antecedent in ITS OWN dependency chain, not a sibling branch, so the cross-branch "match" is never valid antecedent. The current design (FLAG the reference + surface `cross_branch` as a *did-you-mean HINT*, never resolve) is correct and validated. **Do NOT re-attempt cross-branch resolution.** The examiner guard did not unblock it; it quantified the wall at 34% recall loss.
- ✅ **Engine 3 (ref-numeral D1) SHIPPED US — 2026-06-24/25 (PRs #320 R1, #321 R2; see ENGINE3_FINDINGS.md).** −707 FIX-tier D1 false assertions / 0 FN over the 705-draft US corpus (7139→6432). R1 = element-name over-capture (verb/clause names); R2 = Latin-prefix non-designators (AA mutations + immunology prefixes + X2X). New reusable deterministic FN-guard `refnum_corpus_runner.py` (designator-scoped). US D1 over-capture now EXHAUSTED at the FN-safe frontier (residual = semantic tail + bio symbols outside the denylist; further reduction needs DRAWING data, not scraped).
- ❌ **Engine 2 (spec-support) over-capture — INERT.** `extract_noun_phrases` already cleans via `clean_noun_phrase`, and the 3-tier fuzzy matcher absorbs over-capture tails (confirmed by the US R18 cross-check); spec-support is advisory (#314). No clean over-capture win.
- ⏭ **CN/TW Engine 3 — DEFERRED w/ evidence.** TW shares the CN extractor (one fix covers both); ~6,687 FIX conflicts but the CJK residual is FN-risky without CJK D1 gold (leading-connector→1-char collapse breaks `与门`). Future-safe candidate = connector-variant DEDUP with a CJK FN-guard.
- ⏭ **Remaining free levers (thin):** CN/TW Engine 3 (needs the careful connector-dedup or CJK gold); Engine-3 US bio-symbol denylist extensions as new symbols surface; TP reports from real drafts (drain via /triage-report). **Do NOT spend judging-$ on the discriminator** (proven dead). The irreducible semantic tail stays in the FIX/advisory bucket — an AI-free checker ceiling, framed as candidate flags for attorney review.

## Self-audit / correction loops (mandatory every chunk)
- Every fix: FN-guard `silenced_legit==0` + fixture harness `protect_violations==0` + targeted pytest + CI green. **US fixes additionally pass the examiner-§112 FN-guard (0 of 2,965 examiner-confirmed defects altered)** — authoritative, stronger than the LLM-gold sample. Auto-narrow/defer on FN.
- Every measurement: sanity-check against known cases before trusting a number (e.g. the 0%-overlap artifact was a version-misalignment, not a result — always ask "is this real or an integration bug?").
- Every turn/session: commit + push everything, update `project_fp_class_campaign.md`, leave a next-session handoff message, **AND report FP-% ended this turn + cumulative** (user standing ask).
- Adjust course on new findings; surface anything significant or $-spending BEFORE acting.

## Reliability × efficiency (why this ordering)
| | best path | reliability | efficiency | 80%? |
|---|---|---|---|---|
| US | EdgeXpert examiner §112 + over-capture | highest (authoritative) | highest (one build, then free) | attainable |
| CN/TW | judging + over-capture | medium (LLM proxy) | lower (recurring $) | attainable, costlier |
