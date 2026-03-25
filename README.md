# PatentLint

[![CI](https://github.com/kwisschen/Patent-Lint/actions/workflows/ci.yml/badge.svg)](https://github.com/kwisschen/Patent-Lint/actions/workflows/ci.yml)

A web-based patent specification analyzer that checks U.S. patent application drafts (.docx) against USPTO formatting rules and MPEP guidelines. Upload a draft — get a structured compliance report with actionable findings.

## Features

**MPEP Compliance Checks**

| Category | Checks | Reference |
|----------|--------|-----------|
| Specification | Restrictive wording, paragraph sequentiality, punctuation, sequence listing references, cross-references, prior art citations, reference numeral consistency (spec vs drawings) | MPEP § 2173.01 |
| Claims | Indefinite terms, numbering, dependencies, self-references, multiple dependencies, period placement, "wherein" comma rules, means-plus-function detection, antecedent basis validation, preamble consistency, specification support, claim similarity (Jaccard) | MPEP § 2173.05(b), 35 U.S.C. § 112(b)(d)(f) |
| Abstract | Word count (50–150), single paragraph, legal phraseology, implied phrases, self-praising terms | MPEP § 608.01(b) |
| Drawings | Figure count, sequential ordering, single-figure format, prior art references, reference numeral consistency | General |

Each finding is classified as **PASS**, **VERIFY** (needs expert review), or **AMEND** (likely needs correction).

**Web Frontend**
- Drag-and-drop .docx upload
- Priority triage panel — issues grouped by urgency (Action Required → Expert Review → Passed)
- Interactive claim dependency tree with full claim text expansion
- Mermaid claim dependency diagram
- Health donut chart and section bar charts
- Antecedent basis review card with highlighted flagged terms
- Client-side PDF report generation (pdfmake — no server round-trip)
- Copy summary to clipboard
- Dark / light mode
- Internationalization: English, 繁體中文, 简体中文, 日本語

## Architecture

```
                         ┌──────────────────────┐
                         │   React Frontend     │
                         │  (Vite + shadcn/ui)  │
                         └─────┬──────────┬─────┘
               Web (default)   │          │   Docker/self-hosted
          ┌────────────────────┘          └──────────────────┐
          ▼                                                  ▼
┌──────────────────┐                              ┌──────────────────┐
│  Pyodide/WASM    │                              │  FastAPI (app.py) │
│  (in-browser     │                              └────────┬─────────┘
│   analysis)      │                                       │
└────────┬─────────┘                              ┌────────▼─────────┐
         │                                        │  pipeline.py     │
         │         ┌───────────────────────┐      │  analyze_file()  │
         └────────►│  parser/ + analysis/  │◄─────┘  analyze_bytes() │
                   │  (pure Python, zero   │      └──────────────────┘
                   │   framework deps)     │
                   └───────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │   pdfmake    │ │  weasyprint  │ │  Click CLI   │
    │ (web, client)│ │ (Docker/CLI) │ │  (cli.py)    │
    └──────────────┘ └──────────────┘ └──────────────┘
```

```
src/patentlint/
├── models.py        # Pydantic models (Claim, AnalysisResult, ReportData)
├── pipeline.py      # Analysis pipeline (zero web-framework deps)
├── cli.py           # Click CLI (analyze, batch)
├── parser/          # Section extraction, claim parsing, .docx loading
├── analysis/        # Rule checks — all pure functions, independently testable
├── report/          # PDF report generation (Jinja2 + weasyprint)
└── api/             # FastAPI REST endpoints

frontend/            # React + Tailwind + shadcn/ui
├── src/components/  # DropZone, ClaimTree, TriagePanel, HealthDonut, etc.
└── src/i18n/        # Locale files (en, zh-TW, zh-CN, ja)
```

The `parser/` and `analysis/` packages have **zero framework dependencies** — they can be imported and tested independently of FastAPI or any web layer.

## Quick Start

**Prerequisites**
- Python 3.11+
- Node.js 22+
- pango (`brew install pango` on macOS — required for PDF generation)

**Backend**
```bash
pip install -e ".[api,dev]"
pytest -v
uvicorn patentlint.api.app:app --port 8000 --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

**Production (single server)**
```bash
cd frontend && npm run build && cd ..
uvicorn patentlint.api.app:app --port 8000
# → http://localhost:8000 (serves both API and frontend)
```

## CLI

```bash
# Analyze a single patent draft
patentlint analyze patent-draft.docx

# Output JSON to file
patentlint analyze patent-draft.docx -o report.json

# Generate PDF report
patentlint analyze patent-draft.docx --format pdf -o report.pdf

# Batch analyze all .docx files in a directory
patentlint batch ./patents/ --output ./reports/

# Version
patentlint --version
```

Exit codes: `0` = clean, `1` = findings detected, `2` = error.

## Docker

```bash
# Build
docker build -t patentlint .

# Run (serves web UI + API on port 8000)
docker run -p 8000:8000 patentlint

# Analyze via API
curl -X POST http://localhost:8000/api/analyze -F "file=@patent.docx"
```

## REST API

```bash
# Analyze a patent draft (JSON response)
curl -X POST http://localhost:8000/api/analyze \
  -F "file=@patent-draft.docx"

# Analyze with report-formatted response
curl -X POST http://localhost:8000/api/analyze?format=report \
  -F "file=@patent-draft.docx"

# Download PDF report
curl -X POST http://localhost:8000/api/analyze/report \
  -F "file=@patent-draft.docx" -o report.pdf

# Health check
curl http://localhost:8000/api/health
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Pydantic |
| Frontend | React 18, Vite, Tailwind CSS v4, shadcn/ui |
| PDF Generation | pdfmake (web, client-side) · Jinja2 + weasyprint (Docker/CLI) |
| Claim Diagrams | Mermaid |
| CLI | Click |
| Testing | pytest (321 tests) |
| CI/CD | GitHub Actions, Docker |
| i18n | react-i18next |

## Disclaimer

This tool does not constitute legal advice. All findings should be reviewed by a qualified patent professional before use in any filing or legal proceeding.

## License

© 2025 Christopher Chen. All rights reserved.
