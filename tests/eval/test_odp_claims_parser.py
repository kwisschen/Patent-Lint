# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# Unit tests for the WS-A2 ODP claims cleaner. Pure-regex module (no [eval]
# deps) so this runs under CI's [dev] install.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from odp_claims_parser import clean_odp_claims  # noqa: E402


def test_strips_line_number_prefix():
    assert clean_odp_claims("12 12. A widget.") == "12. A widget."


def test_strips_prosecution_markup():
    out = clean_odp_claims("3 3. (Currently Amended) The widget of claim 1.")
    assert out == "3. The widget of claim 1."


def test_drops_canceled_stub():
    out = clean_odp_claims("4 4. (Canceled)\n\n5 5. A gizmo.")
    assert out == "5. A gizmo."


def test_strips_svg_token():
    out = clean_odp_claims("1 1. A device comprising SVG x.12-30.svg 0.11 0.043 Chemistry Black and white a sensor.")
    assert ".svg" not in out
    assert out.startswith("1. A device comprising")
    assert "a sensor." in out


def test_multi_claim_join_and_deps_preserved():
    raw = "1 1. A method comprising a step.\n\n2 2. The method of claim 1, wherein x."
    out = clean_odp_claims(raw)
    assert out == "1. A method comprising a step.\n2. The method of claim 1, wherein x."
