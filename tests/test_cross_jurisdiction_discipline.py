# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Cross-jurisdiction discipline check.

User-driven discipline (2026-06-01): every walker round should either
ship its fix across all applicable jurisdictions in the same PR, OR
document explicitly why it's single-jurisdiction. Past sessions had
recurring drift where US R7 / R8 / R36 shipped without simultaneous
TW / CN parity rounds, and the maintainer had to manually remind.

This test enforces the discipline by scanning the most recent rounds
in each labels file's round_history and asserting that the description
either:
  (a) explicitly references cross-jurisdiction work (matches one of
      the cross-juris markers below), OR
  (b) explicitly disclaims single-jurisdiction scope (matches one of
      the single-juris-scope markers).

The gate applies only to rounds shipped on or after the discipline
start date so existing rounds without the markers don't break the
test retroactively.

Marker philosophy: catch the SUBSTANCE of cross-jurisdiction analysis
without requiring exact phrasing. Patent-attorney voice varies; the
markers cover the common ways one might describe cross-jurisdiction
work or its absence.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Labels files to audit. Each file's metadata.round_history is checked.
LABELS_FILES = (
    REPO_ROOT / "tests/fixtures/us/antecedent_labels_us.json",
    REPO_ROOT / "tests/fixtures/cn/antecedent_labels_cn.json",
    REPO_ROOT / "tests/fixtures/tw/antecedent_labels.json",
)

# Discipline start: rounds shipped on/after this date are subject to the
# cross-jurisdiction check. Earlier rounds are grandfathered to avoid
# retroactive failure.
DISCIPLINE_START = datetime(2026, 6, 1, tzinfo=timezone.utc)

# Markers that indicate cross-jurisdiction work was considered.
_CROSS_JURIS_MARKERS = (
    r"cross-jurisdiction",
    r"cross-juris",
    r"parity",
    r"mirror",  # "TW R10 mirrors US R8"
    r"\bTW (?:R\d|parity)",
    r"\bCN (?:R\d|parity)",
    r"\bUS (?:R\d|parity)",
    r"per (?:standing|the) (?:user )?instruction",
    # Multi-juris round names (e.g., "R9/R37" or "tw\\+cn")
    r"R\d+\s*/\s*R\d+",
    r"\b(?:tw\+cn|us\+cn|us\+tw|cn\+tw)\b",
)
_CROSS_JURIS_RE = re.compile("|".join(_CROSS_JURIS_MARKERS), re.IGNORECASE)

# Markers that indicate a deliberate single-jurisdiction scope. When
# present, the round is exempt from the cross-jurisdiction requirement.
_SINGLE_JURIS_SCOPE_MARKERS = (
    r"(?:US|CN|TW|EPC)[- ]only",
    r"defer(?:red)? (?:to|until)",
    r"no (?:CN|TW|US|EPC) report",
    r"(?:CN|TW|US|EPC) corpus (?:doesn't|does not) (?:currently )?have",
    r"DR-1",  # empirical-grounding discipline — explicit defer
    r"specific to (?:US|CN|TW|EPC)",
)
_SINGLE_JURIS_SCOPE_RE = re.compile("|".join(_SINGLE_JURIS_SCOPE_MARKERS), re.IGNORECASE)


def _load_round_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return []
    return data.get("metadata", {}).get("round_history", []) or []


def _is_in_scope(round_entry: dict) -> bool:
    """Round was shipped on or after the discipline start date."""
    shipped = round_entry.get("shipped_at")
    if not shipped:
        return False
    try:
        ts = datetime.fromisoformat(shipped.replace("Z", "+00:00"))
    except ValueError:
        return False
    return ts >= DISCIPLINE_START


def _has_cross_juris_consideration(description: str) -> bool:
    return bool(
        _CROSS_JURIS_RE.search(description)
        or _SINGLE_JURIS_SCOPE_RE.search(description)
    )


def test_recent_rounds_document_cross_jurisdiction_consideration():
    """Every round shipped on or after the discipline start date must
    document either cross-jurisdiction analysis or explicit single-
    jurisdiction scope. Surfaces drift early; the goal is to make the
    discipline check automatic so the maintainer never has to manually
    remind."""
    failures = []
    for path in LABELS_FILES:
        history = _load_round_history(path)
        juris_key = path.stem  # e.g., antecedent_labels_us, antecedent_labels_cn, antecedent_labels
        for r in history:
            if not _is_in_scope(r):
                continue
            description = r.get("description") or ""
            if not _has_cross_juris_consideration(description):
                failures.append(
                    f"  {juris_key} :: round={r.get('round')} "
                    f"name={r.get('name')!r} — description missing "
                    f"cross-jurisdiction markers AND single-juris-scope markers. "
                    f"Add a sentence about CN/TW/US/EPC analysis (or the explicit "
                    f"reason this round is single-jurisdiction)."
                )
    if failures:
        msg = (
            "Cross-jurisdiction discipline check (post-2026-06-01 rounds):\n"
            + "\n".join(failures)
            + "\n\nMarkers that satisfy the check:\n"
            "  Cross-juris: 'cross-jurisdiction', 'parity', 'mirror', "
            "'TW R<N>', 'CN R<N>', 'US R<N>', 'R<N>/R<M>', 'per standing instruction'\n"
            "  Single-juris-scope: '<juris>-only', 'defer to/until', "
            "'no <juris> report', '<juris> corpus does not have', 'DR-1', "
            "'specific to <juris>'\n"
        )
        pytest.fail(msg)
