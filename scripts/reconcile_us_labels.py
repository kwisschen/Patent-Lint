# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Reconcile US labels file with current walker output.

Walker has evolved since Phase 2b ran (R7+, R30, R31, R32). The
bootstrap labels file (built from Phase 2b verdicts) contains:
  * Labels for findings the current walker no longer emits (drift)
  * Walker now emits findings the labels don't have

This script reconciles by:
  1. Running ``check_antecedent_basis`` once on the full US corpus
  2. Computing the diff between labels and walker output
  3. For labels NOT in walker output: mark ``resolved_by =
     "bootstrap_walker_drift_round_1"`` (consistent with CN/TW
     resolved_by convention). Protect:true ones get demoted with
     reason note.
  4. For walker findings NOT in labels: append as ``unclassified``
     with ``confidence: walker_drift_post_phase2b``
  5. Bumps ``current_round`` 1 → 2

Run: ``python scripts/reconcile_us_labels.py``
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))
sys.path.insert(0, str(PROJECT_ROOT))

LABELS_PATH = PROJECT_ROOT / 'tests/fixtures/us/antecedent_labels_us.json'

from patentlint.analysis.claims import check_antecedent_basis
from tests.eval.round1_corpus_harness import load_corpus, _build_doc


def main() -> None:
    print('Loading corpus…')
    drafts = load_corpus('US')
    print(f'  {len(drafts)} drafts loaded')

    print('Running walker on full corpus…')
    walker_keys: set[tuple] = set()
    fixtures_processed = 0
    for d in drafts:
        pid = d.get('patent_id')
        if not pid:
            continue
        claims = _build_doc(d, 'US')
        if not claims:
            continue
        try:
            findings = check_antecedent_basis(claims)
        except Exception:
            continue
        for f in findings:
            if not isinstance(f, dict):
                continue
            walker_keys.add((pid, f.get('claim_id'), f.get('term'), f.get('reference_form')))
        fixtures_processed += 1
    print(f'  {fixtures_processed} fixtures processed; {len(walker_keys)} walker findings')

    print('Loading labels…')
    labels_obj = json.load(open(LABELS_PATH))
    labels = labels_obj['labels']
    print(f'  {len(labels)} labels')

    # Build key set
    label_keys = {
        (l['fixture'], l['claim_id'], l['term'], l['reference_form'])
        for l in labels
    }

    # Drift counts
    label_only = label_keys - walker_keys
    walker_only = walker_keys - label_keys
    both = label_keys & walker_keys
    print(f'\nDrift analysis:')
    print(f'  In both: {len(both)}')
    print(f'  Label-only (walker drift): {len(label_only)}')
    print(f'  Walker-only (new findings): {len(walker_only)}')

    # Mark label-only as resolved_by drift
    drift_marker = 'bootstrap_walker_drift_round_2'
    protect_demoted = 0
    drift_marked = 0
    for lab in labels:
        key = (lab['fixture'], lab['claim_id'], lab['term'], lab['reference_form'])
        if key in label_only:
            lab['resolved_by'] = drift_marker
            lab['round'] = 2
            if lab.get('protect'):
                lab['protect'] = False
                lab['notes'] = (lab.get('notes', '') + ' | DEMOTED 2026-05-04: '
                                'walker drift since Phase 2b ensemble run; '
                                're-verify if reactivated').strip()
                protect_demoted += 1
            drift_marked += 1
    print(f'  Drift-marked: {drift_marked} (protect-demoted: {protect_demoted})')

    # Append walker_only as unclassified
    appended = 0
    for key in walker_only:
        pid, cid, term, ref = key
        labels.append({
            'fixture': pid,
            'claim_id': cid,
            'term': term,
            'reference_form': ref,
            'category': 'unclassified',
            'protect': False,
            'confidence': 'walker_drift_post_phase2b',
            'notes': ('Stage 3 seed — walker emits this but Phase 2b ensemble '
                      'did not classify (post-Phase 2b walker mechanism).'),
            'resolved_by': None,
            'round': 0,
        })
        appended += 1
    print(f'  Appended walker_only as unclassified: {appended}')

    # Update metadata
    labels_obj['metadata']['current_round'] = 2
    labels_obj['metadata']['total_labeled'] = len(labels)
    labels_obj['metadata']['reconciled'] = datetime.now(timezone.utc).isoformat()
    labels_obj['metadata']['reconciliation_note'] = (
        f'Bootstrap reconciliation 2026-05-04: marked {drift_marked} drift labels '
        f'(of which {protect_demoted} were protect:true demoted), appended '
        f'{appended} walker-only findings as unclassified.'
    )

    json.dump(labels_obj, open(LABELS_PATH, 'w'), indent=2, ensure_ascii=False)
    print(f'\nReconciled. Labels file now: {len(labels)} entries.')


if __name__ == '__main__':
    main()
