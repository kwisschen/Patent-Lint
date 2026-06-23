# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# cluster_fp_classes.py — turn labeled walker_fp INSTANCES into FP CLASSES
# (ADR-159, the class-not-instance layer).
#
# The instance labels (apply_proposed_labels.py) make a fix SAFE to validate;
# they do not by themselves END a recurrence. A recurrence ends when the WALKER
# MECHANISM behind a whole class of FPs is fixed (e.g. "strip quantifier+
# classifier prefixes", "block verb-clause over-capture") — one code change that
# kills every current AND future instance of that class.
#
# This groups confirmed walker_fp findings by their MECHANISM SIGNATURE (derived
# from the captured term shape + the judge's rationale), so the output is a
# ranked list of FP CLASSES — each a single walker-mechanism fix target with its
# instance count, draft spread, examples, and the likely code site. Feed the top
# classes into /walker-round; the instance gold validates the mechanism fix
# didn't regress.
#
# Usage:
#   python tests/eval/cluster_fp_classes.py tests/eval/proposed_labels/proposed_corpus_*_full.json
from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path

# Reference markers that should never be inside a captured element name.
_REF_MARKERS = ("所述", "該等", "前述", "該", "该等", "该", "这", "其")
# Quantifier / classifier leads.
_QUANT = ("多個", "多条", "多條", "兩個", "两个", "三個", "每條", "每条", "各個", "各种",
          "至少一", "複數", "复数", "數個", "数个", "兩條", "两条", "少一條", "條所述", "条所述")
# CJK verb / predicate chars that signal a verb-clause over-capture when interior.
_VERBISH = ("設於", "形成", "連接", "耦接", "傾向", "鄰近", "包括", "具有", "用以", "配置",
            "介於", "達到", "進行", "沿著", "抵靠", "perform", "operable", "configured",
            "disposed", "connected", "coupled", "comprising", "wherein", "having")


def _is_cjk(s: str) -> bool:
    return any("一" <= c <= "鿿" for c in s)


def classify(term: str, reference_form: str, rationale: str) -> str:
    """Map one walker_fp finding to a mechanism CLASS."""
    t = term or ""
    r = (rationale or "").lower()
    # 1. judge said it outright
    if any(k in r for k in ("fragment", "tokeniz", "truncat", "split mid", "cut off")):
        return "tokenization_fragment"
    # 2. reference marker bled into the captured term
    if any(m in t for m in _REF_MARKERS):
        return "ref_marker_bleed"
    # 3. quantifier / classifier prefix
    if any(t.startswith(q) for q in _QUANT):
        return "quantifier_classifier_prefix"
    # 4. verb-clause over-capture (interior predicate, or simply too long)
    if any(v in t for v in _VERBISH):
        return "verb_clause_overcapture"
    if _is_cjk(t):
        if len(t) >= 7:
            return "verb_clause_overcapture"          # long CJK run = swept a clause
        if len(t) <= 3:
            return "single_word_bare_noun"            # the bare-noun-intro arm
    else:
        wc = len(t.split())
        if wc >= 5:
            return "verb_clause_overcapture"
        if wc <= 1:
            return "single_word_bare_noun"
    # 5. rationale hints we can still use
    if "adverb" in r or "modifier" in r or "clause" in r:
        return "verb_clause_overcapture"
    if "preamble" in r or "introduced earlier" in r or "pattern a" in r or "pattern b" in r:
        return "missed_introduction"                  # term WAS introduced; walker missed it
    return "other"


# Each class → the walker code site a maintainer should look at first.
_FIX_SITE = {
    "ref_marker_bleed": "intro/refnum extractors: strip embedded 所述/該/前述 (cn_specification _CN_REF_PREFIXES; cn_claims ref-marker truncation; utils for US)",
    "quantifier_classifier_prefix": "_CN_LEADING_QUANTIFIERS + the guarded classifier strip (cn_specification.py) — same mechanism as PR #294",
    "verb_clause_overcapture": "noun-boundary lookahead: stop the capture at a content-verb follower (tw/cn_claims _STATE/_TRAILING sets; US _STOP_WORDS)",
    "tokenization_fragment": "cjk_tokenize bigram split / _NP_CORE compound-noun synthesis — capture the whole head noun, not a fragment",
    "single_word_bare_noun": "bare-noun-introduction single-word arm (has_bare_noun_introduction*) — the deferred US #265 / TW arm",
    "missed_introduction": "intro-pattern coverage gap: the term IS introduced but the intro extractor doesn't register the shape",
    "other": "needs manual inspection — no clean mechanism signature",
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Cluster walker_fp instances into mechanism CLASSES (ADR-159)")
    ap.add_argument("globs", nargs="+", help="proposed_labels JSON files / globs")
    ap.add_argument("--min-agreement", default="any", choices=["any", "unanimous"],
                    help="only count findings at this agreement level")
    args = ap.parse_args()

    files: list[str] = []
    for g in args.globs:
        files.extend(glob.glob(g))
    classes: dict[str, dict] = defaultdict(lambda: {"instances": 0, "drafts": set(),
                                                    "jurisdictions": set(), "examples": []})
    total_fp = 0
    for f in files:
        d = json.loads(Path(f).read_text())
        for p in d.get("proposed", []):
            if p.get("verdict") != "walker_fp":
                continue
            if args.min_agreement == "unanimous" and p.get("agreement") != "unanimous":
                continue
            total_fp += 1
            cls = classify(p.get("term", ""), p.get("reference_form", ""), p.get("rationale", ""))
            c = classes[cls]
            c["instances"] += 1
            c["drafts"].add(p.get("source"))
            c["jurisdictions"].add(p.get("jurisdiction"))
            if len(c["examples"]) < 4:
                c["examples"].append({"term": p.get("term"), "ref": p.get("reference_form"),
                                      "juris": p.get("jurisdiction"), "why": (p.get("rationale") or "")[:90]})

    ranked = sorted(classes.items(), key=lambda kv: -kv[1]["instances"])
    print(f"# Walker-FP CLASSES across {len(files)} run(s) — {total_fp} walker_fp instances\n")
    print(f"{'class':30} {'instances':>9} {'drafts':>7} {'juris':>8}")
    print("-" * 60)
    for cls, c in ranked:
        print(f"{cls:30} {c['instances']:>9} {len(c['drafts']):>7} {','.join(sorted(j or '?' for j in c['jurisdictions'])):>8}")
    print("\n## Per-class fix targets (one mechanism fix ends the whole class):\n")
    for cls, c in ranked:
        print(f"### {cls}  —  {c['instances']} instances / {len(c['drafts'])} drafts / {','.join(sorted(j or '?' for j in c['jurisdictions']))}")
        print(f"  FIX SITE: {_FIX_SITE.get(cls, '?')}")
        for ex in c["examples"]:
            print(f"    e.g. [{ex['juris']}] term={ex['term']!r} ref={ex['ref']!r}  — {ex['why']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
