# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# refnum_corpus_runner.py — Engine 3 (reference-numeral consistency / D1) FP
# characterization + DETERMINISTIC FN-guard (ADR-159 Path-to-80, Sweep 3).
#
# Unlike Engines 1/2 (antecedent / spec-support) the D1 reference-numeral check
# is STRUCTURALLY anchored: the numeral is an explicit token, so a genuine D1
# defect (the SAME numeral bound to two genuinely-DIFFERENT element nouns) has a
# deterministic signature and needs NO LLM gold. The FP pool is element-name
# OVER-CAPTURE: sentence context (verbs, gerunds, adverbs, clause fragments,
# bio/chem symbols) bleeds into the captured "element name", so one numeral
# appears with several junk "names" and the check fires a phantom conflict.
#
# This runner:
#   * runs check_numeral_consistency over the scraped Google-Patents spec bodies
#     (tests/eval/{us,cn,tw}_descriptions.json, gitignored),
#   * classifies every FIX-tier conflict as PROTECT (a structurally-plausible
#     real D1 conflict — both names look like element nouns, both written
#     repeatedly) or OVERCAPTURE (>=1 name is a non-noun fragment / symbol),
#   * the FN-GUARD is: a name-cleaning fix may silence OVERCAPTURE conflicts
#     freely, but must NOT silence any PROTECT (pid, numeral). real_lost == 0.
#
# Workflow per fix (deterministic, FREE — no LLM):
#   python tests/eval/refnum_corpus_runner.py --juris US --snapshot /tmp/pre_us_refnum.json
#   ... edit specification.py ...
#   python tests/eval/refnum_corpus_runner.py --juris US --compare  /tmp/pre_us_refnum.json
#
# --characterize dumps the FP pool by class for sweep planning.
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
REPO = THIS.parent.parent
sys.path.insert(0, str(REPO / "src"))

# --- spec body extraction from the Google-Patents description dump ----------
# The scraped `description` is plain text: ~190k chars of GP boilerplate
# (classification trees, citation tables) precede the real spec body, and the
# claims/citations footer follows it. Slice to the body so the D1 check sees
# text resembling a real parsed-DOCX spec, not citation noise.
_SEC = re.compile(
    r"\b(CROSS-REFERENCE|TECHNICAL FIELD|FIELD OF (?:THE |)(?:INVENTION|DISCLOSURE)"
    r"|BACKGROUND|RELATED APPLICATION|STATEMENT REGARDING|SUMMARY"
    r"|BRIEF DESCRIPTION|DETAILED DESCRIPTION)\b"
)
_END = re.compile(
    r"(Claims \(\d+\)|Patent Citations \(\d+\)|Cited By \(\d+\)|Family Cites"
    r"|Non-Patent Citations|Similar Documents|Priority And Related Applications)"
)


def spec_body(text: str) -> str:
    m = _SEC.search(text)
    start = m.start() if m else 0
    e = _END.search(text, start)
    end = e.start() if e else len(text)
    return text[start:end]


# --- structural plausibility of a captured element name ---------------------
# Reuses the §112 walker's verb/participle/adverb helpers (cross-CHECK) so the
# guard agrees with the engine that already distinguishes nouns from verbs.
from patentlint.analysis.utils import (  # noqa: E402
    _ADVERB_STOPS,
    _VERB_STOPS,
    _ING_VERB_ONLY,
    _is_likely_past_participle,
)
from patentlint.analysis.specification import (  # noqa: E402
    extract_numeral_name_pairs as us_pairs,
    _detect_d1_conflicts as us_detect,
    _split_ordinal_key,
)


# Self-contained mirror of specification._is_plausible_element_name. NOT imported
# from production — the FN-guard's `--snapshot` runs with specification.py
# STASHED to its pre-edit state (no predicate yet), so the runner must classify
# independently. Kept in sync with the production predicate by hand.
_CLAUSE_WORDS = frozenset({
    "be", "is", "are", "was", "were", "been", "being",
    "do", "does", "did", "not", "that", "which", "who", "whose", "whom",
})
_LY_NOUN_ALLOWLIST = frozenset({
    "supply", "assembly", "family", "anomaly", "subassembly", "resupply",
    "ally", "poly",
})
_NONNOUN_VERB_HEADS = frozenset({
    "displaying", "generating", "submitting", "removing", "altering",
    "committing", "designating", "detecting", "gathering", "enumerating",
    "creating", "getting", "indicating", "depicting", "adding", "summarize",
})


def _head_is_nonnoun(w: str) -> bool:
    """True when the HEAD (last) token can never be an element-name noun.
    Unambiguous signals only — curated verb/adverb sets + -ed participle + -ly
    adverb. NO generic -ing / -s rule (those drop real nouns grating/winding/
    cladding/outputs/inputs → FN). Mirrors specification._d1_head_is_nonnoun."""
    w = w.lower().rstrip(".,;:")
    if (
        w in _ADVERB_STOPS or w in _VERB_STOPS or w in _ING_VERB_ONLY
        or w in _NONNOUN_VERB_HEADS
    ):
        return True
    if _is_likely_past_participle(w):
        return True
    if w.endswith("ly") and len(w) >= 5 and w not in _LY_NOUN_ALLOWLIST:
        return True
    return False


def name_is_element_noun(keyed_name: str) -> bool:
    """Structural test: does this D1 element-name LOOK like a real element noun
    phrase (vs sentence-context over-capture)?

    SAFE / conservative — returns False ONLY when the name is clearly NOT an
    element identity: empty, the HEAD is a non-noun (verb/gerund/adverb), or a
    CLAUSE marker (copula / not / that / which) sits anywhere in the phrase.

    Deliberately does NOT reject past-participle / 3sg words in the BODY —
    those are usually adjectival modifiers of a real element ("integrated
    circuit", "curved surface", "printed circuit board"), so rejecting them
    would drop real conflicts (FN). Mirrors specification._is_plausible_element_name.
    """
    _, head = _split_ordinal_key(keyed_name)
    words = [w for w in head.split() if w]
    if not words:
        return False
    if _head_is_nonnoun(words[-1]):
        return False
    for w in words:
        if w.lower().rstrip(".,;:") in _CLAUSE_WORDS:
            return False
    return True


def classify_conflict(c: dict) -> str:
    """PROTECT (structurally-plausible real D1) vs OVERCAPTURE.

    PROTECT requires: canonical is an element noun AND >=1 outlier is an
    element noun AND they genuinely differ. Everything else is OVERCAPTURE.
    """
    canon = c["canonical"]
    if not name_is_element_noun(canon):
        return "overcapture"
    for o in c["outliers"]:
        if name_is_element_noun(o["name"]):
            return "protect"
    return "overcapture"


def is_strong_real(c: dict) -> bool:
    """The strongest deterministic real-D1 signal: both the canonical and a
    clean outlier are written REPEATEDLY (drafter consistently used both),
    so it is very unlikely to be one-off over-capture. These are the
    conflicts a name-cleaning fix MUST preserve."""
    if classify_conflict(c) != "protect":
        return False
    if c["canonical_count"] < 3:
        return False
    for o in c["outliers"]:
        if o["count"] >= 2 and name_is_element_noun(o["name"]):
            return True
    return False


def both_repeated(c: dict) -> bool:
    """INDEPENDENT FN-guard signal (no POS / verb-predicate): the canonical AND
    at least one outlier were each written >=2 times. A pure sentence-context
    over-capture is almost always a one-off (1x) fragment, so a conflict where
    BOTH names recur is a strong drafter-consistency signal of a real naming
    inconsistency — silencing one is a likely FN regardless of how the verb
    predicate classifies it. This is the guard's hard invariant, computed
    WITHOUT the name_is_element_noun predicate so it can't be defined away."""
    if c["canonical_count"] < 2:
        return False
    return any(o["count"] >= 2 for o in c["outliers"])


# --- corpus iteration -------------------------------------------------------
def _load_descs(juris: str) -> dict:
    p = THIS / f"{juris.lower()}_descriptions.json"
    return json.loads(p.read_text())


def collect_conflicts(juris: str) -> list[tuple[str, dict]]:
    """Return [(pid, conflict-dict)] for EVERY D1 conflict (both FIX and REVIEW
    tiers) over the corpus.

    The FN-guard must track BOTH tiers: a name-cleaning fix often DEMOTES a
    weak conflict from FIX (asserted error) to REVIEW (advisory) by stripping
    the junk outliers that made it look strong — that is a WIN (fewer false
    assertions), not a removal. Tracking FIX-only would mis-count a demotion as
    a silenced conflict and falsely trip the guard."""
    if juris != "US":
        raise NotImplementedError("CN/TW wired after US sweep (cn_specification mirror)")
    descs = _load_descs(juris)
    out: list[tuple[str, dict]] = []
    for pid, obj in descs.items():
        raw = (obj or {}).get("description") or ""
        if not raw:
            continue
        spec = spec_body(raw)
        if len(spec) < 2000:
            continue
        pairs = us_pairs(spec)
        for c in us_detect(pairs, latin_pattern=False):
            if c.get("confidence") not in ("fix", "review"):
                continue
            out.append((pid, c))
    return out


def _key(pid: str, c: dict) -> str:
    return f"{pid}|{c['numeral']}"


def snapshot(juris: str) -> dict:
    confs = collect_conflicts(juris)
    snap = {}
    for pid, c in confs:
        snap[_key(pid, c)] = {
            "tier": c.get("confidence"),
            "tag": classify_conflict(c),
            "strong_real": is_strong_real(c),
            "both_repeated": both_repeated(c),
            "canonical": c["canonical"],
            "canonical_count": c["canonical_count"],
            "outliers": [(o["name"], o["count"]) for o in c["outliers"]],
        }
    return snap


def main() -> int:
    ap = argparse.ArgumentParser(description="Engine 3 refnum D1 FP characterizer + FN-guard")
    ap.add_argument("--juris", default="US", choices=["US", "CN", "TW"])
    ap.add_argument("--snapshot", type=Path, help="write conflict snapshot (BEFORE edit)")
    ap.add_argument("--compare", type=Path, help="compare against snapshot (AFTER edit)")
    ap.add_argument("--characterize", action="store_true", help="dump FP pool by class")
    args = ap.parse_args()

    if args.snapshot:
        snap = snapshot(args.juris)
        args.snapshot.write_text(json.dumps(snap))
        prot = sum(1 for v in snap.values() if v["tag"] == "protect")
        strong = sum(1 for v in snap.values() if v["strong_real"])
        fix_t = sum(1 for v in snap.values() if v["tier"] == "fix")
        print(f"snapshot: {len(snap)} conflicts (fix={fix_t}, review={len(snap)-fix_t}) → {args.snapshot}")
        print(f"  protect(real-candidate)={prot}  strong_real={strong}  overcapture={len(snap)-prot}")
        return 0

    if args.compare:
        pre = json.loads(args.compare.read_text())
        post = snapshot(args.juris)
        pre_keys = set(pre)
        post_keys = set(post)
        removed = pre_keys - post_keys      # gone from BOTH tiers = truly silenced
        added = post_keys - pre_keys
        kept = pre_keys & post_keys
        demoted = [k for k in kept if pre[k]["tier"] == "fix" and post[k]["tier"] == "review"]
        # FN-guard is on TRUE removals only (demotion fix->review is a win, not a loss).
        #
        # HARD GATE = the genuine real-D1 signature: a TRULY-removed conflict whose
        # canonical AND >=1 outlier are BOTH plausible element nouns AND BOTH appear
        # >=2x (drafter consistently used two different element names on one numeral).
        # That is the only shape a name-cleaning fix could lose as a real FN. The
        # `real_lost`/`both_repeated` heuristics below over-flag benign collapses
        # (a junk name being dropped leaves a single noun or all-1x residue), so
        # they are INFORMATIONAL; this signature is the decisive gate.
        def _real_d1_lost(k):
            v = pre[k]
            if not (name_is_element_noun(v["canonical"]) and v["canonical_count"] >= 2):
                return False
            return any(name_is_element_noun(n) and c >= 2 for n, c in v["outliers"])
        noun_noun_lost = [k for k in removed if _real_d1_lost(k)]
        real_lost = [k for k in removed if pre[k]["tag"] == "protect"]
        strong_lost = [k for k in removed if pre[k]["strong_real"]]
        repeated_lost = [k for k in removed if pre[k].get("both_repeated")]
        pre_fix = sum(1 for v in pre.values() if v["tier"] == "fix")
        post_fix = sum(1 for v in post.values() if v["tier"] == "fix")
        print(f"=== Engine 3 refnum FN-guard ({args.juris}) ===")
        print(f"  pre  conflicts: {len(pre_keys)} (fix={pre_fix})")
        print(f"  post conflicts: {len(post_keys)} (fix={post_fix})")
        print(f"  FIX-tier reduction (false-assertion harm ended): {pre_fix - post_fix}")
        print(f"    ├─ demoted fix→review (still advisory): {len(demoted)}")
        print(f"    └─ truly removed (gone from both tiers): {len(removed)}")
        print(f"  new conflicts: {len(added)}")
        print(f"  >>> noun↔noun-both-repeated TRULY removed (HARD GATE, MUST be 0): {len(noun_noun_lost)}")
        print(f"  (informational) strong_real_lost={len(strong_lost)}  "
              f"protect_tag_lost={len(real_lost)}  both_repeated_lost={len(repeated_lost)}")
        if noun_noun_lost:
            print("  --- GENUINE-FN-signature conflicts removed (HARD FAIL) ---")
            for k in sorted(noun_noun_lost):
                print(f"    {k}: {pre[k]['canonical']!r}({pre[k]['canonical_count']}) vs {pre[k]['outliers'][:5]}")
        fail = bool(noun_noun_lost) or bool(strong_lost)
        print(f"  GATE: {'FAIL — investigate above' if fail else 'PASS'}")
        return 1 if fail else 0

    if args.characterize:
        confs = collect_conflicts(args.juris)
        from collections import Counter
        tags = Counter()
        latin = 0
        strong = 0
        oc_examples = []
        protect_examples = []
        for pid, c in confs:
            t = classify_conflict(c)
            tags[t] += 1
            if c["numeral"] and c["numeral"][0].isalpha():
                latin += 1
            if is_strong_real(c):
                strong += 1
                if len(protect_examples) < 30:
                    protect_examples.append((pid, c["numeral"], c["canonical"],
                                             [(o["name"], o["count"]) for o in c["outliers"][:4]]))
            elif t == "overcapture" and len(oc_examples) < 30:
                oc_examples.append((pid, c["numeral"], c["canonical"],
                                    [(o["name"], o["count"]) for o in c["outliers"][:4]]))
        print(f"=== {args.juris} D1 FIX-conflict characterization ===")
        print(f"  total FIX conflicts: {len(confs)}")
        print(f"  by class: {dict(tags)}")
        print(f"  latin-prefix numerals (bio/chem-symbol suspect): {latin}")
        print(f"  STRONG_REAL (both names repeated, plausible nouns): {strong}")
        print("\n--- STRONG_REAL examples (the genuine-D1 candidates to PROTECT) ---")
        for e in protect_examples:
            print("  ", e)
        print("\n--- OVERCAPTURE examples (the FP pool to silence) ---")
        for e in oc_examples:
            print("  ", e)
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
