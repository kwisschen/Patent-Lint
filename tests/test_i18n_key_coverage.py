# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""i18n key coverage CI gate.

Catches the bug class where Python emits a message_key / details_key
that doesn't exist in `frontend/src/i18n/locales/en.json` — the frontend
then silently falls back to the English `message=` / `details=` field
baked into Python source, leaking English UI into localized renderings.

Surfaced on 2026-05-12 when a TW-locale user spotted `check.epc.spec.
numeralConsistency.*` keys missing (3 keys) plus 8 missing `details.*`
keys. After the fix, this test prevents future regressions.

Covers:
  - Literal `message_key="..."` and `details_key="..."` strings.
  - Runtime-rekeyed keys (when Python does `message_key.replace(...)`
    to map US helper output into another jurisdiction's namespace);
    these are catalogued in RUNTIME_REKEYS below — keep this catalog
    in sync when adding new rekey logic.
  - F-string-suffix keys (`f"check.spec.X.{suffix}"`); the per-key
    suffix list F_SUFFIX_KEYS below enumerates known patterns.

If you add a Python emit site whose key isn't in en.json, this test
fails CI with a specific list of missing keys. Add the localized
strings to ALL six locales before merging.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
ANALYSIS_DIR = REPO / "src" / "patentlint" / "analysis"
PARSER_DIR = REPO / "src" / "patentlint" / "parser"
EN_JSON = REPO / "frontend" / "src" / "i18n" / "locales" / "en.json"

# Map of (source_key_substring → target_key) for runtime rekeying.
# When epc_specification.py does
# `message_key.replace("check.spec.numeralConsistency", "check.epc.spec.numeralConsistency")`,
# the predicted runtime key is the target. Audit this list whenever new
# `.replace(` calls land in the analysis layer.
RUNTIME_REKEYS = {
    "check.spec.numeralConsistency": "check.epc.spec.numeralConsistency",
    # Figure-xref rekeys (epc_specification.py:431 _XREF_KEY_MAP):
    "checks.figure_xref_orphaned_brief": "check.epc.spec.figureRefConsistency.orphanedBrief.amend",
    "checks.figure_xref_orphaned_detailed": "check.epc.spec.figureRefConsistency.orphanedDetailed.amend",
    "checks.figure_xref_pass": "check.epc.spec.figureRefConsistency.pass",
    # Same details_key rekey from epc_specification.py:436 _XREF_DETAILS_KEY_MAP:
    "details.orphanedBriefFigures": "details.epc.orphanedBriefFigures",
    "details.orphanedDetailedFigures": "details.epc.orphanedDetailedFigures",
}

# F-string suffix patterns. Each entry: prefix → list of valid suffixes.
# When Python writes `message_key=f"check.spec.numeralConsistency.{suffix}"`
# where `suffix` is one of {amend, verify, pass}, the test predicts each
# full key. Add to this list when new f-string keys land.
F_SUFFIX_KEYS = {
    "check.spec.numeralConsistency": ["amend", "verify", "pass"],
    "check.cn.spec.numeralConsistency": ["amend", "verify", "pass"],
    "check.tw.spec.numeralConsistency": ["amend", "verify", "pass"],
    "check.epc.spec.numeralConsistency": ["amend", "verify", "pass"],
}


def _walk_leaves(d, prefix=""):
    """Yield every leaf path in a nested dict."""
    if isinstance(d, dict):
        for k, v in d.items():
            yield from _walk_leaves(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(d, str):
        yield prefix


def _collect_python_emits():
    """Walk Python sources and collect every literal message_key/details_key."""
    msg_keys = set()
    det_keys = set()
    msg_literal_re = re.compile(r'message_key=["\']([^"\']+)["\']')
    det_literal_re = re.compile(r'details_key=["\']([^"\']+)["\']')
    for src in [*ANALYSIS_DIR.rglob("*.py"), *PARSER_DIR.rglob("*.py")]:
        text = src.read_text()
        for m in msg_literal_re.finditer(text):
            msg_keys.add(m.group(1))
        for m in det_literal_re.finditer(text):
            det_keys.add(m.group(1))
    # Expand runtime rekeys
    for src_sub, dst in RUNTIME_REKEYS.items():
        for k in list(msg_keys):
            if k.startswith(src_sub):
                msg_keys.add(k.replace(src_sub, dst))
        for k in list(det_keys):
            if k == src_sub:
                det_keys.add(dst)
    # Expand f-string suffix keys
    for prefix, suffixes in F_SUFFIX_KEYS.items():
        for s in suffixes:
            msg_keys.add(f"{prefix}.{s}")
    return msg_keys, det_keys


def test_every_python_emitted_key_exists_in_en_json():
    """No Python message_key / details_key may be missing from en.json."""
    msg_keys, det_keys = _collect_python_emits()
    en = json.loads(EN_JSON.read_text())
    en_paths = set(_walk_leaves(en))

    missing_msg = sorted(k for k in msg_keys if k not in en_paths)
    missing_det = sorted(k for k in det_keys if k not in en_paths)

    failures = []
    if missing_msg:
        failures.append(
            f"\n{len(missing_msg)} message_key(s) emitted by Python but missing from en.json:\n"
            + "\n".join(f"  ✗ {k}" for k in missing_msg)
            + "\n\nFix: add a localized string for each missing key in all 6 locale files."
        )
    if missing_det:
        failures.append(
            f"\n{len(missing_det)} details_key(s) emitted by Python but missing from en.json:\n"
            + "\n".join(f"  ✗ {k}" for k in missing_det)
            + "\n\nFix: add a localized template for each missing key in all 6 locale files."
        )
    if failures:
        pytest.fail("\n".join(failures))


def test_all_locales_have_the_same_keys_as_en():
    """All 6 locales must mirror en.json's key structure exactly.

    Cross-locale parity is the gate that prevents zh-TW (or any non-EN
    locale) from missing keys that en.json has. If en.json is the single
    source of truth, drift in non-en locales causes English fallback in
    that locale only — same English-leak bug class.
    """
    locales_dir = EN_JSON.parent
    en = json.loads(EN_JSON.read_text())
    en_paths = set(_walk_leaves(en))

    failures = []
    for locale_file in sorted(locales_dir.glob("*.json")):
        if locale_file.name == "en.json":
            continue
        data = json.loads(locale_file.read_text())
        locale_paths = set(_walk_leaves(data))
        missing = sorted(en_paths - locale_paths)
        if missing:
            failures.append(
                f"\n{locale_file.name}: {len(missing)} key(s) present in en.json but missing locally:\n"
                + "\n".join(f"  ✗ {k}" for k in missing[:15])
                + (f"\n  ... and {len(missing) - 15} more" if len(missing) > 15 else "")
            )
    if failures:
        pytest.fail("\n".join(failures))
