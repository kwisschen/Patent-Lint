// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
//
// Vercel Edge Function — anonymous error-report endpoint.
// Reads payloads POSTed by ReportModal, validates origin + size + JSON
// shape, and forwards a sanitized GitHub Issues create call. Runs at
// the Vercel Edge runtime (Web Standard Request/Response API).
//
// Why GitHub Issues (instead of a custom DB):
//   - Maintainer (and scheduled automation via gh CLI) reads reports as
//     `gh issue list --label report` — no separate UI to build.
//   - GitHub's issue UI handles search, labels, comments, mobile
//     notifications, and reactions for triage.
//   - Issues live in the private kwisschen/patentlint-reports repo
//     (split out from the public code repo on 2026-06-17), so the
//     de-identified report payloads are maintainer-only — not visible
//     to the public even though the code repo is public.
//
// Env vars (set in Vercel dashboard → Settings → Environment Variables):
//   GITHUB_ISSUES_TOKEN   fine-grained PAT scoped to Issues:Write
//                         on kwisschen/patentlint-reports only
//   GITHUB_ISSUES_REPO    "kwisschen/patentlint-reports" (defaults if unset)

export const config = {
  runtime: 'edge',
};

// Origins permitted to POST /api/report. Production is patentlint.com;
// patent-lint.vercel.app is the Vercel default deployment URL. Other
// origins get 403 (anti-spam — this endpoint backs a GitHub Issues
// tracker we don't want strangers writing into).
const ALLOWED_ORIGINS = new Set([
  "https://patentlint.com",
  "https://patent-lint.vercel.app",
]);
const DEFAULT_CORS_ORIGIN = "https://patentlint.com";
// 32 KB cap accommodates the structured per-check extractor payload
// (up to 5 findings × ~300 bytes each + aggregate fields, worst-case
// observed ~3 KB) PLUS the now-larger free-form user comment (up to
// 12000 chars from the modal). bodyText.length counts characters, so
// this is a generous ceiling that still rejects spam-sized bodies; the
// user-comment truncation below is what actually bounds the GitHub
// issue-body size (well under GitHub's 64 KB limit even for CJK).
const MAX_BODY_BYTES = 32 * 1024;
const DEFAULT_REPO = "kwisschen/patentlint-reports";

export default async function handler(request) {
  const origin = request.headers.get("origin") ?? "";
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders(origin) });
  }
  if (request.method === "POST") {
    return handleReport(request, origin);
  }
  return json({ ok: false, reason: "method_not_allowed" }, 405, origin);
}

async function handleReport(request, origin) {
  if (origin && !ALLOWED_ORIGINS.has(origin)) {
    return json({ ok: false, reason: "origin_not_allowed" }, 403, origin);
  }

  const ct = request.headers.get("content-type") ?? "";
  if (!ct.includes("application/json")) {
    return json({ ok: false, reason: "expected_application_json" }, 415, origin);
  }

  const bodyText = await request.text();
  if (bodyText.length > MAX_BODY_BYTES) {
    return json({ ok: false, reason: "payload_too_large" }, 413, origin);
  }

  let payload;
  try {
    payload = JSON.parse(bodyText);
  } catch {
    return json({ ok: false, reason: "invalid_json" }, 400, origin);
  }
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    return json({ ok: false, reason: "body_not_object" }, 400, origin);
  }
  if (typeof payload.check_key !== "string" || payload.check_key.length === 0) {
    return json({ ok: false, reason: "missing_check_key" }, 400, origin);
  }

  const token = process.env.GITHUB_ISSUES_TOKEN;
  if (!token) {
    return json({ ok: false, reason: "endpoint_not_configured" }, 503, origin);
  }
  const repo = process.env.GITHUB_ISSUES_REPO || DEFAULT_REPO;

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
    return json({ ok: false, reason: "github_unreachable" }, 502, origin);
  }

  if (!ghResponse.ok) {
    console.error("github issue create failed:", ghResponse.status, await ghResponse.text());
    return json({ ok: false, reason: "github_create_failed" }, 502, origin);
  }

  return json({ ok: true }, 202, origin);
}

// Cap the optional user-comment field server-side as defence in depth
// (the modal caps at 12000 chars; this 14000 ceiling leaves headroom
// for a non-modal client). Anything beyond gets truncated — the
// alternative would be to reject the whole report, but losing a useful
// diagnostic to a stray over-long comment is the wrong trade. 14000
// chars (≈42 KB if all CJK) + the structured payload stays under
// GitHub's 64 KB issue-body limit.
const USER_COMMENT_MAX_CHARS = 14000;

function buildIssue(payload) {
  const checkKey = payload.check_key;
  const fingerprint =
    typeof payload.fixture_shape_hash === "string"
      ? ` (${payload.fixture_shape_hash})`
      : "";
  const title = `[report] ${checkKey}${fingerprint}`;

  // Separate the optional user-comment from the structural diagnostic
  // payload. The diagnostic stays in the fenced JSON block (its
  // contract is "de-identified structural metadata"); the comment
  // renders as its own block-quoted section below, both for visual
  // separation during triage AND so the trust contract of the JSON
  // block ("only de-identified fields") isn't muddied by free-form
  // text.
  const { user_comment: rawUserComment, ...diagnosticPayload } = payload;
  const userComment =
    typeof rawUserComment === "string"
      ? rawUserComment.trim().slice(0, USER_COMMENT_MAX_CHARS)
      : "";

  // Render the diagnostic payload as pretty JSON inside a fenced
  // ```json block. Top-level keys are sorted for stable diffs across
  // reports; nested findings arrays are preserved as objects (a flat
  // `${k}: ${v}` template would stringify arrays via Array.prototype
  // .toString, which collapses every finding to `[object Object]`).
  const sortedPayload = Object.fromEntries(
    Object.keys(diagnosticPayload)
      .sort()
      .map((k) => [k, diagnosticPayload[k]]),
  );
  const json_block = JSON.stringify(sortedPayload, null, 2);

  const sections = [
    "Anonymous error report submitted via the ReportModal.",
    "",
    "```json",
    json_block,
    "```",
    "",
    "_Submitted via `POST /api/report`. De-identified payload only — no full claim text, no full paragraphs, no email, no IP. See Privacy §6._",
  ];

  if (userComment) {
    // Block-quote each line of the comment with `> ` so any markdown
    // (including injected `</details>` / triple-backticks / image
    // syntax) renders as plain text rather than disrupting the issue
    // body.
    const quoted = userComment
      .split("\n")
      .map((line) => `> ${line}`)
      .join("\n");
    sections.push(
      "",
      "---",
      "",
      "**User comment** _(free-form, not de-identified — typed by the reporter)_:",
      "",
      quoted,
    );
  }

  const body = sections.join("\n");

  const labels = ["report"];
  if (
    typeof payload.jurisdiction === "string" &&
    /^[a-z]{2,3}$/i.test(payload.jurisdiction)
  ) {
    labels.push(payload.jurisdiction.toLowerCase());
  }

  return { title, body, labels };
}

function corsHeaders(origin) {
  // Echo back the request's origin if it's in the allowlist; otherwise
  // fall back to the production domain. Critical for CORS to work
  // correctly across multiple permitted origins (browsers reject a
  // mismatch between request Origin and Access-Control-Allow-Origin).
  const allowed = origin && ALLOWED_ORIGINS.has(origin) ? origin : DEFAULT_CORS_ORIGIN;
  return {
    "access-control-allow-origin": allowed,
    "access-control-allow-methods": "POST, OPTIONS",
    "access-control-allow-headers": "content-type",
    "access-control-max-age": "86400",
  };
}

function json(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      ...corsHeaders(origin),
    },
  });
}
