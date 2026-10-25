# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# mutation_check.py - prove each new test fails with its mechanism disabled.
#
# A test that still passes with its own mechanism switched off is measuring
# someone else's code. This applies one source edit at a time, runs the named
# tests in a fresh interpreter, and restores the file, always.
#
# WHY NOT JUST EDIT AND RE-RUN: two mutants of the same length written within
# the same second share an mtime and size, so Python reuses the previous
# mutant's cached bytecode and the second check silently tests the first
# mutant (seen 2026-10-25). This script disables bytecode writing and clears
# the analysis __pycache__ before every run.
#
# USAGE
#   python tests/eval/mutation_check.py spec.json
# spec.json is a list of [file, label, old_text, new_text, test_path, -k expr]
# where old_text must occur exactly once in file.
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    files = sorted({m[0] for m in spec})
    originals = {f: (REPO_ROOT / f).read_text(encoding="utf-8") for f in files}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    caches = {(REPO_ROOT / f).parent / "__pycache__" for f in files}
    survivors = 0
    try:
        for path, label, old, new, test, expr in spec:
            src = originals[path]
            if src.count(old) != 1:
                print(f"{path} {label}: old_text occurs {src.count(old)} times, skipped")
                survivors += 1
                continue
            (REPO_ROOT / path).write_text(src.replace(old, new), encoding="utf-8")
            for c in caches:
                shutil.rmtree(c, ignore_errors=True)
            cmd = [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", test]
            if expr:
                cmd += ["-k", expr]
            out = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=REPO_ROOT).stdout
            failed = [ln.split("::")[-1] for ln in out.splitlines() if ln.startswith("FAILED")]
            print(f"{path} {label} -> {failed or 'NO FAILURE (the tests do not bite)'}")
            survivors += not failed
            (REPO_ROOT / path).write_text(src, encoding="utf-8")
    finally:
        for f, text in originals.items():
            (REPO_ROOT / f).write_text(text, encoding="utf-8")
        for c in caches:
            shutil.rmtree(c, ignore_errors=True)
    return 1 if survivors else 0


if __name__ == "__main__":
    raise SystemExit(main())
