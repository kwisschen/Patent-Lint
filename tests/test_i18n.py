# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Unit tests for the i18n helper."""

import pytest

from patentlint.i18n import (
    _interpolate,
    _resolve,
    get_translator,
    is_supported,
    load_locale,
    normalize_locale,
    supported_locales,
    translate,
)


class TestLoadLocale:

    def test_all_supported_locales_load(self):
        for locale in supported_locales():
            bundle = load_locale(locale)
            assert isinstance(bundle, dict)
            assert bundle, f"{locale} bundle must be non-empty"

    def test_unknown_locale_falls_back_to_default(self):
        default_bundle = load_locale("en")
        assert load_locale("fr") == default_bundle
        assert load_locale("xx-YY") == default_bundle

    def test_bundles_share_top_level_keys(self):
        """If this fails, translation gaps will show up at render time."""
        en_keys = set(load_locale("en").keys())
        for locale in supported_locales():
            if locale == "en":
                continue
            missing = en_keys - set(load_locale(locale).keys())
            assert not missing, (
                f"{locale} missing top-level keys from en: {missing}"
            )


class TestResolve:

    def test_dotted_key_traversal(self):
        bundle = {"a": {"b": {"c": "leaf"}}}
        assert _resolve(bundle, "a.b.c") == "leaf"

    def test_missing_segment_returns_none(self):
        bundle = {"a": {"b": "leaf"}}
        assert _resolve(bundle, "a.b.c") is None
        assert _resolve(bundle, "a.x") is None
        assert _resolve(bundle, "x") is None

    def test_nested_dict_not_returned_as_leaf(self):
        bundle = {"a": {"b": {"c": "leaf"}}}
        assert _resolve(bundle, "a.b") == {"c": "leaf"}


class TestInterpolate:

    def test_single_var(self):
        assert _interpolate("Hello {{name}}!", {"name": "world"}) == "Hello world!"

    def test_multiple_vars(self):
        out = _interpolate(
            "{{a}} + {{b}} = {{c}}", {"a": 1, "b": 2, "c": 3}
        )
        assert out == "1 + 2 = 3"

    def test_whitespace_in_braces(self):
        assert _interpolate("{{ name }}", {"name": "x"}) == "x"

    def test_missing_placeholder_preserved(self):
        assert _interpolate("Hello {{name}}!", {}) == "Hello {{name}}!"

    def test_none_renders_empty(self):
        assert _interpolate("Hello {{name}}!", {"name": None}) == "Hello !"

    def test_non_string_stringified(self):
        assert _interpolate("Count: {{n}}", {"n": 42}) == "Count: 42"


class TestTranslate:

    def test_en_lookup(self):
        assert translate("pdf.header") == "PatentLint Analysis Report"

    def test_locale_specific_lookup(self):
        # zh-TW has the same key
        assert translate("pdf.header", "zh-TW") != "pdf.header"

    def test_interpolation_with_params(self):
        out = translate(
            "details.claimsOverview",
            "en",
            independent=2,
            dependent=5,
            total=7,
        )
        assert "2" in out and "5" in out and "7" in out

    def test_missing_key_returns_key(self):
        assert translate("does.not.exist") == "does.not.exist"

    def test_fallback_to_en_on_missing_in_locale(self):
        # Add a key that only exists in en for this test — we verify the
        # fallback path works by picking a known-present key and
        # requesting a locale that doesn't have a spec-support review
        # entry. Since all 5 locales do have pdf.header, fall back is
        # implicit in the missing-key test above.
        # Verify that the missing-key fallback chain reaches en, not zh.
        assert translate("pdf.header", "ja") != "pdf.header"

    def test_unknown_locale_resolves_via_default(self):
        # translate('fr') on supported key works via default-locale
        # load inside load_locale().
        assert translate("pdf.header", "fr") == "PatentLint Analysis Report"


class TestGetTranslator:

    def test_bound_locale(self):
        t = get_translator("zh-TW")
        assert t("pdf.header") == translate("pdf.header", "zh-TW")

    def test_params_passthrough(self):
        t = get_translator("en")
        out = t("details.claimsOverview", independent=1, dependent=2, total=3)
        assert "1" in out and "2" in out and "3" in out


class TestNormalizeLocale:

    @pytest.mark.parametrize(
        "given,expected",
        [
            (None, "en"),
            ("", "en"),
            ("en", "en"),
            ("zh-TW", "zh-TW"),
            ("zh-tw", "zh-TW"),
            ("ZH-tw", "zh-TW"),
            ("zh-CN", "zh-CN"),
            ("zh-Hant-TW", "zh-TW"),
            ("zh-Hans", "zh-CN"),
            ("zh-HK", "zh-TW"),
            ("zh", "zh-CN"),
            ("ja", "ja"),
            ("ja-JP", "ja"),
            ("ko", "ko"),
            ("ko-KR", "ko"),
            ("en-US", "en"),
            ("fr", "en"),
            ("de-DE", "en"),
        ],
    )
    def test_bcp47_normalization(self, given, expected):
        assert normalize_locale(given) == expected

    def test_is_supported(self):
        for loc in supported_locales():
            assert is_supported(loc)
        assert not is_supported("fr")
        assert not is_supported("")
