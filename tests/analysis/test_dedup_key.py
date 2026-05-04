# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for `make_document_dedup_key` (Phase 4 walker-side per-document dedup)."""

from patentlint.analysis.utils import make_document_dedup_key


class TestDedupKeyShape:
    def test_basic(self):
        assert make_document_dedup_key("widget", "the widget") == "widget|the widget"

    def test_casefold(self):
        # `Said widget` and `said widget` collapse to the same key.
        a = make_document_dedup_key("Widget", "Said widget")
        b = make_document_dedup_key("widget", "said widget")
        assert a == b

    def test_whitespace_collapse(self):
        a = make_document_dedup_key("widget", "the  widget")
        b = make_document_dedup_key("widget", "the widget")
        assert a == b

    def test_cjk(self):
        assert (
            make_document_dedup_key("控制器", "所述控制器")
            == "控制器|所述控制器"
        )

    def test_distinct_terms_distinct_keys(self):
        a = make_document_dedup_key("widget", "the widget")
        b = make_document_dedup_key("device", "the device")
        assert a != b

    def test_distinct_reference_forms_distinct_keys(self):
        # `the X` vs `said X` are different drafting styles; keep them
        # distinct so the dedup pool can surface stylistic-drift signal.
        a = make_document_dedup_key("widget", "the widget")
        b = make_document_dedup_key("widget", "said widget")
        assert a != b

    def test_empty_inputs(self):
        # Defensive: empty inputs should not crash; return a stable
        # sentinel `|` shape.
        assert make_document_dedup_key("", "") == "|"
