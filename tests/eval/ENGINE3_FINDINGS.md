# Engine 3 — reference-numeral consistency (D1) FP reduction (ADR-159)

The third FP engine in the Path-to-80 campaign. Unlike the §112 antecedent
(Engine 1) and spec-support (Engine 2) checks — whose FP/defect split is
*semantic* and whose discriminator is proven dead on deterministic features —
the D1 reference-numeral check (MPEP § 608.01(g): "the same reference character
should not designate different elements") is **structurally anchored**: the
numeral is an explicit token. So its FN-guard is fully **deterministic and free**
(no LLM gold), and it is the most tractable engine.

## The check
`specification.check_numeral_consistency` extracts every `<element-name, numeral>`
pair from the spec, picks a *canonical* name per numeral, and flags any *outlier*
name that is disjoint from it (Case B) or a same-head-different-ordinal instance
collision (Case A). FIX-tier = asserted error; REVIEW-tier = advisory.

## The harness — `tests/eval/refnum_corpus_runner.py`
Reusable characterizer + deterministic FN-guard over the 705-draft US
scraped-spec corpus (`us_descriptions.json`), with a Google-Patents
body-slicer (strips the ~190k-char classification/citation boilerplate).

- `--characterize` — dumps the FIX-tier conflict pool by class.
- `--snapshot <f>` (before edit) / `--compare <f>` (after edit) — the FN-guard.

**The HARD GATE** is the genuine real-D1 signature: a *truly-removed* conflict
(gone from BOTH tiers, not merely demoted FIX→REVIEW) whose canonical AND ≥1
outlier are BOTH plausible element nouns AND BOTH appear ≥2× (the drafter
consistently used two different element names on one numeral). That is the only
shape a name-cleaning fix could lose as a real FN. The gate is **designator-
scoped**: it excludes known non-element symbols (amino-acid mutations,
immunology/clinical biomarker prefixes, X2X telecom abbreviations), whose
removal is the intended symbol-denylist win, not a lost element conflict.

Two metric artifacts were caught and fixed during the build (sanity-check
every number — ADR-159):
1. **FIX-only-tier tracking** made fix→review *demotions* look like silenced
   conflicts (false FN). Fixed by tracking both tiers; a demotion is a win.
2. **Generic `-ing`/`-s` rejection** wrongly dropped real patent nouns
   (`grating`/`winding`/`cladding`/`outputs`/`inputs`) → would silence real D1s
   (`output grating` vs `second grating`; `waveguide inputs` vs `waveguide
   outputs`). Restricted to unambiguous signals only.

## Shipped — US

### R1 (PR #320, −538 FIX-tier conflicts, 0 FN)
Element-name **over-capture**: sentence context (verbs, gerunds, adverbs, clause
fragments) bled into the captured name, so one numeral was "named" by junk
(`displaying`, `be executed by processor`, `preferably`, `do not generate`) and
fired a phantom conflict. `_is_plausible_element_name` in `_detect_d1_conflicts`
drops a name whose HEAD is a verb/gerund/adverb or that contains a clause marker
(`be/is/are/that/which/not`). FN-safe by construction (a real D1 needs two
distinct element NOUNS). Uses ONLY unambiguous signals — curated `_VERB_STOPS` /
`_ADVERB_STOPS` / `_ING_VERB_ONLY` (reused from the §112 walker — cross-CHECK) +
the `-ed` participle test + `-ly` adverbs + a curated `-ing`/base-verb denylist.
**No generic `-ing`/`-s` rule** (see artifact 2 above).

### R2 (PR #321, −169 FIX-tier conflicts, 0 FN)
Latin-prefix non-designators — symbols mis-read as reference designators:
1. **Amino-acid substitution notation** `[IUPAC]\d{2,4}[IUPAC]` (`K417T`,
   `D614G`, `L234F`). The 20-letter IUPAC set spares uppercase-suffixed
   designators (`U1A`/`Q2B`); the ≥2-digit residue position spares single-digit
   EE/X2X forms (`C2D`), so no electronic designator matches.
2. **Immunology/clinical leading-prefix** denylist (`CD`/`CLDN`/`IGG`/`IGM`/
   `IGA`/`IGE`/`IGD`/`IL`/`TNF`/`IFN`/`HBA`) — curated like the existing
   gene/protein denylist (`HER2`/`CDK4`/`EGFR`).
3. **X2X** communication-mode abbreviations (`D2D`/`V2V`/`V2I`/`V2N`/`V2P`/
   `V2X`/`V2G`/`M2M`) added to `_LATIN_PREFIX_DENYLIST`.

All 65 designator-scoped removals were read and confirmed to be bio markers, AA
mutations, or telecom abbreviations — never `R1`/`C2`/`IC3`/`LD1`.

**Cumulative US Engine 3: −707 FIX-tier D1 false assertions, 0 FN** (7139 → 6432
FIX-tier conflicts over the corpus). Both rounds covered by the D1
corpus-mutation gate + `TestD1ElementNameOverCapture` +
`TestD1BioSymbolAndMutation` unit/integration tests.

## US frontier reached
A post-R2 `--characterize` classifies the remaining ~6,432 FIX conflicts as all
`protect` (no over-capture left by the FN-safe predicate). The residual is the
**semantic tail** — method-step / time-slot numbers (`both`, `current time`
bound to numerals 14–20 in a comm-method patent), prose-symbol noise, and bio
symbols outside the curated denylist. Reducing further would need DRAWING data
(to tell a real reference numeral from a method-step / time-slot number), which
is not currently scraped. Same ceiling shape as the antecedent engine.

## CN / TW — deferred with evidence
TW D1 **reuses** the CN extractor (`tw_specification._cjk_extract_numeral_name_pairs`
/`_cjk_detect_d1_conflicts` are aliases of the `_cn_*` functions), so a CJK fix
is a single change in `cn_specification.py` covering both. CN/TW over-flag too
(~6,687 FIX conflicts over `cn_descriptions.json`), but the CN extractor is
already mature (`_cn_strip_trailing_verb`, `_CN_FRAGMENT_MARKERS`, extensive
measurement/process-context exclusion). The residual CJK FP classes are
**FN-risky without CJK D1 judged gold**:
- **Leading-connector → 1-char collapse** (`和缸`/`及缸`/`于缸` → `缸`): the strip
  is blocked at ≥3 chars precisely because reducing to a 1-char noun is unsafe —
  `与门` (AND gate) → `门` would be a real FN.
- Bio symbols + clause fragments need delicate CJK judgment.

The documented future-safe candidate is a **connector-variant DEDUP**: merge
names that are identical after stripping a leading connector (`和`/`及`/`于`/…)
*only when another name shares the residual* — never dropping a standalone real
noun. It needs its own careful round with a CJK FN-guard; marginal yield is low,
so it was not rushed unsupervised.

## Engine 2 (spec-support) — inert for over-capture
`claims.check_spec_support` extracts claim noun phrases via
`utils.extract_noun_phrases`, which already calls `clean_noun_phrase`, and then
matches against the spec with a 3-tier (exact / stemmed-window / word-window)
fuzzy matcher that **already absorbs over-capture tails** (confirmed by the US
R18 cross-check, where the comparative-tail mirror was inert). Spec-support is
also now ADVISORY (#314). So there is no clean over-capture win in Engine 2; the
cleaner shared helpers it would inherit from Engine 3 do not move its needle.

## Reproduce
```
python3 tests/eval/refnum_corpus_runner.py --juris US --characterize
python3 tests/eval/refnum_corpus_runner.py --juris US --snapshot /tmp/pre.json
# ... edit specification.py ...
python3 tests/eval/refnum_corpus_runner.py --juris US --compare /tmp/pre.json
```
