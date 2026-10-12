"""Orchestrates the Briefing -> Research -> Review -> Grade pipeline for one
student's submission. Replaces the old single-call design: each stage gets only
a compact summary of what came before (not raw docs re-dumped every time), and
Research/Review can pull specific source files on demand via tool calls."""

import json
from typing import Any

from app.ai import grading_agent
from app.ai.briefing import get_or_create_briefing
from app.ai.research_agent import research_student
from app.ai.review_agent import review_student_parallel
from app.db import db_cursor
from app.review_status import mark_not_submitted


def _log_usage(cur, student_id: int | None, module_id: int, session_id: str, kind: str, usage: dict | None) -> None:
    if not usage:
        return
    cur.execute(
        """INSERT INTO ai_usage_log (student_id, module_id, yukta_session_id, kind, tokens_prompt, tokens_completion, iterations)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            student_id,
            module_id,
            session_id,
            kind,
            usage.get("tokens_prompt", 0),
            usage.get("tokens_completion", 0),
            usage.get("iterations", 1),
        ),
    )


def run_full_pipeline(student_id: int, module_id: int) -> dict[str, Any]:
    session_id = f"{student_id}:{module_id}"

    briefing, briefing_usage = get_or_create_briefing(module_id)
    dossier, research_usage = research_student(student_id, module_id, briefing)

    with db_cursor() as cur:
        _log_usage(cur, None, module_id, f"briefing:{module_id}", "briefing", briefing_usage)
        _log_usage(cur, student_id, module_id, session_id, "research", research_usage)

    if not dossier.get("has_genuine_submission", True):
        # Research already determined there's no real assignment attempt to grade (e.g. only
        # an AI Usage Declaration was filed) - skip Review/Grade entirely (nothing to score)
        # and record this distinctly rather than letting it silently read as a graded
        # "Beginning" band, which would still (wrongly) count as a completed review.
        reason = dossier.get("non_submission_reason") or "No genuine attempt at the assignment tasks was found."
        with db_cursor() as cur:
            mark_not_submitted(cur, student_id, module_id, reason)
            cur.execute(
                """INSERT INTO research_dossiers (student_id, module_id, dossier_json, review_draft_json, files_read_count, model)
                   VALUES (?, ?, ?, NULL, ?, ?)
                   ON CONFLICT(student_id, module_id) DO UPDATE SET
                     dossier_json=excluded.dossier_json, review_draft_json=NULL,
                     files_read_count=excluded.files_read_count, model=excluded.model, created_at=datetime('now')""",
                (student_id, module_id, json.dumps(dossier), len(dossier.get("files_reviewed", [])), "gemma-4-26b-a4b-it"),
            )
        return {"status": "not_submitted", "reason": reason}

    review_draft, review_usage_list = review_student_parallel(student_id, module_id, briefing, dossier)
    final, grade_usage = grading_agent.grade_submission(session_id, briefing, dossier, review_draft)

    with db_cursor() as cur:
        for item in review_usage_list:
            _log_usage(
                cur, student_id, module_id, f"{session_id}:review:{item['trait']}", "review", item["usage"]
            )
        _log_usage(cur, student_id, module_id, session_id, "grade", grade_usage)

        cur.execute(
            """INSERT INTO research_dossiers (student_id, module_id, dossier_json, review_draft_json, files_read_count, model)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(student_id, module_id) DO UPDATE SET
                 dossier_json=excluded.dossier_json, review_draft_json=excluded.review_draft_json,
                 files_read_count=excluded.files_read_count, model=excluded.model, created_at=datetime('now')""",
            (
                student_id,
                module_id,
                json.dumps(dossier),
                json.dumps(review_draft),
                len(dossier.get("files_reviewed", [])),
                "gemma-4-26b-a4b-it",
            ),
        )

    return {"status": "graded", **final}
