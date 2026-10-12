from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import db_cursor

router = APIRouter(prefix="/api", tags=["modules"])


class RenameRequest(BaseModel):
    name: str


@router.get("/cohorts")
def list_cohorts():
    with db_cursor() as cur:
        cur.execute("SELECT id, name, created_at FROM cohorts ORDER BY created_at")
        return [dict(r) for r in cur.fetchall()]


@router.patch("/cohorts/{cohort_id}")
def rename_cohort(cohort_id: int, payload: RenameRequest):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Name cannot be empty")
    with db_cursor() as cur:
        cur.execute("SELECT id FROM cohorts WHERE id = ?", (cohort_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Course not found")
        try:
            cur.execute("UPDATE cohorts SET name = ? WHERE id = ?", (name, cohort_id))
        except Exception:
            raise HTTPException(409, f"A course named '{name}' already exists")
        return {"id": cohort_id, "name": name}


@router.delete("/cohorts/{cohort_id}")
def delete_cohort(cohort_id: int):
    with db_cursor() as cur:
        cur.execute("SELECT id FROM cohorts WHERE id = ?", (cohort_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Course not found")
        cur.execute("DELETE FROM cohorts WHERE id = ?", (cohort_id,))
        return {"deleted": True}


@router.get("/cohorts/{cohort_id}/modules")
def list_modules(cohort_id: int):
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, cohort_id, name, imported_at FROM modules WHERE cohort_id = ? ORDER BY imported_at",
            (cohort_id,),
        )
        return [dict(r) for r in cur.fetchall()]


@router.patch("/modules/{module_id}")
def rename_module(module_id: int, payload: RenameRequest):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Name cannot be empty")
    with db_cursor() as cur:
        cur.execute("SELECT id, cohort_id FROM modules WHERE id = ?", (module_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Module not found")
        try:
            cur.execute("UPDATE modules SET name = ? WHERE id = ?", (name, module_id))
        except Exception:
            raise HTTPException(409, f"A module named '{name}' already exists in this course")
        return {"id": module_id, "name": name}


@router.delete("/modules/{module_id}")
def delete_module(module_id: int):
    with db_cursor() as cur:
        cur.execute("SELECT id, cohort_id FROM modules WHERE id = ?", (module_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Module not found")
        cohort_id = row["cohort_id"]
        cur.execute("DELETE FROM modules WHERE id = ?", (module_id,))
        # A student only exists because some module's import created them - once their last
        # module (and all its submission_files) is gone, remove the now-meaningless bare
        # student row too, rather than leaving an orphaned "ghost" student in the course.
        cur.execute(
            """DELETE FROM students WHERE cohort_id = ? AND id NOT IN (
                 SELECT DISTINCT student_id FROM submission_files
               )""",
            (cohort_id,),
        )
        return {"deleted": True, "orphaned_students_removed": cur.rowcount}


@router.get("/modules/{module_id}")
def get_module(module_id: int):
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, cohort_id, name, case_study_html, imported_at FROM modules WHERE id = ?",
            (module_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Module not found")
        return dict(row)


@router.get("/modules/{module_id}/rubric")
def get_rubric(module_id: int):
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, name, weight_pct, sort_order FROM rubric_traits WHERE module_id = ? ORDER BY sort_order",
            (module_id,),
        )
        traits = [dict(r) for r in cur.fetchall()]
        for t in traits:
            cur.execute(
                "SELECT level, label, descriptor FROM rubric_levels WHERE trait_id = ? ORDER BY level",
                (t["id"],),
            )
            t["levels"] = [dict(r) for r in cur.fetchall()]
        return traits


@router.get("/modules/{module_id}/students")
def list_students(module_id: int):
    with db_cursor() as cur:
        cur.execute(
            """SELECT s.id, s.name, s.moodle_participant_id,
                      COALESCE(rs.status, 'not_started') AS status,
                      rs.total_weighted_score, rs.band
               FROM students s
               JOIN modules m ON m.cohort_id = s.cohort_id
               LEFT JOIN review_status rs ON rs.student_id = s.id AND rs.module_id = m.id
               WHERE m.id = ?
               ORDER BY s.name""",
            (module_id,),
        )
        return [dict(r) for r in cur.fetchall()]
