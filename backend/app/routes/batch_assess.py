"""Bulk 'Start Assessment' trigger: after importing a module (via the upload modal or a
chat zip-drop), grade every student who hasn't been graded yet, using the same
run_full_pipeline as the per-student AI-assist call. Grading involves several sequential
LLM calls per student, so this runs in a background thread with in-memory progress the
frontend polls - the same background-thread pattern already used for SSE streaming."""

import threading
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from app.ai.pipeline import run_full_pipeline
from app.db import db_cursor
from app.review_status import recompute_status

router = APIRouter(prefix="/api", tags=["batch-assess"])

_progress: dict[int, dict[str, Any]] = {}


def _finalize_graded(student_id: int, module_id: int, final: dict) -> None:
    """run_full_pipeline's 'graded' result is only the AI's proposed scores - the normal
    per-student flow (routes/ai_assist.py) leaves these as ai_suggestions for a human to
    review and explicitly Save. A bulk batch run has no human in that loop, so here we
    write them straight into `reviews` (source='ai') and recompute status, the same two
    writes a manual Save does via PUT /api/reviews."""
    now = datetime.now(timezone.utc).isoformat()
    with db_cursor() as cur:
        cur.execute("SELECT id, name FROM rubric_traits WHERE module_id = ?", (module_id,))
        trait_by_name = {r["name"]: r["id"] for r in cur.fetchall()}
        for entry in final.get("traits", []):
            trait_id = trait_by_name.get(entry.get("trait"))
            if trait_id is None:
                continue
            cur.execute(
                """INSERT INTO reviews (student_id, module_id, trait_id, level, comment, source, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'ai_accepted', ?)
                   ON CONFLICT(student_id, module_id, trait_id) DO UPDATE SET
                     level=excluded.level, comment=excluded.comment, source=excluded.source,
                     updated_at=excluded.updated_at""",
                (student_id, module_id, trait_id, entry.get("level"), entry.get("rationale"), now),
            )
        cur.execute(
            """INSERT INTO review_status (student_id, module_id, framing_note, status, updated_at)
               VALUES (?, ?, ?, 'in_progress', ?)
               ON CONFLICT(student_id, module_id) DO UPDATE SET
                 framing_note=excluded.framing_note, updated_at=excluded.updated_at""",
            (student_id, module_id, final.get("framing_note"), now),
        )
        recompute_status(cur, student_id, module_id)


def _ungraded_students(module_id: int) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            """SELECT s.id, s.name
               FROM students s
               JOIN modules m ON m.cohort_id = s.cohort_id
               LEFT JOIN review_status rs ON rs.student_id = s.id AND rs.module_id = m.id
               WHERE m.id = ? AND COALESCE(rs.status, 'not_started') = 'not_started'
               ORDER BY s.name""",
            (module_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def _run_batch(module_id: int, students: list[dict]) -> None:
    progress = _progress[module_id]
    for student in students:
        progress["current"] = student["name"]
        try:
            final = run_full_pipeline(student["id"], module_id)
            if final.get("status") == "graded":
                _finalize_graded(student["id"], module_id, final)
        except Exception as e:
            progress["errors"].append({"student": student["name"], "error": str(e)})
        progress["done"] += 1
    progress["current"] = None
    progress["running"] = False


@router.post("/modules/{module_id}/assess-all")
def start_assess_all(module_id: int):
    with db_cursor() as cur:
        cur.execute("SELECT id FROM modules WHERE id = ?", (module_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Module not found")

    existing = _progress.get(module_id)
    if existing and existing.get("running"):
        return {"started": False, "reason": "already_running", **existing}

    students = _ungraded_students(module_id)
    _progress[module_id] = {"running": True, "total": len(students), "done": 0, "current": None, "errors": []}
    if not students:
        _progress[module_id]["running"] = False
        return {"started": False, "reason": "nothing_to_grade", **_progress[module_id]}

    threading.Thread(target=_run_batch, args=(module_id, students), daemon=True).start()
    return {"started": True, **_progress[module_id]}


@router.get("/modules/{module_id}/assess-all/status")
def assess_all_status(module_id: int):
    return _progress.get(module_id, {"running": False, "total": 0, "done": 0, "current": None, "errors": []})
