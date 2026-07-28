# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Container-format sniffing for uploaded files.

PatentLint accepts a narrow set of formats per jurisdiction (see
``pipeline.analyze_bytes``). Anything else used to fail deep inside
python-docx or lxml with an opaque message such as ``Package not found``,
which told the user nothing about what to do next. Worse, five distinct
real-world mistakes (a legacy ``.doc``, a password-protected file, a PDF
renamed to ``.docx``, an RTF, an empty file) all collapsed onto that one
string.

This module sniffs the container up front and raises
:class:`UnsupportedInputError` carrying a stable machine-readable code.
The exception's string form is ``PL_ERR:<code>|<english fallback>`` so
that:

* the CLI, Docker, and API tiers still print a readable English sentence;
* the browser tier can regex the code out of the Pyodide traceback and
  render localized copy (see ``frontend/src/lib/analysisError.js``).

Keep the code strings in sync with the ``error.input.*`` i18n keys.
"""

from __future__ import annotations

ERROR_PREFIX = "PL_ERR:"

# Container magic numbers.
_ZIP_MAGIC = b"PK\x03\x04"
_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_PDF_MAGIC = b"%PDF"
_RTF_MAGIC = b"{\\rtf"

# OLE2 (compound file) directory entries store stream names as UTF-16LE.
# A legacy Word binary carries a "WordDocument" stream; an encrypted OOXML
# file is also an OLE2 container but carries "EncryptedPackage" instead.
# Sniffing for the stream name separates the two without a full CFB parser,
# which matters because they need opposite remedies (re-save vs unlock).
_OLE2_WORD_STREAM = "WordDocument".encode("utf-16-le")
_OLE2_ENCRYPTED_STREAM = "EncryptedPackage".encode("utf-16-le")


class UnsupportedInputError(ValueError):
    """An uploaded file cannot be analyzed, with an actionable reason.

    Subclasses ``ValueError`` so existing ``except ValueError`` handlers in
    the CLI and API keep working unchanged.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.plain_message = message
        super().__init__(f"{ERROR_PREFIX}{code}|{message}")


# English fallbacks. Shown verbatim by the CLI, Docker, and API tiers, and
# used as the last-resort string if the browser sees a code it cannot
# translate. Kept identical to the error.input.* values in en.json; the
# parity is enforced by tests/parser/test_input_format_errors.py.
INPUT_ERROR_MESSAGES: dict[str, str] = {
    "legacy_doc": (
        "This looks like a legacy .doc file. Open it in Word and re-save it "
        "as .docx, then upload it again."
    ),
    "encrypted_office": (
        "This file is password protected, so its text cannot be read. Remove "
        "the password in Word and upload it again."
    ),
    "pdf_not_docx": (
        "This is a PDF, not a Word file. PatentLint checks the .docx draft "
        "you write in Word, before it is converted for filing."
    ),
    "rtf_not_docx": (
        "This looks like an RTF file. Open it in Word and re-save it as "
        ".docx, then upload it again."
    ),
    "empty_file": "This file is empty. Check that the upload finished, then try again.",
    "not_word_package": (
        "This is an Office or Zip file, but not a Word document. Check that "
        "you uploaded the .docx specification."
    ),
    "unreadable_docx": (
        "This file could not be read as a .docx document. It may be corrupted. "
        "Try opening it in Word and re-saving it."
    ),
    "xml_not_patent": (
        "This XML file is not a CNIPA patent document. Export the filing XML "
        "from the CNIPA editor and upload that instead."
    ),
    "xml_malformed": (
        "This XML file could not be parsed. It may be incomplete or corrupted."
    ),
    "zip_no_xml": (
        "No CNIPA patent XML was found in this Zip package. Upload the Zip "
        "produced by the CNIPA editor, or the .xml file directly."
    ),
    "zip_corrupt": "This Zip file could not be opened. It may be corrupted.",
}


def unsupported(code: str) -> UnsupportedInputError:
    """Build an :class:`UnsupportedInputError` for a known code.

    Returned rather than raised so callers can chain the underlying cause
    with ``raise unsupported(code) from exc``.
    """
    return UnsupportedInputError(code, INPUT_ERROR_MESSAGES[code])


def raise_unsupported(code: str) -> None:
    """Raise :class:`UnsupportedInputError` for a known code."""
    raise unsupported(code)


def strip_error_code(value: object) -> str:
    """Render an error for a human, without the machine-readable prefix.

    The ``PL_ERR:<code>|`` prefix exists so the browser can localize the
    message. Every other tier (CLI, Docker, API) wants the sentence only.
    Non-PatentLint errors pass through unchanged.
    """
    text = str(value)
    if not text.startswith(ERROR_PREFIX):
        return text
    _, _, remainder = text.partition("|")
    return remainder or text


def detect_container(data: bytes) -> str:
    """Classify raw bytes by container format.

    Returns one of ``empty``, ``zip`` (which covers every OOXML file,
    ``.docx`` included), ``legacy_doc``, ``encrypted_office``, ``ole2``,
    ``pdf``, ``rtf``, ``xml``, or ``unknown``. Extension is deliberately
    ignored: the whole point is to catch files that were renamed.
    """
    if not data:
        return "empty"
    if data.startswith(_ZIP_MAGIC):
        return "zip"
    if data.startswith(_OLE2_MAGIC):
        # Both a legacy .doc and an encrypted .docx are OLE2 containers.
        # The directory holding the stream names may sit anywhere in the
        # file, so scan the whole buffer rather than a fixed header window.
        if _OLE2_ENCRYPTED_STREAM in data:
            return "encrypted_office"
        if _OLE2_WORD_STREAM in data:
            return "legacy_doc"
        return "ole2"
    if data.startswith(_PDF_MAGIC):
        return "pdf"
    if data.startswith(_RTF_MAGIC):
        return "rtf"
    stripped = data.lstrip()[:5]
    if stripped.startswith(b"<?xml") or stripped.startswith(b"<"):
        return "xml"
    return "unknown"


def guard_word_bytes(data: bytes) -> None:
    """Reject bytes that are definitely not a ``.docx`` package.

    Called before handing off to python-docx so the user gets a remedy
    instead of ``Package not found``. A ``zip`` container passes through:
    it may still turn out not to be a Word package, which python-docx
    detects and :func:`classify_docx_open_failure` then labels.
    """
    kind = detect_container(data)
    if kind == "zip":
        return
    if kind == "empty":
        raise_unsupported("empty_file")
    if kind == "legacy_doc":
        raise_unsupported("legacy_doc")
    if kind == "encrypted_office":
        raise_unsupported("encrypted_office")
    if kind == "ole2":
        # An OLE2 container we could not narrow down is still an old-format
        # Office binary, and re-saving as .docx is the right remedy.
        raise_unsupported("legacy_doc")
    if kind == "pdf":
        raise_unsupported("pdf_not_docx")
    if kind == "rtf":
        raise_unsupported("rtf_not_docx")
    raise_unsupported("unreadable_docx")


def classify_docx_open_failure(data: bytes) -> str:
    """Pick a code for a file that passed the guard but python-docx rejected.

    A valid Zip that is not a Word package (an ``.xlsx``, a Pages export, a
    renamed archive) is a different mistake from a truncated ``.docx``.
    """
    if detect_container(data) == "zip":
        return "not_word_package"
    return "unreadable_docx"
