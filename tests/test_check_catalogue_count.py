# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""Pin every advertised check count to CHECKS.md, so the catalogue cannot drift.

The count is DEFINED by frontend/scripts/emit-stats.mjs, which is what the
live site's stat card shows: CHECKS.md table rows under the jurisdiction
sections, excluding the header/separator rows and the † informational rows
(summary tiles that never produce a graded PASS / REVIEW / FIX result). The
pre-analysis gate rows sit under no jurisdiction section and are excluded for
the same reason.

The README drifted for months because nothing pinned it: the headline said
161 while its own section headers said 34 EPC / 34 CN / 40 TW and the
CHECKS.md footer said 154. This test derives the number and asserts every
advertised copy of it.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Mirror of JUR_BY_HEADER in frontend/scripts/emit-stats.mjs. A test below
# asserts the two mappings are identical, so they cannot drift apart.
JUR_BY_HEADER = {
    "Specification": "US",
    "Claims": "US",
    "Brief Description of Drawings": "US",
    "Abstract": "US",
    "CN Specification": "CN",
    "CN Claims": "CN",
    "CN Abstract": "CN",
    "CN Drawings": "CN",
    "TW Specification": "TW",
    "TW Claims": "TW",
    "TW Abstract": "TW",
    "TW Cross-Reference": "TW",
    "TW Drawings": "TW",
    "EPC Specification": "EPC",
    "EPC Claims": "EPC",
    "EPC Abstract": "EPC",
    "EPC Drawings": "EPC",
}


def _count() -> dict[str, int]:
    counts = {"US": 0, "EPC": 0, "CN": 0, "TW": 0}
    current = None
    for line in (ROOT / "CHECKS.md").read_text(encoding="utf-8").splitlines():
        header = re.match(r"^## (.+?)(?:\s*\(.*\))?$", line)
        if header:
            current = JUR_BY_HEADER.get(header.group(1).strip())
            continue
        if not current or not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 3:
            continue
        first = cols[1]
        if not first or first.startswith("-") or first == "Check" or "†" in first:
            continue
        counts[current] += 1
    return counts


def test_python_mirror_matches_the_js_generator_mapping():
    js = (ROOT / "frontend/scripts/emit-stats.mjs").read_text(encoding="utf-8")
    block = js[js.index("const JUR_BY_HEADER = {"):]
    block = block[: block.index("}")]
    pairs = dict(re.findall(r"'?([A-Za-z][A-Za-z -]*?)'?\s*:\s*'(US|CN|TW|EPC)'", block))
    assert pairs == JUR_BY_HEADER


def test_every_jurisdiction_section_has_checks():
    """Non-vacuity: a parsing regression that counts nothing must fail."""
    counts = _count()
    assert all(n > 0 for n in counts.values()), counts


def test_readme_advertises_the_derived_count():
    c = _count()
    total = sum(c.values())
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"{total} checks against USPTO MPEP" in readme
    assert (
        f"{c['US']} U.S. + {c['EPC']} EPC + {c['CN']} CN + {c['TW']} TW = {total} deterministic checks"
        in readme
    )
    assert f"{total} checks run instantly" in readme
    assert f"{total} automated checks across four jurisdictions" in readme
    assert f"### U.S. Patent Applications ({c['US']} checks)" in readme
    assert f"Patent Applications - English drafts ({c['EPC']} checks, v1 beta)" in readme
    assert f"The full {c['EPC']}-check EPC catalog" in readme
    assert f"### Chinese Patent Applications ({c['CN']} checks)" in readme
    assert f"### Taiwanese Patent Applications ({c['TW']} checks)" in readme


def test_checks_md_footer_matches_its_own_rows():
    c = _count()
    total = sum(c.values())
    text = (ROOT / "CHECKS.md").read_text(encoding="utf-8")
    assert (
        f"**Total checks: {total}** ({c['US']} US + {c['EPC']} EPC + {c['CN']} CN + {c['TW']} TW;"
        in text
    )
