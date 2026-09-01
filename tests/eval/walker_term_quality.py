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

# Pinned residuals as of 2026-09-01, measured on the round-1 corpora. Each is a
# documented withhold, not an unexamined failure:
#   TW 54 - leading predicate heads (根據 / 經過濾結果自) and bare-quantifier
#           tails (計算一 / 圓具有一). The R49 stranded-determiner gate closed
#           this class on the INTRO side; these survive on the REFERENCE side,
#           which R49 deliberately did not touch.
#   CN 35 - the same two shapes. CN is additionally why R49 was not mirrored:
#           CN drafters name elements with a trailing numeral (密封圈一).
#   US 28 - exactly two terms, and the fix for them is MEASURED AND WITHHELD.
#           `monitoring operable` (22x) is a cleaner defect, not a missing
#           rule: stripping `operable` leaves the -ing word `monitoring`,
#           stripping that empties the phrase, and clean_noun_phrase then falls
#           back to the ORIGINAL rather than the last surviving token.
#           Rejecting such a capture outright was measured twice - the broad
#           form (never strip to empty) silenced 19 gold-legit findings, and
#           the narrow form (reject only when the emptying token is a gerund)
#           still silenced 12 for 30 FPs ended. Reading those 12 shows why, and
#           it is the #603-#607 lesson again: they are REAL defects surfaced
#           THROUGH a garbage term - `the comparing indicating`, `the powering
#           up`, `the communicating further communicates`. Dropping the finding
#           loses the defect. The correct fix cleans the TERM while KEEPING the
#           finding, which means separating the intro-side single-word gerund
#           rejection from the reference-side display - a larger change than
#           this gate, and its own round. `respective` (6x) is a bare
#           predicative adjective standing alone, which no trailing strip can
#           reach because there is nothing behind it.
_EXPECTED_BAD_ENGINE1: dict[str, int] = {"TW": 54, "CN": 35, "US": 28}


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
