# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""EPC corpus puller — fetches English EP-A1 drafts from EPO OPS.

Pulls a stratified sample of English-language EP-A1 (pre-grant
publication) documents from the EPO Open Patent Services (OPS) v3.2
REST API, downloads full description + claims for each, writes them
into ``tests/fixtures/epc/local/`` (gitignored), and produces a
manifest JSON with the document IDs + CPC subclasses for the
downstream walker-FP calibration pass.

Credential discovery:

  1. ``OPS_CONSUMER_KEY`` + ``OPS_CONSUMER_SECRET`` env vars (preferred —
     no file read)
  2. ``~/.config/patentlint/ops.env`` (KEY=value format)
  3. ``--credentials <path>`` CLI flag

Usage:
  python3 tests/eval/epc_corpus_pull.py --target 200
  python3 tests/eval/epc_corpus_pull.py --target 10 --dry-run

Outputs:
  - tests/fixtures/epc/local/EP*.txt — one file per draft (raw text)
  - tests/fixtures/epc/local/manifest.json — list of pulled docs +
    CPC subclasses + word counts

EPO OPS rate limits at the Non-paying tier:
  - 4 GB / week quota (more than enough for 200 drafts)
  - Per-second request cap; the puller paces requests via a token bucket

Statute / API references:
  - https://developers.epo.org/ops-v3-2/apis (OAuth2 + endpoints)
  - https://www.epo.org/searching-for-patents/data/web-services/ops.html
  - Espacenet biblio query syntax: https://worldwide.espacenet.com/help
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


# --- OPS API constants -------------------------------------------------------

OPS_TOKEN_URL = "https://ops.epo.org/3.2/auth/accesstoken"
# Bare /search returns just publication-references (lightweight); pagination
# via X-OPS-Range header, not URL param.
OPS_SEARCH_URL = "https://ops.epo.org/3.2/rest-services/published-data/search"
OPS_PUBLISHED_BASE = "https://ops.epo.org/3.2/rest-services/published-data/publication/epodoc/{pub_no}/{section}"

# Token bucket pacing — EPO non-paying tier doesn't publish exact limits
# but practitioner reports converge on ~1 request / second sustained.
REQUEST_INTERVAL_SECONDS = 1.0

# Search query — English EP publications from 2024+. OPS CQL doesn't
# accept `pk` as an index name (CLIENT.InvalidIndex), so kind-code (A1
# vs B1 etc.) filtering happens client-side after fetch. `pn=EP*` alone
# triggers HTTP 413 (millions of results); the date+CPC combo bounds
# each subclass query to a few hundred results.
SEARCH_QUERY = "pn=EP4* AND pd>=20240101"

# CPC subclasses to stratify across so the corpus isn't biased toward one
# field. ~5 drafts per subclass × 40 subclasses = ~200 target. Picked to
# span the major technical fields per EPO classification (mechanical,
# electrical, chemical, software, biotech).
CPC_SUBCLASSES = [
    "A61B", "A61K", "A61M", "A61N",          # medical
    "B01J", "B23K", "B25J", "B29C", "B60L",  # mechanical + transport
    "C07C", "C07D", "C07K", "C08L", "C12N",  # chemistry + biotech
    "F01D", "F02M", "F16D", "F16H", "F24F",  # engines, machine elements
    "G01B", "G01N", "G02B", "G02F",          # measurement + optics
    "G06F", "G06K", "G06N", "G06Q", "G06T",  # software, AI, business
    "H01F", "H01L", "H01M", "H01R", "H01S",  # electronics, semiconductors
    "H02J", "H02K", "H02M",                  # power
    "H03F", "H03H", "H03K", "H03L",          # signal processing
    "H04B", "H04L", "H04N", "H04W",          # communications
]


# --- Credential loading ------------------------------------------------------


@dataclass
class OpsCredentials:
    consumer_key: str
    consumer_secret: str


def load_credentials(credentials_path: str | None) -> OpsCredentials:
    """Load OPS credentials in priority order: env vars → file → CLI path.

    Raises SystemExit with a clear message when no credentials are
    findable, so the user sees the expected setup steps.
    """
    env_key = os.environ.get("OPS_CONSUMER_KEY")
    env_secret = os.environ.get("OPS_CONSUMER_SECRET")
    if env_key and env_secret:
        return OpsCredentials(env_key, env_secret)

    candidate_paths = []
    if credentials_path:
        candidate_paths.append(Path(credentials_path))
    candidate_paths.append(Path.home() / ".config" / "patentlint" / "ops.env")

    for path in candidate_paths:
        if not path.exists():
            continue
        # KEY=value format, one per line
        text = path.read_text(encoding="utf-8")
        parsed: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            parsed[k.strip()] = v.strip().strip("'\"")
        key = parsed.get("OPS_CONSUMER_KEY")
        secret = parsed.get("OPS_CONSUMER_SECRET")
        if key and secret:
            return OpsCredentials(key, secret)

    print(
        "ERROR: No OPS credentials found. Set OPS_CONSUMER_KEY +\n"
        "OPS_CONSUMER_SECRET env vars, or create\n"
        "~/.config/patentlint/ops.env with KEY=value lines, or pass\n"
        "--credentials <path>.",
        file=sys.stderr,
    )
    raise SystemExit(2)


# --- OAuth2 token flow -------------------------------------------------------


def get_access_token(creds: OpsCredentials) -> str:
    """POST to OPS token endpoint with HTTP Basic auth, get bearer token.

    EPO OPS uses standard OAuth2 client_credentials flow. The access
    token is valid for ~20 minutes; the caller can re-call this on
    401 if a long-running session expires.
    """
    auth_bytes = f"{creds.consumer_key}:{creds.consumer_secret}".encode()
    auth_header = "Basic " + base64.b64encode(auth_bytes).decode()
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(
        OPS_TOKEN_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    return payload["access_token"]


# --- Search + fetch ----------------------------------------------------------


def search_publications(token: str, cpc_subclass: str, max_results: int = 25) -> list[str]:
    """Return EPO publication numbers matching the stratified query.

    Pagination via X-OPS-Range header per EPO OPS spec (NOT URL param).
    """
    query = f"{SEARCH_QUERY} AND cpc={cpc_subclass}"
    url = OPS_SEARCH_URL + "?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "X-OPS-Range": f"1-{max_results}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        # Surface server response body so we see exact error reason
        body = ""
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    # OPS biblio search returns a nested structure — extract publication numbers.
    results = (
        data.get("ops:world-patent-data", {})
        .get("ops:biblio-search", {})
        .get("ops:search-result", {})
        .get("ops:publication-reference", [])
    )
    if isinstance(results, dict):
        results = [results]
    pub_nos: list[str] = []
    for ref in results:
        doc = ref.get("document-id", {})
        if isinstance(doc, list):
            doc = doc[0]
        country = doc.get("country", {}).get("$", "")
        number = doc.get("doc-number", {}).get("$", "")
        kind = doc.get("kind", {}).get("$", "")
        if country == "EP" and number and kind == "A1":
            # Store as "EP4736802" (no kind code) — OPS epodoc fetch
            # rejects the concatenated "EP4736802A1" form. The kind
            # filter above ensures we only enqueue A1 publications.
            pub_nos.append(f"EP{number}")
    return pub_nos


def _fetch_section(token: str, pub_no: str, section: str) -> dict:
    """Fetch one section of a publication. OPS rejects the combined
    `biblio,description,claims` path with 400 — sections must be fetched
    individually."""
    url = OPS_PUBLISHED_BASE.format(pub_no=pub_no, section=section)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def fetch_full_text(token: str, pub_no: str) -> dict:
    """Fetch description + claims and return a merged document.

    Returns a synthetic structure mimicking the combined-fetch shape
    that the caller's extract_text expects, so the rest of the pipeline
    doesn't change.
    """
    description = _fetch_section(token, pub_no, "description")
    time.sleep(REQUEST_INTERVAL_SECONDS)
    claims = _fetch_section(token, pub_no, "claims")
    # Merge into a single OPS-shaped document
    merged_root = description.get("ops:world-patent-data", {})
    desc_ft = (merged_root.get("ftxt:fulltext-documents", {})
                          .get("ftxt:fulltext-document", {}))
    claims_root = claims.get("ops:world-patent-data", {})
    claims_ft = (claims_root.get("ftxt:fulltext-documents", {})
                            .get("ftxt:fulltext-document", {}))
    desc_ft["claims"] = claims_ft.get("claims", {})
    return description


def extract_text(full_text_doc: dict) -> str:
    """Flatten OPS full-text JSON into plain text for fixture storage.

    OPS has different shapes for description vs claims:
      - description: ftxt:fulltext-document.description.p[] (paragraph list)
      - claims: ftxt:fulltext-document.claims.claim.claim-text[] (claim list)

    A "CLAIMS" header is inserted before the claims so the EPC parser
    (``extract_claims_section_epc``) finds them.
    """
    sections: list[str] = []
    root = full_text_doc.get("ops:world-patent-data", {})
    ft_doc = (root.get("ftxt:fulltext-documents", {})
                  .get("ftxt:fulltext-document", {}))
    # Description — uses `p` paragraphs
    desc = ft_doc.get("description", {})
    if isinstance(desc, dict):
        desc_text = _flatten_paragraphs(desc, lang="EN")
        if desc_text:
            sections.append(desc_text)
    # Claims — uses `claim.claim-text[]` nested structure
    claims = ft_doc.get("claims", {})
    if isinstance(claims, dict):
        claims_text = _flatten_claims(claims, lang="EN")
        if claims_text:
            sections.append("CLAIMS\n\n" + claims_text)
    return "\n\n".join(s for s in sections if s.strip())


def _flatten_paragraphs(block: dict, lang: str = "EN") -> str:
    """Flatten a description-style block with `p` paragraph nodes."""
    if not isinstance(block, dict):
        return ""
    block_lang = block.get("@lang", "").upper()
    if block_lang and block_lang != lang:
        return ""
    paragraphs = block.get("p")
    if paragraphs is None:
        return ""
    if isinstance(paragraphs, dict):
        paragraphs = [paragraphs]
    lines: list[str] = []
    for p in paragraphs:
        if isinstance(p, dict):
            text = p.get("$", "")
        else:
            text = str(p)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            lines.append(text)
    return "\n\n".join(lines)


def _flatten_claims(block: dict, lang: str = "EN") -> str:
    """Flatten the claims block — handles claim.claim-text[] nesting."""
    if not isinstance(block, dict):
        return ""
    block_lang = block.get("@lang", "").upper()
    if block_lang and block_lang != lang:
        return ""
    claim = block.get("claim")
    if claim is None:
        return ""
    if isinstance(claim, dict):
        claim = [claim]
    lines: list[str] = []
    # OPS often packs all numbered claims into a single `claim` element's
    # `claim-text[]` array — claim 1's main text + bullets + sub-parts +
    # claim 2's main text + bullets + ... all in sequence. Boundaries
    # between numbered claims are inferred from "N. " prefixes at the
    # start of a claim-text element. Use `\n` between every text part
    # so the EPC parser's `^[\d{1,3}\.\s` boundary regex catches each
    # numbered claim start.
    for c in claim:
        if not isinstance(c, dict):
            continue
        texts = c.get("claim-text")
        if texts is None:
            continue
        if isinstance(texts, dict):
            texts = [texts]
        for t in texts:
            if isinstance(t, dict):
                txt = t.get("$", "")
            else:
                txt = str(t)
            txt = re.sub(r"\s+", " ", txt).strip()
            if not txt:
                continue
            # Insert blank line before a new numbered claim ("1." etc.)
            # to give the parser a clean newline-anchored start.
            if re.match(r"^\d{1,3}\.\s", txt) and lines:
                lines.append("")
            lines.append(txt)
    return "\n".join(lines)


# --- Main puller -------------------------------------------------------------


def pull_corpus(
    creds: OpsCredentials,
    target: int,
    output_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Pull a stratified EPC English corpus, return manifest dict."""
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "target": target,
        "pulled": [],
        "skipped": [],
        "errors": [],
    }

    if dry_run:
        print(f"DRY RUN — would pull {target} drafts across "
              f"{len(CPC_SUBCLASSES)} CPC subclasses into {output_dir}")
        manifest["dry_run"] = True
        return manifest

    token = get_access_token(creds)
    per_subclass = max(1, target // len(CPC_SUBCLASSES) + 1)

    pulled_count = 0
    for cpc in CPC_SUBCLASSES:
        if pulled_count >= target:
            break
        try:
            time.sleep(REQUEST_INTERVAL_SECONDS)
            pub_nos = search_publications(token, cpc, max_results=per_subclass)
        except Exception as e:
            manifest["errors"].append({"cpc": cpc, "phase": "search", "error": str(e)})
            continue
        for pub_no in pub_nos:
            if pulled_count >= target:
                break
            out_path = output_dir / f"{pub_no}.txt"
            if out_path.exists():
                manifest["skipped"].append({"pub": pub_no, "reason": "already_downloaded"})
                continue
            try:
                time.sleep(REQUEST_INTERVAL_SECONDS)
                doc = fetch_full_text(token, pub_no)
                text = extract_text(doc)
                if not text.strip():
                    manifest["skipped"].append({"pub": pub_no, "reason": "empty_text"})
                    continue
                out_path.write_text(text, encoding="utf-8")
                manifest["pulled"].append({
                    "pub": pub_no,
                    "cpc": cpc,
                    "word_count": len(text.split()),
                })
                pulled_count += 1
            except Exception as e:
                manifest["errors"].append({"pub": pub_no, "phase": "fetch", "error": str(e)})
                continue

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


# --- CLI ---------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull EPC English corpus from EPO OPS")
    parser.add_argument("--target", type=int, default=200, help="Target draft count")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/fixtures/epc/local"),
        help="Output directory (gitignored)",
    )
    parser.add_argument(
        "--credentials",
        type=str,
        default=None,
        help="Path to credentials env file (overrides ~/.config/patentlint/ops.env)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Don't actually call OPS")
    args = parser.parse_args()

    creds = load_credentials(args.credentials)
    manifest = pull_corpus(creds, args.target, args.output, dry_run=args.dry_run)

    print(
        f"Pulled: {len(manifest.get('pulled', []))} | "
        f"Skipped: {len(manifest.get('skipped', []))} | "
        f"Errors: {len(manifest.get('errors', []))}"
    )
    return 0 if manifest.get("pulled") else 1


if __name__ == "__main__":
    sys.exit(main())
