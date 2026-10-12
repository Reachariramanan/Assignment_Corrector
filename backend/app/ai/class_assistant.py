"""Class-wide assistant: a Yukta agent with read-only DB tools, scoped to one
cohort, that can answer cross-student / cross-module questions
(e.g. "which students are weakest on Task 2 evidence analysis?").

One persistent agent session per cohort (session_id = f"class:{cohort_id}"),
so the conversation carries context across turns.
"""

from typing import Any, Callable

from yukta import AgentConfig, SystemPrompt, Tool, ToolParameter, ToolProcessor, ToolType, create_agent, create_memory

from app.ai.common import UsageCapture, agent_response, new_llm_client
from app.db import db_cursor

_agent_cache: dict[str, Any] = {}

CLASS_ASSISTANT_SYSTEM = """You are a teaching-assistant chatbot for course instructors reviewing student \
case-study submissions in the "Submission Review Interface". You have tools to query the real review \
database for cohort "{cohort_name}" - always call a tool rather than guessing at numbers. Be concise, \
cite specific student names and trait names, and never fabricate a score you haven't retrieved via a tool.
"""


def _make_tools(cohort_id: int) -> ToolProcessor:
    def list_students(module_name: str = "") -> list[dict]:
        with db_cursor() as cur:
            cur.execute(
                """SELECT s.name, m.name AS module, rs.status, rs.total_weighted_score, rs.band
                   FROM students s
                   JOIN modules m ON m.cohort_id = s.cohort_id
                   LEFT JOIN review_status rs ON rs.student_id = s.id AND rs.module_id = m.id
                   WHERE s.cohort_id = ? AND (? = '' OR m.name = ?)
                   ORDER BY m.name, s.name""",
                (cohort_id, module_name, module_name),
            )
            return [dict(r) for r in cur.fetchall()]

    def trait_averages(module_name: str) -> list[dict]:
        with db_cursor() as cur:
            cur.execute(
                """SELECT rt.name AS trait, rt.weight_pct, AVG(r.level) AS avg_level, COUNT(r.level) AS n_scored
                   FROM rubric_traits rt
                   JOIN modules m ON m.id = rt.module_id
                   LEFT JOIN reviews r ON r.trait_id = rt.id
                   WHERE m.cohort_id = ? AND m.name = ?
                   GROUP BY rt.id ORDER BY rt.sort_order""",
                (cohort_id, module_name),
            )
            return [dict(r) for r in cur.fetchall()]

    def lowest_scorers(trait_name: str, module_name: str, limit: int = 5) -> list[dict]:
        with db_cursor() as cur:
            cur.execute(
                """SELECT s.name AS student, r.level, r.comment
                   FROM reviews r
                   JOIN rubric_traits rt ON rt.id = r.trait_id AND rt.name = ?
                   JOIN modules m ON m.id = rt.module_id AND m.name = ?
                   JOIN students s ON s.id = r.student_id
                   WHERE m.cohort_id = ? AND r.level IS NOT NULL
                   ORDER BY r.level ASC LIMIT ?""",
                (trait_name, module_name, cohort_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]

    def student_summary(student_name: str) -> dict:
        with db_cursor() as cur:
            cur.execute(
                "SELECT id, name FROM students WHERE cohort_id = ? AND name LIKE ?",
                (cohort_id, f"%{student_name}%"),
            )
            student = cur.fetchone()
            if not student:
                return {"error": f"No student matching '{student_name}' in this cohort"}
            cur.execute(
                """SELECT m.name AS module, rs.total_weighted_score, rs.band, rs.status
                   FROM review_status rs JOIN modules m ON m.id = rs.module_id
                   WHERE rs.student_id = ? ORDER BY m.imported_at""",
                (student["id"],),
            )
            modules = [dict(r) for r in cur.fetchall()]
            cur.execute(
                """SELECT m.name AS module, rt.name AS trait, r.level, r.comment
                   FROM reviews r JOIN rubric_traits rt ON rt.id = r.trait_id
                   JOIN modules m ON m.id = r.module_id
                   WHERE r.student_id = ? ORDER BY m.imported_at, rt.sort_order""",
                (student["id"],),
            )
            traits = [dict(r) for r in cur.fetchall()]
            return {"student_id": student["id"], "student": student["name"], "modules": modules, "trait_scores": traits}

    processor = ToolProcessor()
    processor.add_tool(
        Tool(
            name="list_students",
            description="List students in this cohort with their status/score/band, optionally filtered to one module by exact name.",
            parameters=[ToolParameter(name="module_name", type="string", description="Exact module name, or empty for all modules", required=False, default="")],
            tool_type=ToolType.CUSTOM,
            function=list_students,
        )
    )
    processor.add_tool(
        Tool(
            name="trait_averages",
            description="Get the class average score (1-4) per rubric trait for a given module.",
            parameters=[ToolParameter(name="module_name", type="string", description="Exact module name", required=True)],
            tool_type=ToolType.CUSTOM,
            function=trait_averages,
        )
    )
    processor.add_tool(
        Tool(
            name="lowest_scorers",
            description="List the students with the lowest scores on a specific rubric trait in a module, with their reviewer comments.",
            parameters=[
                ToolParameter(name="trait_name", type="string", description="Exact rubric trait name", required=True),
                ToolParameter(name="module_name", type="string", description="Exact module name", required=True),
                ToolParameter(name="limit", type="integer", description="Max students to return", required=False, default=5),
            ],
            tool_type=ToolType.CUSTOM,
            function=lowest_scorers,
        )
    )
    processor.add_tool(
        Tool(
            name="student_summary",
            description="Get one student's full cross-module performance history (all modules, all trait scores) by name (partial match ok).",
            parameters=[ToolParameter(name="student_name", type="string", description="Student name or partial name", required=True)],
            tool_type=ToolType.CUSTOM,
            function=student_summary,
        )
    )
    return processor


def get_or_create_assistant(cohort_id: int, cohort_name: str):
    session_id = f"class:{cohort_id}"
    if session_id in _agent_cache:
        return _agent_cache[session_id]

    system_prompt = SystemPrompt(
        prompt_name="ClassAssistant",
        prompt_text=CLASS_ASSISTANT_SYSTEM.format(cohort_name=cohort_name),
    )
    memory = create_memory(system_prompt=system_prompt.get_prompt(), max_tokens=8000, session_id=session_id)
    usage_capture = UsageCapture()
    agent = create_agent(
        name=f"class-assistant-{cohort_id}",
        system_prompt=system_prompt,
        llm_client=new_llm_client(temperature=0.3),
        memory=memory,
        use_memory_cache=True,
        tools_processor=_make_tools(cohort_id),
        config=AgentConfig(temperature=0.3, max_iter=6, verbose=False),
        callbacks=usage_capture,
    )
    agent._usage_capture = usage_capture
    _agent_cache[session_id] = agent
    return agent


def ask_class_assistant(
    cohort_id: int, cohort_name: str, message: str, on_event: Callable[[dict], None] | None = None
) -> tuple[str, dict[str, int], list[dict]]:
    agent = get_or_create_assistant(cohort_id, cohort_name)
    agent._usage_capture.reset()
    agent._usage_capture.live_sink = on_event
    try:
        result = agent.run(user_message=message, reset_conversation=False)
    finally:
        agent._usage_capture.live_sink = None
    usage = {**agent._usage_capture.last_usage, "iterations": result.get("iterations", 1)}
    return agent_response(result), usage, agent._usage_capture.trace
