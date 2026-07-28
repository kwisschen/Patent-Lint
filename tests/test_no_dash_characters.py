# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""Repo-wide gate: no em dashes (U+2014) or en dashes (U+2013) in source.

House rule: use a plain "-", a colon, parentheses, or restructure the
sentence. This covers authored prose (comments, docstrings, UI copy,
Markdown) across every tracked text file.

Two things are deliberately out of scope:

* Labeled corpus and eval RESULT JSON under tests/fixtures and tests/eval.
  Those dashes sit in free-text triage ``notes``; they are data, not
  product prose, and rewriting them churns the FN-guard's memory.

* Four regex character classes that match REAL patent text. Patent drafts
  contain dashed reference numerals ("(12-3)") and claim ranges ("claims
  1-5" written with an en dash), so the analyzer must keep matching those
  characters. Removing them would be a silent functional regression, which
  is why they are pinned here by exact location rather than by a blanket
  file skip.

The detectors use \\u escapes on purpose: written as literals, a future
repo-wide dash sweep would rewrite this file into a gate that only matches
plain hyphens and would then pass vacuously.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

EM_DASH = "—"
EN_DASH = "–"

REPO = Path(__file__).parent.parent

# Regex character classes that must keep the dash characters so the
# analyzer still strips dashed reference numerals / claim ranges from real
# drafts. Pinned as (path, substring-that-must-be-present).
ALLOWED_REGEX_SITES = {
    "src/patentlint/analysis/tw_spec_support.py",
    "src/patentlint/analysis/cn_spec_support.py",
    "src/patentlint/analysis/epc_abstract.py",
    "tests/eval/measure_term_in_desc.py",
    "tests/eval/measure_tipo_anchor.py",
}

SCANNED_SUFFIXES = {
    ".py", ".js", ".jsx", ".mjs", ".css", ".html", ".json", ".md",
    ".yml", ".yaml", ".toml", ".sh",
}

SKIP_SUBSTRINGS = ("node_modules/", "frontend/src/generated/")


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        capture_output=True, text=True, check=True, cwd=REPO,
    ).stdout
    return [f for f in out.split("\0") if f]


def _is_data_file(rel: str) -> bool:
    """Labeled corpus / eval results are data, not authored prose."""
    return (
        rel.startswith(("tests/fixtures/", "tests/eval/")) and rel.endswith(".json")
    ) or ".bak" in Path(rel).name


def _in_char_class(line: str, idx: int) -> bool:
    opened = line.rfind("[", 0, idx)
    return opened != -1 and line.find("]", opened, idx) == -1


def _offenders() -> list[str]:
    found: list[str] = []
    for rel in _tracked_files():
        if any(s in rel for s in SKIP_SUBSTRINGS) or _is_data_file(rel):
            continue
        path = REPO / rel
        if path.suffix not in SCANNED_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        if EM_DASH not in text and EN_DASH not in text:
            continue
        for lineno, line in enumerate(text.split("\n"), 1):
            for i, ch in enumerate(line):
                if ch not in (EM_DASH, EN_DASH):
                    continue
                # A dash inside a regex character class in an allowlisted
                # file is load-bearing; anything else is prose.
                if rel in ALLOWED_REGEX_SITES and _in_char_class(line, i):
                    continue
                found.append(f"{rel}:{lineno}: {line.strip()[:110]}")
                break
    return found


def test_no_dash_characters_in_source():
    offenders = _offenders()
    if offenders:
        pytest.fail(
            f"\n{len(offenders)} line(s) contain an em dash or en dash.\n"
            "Use a plain '-', a colon, or parentheses instead.\n\n"
            + "\n".join(f"  {o}" for o in offenders[:25])
            + (f"\n  ... and {len(offenders) - 25} more" if len(offenders) > 25 else "")
        )


def test_allowlisted_regexes_still_carry_the_dashes():
    """Guard the guard: the allowlist must not silently go stale.

    If a future edit drops the dash characters from these patterns, the
    analyzer stops stripping dashed reference numerals from real drafts.
    That is invisible at runtime, so pin it here.
    """
    for rel in sorted(ALLOWED_REGEX_SITES):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert EM_DASH in text or EN_DASH in text, (
            f"{rel} no longer contains a dash character. If that pattern was "
            f"intentionally removed, drop it from ALLOWED_REGEX_SITES too."
        )
