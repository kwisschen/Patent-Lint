# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""No dev-only debug surface may reach the production bundle.

PatentLint's whole claim is that the analysis runs in the browser and nothing
else runs at all. A debug route that ships is a claim violation, not a cosmetic
slip - and `import.meta.env.DEV` guards are easy to write in a way that leaves
the component in the bundle anyway (the guard only makes the ROUTE unreachable;
a top-level import still pulls the code in unless the bundler can prove it dead).

This asserts the built bundle actually excludes it, rather than trusting that
the guard was written correctly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DIST = REPO / "frontend/dist/assets"

# Strings that only exist inside dev-only surfaces.
DEV_ONLY_MARKERS = [
    "Viewport harness",
    "__viewports",
]


@pytest.mark.parametrize("marker", DEV_ONLY_MARKERS)
def test_marker_absent_from_production_bundle(marker: str) -> None:
    if not DIST.exists():
        pytest.skip("no built bundle in this checkout (run npm run build)")
    hits = [
        p.name for p in DIST.glob("*.js")
        if marker in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not hits, (
        f"dev-only marker {marker!r} reached the production bundle in {hits}. "
        "An import.meta.env.DEV guard on the ROUTE is not enough on its own - "
        "check the component is genuinely unreferenced so the bundler drops it."
    )


def test_the_harness_route_is_guarded_in_source() -> None:
    """Belt and braces: the route registration must carry the DEV guard, so a
    future edit cannot expose it even before the bundle assertion notices."""
    app = (REPO / "frontend/src/App.jsx").read_text(encoding="utf-8")
    assert "__viewports" in app
    idx = app.index("__viewports")
    window = app[max(0, idx - 400):idx]
    assert "import.meta.env.DEV" in window, (
        "the /__viewports route must sit behind an import.meta.env.DEV guard"
    )
