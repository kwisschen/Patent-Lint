# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Ingest synthetic fixtures into TW harness manifest + labels.

Phase A3 deliverable. Also re-runnable during Phase G when corpus grows
and synthetic emissions need refresh.

Walks every ``tests/fixtures/tw/synthetic/*.docx`` registered in
``_registry.json``, runs ``check_antecedent_basis`` against each, and:

1. Merges synthetic fixture records into
   ``tests/fixtures/tw/local/baseline_phase8b_postship.json``
   (metadata.fixture_count, metadata.captured_at, fixtures[key]).
2. Upserts synthetic emissions into
   ``tests/fixtures/tw/antecedent_labels.json``, pre-classified by
   registry intent. Existing labels for a synthetic are left alone on
   re-runs unless --force-reclassify is passed.

Pre-classification from registry::

    - adversarial guardrail → legit_drafting_error, protect:true
    - regression (expected_emissions=0) → no labels (clean fixture)
    - mechanism-under-test → miss_intro.coverage_gap, protect:false
    - over_capture (per walker output inspection) →
      walker_fp.over_capture, protect:false

Deterministic; safe to re-run. Reports changes; does not hide drift.

Run from the project root::

    python tests/fixtures/tw/synthetic/_ingest_synthetics.py
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from patentlint.analysis.tw_claims import check_antecedent_basis  # noqa: E402
from patentlint.parser.docx_loader import load_docx_tw  # noqa: E402
from patentlint.parser.sections_tw import extract_tw_sections  # noqa: E402

SYNTHETIC_DIR = _REPO_ROOT / "tests/fixtures/tw/synthetic"
REGISTRY_PATH = SYNTHETIC_DIR / "_registry.json"
MANIFEST_PATH = _REPO_ROOT / "tests/fixtures/tw/local/baseline_phase8b_postship.json"
LABELS_PATH = _REPO_ROOT / "tests/fixtures/tw/antecedent_labels.json"


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(_REPO_ROOT), text=True
        ).strip()
    except Exception:
        return "unknown"


def _finding_id(claim_id: int, term: str, idx: int) -> str:
    sha = hashlib.sha256(term.encode("utf-8")).hexdigest()[:8]
    return f"claim_{claim_id}_{sha}_{idx}"


def _walk_synthetic(docx_path: Path) -> tuple[int, list[dict]]:
    """Return (claim_count, findings) for one synthetic fixture."""
    loaded = load_docx_tw(docx_path)
    doc = extract_tw_sections(loaded.paragraphs)
    findings: list[dict] = []
    per_claim_idx: dict[int, int] = {}
    for issue in check_antecedent_basis(doc):
        cid = issue["claim_id"]
        idx = per_claim_idx.get(cid, 0)
        per_claim_idx[cid] = idx + 1
        findings.append({
            "finding_id": _finding_id(cid, issue["term"], idx),
            "claim_id": cid,
            "term": issue["term"],
            "reference_form": issue["reference_form"],
            "claim_text_excerpt": issue.get("claim_text", ""),
            "status": "flagged",
        })
    return len(doc.claims), findings


def _classify_for_label(finding: dict, entry: dict) -> tuple[str, bool, str]:
    """Return (category, protect, notes) for a new label based on
    registry intent. Heuristics:

    - Adversarial guardrail → legit_drafting_error, protect:true.
    - If registry says expected_emissions=0, no label (caller handles).
    - If term contains an obvious over-capture trailing verb (設置/分/選自由),
      tag walker_fp.over_capture.
    - Otherwise default to miss_intro.coverage_gap for mechanism-under-test.
    """
    mech = entry.get("target_mechanism", "")
    if mech == "over_fit_guardrail":
        return (
            "legit_drafting_error",
            True,
            f"Adversarial guardrail: {finding['reference_form']} has no antecedent.",
        )
    term = finding["term"]
    # Over-capture heuristic: term ends with a typical trailing verb.
    for suffix in ("選自由", "分", "來自一", "填充", "圍繞", "調節"):
        if term.endswith(suffix):
            return (
                "walker_fp.over_capture",
                False,
                f"Walker captured trailing {suffix!r}; should strip to clean NP.",
            )
    return (
        "miss_intro.coverage_gap",
        False,
        f"Synthetic coverage gap for {mech}.",
    )


def _label_key(fixture: str, claim_id: int, term: str, ref: str) -> tuple:
    return (fixture, claim_id, term, ref)


def _upsert_manifest(manifest: dict, fixture_key: str, path: Path, claim_count: int, findings: list[dict]) -> bool:
    """Insert or update a fixture record. Returns True if changed."""
    rel_path = str(path.relative_to(_REPO_ROOT))
    record = {
        "fixture_path": rel_path,
        "load_status": "ok",
        "load_error": None,
        "claim_count": claim_count,
        "finding_count": len(findings),
        "finding_ids": sorted(f["finding_id"] for f in findings),
        "findings": sorted(findings, key=lambda f: f["finding_id"]),
        "canonical_unique_terms": sorted({f["term"] for f in findings}),
        "cross_check_ok": True,
    }
    existing = manifest["fixtures"].get(fixture_key)
    if existing == record:
        return False
    manifest["fixtures"][fixture_key] = record
    return True


def _upsert_labels(labels_doc: dict, fixture_key: str, findings: list[dict], registry_entry: dict) -> tuple[int, int]:
    """Insert new labels for synthetic findings; leave existing labels
    alone. Returns (added, skipped_existing).
    """
    existing_keys = {
        _label_key(lab["fixture"], lab["claim_id"], lab["term"], lab["reference_form"])
        for lab in labels_doc["labels"]
    }
    added = 0
    skipped = 0
    for f in findings:
        key = _label_key(fixture_key, f["claim_id"], f["term"], f["reference_form"])
        if key in existing_keys:
            skipped += 1
            continue
        category, protect, notes = _classify_for_label(f, registry_entry)
        labels_doc["labels"].append({
            "fixture": fixture_key,
            "claim_id": f["claim_id"],
            "term": f["term"],
            "reference_form": f["reference_form"],
            "category": category,
            "protect": protect,
            "confidence": "synthetic_baseline",
            "notes": notes,
            "resolved_by": None,
            "round": 0,
        })
        added += 1
    return added, skipped


def main() -> int:
    if not REGISTRY_PATH.exists():
        print(f"FATAL: registry not found at {REGISTRY_PATH}", file=sys.stderr)
        return 1
    with REGISTRY_PATH.open(encoding="utf-8") as fh:
        registry = json.load(fh)

    with MANIFEST_PATH.open(encoding="utf-8") as fh:
        manifest = json.load(fh)
    with LABELS_PATH.open(encoding="utf-8") as fh:
        labels_doc = json.load(fh)

    manifest_changed = False
    total_added = 0
    total_skipped = 0
    per_fixture_counts: list[tuple[str, int]] = []

    for entry in registry["synthetic_fixtures"]:
        fixture_key = entry["key"]
        path = _REPO_ROOT / entry["path"]
        if not path.exists():
            print(f"SKIP: {fixture_key} docx not found at {path}")
            continue
        claim_count, findings = _walk_synthetic(path)
        per_fixture_counts.append((fixture_key, len(findings)))
        if _upsert_manifest(manifest, fixture_key, path, claim_count, findings):
            manifest_changed = True
        added, skipped = _upsert_labels(labels_doc, fixture_key, findings, entry)
        total_added += added
        total_skipped += skipped
        print(f"  {fixture_key}: {claim_count} claims, {len(findings)} findings "
              f"(+{added} labels, {skipped} existing)")

    if manifest_changed:
        manifest["metadata"]["fixture_count"] = len(manifest["fixtures"])
        manifest["metadata"]["captured_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
        manifest["metadata"]["commit_hash"] = _git_head()
        notes_suffix = (
            f" | Phase A3 synthetic ingestion {_dt.date.today().isoformat()}: "
            f"{len([r for r in registry['synthetic_fixtures']])} synthetic fixtures merged."
        )
        if notes_suffix not in manifest["metadata"].get("notes", ""):
            manifest["metadata"]["notes"] = manifest["metadata"].get("notes", "") + notes_suffix

    with MANIFEST_PATH.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=False)
        fh.write("\n")
    with LABELS_PATH.open("w", encoding="utf-8") as fh:
        json.dump(labels_doc, fh, ensure_ascii=False, indent=2, sort_keys=False)
        fh.write("\n")

    print()
    print("Ingestion summary:")
    print(f"  manifest: {'UPDATED' if manifest_changed else 'unchanged'} "
          f"({manifest['metadata']['fixture_count']} total fixtures)")
    print(f"  labels: +{total_added} added, {total_skipped} skipped "
          f"(total: {len(labels_doc['labels'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
