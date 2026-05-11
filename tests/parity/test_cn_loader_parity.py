# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Parity tests — CN .docx loader vs CNIPA XML loader.

Both loaders must produce matching claim counts and normalized claim text
for the same patent content. Stage 1 of Phase 8c validates this on two
synthetic fixture pairs committed under ``tests/fixtures/cn/parity/``.

The DTD ships with external-entity references (wipo.ent, sipo.ent, mathml
subset) that the bundled build does not resolve, so ``xmllint
--dtdvalid`` fails on a naked invocation. Structural assertions inside
this test module stand in for DTD validation — required attributes,
required top-level elements, and valid-claim-count are checked
explicitly.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from lxml import etree

from patentlint.parser.docx_loader import load_docx_cn
from patentlint.parser.sections_cn import extract_cn_sections_from_docx
from patentlint.parser.xml_loader import parse_cnipa_xml

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "cn" / "parity"
SAMPLE_DIR = Path(__file__).parent.parent / "fixtures" / "cn"

_NUM_PREFIX_RE = re.compile(r"^\s*\d+\s*[.．。、]\s*")
_WHITESPACE_RE = re.compile(r"[\s\u3000]+")


def _normalize_claim_text(text: str) -> str:
    """Normalize a CN claim body for parity comparison.

    Strips any leading ``N.`` / ``N．`` / ``N、`` numbering prefix,
    collapses all whitespace (including full-width U+3000), and applies
    NFKC normalization to fold full-width / half-width punctuation.
    """
    text = unicodedata.normalize("NFKC", text)
    text = _NUM_PREFIX_RE.sub("", text.strip())
    text = _WHITESPACE_RE.sub("", text)
    return text


def _assert_structural_dtd_sanity(xml_path: Path) -> None:
    """Stand-in for ``xmllint --dtdvalid`` when external entities can't
    be resolved. Verifies required root attributes and the three
    top-level content elements expected by the cn-application-body DTD."""
    root = etree.fromstring(xml_path.read_bytes())
    assert root.tag == "cn-application-body", (
        f"root element is {root.tag!r}, expected cn-application-body"
    )
    for attr in ("lang", "country", "dtd-version", "file", "status"):
        assert root.get(attr), f"{xml_path.name}: missing required attribute {attr!r}"
    assert root.find("description") is not None, f"{xml_path.name}: missing <description>"
    assert root.find("cn-claims") is not None, f"{xml_path.name}: missing <cn-claims>"
    assert root.find("cn-abstract") is not None, f"{xml_path.name}: missing <cn-abstract>"


def _load_docx_claims(docx_path: Path):
    """Run the CN .docx pipeline and return the parsed claims list."""
    loaded = load_docx_cn(str(docx_path))
    return extract_cn_sections_from_docx(loaded.sections).claims


def _load_xml_claims(xml_path: Path):
    return parse_cnipa_xml(xml_path.read_bytes()).claims


def test_pair_a_apparatus_method_minimal_parity():
    """Pair A — typed-prefix claims, body-anchor 五书 layout, 5 claims.

    Exercises Tier 1 (body-anchor) of the CN section-ID fallback chain
    and the ``^N.`` typed-prefix path of ``parse_cn_claims_docx``.
    """
    docx_path = FIXTURE_DIR / "apparatus_method_minimal.docx"
    xml_path = FIXTURE_DIR / "apparatus_method_minimal.xml"
    _assert_structural_dtd_sanity(xml_path)

    docx_claims = _load_docx_claims(docx_path)
    xml_claims = _load_xml_claims(xml_path)

    assert len(xml_claims) == 5, f"XML Pair A should have 5 claims, got {len(xml_claims)}"
    assert len(docx_claims) == 5, (
        f"DOCX Pair A should have 5 claims, got {len(docx_claims)}"
    )
    for d, x in zip(docx_claims, xml_claims, strict=True):
        assert d.id == x.id, f"claim number mismatch: docx={d.id} xml={x.id}"
        assert _normalize_claim_text(d.text) == _normalize_claim_text(x.text), (
            f"claim {d.id} text parity broken:\n  docx={_normalize_claim_text(d.text)!r}\n"
            f"   xml={_normalize_claim_text(x.text)!r}"
        )


def test_pair_b_numbering_multidep_markush_parity():
    """Pair B — w:numPr auto-numbering, Markush, multi-dep, 4 claims.

    Exercises the ``_extract_numpr_claim_number`` backfill path in
    ``load_docx_cn``; claims have no typed ``N.`` prefix in the docx so
    parity depends on synthetic-prefix injection working correctly.
    """
    docx_path = FIXTURE_DIR / "numbering_multidep_markush.docx"
    xml_path = FIXTURE_DIR / "numbering_multidep_markush.xml"
    _assert_structural_dtd_sanity(xml_path)

    docx_claims = _load_docx_claims(docx_path)
    xml_claims = _load_xml_claims(xml_path)

    assert len(xml_claims) == 4, f"XML Pair B should have 4 claims, got {len(xml_claims)}"
    assert len(docx_claims) == 4, (
        f"DOCX Pair B should have 4 claims, got {len(docx_claims)}"
    )
    for d, x in zip(docx_claims, xml_claims, strict=True):
        assert d.id == x.id, f"claim number mismatch: docx={d.id} xml={x.id}"
        assert _normalize_claim_text(d.text) == _normalize_claim_text(x.text), (
            f"claim {d.id} text parity broken:\n  docx={_normalize_claim_text(d.text)!r}\n"
            f"   xml={_normalize_claim_text(x.text)!r}"
        )


def test_doc_page_content_model_does_not_crash():
    """Doc-page (scanned) XML must parse without raising and must set
    the ``has_doc_page_fallback`` flag so downstream checks can gate on
    scanned-image filings. Regression guard against misidentifying
    doc-page paragraphs as 五书 section boundaries."""
    xml_path = SAMPLE_DIR / "cn_doc_page.xml"
    cn_doc = parse_cnipa_xml(xml_path.read_bytes())

    assert cn_doc.has_doc_page_fallback is True
    assert cn_doc.input_format == "xml"
    # Scanned filing has no structured text — all paragraph lists empty.
    assert cn_doc.claims == []
    assert cn_doc.technical_field == []
