# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Pytest gate for the real-drafter audit harness.

Wraps ``tests/eval/real_drafter_audit.py``'s fixture set as a parametrized
pytest test so a CI break catches regressions immediately. Each fixture
spec asserts:

  - silenced_keys: zero amend/verify findings for the bug-class trigger
  - expected_keys: at least one finding (any status) so we catch
    over-silencing where the silencer accidentally crushes legitimate
    emits

The fixtures are programmatic .docx files built from python-docx; no
binary fixtures are committed.
"""

from __future__ import annotations

import pytest

from tests.eval.real_drafter_audit import FIXTURES, FixtureSpec, run_fixture


@pytest.mark.parametrize("spec", FIXTURES, ids=lambda s: s.name)
def test_real_drafter_fixture_silencer(spec: FixtureSpec) -> None:
    """Each fixture's silencer must hold (zero amend/verify on bug class)."""
    result = run_fixture(spec)
    if result.silenced_violations:
        violation_keys = [
            f"{c.message_key} -> {c.message[:80]}"
            for c in result.silenced_violations
        ]
        pytest.fail(
            f"Silencer regression on `{spec.name}` ({spec.fix_round} "
            f"{spec.fix_sha}): {len(result.silenced_violations)} amend/verify "
            f"finding(s) on silenced_keys.\n  "
            + "\n  ".join(violation_keys)
        )


@pytest.mark.parametrize("spec", FIXTURES, ids=lambda s: s.name)
def test_real_drafter_fixture_expected_emits(spec: FixtureSpec) -> None:
    """Each fixture's expected_keys must each emit ≥1 finding (recall guard)."""
    result = run_fixture(spec)
    missing = [k for k, count in result.expected_hits.items() if count < 1]
    if missing:
        pytest.fail(
            f"Over-silencing on `{spec.name}` ({spec.fix_round} "
            f"{spec.fix_sha}): expected check_keys missing emits — "
            + ", ".join(missing)
        )
