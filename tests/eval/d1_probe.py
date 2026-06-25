# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# d1_probe.py — cost-bounded LLM probe of the CN/TW reference-numeral (D1)
# false-positive rate, to quantify the addressable headroom of the paid
# "CJK D1 judged gold" lever before committing to a larger judging run
# (ADR-159 Path-to-80; user-authorized ~$3-5 probe, 2026-06-25).
#
# For a stratified sample of current CN D1 FIX-tier conflicts, ask the judge:
# is this a REAL numeral-naming inconsistency, or a FALSE POSITIVE (over-capture
# / connector-bled / clause fragment / non-element numeral)? Tally the FP rate
# overall and by the runner's structural class, then extrapolate to the pool.
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
sys.path.insert(0, str(THIS.parent.parent / "src"))

import refnum_corpus_runner as R  # noqa: E402
from llm_judges import load_keys, SONNET  # noqa: E402
from anthropic import AsyncAnthropic  # noqa: E402

SYSTEM = """You audit findings from PatentLint's D1 reference-numeral consistency check on CN/TW patent specifications (專利法施行細則 §19 / 专利法实施细则 §21 + 审查指南: the SAME reference numeral must designate the SAME element; different elements need different numerals).

The check flagged a numeral because it found that numeral bound to MULTIPLE distinct captured "element names" in the spec. Your job: decide if that is a REAL inconsistency or a FALSE POSITIVE of the name-extraction.

Verdicts (pick exactly one):
- real_d1: the numeral genuinely labels TWO OR MORE DIFFERENT elements — a true drafting error/typo. Each name is a bona-fide element noun denoting a DIFFERENT thing (e.g. 馬達10 vs 電路10; 選擇邏輯塊 vs 選擇模式塊).
- false_positive: at least one "name" is NOT a distinct element identity, so the flag should not fire. Causes: (a) a captured name is a sentence/clause fragment, verb phrase, or connector-bled form (e.g. 和缸/及缸/於缸 = the same 缸 with a stray 和/及/於; 在框/到軸; 分析在; 且在); (b) the names are mere variants/synonyms/abbreviations of the SAME element; (c) the numeral is not an element reference numeral at all (a method-step number Sxx, a time/quantity/measurement value, a date, a math variable, a bio/chemical symbol like CD3/K417T); (d) one name is a mis-tokenized fragment of a longer noun.
- unsure: genuinely cannot tell from the given info.

Answer ONLY with strict JSON: {"verdict":"real_d1|false_positive|unsure","reason":"<=18 words"}"""


def _excerpt(spec: str, numeral: str) -> str:
    """A short context window around an occurrence of the numeral in the spec."""
    # Prefer an occurrence adjacent to a CJK char (a real element binding).
    for m in re.finditer(re.escape(numeral), spec):
        s, e = m.start(), m.end()
        before = spec[max(0, s - 60):s]
        after = spec[e:e + 20]
        if any("一" <= c <= "鿿" for c in before[-6:]):
            return (before + "【" + numeral + "】" + after).replace("\n", " ").strip()
    i = spec.find(numeral)
    if i < 0:
        return ""
    return (spec[max(0, i - 60):i] + "【" + numeral + "】" + spec[i + len(numeral):i + len(numeral) + 20]).replace("\n", " ").strip()


def build_sample(juris: str, n_oc: int, n_protect: int):
    descs = R._load_descs(juris)
    confs = R.collect_conflicts(juris)  # current main behaviour
    rows = []
    for pid, c in confs:
        if c.get("confidence") != "fix":
            continue
        tag = R.classify_conflict(c, juris)
        rows.append({
            "pid": pid, "numeral": c["numeral"], "tag": tag,
            "strong_real": R.is_strong_real(c, juris),
            "canonical": c["canonical"], "canonical_count": c["canonical_count"],
            "outliers": [(o["name"], o["count"]) for o in c["outliers"][:6]],
        })
    # deterministic stratified sample (stride, no RNG — Math.random is banned anyway)
    oc = [r for r in rows if r["tag"] == "overcapture"]
    pr = [r for r in rows if r["tag"] == "protect"]

    def stride(lst, k):
        if k >= len(lst):
            return lst
        step = len(lst) / k
        return [lst[int(i * step)] for i in range(k)]
    sample = stride(oc, n_oc) + stride(pr, n_protect)
    # attach context
    body_cache = {}
    for r in sample:
        if r["pid"] not in body_cache:
            body_cache[r["pid"]] = R.spec_body((descs.get(r["pid"]) or {}).get("description") or "", juris)
        r["context"] = _excerpt(body_cache[r["pid"]], r["numeral"])
    return sample, len(oc), len(pr)


def _user_prompt(juris, r):
    ol = "; ".join(f"{nm}({ct})" for nm, ct in r["outliers"])
    canon = R._split_ordinal_key(r["canonical"])
    canon_disp = (canon[0] + " " + canon[1]).strip() if canon[0] else canon[1]
    return (
        f"Jurisdiction: {juris}\n"
        f"Reference numeral: {r['numeral']}\n"
        f"Most-frequent captured name (canonical): {canon_disp} ({r['canonical_count']}x)\n"
        f"Other captured names on the SAME numeral: {ol}\n"
        f"Spec context around the numeral: …{r['context']}…\n"
    )


async def judge(client, sem, juris, r, usage):
    async with sem:
        try:
            resp = await client.messages.create(
                model=SONNET, max_tokens=120, system=SYSTEM,
                messages=[{"role": "user", "content": _user_prompt(juris, r)}],
            )
        except Exception as e:
            r["verdict"] = "error"; r["reason"] = str(e)[:60]; return r
        usage["in"] += resp.usage.input_tokens
        usage["out"] += resp.usage.output_tokens
        txt = resp.content[0].text if resp.content else "{}"
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        try:
            j = json.loads(m.group(0)) if m else {}
        except Exception:
            j = {}
        r["verdict"] = j.get("verdict", "parse_error")
        r["reason"] = j.get("reason", "")
        return r


async def main_async(args):
    a_key, _ = load_keys()
    client = AsyncAnthropic(api_key=a_key)
    sample, n_oc_total, n_pr_total = build_sample(args.juris, args.n_oc, args.n_protect)
    print(f"{args.juris} D1 FIX pool — overcapture-class={n_oc_total}  protect-class={n_pr_total}")
    print(f"judging {len(sample)} ({args.n_oc} overcapture + {args.n_protect} protect) with {SONNET}…")
    sem = asyncio.Semaphore(6)
    usage = {"in": 0, "out": 0}
    await asyncio.gather(*[judge(client, sem, args.juris, r, usage) for r in sample])

    from collections import Counter
    def tally(rows):
        c = Counter(r["verdict"] for r in rows)
        tot = sum(c.values()) or 1
        fp = c.get("false_positive", 0)
        return c, fp, fp / tot
    oc = [r for r in sample if r["tag"] == "overcapture"]
    pr = [r for r in sample if r["tag"] == "protect"]
    c_oc, fp_oc, rate_oc = tally(oc)
    c_pr, fp_pr, rate_pr = tally(pr)
    print("\n=== VERDICTS ===")
    print(f"  overcapture-class (n={len(oc)}): {dict(c_oc)}  → FP rate {rate_oc:.0%}")
    print(f"  protect-class     (n={len(pr)}): {dict(c_pr)}  → FP rate {rate_pr:.0%}")
    # extrapolate addressable FPs in the full FIX pool
    est_oc = rate_oc * n_oc_total
    est_pr = rate_pr * n_pr_total
    print("\n=== EXTRAPOLATED ADDRESSABLE FP (full CN FIX pool) ===")
    print(f"  overcapture-class: ~{est_oc:.0f} FP  (of {n_oc_total})")
    print(f"  protect-class:     ~{est_pr:.0f} FP  (of {n_pr_total})")
    print(f"  TOTAL est. addressable FP (CN): ~{est_oc + est_pr:.0f}")
    print(f"  (TW shares the extractor; expect a similar-magnitude pool.)")
    # cost (Sonnet 4.6: $3 / Mtok in, $15 / Mtok out)
    cost = usage["in"] / 1e6 * 3 + usage["out"] / 1e6 * 15
    print(f"\ntokens in={usage['in']} out={usage['out']}  est. cost ${cost:.3f}")
    # dump sample verdicts for audit
    out = THIS / f"d1_probe_{args.juris.lower()}_verdicts.json"
    out.write_text(json.dumps(sample, ensure_ascii=False, indent=1))
    print(f"verdicts → {out}")
    # show some FP and real examples
    print("\n--- sample FALSE_POSITIVE verdicts ---")
    for r in [x for x in sample if x["verdict"] == "false_positive"][:12]:
        print(f"  #{r['numeral']} {r['canonical']!r} vs {r['outliers'][:3]} | {r['reason']}")
    print("\n--- sample REAL_D1 verdicts ---")
    for r in [x for x in sample if x["verdict"] == "real_d1"][:8]:
        print(f"  #{r['numeral']} {r['canonical']!r} vs {r['outliers'][:3]} | {r['reason']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--juris", default="CN", choices=["CN", "TW"])
    ap.add_argument("--n-oc", type=int, default=85)
    ap.add_argument("--n-protect", type=int, default=40)
    asyncio.run(main_async(ap.parse_args()))
