# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Per-draft LLM ensemble for PatentLint round 1 (Phase 2a + 2b).

Distinct from `llm_judges.py` (which is per-finding, vicinity-only, Haiku-primary):

- **Per-draft mode**: one LLM call covers all walker findings in a single
  claim's parent chain. The LLM sees full claim text (+ ancestor claims for
  dependent claims), letting it disambiguate references that span the chain.
- **Sonnet 4.6 PRIMARY** (Step 0 found Haiku misread `所述/該/前述` as
  introducing forms — Sonnet does not).
- **gpt-5-mini cross-family** check.
- **Opus 4.7 tiebreaker** on draft-level disagreement (≥3 finding-level
  category mismatches in the same draft → Opus re-judges the whole draft;
  Opus verdicts override).
- System prompt addresses the four Step 0 failure modes head-on with explicit
  few-shot rules:
  1. `所述/該/前述<noun>` are REFERENCE forms, not introductions.
  2. Possessive `X的Y` does NOT introduce X.
  3. Bare nouns in temporal/adverbial clauses don't introduce.
  4. Coordination introductions (`包括X和Y`) introduce; listings (`各X`) don't.

Reads ANTHROPIC_API_KEY + OPENAI_API_KEY from Patent-Analyst's .env (same
as `llm_judges.py`).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

ANALYST_ENV = Path("/Users/chrischen/Documents/Projects/Patent-Analyst/.env")

SONNET = "claude-sonnet-4-6"
OPUS = "claude-opus-4-7"
GPT_MINI = "gpt-5-mini"

VALID_CATEGORIES: set[str] = {
    "walker_fp",
    "coverage_gap",
    "legit_drafting_error",
    "diagnostic_mis_attribution",
    "ambig",
}

# Draft-level escalation trigger — proportional to draft size (2026-05-02 rev2).
#
# History:
# - Original: hard threshold = 3 (designed for Phase 2a fixtures with 5-15
#   findings/draft).
# - 2026-05-02 morning: lowered to 2 after borderline review (Sonnet 11/13
#   correct; gpt-5-mini 2/13). Intent: catch Sonnet's edge-case errors.
# - 2026-05-02 evening: Phase 2b smoke + full run revealed full-size drafts
#   have 30-50+ findings; threshold=2 escalated 80-85% of drafts on noise
#   (2 disagreements out of 50 = 4% noise, not real disagreement). Cost spike.
#
# Now proportional: max(2, ceil(findings_count * 0.15)). Small drafts keep
# threshold=2 (Phase 2a behavior); large drafts only escalate on substantive
# disagreement (≥15% finding-level mismatches). Quality preserved or improved
# (fewer spurious escalations on noise); cost roughly halved on large-draft
# corpora.
import math  # noqa: E402


def opus_escalation_threshold(findings_count: int) -> int:
    """Per-draft Opus escalation trigger, proportional to draft size."""
    return max(2, math.ceil(findings_count * 0.15))


def load_keys() -> tuple[str, str]:
    """Read both API keys from Patent-Analyst's .env."""
    if not ANALYST_ENV.exists():
        raise FileNotFoundError(f".env not found at {ANALYST_ENV}")
    text = ANALYST_ENV.read_text()
    keys = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        keys[k.strip()] = v.strip()
    anthropic = keys.get("ANTHROPIC_API_KEY")
    openai = keys.get("OPENAI_API_KEY")
    if not anthropic:
        raise RuntimeError("ANTHROPIC_API_KEY missing from .env")
    if not openai:
        raise RuntimeError("OPENAI_API_KEY missing from .env")
    return anthropic, openai


# ---------- system prompt v2 (Phase 2a iteration 1) ----------

SYSTEM_PROMPT_V2 = """You are auditing PatentLint's CN/TW antecedent-basis walker against a real patent draft. The walker fired N findings; you must classify each one based on the FULL claim chain provided. Apply the rules below MECHANICALLY — do not be creative or "fluent reader" generous.

# THE ONLY INTRODUCING PATTERNS

A claim term `X` is "introduced" if and only if ONE of these patterns occurs BEFORE the walker's flagged reference, in the same claim or any ancestor claim:

**Pattern A — Indefinite article**: `一<X>` / `一個<X>` / `一種<X>` / `多個<X>` / `多种<X>` (CN/TW). Or in TW old form: `一<X>` may appear as bare `X` only if it's the FIRST element of an explicit list opened by a head clause (Pattern B).

**Pattern B — Coordination listing under an explicit head**: `<head>，包括：X、Y、Z` / `<head>，包含X和Y` / `具有X以及Y`. The head clause is REQUIRED — it must explicitly say `包括` / `包含` / `具有` / `comprises` / `包括以下任一种` etc. The listed members X, Y, Z are introduced together.

**Nothing else introduces.** If you cannot find Pattern A or Pattern B for `X` in the claim chain, `X` is NOT introduced.

# CRITICAL ANTI-PATTERNS — these do NOT introduce, no matter how natural the Chinese reads

**Anti-pattern 1 — Bare noun in any subordinate, conditional, temporal, or relative clause.** Examples that the walker rightly flags as un-introduced:
- `在检测对象存在已知不良时` — neither `检测对象` nor `已知不良` is introduced. Both sit inside a conditional `…时` clause; that clause is not an introduction even though it appears early in claim 1.
- `当信号下降时` — `信号下降` is a condition, not a noun introduction.
- `若所述X不满足` — `X` is being referenced; the `若` clause cannot introduce it.
- `于X之时` / `當X時` — same; `X` is in a temporal frame, not introduced.

If you find yourself reasoning "this is the first occurrence, so it must be the introduction," STOP. First-occurrence is NOT introduction. Pattern A or B is the only introduction.

**Anti-pattern 2 — Possessive `Y的X`.** The OWNED noun X in `Y的X` is not introduced. Only the head noun `Y` (or the whole phrase `Y的X`, treated as a single compound) is in scope. Examples:
- `服务端进程的服务` does not introduce `服务` standalone.
- `第一信号的频率` does not introduce `第一信号` standalone.
- `用户设备的存储器` does not introduce `用户设备`.

**Anti-pattern 3 — Enumerator/selector words.** `各<X>` / `任一<X>` / `任意<X>` / `每<X>` are SELECTORS over previously-introduced X. They do not introduce X.

**Anti-pattern 4 — Bare noun in claim 1 preamble that isn't the claim subject.** A bare noun `X` appearing in claim 1's preamble is only an introduction if `X` IS the subject of the claim (e.g., `1. 一种方法` introduces `方法`). If `X` is buried inside a description of conditions, ratios, comparisons, or contexts, it is NOT introduced — even though it's the first occurrence.

# REFERENCE forms (these are walker triggers; their presence is evidence of reference, not introduction)

- CN: `所述<X>`, `該<X>`
- TW: `該<X>`, `前述<X>`, `所述<X>`, older `申請專利範圍第N項所述<X>`

When you see `所述X` in the surface text, the walker fired BECAUSE of that reference form. Your job is to determine whether Pattern A or B introduced X earlier — NOT to argue that the bare noun X appearing nearby in a clause is itself the introduction.

# CATEGORIES (pick exactly one per finding)

**walker_fp** — Walker is wrong. Pick this when:
- Pattern A (`一X`) appears in the claim chain before the flagged reference, OR
- Pattern B (`<head>，包括X和Y`) appears in the claim chain before the flagged reference, OR
- The walker's `term` is a tokenization fragment of a larger noun phrase that IS introduced via Pattern A/B (e.g., walker says `新功`, claim says `所述新功能需求` and `新功能需求` was introduced earlier).

Also pick walker_fp when the diagnostic span is grossly wrong — the indicated `reference_form` doesn't appear at the indicated `char_offset` in the claim text. (Note: do not pick `diagnostic_mis_attribution` separately for these cases; merge into walker_fp.)

**coverage_gap** — Pick this when X IS introduced via a pattern that's neither A nor B, but a fluent-reader would still recognize as introducing. Examples:
- Synonym/abbreviation introduction (`服务端进程` introduced, then `所述服务端` referenced — walker doesn't bridge the abbreviation; X is "morally" introduced).
- V-之-Y construction in TW (e.g., `產生之X` — no `一` but a V-marker).
- Mathematical/symbol-based cross-references.
This category captures "walker pattern gap; drafting is acceptable to a fluent reader."

**legit_drafting_error** — Pick this when NO Pattern A and NO Pattern B introduces X in the claim chain. The walker is correct. THIS IS THE DEFAULT when:
- The visible context only shows reference markers (`所述`/`該`/`前述`) before the term, with no `一X`/`一個X`/coordination-introducer-with-explicit-head appearing in the chain.
- The "first occurrence" of a bare noun is in a conditional/temporal/relative clause (Anti-pattern 1).
- The term appears only inside `Y的X` possessives (Anti-pattern 2) without a separate Pattern A/B introduction.

If you find yourself wanting to say walker_fp because "the bare noun appears earlier somehow," check Anti-patterns 1-4 first. If any anti-pattern applies, the answer is `legit_drafting_error`, NOT walker_fp.

**diagnostic_mis_attribution** — Reserve for cases where the walker's diagnostic payload is internally inconsistent (e.g., the indicated `char_offset` plus context don't actually contain the `reference_form`). Most "tokenization fragment" cases should be `walker_fp` instead.

**ambig** — Use sparingly. Only when the claim chain genuinely lacks information needed to apply the rules above (e.g., critical ancestor claim is not provided).

# OUTPUT SCHEMA

Return a JSON object with one verdict per finding:
```
{
  "verdicts": [
    {"claim_id": <int>, "term": "<string>", "category": "<one-of-five>", "confidence": 0-100, "reasoning": "<one short sentence, ≤25 Chinese characters or ≤20 English words>"},
    ...
  ]
}
```

KEEP `reasoning` SHORT. The harness can hold ~250 tokens per verdict; over-long reasoning truncates the output and loses verdicts. Quote the deciding pattern (e.g., "Pattern B in claim 4: 包括…输入模块" or "Anti-pattern 1: bare noun in 存在X时 clause") rather than narrating.

Order verdicts to match the input findings list exactly. The `claim_id` and `term` fields must match the input VERBATIM (preserve every character; do not normalize, truncate, or expand the term)."""


# ---------- system prompt v1 for US (Phase 2b — round 1 path D) ----------
# Canonical source: `prompts/us_judge_v1.md` (versioned for cross-jurisdiction
# reuse). String here mirrors the file content verbatim.

SYSTEM_PROMPT_US_V1 = """You are auditing PatentLint's US antecedent-basis walker against a real US patent draft. The walker fired N findings; you must classify each one based on the FULL claim chain provided. Apply the rules below MECHANICALLY — do not be creative or "fluent reader" generous. US §112(b) requires precise antecedent basis; "the reader could figure it out" is not the standard.

# THE ONLY INTRODUCING PATTERNS

A claim term `X` is "introduced" if and only if ONE of these patterns occurs BEFORE the walker's flagged reference, in the same claim or any ancestor claim:

**Pattern A — Indefinite article**: `a <X>` / `an <X>` / `at least one <X>` / `one or more <X>` (US English). The indefinite article is the strongest introducing signal. Plural without article (`<X>s`) sometimes introduces in claim 1 preamble — but conservatively, treat as introduction only when used as a head noun in the preamble.

**Pattern B — Comprising-listing under an explicit head**: `<head> comprising: A, B, and C` / `<head> including X and Y` / `<head> having X, Y, and Z`. The head clause is REQUIRED — must explicitly use `comprising` / `comprises` / `including` / `having` / `consisting of` / `which includes` etc. Listed members A, B, C are introduced together.

**Pattern B-extended — Markush groups**: `selected from the group consisting of A, B, and C` introduces A, B, and C as alternatives. Treat as Pattern B for antecedent purposes.

**Nothing else introduces.** If you cannot find Pattern A, B, or B-extended for `X` in the claim chain, `X` is NOT introduced.

# CRITICAL ANTI-PATTERNS — these do NOT introduce

**Anti-pattern 1 — Bare noun in any subordinate, conditional, temporal, or relative clause.** Examples that the walker rightly flags as un-introduced:
- `wherein X is configured to...` — `X` is in a `wherein` modifier clause; this REFERENCES X (it should already be introduced) and does not itself introduce.
- `when an event occurs, the X is updated` — `X` (and `event`) are in a temporal clause, not introduced even if first-mention.
- `if a condition is satisfied, then X` — same; conditional clause cannot introduce.
- `responsive to the X` / `in response to X` — prepositional phrase referencing X, not introducing.

If you find yourself reasoning "this is the first occurrence, so it must be the introduction," STOP. First-occurrence is NOT introduction. Pattern A or B is the only introduction.

**Anti-pattern 2 — Possessive `Y's X` or `<noun>-of-<noun>`.** The OWNED noun X in a possessive is not introduced. Only the head noun Y (or the whole compound) is in scope. Examples:
- `the system's processor` does not introduce `processor` standalone.
- `frequency of the first signal` does not introduce `first signal` standalone.
- `output of the controller` does not introduce `controller`.

**Anti-pattern 3 — Enumerator/selector words.** `each <X>` / `every <X>` / `any <X>` / `respective <X>` are SELECTORS over previously-introduced X. They do not introduce X. Critical edge case: even when used inside a Pattern B comprising-list, an enumerator-form member doesn't introduce the bare noun. Examples:
- `comprising each processor` does NOT introduce `processor` (the listed member is `each processor`, an enumerator).
- `having any element of the group` does NOT introduce `element` standalone.

**Anti-pattern 4 — Bare noun in claim 1 preamble that isn't the claim subject.** A bare noun `X` in claim 1's preamble is only an introduction if `X` IS the subject of the claim (e.g., `1. A method` introduces `method`; `1. A device for processing data` introduces `device` not `data`). If `X` appears as a modifier, condition, ratio, or context within the preamble, it is NOT introduced — even though it's the first occurrence.

# REFERENCE forms (these are walker triggers; their presence is evidence of reference, not introduction)

US English reference markers:
- `the <X>` (the dominant reference form)
- `said <X>` (formal/older style; equivalent to `the X`)
- `the aforesaid <X>` / `the aforementioned <X>` (rare; equivalent)
- `the said <X>` (redundant but used; equivalent)

When you see `the X` or `said X` in the surface text, the walker fired BECAUSE of that reference form. Your job is to determine whether Pattern A, B, or B-extended introduced X earlier — NOT to argue that the bare noun X appearing nearby in a clause is itself the introduction.

# CATEGORIES (pick exactly one per finding)

**walker_fp** — Walker is wrong. Pick this when:
- Pattern A (`a X` / `an X`) appears in the claim chain before the flagged reference, OR
- Pattern B (`comprising: X, Y, and Z`) appears in the claim chain before the flagged reference, OR
- Markush group introduces X via `selected from the group consisting of … X …`, OR
- The walker's `term` is a tokenization fragment of a larger noun phrase that IS introduced via Pattern A/B (e.g., walker says `processor`, claim says `the data processor` after `comprising… a data processor`).

Also pick walker_fp when the diagnostic span is grossly wrong — the indicated `reference_form` doesn't appear at the indicated `char_offset` in the claim text. (Note: do not pick `diagnostic_mis_attribution` separately for these; merge into walker_fp.)

**coverage_gap** — Pick this when X IS introduced via a pattern that's neither A nor B, but a fluent reader recognizes as introducing. Examples:
- Synonym/abbreviation introduction (`the data processor` introduced, then `said processor` referenced — walker doesn't bridge the abbreviation; X is "morally" introduced).
- Context-derived introduction (e.g., the term implicitly defined by surrounding structure).
- Mathematical/formula-based cross-references (variables defined by equation context).
This category captures "walker pattern gap; drafting is acceptable to a fluent reader."

**legit_drafting_error** — Pick this when NO Pattern A and NO Pattern B introduces X in the claim chain. The walker is correct. THIS IS THE DEFAULT when:
- The visible context only shows reference markers (`the X` / `said X`) before the term, with no `a X` / `an X` / `comprising-with-explicit-head` appearing in the chain.
- The "first occurrence" of a bare noun is in a `wherein` / `when` / `if` / `responsive to` clause (Anti-pattern 1).
- The term appears only inside `Y's X` or `<noun>-of-<noun>` possessives (Anti-pattern 2) without a separate Pattern A/B introduction.

If you find yourself wanting to say walker_fp because "the bare noun appears earlier somehow," check Anti-patterns 1-4 first. If any anti-pattern applies, the answer is `legit_drafting_error`, NOT walker_fp.

**diagnostic_mis_attribution** — Reserve for cases where the walker's diagnostic payload is internally inconsistent (e.g., the indicated `char_offset` plus context don't actually contain the `reference_form`). Most "tokenization fragment" cases should be `walker_fp` instead.

**ambig** — Use sparingly. Only when the claim chain genuinely lacks information needed to apply the rules above (e.g., critical ancestor claim is not provided).

# OUTPUT SCHEMA

Return a JSON object with one verdict per finding:
```
{
  "verdicts": [
    {"claim_id": <int>, "term": "<string>", "category": "<one-of-five>", "confidence": 0-100, "reasoning": "<one short sentence, ≤20 words>"},
    ...
  ]
}
```

KEEP `reasoning` SHORT. The harness can hold ~250 tokens per verdict; over-long reasoning truncates the output and loses verdicts. Quote the deciding pattern (e.g., "Pattern B in claim 4: comprising… a processor" or "Anti-pattern 1: bare noun in wherein clause") rather than narrating.

Order verdicts to match the input findings list exactly. The `claim_id` and `term` fields must match the input VERBATIM (preserve every character; do not normalize, truncate, or expand the term)."""


# ---------- data shapes ----------


@dataclass
class FindingInput:
    """One walker finding's metadata + vicinity payload."""

    claim_id: int
    term: str
    reference_form: str
    char_offset: int
    context_before: str
    context_after: str


@dataclass
class FindingVerdict:
    """LLM's per-finding classification within a draft."""

    claim_id: int
    term: str
    category: str
    confidence: int
    reasoning: str


@dataclass
class DraftJudgment:
    """One model's verdicts for an entire draft.

    `usage` carries actual token counts from the API response so cost
    projection can be reconciled with billing reality (Anthropic + OpenAI
    both expose `usage` on response objects). Fields:
        input_tokens, output_tokens, cache_read_input_tokens (if any),
        cache_creation_input_tokens (if any).
    `error` captures the exception class name when graceful-degradation
    triggered (e.g., "RateLimitError" when OpenAI quota exhausted).
    """

    model: str
    verdicts: list[FindingVerdict]
    raw: str  # raw model output for audit
    usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None


# Per-million-token pricing (USD) as of 2026-05-03. Used by
# `estimate_cost(judgment)` for live cost telemetry. Update when pricing
# changes; sources: anthropic.com/pricing, openai.com/pricing.
_PRICING: dict[str, dict[str, float]] = {
    SONNET: {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    OPUS: {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75},
    GPT_MINI: {"input": 0.25, "output": 2.0, "cache_read": 0.025, "cache_write": 0.0},
}


def estimate_cost(judgment: DraftJudgment) -> float:
    """Compute USD cost for one model call from its actual token usage.

    Returns 0.0 when usage is empty (e.g., the model errored before usage
    was emitted). Total cost across an ensemble run = sum of estimate_cost()
    for each (sonnet, gpt_mini, opus) judgment in each DraftEnsembleVerdict.
    """
    if not judgment.usage:
        return 0.0
    pricing = _PRICING.get(judgment.model)
    if pricing is None:
        return 0.0
    u = judgment.usage
    cost = 0.0
    cost += u.get("input_tokens", 0) * pricing["input"] / 1_000_000
    cost += u.get("output_tokens", 0) * pricing["output"] / 1_000_000
    cost += u.get("cache_read_input_tokens", 0) * pricing["cache_read"] / 1_000_000
    cost += u.get("cache_creation_input_tokens", 0) * pricing["cache_write"] / 1_000_000
    return cost


@dataclass
class DraftEnsembleVerdict:
    """Final ensemble verdicts for a draft, with all model judgments preserved."""

    fixture_key: str
    findings: list[FindingInput]
    final_verdicts: list[FindingVerdict]
    sonnet: DraftJudgment | None = None
    gpt_mini: DraftJudgment | None = None
    opus: DraftJudgment | None = None
    disagreement_count: int = 0
    used_opus: bool = False

    def total_cost(self) -> float:
        """Sum of actual API costs across all models invoked for this draft."""
        return sum(
            estimate_cost(j) for j in (self.sonnet, self.gpt_mini, self.opus)
            if j is not None
        )


# ---------- prompt construction ----------


def _format_user_prompt(
    fixture_key: str,
    jurisdiction: str,
    claim_chain_texts: dict[int, str],
    findings: list[FindingInput],
) -> str:
    """Build the per-draft user prompt.

    `claim_chain_texts`: dict of claim_id → claim text covering every claim
    referenced by the findings + their ancestor chain. The LLM uses this for
    cross-claim antecedent disambiguation.
    """
    lines: list[str] = []
    lines.append(f"Fixture: {fixture_key}")
    lines.append(f"Jurisdiction: {jurisdiction}")
    lines.append("")
    lines.append("# Claim chain (full text)")
    lines.append("")
    for cid in sorted(claim_chain_texts.keys()):
        lines.append(f"## Claim {cid}")
        lines.append(claim_chain_texts[cid])
        lines.append("")

    lines.append(f"# Walker findings ({len(findings)} total) — classify each")
    lines.append("")
    for i, f in enumerate(findings, 1):
        lines.append(f"## Finding {i}")
        lines.append(f"- claim_id: {f.claim_id}")
        lines.append(f"- term: {f.term!r}")
        lines.append(f"- reference_form: {f.reference_form!r}")
        lines.append(f"- char_offset (in claim {f.claim_id} text): {f.char_offset}")
        lines.append(f"- context_before (~30 chars): {f.context_before!r}")
        lines.append(f"- context_after (~30 chars): {f.context_after!r}")
        lines.append("")

    lines.append("Return one verdict per finding, in input order, in the schema specified by the system prompt.")
    return "\n".join(lines)


# ---------- Anthropic tool schema (Sonnet + Opus) ----------


def _build_classify_tool(findings_count: int) -> dict:
    return {
        "name": "classify_findings",
        "description": (
            f"Emit exactly {findings_count} verdicts, one per walker finding, "
            "in the same order as the input findings list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "verdicts": {
                    "type": "array",
                    "minItems": findings_count,
                    "maxItems": findings_count,
                    "items": {
                        "type": "object",
                        "properties": {
                            "claim_id": {"type": "integer"},
                            "term": {"type": "string"},
                            "category": {
                                "type": "string",
                                "enum": list(VALID_CATEGORIES),
                            },
                            "confidence": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                            },
                            "reasoning": {"type": "string"},
                        },
                        "required": [
                            "claim_id",
                            "term",
                            "category",
                            "confidence",
                            "reasoning",
                        ],
                    },
                },
            },
            "required": ["verdicts"],
        },
    }


# ---------- model callers ----------


async def _judge_draft_anthropic(
    client: AsyncAnthropic,
    model: str,
    system: str,
    user: str,
    findings_count: int,
) -> DraftJudgment:
    tool = _build_classify_tool(findings_count)
    # Output budget — Sonnet produces ~120-200 tokens per verdict (the
    # reasoning field is verbose) and the prompt v2 is long enough that
    # 3000 was insufficient (verified iter2: Sonnet returned `{}` for 13/15
    # fixtures). Use 16K cap with per-finding scaling.
    max_tokens = min(16000, max(3000, findings_count * 250))
    resp = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user}],
        tools=[tool],
        tool_choice={"type": "tool", "name": "classify_findings"},
    )
    # Capture actual usage for cost telemetry (used by estimate_cost()).
    usage_dict: dict[str, int] = {}
    if hasattr(resp, "usage") and resp.usage is not None:
        u = resp.usage
        usage_dict = {
            "input_tokens": getattr(u, "input_tokens", 0) or 0,
            "output_tokens": getattr(u, "output_tokens", 0) or 0,
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        }
    tool_block = next((b for b in resp.content if b.type == "tool_use"), None)
    if tool_block is None:
        return DraftJudgment(
            model=model,
            verdicts=[],
            raw=f"[no tool_use; content={str(resp.content)[:500]}]",
            usage=usage_dict,
        )
    parsed = tool_block.input
    raw_verdicts = parsed.get("verdicts", [])
    verdicts: list[FindingVerdict] = []
    for v in raw_verdicts:
        category = v.get("category", "ambig")
        if category not in VALID_CATEGORIES:
            category = "ambig"
        verdicts.append(
            FindingVerdict(
                claim_id=int(v.get("claim_id", 0)),
                term=str(v.get("term", "")),
                category=category,
                confidence=int(v.get("confidence", 0)),
                reasoning=str(v.get("reasoning", ""))[:500],
            )
        )
    return DraftJudgment(
        model=model,
        verdicts=verdicts,
        raw=json.dumps(parsed, ensure_ascii=False)[:5000],
        usage=usage_dict,
    )


async def _judge_draft_openai(
    client: AsyncOpenAI,
    model: str,
    system: str,
    user: str,
    findings_count: int,
) -> DraftJudgment:
    """gpt-5-mini per-draft call. Reasoning tokens are heavier in per-draft
    mode than per-finding (verified iter1 — 213/235 verdicts came back empty
    at 3000-token cap). Bump baseline to 8000 with per-finding scaling; cost
    impact is minimal since gpt-5-mini is cheap."""
    max_tokens = max(8000, findings_count * 200 + 4000)
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=max_tokens,
    )
    text = (resp.choices[0].message.content or "").strip()
    # Capture actual usage for cost telemetry. OpenAI usage shape differs
    # from Anthropic — use prompt_tokens / completion_tokens.
    usage_dict: dict[str, int] = {}
    if hasattr(resp, "usage") and resp.usage is not None:
        u = resp.usage
        usage_dict = {
            "input_tokens": getattr(u, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(u, "completion_tokens", 0) or 0,
            "cache_read_input_tokens": getattr(
                getattr(u, "prompt_tokens_details", None), "cached_tokens", 0
            ) or 0,
        }
    try:
        parsed = json.loads(text)
        raw_verdicts = parsed.get("verdicts", [])
        verdicts: list[FindingVerdict] = []
        for v in raw_verdicts:
            category = v.get("category", "ambig")
            if category not in VALID_CATEGORIES:
                category = "ambig"
            verdicts.append(
                FindingVerdict(
                    claim_id=int(v.get("claim_id", 0)),
                    term=str(v.get("term", "")),
                    category=category,
                    confidence=int(v.get("confidence", 0)),
                    reasoning=str(v.get("reasoning", ""))[:500],
                )
            )
        return DraftJudgment(model=model, verdicts=verdicts, raw=text[:5000], usage=usage_dict)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        finish = getattr(resp.choices[0], "finish_reason", "?")
        return DraftJudgment(
            model=model,
            verdicts=[],
            raw=f"[parse error: {exc}; finish={finish}; head={text[:300]}]",
            usage=usage_dict,
        )


# ---------- ensemble entry point ----------


def _pair_verdict_to_finding(
    finding: FindingInput, finding_index: int, judgment: DraftJudgment
) -> FindingVerdict | None:
    """Pair a finding to its verdict from a model's output.

    Pairing strategy (in order; first hit wins):
      1. Exact match on (claim_id, term).
      2. Index match — verdict at the same position in the verdicts list.
         Holds when the LLM preserved input order (which the schema requires).
      3. Suffix-match on term within the same claim_id (LLMs sometimes
         truncate or normalize the term — e.g., walker `已知不良` →
         model `不良`). Pick the verdict whose term is a substring of
         the finding's term, or vice versa.

    Returns None if all three fail.
    """
    # Strategy 1: exact match
    for v in judgment.verdicts:
        if v.claim_id == finding.claim_id and v.term == finding.term:
            return v

    # Strategy 2: index match (verdict count must align with findings count)
    if 0 <= finding_index < len(judgment.verdicts):
        v = judgment.verdicts[finding_index]
        # Sanity check: at least the claim_id should align
        if v.claim_id == finding.claim_id:
            return v

    # Strategy 3: suffix-or-substring match within same claim_id
    same_claim = [v for v in judgment.verdicts if v.claim_id == finding.claim_id]
    for v in same_claim:
        if v.term and (v.term in finding.term or finding.term in v.term):
            return v

    return None


def _verdict_pair_disagreements(
    a: DraftJudgment, b: DraftJudgment, findings: list[FindingInput]
) -> int:
    """Count finding-level category disagreements between two model outputs.

    Uses the multi-strategy pairing in `_pair_verdict_to_finding`. Missing
    verdicts in either side count as disagreement.
    """
    count = 0
    for i, f in enumerate(findings):
        va = _pair_verdict_to_finding(f, i, a)
        vb = _pair_verdict_to_finding(f, i, b)
        if va is None or vb is None or va.category != vb.category:
            count += 1
    return count


def _merge_ensemble_verdicts(
    sonnet: DraftJudgment,
    gpt: DraftJudgment,
    opus: DraftJudgment | None,
    findings: list[FindingInput],
) -> list[FindingVerdict]:
    """Per-finding final verdict using multi-strategy pairing.

    Rule:
      - Opus, if present, overrides on every finding.
      - Else: Sonnet primary; gpt cross-check; if both agree, use that
        category; else prefer Sonnet (primary judge).
    """
    final: list[FindingVerdict] = []
    for i, f in enumerate(findings):
        if opus is not None:
            ov = _pair_verdict_to_finding(f, i, opus)
            if ov is not None:
                final.append(ov)
                continue
        sv = _pair_verdict_to_finding(f, i, sonnet)
        gv = _pair_verdict_to_finding(f, i, gpt)
        if sv is None and gv is None:
            final.append(FindingVerdict(
                claim_id=f.claim_id, term=f.term, category="ambig",
                confidence=0, reasoning="[both judges missing this finding]",
            ))
        elif sv is None:
            final.append(gv)  # type: ignore[arg-type]
        elif gv is None:
            final.append(sv)
        elif sv.category == gv.category:
            final.append(sv)
        else:
            final.append(sv)  # primary-judge wins
    return final


async def judge_draft(
    fixture_key: str,
    jurisdiction: str,
    claim_chain_texts: dict[int, str],
    findings: list[FindingInput],
    *,
    anthropic_client: AsyncAnthropic,
    openai_client: AsyncOpenAI,
    system_prompt: str = SYSTEM_PROMPT_V2,
    no_opus: bool = False,
) -> DraftEnsembleVerdict:
    """Run the per-draft ensemble: Sonnet + gpt-5-mini in parallel; if
    finding-level disagreements ≥ proportional Opus threshold, escalate the
    whole draft to Opus.

    Graceful degradation (added 2026-05-03 after OpenAI quota exhaustion
    incident wasted ~$30 of Anthropic spend): each model call is awaited
    via `asyncio.gather(return_exceptions=True)`. When one model fails:
      - Sonnet failure → critical; raise (Sonnet is the primary judge)
      - gpt-5-mini failure → log + degrade to Sonnet-only mode (Opus may
        still escalate based on Sonnet's confidence proxy: count gpt's
        empty verdict list as N disagreements, easily exceeding threshold)
      - Opus failure → log + ensemble keeps Sonnet+gpt verdicts

    Errored model judgments still appear in the result with `error` field
    populated, so audit trail captures what failed and why.
    """
    user = _format_user_prompt(
        fixture_key, jurisdiction, claim_chain_texts, findings
    )

    results = await asyncio.gather(
        _judge_draft_anthropic(
            anthropic_client, SONNET, system_prompt, user, len(findings)
        ),
        _judge_draft_openai(
            openai_client, GPT_MINI, system_prompt, user, len(findings)
        ),
        return_exceptions=True,
    )
    sonnet_result, gpt_result = results

    if isinstance(sonnet_result, BaseException):
        # Sonnet is the primary judge — without it the ensemble is meaningless.
        # Re-raise so the caller's exception handler logs + skips this draft.
        raise sonnet_result
    sonnet: DraftJudgment = sonnet_result

    if isinstance(gpt_result, BaseException):
        # Degrade gracefully: synthesize an empty gpt judgment with error
        # metadata. Sonnet's verdicts remain the basis for final output;
        # Opus still escalates since "no gpt verdicts" looks like maximum
        # disagreement.
        gpt = DraftJudgment(
            model=GPT_MINI,
            verdicts=[],
            raw=f"[graceful-degrade: {type(gpt_result).__name__}]",
            error=type(gpt_result).__name__,
        )
    else:
        gpt = gpt_result

    disagree = _verdict_pair_disagreements(sonnet, gpt, findings)
    threshold = opus_escalation_threshold(len(findings))
    opus: DraftJudgment | None = None
    if not no_opus and disagree >= threshold:
        try:
            opus = await _judge_draft_anthropic(
                anthropic_client, OPUS, system_prompt, user, len(findings)
            )
        except BaseException as exc:
            # Opus failure is recoverable — keep Sonnet+gpt verdicts
            opus = DraftJudgment(
                model=OPUS,
                verdicts=[],
                raw=f"[graceful-degrade: {type(exc).__name__}]",
                error=type(exc).__name__,
            )

    final = _merge_ensemble_verdicts(sonnet, gpt, opus, findings)
    return DraftEnsembleVerdict(
        fixture_key=fixture_key,
        findings=findings,
        final_verdicts=final,
        sonnet=sonnet,
        gpt_mini=gpt,
        opus=opus,
        disagreement_count=disagree,
        used_opus=opus is not None and not opus.error,
    )


def ensemble_to_dict(v: DraftEnsembleVerdict) -> dict:
    """Serialize for JSON dump (e.g., calibration results file)."""
    return {
        "fixture_key": v.fixture_key,
        "disagreement_count": v.disagreement_count,
        "used_opus": v.used_opus,
        "findings": [asdict(f) for f in v.findings],
        "final_verdicts": [asdict(v) for v in v.final_verdicts],
        "sonnet": asdict(v.sonnet) if v.sonnet else None,
        "gpt_mini": asdict(v.gpt_mini) if v.gpt_mini else None,
        "opus": asdict(v.opus) if v.opus else None,
    }
