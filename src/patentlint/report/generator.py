# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""PDF report generator.

Renders AnalysisResult -> HTML (via Jinja2) -> PDF (via weasyprint).

Locale-aware since ADR-138 polish pass: the template reads copy from
``frontend/src/i18n/locales/*.json`` via the ``patentlint.i18n``
helper, so a TW or CN self-hosted user gets a Traditional-Chinese or
Simplified-Chinese PDF that matches what they'd see in the React UI.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from patentlint.i18n import get_translator, normalize_locale
from patentlint.models import AnalysisResult, Jurisdiction
from patentlint.report.details import localize_details, localize_message


def _get_template_dir() -> Path:
    return Path(__file__).parent / "templates"


# Jurisdiction → locale-key map for section headings, abstract counter,
# and the PDF header line. Mirrors frontend/src/lib/jurisdictionConfig.js
# so a check item pulled from ``claims_checks`` renders under the
# appropriate jurisdiction-scoped section label in the PDF.
_JURISDICTION_KEYS: dict[Jurisdiction, dict[str, str]] = {
    Jurisdiction.US: {
        "pdfHeader": "pdf.header",
        "specification": "section.specification",
        "drawings": "section.drawings",
        "claims": "section.claims",
        "abstract": "section.abstract",
        "abstractCounter": "pdf.abstractWordCount",
    },
    Jurisdiction.CN: {
        "pdfHeader": "pdf.header",
        "specification": "section.cn.specification",
        "drawings": "section.cn.drawings",
        "claims": "section.cn.claims",
        "abstract": "section.cn.abstract",
        "abstractCounter": "pdf.abstractCharCount",
    },
    Jurisdiction.TW: {
        "pdfHeader": "pdf.headerTw",
        "specification": "section.tw.specification",
        "drawings": "section.tw.drawings",
        "claims": "section.tw.claims",
        "abstract": "section.tw.abstract",
        "abstractCounter": "pdf.abstractCharCount",
    },
}


def _tree_label_key(label: str) -> str:
    """Map an English claim-tree group label to its locale key.

    ReportData constructs these labels as literal English ("Method
    Claims" / "Apparatus Claims" / "Claims") so the label doubles as a
    sentinel. The frontend pdfExport.js path does the same mapping.
    """
    if label == "Method Claims":
        return "tree.methodClaims"
    if label == "Claims":
        return "tree.claims"
    return "tree.apparatusClaims"


def _patent_type_key(patent_type: str | None) -> str | None:
    """Map an AnalysisResult.patent_type sentinel to a locale key."""
    if not patent_type:
        return None
    if patent_type == "UTILITY_MODEL":
        return "summary.patentTypeUtilityModel"
    return "summary.patentTypeInvention"


def _build_env(locale: str) -> Environment:
    """Build a Jinja env pre-bound to the requested locale.

    ``t()`` is a global callable; filters are registered for the two
    per-item translation helpers so the template can use either form.
    """
    env = Environment(
        loader=FileSystemLoader(str(_get_template_dir())),
        autoescape=True,
    )
    env.globals["t"] = get_translator(locale)
    env.globals["tree_label_key"] = _tree_label_key
    env.globals["patent_type_key"] = _patent_type_key
    env.globals["locale"] = locale
    env.filters["localize_message"] = lambda item: localize_message(item, locale)
    env.filters["localize_details"] = lambda item: localize_details(item, locale)
    return env


def render_html(result: AnalysisResult, locale: str = "en") -> str:
    """Render AnalysisResult to HTML string.

    ``locale`` accepts any BCP-47 tag and is normalized to one of
    ``{en, zh-TW, zh-CN, ja, ko}``. Unsupported tags fall back to
    ``en`` silently, matching i18next's behavior on the frontend.
    """
    normalized = normalize_locale(locale)
    env = _build_env(normalized)
    template = env.get_template("report.html")
    report_data = result.to_report_data()
    jconfig = _JURISDICTION_KEYS.get(
        report_data.jurisdiction, _JURISDICTION_KEYS[Jurisdiction.US]
    )
    return template.render(data=report_data, jconfig=jconfig, locale=normalized)


def render_pdf(result: AnalysisResult, locale: str = "en") -> bytes:
    """Render AnalysisResult to PDF bytes.

    Returns raw PDF bytes suitable for writing to a file or streaming
    in an HTTP response. See ``render_html`` for locale handling.
    """
    html_string = render_html(result, locale=locale)
    return HTML(string=html_string).write_pdf()
