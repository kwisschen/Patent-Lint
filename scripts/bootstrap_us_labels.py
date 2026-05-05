"""Bootstrap US antecedent labels file from Phase 2b ensemble verdicts.

Produces ``tests/fixtures/us/antecedent_labels_us.json`` modelled after
the CN/TW labels schema v11. Each label is keyed by
``(patent_id, claim_id, term, reference_form)`` matching what the round-1
corpus harness emits when running ``check_antecedent_basis`` on the
705-draft US corpus.

Promotion rules:
  * legit_drafting_error w/ confidence ≥ 90 → ``protect: true`` (Phase 2c
    validated 100% on Pass 1, 82% on Pass 2; high-confidence legit
    findings are durable seeds).
  * Other categories preserved with ``protect: false``.

Run: ``python scripts/bootstrap_us_labels.py``
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PHASE2B = PROJECT_ROOT / 'tests/eval/phase2b_results_us.json'
OUTPUT = PROJECT_ROOT / 'tests/fixtures/us/antecedent_labels_us.json'


def main() -> None:
    raw = json.load(open(PHASE2B))
    verdicts = raw.get('verdicts', [])

    labels = []
    seen_keys: set[tuple] = set()
    counts = {'legit_drafting_error': 0, 'walker_fp': 0, 'coverage_gap': 0,
              'ambig': 0, 'diagnostic_mis_attribution': 0, 'unclassified': 0}
    protect_count = 0

    for v in verdicts:
        pid = v.get('patent_id')
        if not pid:
            continue
        ens = v.get('ensemble') or {}
        findings = ens.get('findings') or []
        final_verdicts = ens.get('final_verdicts') or []
        for idx, f in enumerate(findings):
            ver = final_verdicts[idx] if idx < len(final_verdicts) else None
            if not ver:
                continue
            cid = f.get('claim_id')
            term = f.get('term')
            ref = f.get('reference_form')
            if cid is None or term is None or ref is None:
                continue
            key = (pid, cid, term, ref)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            cat = ver.get('category', 'unclassified') or 'unclassified'
            confidence = ver.get('confidence', 0) or 0
            counts[cat] = counts.get(cat, 0) + 1

            protect = (cat == 'legit_drafting_error' and confidence >= 90)
            if protect:
                protect_count += 1

            labels.append({
                'fixture': pid,
                'claim_id': cid,
                'term': term,
                'reference_form': ref,
                'category': cat,
                'protect': protect,
                'confidence': f'phase2b_ensemble_conf{confidence}',
                'notes': (ver.get('reasoning') or '')[:300],
                'resolved_by': None,
                'round': 0,
            })

    metadata = {
        'schema_version': 'v11',
        'current_round': 1,
        'created': datetime.now(timezone.utc).isoformat(),
        'source': 'tests/eval/phase2b_results_us.json',
        'source_phase': 'Phase 2b LLM ensemble (Sonnet 4.6 + gpt-5-mini + Opus 4.7 escalation)',
        'phase2c_validation': '2026-05-03 — 15/15 Pass 1 (100%); 9/11 Pass 2 (82%)',
        'total_labeled': len(labels),
        'protect_count': protect_count,
        'category_counts': counts,
        'key_format': '(fixture=patent_id, claim_id, term, reference_form) tuple',
        'note': ('US bootstrap — corpus-backed labels (no docx fixtures locally; '
                 'fixture key == patent_id from Patent-Analyst-corpus parquet records). '
                 'Harness loads corpus via round1_corpus_harness.load_corpus("US").'),
    }

    out = {'metadata': metadata, 'labels': labels}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUTPUT, 'w'), indent=2, ensure_ascii=False)

    print(f'Wrote {len(labels)} labels to {OUTPUT}')
    print(f'Categories: {counts}')
    print(f'Protect:true: {protect_count}')


if __name__ == '__main__':
    main()
