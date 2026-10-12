"""Research agent: given only the module briefing (not the raw case study/rubric)
and a file listing (not the raw text dumped in), autonomously decides which of
the student's files to open and builds a cited evidence dossier. Free to re-open
a file mid-investigation if something needs clarifying."""

import json
from typing import Any

from app.ai.common import extract_json, run_oneshot
from app.ai.document_tools import make_document_tools

RESEARCH_SYSTEM = """You are the Research stage of a multi-agent grading pipeline for a case-study \
assignment. You do NOT score anything - your job is to build an evidence dossier for the next stage.

## Module briefing
{briefing}

## Your task
This student submitted one or more files. Use list_files to see what they submitted, then read_file to \
open whichever files you need - you decide what's relevant and can re-open a file later if you realize \
you need to check something again. Look for evidence relevant to each task in the briefing and to the \
rubric traits.

FIRST, before anything else, determine whether the student actually attempted the assignment at all. \
Submissions commonly include an "AI Usage Declaration" file alongside the real work - that declaration \
alone is NOT a submission of the assignment. Set has_genuine_submission=false ONLY if none of the files \
contain any actual attempt at Task 1-4 (or whatever tasks the briefing lists) - e.g. the student uploaded \
only a declaration/disclosure form, an empty/template file, or something unrelated to the case study. If \
there is any real attempt at the tasks, even a weak or incomplete one, has_genuine_submission=true.

Be TERSE - your output has a hard length limit. One short sentence per field, not a paragraph. Never quote
long passages; paraphrase in a few words.

When you're done, respond with ONLY a JSON object, no prose:
{{
  "has_genuine_submission": <true/false>,
  "non_submission_reason": "<if false: 1 short sentence on what the files actually contain instead. If true: empty string.>",
  "files_reviewed": ["<filename>", ...],
  "per_task_evidence": [{{"task": "<task name from briefing>", "found": <true/false>, "evidence": "<one short sentence, max ~25 words, with the source filename>", "gaps": "<one short phrase, or empty string if none>"}}],
  "notable_citations": ["<a few short evidence anchors from the briefing that the student did/didn't address>"],
  "overall_impression": "<1 short sentence>"
}}
"""


def research_student(student_id: int, module_id: int, briefing: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    system_text = RESEARCH_SYSTEM.format(briefing=json.dumps(briefing, indent=2))
    tools = make_document_tools(student_id, module_id)
    response, usage = run_oneshot(
        f"research-{student_id}-{module_id}",
        system_text,
        "Investigate this student's submission and produce the dossier JSON.",
        temperature=0.2,
        tools_processor=tools,
    )
    dossier = extract_json(response)
    return dossier, usage
