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
#
# COVERAGE NOTE (explicit, per the #413/#414 gate-audit, 2026-07-22): this runner
# invokes the shared numeral EXTRACTOR + conflict DETECTOR directly
# (extract_numeral_name_pairs / _cn_extract_numeral_name_pairs + _detect_d1_*),
# NOT the doc-level check_numeral_consistency_tw. It therefore does NOT build a
# TwPatentDocument and CANNOT exercise the TW 符號說明-anchoring path
# (_tw_anchor_pairs_to_declared, which collapses body captures onto the declared
# symbol-table name before collision detection — the #284/#244 FN-safe lever, and
# the site of the #414 reachable FN). The scraped Google-Patents descriptions have
# no clean 符號說明 table to anchor against, so a doc-level TW mode would have no
# corpus data to run on anyway. That path is gated SOLELY by the pytest controls
# in tests/analysis/test_tw_specification.py (the #414 regression tests, incl. a
# no-table invariant). Do NOT read a green run of this runner as coverage of the
# TW symbol-table anchor; a regression there is invisible here by construction.
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

# CJK (CN/TW) body markers — the Google-Patents CN/TW description carries an
# English biblio header, then the CJK spec body from the first section heading.
_SEC_CJK = re.compile(
    r"(技术领域|技術領域|背景技术|背景技術|发明内容|發明內容|具体实施|具體實施"
    r"|实施方式|實施方式|附图说明|附圖說明)"
)
_END_CJK = re.compile(
    r"(Patent Citations|Cited By|Family Cites|Similar Documents|Priority date"
    r"|Legal Events|Claims\s*\(|Patent Citations \(\d+\))"
)


def spec_body(text: str, juris: str = "US") -> str:
    sec, end = (_SEC, _END) if juris == "US" else (_SEC_CJK, _END_CJK)
    m = sec.search(text)
    start = m.start() if m else 0
    e = end.search(text, start)
    stop = e.start() if e else len(text)
    return text[start:stop]


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
from patentlint.analysis.cn_specification import (  # noqa: E402
    _cn_extract_numeral_name_pairs as cn_pairs,
    _cn_detect_d1_conflicts as cn_detect,
    _CN_FRAGMENT_MARKERS,
)

# Leading CJK connector/particle chars that are never the FIRST char of a real
# element noun (conjunctions / prepositions / genitive particles). Used by the
# CJK plausibility predicate (a name starting with one is sentence bleed) and by
# the connector-variant dedup fix. Conservative subset of
# cn_specification._CN_LEADING_VERBS_PARTICLES.
_CN_LEADING_CONNECTORS = frozenset(
    "和及與与於于到的或並并而且以之至由在向從从對对"
)


def _cn_name_is_element_noun(keyed_name: str) -> bool:
    """CJK plausibility: >=2 CJK chars, not led by a connector/particle, no
    sentence-fragment marker. The independent FN-guard signal for CN/TW D1 —
    a real element noun passes; connector-bled / clause-fragment captures fail."""
    _, head = _split_ordinal_key(keyed_name)
    head = head.strip()
    cjk = [c for c in head if "一" <= c <= "鿿"]
    if len(cjk) < 2:
        return False
    if head[0] in _CN_LEADING_CONNECTORS:
        return False
    if any(mk in head for mk in _CN_FRAGMENT_MARKERS):
        return False
    return True


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


def name_is_element_noun(keyed_name: str, juris: str = "US") -> bool:
    """Structural test: does this D1 element-name LOOK like a real element noun
    phrase (vs sentence-context over-capture)?

    SAFE / conservative — returns False ONLY when the name is clearly NOT an
    element identity: empty, the HEAD is a non-noun (verb/gerund/adverb), or a
    CLAUSE marker (copula / not / that / which) sits anywhere in the phrase.

    Deliberately does NOT reject past-participle / 3sg words in the BODY —
    those are usually adjectival modifiers of a real element ("integrated
    circuit", "curved surface", "printed circuit board"), so rejecting them
    would drop real conflicts (FN). Mirrors specification._is_plausible_element_name.
    For CN/TW, dispatches to the CJK predicate.
    """
    if juris != "US":
        return _cn_name_is_element_noun(keyed_name)
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


# Known non-element symbol numerals (Engine-3 R2) — amino-acid mutations,
# immunology/clinical biomarkers, X2X telecom abbreviations. A "conflict" on
# one of these was never a real reference-designator D1, so removing it is the
# intended symbol-denylist win and is excluded from the designator FN-gate.
_AA_MUT = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY]\d{2,4}[ACDEFGHIKLMNPQRSTVWY]$")
_BIO_PREFIXES = ("CD", "CLDN", "IGG", "IGM", "IGA", "IGE", "IGD",
                 "IL", "TNF", "IFN", "HBA")
_X2X = {"D2D", "V2V", "V2I", "V2N", "V2P", "V2X", "V2G", "M2M"}


def _is_known_nonelement_symbol(numeral: str) -> bool:
    n = numeral.upper()
    if n in _X2X:
        return True
    if _AA_MUT.match(n):
        return True
    lead = re.match(r"^[A-Z]+", n)
    return bool(lead and lead.group() in _BIO_PREFIXES)


def classify_conflict(c: dict, juris: str = "US") -> str:
    """PROTECT (structurally-plausible real D1) vs OVERCAPTURE.

    PROTECT requires: canonical is an element noun AND >=1 outlier is an
    element noun AND they genuinely differ. Everything else is OVERCAPTURE.
    """
    if not name_is_element_noun(c["canonical"], juris):
        return "overcapture"
    for o in c["outliers"]:
        if name_is_element_noun(o["name"], juris):
            return "protect"
    return "overcapture"


def is_strong_real(c: dict, juris: str = "US") -> bool:
    """The strongest deterministic real-D1 signal: both the canonical and a
    clean outlier are written REPEATEDLY (drafter consistently used both),
    so it is very unlikely to be one-off over-capture. These are the
    conflicts a name-cleaning fix MUST preserve."""
    if classify_conflict(c, juris) != "protect":
        return False
    if c["canonical_count"] < 3:
        return False
    for o in c["outliers"]:
        if o["count"] >= 2 and name_is_element_noun(o["name"], juris):
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
    descs = _load_descs(juris)
    extract, detect = (us_pairs, us_detect) if juris == "US" else (cn_pairs, cn_detect)
    out: list[tuple[str, dict]] = []
    for pid, obj in descs.items():
        raw = (obj or {}).get("description") or ""
        if not raw:
            continue
        spec = spec_body(raw, juris)
        if len(spec) < 1500:
            continue
        pairs = extract(spec)
        confs = detect(pairs, latin_pattern=False) if juris == "US" else detect(pairs)
        for c in confs:
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
            "tag": classify_conflict(c, juris),
            "strong_real": is_strong_real(c, juris),
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
        juris = args.juris

        def _real_d1_lost(k):
            v = pre[k]
            # Scope: the guard protects ELECTRONIC reference designators. A
            # numeral that is a known non-element SYMBOL (amino-acid mutation,
            # immunology/clinical biomarker prefix, or X2X telecom abbreviation)
            # was never a real D1 — removing it is the intended symbol-denylist
            # win, not a lost element conflict. Exclude from the FN gate. (US-only
            # symbol set; the CJK connector-dedup targets connector-bled names,
            # not symbols.)
            numeral = k.split("|", 1)[1]
            if _is_known_nonelement_symbol(numeral):
                return False
            if not (name_is_element_noun(v["canonical"], juris) and v["canonical_count"] >= 2):
                return False
            return any(name_is_element_noun(n, juris) and c >= 2 for n, c in v["outliers"])
        noun_noun_lost = [k for k in removed if _real_d1_lost(k)]
        real_lost = [k for k in removed if pre[k]["tag"] == "protect"]
        # strong_real / both_repeated are INFORMATIONAL and computed WITHOUT the
        # symbol-scope exclusion, so they over-count intended symbol-denylist
        # removals (bio/mutation/X2X). Surface symbol-excluded variants too so
        # the gate reads cleanly.
        strong_lost = [k for k in removed if pre[k]["strong_real"]]
        strong_lost_designator = [
            k for k in strong_lost
            if not _is_known_nonelement_symbol(k.split("|", 1)[1])
        ]
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
        print(f"  >>> designator noun↔noun-both-repeated removed (HARD GATE, MUST be 0): {len(noun_noun_lost)}")
        print(f"  >>> designator strong_real removed (HARD GATE, MUST be 0):           {len(strong_lost_designator)}")
        print(f"  (informational, symbol-inclusive) strong_real_lost={len(strong_lost)}  "
              f"protect_tag_lost={len(real_lost)}  both_repeated_lost={len(repeated_lost)}")
        if noun_noun_lost or strong_lost_designator:
            print("  --- GENUINE designator-FN conflicts removed (HARD FAIL) ---")
            for k in sorted(set(noun_noun_lost) | set(strong_lost_designator)):
                print(f"    {k}: {pre[k]['canonical']!r}({pre[k]['canonical_count']}) vs {pre[k]['outliers'][:5]}")
        fail = bool(noun_noun_lost) or bool(strong_lost_designator)
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
            t = classify_conflict(c, args.juris)
            tags[t] += 1
            if c["numeral"] and c["numeral"][0].isalpha():
                latin += 1
            if is_strong_real(c, args.juris):
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
