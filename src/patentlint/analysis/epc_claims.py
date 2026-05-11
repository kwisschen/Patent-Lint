# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""EPC claims-level checks (G4 + G5 + G6 in the canonical 7-group order).

G4 (structure):
  - check_claims_sequential_epc — Rule 43(5)
  - check_dependency_format_epc — Rule 43(4)
  - check_self_dependent_epc — basic logic
  - check_forward_dependency_epc — Rule 43(4) implied
  - check_single_sentence_per_claim_epc — Rule 43(4) + Guidelines F-IV § 4.10
  - check_reference_signs_in_parens_epc — Rule 43(7)
  - check_subject_consistency_epc — Guidelines F-IV § 3.4
  - check_transition_phrase_epc — Guidelines F-IV § 4.13

G5 (cross-jurisdiction / format guards):
  - check_claims_spec_reference_epc — Rule 43(6)
  - check_multi_dep_on_multi_dep_epc — Rule 43(4)
  - check_markush_format_epc — Guidelines F-IV § 4.20
  - check_independent_claim_count_epc — Rule 43(2) + 43(3) (high difficulty;
    may defer to v1.1)
  - check_two_part_form_epc — Rule 43(1) advisory (conditional)

G6 (§ 112-equivalent — walker territory):
  - check_antecedent_basis_epc — Art. 84 clarity + Guidelines F-IV § 4.5
    (port US walker with ~20-30% changes per duplicate-then-tune decision)
  - check_claim_punctuation_epc — Guidelines F-IV § 4.10
  - check_restrictive_absolutes_epc — Guidelines F-IV § 4.7 advisory
  - check_spec_support_epc — Art. 84 support + Guidelines F-IV § 6.x
    (port US § 112(a) walker)

Walker checks (antecedentBasis + specSupport) ship as REVIEW status at v1
(per locked decision: ADR-154-style promotion to FIX only after FP rate is
measured on real EPC corpus).

Stubs only at scaffolding stage. Walker port lands in a dedicated commit
later in the implementation order.
"""

from __future__ import annotations
