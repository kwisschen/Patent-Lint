# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""TW 專利法 §26 paragraph pins, verified against the primary source.

全國法規資料庫, 專利法 第26條 (current text):
  第1項  說明書應明確且充分揭露 ... (enablement)
  第2項  申請專利範圍 ... 各請求項應以明確、簡潔之方式記載，且必須為說明書所支持。
  第3項  摘要應敘明所揭露發明內容之概要 ... (the abstract)
  第4項  揭露方式，於本法施行細則定之。

Claim clarity (antecedent basis, omnibus claims) and specification support are
both §26 第2項. For months every shipped surface cited 第3項, the ABSTRACT
paragraph, in 21 files including the reference line printed on every TW
report. This gate keeps it from coming back.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRONG = re.compile(r"26\s*第\s*3\s*項|§ 26\(3\)")


def _shipped_files():
    yield from (ROOT / "src/patentlint").rglob("*.py")
    yield from (ROOT / "frontend/src/i18n/locales").glob("*.json")
    yield from (ROOT / "frontend/src").rglob("*.js")
    yield from (ROOT / "frontend/src").rglob("*.jsx")
    yield ROOT / "README.md"
    yield ROOT / "CHECKS.md"


def test_no_shipped_surface_cites_the_abstract_paragraph_for_claims():
    offenders = [
        str(p.relative_to(ROOT))
        for p in _shipped_files()
        if WRONG.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_the_spec_support_check_cites_paragraph_2():
    """Non-vacuity: the scan must be looking where the pin actually lives."""
    text = (ROOT / "src/patentlint/pipeline.py").read_text(encoding="utf-8")
    assert 'reference="專利法 §26 第2項"' in text
