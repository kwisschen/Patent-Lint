# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Phase 8c Stage 1.5 ground-truth claim-count audit.

For each real CN .docx fixture in ``tests/fixtures/cn/local/``, this
script prints two numbers:

1. **Loader count** — claims recovered by the production pipeline
   (``extract_cn_sections_from_docx(load_docx_cn(path))``).
2. **Ground-truth count** — stricter heuristic that walks the raw
   python-docx paragraph stream, locates the claims section positionally,
   and counts only claim starts whose numbering is monotonically
   increasing.

The audit is a gate for Stage 1 loader invariants. Deltas ≥5% on any
fixture indicate the loader is under-counting (missed 五书 boundary,
dropped w:numPr run, swallowed spec paragraphs).

Invoke::

    python tests/fixtures/cn/local/_audit_claim_counts.py

Output goes to stdout as a markdown-formatted table — the writeup pastes
the table verbatim. Real patent filenames are part of the table, so the
table itself does NOT belong in source control (the script does).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

FIXTURE_DIR = Path(__file__).parent
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "src"))

from patentlint.parser.docx_loader import load_docx_cn  # noqa: E402
from patentlint.parser.sections_cn import extract_cn_sections_from_docx  # noqa: E402


_CLAIMS_HEADER_RE = re.compile(r"^[\s\u3000]*权\s*利\s*要\s*求\s*书")
_SPEC_HEADER_RE = re.compile(r"^[\s\u3000]*说\s*明\s*书(?!\s*摘\s*要|\s*附\s*图)")
_CLAIM_START_TYPED_RE = re.compile(r"^[\s\u3000]*(\d+)\s*[.．。、]")
# Spec sub-section headers — if any appear, the claims region has ended
# (some patents have no standalone 说明书 anchor between claims and spec).
_SPEC_SUBSECTION_HEADERS = {
    "技术领域", "背景技术", "发明内容", "附图说明", "具体实施方式",
}


def _has_numpr(para) -> bool:
    pPr = para._element.find(qn("w:pPr"))
    if pPr is None:
        return False
    numPr = pPr.find(qn("w:numPr"))
    if numPr is None:
        return False
    numId = numPr.find(qn("w:numId"))
    if numId is None:
        return False
    val = numId.get(qn("w:val"))
    return val is not None and val != "0"


def ground_truth_count(path: Path) -> int:
    """Stricter counter: positional claims-section bounding + monotonic
    claim-start numbering.

    A paragraph is a "claim start" if (a) it carries a typed Arabic
    numeral prefix (``N.`` / ``N．`` / ``N、``) or (b) it has Word
    ``w:numPr`` auto-numbering. Inside the bounded claims region we
    assign each claim start a synthetic sequential number and require the
    numbering to monotonically increase by 1 (typed prefix) or implicitly
    (numPr run)."""
    doc = Document(str(path))

    in_claims = False
    after_claims = False
    # Synthetic counter — numPr paragraphs don't carry numbers in text.
    synthetic_counter = 0
    claim_starts = 0
    last_typed_num = 0

    for para in doc.paragraphs:
        text = para.text.strip()
        if not in_claims:
            if _CLAIMS_HEADER_RE.match(text):
                in_claims = True
            continue
        if after_claims:
            continue
        # End of claims region: 说明书 header (spec starts) — but NOT
        # 说明书摘要 / 说明书附图.
        if _SPEC_HEADER_RE.match(text):
            after_claims = True
            continue
        # Also treat a standalone 说明书摘要 as end-of-claims boundary,
        # since some exports place abstract after claims.
        if text in ("说明书摘要", "摘要"):
            after_claims = True
            continue
        # Spec sub-section header — claims region is over.
        if text in _SPEC_SUBSECTION_HEADERS:
            after_claims = True
            continue

        typed_match = _CLAIM_START_TYPED_RE.match(text)
        if typed_match:
            n = int(typed_match.group(1))
            # Monotonic requirement — skip stray numerals that don't
            # continue the sequence.
            if n == last_typed_num + 1 or (last_typed_num == 0 and n == 1):
                claim_starts += 1
                synthetic_counter = n
                last_typed_num = n
            elif n > last_typed_num:
                # Accept gaps (some patents skip numbers) but still require
                # monotonic increase.
                claim_starts += 1
                synthetic_counter = n
                last_typed_num = n
            continue
        if _has_numpr(para) and text:
            synthetic_counter += 1
            claim_starts += 1
            last_typed_num = synthetic_counter
            continue
    return claim_starts


def loader_count(path: Path) -> int:
    loaded = load_docx_cn(str(path))
    doc = extract_cn_sections_from_docx(loaded.sections)
    return len(doc.claims)


def main() -> int:
    fixtures = sorted(FIXTURE_DIR.glob("*.docx"))
    if not fixtures:
        print("No .docx fixtures found in", FIXTURE_DIR, file=sys.stderr)
        return 1

    rows: list[tuple[str, int, int, int, str]] = []
    for p in fixtures:
        try:
            g = ground_truth_count(p)
        except Exception as exc:
            rows.append((p.name, -1, -1, 0, f"GT-ERROR: {exc}"))
            continue
        try:
            loader = loader_count(p)
        except Exception as exc:
            rows.append((p.name, -1, g, 0, f"LOADER-ERROR: {exc}"))
            continue
        delta = loader - g
        pct = (abs(delta) / g * 100.0) if g else 0.0
        status = "OK" if pct < 5.0 else f"DELTA {pct:.1f}%"
        rows.append((p.name, loader, g, delta, status))

    # Markdown table
    print("| Fixture | Loader | Ground-truth | Delta | Status |")
    print("|---|---:|---:|---:|---|")
    for name, loader, g, d, s in rows:
        print(f"| {name} | {loader} | {g} | {d:+d} | {s} |")

    worst = 0.0
    for _, loader, g, _, _ in rows:
        if g > 0:
            worst = max(worst, abs(loader - g) / g * 100.0)
    print(f"\nWorst delta: {worst:.2f}%")
    return 0 if worst < 5.0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
