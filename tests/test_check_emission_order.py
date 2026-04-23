# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Regression gates for the canonical check-emission order (ADR-149).

Drift is caught two ways:

1. **Unregistered key gate**: every message_key emitted by any pipeline
   must appear in ``CANONICAL_CHECK_ORDER`` (src/patentlint/check_order.py).
   A new check family that forgets to register fails this gate with the
   offending key named.

2. **Monotonicity gate**: within each of the four emission buckets
   (specification / claims / abstract / drawings), the sequence of
   registered keys must be non-decreasing in (CheckGroup, idx). A future
   refactor that shuffles a check into the wrong canonical group fails
   this gate loudly.

Covers all three jurisdictions (US / CN / TW) via the pass-path — the
empty-fixture emit already exercises ~30+ CheckItems per pipeline, which
is the coverage surface we care about for an ordering invariant.
"""

from __future__ import annotations

from patentlint.check_order import (
    CANONICAL_CHECK_ORDER,
    canonical_rank,
)
from patentlint.models import (
    AnalysisResult,
    CheckItem,
    CnPatentDocument,
    CnPatentType,
    Jurisdiction,
    TwPatentDocument,
    TwPatentType,
)
from patentlint.pipeline import _run_cn_pipeline, _run_tw_pipeline


def _assert_all_registered(items: list[CheckItem], jurisdiction: str, bucket_name: str) -> None:
    """Every emitted CheckItem's message_key must be in CANONICAL_CHECK_ORDER."""
    unregistered = [c.message_key for c in items if canonical_rank(c.message_key) is None]
    assert not unregistered, (
        f"{jurisdiction} {bucket_name}: unregistered message_keys emitted — "
        f"{unregistered}. Every emitted key must be registered in "
        f"src/patentlint/check_order.py (ADR-149). Either add the key to "
        f"CANONICAL_CHECK_ORDER with its canonical (bucket, group, idx), or "
        f"remove the emit site."
    )


def _assert_monotonic(items: list[CheckItem], jurisdiction: str, bucket_name: str) -> None:
    """Registered keys must emit in non-decreasing (group, idx) order."""
    last_sort_key: tuple[int, int] = (0, 0)
    last_message_key = None
    for check in items:
        rank = canonical_rank(check.message_key)
        if rank is None:
            # _assert_all_registered catches this; skip here so the two
            # assertions report independently.
            continue
        _bucket, group, idx = rank
        sort_key = (group.value, idx)
        assert sort_key >= last_sort_key, (
            f"{jurisdiction} {bucket_name} order regression: "
            f"'{check.message_key}' (group={group.value}, idx={idx}) "
            f"emitted after '{last_message_key}' "
            f"(group={last_sort_key[0]}, idx={last_sort_key[1]}). "
            f"See the canonical order in src/patentlint/check_order.py "
            f"(ADR-149)."
        )
        last_sort_key = sort_key
        last_message_key = check.message_key


class TestUsEmissionOrder:
    """US pipeline (``_to_us_report_data``) obeys the canonical order."""

    def test_us_all_buckets_clean(self):
        result = AnalysisResult(jurisdiction=Jurisdiction.US, likely_patent=True)
        report = result.to_report_data()
        for bucket_name, items in (
            ("specification_checks", report.specification_checks),
            ("claims_checks", report.claims_checks),
            ("abstract_checks", report.abstract_checks),
            ("drawings_checks", report.drawings_checks),
        ):
            _assert_all_registered(items, "US", bucket_name)
            _assert_monotonic(items, "US", bucket_name)

    def test_us_required_sections_precedes_sequence_listing(self):
        # Specific document-order invariant: required-sections (G1) must
        # precede sequence-listing (G2). Preserved from the pre-ADR-149
        # regression — gates the same invariant at a finer grain.
        result = AnalysisResult(
            jurisdiction=Jurisdiction.US,
            likely_patent=True,
            required_sections_checks=[
                CheckItem(
                    status="amend",
                    message="Missing X section.",
                    message_key="checks.required_sections_missing",
                ),
            ],
        )
        report = result.to_report_data()
        keys = [c.message_key for c in report.specification_checks]
        rs_idx = keys.index("checks.required_sections_missing")
        sl_idx = keys.index("check.spec.sequenceListing.pass")
        assert rs_idx < sl_idx, (
            f"required_sections (G1) must precede sequence_listing (G2); "
            f"keys={keys}"
        )


class TestCnEmissionOrder:
    """CN pipeline (``_run_cn_pipeline``) obeys the canonical order."""

    def test_cn_all_buckets_clean(self):
        doc = CnPatentDocument(patent_type=CnPatentType.INVENTION)
        result = _run_cn_pipeline(doc)
        for bucket_name, items in (
            ("cn_specification_checks", result.cn_specification_checks),
            ("cn_claims_checks", result.cn_claims_checks),
            ("cn_abstract_checks", result.cn_abstract_checks),
            ("cn_drawings_checks", result.cn_drawings_checks),
        ):
            _assert_all_registered(items, "CN", bucket_name)
            _assert_monotonic(items, "CN", bucket_name)


class TestTwEmissionOrder:
    """TW pipeline (``_run_tw_pipeline``) obeys the canonical order."""

    def test_tw_all_buckets_clean(self):
        doc = TwPatentDocument(patent_type=TwPatentType.INVENTION)
        result = _run_tw_pipeline(doc)
        for bucket_name, items in (
            ("tw_specification_checks", result.tw_specification_checks),
            ("tw_claims_checks", result.tw_claims_checks),
            ("tw_abstract_checks", result.tw_abstract_checks),
            ("tw_drawings_checks", result.tw_drawings_checks),
        ):
            _assert_all_registered(items, "TW", bucket_name)
            _assert_monotonic(items, "TW", bucket_name)


class TestCanonicalConstantInternalConsistency:
    """Sanity gates on the canonical constant itself."""

    def test_every_entry_has_correct_shape(self):
        # Defensive: catches a typo'd entry that accidentally inserts
        # wrong-shaped tuple (e.g., missing the idx).
        for key, value in CANONICAL_CHECK_ORDER.items():
            assert (
                isinstance(value, tuple) and len(value) == 3
            ), f"Bad entry for {key!r}: expected (bucket, group, idx), got {value!r}"

    def test_idx_values_are_non_negative(self):
        for key, (_bucket, _group, idx) in CANONICAL_CHECK_ORDER.items():
            assert idx >= 0, f"{key!r}: idx must be non-negative, got {idx}"
