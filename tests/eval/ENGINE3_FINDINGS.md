# Engine 3 - reference-numeral consistency (D1) FP reduction (ADR-159)

The third FP engine in the Path-to-80 campaign. Unlike the §112 antecedent
(Engine 1) and spec-support (Engine 2) checks - whose FP/defect split is
*semantic* and whose discriminator is proven dead on deterministic features -
the D1 reference-numeral check (MPEP § 608.01(g): "the same reference character
should not designate different elements") is **structurally anchored**: the
numeral is an explicit token. So its FN-guard is fully **deterministic and free**
(no LLM gold), and it is the most tractable engine.

## The check
`specification.check_numeral_consistency` extracts every `<element-name, numeral>`
pair from the spec, picks a *canonical* name per numeral, and flags any *outlier*
name that is disjoint from it (Case B) or a same-head-different-ordinal instance
collision (Case A). FIX-tier = asserted error; REVIEW-tier = advisory.

## The harness - `tests/eval/refnum_corpus_runner.py`
Reusable characterizer + deterministic FN-guard over the 705-draft US
scraped-spec corpus (`us_descriptions.json`), with a Google-Patents
body-slicer (strips the ~190k-char classification/citation boilerplate).

- `--characterize` - dumps the FIX-tier conflict pool by class.
- `--snapshot <f>` (before edit) / `--compare <f>` (after edit) - the FN-guard.

**The HARD GATE** is the genuine real-D1 signature: a *truly-removed* conflict
(gone from BOTH tiers, not merely demoted FIX→REVIEW) whose canonical AND ≥1
outlier are BOTH plausible element nouns AND BOTH appear ≥2× (the drafter
consistently used two different element names on one numeral). That is the only
shape a name-cleaning fix could lose as a real FN. The gate is **designator-
scoped**: it excludes known non-element symbols (amino-acid mutations,
immunology/clinical biomarker prefixes, X2X telecom abbreviations), whose
removal is the intended symbol-denylist win, not a lost element conflict.

Two metric artifacts were caught and fixed during the build (sanity-check
every number - ADR-159):
1. **FIX-only-tier tracking** made fix→review *demotions* look like silenced
   conflicts (false FN). Fixed by tracking both tiers; a demotion is a win.
2. **Generic `-ing`/`-s` rejection** wrongly dropped real patent nouns
   (`grating`/`winding`/`cladding`/`outputs`/`inputs`) → would silence real D1s
   (`output grating` vs `second grating`; `waveguide inputs` vs `waveguide
   outputs`). Restricted to unambiguous signals only.

## Shipped - US

### R1 (PR #320, −538 FIX-tier conflicts, 0 FN)
Element-name **over-capture**: sentence context (verbs, gerunds, adverbs, clause
fragments) bled into the captured name, so one numeral was "named" by junk
(`displaying`, `be executed by processor`, `preferably`, `do not generate`) and
fired a phantom conflict. `_is_plausible_element_name` in `_detect_d1_conflicts`
drops a name whose HEAD is a verb/gerund/adverb or that contains a clause marker
(`be/is/are/that/which/not`). FN-safe by construction (a real D1 needs two
distinct element NOUNS). Uses ONLY unambiguous signals - curated `_VERB_STOPS` /
`_ADVERB_STOPS` / `_ING_VERB_ONLY` (reused from the §112 walker - cross-CHECK) +
the `-ed` participle test + `-ly` adverbs + a curated `-ing`/base-verb denylist.
**No generic `-ing`/`-s` rule** (see artifact 2 above).

### R2 (PR #321, −169 FIX-tier conflicts, 0 FN)
Latin-prefix non-designators - symbols mis-read as reference designators:
1. **Amino-acid substitution notation** `[IUPAC]\d{2,4}[IUPAC]` (`K417T`,
   `D614G`, `L234F`). The 20-letter IUPAC set spares uppercase-suffixed
   designators (`U1A`/`Q2B`); the ≥2-digit residue position spares single-digit
   EE/X2X forms (`C2D`), so no electronic designator matches.
2. **Immunology/clinical leading-prefix** denylist (`CD`/`CLDN`/`IGG`/`IGM`/
   `IGA`/`IGE`/`IGD`/`IL`/`TNF`/`IFN`/`HBA`) - curated like the existing
   gene/protein denylist (`HER2`/`CDK4`/`EGFR`).
3. **X2X** communication-mode abbreviations (`D2D`/`V2V`/`V2I`/`V2N`/`V2P`/
   `V2X`/`V2G`/`M2M`) added to `_LATIN_PREFIX_DENYLIST`.

All 65 designator-scoped removals were read and confirmed to be bio markers, AA
mutations, or telecom abbreviations - never `R1`/`C2`/`IC3`/`LD1`.

**Cumulative US Engine 3: −707 FIX-tier D1 false assertions, 0 FN** (7139 → 6432
FIX-tier conflicts over the corpus). Both rounds covered by the D1
corpus-mutation gate + `TestD1ElementNameOverCapture` +
`TestD1BioSymbolAndMutation` unit/integration tests.

## US frontier reached
A post-R2 `--characterize` classifies the remaining ~6,432 FIX conflicts as all
`protect` (no over-capture left by the FN-safe predicate). The residual is the
**semantic tail** - method-step / time-slot numbers (`both`, `current time`
bound to numerals 14-20 in a comm-method patent), prose-symbol noise, and bio
symbols outside the curated denylist. Reducing further would need DRAWING data
(to tell a real reference numeral from a method-step / time-slot number), which
is not currently scraped. Same ceiling shape as the antecedent engine.

## CN / TW - connector-variant dedup BUILT, MEASURED, and REJECTED (net-negative)
TW D1 **reuses** the CN extractor (`tw_specification._cjk_extract_numeral_name_pairs`
/`_cjk_detect_d1_conflicts` are aliases of the `_cn_*` functions), so a CJK fix
is a single change in `cn_specification.py` covering both. CN/TW over-flag too
(7,282 FIX+REVIEW conflicts / 6,687 FIX over `cn_descriptions.json`), but the CN
extractor is already mature (`_cn_strip_trailing_verb`, `_CN_FRAGMENT_MARKERS`,
extensive measurement/process-context exclusion, `_cn_merge_suffix_clusters`).

The candidate fix was a **connector-variant dedup**: merge names identical after
stripping leading connector/particle chars (`及缸`/`于缸`/`的缸` → `缸`). It was
**implemented with a CJK FN-guard** (`refnum_corpus_runner.py --juris CN`, CJK
plausibility predicate + designator-scoped gate) and **measured on the full
corpus** - then **reverted**, for two empirical reasons:

1. **Net-negative on FP count.** FIX-tier conflicts went 6,687 → 6,698 (**+11
   conflicts**, not fewer): the gate PASSED (0 designator FN) but the merge
   removed 7 and *created 18 new* conflicts. Root cause: connector-variants are
   individually 1× - *below* the digit canonical threshold (2), so they are
   already correctly ignored as noise. Summing them on merge **promotes ignored
   noise to a flagged conflict.** The dedup is counterproductive.
2. **The genuinely-helpful cases can't be touched FN-safely.** Fully collapsing
   `和缸`/`与缸`/`或缸` needs `和`/`与`/`或` in the strip set, but those create
   real FNs: `与门` (AND gate) and `或门` (OR gate) both strip to `门`, so a
   genuine D1 (one numeral on two different gates) would be silenced. The
   1-char-residual clusters (`缸`/`轴`/`框`) live exactly in this danger zone.
   The safe (≥2-char-residual) connector-variants are already collapsed by
   `_cn_merge_suffix_clusters` when the bare noun appears.

**Conclusion:** CN/TW D1 over-capture cannot be reduced FN-safely with
deterministic character rules beyond the existing suffix-merge. It genuinely
needs **CJK D1 judged gold** (none exists) to validate the risky-connector /
1-char-residual merges and the bio-symbol/clause-fragment classes. The runner's
CN FN-guard support is committed so that work is one snapshot/compare away once
gold exists.

## Engine 2 (spec-support) - MEASURED inert for over-capture
`claims.check_spec_support` extracts claim noun phrases via
`utils.extract_noun_phrases`, which already calls `clean_noun_phrase` (so it
already has Engine 1's cleaning - Engines 1 and 2 *share* the extractor), then
matches against the spec with a 3-tier (exact / stemmed-window / word-window)
fuzzy matcher that **absorbs over-capture tails**.

**Measured** over the 705-draft US corpus (`specsup_char.py`): only **189 flags
across 59/703 drafts** (vs Engine 3's ~7,000 and antecedent's thousands). The
189 are dominated by **Google-Patents OCR whitespace-collapse artifacts** -
`comprisesa data line`, `systemreceive`, `value krfor`, `kmno4sulfuric`,
`includingdetermining` - i.e. adjacent words run together in the HTML text
extraction, which does **not** happen in a clean DOCX upload. The genuine
over-capture is already absorbed by the fuzzy matcher; what survives is corpus
extraction noise, and the check is ADVISORY (#314). So there is **no clean
production over-capture FP class** in Engine 2 - confirmed by measurement, not
assumption. (A whitespace-collapse splitter would only improve the eval corpus,
not production, so it was not pursued.)

## Reproduce
```
python3 tests/eval/refnum_corpus_runner.py --juris US --characterize
python3 tests/eval/refnum_corpus_runner.py --juris US --snapshot /tmp/pre.json
# ... edit specification.py ...
python3 tests/eval/refnum_corpus_runner.py --juris US --compare /tmp/pre.json
```

## CORRECTION (2026-06-25, d1_probe.py) - "US over-capture exhausted" ≠ "US D1 clean"
The "US frontier reached" section above is about the OVER-CAPTURE class only. An
LLM probe (Sonnet, 40-sample US "protect"-class) judged it **~100% false
positive** - the structural `_is_plausible_element_name` predicate is a poor
proxy: it classifies ~6,432 US D1 FIX conflicts as "protect" (real-candidate),
but they are dominated by FPs it cannot see - figure numbers read as element
numerals, synonyms/abbreviations of ONE element, over-capture fragments, and
mis-attributed neighbouring numerals. So US D1 is NOT clean; it has a large
graded-FP pool just like CN/TW. The same probe on CN gave ~86%. Caveats: the
corpus is Google-Patents HTML (extraction noise inflates the rate) and it is a
single-judge short-context probe, so the true production rate is high but likely
below 100%. Reducing this pool needs the deterministic-cleaning + gold-FN-guard
program (figure-number / measurement / step-number exclusion, neighbour-numeral
disambiguation, synonym/variant merge), validated against a cheap (~$5) D1 gold
set. Applies to US, CN, and TW.
