"""Grading agent: the finalizer/aggregator stage of the pipeline. The Review stage now
runs one independent parallel sub-agent per rubric trait; this stage takes all of their
verdicts (each already has a level + verbatim reasoning + optional open_question) and
resolves any open questions, writes the one holistic framing_note no single trait agent
could see, and re-emits everything in the app's stable per-trait JSON contract. This
same agent (and its memory) then stays alive as the reviewer's follow-up chat session
for that student, so "why this score?" is answered with the full research/review trail
in context - not just the final numbers.
"""

import json
from typing import Any, Callable

from yukta import AgentConfig, SystemPrompt, create_agent, create_memory

from app.ai.briefing import get_or_create_briefing
from app.ai.common import UsageCapture, agent_response, extract_json, new_llm_client
from app.ai.document_tools import make_document_tools
from app.db import db_cursor

_agent_cache: dict[str, Any] = {}

GRADING_SYSTEM_TEMPLATE = """You are the Grading (finalizer/aggregator) stage of a multi-agent pipeline \
for an audit-training case-study assignment. Each rubric trait below was independently graded by its own \
dedicated sub-agent, in parallel - each already gives a level (1-4) and verbatim, evidence-quoting \
reasoning for that trait alone. None of them could see the whole submission or each other's verdicts.

## Module briefing
{briefing}

## Research dossier (whole-submission evidence, built by an earlier stage)
{dossier}

## Per-trait verdicts from the parallel Review stage
{review_draft}

## Instructions
For each trait, respect the sub-agent's level unless its own reasoning is clearly inconsistent with the \
level it picked (rare) - your job is not to re-grade each trait but to: (1) resolve any per-trait \
"open_question" using your judgement and the dossier's whole-submission view, and (2) write ONE holistic \
framing_note across the whole submission (no single trait agent had that view). Respond with ONLY a JSON \
object of this exact shape, no prose before or after:
{{
  "framing_note": "<1-2 sentence note on how well the submission opens by framing the core issue>",
  "traits": [
    {{"trait": "<exact trait name>", "level": <1-4>, "rationale": "<the trait sub-agent's verbatim reasoning, resolved if it flagged an open_question>"}}
  ]
}}
Include one entry in "traits" for every rubric trait given above, in the order given.
When the reviewer asks a follow-up question afterward, answer conversationally and briefly using the \
research/review context above - do not repeat the JSON block unless asked to re-grade. You also have \
list_files/read_file tools for this student's submission if a follow-up question needs you to actually \
go check something in the source document rather than rely on the dossier summary.
"""


def get_or_create_agent(session_id: str, briefing: dict, dossier: dict, review_draft: dict):
    if session_id in _agent_cache:
        return _agent_cache[session_id]

    student_id_str, module_id_str = session_id.split(":")
    tools = make_document_tools(int(student_id_str), int(module_id_str))

    system_prompt = SystemPrompt(
        prompt_name="ModuleGrader",
        prompt_text=GRADING_SYSTEM_TEMPLATE.format(
            briefing=json.dumps(briefing, indent=2),
            dossier=json.dumps(dossier, indent=2),
            review_draft=json.dumps(review_draft, indent=2),
        ),
    )
    memory = create_memory(
        system_prompt=system_prompt.get_prompt(),
        max_tokens=12000,
        session_id=session_id,
    )
    usage_capture = UsageCapture()
    agent = create_agent(
        name=f"grader-{session_id}",
        system_prompt=system_prompt,
        llm_client=new_llm_client(temperature=0.2),
        memory=memory,
        use_memory_cache=True,
        tools_processor=tools,
        config=AgentConfig(temperature=0.2, max_iter=6, verbose=False),
        callbacks=usage_capture,
    )
    agent._usage_capture = usage_capture  # stashed for grade_submission/chat_followup to read
    _agent_cache[session_id] = agent
    return agent


def grade_submission(
    session_id: str, briefing: dict, dossier: dict, review_draft: dict
) -> tuple[dict[str, Any], dict[str, int]]:
    agent = get_or_create_agent(session_id, briefing, dossier, review_draft)
    agent._usage_capture.reset()
    result = agent.run(
        user_message="Finalize your grading. Return only the JSON object described in your instructions.",
        reset_conversation=False,
    )
    parsed = extract_json(agent_response(result))
    usage = {**agent._usage_capture.last_usage, "iterations": result.get("iterations", 1)}
    return parsed, usage


def _rehydrate_agent(session_id: str):
    """The agent cache is in-process memory only, so it's empty right after any backend
    restart even though the grading data itself is safely persisted in SQLite. Rebuild the
    same agent (same system prompt/tools) from the persisted briefing + research dossier +
    review draft instead of requiring grade_submission to have run in this process's lifetime."""
    student_id_str, module_id_str = session_id.split(":")
    student_id, module_id = int(student_id_str), int(module_id_str)
    with db_cursor() as cur:
        cur.execute(
            "SELECT dossier_json, review_draft_json FROM research_dossiers WHERE student_id = ? AND module_id = ?",
            (student_id, module_id),
        )
        row = cur.fetchone()
    if not row or not row["review_draft_json"]:
        raise ValueError("No graded submission on record for this student/module - run grading first")
    dossier = json.loads(row["dossier_json"])
    review_draft = json.loads(row["review_draft_json"])
    briefing, _usage = get_or_create_briefing(module_id)
    return get_or_create_agent(session_id, briefing, dossier, review_draft)


def chat_followup(
    session_id: str, message: str, on_event: Callable[[dict], None] | None = None
) -> tuple[str, dict[str, int], list[dict]]:
    agent = _agent_cache.get(session_id) or _rehydrate_agent(session_id)
    agent._usage_capture.reset()
    agent._usage_capture.live_sink = on_event
    try:
        result = agent.run(user_message=message, reset_conversation=False)
    finally:
        agent._usage_capture.live_sink = None
    usage = {**agent._usage_capture.last_usage, "iterations": result.get("iterations", 1)}
    return agent_response(result), usage, agent._usage_capture.trace
