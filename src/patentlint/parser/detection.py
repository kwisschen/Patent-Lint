# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Shared detection-reason codes used by the three jurisdiction detectors.

When :func:`detect_patent_document` / ``_cn`` / ``_tw`` rejects a document,
the reason code carries forward to the frontend banner so the copy can
honestly describe what happened — rather than the legacy behavior of
always saying "no standard sections/claims/paragraphs found" regardless
of whether the real trigger was content absence or cross-script
contamination.

Reason codes:

- ``patent_detected`` — positive evidence found; not rejected.
- ``content_missing`` — no positive evidence of any kind (no recognized
  section headers, no numbered claims, no paragraph numbering). The
  legacy banner copy was written for this case.
- ``cross_script_japanese`` — enough JP-specific kana content to
  conclude the document is Japanese (not a supported jurisdiction).
- ``cross_script_korean`` — enough Hangul content to conclude the
  document is Korean (not a supported jurisdiction).
- ``weak_signal`` — ambiguous: some indicators present but below the
  confidence threshold. Used when positive evidence is weak AND the
  cross-script ratio is non-zero but also below the rejection
  threshold.
"""

from __future__ import annotations

from enum import Enum


class DetectionReason(str, Enum):
    PATENT_DETECTED = "patent_detected"
    CONTENT_MISSING = "content_missing"
    CROSS_SCRIPT_JAPANESE = "cross_script_japanese"
    CROSS_SCRIPT_KOREAN = "cross_script_korean"
    WEAK_SIGNAL = "weak_signal"


# A ratio ≥ this share of non-whitespace content is treated as strong
# evidence that the document is written in the named foreign script.
# 0.5% thresholds tolerate trace contamination (translated-from-JP drafts
# keeping a handful of katakana for transliterated terms) while still
# catching genuinely-foreign documents.
JP_KANA_REJECTION_RATIO = 0.005
HANGUL_REJECTION_RATIO = 0.005

# Result tuple shape: (is_patent, reason). Consumers unpack both; the
# pipeline stores ``reason.value`` on AnalysisResult.patent_detection_reason
# so the frontend banner can key off it.
DetectionResult = tuple[bool, DetectionReason]
