# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025 Christopher Chen
"""Brief Description of Drawings analysis.

Figure counting, sequential ordering, single-figure format, and prior art reference detection.
"""

import re

from patentlint.analysis.utils import _dx
from patentlint.models import CheckItem, FigureReference

_FIGURE_PATTERN = re.compile(
    r"(FIG(?:S)?\.?|Figure(?:s)?)\s*(\d+)(?:\(([a-zA-Z])\)|([a-zA-Z]))?"
    r"(?:\s*(?:-|~|to|and|through)\s*(?:(FIG(?:S)?\.?|Figure(?:s)?)\s*)?(\d+)(?:\(([a-zA-Z])\)|([a-zA-Z]))?)?",
    re.IGNORECASE,
)


def _truncate_to_words(line: str, max_words: int) -> str:
    words = line.split()
    return " ".join(words[:max_words])


def _extract_suffix(paren_group: str | None, bare_group: str | None) -> str:
    if paren_group:
        return paren_group.upper()
    if bare_group:
        return bare_group.upper()
    return ""


def count_figure_range(
    start_fig: str, end_fig: str, start_suffix: str, end_suffix: str
) -> int:
    """Count figures in a range (e.g., FIG. 1-5 or FIG. 2A-2D)."""
    start = int(start_fig)
    end = int(end_fig)

    if start == end and start_suffix and end_suffix:
        return ord(end_suffix[0]) - ord(start_suffix[0]) + 1
    return end - start + 1


def get_figure_count(text: str) -> int:
    """Total number of figures, considering only first 8 words of each line."""
    total = 0
    for line in text.split("\n"):
        truncated = _truncate_to_words(line, 8)
        for m in _FIGURE_PATTERN.finditer(truncated):
            start_suffix = _extract_suffix(m.group(3), m.group(4))
            end_fig = m.group(6)
            end_suffix = _extract_suffix(m.group(7), m.group(8))

            if end_fig is not None:
                total += count_figure_range(m.group(2), end_fig, start_suffix, end_suffix)
            else:
                total += 1
    return total


def extract_figure_references(text: str) -> list[FigureReference]:
    """Extract ordered list of figure references from drawings section."""
    refs: list[FigureReference] = []
    for line in text.split("\n"):
        trimmed = re.sub(r"^\[\d+\]\s*", "", line).strip()
        if not re.match(r"(?i)^(FIG(?:S)?\.?|Figure(?:s)?)\b", trimmed):
            continue

        truncated = _truncate_to_words(trimmed, 8)
        for m in _FIGURE_PATTERN.finditer(truncated):
            start_num = int(m.group(2))
            start_suffix = _extract_suffix(m.group(3), m.group(4))
            start_alpha = start_suffix[0] if start_suffix else " "

            end_fig_str = m.group(6)
            end_suffix = _extract_suffix(m.group(7), m.group(8))

            if end_fig_str is not None:
                end_num = int(end_fig_str)
                if start_num != end_num:
                    for i in range(start_num, end_num + 1):
                        refs.append(FigureReference(number=i))
                elif start_suffix and end_suffix:
                    end_alpha = end_suffix[0]
                    for alpha in range(ord(start_alpha), ord(end_alpha) + 1):
                        refs.append(FigureReference(number=start_num, suffix=chr(alpha)))
                else:
                    refs.append(FigureReference(number=start_num, suffix=start_alpha))
            else:
                refs.append(FigureReference(number=start_num, suffix=start_alpha))

    return refs


def are_figures_sequential(text: str) -> bool:
    """Check if figures are listed in sequential order."""
    refs = extract_figure_references(text)
    if not refs:
        return True

    prev = refs[0]
    for cur in refs[1:]:
        if cur.number == prev.number:
            if not prev.has_suffix or not cur.has_suffix:
                return False
            if ord(cur.suffix) != ord(prev.suffix) + 1:
                return False
        else:
            if cur.number != prev.number + 1:
                return False
        prev = cur
    return True


def compute_missing_figure_numbers(text: str) -> list[int]:
    """Return sorted gap-list of missing parent figure numbers in ``1..max``.

    Mirrors the CN ``check_figures_sequential`` shape (cn_abstract.py:129):
    collect parent numbers, compute ``range(1, max+1) - actual``. Sub-figure
    suffix ordering violations are handled by ``are_figures_sequential`` and
    are not reported here — this helper reports only the attorney-actionable
    gap subset (e.g. FIG. 1, FIG. 3 → ``[2]``).
    """
    refs = extract_figure_references(text)
    if not refs:
        return []
    numbers = {r.number for r in refs}
    max_n = max(numbers)
    return sorted(set(range(1, max_n + 1)) - numbers)


def is_single_figure(text: str) -> bool:
    """True if exactly one figure (FIG. 1 only, no FIG. 2+)."""
    pattern = re.compile(r"(?i)(FIG\.?|Fig\.?|Figure)\s*(\d+)")
    max_fig = 0
    found = False
    for m in pattern.finditer(text):
        fig_num = int(m.group(2))
        if fig_num > max_fig:
            max_fig = fig_num
        found = True
        if fig_num > 1:
            return False
    return found and max_fig == 1


def uses_wrong_label_for_single_figure(text: str) -> bool:
    """True if text uses 'FIG. 1' instead of 'The Figure' for a single-figure patent."""
    return bool(re.search(r"(?i)(FIG\.?|Fig\.?|Figure)\s*1", text))


def _extract_figure_ids(text: str) -> set[str]:
    """Extract all figure identifiers from text as a normalized set.

    Handles: FIG. N, FIGS. N-M, FIGS. N and M, FIG. Na / FIG. N(a),
    Figure N (full word). Returns identifiers like "1", "2A", "3".
    """
    ids: set[str] = set()
    for m in _FIGURE_PATTERN.finditer(text):
        start_num = int(m.group(2))
        start_suffix = _extract_suffix(m.group(3), m.group(4))

        end_fig_str = m.group(6)
        end_suffix = _extract_suffix(m.group(7), m.group(8))

        if end_fig_str is not None:
            end_num = int(end_fig_str)
            if start_num == end_num and start_suffix and end_suffix:
                # Alpha range: FIG. 2A-2D
                for alpha in range(ord(start_suffix[0]), ord(end_suffix[0]) + 1):
                    ids.add(f"{start_num}{chr(alpha)}")
            else:
                # Numeric range: FIG. 1-5
                for i in range(start_num, end_num + 1):
                    ids.add(str(i))
        else:
            if start_suffix:
                ids.add(f"{start_num}{start_suffix}")
            else:
                ids.add(str(start_num))

    return ids


def check_figure_cross_references(
    brief_description: str, detailed_description: str
) -> list[CheckItem]:
    """Check figure reference consistency between Brief Description and Detailed Description.

    Returns CheckItems for orphaned or undescribed figure references.
    """
    from patentlint.models import CheckItem

    if not brief_description.strip() and not detailed_description.strip():
        return []

    brief_figs = _extract_figure_ids(brief_description)
    detailed_figs = _extract_figure_ids(detailed_description)

    if not brief_figs and not detailed_figs:
        return []

    results: list[CheckItem] = []

    orphaned_brief = sorted(brief_figs - detailed_figs, key=_sort_fig_id)
    orphaned_detailed = sorted(detailed_figs - brief_figs, key=_sort_fig_id)

    if orphaned_brief:
        fig_list = ", ".join(orphaned_brief)
        results.append(CheckItem(
            status="amend",
            message=f"FIG(s). {fig_list} described in Brief Description of Drawings but not referenced in Detailed Description.",
            message_key="checks.figure_xref_orphaned_brief",
            details=fig_list,
            details_key="details.orphanedBriefFigures",
            details_params={"list": fig_list},
            diagnostics=_dx(
                orphan_count=len(orphaned_brief),
                total_brief=len(brief_figs),
                total_detailed=len(detailed_figs),
                orphans=orphaned_brief[:10],
                brief_figs_sample=sorted(brief_figs, key=_sort_fig_id)[:5],
                detailed_figs_sample=sorted(detailed_figs, key=_sort_fig_id)[:5],
            ),
        ))

    if orphaned_detailed:
        fig_list = ", ".join(orphaned_detailed)
        results.append(CheckItem(
            status="amend",
            message=f"FIG(s). {fig_list} referenced in Detailed Description but not described in Brief Description of Drawings.",
            message_key="checks.figure_xref_orphaned_detailed",
            details=fig_list,
            details_key="details.orphanedDetailedFigures",
            details_params={"list": fig_list},
            diagnostics=_dx(
                orphan_count=len(orphaned_detailed),
                total_brief=len(brief_figs),
                total_detailed=len(detailed_figs),
                orphans=orphaned_detailed[:10],
                brief_figs_sample=sorted(brief_figs, key=_sort_fig_id)[:5],
                detailed_figs_sample=sorted(detailed_figs, key=_sort_fig_id)[:5],
            ),
        ))

    if not orphaned_brief and not orphaned_detailed:
        results.append(CheckItem(
            status="pass",
            message="All figure references are consistent between Brief Description of Drawings and Detailed Description.",
            message_key="checks.figure_xref_pass",
        ))

    return results


def _sort_fig_id(fig_id: str) -> tuple[int, str]:
    """Sort key for figure IDs: numeric part first, then alpha suffix."""
    num_part = ""
    alpha_part = ""
    for ch in fig_id:
        if ch.isdigit():
            num_part += ch
        else:
            alpha_part += ch
    return (int(num_part) if num_part else 0, alpha_part)


def contains_prior_art_references(text: str) -> bool:
    """True if drawings section contains prior art references."""
    return bool(re.search(r"\bart\b|\bconventional\b|\btraditional\b|\bprior art\b", text, re.IGNORECASE))


_PRIOR_ART_MARKER_CN = re.compile(r"现有技术|已知技术|背景技术")
# Labeling pattern: a figure number followed/preceded by prior-art marker
# in a descriptive context. Covers 图N为/示出/是/显示 現有技術 and reverse.
_PRIOR_ART_LABEL_CN = re.compile(
    r"图\s*\d+[^\n。；]{0,20}?(?:现有技术|已知技术|背景技术)"
    r"|(?:现有技术|已知技术|背景技术)[^\n。；]{0,20}?图\s*\d+"
)


def contains_prior_art_references_cn(text: str) -> bool:
    """True if CN 附图说明 labels a specific figure as prior art.

    CNIPA 审查指南 第一部分第一章 §4.2 requires prior-art figures to be
    labeled. Only flags when a prior-art marker (现有技术/已知技术/背景技术)
    appears in proximity to a figure number (图N) — this excludes the
    common 附图说明 boilerplate preamble (``为了更清楚地说明本发明实施例或
    现有技术…``) which mentions 现有技术 conceptually without labeling
    any figure.
    """
    if not _PRIOR_ART_MARKER_CN.search(text):
        return False
    # Check each paragraph independently so the boilerplate preamble — which
    # mentions 现有技术 but references no specific figure — doesn't trigger.
    for para in text.split("\n"):
        if _PRIOR_ART_LABEL_CN.search(para):
            return True
    return False
