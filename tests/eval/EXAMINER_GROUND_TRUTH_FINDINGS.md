# US examiner §112 ground truth — WS-A findings (ADR-159 Path-to-80)

Real USPTO examiner §112(b) antecedent-basis rejections from the EdgeXpert ODP
corpus, used as authoritative LEGIT/recall labels for the US antecedent walker.
(See `reference_edgexpert_corpus_db` memory for the DB; `parse_examiner_112.py`
WS-A1 → `us_examiner_legit.json`: 1,843 apps / 2,964 examiner-confirmed terms.)

## WS-A2 — ODP claims parser (`odp_claims_parser.py`)

The reference feared "parse_claims handled 2/80." That was after *naive* markup
stripping. Characterized on a 400-app sample of `corpus_application_text.claims_text`:

| feature | rate | handling |
|---|---|---|
| leading line-number prefix (`12 12.`) | 86% | stripped |
| prosecution markup (`(Currently Amended)` …) | 51% | stripped; canceled stubs dropped |
| embedded OCR SVG/figure tokens | 14% | stripped (precisely-bounded, not greedy) |
| clean `claim N` dependency ref | 86% | preserved |
| mangled dep preamble (number dropped) | 11% | tolerated (term-level join, not claim-number) |
| intra-word OCR damage (`sul fu ric acid`) | — | unrecoverable → bounds join recall |

With `clean_odp_claims`, production `parse_claims` reaches **92% coverage**
(368/400 parse ≥1 claim, 367 ≥2) — far above the WS-A2 ≥50% target.

## WS-A3 — walker ↔ examiner term-level join (`ws_a3_examiner_join.py`)

Join on `(app, normalized-term)`, NOT claim-number — **version-robust**, which
sidesteps the claim-version-skew 0%-overlap artifact the reference warns about.
1,837 / 1,843 examiner apps (100%) are present in `corpus_application_text`.

**Result (400-app sanity sample, sanity-checked against the artifact failure mode):**

| metric | value | reading |
|---|---|---|
| examiner terms | 590 | |
| survive OCR in claim text | **72%** (424) | recall CEILING — a term the OCR destroyed can't be matched |
| walker **recalled** | **56% of surviving** (238) / 40% of all | the walker catches real examiner-flagged §112(b) defects |
| walker findings examiner-confirmed | **7.2%** (310 / 4,294) | benign-rate *signal* (see caveat) |

Spot-checked matches are clean genuine antecedent defects: `the target pieces`,
`the transparent material`, `the purge gas`, `the glass structure`,
`the first user device`, `the odd numbered zones`. **Not a 0%-artifact** — the
signal is non-zero, non-100%, and the matches are real.

### How to read these two numbers (honest framing)
- **Recall 56% (of surviving)** is a *lower bound* on true recall: (a) the 11%
  mangled-dep apps mis-parse → the walker can over- or under-flag; (b) some
  examiner terms were flagged against an *earlier* claim version than the (later,
  amended) `claims_text` — if amended out, it's structurally un-flaggable. So the
  walker catches **at least** ~56% of OCR-surviving real defects. The ~44% gap is
  a genuine RECALL question (the walker under-flags some real defects) — separate
  from, and smaller-signal than, the FP problem.
- **7.2% examiner-confirmed is NOT a 93% FP rate.** Examiner-absence ≠ benign:
  examiners miss limitations, and many §112 issues are amended out before the OA
  that would have named them. This bounds the picture (the walker flags ~14× more
  than examiners confirmed on these apps) but is not proof of FP. Establishing the
  true benign rate needs the full-corpus run + cross-referencing amendment history
  (WS-A3-scale / WS-A4).

## Next (handed off)
- **WS-A3 at scale:** run the join over all 86k EdgeXpert apps (not just the 1,843
  examiner-flagged) → corpus-wide benign-rate signal (terms the walker flags that
  NO examiner ever flagged anywhere → strongest benign candidates). The 1,837-app
  run is slow (~min/400 apps) — batch it.
- **WS-A4:** use `us_examiner_legit.json` as authoritative FN-guards to re-attempt
  the missed-linkage fix safely, and to train/calibrate a US confidence
  discriminator with the examiner labels (the missed-linkage capstone showed
  surface heuristics can't separate real bare-intros from real defects without
  semantic labels — examiner labels are exactly that signal for the recall side).

## Reproduce
```
# 1. pull the claims dump from the Patent-Analyst venv (psycopg2) — see the
#    header of ws_a3_examiner_join.py for the exact query.
# 2. PL venv:
python3 tests/eval/ws_a3_examiner_join.py --limit 400
```
