# PatentLint

A web-based patent specification analyzer that checks U.S. patent application drafts (.docx) against USPTO formatting rules and MPEP guidelines. Upload a draft — get a structured compliance report with actionable findings.

## Features

**MPEP Compliance Checks**

| Category | Checks | Reference |
|----------|--------|-----------|
| Specification | Restrictive wording, paragraph sequentiality, punctuation, sequence listing references, cross-references, prior art citations | MPEP § 2173.01 |
| Claims | Indefinite terms, numbering, dependencies, self-references, multiple dependencies, period placement, "wherein" comma rules, means-plus-function detection, antecedent basis validation, claim similarity (Jaccard) | MPEP § 2173.05(b), 35 U.S.C. § 112(b)(f) |
| Abstract | Word count (50–150), single paragraph, legal phraseology, implied phrases, self-praising terms | MPEP § 608.01(b) |
| Drawings | Figure count, sequential ordering, single-figure format, prior art references | General |

Each finding is classified as **PASS**, **VERIFY** (needs expert review), or **AMEND** (likely needs correction).

**Web Frontend**
- Drag-and-drop .docx upload
- Priority triage panel — issues grouped by urgency (Action Required → Expert Review → Passed)
- Interactive claim dependency tree with full claim text expansion
- Mermaid claim dependency diagram
- Health donut chart and section bar charts
- Antecedent basis review card with highlighted flagged terms
- Downloadable PDF report
- Copy summary to clipboard
- Dark / light mode
- Internationalization: English, 繁體中文, 简体中文, 日本語

## Architecture

```
src/patentlint/
├── models.py        # Pydantic models (Claim, AnalysisResult, ReportData)
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
| PDF Generation | Jinja2 + weasyprint |
| Claim Diagrams | Mermaid |
| Testing | pytest (134 tests) |
| i18n | react-i18next |

## Disclaimer

This tool does not constitute legal advice. All findings should be reviewed by a qualified patent professional before use in any filing or legal proceeding.

## License

© 2025 Christopher Chen. All rights reserved.
