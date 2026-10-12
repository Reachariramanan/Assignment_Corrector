import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ai.prompt_coach import assess_ai_usage
from app.db import db_cursor

router = APIRouter(prefix="/api", tags=["ai-usage"])


def _strip_html(html: str) -> str:
    import re

    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _row_to_response(row) -> dict:
    return {
        "has_declaration": bool(row["has_declaration"]),
        "declared_tools": json.loads(row["declared_tools"]) if row["declared_tools"] else [],
        "integration_quality": row["integration_quality"],
        "coaching_note": row["coaching_note"],
        "prompting_suggestions": json.loads(row["prompting_suggestions"]) if row["prompting_suggestions"] else [],
    }


@router.get("/ai-usage")
def get_ai_usage(student_id: int, module_id: int):
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM ai_usage_assessments WHERE student_id = ? AND module_id = ?",
            (student_id, module_id),
        )
        row = cur.fetchone()
        if not row:
            return {"has_declaration": None}
        return _row_to_response(row)


class AssessRequest(BaseModel):
    student_id: int
    module_id: int


@router.post("/ai-usage/assess")
def assess(payload: AssessRequest):
    with db_cursor() as cur:
        cur.execute(
            "SELECT case_study_html FROM modules WHERE id = ?", (payload.module_id,)
        )
        module_row = cur.fetchone()
        if not module_row:
            raise HTTPException(404, "Module not found")

        cur.execute(
            "SELECT extracted_text FROM submission_files WHERE student_id = ? AND module_id = ? AND kind = 'ai_declaration'",
            (payload.student_id, payload.module_id),
        )
        decl_row = cur.fetchone()
        if not decl_row:
            cur.execute(
                """INSERT INTO ai_usage_assessments (student_id, module_id, has_declaration)
                   VALUES (?, ?, 0)
                   ON CONFLICT(student_id, module_id) DO UPDATE SET has_declaration=0""",
                (payload.student_id, payload.module_id),
            )
            return {"has_declaration": False}

        cur.execute(
            "SELECT kind, extracted_text FROM submission_files WHERE student_id = ? AND module_id = ? AND kind != 'ai_declaration'",
            (payload.student_id, payload.module_id),
        )
        other_files = cur.fetchall()
        submission_text = "\n\n".join(f"--- {f['kind'].upper()} ---\n{f['extracted_text']}" for f in other_files)

        try:
            result, _usage = assess_ai_usage(
                _strip_html(module_row["case_study_html"]), decl_row["extracted_text"], submission_text
            )
        except Exception as e:
            raise HTTPException(502, f"AI-usage coaching call failed: {e}")

        cur.execute(
            """INSERT INTO ai_usage_assessments
                 (student_id, module_id, has_declaration, declared_tools, integration_quality, coaching_note, prompting_suggestions, model)
               VALUES (?, ?, 1, ?, ?, ?, ?, ?)
               ON CONFLICT(student_id, module_id) DO UPDATE SET
                 has_declaration=1, declared_tools=excluded.declared_tools, integration_quality=excluded.integration_quality,
                 coaching_note=excluded.coaching_note, prompting_suggestions=excluded.prompting_suggestions, model=excluded.model""",
            (
                payload.student_id,
                payload.module_id,
                json.dumps(result.get("declared_tools", [])),
                result.get("integration_quality"),
                result.get("coaching_note"),
                json.dumps(result.get("prompting_suggestions", [])),
                "gemma-4-26b-a4b-it",
            ),
        )
        return {"has_declaration": True, **result}
