# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# specsup_corpus_runner.py - Engine-2 (spec-support / §112(a) written-description)
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
# ⚠️ CORRECTED 2026-09-01 - READ THIS BEFORE TRUSTING THE 2026-06-28 FINDING.
# This header used to end with: "Do NOT ship inventory-term cosmetic fixes for
# spec-support - they reduce no FPs." That conclusion measured the right number
# and drew the wrong lesson, and it is why an entire FP class kept recurring:
# every later session read it as "this class is not worth fixing".
#
# What 2026-06-28 actually established is that cleaning an inventory term does
# not change the finding COUNT, because the 3-tier fuzzy matcher still locates
# the bare noun inside a coverb-leaked term. That is true and still true.
# What it missed is that the reporter never sees the count - they see the TERM.
# A finding whose term reads 漸縮部且容置於 or 以擷取一 or `local statistical
# values respective` is a visible defect at 137 findings just as much as at 138,
# and four reports in one week (#676 / #691 / #692 TW, #688 / #689 US) say so.
#
# So: a count-based no-growth gate CANNOT see this class in either direction.
# That is why `--quality` exists below. Run BOTH. The count gate answers "did I
# manufacture findings"; the quality gate answers "are the terms I emit
# structurally nouns". Engine 2 had only the first for its whole life.
#
# USAGE:
#   python tests/eval/specsup_corpus_runner.py --juris TW
#   python tests/eval/specsup_corpus_runner.py --juris TW --terms   # dump finding terms
#   python tests/eval/specsup_corpus_runner.py --juris TW --quality # TERM-QUALITY gate
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
        doc = TwPatentDocument(
            patent_type=TwPatentType.INVENTION, title="x",
            technical_field=[], prior_art=[], disclosure=[],
            drawings_description=[], embodiment=[spec_text], symbol_table=[],
            claims=base.claims, abstract_text="",
        )
    elif juris == "CN":
        from patentlint.models import CnPatentDocument
        # CnPatentDocument's body field is `detailed_description`; there is no
        # `embodiments` field. Passing one silently dropped the spec (pydantic
        # ignores extras), so _collect_spec_text_cn saw an EMPTY spec and every
        # claim term counted as unsupported - 58,943 findings over 1,025 drafts
        # vs TW's 137, and a term written 7 times in the spec still "failed".
        # That made the CN no-growth gate VACUOUS (noise compared to noise).
        doc = CnPatentDocument(
            title="x", claims=base.claims, technical_field=[], background=[],
            summary=[], detailed_description=[spec_text],
        )
    else:
        raise SystemExit(f"unsupported juris {juris}")
    _assert_spec_survived(doc, juris, spec_text)
    return doc


def _assert_spec_survived(doc, juris: str, spec_text: str) -> None:
    """#413 non-vacuity guard - the durable fix for the class, not the instance.

    Both patent-document models use pydantic ``extra='ignore'``, so a wrong
    field name is dropped SILENTLY and the spec vanishes with no error. That is
    exactly how the CN arm ran vacuous for months (``embodiments=`` instead of
    ``detailed_description=``): every claim term counted unsupported and the
    "no-growth" gate compared noise to noise. Round-trip the injected spec
    through the SAME collector the check uses and fail LOUD if it did not
    survive, so any future field-name drift trips on the first draft instead of
    quietly producing confident garbage. (An empty spec is legitimately empty.)
    """
    if not spec_text.strip():
        return
    from patentlint.analysis.cn_spec_support import _collect_spec_text_cn
    from patentlint.analysis.tw_spec_support import _collect_spec_text
    collect = _collect_spec_text if juris == "TW" else _collect_spec_text_cn
    field = "embodiment" if juris == "TW" else "detailed_description"
    if not collect(doc).strip():
        raise SystemExit(
            f"specsup runner VACUITY GUARD ({juris}): the injected spec did not "
            f"survive into doc.{field} -> the collector (collected text is empty "
            f"while spec_text is non-empty). A field name was almost certainly "
            f"dropped by pydantic extra='ignore' - the #413 failure mode. Any "
            f"'no-growth' number from this runner in this state is vacuous."
        )


def _checker(juris: str):
    if juris == "TW":
        from patentlint.analysis.tw_spec_support import check_spec_support_tw
        return check_spec_support_tw
    from patentlint.analysis.cn_spec_support import check_spec_support_cn
    return check_spec_support_cn


# --- TERM-QUALITY gate -----------------------------------------------------
# A structurally-bad term is one that is not a noun phrase at all. These are
# the shapes real reporters filed, generalised to their grammatical class -
# NOT a list of the specific strings reported, which would only ever catch the
# reports already filed.
_STRUCTURAL_CONJ_TW = "\u4e14\u4e26\u800c\u53c8\u4ea6\u7686\u9808\u9010"
# ...but several of those characters DO head real compounds, so the gate needs
# the same lexeme exceptions the walker does or it reports its own false
# positives and gets ignored. Measured on the corpus: 並聯 118, 並排 13,
# 並列 5, 逐漸 13, 逐出 19.
_CONJ_COMPOUND_EXCEPTIONS_TW = (
    "\u4e26\u806f", "\u4e26\u5217", "\u4e26\u6392",
    "\u9010\u6f38", "\u9010\u51fa", "\u9010\u884c",
)
# Verb+preposition lexemes: nothing that begins with one is an element name.
_PREDICATE_HEADS_TW = (
    "\u5c6c\u65bc", "\u7528\u65bc", "\u57fa\u65bc", "\u4f4d\u65bc",
    "\u7d93\u904e", "\u4f86\u81ea", "\u6839\u64da",
)
_PREDICATE_TAILS_US = (
    " respective", " indicative", " operable", " responsive", " configured",
)


def _term_defects(juris: str, term: str) -> list[str]:
    """Name every structural reason `term` is not a noun phrase."""
    out = []
    if juris.upper() in ("TW", "CN"):
        masked = term
        for exc in _CONJ_COMPOUND_EXCEPTIONS_TW:
            masked = masked.replace(exc, "\u3007" * len(exc))
        for ch in _STRUCTURAL_CONJ_TW:
            if ch in masked:
                out.append(f"contains the conjunction {ch}")
        for lx in _PREDICATE_HEADS_TW:
            if term.startswith(lx):
                out.append(f"opens with the predicate head {lx}")
        # A term ending in a bare quantifier is never a complete noun phrase
        # (以擷取一, 傳遞一). The walker calls this the object-final shape.
        if term and term[-1] in "\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341":
            out.append("ends in a bare quantifier")
    else:
        low = " " + term.lower()
        for tl in _PREDICATE_TAILS_US:
            if low.endswith(tl):
                out.append(f"ends in the predicative adjective{tl}")
    return out


# Known residuals as of 2026-09-01 (TW R47 / CN R64). A gate that is
# permanently red gets ignored, so the bar is "no MORE than this", and every
# member is a documented withhold rather than an unexamined failure:
#   TW 1 - 並包含一組n-1個二極體. 並 cannot be cut (並聯 "parallel connection"
#          occurs 118x, plus 並列 / 並排), so this one needs a lexeme-gated
#          cut, not the bare conjunction cut that shipped.
#   CN 5 - 并且-initial captures (并且在 / 并且当 / 并且-). Cutting at 且 leaves
#          a single character, below the 2-char floor, so the capture falls
#          back uncut. Needs the leading-conjunction strip, a separate class.
# RAISING EITHER NUMBER IS A REGRESSION. Lowering one is the next round's win.
_EXPECTED_BAD = {"TW": 1, "CN": 5, "US": 0}


def _report_term_quality(juris: str, terms) -> int:
    """Report structurally-bad emitted terms. Returns 1 on a REGRESSION."""
    bad = []
    for entry in terms:
        t = entry[1] if isinstance(entry, (tuple, list)) else entry
        d = _term_defects(juris, str(t))
        if d:
            bad.append((str(t), d))
    exp = _EXPECTED_BAD.get(juris.upper(), 0)
    print(f"\n=== TERM-QUALITY gate ({juris}) ===")
    print(f"  terms emitted        : {len(terms)}")
    print(f"  structurally BAD     : {len(bad)}  (documented residual: {exp})")
    for t, d in bad:
        print(f"    {t!r}  <- {'; '.join(d)}")
    ok = len(bad) <= exp
    if len(bad) < exp:
        print(f"  ** IMPROVED: {exp - len(bad)} fewer than the recorded "
              f"residual - lower _EXPECTED_BAD to {len(bad)} in this file. **")
    print(f"  GATE: {'PASS' if ok else 'FAIL (REGRESSION)'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Engine-2 spec-support corpus runner")
    ap.add_argument("--juris", required=True, choices=["TW", "CN"])
    ap.add_argument("--terms", action="store_true", help="dump finding terms")
    ap.add_argument("--limit", type=int, default=0,
                    help="cap the --terms dump (0 = all; the gate needs all)")
    ap.add_argument("--quality", action="store_true",
                    help="TERM-QUALITY gate: report emitted terms that are not "
                         "structurally noun phrases. The count gate cannot see "
                         "this class - see the corrected header.")
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
        if args.terms or args.quality:
            for f in findings:
                # Spec-support findings carry `phrase`, NOT `term` - reading
                # `term` alone yields None on every one of them (the 2026-08-28
                # mis-diagnosis). Safe accessor, both shapes.
                t = (getattr(f, "term", None) or getattr(f, "phrase", None)
                     or (f.get("term") or f.get("phrase")
                         if isinstance(f, dict) else None)
                     or str(f))
                terms.append((pid, t))

    print(f"== {args.juris} spec-support ==")
    print(f"drafts measured : {drafts}  (skipped-on-error: {errors})")
    print(f"total findings  : {total}")
    if args.terms:
        # The dump was truncated at 60 for years, which silently made the
        # no-growth gate compare two TRUNCATED lists - a count equal to its own
        # limit is a truncation, not a count. --limit 0 (the default) dumps all.
        for pid, t in (terms if args.limit == 0 else terms[:args.limit]):
            print(f"  {pid}  {t!r}")
    if args.quality:
        return _report_term_quality(args.juris, terms)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
