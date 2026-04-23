# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""i18n helper — loads frontend locale JSON and provides translation.

Single source of truth is ``frontend/src/i18n/locales/*.json``. In a
built wheel, these files ship at ``patentlint/_locales/`` via hatchling
force-include (see ``pyproject.toml``). In an editable / source
checkout, the helper loads them directly from the frontend tree.

The translation surface mirrors i18next's primitives used by the
frontend so Python-rendered copy (weasyprint PDFs, CLI output) matches
what a user would see in React. Specifically:

  * Dotted-key lookup through nested dicts.
  * ``{{var}}`` interpolation (no expressions, no nesting).
  * Locale fallback: requested → ``en`` → raw key.

Non-goals: i18next's plural-suffix machinery (``_one`` / ``_other``).
PatentLint's locale files use inline ``{{count}}`` singular/plural
constructs instead, so this helper stays minimal.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

_SUPPORTED_LOCALES: tuple[str, ...] = ("en", "de", "zh-TW", "zh-CN", "ja", "ko")
_DEFAULT_LOCALE: str = "en"

# ``{{var}}`` interpolation. Identifiers only — no expressions, no
# nesting. Whitespace inside the braces is tolerated.
_INTERPOLATION_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def _locale_dir() -> Path:
    """Resolve the directory containing locale JSON files.

    Order:
    1. ``patentlint/_locales/`` — wheel location (populated by hatchling
       force-include at build time).
    2. ``<repo>/frontend/src/i18n/locales/`` — dev-tree source of truth.
    """
    packaged = Path(__file__).parent / "_locales"
    if packaged.is_dir():
        return packaged
    repo_root = Path(__file__).resolve().parent.parent.parent
    dev_path = repo_root / "frontend" / "src" / "i18n" / "locales"
    if dev_path.is_dir():
        return dev_path
    raise FileNotFoundError(
        "Locale directory not found. Searched: "
        f"{packaged} (wheel) and {dev_path} (dev-tree)"
    )


@lru_cache(maxsize=len(_SUPPORTED_LOCALES) + 1)
def load_locale(locale: str) -> dict:
    """Load a locale's JSON bundle. Cached by locale string.

    Unknown locale codes silently fall back to the default locale so
    callers never see a missing-file error for a code like ``"fr"``
    that PatentLint doesn't translate into.
    """
    if locale not in _SUPPORTED_LOCALES:
        locale = _DEFAULT_LOCALE
    path = _locale_dir() / f"{locale}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _resolve(bundle: dict, key: str) -> Any:
    """Resolve a dotted key path through a nested dict.

    Returns ``None`` if any segment is missing or if the path bottoms
    out at a non-string value. The caller decides what to do with a
    ``None`` — typically fall back to ``en`` then to the raw key.
    """
    cur: Any = bundle
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _interpolate(template: str, params: dict[str, Any]) -> str:
    """Apply i18next-style ``{{var}}`` interpolation.

    Unknown placeholders are left intact (matches i18next's default
    behavior). ``None`` values render as empty strings to avoid the
    literal ``"None"`` leaking into user-facing copy.
    """

    def replace(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in params:
            value = params[var_name]
            return "" if value is None else str(value)
        return match.group(0)

    return _INTERPOLATION_RE.sub(replace, template)


def translate(key: str, locale: str = _DEFAULT_LOCALE, /, **params: Any) -> str:
    """Look up ``key`` in ``locale`` bundle, interpolate ``params``, return.

    Fallback chain:
      1. Requested locale.
      2. ``en`` (default locale).
      3. Raw key — visible-on-missing is deliberate so translation gaps
         surface in QA instead of rendering as empty strings.
    """
    bundle = load_locale(locale)
    value = _resolve(bundle, key)
    if value is None and locale != _DEFAULT_LOCALE:
        value = _resolve(load_locale(_DEFAULT_LOCALE), key)
    if not isinstance(value, str):
        return key
    return _interpolate(value, params)


def get_translator(locale: str = _DEFAULT_LOCALE) -> Callable[..., str]:
    """Return a pre-bound translator callable for ``locale``.

    Convenient for Jinja contexts::

        env.globals["t"] = get_translator(locale)

    Inside templates::

        {{ t('pdf.header') }}
        {{ t('details.claimsOverview', independent=2, dependent=5, total=7) }}
    """

    def t(key: str, **params: Any) -> str:
        return translate(key, locale, **params)

    return t


def is_supported(locale: str) -> bool:
    return locale in _SUPPORTED_LOCALES


def supported_locales() -> tuple[str, ...]:
    return _SUPPORTED_LOCALES


def normalize_locale(locale: str | None) -> str:
    """Normalize a locale code to one we support, or return the default.

    Rules:
      * ``None`` / empty → default.
      * Exact match to a supported locale → as-is.
      * Case-insensitive match (e.g., ``"ZH-tw"``) → canonical form.
      * BCP-47 variants (``"zh-Hant-TW"`` / ``"zh-hans"``) → closest
        supported locale by script/region heuristics.
      * Anything else → default.
    """
    if not locale:
        return _DEFAULT_LOCALE

    lower = locale.lower()

    for supported in _SUPPORTED_LOCALES:
        if supported.lower() == lower:
            return supported

    # Heuristic BCP-47 mapping. Covers the common browser Accept-Language
    # variants without pulling babel as a dependency.
    if lower.startswith("zh"):
        if "hant" in lower or "tw" in lower or "hk" in lower or "mo" in lower:
            return "zh-TW"
        if "hans" in lower or "cn" in lower or "sg" in lower:
            return "zh-CN"
        return "zh-CN"
    if lower.startswith("de"):
        return "de"
    if lower.startswith("ja"):
        return "ja"
    if lower.startswith("ko"):
        return "ko"
    if lower.startswith("en"):
        return "en"
    return _DEFAULT_LOCALE
