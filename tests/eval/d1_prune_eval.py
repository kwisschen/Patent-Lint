# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# d1_prune_eval.py — pick an FN-SAFE deterministic pruning rule for the
# reference-numeral (D1) advisory count (ADR-159, user-authorized gold step,
# 2026-06-25). Loads the LLM gold verdicts (real_d1 vs false_positive), re-runs
# the detector per draft to recover the FULL numeral→dominant-name map, then for
# each candidate pruning rule reports, per jurisdiction:
#   FP-suppressed (good)   vs   real_d1-suppressed (FN — HARD GATE: must be 0).
# Only rules with 0 genuine catches suppressed are eligible to ship.
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
sys.path.insert(0, str(THIS.parent.parent / "src"))

import refnum_corpus_runner as R  # noqa: E402

# ---- gold sources (pid, numeral, verdict) -------------------------------------
GOLD_FILES = {
    "US": THIS / "d1_probe_us_verdicts.json",
    "CN": THIS / "d1_probe_cn_verdicts.json",
    "TW": THIS / "d1_local_tw_verdicts.json",
}

_ORD = re.compile(r"^(第[一二三四五六七八九十百0-9]+|first|second|third|fourth|fifth|"
                  r"sixth|seventh|eighth|ninth|tenth)\b", re.I)


def _strip_ordinal(name: str) -> str:
    """Base noun without a leading ordinal (handles the '第二|base' pipe key
    from the CJK detector and English 'second base')."""
    if "|" in name:
        return name.split("|", 1)[1].strip()
    return _ORD.sub("", name).strip()


def _norm(name: str) -> str:
    return _strip_ordinal(name).lower().replace(" ", "")


# ---- per-draft detector replay -------------------------------------------------
def _us_pairs_and_conflicts(text):
    from patentlint.analysis import specification as S
    pairs = S.extract_numeral_name_pairs(text)
    confs = S._detect_d1_conflicts(pairs)
    return pairs, confs


def _cjk_pairs_and_conflicts(text):
    from patentlint.analysis import cn_specification as C
    pairs = C._cn_extract_numeral_name_pairs(text)
    confs = C._cn_detect_d1_conflicts(pairs)
    return pairs, confs


def _dominant_map(pairs):
    """numeral -> (dominant_name, total_count, {name: count})."""
    by_num = defaultdict(Counter)
    for num, name in pairs:
        by_num[str(num)][name] += 1
    out = {}
    for num, ctr in by_num.items():
        dom, _ = ctr.most_common(1)[0]
        out[num] = (dom, sum(ctr.values()), dict(ctr))
    return out


_DESCS_CACHE = {}

def _load_text(juris, pid):
    if juris == "TW":
        from patentlint.parser.docx_loader import load_docx_tw
        p = THIS.parent / "fixtures/tw/local" / pid
        return "\n".join(load_docx_tw(str(p)).paragraphs)
    if juris not in _DESCS_CACHE:
        _DESCS_CACHE[juris] = R._load_descs(juris)
    descs = _DESCS_CACHE[juris]
    return R.spec_body((descs.get(pid) or {}).get("description") or "", juris)


# ---- candidate pruning rules ---------------------------------------------------
# Each rule: given (conflict, dom_map) -> set of outlier-name strings to DROP.
# After dropping, if no outliers remain the conflict is SUPPRESSED.

def rule_misattr_dominant(conf, dom_map):
    """Drop a 1x outlier whose base-noun equals the DOMINANT name of another
    numeral (it bled across a numeral boundary during extraction)."""
    drop = set()
    self_num = str(conf["numeral"])
    other_doms = {_norm(v[0]) for k, v in dom_map.items() if k != self_num}
    for o in conf["outliers"]:
        if o["count"] == 1 and _norm(o["name"]) in other_doms:
            drop.add(o["name"])
    return drop


def rule_misattr_anyname(conf, dom_map):
    """Drop a 1x outlier whose base-noun appears as ANY name on another numeral
    (broader bleed signal)."""
    drop = set()
    self_num = str(conf["numeral"])
    other_names = set()
    for k, v in dom_map.items():
        if k != self_num:
            other_names |= {_norm(n) for n in v[2]}
    for o in conf["outliers"]:
        if o["count"] == 1 and _norm(o["name"]) in other_names:
            drop.add(o["name"])
    return drop


def rule_ordinal_variant(conf, dom_map):
    """Drop a 1x outlier that differs from the canonical ONLY by ordinal prefix
    (same base noun) — '第一X' vs '第二X' single-occurrence = bleed."""
    drop = set()
    canon_base = _norm(conf["canonical"])
    for o in conf["outliers"]:
        if o["count"] == 1 and _norm(o["name"]) == canon_base and o["name"] != conf["canonical"]:
            drop.add(o["name"])
    return drop


def rule_substring(conf, dom_map):
    """Drop a 1x outlier whose base-noun is a substring/superstring of the
    canonical base-noun (fragment capture)."""
    drop = set()
    cb = _norm(conf["canonical"])
    for o in conf["outliers"]:
        ob = _norm(o["name"])
        if o["count"] == 1 and ob and cb and (ob in cb or cb in ob) and ob != cb:
            drop.add(o["name"])
    return drop


RULES = {
    "misattr_dominant": rule_misattr_dominant,
    "misattr_anyname": rule_misattr_anyname,
    "ordinal_variant": rule_ordinal_variant,
    "substring": rule_substring,
}
# combos evaluated as union of drops
COMBOS = {
    "dom+ordinal": ["misattr_dominant", "ordinal_variant"],
    "dom+ordinal+substr": ["misattr_dominant", "ordinal_variant", "substring"],
    "any+ordinal+substr": ["misattr_anyname", "ordinal_variant", "substring"],
}


def suppressed(conf, dom_map, rule_fns):
    drop = set()
    for fn in rule_fns:
        drop |= fn(conf, dom_map)
    remaining = [o for o in conf["outliers"] if o["name"] not in drop]
    return len(remaining) == 0


def main():
    grand = {}
    for juris, gf in GOLD_FILES.items():
        if not gf.exists():
            print(f"{juris}: gold file missing ({gf.name}) — skip")
            continue
        gold = json.loads(gf.read_text())
        # index verdict by (pid, numeral)
        verdict = {(g["pid"], str(g["numeral"])): g["verdict"] for g in gold}
        pids = sorted({g["pid"] for g in gold})
        replay = _us_pairs_and_conflicts if juris == "US" else _cjk_pairs_and_conflicts
        # re-run detector per draft → conflict objects keyed by (pid, numeral)
        conf_by = {}
        dom_by = {}
        for pid in pids:
            try:
                text = _load_text(juris, pid)
                pairs, confs = replay(text)
            except Exception as e:
                print(f"  {juris} {pid}: replay error {e}")
                continue
            dom_by[pid] = _dominant_map(pairs)
            for c in confs:
                conf_by[(pid, str(c["numeral"]))] = c
        # evaluate every rule + combo
        names = list(RULES.keys()) + list(COMBOS.keys())
        fp_keys = [k for k, v in verdict.items() if v == "false_positive"]
        real_keys = [k for k, v in verdict.items() if v == "real_d1"]
        print(f"\n=== {juris} (gold: {len(fp_keys)} FP, {len(real_keys)} real_d1; "
              f"{len(conf_by)} conflicts replayed) ===")
        res = {}
        for nm in names:
            fns = [RULES[r] for r in (COMBOS[nm] if nm in COMBOS else [nm])]
            fp_sup = real_sup = 0
            for k in fp_keys:
                c = conf_by.get(k)
                if c and suppressed(c, dom_by.get(k[0], {}), fns):
                    fp_sup += 1
            for k in real_keys:
                c = conf_by.get(k)
                if c and suppressed(c, dom_by.get(k[0], {}), fns):
                    real_sup += 1
            res[nm] = (fp_sup, real_sup)
            flag = "  ✗ FN!" if real_sup else "  ✓ FN-safe"
            print(f"  {nm:24s} FP-suppressed {fp_sup:4d}/{len(fp_keys):<4d} "
                  f"({fp_sup/max(1,len(fp_keys)):4.0%})  real-suppressed {real_sup}{flag}")
        grand[juris] = res
    return grand


if __name__ == "__main__":
    main()
