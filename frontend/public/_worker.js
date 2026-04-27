// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
//
// Cloudflare Pages single-file Worker.
//
// Handles /api/report (anonymous error-report endpoint) and falls
// every other request through to Pages' static-asset serving via
// env.ASSETS.fetch. This single-file pattern is the well-supported
// path for `wrangler pages deploy <dir>` workflows, where directory-
// based functions/ detection is unreliable.
//
// Why GitHub Issues (instead of a custom DB):
//   - Maintainer (and Claude Code via gh CLI) reads reports as
//     `gh issue list --label report` — no separate UI to build.
//   - GitHub's issue UI handles search, labels, comments, mobile
//     notifications, and reactions for triage.
//   - Issues live in the private Patent-Lint repo, so they're
//     maintainer-only.
//
// Env vars (set in Cloudflare Pages dashboard):
//   GITHUB_ISSUES_TOKEN   fine-grained PAT scoped to Issues:Write
//                         on kwisschen/Patent-Lint only
//   GITHUB_ISSUES_REPO    "kwisschen/Patent-Lint" (defaults if unset)

const ALLOWED_ORIGIN = "https://patentlint.com";
// 16 KB cap accommodates the richer per-check extractor payloads
// (up to 5 findings × ~300 bytes each + aggregate fields). Worst-case
// observed ~3 KB; cap leaves comfortable headroom while still
// rejecting spam-sized bodies. Well under GitHub Issues 64 KB body
// limit.
const MAX_BODY_BYTES = 16 * 1024;
const DEFAULT_REPO = "kwisschen/Patent-Lint";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/report") {
      if (request.method === "OPTIONS") {
        return new Response(null, { status: 204, headers: corsHeaders() });
      }
      if (request.method === "POST") {
        return handleReport(request, env);
      }
      return json({ ok: false, reason: "method_not_allowed" }, 405);
    }

    // Everything else: serve static assets.
    return env.ASSETS.fetch(request);
  },
};

async function handleReport(request, env) {
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
    console.error("github issue create failed:", ghResponse.status, await ghResponse.text());
    return json({ ok: false, reason: "github_create_failed" }, 502);
  }

  return json({ ok: true }, 202);
}

function buildIssue(payload) {
  const checkKey = payload.check_key;
  const fingerprint =
    typeof payload.fixture_shape_hash === "string"
      ? ` (${payload.fixture_shape_hash})`
      : "";
  const title = `[report] ${checkKey}${fingerprint}`;

  // Render the payload as pretty JSON inside a fenced ```json block.
  // Top-level keys are sorted for stable diffs across reports; nested
  // findings arrays are preserved as objects (the previous flat
  // `${k}: ${v}` template stringified arrays via Array.prototype.toString,
  // which collapses every finding to `[object Object]`).
  const sortedPayload = Object.fromEntries(
    Object.keys(payload)
      .sort()
      .map((k) => [k, payload[k]]),
  );
  const json_block = JSON.stringify(sortedPayload, null, 2);

  const body = [
    "Anonymous error report submitted via the ReportModal.",
    "",
    "```json",
    json_block,
    "```",
    "",
    "_Submitted via `POST /api/report`. De-identified payload only — no full claim text, no full paragraphs, no email, no IP. See Privacy §6._",
  ].join("\n");

  const labels = ["report"];
  if (
    typeof payload.jurisdiction === "string" &&
    /^[a-z]{2,3}$/i.test(payload.jurisdiction)
  ) {
    labels.push(payload.jurisdiction.toLowerCase());
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
