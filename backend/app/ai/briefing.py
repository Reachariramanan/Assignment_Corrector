"""Module briefing: read the case-study + rubric + the FULL sample-answer/evaluator-key
docx ONCE per module and produce a detailed, reusable briefing (including a per-trait
"detailed_prompt") that every downstream agent (research/review/grade) works from,
instead of each of them re-reading the full raw docs on every student."""

import json
import re
from pathlib import Path
from typing import Any

from app.ai.common import extract_json, run_oneshot
from app.db import db_cursor
from app.ingest.docx_parser import docx_to_plain

BRIEFING_SYSTEM = """You are briefing a team of grading agents on a case-study assignment before they \
review student submissions. Read the case study, the rubric, and the evaluator's own sample-answer/model-
response document below, then produce a detailed briefing so the agents never need to re-read the full \
documents themselves.

For each rubric trait, write a genuinely detailed "detailed_prompt" - several sentences that a grading \
sub-agent could use as its entire instruction for that trait with no further lookup needed. Synthesize: \
the trait's full level descriptors (what separates each level), AND anything the sample-answer document \
says specifically about that trait area - its model answer content, any "standards grounding" reasoning, \
and especially its "common shortfalls to watch for" notes, since those tell a grader exactly what mistakes \
to look for.

Respond with ONLY a JSON object:
{
  "scenario_summary": "<2-3 sentence summary of the scenario>",
  "tasks": [{"task": "<task name>", "gist": "<1 sentence on what's required>"}],
  "key_evidence_anchors": ["<specific facts/IDs from the data pack a strong answer should cite, e.g. device IDs, record IDs>"],
  "rubric_summary": [{"trait": "<exact trait name>", "weight_pct": <number>, "gist": "<1 sentence summary>", "detailed_prompt": "<several detailed sentences per the instructions above>"}]
}
"""


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def get_or_create_briefing(module_id: int) -> tuple[dict[str, Any], dict[str, int] | None]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT briefing_json, case_study_html, sample_answer_path FROM modules WHERE id = ?", (module_id,)
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Module {module_id} not found")
        if row["briefing_json"]:
            return json.loads(row["briefing_json"]), None

        cur.execute(
            "SELECT name, weight_pct, sort_order FROM rubric_traits WHERE module_id = ? ORDER BY sort_order",
            (module_id,),
        )
        traits = [dict(r) for r in cur.fetchall()]
        for t in traits:
            cur.execute("SELECT level, label, descriptor FROM rubric_levels WHERE trait_id = (SELECT id FROM rubric_traits WHERE module_id = ? AND name = ?) ORDER BY level", (module_id, t["name"]))
            t["levels"] = [dict(r) for r in cur.fetchall()]

        rubric_text = "\n".join(
            f"### {t['name']} ({t['weight_pct']}%)\n" + "\n".join(f"- L{l['level']} {l['label']}: {l['descriptor']}" for l in t["levels"])
            for t in traits
        )

        sample_answer_text = ""
        if row["sample_answer_path"]:
            try:
                sample_answer_text = docx_to_plain(Path(row["sample_answer_path"]))
            except Exception as e:
                print(f"Warning: could not read sample-answer docx for briefing: {e}")

        user_text = (
            f"## Case Study\n{_strip_html(row['case_study_html'])[:8000]}\n\n"
            f"## Rubric\n{rubric_text}\n\n"
            f"## Evaluator Key / Sample Answer (full document)\n{sample_answer_text[:16000]}"
        )
        response, usage = run_oneshot("module-briefing", BRIEFING_SYSTEM, user_text, temperature=0.1)
        briefing = extract_json(response)

        cur.execute("UPDATE modules SET briefing_json = ? WHERE id = ?", (json.dumps(briefing), module_id))
        return briefing, usage
