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

English (US) reporter text is scanned the same way in WORD windows: the text is
NFKC-normalised, lowercased and split into runs of ``[a-z0-9]``, so punctuation,
hyphens and comment markers do not hide a match, and every window of
``PROTECTED_WORD_LENGTHS`` consecutive words is hashed. To add one, hash each
six-word window of the scrubbed wording that is specific to the draft (leave
out windows that are only a generic term of art)::

    python3 -c "import hashlib,re,unicodedata,sys; \
        w=re.findall(r'[a-z0-9]+', unicodedata.normalize('NFKC', sys.argv[1]).lower()); \
        [print(hashlib.sha256(' '.join(w[i:i+6]).encode()).hexdigest()) for i in range(len(w)-5)]" '<wording>'

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
    # 2026-10-24, wave C rulings batch (#945/#953): the ruling shapes as
    # reported, replaced with synthesized ones.
    "0036cc7dfc66b05d585349ceace44da4f6c6603e1e4d45919a8a1b5c949bda03",
    "b696bf9e90f5c3f19f7218c70024c6aedb1ff45394c364db99ea0ad199f1f14b",
    # 2026-10-24, wave C TW spec-support batch: comment examples taken from
    # the reports while fixing them, replaced with synthesized ones before commit.
    "39f80661b9adb7248b52335152e18bde47b826769da76ba43ea6df6a98e25197",
    "c2ff8ee5f605ce5688e78d41e88aadb7ed245841c6af76c9528390a5762e5c76",
    "85a94c540001b705ca30990e2fb988c471cd98a1ec1aad99c3cfd7bdf2e810fc",
    "f2b21581d427bb6d9c0fb646f1d61c09fcaec79bd1b86c97df13dddf85026384",
    "bad03dad7713e0690bd981dc7ff98ee891ed9b7ce42e3544b8885b764d22d26b",
    "fb06b5f4f44469623df3e209b90f7fdc9f419a2ad6413af4c6a4bd407b60666b",
    "ebfb64c32505e200504f2a3c14b8a5dba8f751e531e38df461d69df8eca1eda1",
    "ca51c7e1950eeb4e129632149b2f4b2f301639f39b592e8ea496c0b071d75149",
    # 2026-09-29, reports #796 / #800 (TW D1): an element name quoted into a
    # shipped source comment while fixing the report.
    "4841f318b5bfa960370c76c9dbc70bfce4e010d374011c955470e3ffe441f292",
    "b473ce47e4760ed4766b6dcb43e56eb5bec5e084e78cdc2469a21f7c2b8bab7b",
    "072a9f08f4afab6f3f725465b4a19cc42873f7c3d4454857498b85d1f46c2f2f",
    "a79311bc5ea5b7179f8eaba24d0c26770c3a6253ef0a1f744b0f30194f4dde04",
    "91c793ab24563eea3c858de0aee3e310613167594d73aad82213b0038379b0a2",
    "baa4f8a4f4e124a3f15a125ff2dbcacfab6e34f25c251646334b73fddd2db2d3",
    # 2026-09-16, the #771-#788 batch (TW R62): seven fragments from one
    # reporter's two drafts, kept out of the code comments, tests and
    # round_history that the fix would otherwise have quoted.
    "ed6d266ee87a83d63c1574cdb311aebd23d6e9a64d7eb32ae885e745a795b75b",
    "24f071eb7dd2be9e0c24704a9c6767d7e7794b4dafe6cc01062c32871268d3a4",
    "e788f83f5acf7df1619d8b00db04c0628d4501d4fb8c1f4341c6bfa2c4f34cea",
    "32404e3735ddbf5223ac74e62e3b0781d2f77e63d405a1efa3a4eb9050bf1d74",
    "64b80ecf26e8db8ba4717fa4e29414e78b62d1c082e9e3b020790e9542aea942",
    "dd38c8e169e4f70963454cb04e25456e3c7ae80c69d12fe9d39d2542bbf17b29",
    "50effba522a950bc88d128adfdf3fb75e1e5e3e32f84009b159a6f718b50d8b7",
    # wave B (2026-10-24): four windows scrubbed before push.
    "86a0be339b0ce34a7446a3174c04d755683aa053bdccf42cfcff9e295600420d",
    "35ddc2cf26d656e1c92e233cc7f4dbcc94afe339a259020586dcb505c6377d92",
    "c8e575edda35d41fc9fc4fd2062e93652434b4e7926708845f45a61ebf800b7b",
    "c4c1084384bfefc464f8fdb709666f0336311eeaa0c73592a8a350bb87c580a9",
    # 2026-10-25, wave D (#853, #963-#966): report shapes that reached test
    # strings and code comments while fixing them, replaced before push.
    "9d3e1054e26768ec59abacba40e9223f21abb561f23c8a8c56f8ac9752570bf4",
    "85e75d00f29ccb847b18e164678a1b18bd2cb09804d0bdb7001b90216ad3e922",
    "f252a5cb1906f28ffa75a310ef591e758667424b7bfd0f43d521909cb528971b",
    "b47a68435a25d30bad974167798e7ee60a5b7654b383f5665e5295aab6dd7d3d",
    "197f37b0d0c8be393a4cc5e02a0c5b8d6cde9d09a0311fe55a26cf109737869e",
    "86fe21f35aba51ddef0462160fa2d2f2993f5034dc4c81b26db2cddbc120b62c",
    "e527c4f14d8776d59799bd5221203e4c09635c2788a55c8a66a1a884b1aab510",
})

# SHA-256 of six-word windows (see the module docstring) of English reporter
# wording that was scrubbed. Same rules as BANNED_HASHES: hashes only.
BANNED_LATIN_HASHES: frozenset[str] = frozenset({
    # 2026-10-27, wave O (#968, US R60): the reporter's element wording reached a
    # utils.py comment and a commit message; replaced with a synthesized example
    # before push. Windows of the claim clause, minus the bare term of art.
    "10c78897590901dbcb495dcdbff7f5087271e0fa3b2048346cb409a7e072a1b2",
    "cb7b8751f64ceea43a670647c109b6c3bc874549bfd3d5ecd9e37c2d5681aaa8",
    "ed057d9b95158ccc217293cbf8e0b5282df9cc05e745e312796484acd3c5f1a6",
    "f5377811f3706424dc83b3f5cd8cf3d9de1238d63e49230620132a714f1078e7",
    "6d27ea822544e11867c5bda02293251729d52b5329dd180a0760872284ff3756",
    "6c6cd8a5d8357854a98917c00dd8b6d9f1f487449ae510358c4556803dcf9825",
    "ab65bc2c789b714f037862e2038271b5be86c8527ea829e2cf750e266de1f9b1",
    "07964e496b509474a03b888a92a80a1539438ebcca390f71ab531ff8bde4eba2",
    "210a202d69df768e34f982cb2506f89ee7b25a7250871b0b427676532978e907",
    "e59fdadf160ae36dae92dd7b2e67d491b090ad059ff9ae19bb4139bcf0b46a98",
    "bd24541c6fda822236c3a005aae332d35cb854f24b56bce72c9ae24fb0a9db8a",
})

PROTECTED_WORD_LENGTHS: tuple[int, ...] = (6,)

_LATIN_WORD = re.compile(r"[a-z0-9]+")

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


def _offending_latin_windows(text: str) -> set[str]:
    """Hashes of any banned English word window appearing in ``text``."""
    if not BANNED_LATIN_HASHES:
        return set()
    words = _LATIN_WORD.findall(unicodedata.normalize("NFKC", text).lower())
    hits: set[str] = set()
    for size in PROTECTED_WORD_LENGTHS:
        for i in range(len(words) - size + 1):
            h = hashlib.sha256(" ".join(words[i:i + size]).encode()).hexdigest()
            if h in BANNED_LATIN_HASHES:
                hits.add(h)
    return hits


def test_no_scrubbed_reporter_fragment_is_present_in_any_tracked_file():
    offenders: dict[str, set[str]] = {}
    for path in _tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hits = _offending_windows(text) | _offending_latin_windows(text)
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


def test_the_latin_gate_is_not_vacuous():
    """The English branch catches a banned window through case, hyphens,
    parentheses and a comment line break, and nothing else."""
    synthetic = "a hypothetical twelve-lobe (HTL) bracket assembly"
    words = _LATIN_WORD.findall(synthetic.lower())
    h = hashlib.sha256(" ".join(words[:6]).encode()).hexdigest()

    global BANNED_LATIN_HASHES
    original = BANNED_LATIN_HASHES
    try:
        BANNED_LATIN_HASHES = frozenset(original | {h})
        assert _offending_latin_windows(
            "# includes A Hypothetical twelve-lobe\n# (HTL) Bracket mount"
        ) == {h}
        assert _offending_latin_windows("# a hypothetical twelve lobe bracket assembly") == set()
    finally:
        BANNED_LATIN_HASHES = original


def test_every_latin_hash_is_well_formed():
    assert BANNED_LATIN_HASHES, "the English banned set must not be empty"
    assert PROTECTED_WORD_LENGTHS, "no word window lengths would make the scan a no-op"
    assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in BANNED_LATIN_HASHES)


if __name__ == "__main__":
    # The commit-msg hook (.githooks/commit-msg) runs this on the message file:
    # commit messages are public too, and one carried reporter wording in wave O.
    import sys

    found = 0
    for name in sys.argv[1:]:
        body = Path(name).read_text(encoding="utf-8", errors="replace")
        found += len(_offending_windows(body) | _offending_latin_windows(body))
    if found:
        print(f"[commit-msg] {found} scrubbed reporter fragment(s) in the message; "
              "replace them with a synthesized example (do not print the fragment).",
              file=sys.stderr)
    sys.exit(1 if found else 0)
