# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""Attribute a TW spurious introduction to the extractor arm that produced it,
and price a predicate-capture gate on that arm.

WHY THIS EXISTS (2026-08-28). ~136 walker FPs were booked behind the
"`所述X的Y` is a reference, not an introduction" lever. Measuring it showed
only 30 of them are the F5a arm; `耦接` / `定位` / `配置` cascade through the
F10/F10b `的NOUN` arm instead, which no F5a gate can see. The diagnosis came
from reading the offending intro's ORIGINAL span and noticing it opened with
`的`. This script makes that a command instead of a manual dig.

  --attribute PATENT_ID --claim N [--term SUBSTR]
      Dump every (original, normalized) intro pair on that claim with the arm
      named, so an FP class is attributed to the right extractor BEFORE any
      gate is written. Arm is read off the span opener:
        所述/該/前述 -> F5a      的 -> F10 / F10b      於/在 -> F7 family

  --gate {f5a,f10}  [--members 儲存,耦接]
      Price the PREDICATE-CAPTURE gate on that arm over the whole TW corpus:
      reject an intro whose RAW capture is not already a clean noun, because a
      capture that ran past the noun into a predicate took a CLAUSE, and the
      clause's subject is a reference rather than a new element. Optionally
      stack trailing-denylist members on top, which is the only way the gate
      can pay for itself (an intro-side tightening only ADDS findings).

MEASURED 2026-08-28 against a 17,631-finding TW HEAD, so a future run can
tell drift from change. Every gate below is the SAME predicate-capture gate,
applied to a different arm:

  --gate f5a                 17734  (+103; 21 new on gold walker_fp, 11 gold
                                     legit recovered, 0 silenced)
  --gate f10                 17647  (+16;  4 on gold walker_fp)   <- cheapest
  --gate f7c                 17773  (+142; 4 on gold walker_fp)
  --gate f5a --members 儲存   17695  (30 silenced / 0 legit / 32 paired,
                                     HONEST YIELD -2)

NONE OF THESE SHIP. An intro-side tightening can only ADD findings, so its
whole value is the trailing members it unblocks - and no single-arm gate
unblocks 耦接 / 定位 / 配置. All three still register a spurious intro with
f5a, f10 AND f7c gated.

WHAT THE ARM HUNT ACTUALLY ESTABLISHED (three attributions, two of them wrong,
which is the point):
  - The 2026-08-25 handoff said the class was `所述X的Y`, i.e. F5a. True for
    儲存 (30 FPs) ONLY.
  - Reading the span said F10/F10b, because it opens with `的`. Also wrong.
  - The real producer on TW202529383A c20 is `_POST_DE_ORDINAL_PATTERN` (F7c,
    `的第Y`), which has NO hygiene gate at all - no ref-prefix rejection, no
    length floor, no component-suffix test. Several arms emit `的`-opening
    spans, so `--attribute` narrows the candidates but does not settle it;
    finish the job by iterating the module's compiled regexes for the one
    whose group(0) equals the offending span exactly.

AND `耦接` HAS TWO SEPARATE BLOCKERS, not one - do not treat its 3 silenced
legit as a single class:
  - `第二端子` (TW202529383A c20): term does NOT contain the token. This is
    the spurious-intro cascade (the 项目经理 shape from CN R63).
  - `負端耦接` (TW202222015A c2/c16): the gold term ITSELF ends in 耦接, so
    the strip re-keys it to `負端`. That is very likely an ADR-111 SHIFT
    rather than an FN, and needs a claim read, not a gate.

TWO TRAPS THIS SCRIPT EXISTS TO AVOID (both cost real time on 2026-08-28):
  1. `_extract_supplementary_intros` returns `cleaned + extras` - it runs
     `clean_noun_phrase_tw` BEFORE returning. A drop-set keyed on RAW captures
     matches NOTHING it emits, and the run then reports a PERFECT NO-OP that
     looks exactly like the R43 "pure mechanism change" signature. The gate
     here is applied inside a re-implementation of the arm's emit predicate,
     and --gate always prints how many emissions it rejected. A rejection count
     of 0 means the probe is broken, not that the gate is safe.
  2. `_TRAILING_VERB_DENYLIST` is a LENGTH-SORTED TUPLE and the ordering is
     load-bearing (break-on-first-match). Members are re-sorted by length here,
     never dropped into a set.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests" / "eval"))


def _arm_of(original: str) -> str:
    if original.startswith(("所述", "該", "前述")):
        return "F5a  (_REF_POSSESSIVE_*)"
    if original.startswith("的"):
        return "F10/F10b (_F10*_BARE_DE_NOUN_RE)"
    if original.startswith(("於", "在")):
        return "F7 family (locative)"
    if original.startswith("一"):
        return "main _INTRO_PATTERN / F5b"
    return "other supplementary arm"


class _GatedPattern:
    """A compiled-regex stand-in that hides matches failing the gate.

    Filtering the arm's OWN iterator is the only faithful way to price this.
    The first version of this probe post-filtered the returned pairs by their
    normalized string and over-dropped by 80 findings (+183 where the real
    in-source gate measures +103), because a normalized form can be produced
    by more than one arm and the post-filter cannot tell them apart. Gating
    here means the arm skips the match exactly as a real `continue` would.
    """

    def __init__(self, inner, group, predicate, counter):
        self._inner = inner
        self._group = group
        self._predicate = predicate
        self._counter = counter

    def finditer(self, text, *a, **kw):
        for m in self._inner.finditer(text, *a, **kw):
            if self._predicate(m.group(self._group)):
                self._counter[0] += 1
                continue
            yield m

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _ran_into_a_predicate(T):
    """True when the RAW capture is not already a clean noun.

    A capture that needed predicate-stripping took a CLAUSE, so its subject is
    a reference rather than a newly introduced element.
    """
    def pred(raw: str) -> bool:
        normalized = re.sub(r"\([A-Za-z0-9]+\)", "", raw)
        return bool(normalized) and T.clean_noun_phrase_tw(normalized) != normalized
    return pred


def _install_f5a_gate(T, counter):
    pred = _ran_into_a_predicate(T)
    T._REF_POSSESSIVE_WITH_NUM = _GatedPattern(
        T._REF_POSSESSIVE_WITH_NUM, 1, pred, counter)
    T._REF_POSSESSIVE_NO_NUM = _GatedPattern(
        T._REF_POSSESSIVE_NO_NUM, 1, pred, counter)


def _install_f10_gate(T, counter):
    pred = _ran_into_a_predicate(T)
    T._F10_BARE_DE_NOUN_RE = _GatedPattern(
        T._F10_BARE_DE_NOUN_RE, "noun", pred, counter)
    T._F10B_BARE_DE_NOUN_RE = _GatedPattern(
        T._F10B_BARE_DE_NOUN_RE, "noun", pred, counter)


def _install_f7c_gate(T, counter):
    """F7c `的第Y` (_POST_DE_ORDINAL_PATTERN).

    This arm has NO hygiene gate of its own - no ref-prefix rejection, no
    length floor, no component-suffix test - it appends whatever it captures.
    It is the arm that actually blocks 耦接 / 定位 / 配置, which the
    2026-08-28 handoff had attributed first to F5a and then to F10/F10b. Both
    were wrong: on TW202529383A c20 the offending span
    `的第二端子耦接至所述第三場效電晶體` is produced HERE.
    """
    T._POST_DE_ORDINAL_PATTERN = _GatedPattern(
        T._POST_DE_ORDINAL_PATTERN, 1, _ran_into_a_predicate(T), counter)


ARMS = {
    "f5a": _install_f5a_gate,
    "f10": _install_f10_gate,
    "f7c": _install_f7c_gate,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--attribute", metavar="PATENT_ID")
    ap.add_argument("--claim", type=int)
    ap.add_argument("--term", default="")
    ap.add_argument("--gate", choices=sorted(ARMS))
    ap.add_argument("--members", default="",
                    help="comma-separated trailing-denylist members to stack on")
    ap.add_argument("--baseline", type=Path,
                    help="validate_fix snapshot to compare against")
    args = ap.parse_args()

    import round1_corpus_harness as h
    from patentlint.analysis import tw_claims as T

    if args.attribute:
        recs = [r for r in h.load_corpus("TW")
                if r.get("patent_id") == args.attribute]
        if not recs:
            print(f"no corpus record for {args.attribute}")
            return 2
        doc = h._build_doc(recs[0], "TW")
        for cl in doc.claims:
            if args.claim and cl.id != args.claim:
                continue
            print(f"=== {args.attribute} c{cl.id} ===")
            for original, normalized in T.extract_introductions_tw(cl):
                if args.term and args.term not in normalized and args.term not in original:
                    continue
                print(f"  {_arm_of(original):34s} {original!r} -> {normalized!r}")
        return 0

    if not args.gate:
        ap.error("pass --attribute or --gate")

    members = [m for m in args.members.split(",") if m]
    if members:
        orig = T._TRAILING_VERB_DENYLIST
        assert isinstance(orig, tuple), "ordering is load-bearing; see module docstring"
        T._TRAILING_VERB_DENYLIST = tuple(
            sorted(set(orig) | set(members), key=len, reverse=True)
        )

    rejected = [0]
    ARMS[args.gate](T, rejected)

    recs = h.load_corpus("TW")
    post = h.run_walker(recs, "TW")

    print(f"gate={args.gate}  members={members or '(none)'}")
    # counts MATCHES suppressed, and the extractor runs more than once per
    # claim, so this is a fired/not-fired signal rather than a finding count.
    print(f"  matches suppressed by the gate : {rejected[0]}")
    if rejected[0] == 0:
        print("  !! ZERO rejections - the probe is broken, not the gate. "
              "See trap 1 in the module docstring.")
    print(f"  findings                       : {len(post)}")

    if args.baseline:
        import collections
        import json
        pre = {tuple(x) for x in json.loads(args.baseline.read_text())}
        verdicts = h.load_ensemble_verdicts("TW")
        rep = h.classify_findings(pre, post, verdicts)
        new, gone = post - pre, pre - post
        gone_dc = {(k[0], k[1]) for k in gone}
        unpaired = [k for k in new if (k[0], k[1]) not in gone_dc]
        paired = len(new) - len(unpaired)

        def v(k):
            x = verdicts.get(k)
            return x.get("category") if isinstance(x, dict) else x

        print(f"  net                            : {len(pre)} -> {len(post)} "
              f"({len(post) - len(pre):+d})")
        print(f"  silenced_walker_fp             : {rep.silenced_walker_fp}")
        print(f"  silenced_legit  (MUST be 0)    : {rep.silenced_legit}")
        print(f"  UNPAIRED-NEW / paired shifts   : {len(unpaired)} / {paired}")
        print(f"  HONEST YIELD (silenced-paired) : {rep.silenced_walker_fp - paired}")
        print(f"  UNPAIRED-NEW gold verdicts     : "
              f"{dict(collections.Counter(str(v(k)) for k in unpaired))}")
        for k in gone:
            if v(k) == "legit_drafting_error":
                print(f"    SILENCED LEGIT: {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
