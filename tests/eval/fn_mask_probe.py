# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# fn_mask_probe.py - size the three FALSE-NEGATIVE masks found in wave E
# (2026-10-25). Each is a place where a reference is never checked at all, so
# no user report and no FP-driven round can surface it.
#
#   onechar   references the normalizer cuts to ONE character, which the walker
#             drops without a lookup (carried item 6). Wave E: TW 1,227 / CN 683,
#             led by 所述至少一個處理器 -> 個.
#   embedded  determiners inside an earlier reference's noun run: 所/述 are noun
#             characters, so 所述记录器接收所述警报 is ONE capture and 所述警报 is
#             never looked up (carried item 11). Wave E: TW 2,639 / CN 7,116.
#             YIELD MEASURED wave F (2026-10-26), WITHHELD: the rescan in
#             tests/eval/withheld/item11_embedded_rescan.patch adds TW 427 / CN
#             937 findings, 246 / 507 of them on a term the draft already flags.
#             Read: mostly article-less introductions (FPs under the CN ruling)
#             and predicates glued to the noun, because the capture ends at the
#             NEXT determiner, not at a verb. Gating on "no prefix of 3+ chars
#             mentioned earlier in the chain" leaves TW 26 / CN 91, about half
#             real. The lever is predicate stripping on these spans first.
#   selfintro introduction spans that start right after a determiner, so a
#             quantified reference (所述至少一個X) introduces itself (carried
#             item 13). Wave E: TW 11,691 / CN 5,341. Exposure, not FNs: many
#             of those terms are also introduced properly elsewhere.
#
# USAGE
#   python tests/eval/fn_mask_probe.py onechar  [--juris TW|CN|ALL]
#   python tests/eval/fn_mask_probe.py embedded [--juris ALL]
#   python tests/eval/fn_mask_probe.py selfintro [--juris ALL]
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(THIS_DIR.parents[1] / "src"))

import round1_corpus_harness as h  # noqa: E402
from patentlint.analysis import cn_claims as cn  # noqa: E402
from patentlint.analysis import tw_claims as tw  # noqa: E402

_JURIS = {
    "TW": (tw._REF_PATTERN_CAPTURE, tw.normalize_reference_term, tw.extract_introductions_tw,
           ("所述", "前述", "該")),
    "CN": (cn._REF_PATTERN_CAPTURE_CN, cn.normalize_reference_term_cn, cn.extract_introductions_cn,
           ("所述", "前述", "该")),
}


def _claims(juris: str):
    for rec in h.load_corpus(juris):
        doc = h._build_doc(rec, juris)
        if doc is not None:
            yield rec["patent_id"], doc.claims


def onechar(juris: str, show: int) -> None:
    pat, norm, _, _ = _JURIS[juris]
    members: Counter = Counter()
    for _, claims in _claims(juris):
        for c in claims:
            for m in pat.finditer(c.text):
                t = norm(m.group("prefix") + m.group("noun"))
                if t and len(t) == 1:
                    members[(m.group("noun")[:6], t)] += 1
    print(f"{juris} one-character references dropped: {sum(members.values())}")
    for (raw, t), n in members.most_common(show):
        print(f"    {n:5d}  {raw} -> {t}")


def embedded(juris: str, show: int) -> None:
    pat, _, _, dets = _JURIS[juris]
    runs = hidden = 0
    drafts = set()
    for pid, claims in _claims(juris):
        for c in claims:
            for m in pat.finditer(c.text):
                runs += 1
                k = len(re.findall("|".join(dets), m.group("noun")))
                if k:
                    hidden += k
                    drafts.add(pid)
    print(f"{juris} reference runs {runs}, embedded determiners never checked {hidden}, drafts {len(drafts)}")


def selfintro(juris: str, show: int) -> None:
    _, _, extract, dets = _JURIS[juris]
    n = 0
    drafts = set()
    for pid, claims in _claims(juris):
        for c in claims:
            for orig, _norm in extract(c):
                i = c.text.find(orig)
                if i >= 2 and c.text[:i].endswith(dets):
                    n += 1
                    drafts.add(pid)
    print(f"{juris} introduction spans right after a determiner: {n}, drafts {len(drafts)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Size the wave E false-negative masks")
    ap.add_argument("probe", choices=["onechar", "embedded", "selfintro"])
    ap.add_argument("--juris", default="ALL", choices=["TW", "CN", "ALL"])
    ap.add_argument("--show", type=int, default=15)
    args = ap.parse_args()
    fn = {"onechar": onechar, "embedded": embedded, "selfintro": selfintro}[args.probe]
    for j in (["TW", "CN"] if args.juris == "ALL" else [args.juris]):
        fn(j, args.show)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
