# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# walker_term_quality.py - ENGINE 1 (antecedent / §112(b)) term-quality gate.
#
# WHY THIS EXISTS. The `feedback_carried_without_a_number_is_undone` diagnosis
# of 2026-09-01 named the mechanism by which a whole FP class recurred for
# months: "an engine with no term-QUALITY gate recurs forever, because a count
# gate cannot see term quality." That was fixed for Engine 2 (spec-support) in
# #467, and for Engine 2's US arm in #471.
#
# It was never applied to ENGINE 1. `validate_fix` measures whether the
# antecedent walker's finding COUNT moved and whether gold labels were
# silenced; nothing anywhere asked whether the TERM it emits is a noun phrase.
# And the reporter sees the term: reports #681/#682 were `antecedentBasis`
# findings whose whole complaint was the emitted term
# (`local statistical values respective`), not the count.
#
# First run over the corpora found this class alive and unwatched:
#   TW 54 occurrences / 34 distinct (根據, 計算一, 經過濾結果自, 圓具有一)
#   CN 35 occurrences / 24 distinct (N个变焦透镜一一, 消息从第一)
#   US 28 occurrences /  2 distinct (monitoring operable x22, respective x6)
#
# The classifier is IMPORTED from specsup_corpus_runner rather than copied, so
# the two engines' notions of "structurally not a noun phrase" cannot drift -
# the US round this session was a lesson in what happens when you re-implement
# a sibling's logic instead of reusing it.
#
#   python tests/eval/walker_term_quality.py --juris TW
#   python tests/eval/walker_term_quality.py --juris ALL --show 20
#
# GATE: bad occurrences must not EXCEED the pinned residual. Lowering a pin is
# the next round's win; raising one is a regression.
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent

# Pinned residuals. Each is a documented withhold, not an unexamined failure.
#
#   US  0 - CLOSED 2026-09-02 in two rounds. R49 (`gerund_display_head`)
#           cleaned the `monitoring operable` shape, 22 of the 28, at the
#           EMISSION site so resolution, dedup and the ancestor diagnostic keep
#           the RAW term: 67 renames, count 10839 -> 10839, 0 claims changing
#           count, 0 unpaired-new, examiner guard 1377 -> 1377. R50 dropped the
#           remaining 6 bare `respective` selectors, which were a DIFFERENT
#           shape - the adjective LEADS and the capture truncated before its
#           head, so no trailing strip could ever reach it. R50 needed an
#           ATTORNEY READ, because the ensemble had labelled the identical
#           construction both ways (walker_fp on US11492933B2,
#           legit_drafting_error on US11522827B2).
#
#   TW 54 - leading predicate heads (根據 / 經過濾結果自) and bare-quantifier
#           tails (計算一 / 圓具有一). The TW R49 stranded-determiner gate closed
#           this on the INTRO side; these survive on the REFERENCE side.
#   CN 35 - the same two shapes. CN is additionally why TW R49 was not
#           mirrored: CN drafters name elements with a trailing numeral (密封圈一).
#
#   TW/CN WERE ATTACKED 2026-09-02 AND BOTH MOVES WERE REJECTED WITH NUMBERS.
#   Do not retry either without new evidence:
#   (1) Mirroring the US R49 shape - strip the stranded determiner, then let the
#       existing trailing-verb cascade reach the verb behind it (the US R47
#       "one unhandled token blocks the rest" mechanism). It DOES work
#       sometimes (圓具有一 -> 圓, 第一UE發送一 -> 第一UE) but not reliably: of the
#       54, it leaves 26 still bad and MID-WORD TRUNCATES others
#       (排程資訊做出一 -> 排程資訊做, 行為中一 -> 行), which is the #525
#       under-capture shape. Worse, it would drop the pin 54 -> ~26 while terms
#       like 製品進一步呈現下列 and 主控資料儲存子系統詢問 stay unusable - GAMING THE
#       GATE, because the defect vocabulary below cannot see a trailing verb.
#   (2) Widening that vocabulary with the walker's own trailing-verb denylists
#       (TW 191 members, CN 180). Measured: +275 TW / +494 CN newly flagged,
#       dominated by SINGLE-CHARACTER members firing on real nouns (第一方向 on
#       向, 金屬 on 屬, 操作 on 作, 腔中 on 中). Restricting to multi-character
#       members still flags 135 TW / 130 CN, and those are noun-gray
#       nominalizations a drafter may legitimately name (输入 "the input",
#       檢測 "the detection", 分析 "the analysis"). THE LESSON: A STRIP DENYLIST
#       IS NOT A TERM-QUALITY CLASSIFIER - it encodes "strippable when trailing
#       a head", which is a different question from "is this whole term a noun
#       phrase". A gate that is permanently red gets ignored, so it stays out.
#
# RAISING ANY NUMBER IS A REGRESSION. Lowering one is the next round's win.
_EXPECTED_BAD_ENGINE1: dict[str, int] = {"TW": 54, "CN": 35, "US": 0}


def main() -> int:
    ap = argparse.ArgumentParser(description="Engine-1 walker term-quality gate")
    ap.add_argument("--juris", required=True, choices=["TW", "CN", "US", "ALL"])
    ap.add_argument("--show", type=int, default=12,
                    help="how many distinct bad terms to print per jurisdiction")
    args = ap.parse_args()

    sys.path.insert(0, str(THIS_DIR))
    sys.path.insert(0, str(THIS_DIR.parent))
    from eval.round1_corpus_harness import load_corpus, run_walker
    from eval.specsup_corpus_runner import _term_defects

    jurisdictions = ["TW", "CN", "US"] if args.juris == "ALL" else [args.juris]
    failed = False

    for juris in jurisdictions:
        findings = run_walker(load_corpus(juris), juris)
        bad: collections.Counter = collections.Counter()
        for key in findings:
            term = key[2]
            defects = _term_defects(juris, term)
            if defects:
                bad[(term, defects[0])] += 1

        occurrences = sum(bad.values())
        pinned = _EXPECTED_BAD_ENGINE1.get(juris, 0)
        print(f"\n=== ENGINE-1 TERM-QUALITY gate ({juris}) ===")
        print(f"  findings emitted     : {len(findings)}")
        print(f"  structurally BAD     : {occurrences}"
              f"  ({len(bad)} distinct; pinned residual: {pinned})")
        for (term, reason), n in bad.most_common(args.show):
            print(f"    {n:4d}  {term!r}  <- {reason}")
        if occurrences > pinned:
            print(f"  GATE: FAIL - {occurrences - pinned} MORE than the pinned "
                  f"residual. A new bad-term class was introduced.")
            failed = True
        elif occurrences < pinned:
            print(f"  ** IMPROVED: {pinned - occurrences} fewer than pinned - "
                  f"lower _EXPECTED_BAD_ENGINE1['{juris}'] to {occurrences}. **")
            print("  GATE: PASS")
        else:
            print("  GATE: PASS")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
