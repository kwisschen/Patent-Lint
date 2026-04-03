# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025 Christopher Chen
"""CNIPA filing XML parser — cn-application-body DTD."""

from __future__ import annotations

import io
import zipfile

from lxml import etree

from patentlint.models import Claim, CnPatentDocument


def _iter_text(element) -> str:
    """Recursively extract plain text from an element, stripping all markup."""
    if element is None:
        return ""
    parts: list[str] = []
    if element.text:
        parts.append(element.text)
    for child in element:
        parts.append(_iter_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _extract_paragraphs(parent, section_tag: str) -> list[str]:
    """Extract paragraph text from a named section element."""
    if parent is None:
        return []
    section = parent.find(section_tag)
    if section is None:
        return []
    return [_iter_text(p) for p in section.findall("p")]


def _extract_paragraph_numbers(desc) -> list[int]:
    """Extract sequential paragraph numbers from p/@num across all sections."""
    if desc is None:
        return []
    nums: list[int] = []
    for p in desc.iter("p"):
        num_str = p.get("num")
        if num_str is not None:
            try:
                nums.append(int(num_str))
            except ValueError:
                continue
    return sorted(nums)


def _extract_figure_refs(root) -> list[str]:
    """Extract figure reference text from all <figref> elements."""
    return [_iter_text(ref) for ref in root.iter("figref") if _iter_text(ref)]


def _count_figures(root) -> int:
    """Count figure elements in drawings."""
    drawings = root.find(".//cn-drawings")
    if drawings is None:
        drawings = root.find(".//drawings")
    if drawings is None:
        return 0
    return len(drawings.findall("figure"))


def _parse_claim_ref_id(idref: str) -> int | None:
    """Extract claim number from idref like 'cl0003' or 'c01.0003'."""
    if not idref:
        return None
    # Handle c01.0003 format (multiple claim sets)
    if "." in idref:
        idref = idref.rsplit(".", 1)[-1]
    # Strip non-digit prefix (e.g., "cl" from "cl0003")
    digits = ""
    for ch in reversed(idref):
        if ch.isdigit():
            digits = ch + digits
        else:
            break
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _parse_claims_xml(claims_el) -> list[Claim]:
    """Parse claim elements into Claim models."""
    if claims_el is None:
        return []
    claims: list[Claim] = []
    for claim_el in claims_el.findall("claim"):
        num_str = claim_el.get("num", "0")
        try:
            num = int(num_str)
        except ValueError:
            continue

        text = _iter_text(claim_el).strip()

        # Extract dependencies from claim-ref elements
        deps: list[int] = []
        for ref in claim_el.iter("claim-ref"):
            idref = ref.get("idref", "")
            dep_num = _parse_claim_ref_id(idref)
            if dep_num is not None and dep_num != num:
                deps.append(dep_num)
        deps = sorted(set(deps))

        claims.append(Claim(
            id=num,
            text=text,
            independent=len(deps) == 0,
            dependencies=deps,
            multiple_dependent=len(deps) > 1,
            method_claim=False,
        ))
    return claims


def _extract_abstract_text(abstract_el) -> str:
    """Extract abstract text from cn-abstract or abstract element."""
    if abstract_el is None:
        return ""
    # Check for structured abstract (abst-problem, abst-solution)
    parts: list[str] = []
    for tag in ("abst-problem", "abst-solution"):
        sub = abstract_el.find(tag)
        if sub is not None:
            for p in sub.findall("p"):
                parts.append(_iter_text(p))
    # Also get direct <p> children (plain abstract format)
    for p in abstract_el.findall("p"):
        parts.append(_iter_text(p))
    return "\n".join(parts).strip()


def parse_cnipa_xml(data: bytes) -> CnPatentDocument:
    """Parse CNIPA filing XML (cn-application-body DTD) into CnPatentDocument.

    Handles both cn- prefixed element names (filing XML) and unprefixed
    WIPO-standard names (publication XML) via fallback finds.
    """
    root = etree.fromstring(data)

    # Detect doc-page fallback (scanned images, no structured text)
    has_doc_pages = root.find(".//doc-page") is not None
    has_description = root.find(".//description") is not None
    if has_doc_pages and not has_description:
        return CnPatentDocument(has_doc_page_fallback=True, input_format="xml")

    # Description sections
    desc = root.find(".//description")
    title_el = desc.find("invention-title") if desc is not None else None
    title = _iter_text(title_el).strip() if title_el is not None else ""

    technical_field = _extract_paragraphs(desc, "technical-field")
    background = _extract_paragraphs(desc, "background-art")
    summary = _extract_paragraphs(desc, "disclosure")
    drawings_description = _extract_paragraphs(desc, "description-of-drawings")
    detailed_description = _extract_paragraphs(desc, "mode-for-invention")

    # Paragraph numbers from p/@num
    paragraph_numbers = _extract_paragraph_numbers(desc)

    # Claims (cn-claims or claims fallback)
    claims_el = root.find(".//cn-claims")
    if claims_el is None:
        claims_el = root.find(".//claims")
    claims = _parse_claims_xml(claims_el)

    # Abstract (cn-abstract or abstract fallback)
    abstract_el = root.find(".//cn-abstract")
    if abstract_el is None:
        abstract_el = root.find(".//abstract")
    abstract_text = _extract_abstract_text(abstract_el)

    # Figures
    figure_count = _count_figures(root)
    figure_refs = _extract_figure_refs(root)

    return CnPatentDocument(
        title=title,
        technical_field=technical_field,
        background=background,
        summary=summary,
        drawings_description=drawings_description,
        detailed_description=detailed_description,
        claims=claims,
        abstract_text=abstract_text,
        abstract_char_count=len(abstract_text.replace("\n", "").replace(" ", "")),
        paragraph_numbers=paragraph_numbers,
        figure_count=figure_count,
        figure_refs=figure_refs,
        has_paragraph_numbering=len(paragraph_numbers) > 0,
        input_format="xml",
        has_doc_page_fallback=False,
    )


def extract_cn_xml_from_zip(data: bytes) -> tuple[bytes, str]:
    """Extract the main patent content XML from a CNIPA converter zip package.

    Searches for an XML file whose root element is cn-application-body
    (or application-body). Returns (xml_bytes, filename).

    Raises ValueError if no matching XML found.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".xml"):
                continue
            xml_data = zf.read(name)
            try:
                root = etree.fromstring(xml_data)
            except etree.XMLSyntaxError:
                continue
            if root.tag in ("cn-application-body", "application-body"):
                return xml_data, name
    msg = "No cn-application-body XML found in zip"
    raise ValueError(msg)
