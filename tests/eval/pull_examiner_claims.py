#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# pull_examiner_claims.py - fetch the EdgeXpert claims dump that
# examiner_fn_guard.py consumes, WITHOUT being blocked by the recurring
# "EdgeXpert is down" failure.
#
#   /usr/local/bin/python3 tests/eval/pull_examiner_claims.py   # needs psycopg2
#   python tests/eval/examiner_fn_guard.py --snapshot /tmp/pre_exam.json
#
# NOTE the two different interpreters: the PULL needs psycopg2, which lives in
# the Patent-Analyst-side interpreter, not the Patent-Lint env (CI installs
# [dev], not a DB driver). The GUARD itself runs in the Patent-Lint env.
#
# WHY THIS EXISTS. The pull used to be a copy-paste snippet in the
# examiner_fn_guard.py header that connected straight to
# ``<host>:5432``. That direct connection has failed in FIVE separate
# sessions (2026-07-13, 07-19, 07-20, 08-08, 08-10), and each time it blocked
# the authoritative US FN-guard - twice badly enough that a walker round
# (US R41, US R42) shipped on a weaker static substitute instead.
#
# There are exactly two distinct causes, and NEITHER means the box is down:
#
#   1. HOSTNAME TRAP - `edgexpert-ts` is an ~/.ssh/config Host ALIAS, not a
#      DNS name, so resolving it always fails. Connect to the IP.
#   2. BOOT-ORDER RACE - postgresql@16-main orders After=network.target, not
#      after tailscaled. At boot Postgres cannot bind the Tailscale address
#      from `listen_addresses` yet, so it silently falls back to listening on
#      127.0.0.1 ONLY. The box answers ping and SSH; only 5432 refuses.
#
# Cause 2 is the common one and it has a property worth exploiting: Postgres
# IS running and IS reachable - just on the box's loopback. SSH still works.
# So instead of failing, this script forwards a local port to the remote
# loopback and connects through that. No sudo, no restart, no waiting on the
# durable systemd fix.
#
# The permanent server-side repair is still worth doing (a systemd drop-in
# that waits for the tailscale0 address before starting Postgres) - see the
# reference_edgexpert_corpus_db memory. This script means the FN-guard is no
# longer hostage to it.

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import os
from pathlib import Path

DEFAULT_ENV = Path.home() / "Documents/Projects/Patent-Analyst/.env"
DEFAULT_OUT = Path("/tmp/odp_examiner_claims.json")
EXAM_JSON = Path(__file__).resolve().parent / "us_examiner_legit.json"

SSH_HOST = os.environ.get("PATENTLINT_EXAMINER_SSH_HOST", "edgexpert-ts")
# An ~/.ssh/config Host ALIAS - correct for ssh, NEVER for socket connects.
REMOTE_PG = "127.0.0.1:5432"
LOCAL_PORT = 15432


def read_db_url(env_path: Path) -> str:
    key = "ANALYST_CORPUS_DATABASE_URL"
    for line in env_path.read_text().splitlines():
        if line.startswith(key):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"FATAL: {key} not found in {env_path}")


def open_tunnel() -> None:
    """Forward LOCAL_PORT to the box's own loopback Postgres over SSH."""
    subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-f", "-N",
         "-L", f"{LOCAL_PORT}:{REMOTE_PG}", SSH_HOST],
        check=True,
    )
    time.sleep(2)


def connect(url: str, timeout: int = 30):
    try:
        import psycopg2
    except ModuleNotFoundError:
        raise SystemExit(
            "FATAL: psycopg2 is not installed in this interpreter.\n"
            "  The Patent-Lint env does not carry it (CI installs [dev], not a DB driver).\n"
            "  Run this script with an interpreter that has it, e.g.\n"
            "    /usr/local/bin/python3 tests/eval/pull_examiner_claims.py"
        ) from None

    return psycopg2.connect(url, connect_timeout=timeout)


def main() -> int:
    ap = argparse.ArgumentParser(description="Pull the EdgeXpert examiner claims dump")
    ap.add_argument("--env", type=Path, default=DEFAULT_ENV)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    if not EXAM_JSON.exists():
        print(f"FATAL: {EXAM_JSON} missing (gitignored, local-only).")
        return 2

    url = read_db_url(args.env)
    exam = json.loads(EXAM_JSON.read_text())

    try:
        conn = connect(url)
        route = "direct"
    except Exception as exc:  # noqa: BLE001 - any connect failure earns the fallback
        print(f"direct connect failed ({type(exc).__name__}) - falling back to SSH tunnel.")
        print("  This is almost certainly the boot-order race, NOT a down box:")
        print("  Postgres is up but bound to the remote loopback only.")
        open_tunnel()
        host_port = url.split("@", 1)[1].split("/", 1)[0]
        conn = connect(url.replace(host_port, f"127.0.0.1:{LOCAL_PORT}"))
        route = f"ssh tunnel (localhost:{LOCAL_PORT} -> {SSH_HOST} {REMOTE_PG})"

    cur = conn.cursor()
    cur.execute(
        "select source_key, claims_text from corpus_application_text "
        "where source_key = any(%s) and claims_text is not null",
        (list(exam),),
    )
    rows = cur.fetchall()
    args.out.write_text(json.dumps([[k, c] for k, c in rows]))

    print(f"route : {route}")
    print(f"pulled: {len(rows)} applications with claims_text (of {len(exam)} examiner apps)")
    print(f"wrote : {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
