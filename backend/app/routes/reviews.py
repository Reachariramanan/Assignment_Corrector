from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import db_cursor
from app.review_status import recompute_status

router = APIRouter(prefix="/api", tags=["reviews"])


class TraitScore(BaseModel):
    trait_id: int
    level: int = Field(ge=1, le=4)
    comment: str | None = None
    source: str = "manual"


class ReviewPayload(BaseModel):
    framing_note: str | None = None
    traits: list[TraitScore]


@router.get("/reviews")
def get_reviews(student_id: int, module_id: int):
    with db_cursor() as cur:
        cur.execute(
            """SELECT rt.id AS trait_id, rt.name, rt.weight_pct, r.level, r.comment, r.source
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
        return {"traits": traits, "summary": dict(status_row) if status_row else None}


@router.put("/reviews")
def put_reviews(student_id: int, module_id: int, payload: ReviewPayload):
    with db_cursor() as cur:
        cur.execute("SELECT id FROM students WHERE id = ?", (student_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Student not found")

        for t in payload.traits:
            cur.execute(
                """INSERT INTO reviews (student_id, module_id, trait_id, level, comment, source, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(student_id, module_id, trait_id) DO UPDATE SET
                     level=excluded.level, comment=excluded.comment, source=excluded.source,
                     updated_at=excluded.updated_at""",
                (student_id, module_id, t.trait_id, t.level, t.comment, t.source, datetime.now(timezone.utc).isoformat()),
            )

        cur.execute(
            """INSERT INTO review_status (student_id, module_id, framing_note, status, updated_at)
               VALUES (?, ?, ?, 'in_progress', ?)
               ON CONFLICT(student_id, module_id) DO UPDATE SET
                 framing_note=excluded.framing_note, updated_at=excluded.updated_at""",
            (student_id, module_id, payload.framing_note, datetime.now(timezone.utc).isoformat()),
        )
        recompute_status(cur, student_id, module_id)

        cur.execute(
            "SELECT framing_note, total_weighted_score, band, status FROM review_status WHERE student_id = ? AND module_id = ?",
            (student_id, module_id),
        )
        return dict(cur.fetchone())
