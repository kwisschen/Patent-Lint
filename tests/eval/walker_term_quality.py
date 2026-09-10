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
#
# ── SECOND DEFECT FAMILY, ADDED 2026-09-07: MID-WORD TRUNCATION ──────────────
#
# The string classifier above is a LEXICON: it knows conjunctions, leading
# predicate heads and bare-quantifier tails. It is therefore structurally blind
# to the single largest remaining CJK defect - a capture that stops INSIDE a
# word. `电压箝` (cutting 箝位), `类人行` (cutting 行为), `推车重新定` (cutting
# 定位) are not noun phrases, and no denylist can ever say so, because the
# defect is not a token that should have been stripped - it is a BOUNDARY that
# does not exist.
#
# HOW BADLY THE LEXICON UNDER-COUNTS: it reports 35 bad terms on CN and 54 on
# TW. Segmentation finds 1,070 and 1,209. That is ~30x on CN and ~22x on TW,
# and 554 CN / 530 TW of them carry a gold `walker_fp` verdict - a class of
# roughly the size of the campaign's entire honest cumulative, sitting unwatched
# because the instrument could not see it.
#
# WHY A SEGMENTER AND NOT ANOTHER RULE. Two string detectors were built and
# MEASURED first, and both failed on the same wall. "The term never stands alone
# in the document" flags a real element followed by a VERB (`远程设备传输`,
# `第一設定使用`) at a ~25-30% false-positive rate. "A determiner-marked longer
# form exists" flags 93% of all findings, because the extension matches verbs
# and conjunctions too (`所述顶部和底部限定`). Both reduce to asking whether the
# next character continues a noun or starts a predicate, which is exactly the
# question a segmenter answers and a lexicon cannot. The campaign has this
# lesson already: "if the honest answer is the semantics of the head, there is
# no gate."
#
# jieba is DEV-TIME ONLY and OPTIONAL. It is never imported by `src/`, so the
# runtime stays AI-free and dependency-free and the Pyodide wheel is untouched.
# When it is absent this arm SKIPS with a notice rather than failing, matching
# how the corpus runners already behave without their local-only data. The
# version is pinned, because a segmenter revision would move every count.
#
# US is deliberately excluded: English is space-delimited, so the class cannot
# occur and a segmenter would only add noise.
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
_EXPECTED_BAD_ENGINE1: dict[str, int] = {"TW": 54, "CN": 33, "US": 0}

# Mid-word truncation residuals, re-derived 2026-09-07 with jieba 0.42.1.
# These are a BASELINE to drive DOWN, not an accepted state: each one is a
# capture that stopped inside a word. US is absent by construction (see header).
# RATCHETED 2026-09-10 after TW R57/R59 and CN R68/R69: TW 1209 -> 1155,
# CN 1070 -> 995. Lowering the pin after an improvement is what makes it a
# ratchet - left at the old value, a later regression back to 1209 would pass.
_EXPECTED_MIDWORD: dict[str, int] = {"TW": 1155, "CN": 995}


def _load_segmenter():
    """Return a deterministic CJK cut() or None. Dev-time only, never src/."""
    try:
        import logging

        import jieba
    except ImportError:
        return None
    jieba.setLogLevel(logging.ERROR)
    jieba.initialize()
    return jieba.cut


def _ends_midword(term: str, text: str, cut) -> bool:
    """True when EVERY occurrence of ``term`` in ``text`` ends inside a word.

    One clean occurrence is enough to acquit the term: a drafter who writes the
    element followed by punctuation or a particle anywhere in the document has
    shown where its boundary is. Requiring ALL occurrences to be mid-word is
    what keeps a real name that merely happens to precede a verb out of the
    count - that was the 25-30% false-positive mode of the string detector this
    replaces.
    """
    import re as _re

    starts = [m.start() for m in _re.finditer(_re.escape(term), text)]
    if not starts:
        return False
    for i in starts:
        window = text[i:i + len(term) + 8]
        pos = 0
        straddled = False
        for tok in cut(window):
            if pos < len(term) < pos + len(tok):
                straddled = True
                break
            pos += len(tok)
            if pos >= len(term):
                break
        if not straddled:
            return False
    return True


def _midword_arm(juris, findings, records, cut, show):
    """The mid-word truncation arm. Returns True on FAIL."""
    text = {r["patent_id"]: "\n".join(r.get("claims") or []) for r in records}
    bad: collections.Counter = collections.Counter()
    for key in findings:
        doc = text.get(key[0])
        if doc and _ends_midword(key[2], doc, cut):
            bad[key[2]] += 1
    occurrences = sum(bad.values())
    pinned = _EXPECTED_MIDWORD.get(juris, 0)
    print(f"\n=== ENGINE-1 MID-WORD TRUNCATION gate ({juris}) ===")
    print(f"  findings emitted     : {len(findings)}")
    print(f"  ends INSIDE a word   : {occurrences}"
          f"  ({len(bad)} distinct; pinned residual: {pinned})")
    for term, n in bad.most_common(show):
        print(f"    {n:4d}  {term!r}")
    if occurrences > pinned:
        print(f"  GATE: FAIL - {occurrences - pinned} MORE than the pinned residual.")
        return True
    if occurrences < pinned:
        print(f"  ** IMPROVED: {pinned - occurrences} fewer than pinned - "
              f"lower _EXPECTED_MIDWORD['{juris}'] to {occurrences}. **")
    print("  GATE: PASS")
    return False


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

    cut = _load_segmenter()

    for juris in jurisdictions:
        records = load_corpus(juris)
        findings = run_walker(records, juris)
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

        # Second arm: mid-word truncation. CJK only, and only when the
        # dev-time segmenter is installed.
        if juris in _EXPECTED_MIDWORD:
            if cut is None:
                print(f"\n=== ENGINE-1 MID-WORD TRUNCATION gate ({juris}) ===")
                print("  SKIPPED - the dev-time segmenter is not installed.")
                print('  Install it with:  pip install -e ".[eval]"')
            elif _midword_arm(juris, findings, records, cut, args.show):
                failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
