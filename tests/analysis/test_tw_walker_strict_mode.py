# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Phase 8b TW antecedent walker — strict_plural_reference_matching tests.

Per ADR-095, the walker treats plural reference forms (該等X / 該些X)
as number-neutral by default: a singular intro 一X is an acceptable
antecedent for 該等X. The strict_plural_reference_matching escape hatch
flips this behaviour so the walker emits a finding when an explicitly
plural reference form references a singular intro.

Default behaviour (number-neutral) is exercised in test_tw_walker.py.
This file covers the escape hatch only.
"""

from __future__ import annotations

from patentlint.analysis.tw_claims import check_antecedent_basis
from patentlint.models import Claim, TwPatentDocument, TwPatentType


def _make_doc(claims: list[Claim]) -> TwPatentDocument:
    return TwPatentDocument(
        patent_type=TwPatentType.INVENTION,
        title="一種裝置",
        technical_field=["本發明涉及一種裝置。"],
        prior_art=["已知有相關技術。"],
        disclosure=["本發明提供一種解決方案。"],
        embodiment=["參照圖1說明實施方式。"],
        claims=claims,
    )


def _claim(
    num: int,
    text: str,
    independent: bool = True,
    deps: list[int] | None = None,
    multi_dep: bool = False,
) -> Claim:
    return Claim(
        id=num,
        text=text,
        independent=independent,
        dependencies=deps or [],
        multiple_dependent=multi_dep,
    )


# ─────────────────────────────────────────────────────────────────────────
# Strict mode flips the silent number-neutral path into an emit
# ─────────────────────────────────────────────────────────────────────────


class TestStrictPluralEscapeHatch:
    def test_singular_intro_plural_reference_emits_in_strict(self):
        """一齒輪 → 該等齒輪 — strict mode emits, default does not.

        This is the canonical case the escape hatch was designed for: a
        plural reference (該等) where the antecedent introduced only a
        single instance.
        """
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一齒輪。"),
            _claim(2, "2. 如請求項1所述之裝置，其中該等齒輪為金屬。",
                   independent=False, deps=[1]),
        ])
        assert check_antecedent_basis(doc) == []
        strict = check_antecedent_basis(
            doc, strict_plural_reference_matching=True
        )
        assert len(strict) == 1
        finding = strict[0]
        assert finding["claim_id"] == 2
        assert finding["term"] == "齒輪"
        assert finding["reference_form"] == "該等齒輪"

    def test_singular_intro_該些_reference_emits_in_strict(self):
        """該些 is the second plural marker — same escape-hatch behavior."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一電極。"),
            _claim(2, "2. 如請求項1所述之裝置，其中該些電極為陽極。",
                   independent=False, deps=[1]),
        ])
        assert check_antecedent_basis(doc) == []
        strict = check_antecedent_basis(
            doc, strict_plural_reference_matching=True
        )
        assert len(strict) == 1
        assert strict[0]["reference_form"] == "該些電極"

    def test_plural_intro_plural_reference_silent_in_strict(self):
        """複數齒輪 → 該等齒輪 — both sides plural, strict must NOT fire.

        The escape hatch only flags singular→plural mismatches; matched
        plurality is the entire point of the strict mode and must pass.
        """
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含複數齒輪。"),
            _claim(2, "2. 如請求項1所述之裝置，其中該等齒輪為金屬。",
                   independent=False, deps=[1]),
        ])
        assert check_antecedent_basis(
            doc, strict_plural_reference_matching=True
        ) == []

    def test_plural_intro_singular_reference_silent_in_strict(self):
        """複數齒輪 → 該齒輪 — singular reference under default tolerance.

        Strict mode tightens plural references but does NOT tighten
        singular references against plural intros (the writer dropping
        the plural marker is conventionally acceptable in TW practice).
        """
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含複數齒輪。"),
            _claim(2, "2. 如請求項1所述之裝置，其中該齒輪為金屬。",
                   independent=False, deps=[1]),
        ])
        assert check_antecedent_basis(
            doc, strict_plural_reference_matching=True
        ) == []

    def test_singular_intro_singular_reference_silent_in_strict(self):
        """一齒輪 → 該齒輪 — neither marker plural, strict must NOT fire."""
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一齒輪。"),
            _claim(2, "2. 如請求項1所述之裝置，其中該齒輪為金屬。",
                   independent=False, deps=[1]),
        ])
        assert check_antecedent_basis(
            doc, strict_plural_reference_matching=True
        ) == []

    def test_unresolved_term_still_emits_in_strict(self):
        """When the term has no antecedent at all, strict mode emits the
        same finding as default — strict only ADDS findings, never
        suppresses them.
        """
        doc = _make_doc([
            _claim(1, "1. 一種裝置，包含一底座，該齒輪與該底座相連。"),
        ])
        default = check_antecedent_basis(doc)
        strict = check_antecedent_basis(
            doc, strict_plural_reference_matching=True
        )
        assert len(default) == 1
        assert default[0]["term"] == "齒輪"
        # Strict result must include the same unresolved finding.
        terms_strict = {f["term"] for f in strict}
        assert "齒輪" in terms_strict
