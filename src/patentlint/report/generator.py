"""PDF report generator.

Renders AnalysisResult -> HTML (via Jinja2) -> PDF (via weasyprint).
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from patentlint.models import AnalysisResult


def _get_template_dir() -> Path:
    return Path(__file__).parent / "templates"


def _build_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_get_template_dir())),
        autoescape=True,
    )


def render_html(result: AnalysisResult) -> str:
    """Render AnalysisResult to HTML string."""
    env = _build_env()
    template = env.get_template("report.html")
    report_data = result.to_report_data()
    return template.render(data=report_data)


def render_pdf(result: AnalysisResult) -> bytes:
    """Render AnalysisResult to PDF bytes.

    Returns raw PDF bytes suitable for writing to a file or streaming
    in an HTTP response.
    """
    html_string = render_html(result)
    return HTML(string=html_string).write_pdf()
