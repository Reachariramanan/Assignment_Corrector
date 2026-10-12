"""SSE streaming chat endpoints: the agent's tool-call activity ("thinking") streams to
the client in real time as it happens, by running the (blocking) agent call in a worker
thread and relaying its callback events through a queue into an async-friendly generator.
The final answer text itself isn't token-streamed (Yukta's agent loop doesn't expose that),
but every tool call - and a 'thinking' pulse for each LLM round - appears live, which is
the part that previously only showed up all at once after the whole call finished."""

import json
import queue
import threading

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.ai.class_assistant import ask_class_assistant
from app.ai.grading_agent import chat_followup
from app.db import db_cursor

router = APIRouter(prefix="/api", tags=["streaming"])


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _stream_from_worker(worker_fn):
    """worker_fn(on_event) must do its work, call on_event(...) for live updates, and
    return a dict to send as the final 'done' event (or raise, surfaced as 'error')."""
    q: "queue.Queue[dict | None]" = queue.Queue()

    def run():
        try:
            final = worker_fn(lambda e: q.put(e))
            q.put({"type": "done", **final})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
        finally:
            q.put(None)

    threading.Thread(target=run, daemon=True).start()

    def generator():
        while True:
            event = q.get()
            if event is None:
                break
            yield _sse(event)

    return StreamingResponse(generator(), media_type="text/event-stream")


class ChatStreamRequest(BaseModel):
    student_id: int
    module_id: int
    message: str


@router.post("/ai-assist/chat/stream")
def ai_assist_chat_stream(payload: ChatStreamRequest):
    session_id = f"{payload.student_id}:{payload.module_id}"
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO chat_messages (student_id, module_id, role, content) VALUES (?, ?, 'user', ?)",
            (payload.student_id, payload.module_id, payload.message),
        )

    def worker(on_event):
        # Any exception here (including the ValueError chat_followup raises when there's no
        # active grading session yet) is caught by _stream_from_worker and surfaced as an
        # {"type": "error"} SSE event - there's no request/response cycle left at this point
        # for FastAPI's own HTTPException handling to intercept, since this runs in a thread.
        reply, usage, trace = chat_followup(session_id, payload.message, on_event=on_event)
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

    return _stream_from_worker(worker)


class AssistantStreamRequest(BaseModel):
    cohort_id: int
    message: str


@router.post("/assistant/chat/stream")
def assistant_chat_stream(payload: AssistantStreamRequest):
    with db_cursor() as cur:
        cur.execute("SELECT name FROM cohorts WHERE id = ?", (payload.cohort_id,))
        cohort = cur.fetchone()
        if not cohort:
            raise HTTPException(404, "Cohort not found")
        cohort_name = cohort["name"]
        cur.execute(
            "INSERT INTO class_chat_messages (cohort_id, role, content) VALUES (?, 'user', ?)",
            (payload.cohort_id, payload.message),
        )

    def worker(on_event):
        reply, _usage, trace = ask_class_assistant(payload.cohort_id, cohort_name, payload.message, on_event=on_event)
        with db_cursor() as cur:
            cur.execute(
                "INSERT INTO class_chat_messages (cohort_id, role, content, trace_json) VALUES (?, 'assistant', ?, ?)",
                (payload.cohort_id, reply, json.dumps(trace)),
            )

        student_id = None
        for step in trace:
            if step.get("tool") != "student_summary" or not isinstance(step.get("result"), dict):
                continue
            inner = step["result"].get("result", step["result"])
            if isinstance(inner, dict) and inner.get("student_id") is not None:
                student_id = inner["student_id"]

        return {"reply": reply, "trace": trace, "student_id": student_id}

    return _stream_from_worker(worker)
