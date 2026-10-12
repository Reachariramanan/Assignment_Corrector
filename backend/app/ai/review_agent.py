"""Review stage: ONE parallel sub-agent PER rubric trait ("perspective"), each reasoning
only about its own trait against that trait's full level descriptors + the briefing's
detailed_prompt for it, with the same document-access tools Research has so it can go
re-check the source file itself if the dossier's evidence feels thin for its trait.

The earned percentage (weight_pct * level/4) is computed deterministically in Python,
never by the model - the model's job is to pick the level and justify it with verbatim,
evidence-quoting reasoning; the arithmetic is ours so it's always internally consistent."""

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.ai.common import extract_json, run_oneshot
from app.ai.document_tools import make_document_tools
from app.db import db_cursor

MAX_PARALLEL_TRAIT_AGENTS = 8

TRAIT_SYSTEM = """You are one of several parallel grading sub-agents, each independently responsible for \
ONE rubric trait/perspective on a case-study submission. You do NOT see or influence the other traits' \
verdicts - focus only on yours.

## Your trait
**{trait_name}** (weight {weight_pct}% of the total grade)

## Full level descriptors for this trait
{level_table}

## Detailed grading guidance for this trait (from the module's evaluator key)
{detailed_prompt}

## Research dossier for this student (built by an earlier stage - evidence found across their files)
{dossier}

## Your task
Decide which level (1-4) this student's submission earned on THIS trait, anchored strictly to the level \
descriptors above. If the dossier's evidence for your trait feels thin, incomplete, or you want to verify \
something yourself, use list_files/read_file to check the actual source document - don't just guess.

Your reasoning must be VERBATIM and evidence-grounded: quote (or closely paraphrase) the exact descriptor \
phrase that justifies your level choice, AND quote/cite the specific evidence from the student's submission \
(exact figures, Device IDs, quoted phrases) that supports it. This is not a summary - be specific and \
concrete, though still no more than 3-4 sentences.

Respond with ONLY a JSON object, no prose:
{{
  "level": <1-4>,
  "reasoning_verbatim": "<quotes the exact descriptor phrase for that level + quotes/cites specific evidence from the submission>",
  "open_question": "<anything the final aggregating stage should double-check about this trait, or empty string if none>"
}}
"""


def _format_level_table(levels: list[dict]) -> str:
    return "\n".join(f"- Level {lvl['level']} ({lvl['label']}): {lvl['descriptor']}" for lvl in levels)


MAX_ATTEMPTS_PER_TRAIT = 3


def _review_single_trait(
    trait: dict[str, Any], detailed_prompt: str, dossier: dict[str, Any], student_id: int, module_id: int
) -> tuple[dict[str, Any], dict[str, int]]:
    """Never raises: a transient empty/malformed response from one trait agent must not
    sink the other traits' already-successful parallel work (ThreadPoolExecutor.result()
    re-raises into the caller, which would otherwise crash the whole batch). Retries a
    couple of times first (these failures have consistently been transient in practice),
    then falls back to a clearly-flagged verdict that a human reviewer needs to check."""
    system_text = TRAIT_SYSTEM.format(
        trait_name=trait["name"],
        weight_pct=trait["weight_pct"],
        level_table=_format_level_table(trait["levels"]),
        detailed_prompt=detailed_prompt or "(no additional guidance provided)",
        dossier=json.dumps(dossier, indent=2),
    )
    tools = make_document_tools(student_id, module_id)
    last_error: Exception | None = None
    total_usage = {"tokens_prompt": 0, "tokens_completion": 0}
    for attempt in range(1, MAX_ATTEMPTS_PER_TRAIT + 1):
        try:
            response, usage = run_oneshot(
                f"review-{student_id}-{module_id}-{trait['name']}-attempt{attempt}",
                system_text,
                f"Grade the '{trait['name']}' trait and return the JSON verdict.",
                temperature=0.2,
                tools_processor=tools,
            )
            total_usage["tokens_prompt"] += usage.get("tokens_prompt", 0)
            total_usage["tokens_completion"] += usage.get("tokens_completion", 0)
            verdict = extract_json(response)
            return verdict, total_usage
        except Exception as e:
            last_error = e

    fallback = {
        "level": 1,
        "reasoning_verbatim": "",
        "open_question": f"AUTOMATIC GRADING FAILED for this trait after {MAX_ATTEMPTS_PER_TRAIT} attempts "
        f"({last_error}) - a human reviewer must score this trait manually.",
    }
    return fallback, total_usage


def review_student_parallel(
    student_id: int, module_id: int, briefing: dict[str, Any], dossier: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Returns (result, per_trait_usage_list). result = {"traits": [...]}"""
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, name, weight_pct FROM rubric_traits WHERE module_id = ? ORDER BY sort_order",
            (module_id,),
        )
        traits = [dict(r) for r in cur.fetchall()]
        for t in traits:
            cur.execute("SELECT level, label, descriptor FROM rubric_levels WHERE trait_id = ? ORDER BY level", (t["id"],))
            t["levels"] = [dict(r) for r in cur.fetchall()]

    detailed_prompts = {
        rs["trait"]: rs.get("detailed_prompt", "") for rs in briefing.get("rubric_summary", [])
    }

    max_workers = min(len(traits), MAX_PARALLEL_TRAIT_AGENTS)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(_review_single_trait, t, detailed_prompts.get(t["name"], ""), dossier, student_id, module_id)
            for t in traits
        ]
        results = [f.result() for f in futures]

    trait_verdicts = []
    usage_list = []
    for trait, (verdict, usage) in zip(traits, results):
        level = verdict.get("level", 1)
        level_label = next((lvl["label"] for lvl in trait["levels"] if lvl["level"] == level), "")
        earned_pct = round(trait["weight_pct"] * level / 4, 1)
        trait_verdicts.append(
            {
                "trait": trait["name"],
                "weight_pct": trait["weight_pct"],
                "level": level,
                "level_label": level_label,
                "earned_pct": earned_pct,
                "reasoning_verbatim": verdict.get("reasoning_verbatim", ""),
                "open_question": verdict.get("open_question", ""),
            }
        )
        usage_list.append({"trait": trait["name"], "usage": usage})

    return {"traits": trait_verdicts}, usage_list
