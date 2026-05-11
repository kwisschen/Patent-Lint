# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""EPC drawings-level checks (G3 in the canonical 7-group order).

  - check_figures_sequential_epc — Rule 46(2)(a)
  - check_single_figure_label_epc — Guidelines F-V § 1.2 (EPC convention is
    "Fig." not US's "FIG.")
  - check_prior_art_labeling_epc — Rule 46(2)(h)
  - figure_count_epc — informational tile (not a failure check)

Stubs only at scaffolding stage.
"""

from __future__ import annotations
