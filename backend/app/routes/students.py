from fastapi import APIRouter, HTTPException

from app.db import db_cursor

router = APIRouter(prefix="/api", tags=["students"])


@router.get("/students/{student_id}/submissions")
def get_submissions(student_id: int, module_id: int):
    with db_cursor() as cur:
        cur.execute(
            """SELECT id, kind, original_filename, source_format, extracted_html
               FROM submission_files WHERE student_id = ? AND module_id = ?
               ORDER BY CASE kind
                 WHEN 'worksheet' THEN 1 WHEN 'control_note' THEN 2 WHEN 'combined' THEN 3
                 WHEN 'onlinetext' THEN 4 WHEN 'ai_declaration' THEN 5 ELSE 6 END, original_filename""",
            (student_id, module_id),
        )
        return [dict(r) for r in cur.fetchall()]


@router.get("/students/{student_id}/profile")
def get_student_profile(student_id: int):
    with db_cursor() as cur:
        cur.execute("SELECT id, name, moodle_participant_id, cohort_id FROM students WHERE id = ?", (student_id,))
        student = cur.fetchone()
        if not student:
            raise HTTPException(404, "Student not found")

        cur.execute(
            """SELECT m.id AS module_id, m.name AS module, rs.total_weighted_score, rs.band, rs.status, m.imported_at
               FROM modules m
               LEFT JOIN review_status rs ON rs.module_id = m.id AND rs.student_id = ?
               WHERE m.cohort_id = ? ORDER BY m.imported_at""",
            (student_id, student["cohort_id"]),
        )
        modules = [dict(r) for r in cur.fetchall()]

        cur.execute(
            """SELECT m.name AS module, rt.name AS trait, r.level
               FROM reviews r
               JOIN rubric_traits rt ON rt.id = r.trait_id
               JOIN modules m ON m.id = r.module_id
               WHERE r.student_id = ? ORDER BY m.imported_at, rt.sort_order""",
            (student_id,),
        )
        trait_history = [dict(r) for r in cur.fetchall()]

        scored = [m["total_weighted_score"] for m in modules if m["total_weighted_score"] is not None]
        avg_score = round(sum(scored) / len(scored), 1) if scored else None

        return {
            "student": dict(student),
            "modules": modules,
            "trait_history": trait_history,
            "average_weighted_score": avg_score,
        }


@router.get("/students/{student_id}/report")
def get_report(student_id: int, module_id: int):
    with db_cursor() as cur:
        cur.execute("SELECT id, name, moodle_participant_id FROM students WHERE id = ?", (student_id,))
        student = cur.fetchone()
        if not student:
            raise HTTPException(404, "Student not found")
        cur.execute(
            """SELECT rt.name AS trait, rt.weight_pct, r.level, r.comment
               FROM rubric_traits rt
               LEFT JOIN reviews r ON r.trait_id = rt.id AND r.student_id = ? AND r.module_id = ?
               WHERE rt.module_id = ? ORDER BY rt.sort_order""",
            (student_id, module_id, module_id),
        )
        traits = [dict(r) for r in cur.fetchall()]
        cur.execute(
            "SELECT framing_note, total_weighted_score, band, status FROM review_status WHERE student_id = ? AND module_id = ?",
            (student_id, module_id),
        )
        status_row = cur.fetchone()
        return {
            "student": dict(student),
            "traits": traits,
            "summary": dict(status_row) if status_row else None,
        }
