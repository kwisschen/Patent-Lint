# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Shared figure-reference parser for US, TW, and CN jurisdictions.

Config-driven parser that handles singletons, ranges (numeric and alpha
sub-figure), and list enumeration with jurisdiction-specific operators
and left-boundary guards for CJK compound-noun disambiguation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FigureExtractResult:
    """Result of figure reference extraction."""

    ids: frozenset[str]
    ordered: tuple[str, ...]
    spans: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class FigureParserConfig:
    """Configuration for a jurisdiction-specific figure reference parser."""

    name: str
    prefix_pattern: str
    suffix_prefix_pattern: str | None
    range_operators: tuple[str, ...]
    list_joiners: tuple[str, ...]
    left_boundary_guard: str
    case_insensitive: bool


_NUMERAL_RE = re.compile(r"\d+(?:\([a-zA-Z]\)|[a-zA-Z])?")
_WS_RE = re.compile(r"\s+")


def _build_op_regex(
    ops: tuple[str, ...], case_insensitive: bool = False,
) -> re.Pattern[str]:
    """Build a regex that matches any of the given operators."""
    parts: list[str] = []
    for op in sorted(ops, key=len, reverse=True):
        escaped = re.escape(op)
        if op.isascii() and op.isalpha():
            parts.append(rf"\b{escaped}\b")
        else:
            parts.append(escaped)
    flags = re.IGNORECASE if case_insensitive else 0
    return re.compile("|".join(parts), flags)


def _normalize_numeral(raw: str) -> str:
    """Normalize a numeral token: strip parens, uppercase suffix."""
    m = re.match(r"(\d+)(?:\(([a-zA-Z])\)|([a-zA-Z]))?", raw)
    if not m:
        return raw
    num = m.group(1)
    suffix = (m.group(2) or m.group(3) or "").upper()
    return num + suffix


def _parse_fig_id(fig_id: str) -> tuple[int, str]:
    """Parse a normalized figure ID into (number, suffix)."""
    m = re.match(r"(\d+)([A-Z])?$", fig_id)
    if not m:
        return (0, "")
    return (int(m.group(1)), m.group(2) or "")


def _expand_range(start: str, end: str) -> list[str]:
    """Expand a range between two figure IDs."""
    s_num, s_suffix = _parse_fig_id(start)
    e_num, e_suffix = _parse_fig_id(end)

    if s_num == e_num and s_suffix and e_suffix:
        return [f"{s_num}{chr(c)}" for c in range(ord(s_suffix), ord(e_suffix) + 1)]
    if not s_suffix and not e_suffix:
        return [str(i) for i in range(s_num, e_num + 1)]
    # Ambiguous (different numbers with suffixes): emit endpoints only
    return [start, end]


class FigureRefParser:
    """Config-driven figure reference parser for patent documents."""

    def __init__(self, config: FigureParserConfig) -> None:
        self._config = config
        self._span_re = self._build_span_regex()
        ci = config.case_insensitive
        self._range_re = _build_op_regex(config.range_operators, ci)
        self._list_re = _build_op_regex(config.list_joiners, ci)

    def _build_span_regex(self) -> re.Pattern[str]:
        cfg = self._config
        prefix = cfg.prefix_pattern
        guard = cfg.left_boundary_guard
        num = r"\d+(?:\([a-zA-Z]\)|[a-zA-Z])?"

        # Combined operator alternation (range + list) for span detection
        all_ops = list(cfg.range_operators) + list(cfg.list_joiners)
        op_parts: list[str] = []
        for op in sorted(all_ops, key=len, reverse=True):
            escaped = re.escape(op)
            if op.isascii() and op.isalpha():
                op_parts.append(rf"\b{escaped}\b")
            else:
                op_parts.append(escaped)
        ops_alt = "|".join(op_parts)

        # Continuation: one-or-more operators then a continuation element.
        # Multiple operators handles Oxford comma: ", and".
        if cfg.suffix_prefix_pattern:
            sfx = re.escape(cfg.suffix_prefix_pattern)
            cont_elem = (
                rf"(?:{sfx}\s*{num}\s*{prefix}|{prefix}\s*{num}|{num})"
            )
            cont = rf"(?:(?:\s*(?:{ops_alt}))+\s*{cont_elem})*"
            prefix_span = rf"{guard}{prefix}\s*{num}{cont}"
            suffix_span = rf"{sfx}\s*{num}\s*{prefix}{cont}"
            pattern = rf"(?:{suffix_span}|{prefix_span})"
        else:
            cont_elem = rf"(?:{prefix}\s*{num}|{num})"
            cont = rf"(?:(?:\s*(?:{ops_alt}))+\s*{cont_elem})*"
            pattern = rf"{guard}{prefix}\s*{num}{cont}"

        flags = re.IGNORECASE if cfg.case_insensitive else 0
        return re.compile(pattern, flags)

    def extract(self, text: str) -> FigureExtractResult:
        """Extract all figure references from text."""
        spans: list[tuple[int, int]] = []
        all_ids: list[str] = []
        seen: set[str] = set()

        for m in self._span_re.finditer(text):
            spans.append((m.start(), m.end()))
            for fid in self._resolve_span(m.group()):
                if fid not in seen:
                    all_ids.append(fid)
                    seen.add(fid)

        return FigureExtractResult(
            ids=frozenset(seen),
            ordered=tuple(all_ids),
            spans=tuple(spans),
        )

    def _resolve_span(self, span_text: str) -> list[str]:
        """Tokenize a matched span and walk tokens to produce figure IDs."""
        return self._walk_tokens(self._tokenize(span_text))

    def _tokenize(self, text: str) -> list[tuple[str, str]]:
        """Tokenize span text into NUM / RANGE / LIST tokens."""
        tokens: list[tuple[str, str]] = []
        pos = 0
        while pos < len(text):
            m = _WS_RE.match(text, pos)
            if m:
                pos = m.end()
                continue

            m = _NUMERAL_RE.match(text, pos)
            if m:
                tokens.append(("NUM", _normalize_numeral(m.group())))
                pos = m.end()
                continue

            m = self._range_re.match(text, pos)
            if m:
                tokens.append(("RANGE", m.group()))
                pos = m.end()
                continue

            m = self._list_re.match(text, pos)
            if m:
                tokens.append(("LIST", m.group()))
                pos = m.end()
                continue

            # Skip non-token characters (prefix text, punctuation, etc.)
            pos += 1

        return tokens

    @staticmethod
    def _walk_tokens(tokens: list[tuple[str, str]]) -> list[str]:
        """Walk token list: expand ranges, emit list items as singletons."""
        ids: list[str] = []
        i = 0
        while i < len(tokens):
            if tokens[i][0] == "NUM":
                if (
                    i + 2 < len(tokens)
                    and tokens[i + 1][0] == "RANGE"
                    and tokens[i + 2][0] == "NUM"
                ):
                    ids.extend(_expand_range(tokens[i][1], tokens[i + 2][1]))
                    i += 3
                else:
                    ids.append(tokens[i][1])
                    i += 1
            else:
                i += 1
        return ids


# ── Jurisdiction configs ────────────────────────────────────────────────

US_CONFIG = FigureParserConfig(
    name="us",
    prefix_pattern=r"(?:FIG(?:S)?\.?|Figure(?:s)?)",
    suffix_prefix_pattern=None,
    range_operators=("-", "\u2013", "\u2014", "~", "to", "through"),
    list_joiners=(",", "and"),
    left_boundary_guard="",
    case_insensitive=True,
)

TW_CONFIG = FigureParserConfig(
    name="tw",
    prefix_pattern=r"圖",
    suffix_prefix_pattern=r"第",
    range_operators=("至", "到", "~", "～", "\u2013", "\u2014", "-"),
    list_joiners=("、", "及", "和", "與", "以及", "，", ","),
    # Blocklist: characters that, when immediately preceding 圖, indicate 圖
    # is the head noun of a compound (diagram/map/chart) rather than a figure
    # label prefix. Passes through verbal references (參見圖, 如圖, 根據圖)
    # and view-type figures (俯視圖, 剖視圖, 立體圖, 爆炸圖).
    #   地 → 地圖 (map)          縮 → 縮圖 (thumbnail)
    #   意 → 示意圖 (schematic)  程 → 流程圖 (flowchart)
    #   構 → 架構圖 (framework)  略 → 略圖 (outline)
    #   草 → 草圖 (sketch)       藍 → 藍圖 (blueprint)
    #   版 → 版圖 (layout)       拼 → 拼圖 (puzzle)
    #   製 → 製圖 (drafting)
    left_boundary_guard=r"(?<![地縮意程構略草藍版拼製])",
    case_insensitive=False,
)

CN_CONFIG = FigureParserConfig(
    name="cn",
    prefix_pattern=r"(?:图|附图)",
    suffix_prefix_pattern=r"第",
    range_operators=("至", "到", "~", "～", "\u2013", "\u2014", "-"),
    list_joiners=("、", "及", "和", "与", "以及", "，", ","),
    # Blocklist (simplified equivalents): characters that, when immediately
    # preceding 图, indicate 图 is the head noun of a compound rather than
    # a figure label prefix.
    #   地 → 地图 (map)          缩 → 缩图 (thumbnail)
    #   意 → 示意图 (schematic)  程 → 流程图 (flowchart)
    #   构 → 架构图 (framework)  略 → 略图 (outline)
    #   草 → 草图 (sketch)       蓝 → 蓝图 (blueprint)
    #   版 → 版图 (layout)       拼 → 拼图 (puzzle)
    #   制 → 制图 (drafting)
    left_boundary_guard=r"(?<![地缩意程构略草蓝版拼制])",
    case_insensitive=False,
)

US_PARSER = FigureRefParser(US_CONFIG)
TW_PARSER = FigureRefParser(TW_CONFIG)
CN_PARSER = FigureRefParser(CN_CONFIG)
