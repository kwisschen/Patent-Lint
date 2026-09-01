# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""Every non-scalar details_params field that a template interpolates by name
must have a formatter registered in detailsFormatter.js.

`check.spec.scopeLimitWording` emitted `samples=[{phrase, context}, ...]` while
`details.scopeLimitWording` interpolated `{{samples}}`. i18next stringifies an
object instead of warning, so the check shipped reading

    "1 restrictive-wording occurrence(s) detected. Examples: [object Object]"

to users, in all six locales, for as long as the check existed. The mechanism
built for exactly this (`detailsFormatter.js`) already existed - the check was
never wired into it, and no gate could see the difference.

The types are taken from a REAL PIPELINE RUN rather than inferred from the
source. A first version of this test guessed at shapes with a name heuristic
and immediately mis-flagged integers like `total_groups`; running the analysis
and reading what is actually emitted is the only honest way to know.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FORMATTER_JS = REPO / "frontend/src/lib/detailsFormatter.js"
EN_JSON = REPO / "frontend/src/i18n/locales/en.json"

FIXTURES = [
    ("US", REPO / "tests/fixtures/TestSpec1.docx"),
    ("US", REPO / "tests/fixtures/TestSpec5.docx"),
    ("US", REPO / "tests/fixtures/TestSpec9.docx"),
    ("TW", REPO / "tests/fixtures/tw/invention_complete.docx"),
    ("TW", REPO / "tests/fixtures/tw/symbol_table_variants.docx"),
    ("CN", REPO / "tests/fixtures/cn/WORD转XML编辑器五书模板文件.docx"),
]


def _registered_fields() -> set[str]:
    js = FORMATTER_JS.read_text(encoding="utf-8")
    block = re.search(r"const STRUCTURED_FORMATTERS = \{(.*?)\n\}", js, re.S)
    assert block, "STRUCTURED_FORMATTERS registry not found"
    return set(re.findall(r"^\s*([A-Za-z_][\w]*)\s*:", block.group(1), re.M))


def _template_placeholders() -> dict[str, set[str]]:
    flat: dict[str, str] = {}

    def walk(node, prefix=""):
        for k, v in node.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                walk(v, key)
            elif isinstance(v, str):
                flat[key] = v

    walk(json.loads(EN_JSON.read_text(encoding="utf-8")))
    return {k: set(re.findall(r"\{\{(\w+)\}\}", v)) for k, v in flat.items()}


def _emitted_check_items(jurisdiction: str, path: Path) -> list[dict]:
    from patentlint.pipeline import analyze_file

    result = analyze_file(str(path), jurisdiction=jurisdiction)
    items: list[dict] = []

    def collect(node):
        if isinstance(node, dict):
            if "details_key" in node or "message_key" in node:
                items.append(node)
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for v in node:
                collect(v)

    collect(result.model_dump())
    return items


def test_no_interpolated_field_stringifies_to_object_object() -> None:
    registered = _registered_fields()
    placeholders = _template_placeholders()
    offenders: set[str] = set()

    for jurisdiction, path in FIXTURES:
        if not path.exists():
            pytest.skip(f"fixture missing: {path}")
        for item in _emitted_check_items(jurisdiction, path):
            key = item.get("details_key")
            params = item.get("details_params") or {}
            if not key:
                continue
            for field, value in params.items():
                if not isinstance(value, (list, dict)):
                    continue
                if field not in placeholders.get(key, set()):
                    continue  # not interpolated by name - nothing to stringify
                if field not in registered:
                    offenders.add(f"{key} interpolates {{{{{field}}}}} ({type(value).__name__})")

    assert not offenders, (
        "These fields reach a locale template as a list/dict with no formatter, "
        "so i18next renders them as [object Object] with no warning:\n  "
        + "\n  ".join(sorted(offenders))
    )


def test_the_scope_limit_wording_regression_specifically() -> None:
    """Pin the exact case that shipped broken."""
    assert "samples" in _registered_fields()
    assert "samples" in _template_placeholders()["details.scopeLimitWording"]


def test_array_fields_all_have_formatters() -> None:
    """A field in ARRAY_FORMATTER_FIELDS with no formatter would silently take
    the object-shaped branch and never run against the list it was added for."""
    js = FORMATTER_JS.read_text(encoding="utf-8")
    arr = re.search(r"const ARRAY_FORMATTER_FIELDS = new Set\(\[(.*?)\]\)", js, re.S)
    assert arr
    assert set(re.findall(r'"(\w+)"', arr.group(1))) <= _registered_fields()
