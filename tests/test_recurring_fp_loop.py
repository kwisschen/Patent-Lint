"""CI-safe smoke test for the dev-time recurring-FP loop (ADR-159).

The loop module imports with stdlib only (heavy deps — anthropic/openai/pyarrow
— are lazy, behind the `eval` extra). These tests exercise the pure logic and
the graceful-degradation paths so the foundation can't silently rot, WITHOUT
needing the corpus, the LLM SDKs, network, or gh.
"""
import importlib.util
import sys
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parent / "eval" / "recurring_fp_loop.py"


def _load():
    spec = importlib.util.spec_from_file_location("recurring_fp_loop", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass (string annotations) can resolve
    # cls.__module__ via sys.modules.
    sys.modules["recurring_fp_loop"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_module_imports_stdlib_only():
    mod = _load()
    assert hasattr(mod, "run_corpus_mode")
    assert hasattr(mod, "run_reports_mode")


def test_action_mapping():
    mod = _load()
    assert mod.action_for("walker_fp") == "silence_fp"
    assert mod.action_for("legit_drafting_error") == "protect"
    for c in ("coverage_gap", "diagnostic_mis_attribution", "ambig"):
        assert mod.action_for(c) == "needs_human"


def test_stub_verdict_overcapture_signature():
    mod = _load()
    # Over-capture shapes (ref-prefix bleed / verb clause / long) lean walker_fp.
    v, _ = mod._stub_verdict("兩個所述上側柱", "該兩個所述上側柱")
    assert v == "walker_fp"
    v, _ = mod._stub_verdict("satellite device both perform communication", None)
    assert v == "walker_fp"
    # Short clean noun → undetermined (defer to the real judge).
    v, _ = mod._stub_verdict("外殼", "該外殼")
    assert v == "ambig"


def test_parse_payload():
    mod = _load()
    body = 'noise\n```json\n{"check_key": "antecedentBasis", "findings": []}\n```\nmore'
    assert mod.parse_payload(body)["check_key"] == "antecedentBasis"
    assert mod.parse_payload("no fenced block") is None


def test_reports_mode_dry_run_degrades_without_gh(monkeypatch):
    """With no reachable tracker (gh absent / errors), the loop returns an
    empty result rather than throwing — safe to run anywhere."""
    mod = _load()
    monkeypatch.setattr(mod, "iter_open_reports", lambda limit: [])
    res = mod.run_reports_mode(limit=5, cost_cap=0, dry_run=True)
    assert res.mode == "reports"
    assert res.findings_seen == 0
    assert res.proposed == []


def test_corpus_mode_dry_run_degrades_without_corpus(monkeypatch, tmp_path):
    """With the corpus root absent, corpus mode notes-and-skips."""
    mod = _load()
    monkeypatch.setenv("PATENTLINT_CORPUS_ROOT", str(tmp_path / "does-not-exist"))
    res = mod.run_corpus_mode("TW", limit=5, cost_cap=0, dry_run=True)
    assert any("corpus root absent" in n for n in res.notes)


def test_loop_result_summary_shape():
    mod = _load()
    res = mod.LoopResult(mode="corpus", jurisdiction="TW")
    res.proposed.append(mod.ProposedLabel(
        jurisdiction="TW", source="corpus:TWx", claim_id=1, term="外殼",
        reference_form="該外殼", verdict="walker_fp", confidence="dry-run-stub",
        proposed_action="silence_fp",
    ))
    s = res.summary()
    assert s["proposed_total"] == 1
    assert s["by_action"]["silence_fp"] == 1
