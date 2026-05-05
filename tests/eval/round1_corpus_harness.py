"""Round-1 corpus harness — runs walker on full corpus + joins to Phase 2b
ensemble verdicts for accuracy measurement.

Usage as a sim gate during walker mechanism development:

    from tests.eval.round1_corpus_harness import (
        load_corpus, run_walker, classify_findings, accuracy_report
    )

    cn_drafts = load_corpus('CN')
    findings = run_walker(cn_drafts, jurisdiction='CN')
    report = classify_findings(findings, ground_truth_path='...')

The ensemble verdicts (Phase 2b results JSONs) classify each walker finding
into walker_fp / coverage_gap / legit_drafting_error / ambig /
diagnostic_mis_attribution. This harness joins by (patent_id, claim_id, term,
reference_form) to give per-finding ground truth.

Accuracy metrics:

  pre_total          = walker findings before mechanism
  post_total         = walker findings after mechanism
  silenced           = pre - post (finding existed, no longer fires)
  false_fires        = post - pre (new finding, didn't exist before)
  silenced_walker_fp = silenced ∩ ensemble verdict 'walker_fp' (GOOD)
  silenced_coverage  = silenced ∩ 'coverage_gap' (GOOD — also walker miss)
  silenced_legit     = silenced ∩ 'legit_drafting_error' (BAD — over-silenced)
  silenced_ambig     = silenced ∩ 'ambig' (neutral)
  silenced_unjudged  = silenced - any verdict (uncertain)

Goal: maximize silenced_walker_fp + silenced_coverage; minimize
silenced_legit + false_fires.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pyarrow.parquet as pq

PROJECT_ROOT = Path('/Users/chrischen/Documents/Projects/Patent-Lint')
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

CORPUS_ROOT = Path('/Users/chrischen/Documents/Projects/Patent-Analyst-corpus/parquet/cn_tw_drafts')
PHASE2B_RESULTS = {
    'CN': [
        PROJECT_ROOT / 'tests/eval/phase2b_results.json',
        PROJECT_ROOT / 'tests/eval/phase2b_results_cn_supplement.json',
    ],
    'TW': [
        PROJECT_ROOT / 'tests/eval/phase2b_results_tw.json',
        PROJECT_ROOT / 'tests/eval/phase2b_results_tw_supplement.json',
    ],
    'US': [
        PROJECT_ROOT / 'tests/eval/phase2b_results_us.json',
    ],
}

# Claim parsing — call PRODUCTION parsers directly so corpus walker output
# matches what real .docx ingestion would produce. Inline regex copies
# diverged from production in three jurisdictions, systematically biasing
# walker FP/precision metrics:
#
#   US: previous fall-through used the TW regex → every dep claim parsed
#       as independent → ancestor chain empty → spurious missing-antecedent
#       findings for every body reference (~25k judged-wfp inflation).
#   CN: previous regex matched only a single claim number per dep, missing
#       range/enumeration/disjunction expansions (`权利要求1至5中任一项`,
#       `权利要求1、2或3`) so the walker reached only the first parent.
#   TW: previous regex didn't model 引用記載型式 (`一種X，具備如請求項N
#       所述的Y`) — those are statutorily INDEPENDENT (own preamble) but
#       still need chain traversal via `quoted_references`. The corpus
#       harness misclassified them as dependent and dropped the
#       quoted_references field, so the walker couldn't resolve intros
#       that production correctly resolves.
#
# Switching to production parsers eliminates regex drift entirely. Each
# corpus record is reshaped to the .docx-style input the production parser
# expects (US/CN already have leading `N.` prefixes; TW needs them
# synthesized from list position). All three return `list[Claim]` with
# proper `dependencies` and (TW) `quoted_references` populated.
from patentlint.parser.claims import parse_claims as _parse_us_claims  # noqa: E402
from patentlint.parser.claims_cn import parse_cn_claims_docx as _parse_cn_claims  # noqa: E402
from patentlint.parser.claims_tw import parse_tw_claims as _parse_tw_claims  # noqa: E402


def _build_doc(record: dict, jurisdiction: str):
    from patentlint.models import CnPatentDocument, TwPatentDocument
    claims = record.get('claims') or []
    if not claims:
        return None
    if jurisdiction == 'US':
        # US corpus claims carry leading `N. ` prefixes already.
        parsed = _parse_us_claims('\n'.join(claims))
        return parsed if parsed else None
    if jurisdiction == 'CN':
        parsed = _parse_cn_claims('\n'.join(claims))
        if not parsed:
            return None
        return CnPatentDocument(claims=parsed, input_format='google_patents_html')
    if jurisdiction == 'TW':
        # TW corpus claims have NO leading `N.` (claim 1 starts directly
        # with `一種…`); synthesize from list position so production
        # `_TW_CLAIM_NUM` regex finds boundaries.
        paragraphs = [f"{i + 1}. {c}" for i, c in enumerate(claims)]
        parsed = _parse_tw_claims(paragraphs)
        if not parsed:
            return None
        return TwPatentDocument(claims=parsed, input_format='google_patents_html')
    return None


def load_corpus(jurisdiction: str) -> list[dict]:
    """Load + dedup-by-patent_id corpus records for a jurisdiction."""
    glob = f'jurisdiction={jurisdiction}/**/*.parquet'
    raw = []
    for p in sorted(CORPUS_ROOT.glob(glob)):
        raw.extend(pq.ParquetFile(p).read().to_pylist())
    seen = set()
    dedup = []
    for r in raw:
        pid = r.get('patent_id')
        if pid and pid not in seen:
            seen.add(pid)
            dedup.append(r)
    return dedup


def run_walker(records: Iterable[dict], jurisdiction: str) -> set[tuple]:
    """Run walker on all records; return set of (patent_id, claim_id, term, reference_form)."""
    from patentlint.analysis.cn_claims import check_antecedent_basis_cn
    from patentlint.analysis.tw_claims import check_antecedent_basis as check_antecedent_basis_tw
    from patentlint.analysis.claims import check_antecedent_basis as check_antecedent_basis_us
    findings = set()
    for rec in records:
        doc = _build_doc(rec, jurisdiction)
        if doc is None:
            continue
        try:
            if jurisdiction == 'CN':
                results = check_antecedent_basis_cn(doc)
            elif jurisdiction == 'TW':
                results = check_antecedent_basis_tw(doc)
            elif jurisdiction == 'US':
                results = check_antecedent_basis_us(doc)
            else:
                continue
            for f in results:
                if isinstance(f, dict):
                    if f.get('category') == 'tw_contamination':
                        continue
                    findings.add((
                        rec['patent_id'],
                        f.get('claim_id'),
                        f.get('term'),
                        f.get('reference_form'),
                    ))
        except Exception:
            pass
    return findings


def load_ensemble_verdicts(jurisdiction: str) -> dict[tuple, str]:
    """Load Phase 2b ensemble verdicts → {(pid, cid, term, ref): category}."""
    verdicts: dict[tuple, str] = {}
    for fname in PHASE2B_RESULTS.get(jurisdiction, []):
        if not fname.exists():
            continue
        d = json.load(open(fname))
        for v in d.get('verdicts', []):
            if v.get('jurisdiction') != jurisdiction:
                continue
            ens = v.get('ensemble') or {}
            findings = ens.get('findings') or []
            final_verdicts = ens.get('final_verdicts') or []
            for idx, f in enumerate(findings):
                ver = final_verdicts[idx] if idx < len(final_verdicts) else None
                if not ver:
                    continue
                key = (
                    v['patent_id'],
                    f.get('claim_id'),
                    f.get('term'),
                    f.get('reference_form'),
                )
                # Last write wins (supplement may overlap main)
                verdicts[key] = ver.get('category', 'unjudged')
    return verdicts


@dataclass
class AccuracyReport:
    pre_total: int
    post_total: int
    silenced: int
    false_fires: int
    silenced_walker_fp: int
    silenced_coverage: int
    silenced_legit: int
    silenced_ambig: int
    silenced_unjudged: int
    false_fires_walker_fp: int
    false_fires_coverage: int
    false_fires_legit: int
    false_fires_unjudged: int

    @property
    def good_silences(self) -> int:
        return self.silenced_walker_fp + self.silenced_coverage

    @property
    def bad_silences(self) -> int:
        return self.silenced_legit

    @property
    def baseline_walker_fp_count(self) -> int:
        # Approx: walker_fp + coverage_gap in pre were "should be silenced"
        return self.pre_total  # we don't have exact split here without verdicts
        # see verbose report

    def __str__(self) -> str:
        return f"""=== ACCURACY REPORT ===
Pre  : {self.pre_total} findings
Post : {self.post_total} findings
Net  : {self.post_total - self.pre_total:+d}

Silenced (good): {self.good_silences}  ({self.silenced_walker_fp} walker_fp + {self.silenced_coverage} coverage_gap)
Silenced (bad) : {self.bad_silences}  ← MUST be near zero
Silenced (other): {self.silenced_ambig + self.silenced_unjudged} ({self.silenced_ambig} ambig + {self.silenced_unjudged} unjudged)
TOTAL silenced  : {self.silenced}

False-fires (walker_fp): {self.false_fires_walker_fp}  (bug-class regression — new findings on terms ensemble already said are walker bugs)
False-fires (legit)    : {self.false_fires_legit}  (these are GOOD — walker now flags real drafting errors)
False-fires (other)    : {self.false_fires_coverage + self.false_fires_unjudged}
TOTAL false-fires      : {self.false_fires}
"""


def classify_findings(
    pre: set[tuple],
    post: set[tuple],
    verdicts: dict[tuple, str],
) -> AccuracyReport:
    """Classify silenced/added findings against ensemble verdicts."""
    silenced = pre - post
    false_fires = post - pre

    sw, sc, sl, sa, su = 0, 0, 0, 0, 0
    for k in silenced:
        cat = verdicts.get(k)
        if cat == 'walker_fp':
            sw += 1
        elif cat == 'coverage_gap':
            sc += 1
        elif cat == 'legit_drafting_error':
            sl += 1
        elif cat == 'ambig':
            sa += 1
        else:
            su += 1

    fw, fc, fl, fu = 0, 0, 0, 0
    for k in false_fires:
        cat = verdicts.get(k)
        if cat == 'walker_fp':
            fw += 1
        elif cat == 'coverage_gap':
            fc += 1
        elif cat == 'legit_drafting_error':
            fl += 1
        else:
            fu += 1

    return AccuracyReport(
        pre_total=len(pre), post_total=len(post),
        silenced=len(silenced), false_fires=len(false_fires),
        silenced_walker_fp=sw, silenced_coverage=sc,
        silenced_legit=sl, silenced_ambig=sa, silenced_unjudged=su,
        false_fires_walker_fp=fw, false_fires_coverage=fc,
        false_fires_legit=fl, false_fires_unjudged=fu,
    )


def baseline_breakdown(findings: set[tuple], verdicts: dict[tuple, str]) -> dict[str, int]:
    """Categorize ALL pre-baseline findings by ensemble verdict."""
    breakdown = {}
    for k in findings:
        cat = verdicts.get(k, 'unjudged')
        breakdown[cat] = breakdown.get(cat, 0) + 1
    return breakdown
