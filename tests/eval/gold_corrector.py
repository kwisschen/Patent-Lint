# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# gold_corrector.py — the autonomy keystone for the Zero-FP Sweep campaign
# (ADR-159).
#
# When `validate_fix.py --compare` reports `silenced_legit > 0`, a fix appears
# to have silenced a finding the ensemble labeled `legit_drafting_error` — i.e.
# an apparent FALSE NEGATIVE. Two things can cause that:
#
#   (1) the fix is genuinely too broad and silenced a real defect  → REAL FN,
#       must narrow / revert (DR-1); OR
#   (2) the ensemble MISLABELED a walker FP as legit — the term really IS
#       introduced (an explicit Pattern-A article introduction sits before the
#       reference) and the walker was right to (eventually) stop flagging it
#       → VERIFIED GOLD ERROR, record in phase2b_results_<j>_corrections.json.
#
# To keep the campaign autonomous WITHOUT letting the agent rationalize real
# FNs away, this module makes the (1)-vs-(2) decision DETERMINISTIC: it runs a
# conservative, high-precision Pattern-A intro-presence scan over the claim and
# its ancestor chain. It is deliberately STRICTER and SIMPLER than the walker's
# own intro logic — it must be an INDEPENDENT check (if it merely re-ran the
# walker it would always agree and never surface a gold error). It only flips a
# label when an explicit indefinite-article / "at least one" / "one or more"
# introduction of the exact term is present.
#
# SAFETY CAP: if more than `cap` (default 5%) of a fix's silenced-legit findings
# auto-correct as gold errors, that is evidence the FIX is wrong (silencing a
# whole class of real defects), not that the gold is wrong en masse — HALT and
# surface for human review. A single fix should at most mop up a stray mislabel.
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))


def _norm(s: str | None) -> str:
    """Lower-case + collapse whitespace; leaves words intact for \\b anchoring."""
    return re.sub(r"\s+", " ", (s or "").strip().lower())


# Explicit Pattern-A introduction prefixes. Indefinite article OR enumerated
# "at least one" / "one or more" (MPEP § 2173.05(e) reasonably-ascertainable
# introductions). `said`/`the`/`a plurality of` are deliberately EXCLUDED —
# `said`/`the` are references, and `a plurality of X` introduces X but the
# captured term would be `plurality of X`, handled by the walker not here.
_INTRO_TEMPLATES = (
    r"\b(?:a|an)\s+{t}\b",
    r"\bat\s+least\s+one\s+(?:of\s+)?{t}\b",
    r"\bone\s+or\s+more\s+(?:of\s+)?{t}\b",
)


def pattern_a_intro_present(
    term: str,
    claim_text: str,
    ancestor_texts: Optional[list[str]] = None,
    reference_form: Optional[str] = None,
) -> tuple[bool, str]:
    """High-precision deterministic Pattern-A intro check.

    Returns (present, evidence). `present` is True only when an explicit
    indefinite-article / at-least-one introduction of the EXACT term appears
    either (a) anywhere in an ancestor claim (always before the reference), or
    (b) in the same claim BEFORE the reference occurrence.
    """
    t = _norm(term)
    if not t:
        return False, ""
    patterns = [re.compile(tmpl.format(t=re.escape(t))) for tmpl in _INTRO_TEMPLATES]

    # Ancestors first — any intro there is unconditionally before the reference.
    for anc in ancestor_texts or []:
        h = _norm(anc)
        for rx in patterns:
            m = rx.search(h)
            if m:
                return True, m.group(0)

    # Same claim — intro must precede the reference position.
    claim_h = _norm(claim_text)
    ref_h = _norm(reference_form) if reference_form else ""
    ref_pos = claim_h.find(ref_h) if ref_h else -1
    for rx in patterns:
        for m in rx.finditer(claim_h):
            if ref_pos < 0 or m.start() < ref_pos:
                return True, m.group(0)
    return False, ""


@dataclass
class CorrectionAudit:
    """Result of auditing a fix's silenced-legit findings against Pattern A."""
    total_silenced_legit: int = 0
    gold_errors: list[dict] = field(default_factory=list)   # verified mislabels → correct
    real_fns: list[dict] = field(default_factory=list)      # intro absent → real FN
    cap: float = 0.05

    @property
    def gold_error_fraction(self) -> float:
        if not self.total_silenced_legit:
            return 0.0
        return len(self.gold_errors) / self.total_silenced_legit

    @property
    def halt(self) -> bool:
        """True when too many silenced-legit auto-correct → the FIX is suspect."""
        return self.gold_error_fraction > self.cap and len(self.gold_errors) > 0

    @property
    def has_real_fns(self) -> bool:
        return len(self.real_fns) > 0


def audit_silenced_legit(findings: list[dict], cap: float = 0.05) -> CorrectionAudit:
    """Classify each silenced-legit finding as gold-error vs real-FN.

    Each finding dict must carry: term, claim_text, ancestor_texts (list),
    reference_form, and any identity keys (patent_id, claim_id) to echo back.
    """
    audit = CorrectionAudit(total_silenced_legit=len(findings), cap=cap)
    for f in findings:
        present, evidence = pattern_a_intro_present(
            f.get("term", ""),
            f.get("claim_text", ""),
            f.get("ancestor_texts") or [],
            f.get("reference_form"),
        )
        rec = dict(f)
        rec["pattern_a_evidence"] = evidence
        (audit.gold_errors if present else audit.real_fns).append(rec)
    return audit


# ---- claim/ancestor text retrieval from the corpus (production parser) -------

def claim_and_ancestor_text(jurisdiction: str, patent_id: str, claim_id) -> tuple[str, list[str]]:
    """Return (claim_text, [ancestor_claim_texts]) for a corpus finding,
    using the production parser's dependency chain. Empty on miss."""
    import round1_corpus_harness as h
    records = {r.get("patent_id"): r for r in h.load_corpus(jurisdiction)}
    rec = records.get(patent_id)
    if not rec:
        return "", []
    doc = h._build_doc(rec, jurisdiction)
    if doc is None:
        return "", []
    claims = doc if isinstance(doc, list) else getattr(doc, "claims", [])
    by_num = {}
    for c in claims:
        num = getattr(c, "id", None)
        if num is not None:
            by_num[num] = c
    target = by_num.get(claim_id)
    if target is None:
        return "", []

    def _text(c) -> str:
        return getattr(c, "text", None) or str(c)

    # Walk ancestor chain (transitive) via .dependencies.
    seen, frontier, anc = set(), list(getattr(target, "dependencies", []) or []), []
    while frontier:
        n = frontier.pop()
        if n in seen or n == claim_id:
            continue
        seen.add(n)
        pc = by_num.get(n)
        if pc is not None:
            anc.append(_text(pc))
            frontier.extend(getattr(pc, "dependencies", []) or [])
    return _text(target), anc
