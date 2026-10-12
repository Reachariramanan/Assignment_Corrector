import json

from fastapi import APIRouter

from app.db import db_cursor

router = APIRouter(prefix="/api", tags=["dossier"])


@router.get("/dossier")
def get_dossier(student_id: int, module_id: int):
    with db_cursor() as cur:
        cur.execute(
            "SELECT dossier_json, review_draft_json, files_read_count, created_at FROM research_dossiers "
            "WHERE student_id = ? AND module_id = ?",
            (student_id, module_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "dossier": json.loads(row["dossier_json"]),
            "review_draft": json.loads(row["review_draft_json"]) if row["review_draft_json"] else None,
            "files_read_count": row["files_read_count"],
            "created_at": row["created_at"],
        }
