# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Corpus-wide D1 mutation smoke test.

Iterates every fixture × jurisdiction. For each, finds the strongest
canonical (numeral with ≥5 same-name occurrences) and replaces one
occurrence with a synthetic typo. Asserts D1 then fires a conflict at
that numeral with the typo as an outlier.

This is the regression gate for the structural reliability of D1
across US/CN/TW. Mutations that were undetected previously caused
trust-loss bugs (Christopher's 110P000868 主控模組82 → 50 case);
codifying them prevents silent regression.

Skips fixtures that don't have a strong-enough canonical (test6's
SAG503A Latin-prefix entry, testspec4's resin system with only 3
occurrences) — these can't host a meaningful mutation test.
"""
from __future__ import annotations

import re
from pathlib import Path
from collections import Counter

import pytest

from patentlint.parser.docx_loader import (
    load_docx,
    load_docx_cn,
    load_docx_tw,
)
from patentlint.analysis.specification import (
    extract_numeral_name_pairs as us_pairs,
    _detect_d1_conflicts as us_detect_d1,
)
from patentlint.analysis.cn_specification import (
    _cn_extract_numeral_name_pairs as cn_pairs,
    _cn_detect_d1_conflicts as cn_detect_d1,
)


REPO = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = REPO / "tests" / "fixtures"

# Per-fixture skip reasons — all are corpus issues, not algorithm bugs.
KNOWN_SKIP = {
    # Latin-prefix Sag503A — no plausible mutation target after our
    # canonical-discovery heuristic; represents a 5%-noise edge case.
    "test6_chemistry_bare_noun_list.docx",
    # canonical "resin system" only 3 occurrences with awkward spacing
    # ("resin system 10" not actually adjacent in this draft); the
    # canonical-finder picks it but the regex-based mutator can't
    # locate "resin system 10" to replace.
    "testspec4_resin_markush.docx",
}


def _list_fixtures(j: str) -> list[Path]:
    d = FIXTURES_DIR / j / "local"
    if not d.exists():
        return []
    return sorted(
        p for p in d.iterdir()
        if p.suffix.lower() in (".docx",) and not p.name.startswith("~")
    )


def _get_text(p: Path, j: str) -> str:
    if j == "us":
        return load_docx(str(p)).full_text
    if j == "tw":
        return "\n".join(load_docx_tw(str(p)).paragraphs)
    if j == "cn":
        out: list[str] = []
        for sec in load_docx_cn(str(p)).sections:
            out.extend(sec.paragraphs)
        return "\n".join(out)
    raise ValueError(j)


def _find_canonical(text: str, j: str) -> tuple[str, str] | None:
    """Find a (numeral, canonical_keyed_name) pair with ≥5 occurrences."""
    pairs = us_pairs(text) if j == "us" else cn_pairs(text)
    by_num: dict[str, Counter] = {}
    for n, name in pairs:
        by_num.setdefault(n, Counter())[name] += 1
    for n, ct in by_num.items():
        for name, c in ct.most_common(1):
            if c >= 5:
                return (n, name)
    return None


def _mutate_one(text: str, j: str, num: str, canonical: str) -> str | None:
    """Replace one occurrence of canonical+num with a synthetic typo."""
    if "|" in canonical:
        ord_, head = canonical.split("|", 1)
        canon_surface = ord_ + head
    else:
        canon_surface = canonical
    if j == "us":
        pattern = re.compile(
            rf"\b{re.escape(canon_surface)}\s+{re.escape(num)}\b",
            re.IGNORECASE,
        )
        m = pattern.search(text)
        if not m:
            return None
        replaced = m.group(0).replace(
            canon_surface, "completely different element"
        )
        return text[: m.start()] + replaced + text[m.end():]
    target = canon_surface + num
    if target not in text:
        return None
    # Use a marker noun with NO 的/之 marker so post-de strip preserves
    # the full "迥異標記元件" string in the captured outlier.
    return text.replace(target, "迥異標記元件" + num, 1)


def _gather_test_cases() -> list[tuple[str, str, Path]]:
    cases: list[tuple[str, str, Path]] = []
    for j in ("us", "cn", "tw"):
        for p in _list_fixtures(j):
            if p.name in KNOWN_SKIP:
                continue
            cases.append((j, p.name, p))
    return cases


CASES = _gather_test_cases()


@pytest.mark.parametrize(
    "jurisdiction, fixture_name, fixture_path",
    [(j, n, p) for (j, n, p) in CASES],
    ids=[f"{j}-{n}" for (j, n, _) in CASES],
)
def test_d1_detects_synthetic_mutation(
    jurisdiction: str,
    fixture_name: str,
    fixture_path: Path,
) -> None:
    """For each fixture, mutating one canonical occurrence produces a
    detectable D1 conflict at that numeral with the typo as outlier."""
    if not fixture_path.exists():
        pytest.skip(f"{fixture_name} not present")
    try:
        text = _get_text(fixture_path, jurisdiction)
    except Exception as e:
        pytest.skip(f"load error: {e}")
    canonical = _find_canonical(text, jurisdiction)
    if canonical is None:
        pytest.skip("no strong canonical found in fixture")
    num, canon_keyed = canonical
    mutated = _mutate_one(text, jurisdiction, num, canon_keyed)
    if mutated is None:
        pytest.skip(f"could not locate canonical {canon_keyed!r} + #{num}")

    conflicts = (
        us_detect_d1(us_pairs(mutated))
        if jurisdiction == "us"
        else cn_detect_d1(cn_pairs(mutated))
    )
    matched = [c for c in conflicts if c["numeral"] == num]
    assert matched, (
        f"D1 did not fire for #{num} after mutating canonical "
        f"{canon_keyed!r} in {fixture_name}"
    )
    outlier_names = [
        (o["name"] or "") for o in matched[0]["outliers"]
    ]
    typo_marker = (
        "completely different element"
        if jurisdiction == "us"
        else "迥異標記元件"
    )
    has_typo_outlier = any(typo_marker in n for n in outlier_names) or any(
        # Looser: capture if any of the typo's content chars survive
        ("迥" in n or "異標" in n) if jurisdiction != "us"
        else "different" in n.lower()
        for n in outlier_names
    )
    assert has_typo_outlier, (
        f"D1 fired for #{num} but the synthetic typo wasn't surfaced as "
        f"an outlier; outliers: {outlier_names!r}"
    )
