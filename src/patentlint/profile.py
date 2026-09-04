"""Deployment profile - per-deployment suppression of advisory § 112 findings.

A *profile* lets a self-hosted deployment silence the advisory antecedent-basis
(§ 112(b)) and specification-support (§ 112(a)) findings for terms that are
house vocabulary rather than drafting defects, without forking the engine.
Deployment-specific behaviour is DATA, not a fork: every deployment runs the
same build, and the profile is a JSON file the deployment points at.

Activation is opt-in via the ``PATENTLINT_PROFILE`` environment variable.
With the variable unset - which is the case for the public web tier, where
Pyodide has no environment to read - every function here is a no-op and
behaviour is byte-identical to an unprofiled build.

Scope is deliberately limited to the two advisory lists. Both are in
``rubric.ADVISORY_REVIEW_KEYS`` and therefore carry zero grade impact, so
suppression provably cannot move a document's grade. Suppressing a
grade-bearing check would require regrading and is out of scope for v1.

Profile format::

    {
      "version": 1,
      "name": "Example IP",
      "suppress_terms": {
        "*":  ["shared house term"],
        "CN": ["控制模块"],
        "US": ["controller unit"]
      }
    }

``suppress_terms`` also accepts a flat list, which is sugar for ``{"*": [...]}``.

Matching is exact after NFKC + casefold + strip normalisation, against BOTH
the finding's cleaned ``term`` and its ``reference_form``. Matching the
reference form matters because the reporter-facing surfaces render
``reference_form || term``, so the string a reader copies out of a report is
usually the reference form, not the cleaned term.
"""

from __future__ import annotations

import json
import os
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

ENV_VAR = "PATENTLINT_PROFILE"
SUPPORTED_VERSIONS = frozenset({1})
_ALL = "*"

# Rejecting unknown keys is deliberate. A profile whose typo'd key is silently
# dropped is a gate that reports success while doing nothing - the exact
# failure class that let the CN spec-support gate compare noise to noise for
# months. Fail loudly at load instead.
_TOP_LEVEL_KEYS = frozenset({"version", "name", "suppress_terms", "notes"})

T = TypeVar("T")


class ProfileError(ValueError):
    """Raised when a profile file is missing, malformed, or unsupported."""


def _normalize(value: str) -> str:
    """Fold a term to its comparison form (width, case, and edge whitespace)."""
    return unicodedata.normalize("NFKC", value).casefold().strip()


@dataclass(frozen=True)
class Profile:
    """A loaded, validated deployment profile."""

    name: str = ""
    # jurisdiction code (or "*") -> normalised terms to suppress
    suppress_terms: dict[str, frozenset[str]] = field(default_factory=dict)

    def suppressed_for(self, jurisdiction: str) -> frozenset[str]:
        """Normalised terms suppressed for ``jurisdiction``, plus the "*" set."""
        shared = self.suppress_terms.get(_ALL, frozenset())
        specific = self.suppress_terms.get(jurisdiction.upper(), frozenset())
        return shared | specific

    @property
    def is_empty(self) -> bool:
        return not any(self.suppress_terms.values())


def _parse_suppress_terms(raw: Any) -> dict[str, frozenset[str]]:
    if raw is None:
        return {}
    if isinstance(raw, list):
        raw = {_ALL: raw}
    if not isinstance(raw, dict):
        msg = "'suppress_terms' must be a list or an object keyed by jurisdiction"
        raise ProfileError(msg)

    parsed: dict[str, frozenset[str]] = {}
    for key, terms in raw.items():
        if not isinstance(terms, list) or not all(isinstance(t, str) for t in terms):
            msg = f"'suppress_terms.{key}' must be a list of strings"
            raise ProfileError(msg)
        normalized = {_normalize(t) for t in terms if _normalize(t)}
        if normalized:
            parsed[key if key == _ALL else key.upper()] = frozenset(normalized)
    return parsed


def parse_profile(data: Any, *, source: str = "<profile>") -> Profile:
    """Validate a decoded profile document. Raises ``ProfileError`` on any fault."""
    if not isinstance(data, dict):
        msg = f"{source}: profile must be a JSON object"
        raise ProfileError(msg)

    unknown = set(data) - _TOP_LEVEL_KEYS
    if unknown:
        msg = f"{source}: unknown profile key(s): {', '.join(sorted(unknown))}"
        raise ProfileError(msg)

    version = data.get("version")
    if version not in SUPPORTED_VERSIONS:
        msg = (
            f"{source}: unsupported profile version {version!r} "
            f"(supported: {sorted(SUPPORTED_VERSIONS)})"
        )
        raise ProfileError(msg)

    name = data.get("name", "")
    if not isinstance(name, str):
        msg = f"{source}: 'name' must be a string"
        raise ProfileError(msg)

    try:
        suppress = _parse_suppress_terms(data.get("suppress_terms"))
    except ProfileError as exc:
        raise ProfileError(f"{source}: {exc}") from exc

    return Profile(name=name, suppress_terms=suppress)


def load_profile_file(path: str | os.PathLike[str]) -> Profile:
    """Load and validate a profile from ``path``."""
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"cannot read profile at {p}: {exc}"
        raise ProfileError(msg) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"{p}: invalid JSON: {exc}"
        raise ProfileError(msg) from exc
    return parse_profile(data, source=str(p))


_CACHE: dict[tuple[str, int], Profile] = {}


def active_profile() -> Profile | None:
    """The profile named by ``PATENTLINT_PROFILE``, or ``None`` if unset.

    Cached on (path, mtime_ns) so an edited profile is picked up on the next
    analysis without a restart.
    """
    path = os.environ.get(ENV_VAR, "").strip()
    if not path:
        return None
    try:
        mtime = Path(path).stat().st_mtime_ns
    except OSError as exc:
        msg = f"cannot stat profile at {path}: {exc}"
        raise ProfileError(msg) from exc
    key = (path, mtime)
    if key not in _CACHE:
        _CACHE[key] = load_profile_file(path)
    return _CACHE[key]


def _term_matches(candidates: Iterable[str | None], suppressed: frozenset[str]) -> bool:
    return any(c and _normalize(c) in suppressed for c in candidates)


def suppress_findings(
    items: list[T],
    jurisdiction: str,
    *,
    candidates: Callable[[T], Iterable[str | None]],
    profile: Profile | None = None,
) -> list[T]:
    """Drop findings whose term is suppressed for ``jurisdiction``.

    ``candidates`` yields every surface string a profile might have used to
    name the finding (its cleaned term and its reference form). Returns
    ``items`` unchanged - the identical object - when no profile is active, so
    the unprofiled path costs one dict lookup.
    """
    prof = profile if profile is not None else active_profile()
    if prof is None or prof.is_empty:
        return items
    suppressed = prof.suppressed_for(jurisdiction)
    if not suppressed:
        return items
    return [it for it in items if not _term_matches(candidates(it), suppressed)]


def suppress_antecedent(items: list[Any], jurisdiction: str) -> list[Any]:
    """Filter advisory antecedent-basis findings (dicts with term/reference_form)."""
    return suppress_findings(
        items,
        jurisdiction,
        candidates=lambda d: (d.get("term"), d.get("reference_form")),
    )


def suppress_spec_support(items: list[Any], jurisdiction: str) -> list[Any]:
    """Filter advisory spec-support findings (``UnsupportedTerm.phrase``)."""
    return suppress_findings(
        items,
        jurisdiction,
        candidates=lambda t: (getattr(t, "phrase", None),),
    )
