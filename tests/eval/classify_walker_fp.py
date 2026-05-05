# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Classify TW walker_fp findings into over-capture vs trivially-amendable.

The LLM ensemble flattens two structurally different classes into
`walker_fp`:

  1. **True walker over-capture** — captured text is a fragment, verb-
     suffixed, or boundary-broken. Walker bug; should not have emitted.
     Drafter-amend likelihood: 0% (the text isn't a real element).

  2. **Trivially-amendable defect** — captured text is a clean noun
     phrase that's in spec/symbol_table but missing claim-level intro.
     Walker is correct under strict §26 第3項. Drafter-amend likelihood:
     ~100% (one-line fix: add `一X` to claim 1 preamble).

Eliminating only class 1 is the actual precision goal. Silencing class 2
hides real defects from drafters. This script estimates the split
(heuristic, not perfect) so we can size the walker-tightening backlog.

Output on TW supplement_v2 (n=8180 walker_fp findings, 2026-05-05):
  - over_capture: ~13% (1086 findings; targets for walker-mine R62+)
  - trivially_amendable: ~87% (7094 findings; KEEP emitting per statute)

Top over-capture clusters by frequency:
  - Length 11-12 chars: 452 (greedy noun extension past natural boundary)
  - Latin-mid-CJK + paren: 130 (paren-overgreedy variant)
  - 系統/結構/機構/模型 head-noun overshoots
  - 合蛋 (結合蛋白 truncation), 指令/命令/操作 verb-vs-noun ambiguity
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

# Trailing 1-char markers that almost always indicate over-capture.
# 令 is intentionally EXCLUDED here even though it's a particle, because
# 指令/命令 are common legitimate noun tails — flagging them inflates
# the over-capture estimate. Real over-captures with 令 tail are caught
# by the length-> 10 rule instead.
_VERB_PARTICLES = ("係", "為", "具", "有", "於", "將", "由", "在", "可", "被", "作", "使", "即", "所")
_BOUNDARY_VERBS = ("讀", "寫", "送", "接", "連", "結", "處", "理", "形", "生", "產", "推", "執")


def is_over_capture(term: str, in_desc: bool, in_st: bool) -> bool:
    """Heuristic: true iff the captured text looks like a walker bug.

    Imperfect — false-positives on legitimate long compound nouns; false-
    negatives when verb-noun ambiguity allows clean trailing pattern.
    Use as directional signal only, not as silencing trigger.
    """
    if not term:
        return True
    if len(term) > 10:
        return True
    if term[-1] in _VERB_PARTICLES:
        return True
    if any(term.endswith(b) and len(term) > len(b) + 1 for b in _BOUNDARY_VERBS):
        return True
    if not in_desc and not in_st:
        return True
    return False


def main() -> int:
    from tests.eval.measure_term_in_desc import (
        extract_inline_symbol_table_names,
        load_sv2_verdicts,
    )
    from tests.eval.measure_tipo_anchor import extract_inline_symbol_pairs
    from tests.eval.round1_corpus_harness import load_corpus

    from patentlint.analysis.tw_claims import check_antecedent_basis
    from patentlint.models import SymbolEntry, TwPatentDocument
    from patentlint.parser.claims_tw import parse_tw_claims

    descs = json.loads((PROJECT_ROOT / "tests/eval/tw_descriptions.json").read_text())
    verdicts = load_sv2_verdicts()
    sv2 = json.loads(
        (PROJECT_ROOT / "tests/eval/phase2b_results_supplement_v2.json").read_text()
    )
    sv2_pids = {v["patent_id"] for v in sv2["verdicts"] if v.get("jurisdiction") == "TW"}

    over_capture = 0
    trivially_amendable = 0
    over_capture_terms: list[str] = []

    for rec in load_corpus("TW"):
        pid = rec.get("patent_id")
        if pid not in sv2_pids or pid not in descs:
            continue
        claims_text = rec.get("claims") or []
        if not claims_text:
            continue
        paragraphs = [f"{i+1}. {c}" for i, c in enumerate(claims_text)]
        parsed = parse_tw_claims(paragraphs)
        if not parsed:
            continue
        desc = (descs.get(pid) or {}).get("description") or ""
        st_names = extract_inline_symbol_table_names(desc)
        pairs = extract_inline_symbol_pairs(desc)
        st_entries = [SymbolEntry(numeral=n, name=v) for n, v in pairs.items()]
        doc = TwPatentDocument(
            claims=parsed,
            symbol_table=st_entries,
            input_format="google_patents_html",
        )
        try:
            results = check_antecedent_basis(doc)
        except Exception:
            continue
        for f in results:
            key = (pid, f.get("claim_id"), f.get("term"), f.get("reference_form"))
            if verdicts.get(key) != "walker_fp":
                continue
            term = f.get("term", "")
            in_desc = bool(term) and term in desc
            in_st = bool(term) and term in st_names
            if is_over_capture(term, in_desc, in_st):
                over_capture += 1
                over_capture_terms.append(term)
            else:
                trivially_amendable += 1

    total = over_capture + trivially_amendable
    print(f"TW supplement_v2 walker_fp findings: {total}")
    print(f"  TRUE OVER-CAPTURE (walker-tighten target): "
          f"{over_capture} ({100*over_capture/max(total,1):.1f}%)")
    print(f"  TRIVIALLY AMENDABLE (real defect under §26 第3項): "
          f"{trivially_amendable} ({100*trivially_amendable/max(total,1):.1f}%)")
    print()
    print("Top trailing-2 patterns in over-capture set:")
    tail_2 = Counter(t[-2:] for t in over_capture_terms if len(t) >= 2)
    for pat, n in tail_2.most_common(15):
        print(f"  {pat!r}: {n}")
    print()
    print("Length distribution:")
    lens = Counter(len(t) for t in over_capture_terms)
    for L in sorted(lens.keys()):
        print(f"  len={L:>3}: {lens[L]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
