# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# specsup_corpus_runner.py — Engine-2 (spec-support / §112(a) written-description)
# corpus FN-guard + characterizer (ADR-159, 2026-06-28).
#
# WHY: validate_fix.py measures the ANTECEDENT (§112(b)) walker. Spec-support is
# a separate check (check_spec_support_tw / _cn) whose over-capture FPs cannot be
# measured by validate_fix. This runner joins the claims corpus
# (round1_corpus_harness) to the scraped specification (tests/eval/<j>_descriptions.json)
# and runs check_spec_support_* end-to-end, so a candidate spec-support fix can be
# FN-guarded: the finding set must only SHRINK, and every removed finding's term
# must now be present in the spec (an over-capture that was resolved), never a
# genuinely-unsupported term.
#
# KEY FINDING (2026-06-28): the TW spec-support coverb over-capture (#293-296,
# 至一電容 / 向一第二網路 / 為一現場可編程邏輯閘陣列) is INERT. Cleaning the
# inventory term (至一電容 -> 電容) changed 0 of 137 corpus findings (before ==
# after) — the 3-tier fuzzy matcher (substring + word-window) already locates the
# bare noun inside the coverb-leaked term against the spec, so the leak never
# becomes a finding. This re-confirms the earlier "spec-support over-capture is
# INERT" conclusion at corpus scale. Do NOT ship inventory-term cosmetic fixes
# for spec-support — they reduce no FPs.
#
# USAGE:
#   python tests/eval/specsup_corpus_runner.py --juris TW
#   python tests/eval/specsup_corpus_runner.py --juris TW --terms   # dump finding terms
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent


def _load_descriptions(juris: str) -> dict:
    path = THIS_DIR / f"{juris.lower()}_descriptions.json"
    if not path.exists():
        print(f"FATAL: scraped spec not found at {path} (gitignored, local-only)")
        sys.exit(2)
    return json.loads(path.read_text())


def _build_doc_with_spec(record, juris: str, spec_text: str, harness):
    """Build a jurisdiction doc carrying the claims + the scraped spec body.

    The spec is injected as a single embodiment paragraph; check_spec_support's
    matcher concatenates all body sections, so sectioning does not affect the
    substring / word-window match.
    """
    base = harness._build_doc(record, juris)
    if not base:
        return None
    if juris == "TW":
        from patentlint.models import TwPatentDocument, TwPatentType
        return TwPatentDocument(
            patent_type=TwPatentType.INVENTION, title="x",
            technical_field=[], prior_art=[], disclosure=[],
            drawings_description=[], embodiment=[spec_text], symbol_table=[],
            claims=base.claims, abstract_text="",
        )
    if juris == "CN":
        from patentlint.models import CnPatentDocument
        return CnPatentDocument(
            title="x", claims=base.claims, technical_field=[], background=[],
            summary=[], embodiments=[spec_text],
        )
    raise SystemExit(f"unsupported juris {juris}")


def _checker(juris: str):
    if juris == "TW":
        from patentlint.analysis.tw_spec_support import check_spec_support_tw
        return check_spec_support_tw
    from patentlint.analysis.cn_spec_support import check_spec_support_cn
    return check_spec_support_cn


def main() -> int:
    ap = argparse.ArgumentParser(description="Engine-2 spec-support corpus runner")
    ap.add_argument("--juris", required=True, choices=["TW", "CN"])
    ap.add_argument("--terms", action="store_true", help="dump finding terms")
    ap.add_argument("--min-spec", type=int, default=2000,
                    help="skip drafts whose scraped spec is shorter than this")
    args = ap.parse_args()

    sys.path.insert(0, str(THIS_DIR))
    import round1_corpus_harness as h

    desc = _load_descriptions(args.juris)
    records = h.load_corpus(args.juris)
    check = _checker(args.juris)

    total = drafts = errors = 0
    terms: list[tuple[str, str]] = []
    for r in records:
        pid = r.get("patent_id")
        entry = desc.get(pid)
        if not entry:
            continue
        spec = (entry.get("description") if isinstance(entry, dict) else entry) or ""
        if len(spec) < args.min_spec:
            continue
        doc = _build_doc_with_spec(r, args.juris, spec, h)
        if not doc:
            continue
        try:
            findings = check(doc)
        except Exception:
            errors += 1
            continue
        drafts += 1
        total += len(findings)
        if args.terms:
            for f in findings:
                t = getattr(f, "term", None) or (
                    f.get("term") if isinstance(f, dict) else str(f))
                terms.append((pid, t))

    print(f"== {args.juris} spec-support ==")
    print(f"drafts measured : {drafts}  (skipped-on-error: {errors})")
    print(f"total findings  : {total}")
    if args.terms:
        for pid, t in terms[:60]:
            print(f"  {pid}  {t!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
