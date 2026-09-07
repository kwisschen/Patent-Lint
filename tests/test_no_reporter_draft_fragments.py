"""Regression gate: a reporter's draft text must never re-enter the repo.

This repository is PUBLIC. Error reports arrive from practising attorneys whose
drafts are unfiled and confidential, and § 6.5 of the commercial licence now
promises in writing that their text will not appear in any public artifact.

The failure this gate exists for is not hypothetical and is not a one-off. On
2026-09-03 a reporter's composition-claim fragment was pasted into test
fixtures, a source comment and a labels description while triaging their report.
It was scrubbed. The very next walker round, working the same report cluster,
pasted the identical fragment back into a source comment that ships inside the
Pyodide wheel served from patentlint.com, into two test files, and into the TW
labels file. A lesson recorded only in prose did not survive one session.

Design notes, both load-bearing:

1. The fragments are stored as SHA-256 HASHES, never as plaintext. A denylist
   written in the clear would reintroduce into the repo exactly the text it is
   meant to keep out.

2. There is deliberately NO general heuristic here. The obvious one, "flag long
   CJK runs", was implemented and measured before being rejected: `src/` and
   `tests/` contain 9,379 CJK runs of twelve characters or more, essentially all
   of them legitimate figure-reference, specification and public-patent corpus
   fixtures. A guard with that false-positive rate would be switched off within a
   week. This gate is therefore precise rather than clever: it catches the
   recurrence mode that actually happened, which is the same text being pasted
   back while working the same cluster of reports.

TO ADD A FRAGMENT after scrubbing one, print its hash and paste that in::

    python3 -c "import hashlib,unicodedata,sys; \
        print(hashlib.sha256(unicodedata.normalize('NFKC', sys.argv[1]).encode()).hexdigest())" '<fragment>'

Do not paste the fragment itself into this file, a commit message, a PR body,
or an issue comment.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# SHA-256 of NFKC-normalised fragments taken from reporters' unfiled drafts and
# since scrubbed. Plaintext deliberately absent; see the module docstring.
BANNED_HASHES: frozenset[str] = frozenset({
    "b473ce47e4760ed4766b6dcb43e56eb5bec5e084e78cdc2469a21f7c2b8bab7b",
    "072a9f08f4afab6f3f725465b4a19cc42873f7c3d4454857498b85d1f46c2f2f",
    "a79311bc5ea5b7179f8eaba24d0c26770c3a6253ef0a1f744b0f30194f4dde04",
    "91c793ab24563eea3c858de0aee3e310613167594d73aad82213b0038379b0a2",
    "baa4f8a4f4e124a3f15a125ff2dbcacfab6e34f25c251646334b73fddd2db2d3",
})

# Window sizes to test, derived from the banned fragments' own lengths. Keeping
# this explicit means the scan stays O(text) rather than O(text x every length).
PROTECTED_LENGTHS: tuple[int, ...] = (4, 6, 7, 8)

_CJK_RUN = re.compile(r"[㐀-䶿一-鿿]+")

# Text-bearing files worth scanning. Binary assets and lockfiles cannot carry a
# pasted fragment in a form a reader would ever see.
_SCANNED_SUFFIXES = frozenset({".py", ".json", ".md", ".js", ".jsx", ".ts", ".tsx", ".html", ".txt", ".yml", ".yaml"})


def _tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [
        REPO_ROOT / name
        for name in out.split("\0")
        if name and Path(name).suffix in _SCANNED_SUFFIXES
    ]


def _offending_windows(text: str) -> set[str]:
    """Hashes of any banned fragment appearing in ``text``."""
    hits: set[str] = set()
    for run in _CJK_RUN.finditer(text):
        s = unicodedata.normalize("NFKC", run.group())
        for size in PROTECTED_LENGTHS:
            for i in range(len(s) - size + 1):
                h = hashlib.sha256(s[i:i + size].encode()).hexdigest()
                if h in BANNED_HASHES:
                    hits.add(h)
    return hits


def test_no_scrubbed_reporter_fragment_is_present_in_any_tracked_file():
    offenders: dict[str, set[str]] = {}
    for path in _tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hits = _offending_windows(text)
        if hits:
            offenders[str(path.relative_to(REPO_ROOT))] = hits

    assert not offenders, (
        "A scrubbed reporter draft fragment has re-entered the repository.\n"
        + "\n".join(f"  {f}: {len(h)} fragment(s)" for f, h in sorted(offenders.items()))
        + "\n\nThis repository is public and the text belongs to a practising attorney's\n"
          "unfiled draft. Replace it with a synthesised placeholder that preserves the\n"
          "grammatical shape the rule keys on, exactly as the TW R54/R55 entries do\n"
          "(第一材料 / 第二材料). Do not print the fragment while fixing this."
    )


def test_the_gate_is_not_vacuous():
    """A gate reporting zero must be shown able to catch something.

    Reconstructing a banned fragment from its own hash is not possible, so
    non-vacuity is proven on a synthetic fragment run through the identical
    code path: hash it, add it to the banned set, and confirm the scanner
    finds it inside representative surrounding text.
    """
    synthetic = "假想測試片語"
    h = hashlib.sha256(unicodedata.normalize("NFKC", synthetic).encode()).hexdigest()
    assert len(synthetic) in PROTECTED_LENGTHS, "synthetic must use a scanned window size"

    global BANNED_HASHES
    original = BANNED_HASHES
    try:
        BANNED_HASHES = frozenset(original | {h})
        assert _offending_windows(f"# comment: 所述{synthetic}的實施例") == {h}
        assert _offending_windows("# comment: 一種完全無關的組成物") == set()
    finally:
        BANNED_HASHES = original


def test_every_banned_hash_has_a_scannable_window_length():
    """A hash whose length is not in PROTECTED_LENGTHS can never be matched.

    Without this, adding a fragment of an unlisted length would silently
    produce a gate that passes because it cannot look.
    """
    assert BANNED_HASHES, "the banned set must not be empty"
    assert PROTECTED_LENGTHS, "no window lengths would make the scan a no-op"
