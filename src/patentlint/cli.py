# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""PatentLint CLI — analyze patent .docx files from the command line.

Usage:
    patentlint analyze <file> [--format json|pdf] [-o/--output PATH]
    patentlint batch <directory> --output <directory> [--format json|pdf]
    patentlint --version
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from patentlint.i18n import supported_locales
from patentlint.models import Jurisdiction
from patentlint.pipeline import analyze_file

EXIT_SUCCESS = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

_LOCALE_HELP = (
    "PDF output locale. Accepts BCP-47 tags "
    f"({', '.join(supported_locales())}, or regional variants). "
    "Ignored for JSON output."
)


@click.group()
@click.version_option(version="1.0.0", prog_name="patentlint")
def main():
    """PatentLint — Patent draft quality checker."""


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--format", "fmt", type=click.Choice(["json", "pdf"]), default="json", help="Output format.")
@click.option("-o", "--output", type=click.Path(), default=None, help="Output file path (required for PDF).")
@click.option(
    "--jurisdiction",
    type=click.Choice(["us", "cn", "tw"], case_sensitive=False),
    default="us",
    help="Patent jurisdiction (us, cn, or tw).",
)
@click.option(
    "--locale",
    default="en",
    help=_LOCALE_HELP,
)
def analyze(file: str, fmt: str, output: str | None, jurisdiction: str, locale: str):
    """Analyze a single patent .docx file."""
    if fmt == "pdf" and output is None:
        click.echo("PDF output requires -o/--output. Example: patentlint analyze file.docx --format pdf -o report.pdf", err=True)
        raise SystemExit(EXIT_ERROR)

    j = Jurisdiction(jurisdiction.upper())

    try:
        result = analyze_file(file, jurisdiction=j)
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(EXIT_ERROR)

    if fmt == "pdf":
        try:
            from patentlint.report.generator import render_pdf
        except ImportError:
            click.echo("PDF output requires weasyprint. Install with: pip install patentlint[pdf]", err=True)
            raise SystemExit(EXIT_ERROR)

        pdf_bytes = render_pdf(result, locale=locale)
        Path(output).write_bytes(pdf_bytes)
        click.echo(f"PDF report written to {output}")
    else:
        json_str = result.model_dump_json(indent=2)
        if output:
            Path(output).write_text(json_str, encoding="utf-8")
            click.echo(f"JSON report written to {output}")
        else:
            click.echo(json_str)

    # Exit code based on findings
    report = result.to_report_data()
    all_checks = (
        report.specification_checks
        + report.claims_checks
        + report.abstract_checks
        + report.drawings_checks
    )
    has_findings = any(c.status in ("amend", "verify") for c in all_checks)
    raise SystemExit(EXIT_FINDINGS if has_findings else EXIT_SUCCESS)


@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--output", "-o", required=True, type=click.Path(), help="Output directory for reports.")
@click.option("--format", "fmt", type=click.Choice(["json", "pdf"]), default="json", help="Output format.")
@click.option(
    "--jurisdiction",
    type=click.Choice(["us", "cn", "tw"], case_sensitive=False),
    default="us",
    help="Patent jurisdiction (us, cn, or tw).",
)
@click.option(
    "--locale",
    default="en",
    help=_LOCALE_HELP,
)
def batch(directory: str, output: str, fmt: str, jurisdiction: str, locale: str):
    """Analyze all .docx files in a directory."""
    os.makedirs(output, exist_ok=True)

    docx_files = sorted(Path(directory).glob("*.docx"))
    if not docx_files:
        click.echo(f"No .docx files found in {directory}", err=True)
        raise SystemExit(EXIT_ERROR)

    if fmt == "pdf":
        try:
            from patentlint.report.generator import render_pdf
        except ImportError:
            click.echo("PDF output requires weasyprint. Install with: pip install patentlint[pdf]", err=True)
            raise SystemExit(EXIT_ERROR)

    j = Jurisdiction(jurisdiction.upper())

    has_errors = False
    has_findings = False

    with click.progressbar(docx_files, label="Analyzing", file=sys.stderr) as bar:
        for docx_path in bar:
            stem = docx_path.stem
            try:
                result = analyze_file(str(docx_path), jurisdiction=j)
            except Exception as e:
                click.echo(f"\nError processing {docx_path.name}: {e}", err=True)
                has_errors = True
                continue

            if fmt == "pdf":
                out_path = Path(output) / f"{stem}.pdf"
                pdf_bytes = render_pdf(result, locale=locale)
                out_path.write_bytes(pdf_bytes)
            else:
                out_path = Path(output) / f"{stem}.json"
                out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

            # Check for findings
            report = result.to_report_data()
            all_checks = (
                report.specification_checks
                + report.claims_checks
                + report.abstract_checks
                + report.drawings_checks
            )
            if any(c.status in ("amend", "verify") for c in all_checks):
                has_findings = True

    click.echo(f"Processed {len(docx_files)} files. Reports in {output}/", err=True)

    if has_errors:
        raise SystemExit(EXIT_ERROR)
    elif has_findings:
        raise SystemExit(EXIT_FINDINGS)
    else:
        raise SystemExit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
