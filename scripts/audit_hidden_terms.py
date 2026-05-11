# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Audit CheckItem emit sites for params-template mismatch.

Walks every Python file in src/patentlint/analysis and src/patentlint/models.py,
extracts every CheckItem(...) construction via AST, reads the referenced
i18n template from frontend/src/i18n/locales/en.json, and flags mismatches:

  - params_not_rendered : details_params supplies a key the template does not use
  - template_missing_key: template references a {{placeholder}} no emit site provides

This is a diagnostic tool for Part A of Phase 10 (surface hidden detected terms).
Exit code is non-zero if any mismatches are found, so it can gate CI if wired up.

Usage:
  python3 scripts/audit_hidden_terms.py
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = ROOT / "src" / "patentlint" / "analysis"
MODELS_PY = ROOT / "src" / "patentlint" / "models.py"
EN_LOCALE = ROOT / "frontend" / "src" / "i18n" / "locales" / "en.json"

PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

# Keys recognized by frontend/src/lib/detailsFormatter.js's STRUCTURED_FORMATTERS
# registry. These are pre-rendered before t() interpolation, so they satisfy a
# same-named {{placeholder}} in the template via the formatter output — not as
# a raw value. Treat their presence as "rendered" during the audit.
STRUCTURED_FORMATTER_KEYS = {
    "numerals_with_locations",
    "figures_with_locations",
    "paragraph_list",
    "figure_list",
    "claim_list",
    "paragraph_list_simple",
    "numeral_list",
    "claims",
    "paragraphs",
    "figures",
    "sample_names",
    "figure_ref_inconsistency",
    "symbol_table_inconsistency",
    "symbol_mismatch_triples",
    "title_prohibited_items",
    "paragraph_format_violations",
    # Part B forward-looking keys — structured flagged-term payloads emitted
    # now, rendered as chips by the FlaggedTermList component once Part B
    # lands.
    "flagged_phrases",
}


def _load_locale(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _resolve_key(locale: dict, dotted: str):
    node = locale
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _placeholders_in(template) -> set[str]:
    if isinstance(template, str):
        return set(PLACEHOLDER_RE.findall(template))
    if isinstance(template, dict):
        found: set[str] = set()
        for v in template.values():
            found |= _placeholders_in(v)
        return found
    return set()


def _extract_checkitem_emits(src: str, path: Path):
    """Yield (lineno, message_key, details_key, params_keys) tuples."""
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name != "CheckItem":
            continue

        message_key = None
        details_key = None
        params_keys: set[str] = set()

        for kw in node.keywords:
            if kw.arg == "message_key" and isinstance(kw.value, ast.Constant):
                message_key = kw.value.value
            elif kw.arg == "details_key" and isinstance(kw.value, ast.Constant):
                details_key = kw.value.value
            elif kw.arg == "details_params":
                params_keys = _collect_dict_keys(kw.value)

        yield (node.lineno, message_key, details_key, params_keys)


def _collect_dict_keys(value_node: ast.AST) -> set[str]:
    """Extract literal string keys from a dict or dict-expression AST node."""
    if isinstance(value_node, ast.Dict):
        keys: set[str] = set()
        for k in value_node.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                keys.add(k.value)
        return keys
    if isinstance(value_node, ast.IfExp):
        # `{...} if cond else None` — pull from the truthy branch.
        return _collect_dict_keys(value_node.body)
    return set()


def main() -> int:
    locale = _load_locale(EN_LOCALE)

    targets: list[Path] = [MODELS_PY, *sorted(ANALYSIS_DIR.glob("*.py"))]

    mismatches: list[tuple[str, int, str, str, set[str], set[str]]] = []
    checked = 0

    for path in targets:
        src = path.read_text()
        for lineno, message_key, details_key, params_keys in _extract_checkitem_emits(src, path):
            checked += 1
            if not details_key:
                continue
            template = _resolve_key(locale, details_key)
            if template is None:
                mismatches.append((
                    str(path.relative_to(ROOT)),
                    lineno,
                    message_key or "?",
                    details_key,
                    params_keys,
                    {"<missing locale template>"},
                ))
                continue
            placeholders = _placeholders_in(template)
            # Structured-formatter keys are pre-rendered by detailsFormatter.js
            # before t() is called, so a same-named {{placeholder}} in the
            # template is satisfied by the formatter output. Also treat the
            # registry keys as "always OK" when the template simply doesn't
            # render them — they're intentional forward-looking payloads for
            # Part B's chip rendering.
            not_rendered = (params_keys - placeholders) - STRUCTURED_FORMATTER_KEYS
            missing_from_params = placeholders - params_keys - STRUCTURED_FORMATTER_KEYS
            if not_rendered or missing_from_params:
                mismatches.append((
                    str(path.relative_to(ROOT)),
                    lineno,
                    message_key or "?",
                    details_key,
                    not_rendered,
                    missing_from_params,
                ))

    print(f"Audited {checked} CheckItem emit sites against en.json.\n")

    if not mismatches:
        print("No mismatches found. Every details_params key is rendered and every")
        print("template placeholder has a matching param.")
        return 0

    print(f"{len(mismatches)} mismatch(es):\n")
    print("| file | line | message_key | details_key | params_not_rendered | template_missing_keys |")
    print("|---|---|---|---|---|---|")
    for file_, lineno, mkey, dkey, not_rendered, missing in mismatches:
        nr = ", ".join(sorted(not_rendered)) or "—"
        mk = ", ".join(sorted(missing)) or "—"
        print(f"| {file_} | {lineno} | {mkey} | {dkey} | {nr} | {mk} |")

    return 1


if __name__ == "__main__":
    sys.exit(main())
