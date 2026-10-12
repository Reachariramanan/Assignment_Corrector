import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ai.class_assistant import ask_class_assistant
from app.db import db_cursor

router = APIRouter(prefix="/api", tags=["assistant"])


@router.get("/assistant/chat")
def get_assistant_history(cohort_id: int):
    with db_cursor() as cur:
        cur.execute(
            "SELECT role, content, trace_json, created_at FROM class_chat_messages WHERE cohort_id = ? ORDER BY id",
            (cohort_id,),
        )
        return [
            {**{k: r[k] for k in r.keys() if k != "trace_json"}, "trace": json.loads(r["trace_json"]) if r["trace_json"] else []}
            for r in cur.fetchall()
        ]


class AssistantChatRequest(BaseModel):
    cohort_id: int
    message: str


@router.post("/assistant/chat")
def assistant_chat(payload: AssistantChatRequest):
    with db_cursor() as cur:
        cur.execute("SELECT name FROM cohorts WHERE id = ?", (payload.cohort_id,))
        cohort = cur.fetchone()
        if not cohort:
            raise HTTPException(404, "Cohort not found")

        cur.execute(
            "INSERT INTO class_chat_messages (cohort_id, role, content) VALUES (?, 'user', ?)",
            (payload.cohort_id, payload.message),
        )
        try:
            reply, _usage, trace = ask_class_assistant(payload.cohort_id, cohort["name"], payload.message)
        except Exception as e:
            raise HTTPException(502, f"Assistant call failed: {e}")

        cur.execute(
            "INSERT INTO class_chat_messages (cohort_id, role, content, trace_json) VALUES (?, 'assistant', ?, ?)",
            (payload.cohort_id, reply, json.dumps(trace)),
        )

        student_id = None
        for step in trace:
            if step.get("tool") != "student_summary" or not isinstance(step.get("result"), dict):
                continue
            # ToolProcessor wraps a tool's raw dict return in {"success", "result", "tool"} -
            # unwrap one level if present, otherwise assume the raw dict itself.
            payload = step["result"].get("result", step["result"])
            if isinstance(payload, dict) and payload.get("student_id") is not None:
                student_id = payload["student_id"]

        return {"reply": reply, "trace": trace, "student_id": student_id}
