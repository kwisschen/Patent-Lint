# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""EPC specification-level checks (G1 + G2 in the canonical 7-group order).

G1 (structure):
  - check_required_sections_epc — Art. 78(1) + Rule 41 + Rule 42(1)
  - check_section_ordering_epc — Rule 42(1) canonical order
  - check_paragraph_numbering_epc — Guidelines F-II § 4.2
  - check_paragraph_ending_epc — drafting hygiene (no specific statute)
  - check_title_required_epc — Rule 41(2)(b)

G2 (content):
  - check_figure_ref_consistency_epc — Rule 46(2)(h)
  - check_numeral_consistency_epc — Rule 46(2)(h) + Rule 43(7)
  - check_claim_reference_in_spec_epc — Guidelines F-IV § 4.3 forbids
    paragraph-by-claim-number references in the description

Stubs only at scaffolding stage. Each check returns a passing ``CheckItem``
so the pipeline can run end-to-end before any real-corpus signal exists. Per
DR-1: no real check logic ships without statute-grounded primary-source
research first.
"""

from __future__ import annotations
