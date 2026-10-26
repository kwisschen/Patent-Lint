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
#             Wave J (2026-10-26) SHIPPED the TW "one or more" family (該一或多個X)
#             with its bases. The BROAD rule (every multi-character quantifier,
#             tests/eval/withheld/item13_broad_selfskip.patch) is WITHHELD: TW +205
#             net with 1 gold-legit lost, CN +58; the new findings are mostly
#             residue on both sides of a quantified pair and intros the span
#             hid. CN "one or more" mirror, bare: +50 / -0, unmeasured with the
#             TW bases.
#   stemfallback  references the longest-prefix fallback resolves through a
#             TWO-character stem with a 2+ character tail (carried item 15).
#             Wave G (2026-10-26): TW 1,959 / CN 1,294 (CN tails are verbs:
#             配置, 结合, 操作). Fuller form mentioned after a quantifier
#             anywhere in the draft: TW 546 / CN 83 (an intro the
#             extractor cut short, e.g. an interior-verb cut, which the
#             fallback correctly absorbs); of the rest about half are verb
#             residue on the right element (該UE執行測量 by UE). A guard on a
#             noun-head tail plus "no earlier non-determiner mention" added TW
#             84 findings, about 5 real (abbreviation intros, 第1 vs 第一,
#             第一及第二X distributives, paraphrases like 修改的參數): WITHHELD.
#
# USAGE
#   python tests/eval/fn_mask_probe.py onechar  [--juris TW|CN|ALL]
#   python tests/eval/fn_mask_probe.py embedded [--juris ALL]
#   python tests/eval/fn_mask_probe.py selfintro [--juris ALL]
#   python tests/eval/fn_mask_probe.py stemfallback [--juris ALL]
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
    # Counted at the walker's own drop site (the observer hook), not by
    # re-running the capture regex: the walker extends 能/應/時 compounds
    # after capture, which a regex-only count misses (wave G: the regex-only
    # count was TW 850 / CN 526).
    mod = tw if juris == "TW" else cn
    check = tw.check_antecedent_basis if juris == "TW" else cn.check_antecedent_basis_cn
    members: Counter = Counter()

    def observe(raw: str, term: str, _cid: int) -> None:
        members[(raw[:6], term)] += 1

    mod._ONE_CHAR_DROP_OBSERVER = observe
    try:
        for rec in h.load_corpus(juris):
            doc = h._build_doc(rec, juris)
            if doc is None:
                continue
            try:
                check(doc)
            except Exception:  # noqa: BLE001 - a probe counts what it can
                continue
    finally:
        mod._ONE_CHAR_DROP_OBSERVER = None
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


def stemfallback(juris: str, show: int) -> None:
    mod = tw if juris == "TW" else cn
    check = tw.check_antecedent_basis if juris == "TW" else cn.check_antecedent_basis_cn
    quant = r"(?:一|一種|一个|一個|複數|複數個|多個|多个|至少一|至少一個|至少一个|兩|两|二|若干)"
    tails: Counter[str] = Counter()
    rows: list[tuple[str, str, str]] = []
    cur: dict = {}

    def observe(intro: str, term: str, _cid: int) -> None:
        if len(intro) == 2 and len(term) - len(intro) >= 2:
            rows.append((cur["pid"], intro, term))
            tails[term[2:4]] += 1

    mod._PREFIX_FALLBACK_OBSERVER = observe
    cut_intro = 0
    try:
        for rec in h.load_corpus(juris):
            doc = h._build_doc(rec, juris)
            if doc is None:
                continue
            cur["pid"] = rec["patent_id"]
            n0 = len(rows)
            try:
                check(doc)
            except Exception:  # noqa: BLE001 - a probe counts what it can
                continue
            text = "".join(c.text for c in doc.claims)
            for _pid, stem, term in rows[n0:]:
                if any(re.search(quant + re.escape(term[:k]), text)
                       for k in range(len(term), len(stem) + 1, -1)):
                    cut_intro += 1
    finally:
        mod._PREFIX_FALLBACK_OBSERVER = None
    print(f"{juris} 2-char-stem fallbacks {len(rows)}, fuller form introduced earlier {cut_intro}")
    for tail, n in tails.most_common(show):
        print(f"  {n:5d} {tail}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Size the wave E false-negative masks")
    ap.add_argument("probe", choices=["onechar", "embedded", "selfintro", "stemfallback"])
    ap.add_argument("--juris", default="ALL", choices=["TW", "CN", "ALL"])
    ap.add_argument("--show", type=int, default=15)
    args = ap.parse_args()
    fn = {"onechar": onechar, "embedded": embedded, "selfintro": selfintro,
          "stemfallback": stemfallback}[args.probe]
    for j in (["TW", "CN"] if args.juris == "ALL" else [args.juris]):
        fn(j, args.show)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
