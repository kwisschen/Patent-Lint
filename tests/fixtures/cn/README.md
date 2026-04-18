# CN fixtures

Layout:

```
cn/
├── *.xml                             # committed XML fixtures (CNIPA samples)
├── synthetic/                        # committed synthetic .docx for tw_contamination
├── local/                            # gitignored (see tests/fixtures/*/local/**)
│   ├── *.docx                        # real production CN patents (never committed)
│   ├── _capture_baseline_cn.py       # Stage 3 baseline capture + labels bootstrap
│   ├── _audit_claim_counts.py
│   └── baseline_phase8c.json
├── _phase8c_harness.py               # Phase 8c harness (ADR-110/111)
├── test_phase8c_harness.py
├── antecedent_labels_cn.json         # labels file, schema v11
└── parity/                           # committed parity tests
```

## Baseline capture script

`local/_capture_baseline_cn.py` runs `check_antecedent_basis_cn` across the
10 real CN fixtures and the 3 synthetic `tw_contamination` fixtures, then
writes two JSON payloads:

1. `local/baseline_phase8c.json` (gitignored) — fixture index with per-fixture
   finding counts and claim counts.
2. `antecedent_labels_cn.json` — schema v11 labels seed (committed).

### Labels-file guard

The script refuses to overwrite `antecedent_labels_cn.json` if it already
exists unless `--bootstrap` is passed. The committed labels file has evolved
across many walker-tuning rounds (resolved_by provenance, round tags, protect
flags); clobbering it silently is never what's intended outside a genuine
Stage 3 re-bootstrap.

### Per-finding `claim_text` (Phase 9 #29)

Each label dict now carries a `claim_text` field containing the verbatim
parsed claim body. This snapshot exists only on NEW captures — the existing
1507-entry committed labels file is unchanged by the Phase 9 #29 edit, so
older entries have no `claim_text` until they're re-bootstrapped. Future
walker investigations that want the source text for a finding can read it
straight off the label rather than re-parsing the `.docx` via
`load_docx_cn` + `extract_cn_sections_from_docx`.

### Usage

```bash
# Full capture (all fixtures). Labels-file write is guarded unless --bootstrap.
python tests/fixtures/cn/local/_capture_baseline_cn.py

# Single-fixture dry-run (never writes labels file).
python tests/fixtures/cn/local/_capture_baseline_cn.py --fixture CN110276410B

# Genuine Stage 3 re-bootstrap (destructive — replaces committed labels).
python tests/fixtures/cn/local/_capture_baseline_cn.py --bootstrap
```
