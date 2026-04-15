# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Tests for CNIPA filing XML parser."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from patentlint.parser.xml_loader import extract_cn_xml_from_zip, parse_cnipa_xml

FIXTURES = Path(__file__).parent.parent / "fixtures" / "cn"


# ---------------------------------------------------------------------------
# parse_cnipa_xml — file-based fixtures
# ---------------------------------------------------------------------------


class TestMinimalPass:
    """Tests against cn_minimal_pass.xml — a well-formed CNIPA filing."""

    @pytest.fixture()
    def doc(self):
        data = (FIXTURES / "cn_minimal_pass.xml").read_bytes()
        return parse_cnipa_xml(data)

    def test_title(self, doc):
        assert doc.title == "一种测试装置"

    def test_sections_present(self, doc):
        assert len(doc.technical_field) == 1
        assert len(doc.background) == 1
        assert len(doc.summary) == 1
        assert len(doc.drawings_description) == 1
        assert len(doc.detailed_description) == 1

    def test_claims_count_and_independence(self, doc):
        assert len(doc.claims) == 2
        assert doc.claims[0].id == 1
        assert doc.claims[0].independent is True
        assert doc.claims[1].id == 2
        assert doc.claims[1].independent is False
        assert doc.claims[1].dependencies == [1]

    def test_abstract(self, doc):
        assert doc.abstract_text
        assert "测试装置" in doc.abstract_text
        assert doc.abstract_char_count > 0

    def test_paragraph_numbers(self, doc):
        assert doc.paragraph_numbers == [1, 2, 3, 4, 5]

    def test_figures(self, doc):
        assert doc.figure_count == 1
        assert len(doc.figure_refs) >= 1

    def test_metadata_flags(self, doc):
        assert doc.has_paragraph_numbering is True
        assert doc.input_format == "xml"
        assert doc.has_doc_page_fallback is False


class TestDocPageFallback:
    """Tests against cn_doc_page.xml — scanned-image fallback."""

    @pytest.fixture()
    def doc(self):
        data = (FIXTURES / "cn_doc_page.xml").read_bytes()
        return parse_cnipa_xml(data)

    def test_fallback_flag(self, doc):
        assert doc.has_doc_page_fallback is True
        assert doc.input_format == "xml"

    def test_empty_content(self, doc):
        assert doc.title == ""
        assert len(doc.claims) == 0


class TestWipoElementNames:
    """Tests against cn_wipo_names.xml — unprefixed WIPO element names."""

    @pytest.fixture()
    def doc(self):
        data = (FIXTURES / "cn_wipo_names.xml").read_bytes()
        return parse_cnipa_xml(data)

    def test_title(self, doc):
        assert doc.title == "一种测试方法"

    def test_claims(self, doc):
        assert len(doc.claims) == 1
        assert doc.claims[0].id == 1

    def test_abstract(self, doc):
        assert "测试方法" in doc.abstract_text

    def test_no_fallback(self, doc):
        assert doc.has_doc_page_fallback is False


class TestRichInlineStripping:
    """Tests against cn_rich_inline.xml — inline markup must be stripped."""

    @pytest.fixture()
    def doc(self):
        data = (FIXTURES / "cn_rich_inline.xml").read_bytes()
        return parse_cnipa_xml(data)

    def test_bold_italic_stripped(self, doc):
        text = doc.technical_field[0]
        assert "重要的" in text
        assert "特殊" in text

    def test_sub_sup_stripped(self, doc):
        text = doc.technical_field[0]
        assert "H2O" in text
        assert "E=mc2" in text

    def test_no_xml_tags_in_text(self, doc):
        for section in (
            doc.technical_field,
            doc.background,
            doc.summary,
            doc.detailed_description,
        ):
            for para in section:
                assert "<" not in para
                assert ">" not in para


# ---------------------------------------------------------------------------
# parse_cnipa_xml — inline XML tests
# ---------------------------------------------------------------------------


class TestEmptyDescription:
    """XML with no <description> — claims and abstract still parsed."""

    def test_empty_description(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN" dtd-version="1.0" file="t" status="new">
  <cn-claims>
    <claim id="cl0001" num="0001">
      <claim-text>权利要求一。</claim-text>
    </claim>
  </cn-claims>
  <cn-abstract id="abst">
    <p id="p0001a" num="0001">摘要。</p>
  </cn-abstract>
</cn-application-body>""".encode()
        doc = parse_cnipa_xml(xml)
        assert doc.title == ""
        assert doc.technical_field == []
        assert doc.paragraph_numbers == []
        assert len(doc.claims) == 1
        assert doc.claims[0].id == 1


class TestClaimDependencies:
    """Verify dependency extraction across 4 claims."""

    def test_dependencies(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN" dtd-version="1.0" file="t" status="new">
  <cn-claims>
    <claim id="cl0001" num="0001">
      <claim-text>独立权利要求。</claim-text>
    </claim>
    <claim id="cl0002" num="0002">
      <claim-text>如<claim-ref idref="cl0001">权利要求1</claim-ref>所述。</claim-text>
    </claim>
    <claim id="cl0003" num="0003">
      <claim-text>如<claim-ref idref="cl0001">权利要求1</claim-ref>或<claim-ref idref="cl0002">权利要求2</claim-ref>所述。</claim-text>
    </claim>
    <claim id="cl0004" num="0004">
      <claim-text>如<claim-ref idref="cl0003">权利要求3</claim-ref>所述。</claim-text>
    </claim>
  </cn-claims>
</cn-application-body>""".encode()
        doc = parse_cnipa_xml(xml)
        assert doc.claims[0].independent is True
        assert doc.claims[1].dependencies == [1]
        assert doc.claims[2].dependencies == [1, 2]
        assert doc.claims[2].multiple_dependent is True
        assert doc.claims[3].dependencies == [3]


class TestParagraphNumbersSequential:
    """Paragraphs numbered 0001-0010 produce [1..10]."""

    def test_sequential(self):
        paras = "".join(
            f'<p id="p{i:04d}" num="{i:04d}">段落{i}。</p>' for i in range(1, 11)
        )
        xml = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN" dtd-version="1.0" file="t" status="new">
  <description>
    <invention-title>标题</invention-title>
    <technical-field>{paras}</technical-field>
  </description>
</cn-application-body>""".encode()
        doc = parse_cnipa_xml(xml)
        assert doc.paragraph_numbers == list(range(1, 11))


class TestParagraphNumbersWithGap:
    """Paragraphs 0001, 0002, 0004 — gap at 3."""

    def test_gap(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN" dtd-version="1.0" file="t" status="new">
  <description>
    <invention-title>标题</invention-title>
    <technical-field>
      <p id="p0001" num="0001">一。</p>
      <p id="p0002" num="0002">二。</p>
      <p id="p0004" num="0004">四。</p>
    </technical-field>
  </description>
</cn-application-body>""".encode()
        doc = parse_cnipa_xml(xml)
        assert doc.paragraph_numbers == [1, 2, 4]


class TestStructuredAbstract:
    """Abstract with abst-problem and abst-solution sub-elements."""

    def test_structured(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN" dtd-version="1.0" file="t" status="new">
  <cn-abstract id="abst">
    <abst-problem>
      <p id="ap1" num="0001">问题描述。</p>
    </abst-problem>
    <abst-solution>
      <p id="as1" num="0001">解决方案。</p>
    </abst-solution>
  </cn-abstract>
</cn-application-body>""".encode()
        doc = parse_cnipa_xml(xml)
        assert "问题描述" in doc.abstract_text
        assert "解决方案" in doc.abstract_text


class TestAbstractCharCountExcludesWhitespace:
    """abstract_char_count should exclude spaces and newlines."""

    def test_char_count(self):
        xml = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN" dtd-version="1.0" file="t" status="new">
  <cn-abstract id="abst">
    <p id="p1" num="0001">A B C</p>
    <p id="p2" num="0002">D E</p>
  </cn-abstract>
</cn-application-body>"""
        doc = parse_cnipa_xml(xml)
        # "A B C" + "D E" -> after removing spaces/newlines: "ABCDE" = 5 chars
        expected = len(doc.abstract_text.replace("\n", "").replace(" ", ""))
        assert doc.abstract_char_count == expected
        assert doc.abstract_char_count == 5


# ---------------------------------------------------------------------------
# extract_cn_xml_from_zip
# ---------------------------------------------------------------------------


def _make_zip(files: dict[str, bytes]) -> bytes:
    """Helper: create an in-memory zip with the given name->content mapping."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


class TestZipExtraction:
    """extract_cn_xml_from_zip on a valid zip with patent XML."""

    def test_extraction(self):
        xml_data = (FIXTURES / "cn_minimal_pass.xml").read_bytes()
        zip_data = _make_zip({"patent.xml": xml_data, "image.tif": b"\x00" * 10})
        extracted, filename = extract_cn_xml_from_zip(zip_data)
        assert filename == "patent.xml"
        doc = parse_cnipa_xml(extracted)
        assert doc.title == "一种测试装置"


class TestZipNoXml:
    """Zip containing only a non-XML file raises ValueError."""

    def test_no_xml(self):
        zip_data = _make_zip({"image.tif": b"\x00" * 10})
        with pytest.raises(ValueError, match="No cn-application-body XML found"):
            extract_cn_xml_from_zip(zip_data)


class TestZipWrongRoot:
    """Zip with XML that has a different root element raises ValueError."""

    def test_wrong_root(self):
        xml = b'<?xml version="1.0"?><other-document/>'
        zip_data = _make_zip({"doc.xml": xml})
        with pytest.raises(ValueError, match="No cn-application-body XML found"):
            extract_cn_xml_from_zip(zip_data)


class TestZipMultipleXmlFindsCorrect:
    """Zip with two XMLs — only the cn-application-body one is returned."""

    def test_finds_correct(self):
        wrong = b'<?xml version="1.0"?><other-doc/>'
        correct = (FIXTURES / "cn_minimal_pass.xml").read_bytes()
        zip_data = _make_zip({"wrong.xml": wrong, "patent.xml": correct})
        extracted, filename = extract_cn_xml_from_zip(zip_data)
        assert filename == "patent.xml"
        doc = parse_cnipa_xml(extracted)
        assert doc.title == "一种测试装置"
