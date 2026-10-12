import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ai.grading_agent import chat_followup
from app.ai.pipeline import run_full_pipeline
from app.db import db_cursor

router = APIRouter(prefix="/api", tags=["ai-assist"])


def _session_id(student_id: int, module_id: int) -> str:
    return f"{student_id}:{module_id}"


class AiAssistRequest(BaseModel):
    student_id: int
    module_id: int


@router.post("/ai-assist")
def ai_assist(payload: AiAssistRequest):
    with db_cursor() as cur:
        cur.execute("SELECT id FROM modules WHERE id = ?", (payload.module_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Module not found")
        cur.execute(
            "SELECT COUNT(*) AS n FROM submission_files WHERE student_id = ? AND module_id = ?",
            (payload.student_id, payload.module_id),
        )
        if cur.fetchone()["n"] == 0:
            raise HTTPException(404, "No submission files found for this student/module")

    # Run the full pipeline (briefing -> research -> review -> grade) OUTSIDE any open
    # cursor/transaction of our own - it does its own DB writes (usage log, dossier) and
    # SQLite only allows one writer at a time.
    try:
        final = run_full_pipeline(payload.student_id, payload.module_id)
    except Exception as e:
        raise HTTPException(502, f"AI grading pipeline failed: {e}")

    if final.get("status") == "not_submitted":
        # Research determined there's no genuine assignment attempt - review_status was
        # already finalized to 'not_submitted'/0% by the pipeline; nothing to suggest/accept.
        return {"not_submitted": True, "reason": final.get("reason"), "suggestions": []}

    with db_cursor() as cur:
        cur.execute(
            "SELECT id, name FROM rubric_traits WHERE module_id = ?", (payload.module_id,)
        )
        trait_by_name = {r["name"]: r["id"] for r in cur.fetchall()}

        suggestions = []
        for entry in final.get("traits", []):
            trait_id = trait_by_name.get(entry.get("trait"))
            if trait_id is None:
                continue
            cur.execute(
                """INSERT INTO ai_suggestions (student_id, module_id, trait_id, suggested_level, rationale, model)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (payload.student_id, payload.module_id, trait_id, entry.get("level"), entry.get("rationale"), "gemma-4-26b-a4b-it"),
            )
            suggestions.append({
                "trait_id": trait_id,
                "trait": entry.get("trait"),
                "level": entry.get("level"),
                "rationale": entry.get("rationale"),
            })

        return {"not_submitted": False, "framing_note": final.get("framing_note"), "suggestions": suggestions}


class ChatRequest(BaseModel):
    student_id: int
    module_id: int
    message: str


@router.post("/ai-assist/chat")
def ai_assist_chat(payload: ChatRequest):
    session_id = _session_id(payload.student_id, payload.module_id)
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO chat_messages (student_id, module_id, role, content) VALUES (?, ?, 'user', ?)",
            (payload.student_id, payload.module_id, payload.message),
        )

    try:
        reply, usage, trace = chat_followup(session_id, payload.message)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"AI chat call failed: {e}")

    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO chat_messages (student_id, module_id, role, content, trace_json) VALUES (?, ?, 'assistant', ?, ?)",
            (payload.student_id, payload.module_id, reply, json.dumps(trace)),
        )
        cur.execute(
            """INSERT INTO ai_usage_log (student_id, module_id, yukta_session_id, kind, tokens_prompt, tokens_completion, iterations)
               VALUES (?, ?, ?, 'chat', ?, ?, ?)""",
            (payload.student_id, payload.module_id, session_id, usage.get("tokens_prompt", 0), usage.get("tokens_completion", 0), usage.get("iterations", 1)),
        )
        return {"reply": reply, "trace": trace}


@router.get("/ai-assist/chat")
def get_chat_history(student_id: int, module_id: int):
    with db_cursor() as cur:
        cur.execute(
            "SELECT role, content, trace_json, created_at FROM chat_messages WHERE student_id = ? AND module_id = ? ORDER BY id",
            (student_id, module_id),
        )
        return [
            {**{k: r[k] for k in r.keys() if k != "trace_json"}, "trace": json.loads(r["trace_json"]) if r["trace_json"] else []}
            for r in cur.fetchall()
        ]
