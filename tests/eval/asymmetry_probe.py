# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# asymmetry_probe.py - the normalization-asymmetry FP miner (ADR-159, 2026-06-26).
#
# WHY: the trailing-token cluster miner (trailing_token_miner.py) groups ALL
# walker_fp by trailing token; its clean (legit==0) clusters are dominated by
# NOUNS (missed-intro, the semantic wall). This probe finds a DIFFERENT, FN-SAFE
# class: findings where `term` and `suggested_match.term` (did_you_mean) differ
# ONLY by a strippable artifact (a trailing finite verb, a parenthetical gloss, a
# quantifier). When they differ that way, the INTRODUCTION IS RIGHT THERE - the
# walker captured it under a near-identical key - so resolving the normalization
# gap silences the FP WITHOUT hiding a real defect. This reopened the US/TW/CN
# over-capture lever for +226 antecedent FPs after trailing-verb mining was
# "exhausted" (US R19-21, TW R14-15, CN R45).
#
# WORKFLOW: run this → eyeball the trailing-verb / gloss / quantifier clusters →
# batch the clean candidates into the relevant strip set (_STOP_WORDS for US,
# _TRAILING_VERB_DENYLIST_{TW,CN}) → validate_fix.py auto-narrows to the
# silenced_legit==0 subset. Truncation clusters (the LONGER form is the real
# element, e.g. 控制器→控) are the FN-DELICATE under-capture class - NOT a
# trailing-strip target; flagged separately as `trunc?`.
from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent


def _walker(jurisdiction: str):
    if jurisdiction == "US":
        from patentlint.analysis.claims import check_antecedent_basis
        return check_antecedent_basis
    if jurisdiction == "CN":
        from patentlint.analysis.cn_claims import check_antecedent_basis_cn
        return check_antecedent_basis_cn
    from patentlint.analysis.tw_claims import check_antecedent_basis
    return check_antecedent_basis


def main() -> int:
    ap = argparse.ArgumentParser(description="Normalization-asymmetry FP miner")
    ap.add_argument("juris", choices=["US", "CN", "TW"])
    ap.add_argument("--min", type=int, default=2, help="min cluster size to print")
    args = ap.parse_args()

    sys.path.insert(0, str(THIS_DIR))
    import round1_corpus_harness as h

    records = h.load_corpus(args.juris)
    verdicts = h.load_ensemble_verdicts(args.juris)
    walk = _walker(args.juris)

    # cluster the strippable-artifact diff between term and did_you_mean
    tail = collections.Counter()           # over-capture: longer = shorter + tail
    trunc = collections.Counter()          # truncation: shorter is mid-compound cut
    samp: dict = collections.defaultdict(list)
    for r in records:
        doc = h._build_doc(r, args.juris)
        if not doc:
            continue
        pid = r.get("patent_id")
        for f in walk(doc):
            sm = f.get("suggested_match") or {}
            dym = sm.get("term")
            term = f.get("term")
            if not dym or not term or dym == term:
                continue
            key = (pid, f.get("claim_id"), term, f.get("reference_form"))
            if verdicts.get(key) != "walker_fp":
                continue
            longer, shorter = (term, dym) if len(term) > len(dym) else (dym, term)
            if not longer.startswith(shorter):
                continue
            diff = longer[len(shorter):]
            # Latin: a CJK/Latin tail that is a word-suffix (timer→time r) is a
            # truncation tell; a standalone trailing verb is over-capture. We
            # can't perfectly tell, so bucket by whether the tail completes a
            # word boundary in Latin (space-delimited) vs CJK.
            if re.fullmatch(r"[一-鿿]{1,2}", diff) or re.fullmatch(r"[A-Za-z]+", diff.strip()):
                # heuristic: CJK 1-char tail that is a noun-suffix (器/路/线/件...)
                # likely a truncation; else over-capture verb.
                if re.fullmatch(r"[器路線线件管板樑梁层層]", diff):
                    trunc[diff] += 1
                else:
                    tail[diff] += 1
                    if len(samp[diff]) < 3:
                        samp[diff].append((term, dym))

    print(f"== {args.juris} ==  normalization-asymmetry walker_fp (intro exists)")
    print("OVER-CAPTURE tails (FN-safe strip candidates; verify each is a verb, not a noun):")
    for w, ct in tail.most_common(40):
        if ct >= args.min:
            print(f"  {ct:3} {w!r}  {samp[w][:2]}")
    if trunc:
        print("TRUNCATION tails (FN-DELICATE under-capture; NOT strip targets):")
        for w, ct in trunc.most_common(15):
            if ct >= args.min:
                print(f"  {ct:3} {w!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
