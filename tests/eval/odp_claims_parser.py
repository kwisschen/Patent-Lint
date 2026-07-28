# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# odp_claims_parser.py - WS-A2 (ADR-159 Path-to-80). Clean EdgeXpert's
# `corpus_application_text.claims_text` (USPTO ODP-sourced, OCR-converted) into
# text the production `parse_claims` can ingest, so the antecedent walker can run
# on the 86k-app EdgeXpert corpus and be joined to real examiner §112 labels.
#
# The reference memory feared "parse_claims only handled 2/80" - that was after
# NAIVE markup-stripping. Characterized on a 400-app sample: 86% carry a leading
# line-number prefix (`12 12.`), 51% carry prosecution markup tags
# (`(Currently Amended)` …), 14% embed OCR'd SVG/figure tokens, 11% have a
# mangled dependency preamble (`according to The … according to`, claim number
# dropped). With the cleaner below, parse_claims reaches **92%** coverage
# (368/400 parse ≥1 claim, 367 ≥2). The 11% mangled-dep minority just produces
# noisier walker output - tolerable because the examiner join is term-level
# (app, term), NOT claim-number-keyed (which sidesteps the claim-version-skew
# 0%-overlap artifact the reference warns about).
from __future__ import annotations

import re

_LINE_PREFIX = re.compile(r"^\s*\d+\s+(\d+\s*\.)")
# `SVG <file>.svg 0.11 0.043 Chemistry Black and white` - the OCR figure token
# is the filename + up to a few floats + a closed set of category phrases. Bound
# it precisely (NOT a greedy `[\w\s]{0,30}`, which swallows real claim text like
# "a sensor" after the token).
_SVG_BLOCK = re.compile(
    r"SVG\s+\S+\.svg(?:\s+[\d.]+){0,4}"
    r"(?:\s+(?:Chemistry|Black and white|Color|Colour|Grayscale|Greyscale|Drawing|Line))*",
    re.I,
)
_SVG_BARE = re.compile(r"\S+\.svg\b")
_MARKUP = re.compile(
    r"\((?:Currently Amended|Previously Presented|Original|New|"
    r"Canceled|Cancelled|Withdrawn|Not Entered)\)",
    re.I,
)
_CANCELED_ONLY = re.compile(r"^\d+\s*\.\s*$")
_WS = re.compile(r"\s{2,}")


def clean_odp_claims(claims_text: str) -> str:
    """Normalize ODP/OCR claims_text into newline-joined `N. <text>` claims.

    Strips the line-number prefix, SVG OCR tokens, and prosecution-markup tags;
    drops canceled-only claim stubs. Does NOT repair intra-word OCR spacing
    (`sul fu ric acid`) - that is unrecoverable and bounds join recall instead.
    """
    out: list[str] = []
    for block in re.split(r"\n\s*\n", claims_text or ""):
        b = block.strip()
        if not b:
            continue
        b = _LINE_PREFIX.sub(r"\1", b)
        b = _SVG_BLOCK.sub(" ", b)
        b = _SVG_BARE.sub(" ", b)
        b = _MARKUP.sub("", b)
        if _CANCELED_ONLY.match(b):
            continue
        out.append(_WS.sub(" ", b).strip())
    return "\n".join(out)
