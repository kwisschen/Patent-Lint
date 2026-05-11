# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Cross-family LLM ensemble for PatentLint triage + Step 0 calibration.

Runs Haiku 4.5 + gpt-5-mini in parallel on a finding's diagnostic payload;
escalates to Sonnet 4.6 as tiebreaker on disagreement; returns a 2-of-3
majority vote with all individual judgments preserved.

Reads ANTHROPIC_API_KEY + OPENAI_API_KEY from Patent-Analyst's .env.
Designed for jurisdiction-portability per round-1 plan §reusable scaffolding.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

ANALYST_ENV = Path("/Users/chrischen/Documents/Projects/Patent-Analyst/.env")

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"
GPT_MINI = "gpt-5-mini"

Category = Literal[
    "walker_fp",
    "coverage_gap",
    "legit_drafting_error",
    "diagnostic_mis_attribution",
    "ambig",
]

VALID_CATEGORIES: set[str] = {
    "walker_fp",
    "coverage_gap",
    "legit_drafting_error",
    "diagnostic_mis_attribution",
    "ambig",
}


def load_keys() -> tuple[str, str]:
    """Read both API keys from Patent-Analyst's .env without exposing values."""
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


SYSTEM_PROMPT_ANTECEDENT = """You are triaging a finding from PatentLint's antecedent-basis walker (CN/TW jurisdictions, post-`ea19383` diagnostic payload shape).

The walker fired because it believes the term, in its CONSTRUCTED reference form, lacks a proper prior INTRODUCTION in the same or ancestor claim. You must classify the finding into exactly one category based ONLY on the ~30-char vicinity context the diagnostic payload provides.

CRITICAL — Chinese/CJK antecedent grammar:

INTRODUCING forms (the FIRST appearance of a noun; satisfies §112(b) / TW 專利法 §26 / CN 专利法 §26):
- `一<noun>` / `一個<noun>` / `一種<noun>` / `多個<noun>` (CN+TW)  ← classic indefinite-article introducer
- `<noun>` standing alone at the very start of claim 1's preamble (no determiner — bare-noun introduction)
- Coordination introductions: `具有X和Y` / `具有X以及Y` / `包括X、Y` (the head noun plus listed members; the LISTED member is introduced)

REFERENCE forms (back-pointers to a prior introduction; do NOT introduce):
- CN: `所述<noun>`, `該<noun>`
- TW: `該<noun>`, `前述<noun>`, `所述<noun>` (rarer)
- These imply "the aforementioned <noun>." If you see `所述X` in context_before, that indicates THE WALKER'S WHOLE FLAG IS the reference — it does NOT mean X was introduced. X must have been introduced ELSEWHERE (earlier in this claim, or in an ancestor claim) for the reference to be valid.

The walker's `reference_form` field is what the walker constructed as the canonical "this is the reference shape" — usually `所述<term>` or `該<term>` or `前述<term>`. Seeing this same shape in context_before means you're looking at the reference itself, not a fresh introduction.

Categories (pick exactly one):

- walker_fp: Walker is wrong. Strong signals:
  (a) `context_before` shows an INTRODUCING form (一<noun>/一個<noun>/coordination-introduced) of the term within the visible window — drafter DID introduce it, walker missed.
  (b) compound-noun mis-tokenization: walker's term is a fragment of a larger noun phrase that, taken whole, IS introduced.
  (c) `reference_form` mismatch with surface text: walker emits `該X` but the surface clearly shows `一X` or bare `X` — walker tokenized wrong.

- coverage_gap: Walker correctly notes "no obvious antecedent in my pattern set" but the term IS introduced somewhere via a pattern the walker doesn't recognize (synonym, V-之-Y construction, conjunction-split intro `X和Y`, mathematical-symbol cross-reference). Walker capability gap, not drafting error. Note: you usually CAN'T see this from a 30-char window — only mark this if there's strong evidence of a recognizable-but-non-walker-supported intro.

- legit_drafting_error: Drafter genuinely failed to introduce antecedent. The term appears with a reference form (`所述X`/`該X`/`前述X`) but no introducing form (`一X`/`一個X`/bare X) is visible in context_before. The walker's flag is correct. **Default for "context_before only shows reference markers like 所述/該/前述 immediately before the term"** — that's evidence of REFERENCE (reaffirming the walker's complaint), not of introduction.

- diagnostic_mis_attribution: The `reference_form` doesn't actually appear in `context_before + term + context_after` at the indicated char_offset. Diagnostic extractor pointed at the wrong span.

- ambig: 30-char window is genuinely insufficient AND no clear signal either way. Use sparingly. Note: simply not seeing the introduction in 30 chars doesn't make it ambig — for valid drafts, the introduction would still typically be reachable from the term, especially if `claim_id` is 1 (no ancestors).

Return ONLY a JSON object: {"category": "...", "confidence": 0-100, "reasoning": "<1-2 sentences>"}"""

SYSTEM_PROMPT_SPEC_SUPPORT = """You are triaging a finding from PatentLint's spec-support walker (TW jurisdiction, post-`ea19383` diagnostic payload shape).

The walker fired because a phrase in a claim was not found in the specification through any of its tier checks (symbol_table, normalized_exact, raw_exact, char_window). You must classify the finding into exactly one category based ONLY on the diagnostic payload.

Categories (pick exactly one):

- walker_fp: Walker is incorrectly flagging. Signals: phrase is a partial fragment (function-word residue like 較前述, 對在), an aggregate construct that the spec describes via its components rather than verbatim, or a phrase that obviously appears in the spec via a tier the walker mishandled.

- coverage_gap: Phrase IS present in the spec, but the walker's tier checks all missed it (e.g., spec uses synonym, abbreviation, character-variant the symbol table doesn't capture). Walker capability gap.

- legit_drafting_error: Drafter introduced a claim-only term not supported by the spec — TW 專利法 §26 第3項 violation. The phrase is a substantive technical term (not a function-word fragment).

- diagnostic_mis_attribution: The `phrase` field clearly doesn't match what the walker should have flagged given the context (e.g., the walker tokenized too aggressively or pointed at offsets that don't span the actual phrase).

- ambig: Cannot determine from the diagnostic alone.

Return ONLY a JSON object: {"category": "...", "confidence": 0-100, "reasoning": "<1-2 sentences>"}"""


@dataclass
class Judgment:
    """A single LLM's classification of a finding."""

    model: str
    category: str
    confidence: int
    reasoning: str
    raw: str  # the full JSON the model emitted, for audit


@dataclass
class EnsembleVerdict:
    """Final ensemble verdict with all individual judgments preserved."""

    finding_key: str
    final_category: str
    agreement_level: Literal["unanimous", "majority", "tiebreaker", "three_way_split"]
    judgments: list[Judgment]


def _system_for(check_class: str) -> str:
    if check_class == "antecedentBasis":
        return SYSTEM_PROMPT_ANTECEDENT
    if check_class == "specSupport":
        return SYSTEM_PROMPT_SPEC_SUPPORT
    raise ValueError(f"Unknown check_class: {check_class}")


def _format_finding_user_prompt(finding: dict, jurisdiction: str, check_class: str) -> str:
    if check_class == "antecedentBasis":
        # Vicinity-window-only by default (matches production triage payload privacy contract).
        # Step 0 calibration showed full_claim_text REGRESSES protect:true accuracy
        # because LLMs over-detect "antecedents" in wider context — domain-specific nuances
        # (compound nouns, temporal-clause bare nouns, X的Y constructions that don't
        # introduce X) trip up unconstrained judges. Vicinity window keeps them honest.
        return (
            f"Jurisdiction: {jurisdiction}\n"
            f"Term (walker matched): {finding.get('term')!r}\n"
            f"Reference form (walker constructed): {finding.get('reference_form')!r}\n"
            f"Did you mean: {finding.get('did_you_mean')!r}\n"
            f"Did you mean claim_id: {finding.get('did_you_mean_claim_id')!r}\n"
            f"Claim ID: {finding.get('claim_id')}\n"
            f"char_offset: {finding.get('char_offset')}\n"
            f"context_before (~30 chars): {finding.get('context_before')!r}\n"
            f"context_after (~30 chars): {finding.get('context_after')!r}\n"
            f"Claim text length: {finding.get('claim_text_charlen')} chars\n\n"
            "Classify this finding."
        )
    if check_class == "specSupport":
        return (
            f"Jurisdiction: {jurisdiction}\n"
            f"Phrase (claim term not found in spec): {finding.get('phrase')!r}\n"
            f"Cross-reference: {finding.get('cross_ref')!r}\n"
            f"Tiers checked: {finding.get('tiers_checked', [])}\n"
            f"Claim ID: {finding.get('claim_id')}\n"
            f"char_offset: {finding.get('char_offset', 'N/A')}\n"
            f"context_before: {finding.get('context_before', 'N/A')!r}\n"
            f"context_after: {finding.get('context_after', 'N/A')!r}\n"
            f"Claim text length: {finding.get('claim_text_charlen', 'N/A')}\n\n"
            "Classify this finding."
        )
    raise ValueError(f"Unknown check_class: {check_class}")


CLASSIFY_TOOL = {
    "name": "classify_finding",
    "description": "Emit a single classification verdict for the given finding.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": list(VALID_CATEGORIES),
                "description": "The classification.",
            },
            "confidence": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Confidence 0-100.",
            },
            "reasoning": {
                "type": "string",
                "description": "1-2 sentence rationale.",
            },
        },
        "required": ["category", "confidence", "reasoning"],
    },
}


async def _judge_anthropic(
    client: AsyncAnthropic, model: str, system: str, user: str
) -> Judgment:
    """Anthropic call via forced tool_use for typed structured output."""
    resp = await client.messages.create(
        model=model,
        max_tokens=600,
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user}],
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "classify_finding"},
    )
    # Find the tool_use block
    tool_block = next((b for b in resp.content if b.type == "tool_use"), None)
    if tool_block is None:
        return Judgment(
            model=model, category="ambig", confidence=0,
            reasoning="[no tool_use block returned]", raw=str(resp.content)[:500],
        )
    parsed = tool_block.input
    category = parsed.get("category", "ambig")
    if category not in VALID_CATEGORIES:
        category = "ambig"
    return Judgment(
        model=model,
        category=category,
        confidence=int(parsed.get("confidence", 0)),
        reasoning=str(parsed.get("reasoning", ""))[:500],
        raw=json.dumps(parsed, ensure_ascii=False),
    )


async def _judge_openai(
    client: AsyncOpenAI, model: str, system: str, user: str
) -> Judgment:
    """OpenAI call. gpt-5-mini uses heavy reasoning tokens; max_completion_tokens
    must be generous (~3000) so content has budget after reasoning consumes ~1000-1500."""
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=3000,
    )
    text = (resp.choices[0].message.content or "").strip()
    try:
        parsed = json.loads(text)
        category = parsed.get("category", "ambig")
        if category not in VALID_CATEGORIES:
            category = "ambig"
        return Judgment(
            model=model,
            category=category,
            confidence=int(parsed.get("confidence", 0)),
            reasoning=str(parsed.get("reasoning", ""))[:500],
            raw=text,
        )
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        finish = getattr(resp.choices[0], "finish_reason", "?")
        return Judgment(
            model=model,
            category="ambig",
            confidence=0,
            reasoning=f"[parse error: {e}; finish={finish}]",
            raw=text[:500],
        )


async def judge_finding(
    finding: dict,
    jurisdiction: str,
    check_class: str,
    finding_key: str,
    anthropic_client: AsyncAnthropic,
    openai_client: AsyncOpenAI,
) -> EnsembleVerdict:
    """Run cross-family ensemble + Sonnet tiebreaker on a single finding."""
    system = _system_for(check_class)
    user = _format_finding_user_prompt(finding, jurisdiction, check_class)

    haiku, gpt = await asyncio.gather(
        _judge_anthropic(anthropic_client, HAIKU, system, user),
        _judge_openai(openai_client, GPT_MINI, system, user),
    )

    if haiku.category == gpt.category:
        return EnsembleVerdict(
            finding_key=finding_key,
            final_category=haiku.category,
            agreement_level="unanimous",
            judgments=[haiku, gpt],
        )

    # Disagreement → Sonnet tiebreaker
    sonnet = await _judge_anthropic(anthropic_client, SONNET, system, user)
    cats = [haiku.category, gpt.category, sonnet.category]
    counts: dict[str, int] = {}
    for c in cats:
        counts[c] = counts.get(c, 0) + 1
    top = max(counts.items(), key=lambda x: x[1])
    if top[1] >= 2:
        return EnsembleVerdict(
            finding_key=finding_key,
            final_category=top[0],
            agreement_level="tiebreaker",
            judgments=[haiku, gpt, sonnet],
        )
    # 1-1-1 split
    return EnsembleVerdict(
        finding_key=finding_key,
        final_category="ambig",
        agreement_level="three_way_split",
        judgments=[haiku, gpt, sonnet],
    )


def verdict_to_dict(v: EnsembleVerdict) -> dict:
    return {
        "finding_key": v.finding_key,
        "final_category": v.final_category,
        "agreement_level": v.agreement_level,
        "judgments": [asdict(j) for j in v.judgments],
    }
