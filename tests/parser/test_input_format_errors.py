# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Actionable errors for files PatentLint cannot analyze.

Every one of these inputs used to fail with the same opaque python-docx
string (``Package not found``) or, for a non-patent XML, to succeed
silently with an empty result. Each now reports a distinct code that the
frontend maps to localized copy.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from patentlint.models import Jurisdiction
from patentlint.parser.file_format import (
    INPUT_ERROR_MESSAGES,
    UnsupportedInputError,
    detect_container,
    guard_word_bytes,
    strip_error_code,
    unsupported,
)
from patentlint.parser.xml_loader import parse_cnipa_xml
from patentlint.pipeline import analyze_bytes

FIXTURES = Path(__file__).parent.parent / "fixtures" / "cn"

OLE2_MAGIC = bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1])


def _ole2(stream_name: str) -> bytes:
    """Minimal OLE2 container advertising a named stream (UTF-16LE)."""
    return OLE2_MAGIC + b"\x00" * 512 + stream_name.encode("utf-16-le") + b"\x00" * 512


def _zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


class TestContainerDetection:
    """Format sniffing ignores the extension and reads the magic bytes."""

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            (b"", "empty"),
            (b"PK\x03\x04rest", "zip"),
            (_ole2("WordDocument"), "legacy_doc"),
            (_ole2("EncryptedPackage"), "encrypted_office"),
            (OLE2_MAGIC + b"\x00" * 64, "ole2"),
            (b"%PDF-1.7\n", "pdf"),
            (b"{\\rtf1\\ansi}", "rtf"),
            (b'<?xml version="1.0"?><a/>', "xml"),
            (b"\x01\x02\x03junk", "unknown"),
        ],
    )
    def test_detect(self, data, expected):
        assert detect_container(data) == expected

    def test_encrypted_wins_over_word_stream(self):
        """An encrypted OOXML may carry both names; unlock is the remedy."""
        data = OLE2_MAGIC + _ole2("WordDocument") + "EncryptedPackage".encode("utf-16-le")
        assert detect_container(data) == "encrypted_office"


class TestWordGuardCodes:
    """guard_word_bytes raises a distinct code per real-world mistake."""

    @pytest.mark.parametrize(
        ("data", "code"),
        [
            (_ole2("WordDocument"), "legacy_doc"),
            (_ole2("EncryptedPackage"), "encrypted_office"),
            (OLE2_MAGIC + b"\x00" * 64, "legacy_doc"),
            (b"%PDF-1.7\n", "pdf_not_docx"),
            (b"{\\rtf1\\ansi}", "rtf_not_docx"),
            (b"", "empty_file"),
            (b"\x01\x02\x03junk", "unreadable_docx"),
        ],
    )
    def test_code(self, data, code):
        with pytest.raises(UnsupportedInputError) as excinfo:
            guard_word_bytes(data)
        assert excinfo.value.code == code

    def test_zip_passes_through(self):
        """A Zip may be a real .docx, so the guard must not reject it."""
        guard_word_bytes(b"PK\x03\x04rest")

    def test_message_is_actionable_not_opaque(self):
        with pytest.raises(UnsupportedInputError) as excinfo:
            guard_word_bytes(_ole2("WordDocument"))
        message = excinfo.value.plain_message
        assert ".docx" in message
        assert "Package not found" not in message

    def test_subclasses_value_error(self):
        """CLI and API tiers catch ValueError; that must keep working."""
        with pytest.raises(ValueError):
            guard_word_bytes(b"%PDF-1.7\n")


class TestDocxPipelineCodes:
    """The codes reach callers through analyze_bytes for every .docx tier."""

    @pytest.mark.parametrize(
        "jurisdiction",
        [Jurisdiction.US, Jurisdiction.TW, Jurisdiction.EPC, Jurisdiction.CN],
    )
    def test_legacy_doc_all_jurisdictions(self, jurisdiction):
        with pytest.raises(UnsupportedInputError) as excinfo:
            analyze_bytes(_ole2("WordDocument"), "draft.docx", jurisdiction)
        assert excinfo.value.code == "legacy_doc"

    def test_pdf_renamed_to_docx(self):
        with pytest.raises(UnsupportedInputError) as excinfo:
            analyze_bytes(b"%PDF-1.7\n" + b"\x00" * 128, "draft.docx")
        assert excinfo.value.code == "pdf_not_docx"

    def test_valid_zip_that_is_not_word(self):
        """An .xlsx or Pages export renamed to .docx leaked an lxml error."""
        data = _zip({"[Content_Types].xml": b"<Types/>", "xl/workbook.xml": b"<w/>"})
        with pytest.raises(UnsupportedInputError) as excinfo:
            analyze_bytes(data, "draft.docx")
        assert excinfo.value.code == "not_word_package"


class TestCnXmlGuards:
    """CN XML and Zip inputs report a reason instead of failing silently."""

    def test_non_patent_xml_no_longer_silently_succeeds(self):
        """Regression: this returned an empty result with likely_patent=True."""
        data = b'<?xml version="1.0"?><hello><world>not a patent</world></hello>'
        with pytest.raises(UnsupportedInputError) as excinfo:
            analyze_bytes(data, "x.xml", Jurisdiction.CN)
        assert excinfo.value.code == "xml_not_patent"

    def test_malformed_xml_wrapped(self):
        """Previously leaked a raw lxml XMLSyntaxError, not a ValueError."""
        with pytest.raises(UnsupportedInputError) as excinfo:
            analyze_bytes(b'<?xml version="1.0"?><unclosed>', "x.xml", Jurisdiction.CN)
        assert excinfo.value.code == "xml_malformed"

    def test_empty_xml(self):
        with pytest.raises(UnsupportedInputError) as excinfo:
            analyze_bytes(b"", "x.xml", Jurisdiction.CN)
        assert excinfo.value.code == "empty_file"

    def test_corrupt_zip_wrapped(self):
        """Previously leaked a raw zipfile.BadZipFile, not a ValueError."""
        with pytest.raises(UnsupportedInputError) as excinfo:
            analyze_bytes(b"not a zip at all", "x.zip", Jurisdiction.CN)
        assert excinfo.value.code == "zip_corrupt"

    def test_zip_without_patent_xml(self):
        with pytest.raises(UnsupportedInputError) as excinfo:
            analyze_bytes(_zip({"readme.txt": b"no xml"}), "x.zip", Jurisdiction.CN)
        assert excinfo.value.code == "zip_no_xml"


class TestCnXmlGuardIsFnSafe:
    """The structural guard must never reject a legitimate CNIPA document.

    It gates on the full set of element paths parse_cnipa_xml reads, so it
    can only fire when the parser would have produced an empty document.
    Covers filing XML, unprefixed WIPO publication XML, and the scanned
    doc-page fallback.
    """

    @pytest.mark.parametrize(
        "name",
        [
            "cn_minimal_pass.xml",
            "cn_rich_inline.xml",
            "cn_wipo_names.xml",
            "cn_doc_page.xml",
            "parity/apparatus_method_minimal.xml",
            "parity/numbering_multidep_markush.xml",
        ],
    )
    def test_real_fixture_still_parses(self, name):
        data = (FIXTURES / name).read_bytes()
        doc = parse_cnipa_xml(data)
        assert doc is not None

    def test_claims_only_document_accepted(self):
        """A tree with claims but no description must still pass."""
        data = b'<?xml version="1.0"?><cn-application-body><cn-claims/></cn-application-body>'
        assert parse_cnipa_xml(data) is not None

    def test_abstract_only_document_accepted(self):
        data = b'<?xml version="1.0"?><application-body><abstract/></application-body>'
        assert parse_cnipa_xml(data) is not None


class TestStripErrorCode:
    """Non-browser tiers show the sentence, never the machine prefix."""

    def test_strips_prefix_from_exception(self):
        exc = unsupported("legacy_doc")
        assert strip_error_code(exc) == INPUT_ERROR_MESSAGES["legacy_doc"]
        assert "PL_ERR" not in strip_error_code(exc)

    def test_passes_through_unrelated_errors(self):
        assert strip_error_code(FileNotFoundError("File not found: x.docx")) == (
            "File not found: x.docx"
        )

    def test_passes_through_plain_string(self):
        assert strip_error_code("some other problem") == "some other problem"

    def test_cli_output_has_no_machine_prefix(self, tmp_path):
        """The CLI is a shipping tier; its copy must read like a sentence."""
        from click.testing import CliRunner

        from patentlint.cli import main

        bad = tmp_path / "legacy.docx"
        bad.write_bytes(OLE2_MAGIC + b"\x00" * 512 + "WordDocument".encode("utf-16-le"))
        result = CliRunner().invoke(main, ["analyze", str(bad)])
        assert "PL_ERR" not in result.output
        assert "legacy .doc" in result.output


class TestErrorCodeI18nParity:
    """Every code must be translatable, in every locale.

    An untranslated code silently falls back to English, which is exactly
    the leak tests/test_i18n_key_coverage.py exists to prevent.
    """

    LOCALES = ("en", "de", "zh-TW", "zh-CN", "ja", "ko")
    LOCALE_DIR = Path(__file__).parent.parent.parent / "frontend" / "src" / "i18n" / "locales"

    def _input_errors(self, locale: str) -> dict:
        import json

        with open(self.LOCALE_DIR / f"{locale}.json", encoding="utf-8") as fh:
            return json.load(fh)["error"]["input"]

    @pytest.mark.parametrize("locale", LOCALES)
    def test_locale_covers_every_code(self, locale):
        translated = self._input_errors(locale)
        missing = sorted(set(INPUT_ERROR_MESSAGES) - set(translated))
        assert not missing, f"{locale}.json missing error.input keys: {missing}"

    @pytest.mark.parametrize("locale", LOCALES)
    def test_locale_has_no_orphan_codes(self, locale):
        translated = self._input_errors(locale)
        orphan = sorted(set(translated) - set(INPUT_ERROR_MESSAGES))
        assert not orphan, f"{locale}.json has error.input keys Python never emits: {orphan}"

    def test_python_fallback_matches_en_json(self):
        """The English fallback and en.json must not drift apart."""
        en = self._input_errors("en")
        drifted = {k: (v, en[k]) for k, v in INPUT_ERROR_MESSAGES.items() if en[k] != v}
        assert not drifted, f"Python fallback differs from en.json for: {sorted(drifted)}"

    @pytest.mark.parametrize("locale", LOCALES)
    def test_no_dashes_in_copy(self, locale):
        """Repo-wide typography rule: no em dash or en dash in UI copy."""
        offenders = [
            key for key, text in self._input_errors(locale).items()
            if "—" in text or "–" in text
        ]
        assert not offenders, f"{locale}.json error.input has dash characters: {offenders}"
