// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// Anonymous error-report endpoint — Cloudflare Pages Function.
//
// Receives POST /api/report from the ReportModal in the frontend,
// forwards the structural diagnostic payload to GitHub Issues on
// the Patent-Lint repo, and returns { ok: true } or
// { ok: false, reason }.
//
// Why GitHub Issues (instead of a custom DB / admin UI):
//   - Maintainer (and Claude Code, via gh CLI) can read reports as
//     `gh issue list --label report` — no separate UI to build.
//   - GitHub's issue UI handles search, labels, comments, close
//     states, mobile notifications, and reactions for triage status.
//   - Issues live in a private repo, so they're maintainer-only.
//   - Free tier handles this trivially.
//
// Env vars (set in Cloudflare Pages dashboard):
//   GITHUB_ISSUES_TOKEN   fine-grained PAT, scoped to Issues:Write
//                         on kwisschen/Patent-Lint only
//   GITHUB_ISSUES_REPO    "kwisschen/Patent-Lint" (defaults if unset)
//
// Privacy invariants enforced here:
//   - No IP logging (we never read request.headers["cf-connecting-ip"]
//     or request.cf)
//   - No cookies set
//   - Origin gate (only patentlint.com may submit)
//   - Payload size capped at 8 KB (reports are small fingerprints)
//   - No content scrubbing — the modal previewed exactly what's in
//     the payload, so nothing is hidden from the user

const ALLOWED_ORIGIN = "https://patentlint.com";
const MAX_BODY_BYTES = 8 * 1024;
const DEFAULT_REPO = "kwisschen/Patent-Lint";

export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: corsHeaders(),
  });
}

export async function onRequestPost(context) {
  const { request, env } = context;

  const origin = request.headers.get("origin") ?? "";
  if (origin && origin !== ALLOWED_ORIGIN) {
    return json({ ok: false, reason: "origin_not_allowed" }, 403);
  }

  const ct = request.headers.get("content-type") ?? "";
  if (!ct.includes("application/json")) {
    return json({ ok: false, reason: "expected_application_json" }, 415);
  }

  const bodyText = await request.text();
  if (bodyText.length > MAX_BODY_BYTES) {
    return json({ ok: false, reason: "payload_too_large" }, 413);
  }

  let payload;
  try {
    payload = JSON.parse(bodyText);
  } catch {
    return json({ ok: false, reason: "invalid_json" }, 400);
  }
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    return json({ ok: false, reason: "body_not_object" }, 400);
  }
  if (typeof payload.check_key !== "string" || payload.check_key.length === 0) {
    return json({ ok: false, reason: "missing_check_key" }, 400);
  }

  const token = env.GITHUB_ISSUES_TOKEN;
  if (!token) {
    return json({ ok: false, reason: "endpoint_not_configured" }, 503);
  }
  const repo = env.GITHUB_ISSUES_REPO || DEFAULT_REPO;

  const issue = buildIssue(payload);

  let ghResponse;
  try {
    ghResponse = await fetch(`https://api.github.com/repos/${repo}/issues`, {
      method: "POST",
      headers: {
        accept: "application/vnd.github+json",
        authorization: `Bearer ${token}`,
        "user-agent": "patentlint-report-endpoint",
        "content-type": "application/json",
        "x-github-api-version": "2022-11-28",
      },
      body: JSON.stringify(issue),
    });
  } catch {
    return json({ ok: false, reason: "github_unreachable" }, 502);
  }

  if (!ghResponse.ok) {
    // GitHub returned 4xx or 5xx. Don't leak detail to the client;
    // the response body lands in Cloudflare's observability surface.
    console.error("github issue create failed:", ghResponse.status, await ghResponse.text());
    return json({ ok: false, reason: "github_create_failed" }, 502);
  }

  return json({ ok: true }, 202);
}

// Build the GitHub Issue payload. Title is short and greppable; body
// renders the structural fields as a markdown code block so future-
// you (or Claude reading via `gh issue view`) sees the exact wire
// shape.
function buildIssue(payload) {
  const checkKey = payload.check_key;
  const fingerprint = typeof payload.fixture_shape_hash === "string"
    ? ` (${payload.fixture_shape_hash})`
    : "";
  const title = `[report] ${checkKey}${fingerprint}`;

  // Sort keys for deterministic body output. Same fingerprint
  // shape produces identical issue body, regardless of object
  // iteration order.
  const sortedKeys = Object.keys(payload).sort();
  const lines = sortedKeys.map((k) => {
    const v = payload[k];
    const display = typeof v === "boolean" ? String(v) : v;
    return `${k}: ${display}`;
  });

  const body = [
    "Anonymous error report submitted via the ReportModal.",
    "",
    "```",
    ...lines,
    "```",
    "",
    "_Submitted via `POST /api/report`. No claim text, no draft contents, no IP logging — see Privacy Policy._",
  ].join("\n");

  // Labels: always `report`. Add jurisdiction label if present so
  // `gh issue list --label cn` works for jurisdiction-specific
  // triage. Labels must already exist on the repo to apply; if
  // they don't, the API call still succeeds but the label is
  // silently dropped (set up jurisdiction labels once in the
  // GitHub repo settings).
  const labels = ["report"];
  if (typeof payload.jurisdiction === "string" && /^[a-z]{2,3}$/.test(payload.jurisdiction)) {
    labels.push(payload.jurisdiction);
  }

  return { title, body, labels };
}

function corsHeaders() {
  return {
    "access-control-allow-origin": ALLOWED_ORIGIN,
    "access-control-allow-methods": "POST, OPTIONS",
    "access-control-allow-headers": "content-type",
    "access-control-max-age": "86400",
  };
}

function json(body, status) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      ...corsHeaders(),
    },
  });
}
