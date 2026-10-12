"""
coordinator.py — Structured-rounds coordinator for HIERARCHICAL teams.

Protocol
--------
Each round:
  1. Leader agent is invoked with the task + prior-round reports.
     It must respond with a JSON object matching ``LeaderBrief``.
  2. Each assignment in the brief is dispatched to the named agent (in parallel).
     Every sub-agent must respond with a JSON object matching ``AgentReport``.
  3. The collected reports are fed back to the leader for the next round.
  4. When the leader sets ``done=true`` the session ends with a final answer.

This replaces the keyword-based approval detection in ``GroupChatSession`` for
HIERARCHICAL teams.
"""

from __future__ import annotations

import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("yukta.coordinator")

try:
    from yukta.core.memory import create_memory
    YUKTA_AVAILABLE = True
except ImportError:
    YUKTA_AVAILABLE = False
    create_memory = None

from .models import (
    AgentData, AgentReport, ApprovalStatus, LeaderBrief,
    SystemConfig, TeamData, TeamSession,
)
from .runner import run_agent
from .transformer import transform_agent

# ── Prompt fragments injected at runtime ─────────────────────────────────────

_LEADER_SCHEMA = """
You are the coordinator for this team. Your job is to break the goal into tasks,
assign them to the right agents, and synthesise their results.

Each time you respond you MUST output ONLY a valid JSON object — no prose, no markdown —
that matches this schema exactly:

{
  "round":        <int>,
  "assignments":  [{"agent_id": "<str>", "task": "<str>", "expected_output": "<str>"}],
  "context":      "<str>   (summary of progress so far)",
  "done":         <bool>,
  "final_answer": "<str>   (populate only when done=true)"
}

Rules:
- Set done=true and populate final_answer when the team goal is fully achieved.
- assignments may be empty only when done=true.
- agent_id must exactly match one of the agent IDs you were told about.
- Output raw JSON only — the first character must be '{'.
"""

_AGENT_SCHEMA = (
    "Respond ONLY with a valid JSON object that matches this schema exactly — no prose:\n"
    '{"agent_id": "<your agent_id>", "status": "done|blocked|needs_help", '
    '"output": "<your work>", "confidence": <0.0-1.0>}\n'
    "The first character of your response must be '{'."
)


def _parse_leader_brief(raw: Dict[str, Any], round_num: int) -> Optional[LeaderBrief]:
    """Extract a LeaderBrief from the agent's raw response dict."""
    response_text: str = raw.get("response", "")
    # Strip markdown fences if present
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Try to find the first '{' ... '}' block
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end])
            except (json.JSONDecodeError, ValueError):
                logger.warning("Leader response is not valid JSON (round %d): %r", round_num, text[:200])
                return None
        else:
            logger.warning("No JSON found in leader response (round %d): %r", round_num, text[:200])
            return None

    try:
        return LeaderBrief(
            round=data.get("round", round_num),
            assignments=data.get("assignments", []),
            context=data.get("context", ""),
            done=bool(data.get("done", False)),
            final_answer=data.get("final_answer", ""),
        )
    except Exception as exc:
        logger.warning("Failed to construct LeaderBrief: %s", exc)
        return None


def _parse_agent_report(raw: Dict[str, Any], agent_id: str) -> AgentReport:
    """Extract an AgentReport from the agent's raw response dict."""
    response_text: str = raw.get("response", "")
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end])
            except (json.JSONDecodeError, ValueError):
                data = {}
        else:
            data = {}

    return AgentReport(
        agent_id=data.get("agent_id", agent_id),
        status=data.get("status", "done"),
        output=data.get("output", response_text),
        confidence=float(data.get("confidence", 0.5)),
        metadata=data.get("metadata", {}),
    )


class LeaderCoordinator:
    """
    Structured-rounds coordinator for HIERARCHICAL teams.

    The leader issues explicit per-agent task assignments each round and
    receives structured JSON reports in return.  No keyword matching is used.

    Args:
        team:      TeamData describing the team (leader + members).
        ecosystem: Loaded ecosystem dict (keys: agents, skills, tools, config).
        llm_client: LLM client to inject into every built agent.
    """

    def __init__(
        self,
        team: TeamData,
        ecosystem: Dict[str, Any],
        llm_client: Any = None,
        on_round_complete: Optional[Callable] = None,
    ) -> None:
        if not YUKTA_AVAILABLE:
            raise RuntimeError("yukta package is required for team coordination")

        self.team = team
        self.ecosystem = ecosystem
        self.llm_client = llm_client
        self.on_round_complete = on_round_complete
        self.session_id = f"coord_{team.team_id}_{uuid.uuid4().hex[:8]}"
        self.session = TeamSession(session_id=self.session_id, team_id=team.team_id)

        self.shared_memory = create_memory(
            system_prompt="[Coordinator Bus]",
            session_id=self.session_id,
        ) if create_memory else None

        self._built_agents: Dict[str, Any] = {}

    # ── Agent building ────────────────────────────────────────────────────────

    def _build_agent(self, agent_id: str, extra_system_suffix: str = "") -> Any:
        cache_key = f"{agent_id}::{extra_system_suffix}"
        if cache_key in self._built_agents:
            return self._built_agents[cache_key]

        agents: List[AgentData] = self.ecosystem.get("agents", [])
        agent_data = next((a for a in agents if a.agent_id == agent_id), None)
        if not agent_data:
            raise ValueError(f"Agent '{agent_id}' not found in ecosystem")

        # Append the structured-output schema to the agent's system prompt
        if extra_system_suffix:
            agent_data = _clone_agent_data_with_extra_prompt(agent_data, extra_system_suffix)

        yukta_agent = transform_agent(
            agent_data=agent_data,
            loaded_skills=self.ecosystem.get("skills", []),
            loaded_tools=self.ecosystem.get("tools", []),
            system_config=self.ecosystem.get("config"),
            bootstrap_prompt=None,
            memory=self.shared_memory,
        )

        if self.llm_client:
            yukta_agent.set_llm_client(self.llm_client)

        # Give agents enough headroom to produce their JSON output
        yukta_agent.config.max_iter = 5

        self._built_agents[cache_key] = yukta_agent
        return yukta_agent

    # ── Round execution ───────────────────────────────────────────────────────

    def _invoke_leader(self, message: str) -> Dict[str, Any]:
        agent = self._build_agent(self.team.leader_id, extra_system_suffix=_LEADER_SCHEMA)
        return run_agent(agent, message)

    def _build_leader_input(self, task: str, round_num: int) -> str:
        if round_num == 1:
            member_ids = ", ".join(self.team.members) or "(none)"
            return (
                f"TEAM GOAL: {task}\n\n"
                f"Available team members: {member_ids}\n"
                f"Your own agent_id: {self.team.leader_id}\n\n"
                "Issue your round-1 task brief as JSON."
            )

        history = self.session.history
        reports_text = json.dumps(history[-1].get("reports", []), indent=2) if history else "[]"
        return (
            f"TEAM GOAL: {task}\n\n"
            f"Round {round_num - 1} agent reports:\n{reports_text}\n\n"
            "Issue your next brief as JSON, or set done=true with a final_answer."
        )

    def _execute_assignments(
        self, brief: LeaderBrief, task: str
    ) -> List[AgentReport]:
        """Dispatch each assignment to its agent in parallel."""
        reports: List[AgentReport] = []

        def _run_one(assignment: Dict[str, Any]) -> AgentReport:
            agent_id: str = assignment.get("agent_id", "")
            sub_task: str = assignment.get("task", task)
            expected: str = assignment.get("expected_output", "")

            prompt = (
                f"TASK: {sub_task}\n"
                f"EXPECTED OUTPUT: {expected}\n\n"
                f"Your agent_id is: {agent_id}\n\n"
                f"{_AGENT_SCHEMA}"
            )

            try:
                agent = self._build_agent(agent_id)
                raw = run_agent(agent, prompt)
                return _parse_agent_report(raw, agent_id)
            except Exception as exc:
                logger.error("Agent '%s' failed: %s", agent_id, exc)
                return AgentReport(
                    agent_id=agent_id,
                    status="blocked",
                    output=f"Agent execution error: {exc}",
                    confidence=0.0,
                )

        with ThreadPoolExecutor(max_workers=max(1, len(brief.assignments))) as pool:
            futures = {pool.submit(_run_one, a): a for a in brief.assignments}
            for future in as_completed(futures):
                try:
                    reports.append(future.result())
                except Exception as exc:
                    assignment = futures[future]
                    reports.append(AgentReport(
                        agent_id=assignment.get("agent_id", "unknown"),
                        status="blocked",
                        output=str(exc),
                        confidence=0.0,
                    ))

        return reports

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self, task: str, max_rounds: int = 5) -> Dict[str, Any]:
        """
        Execute the team using structured rounds.

        Args:
            task:       The high-level task for the team.
            max_rounds: Maximum coordination rounds before giving up.

        Returns:
            dict with keys: success, final_answer (if success), rounds, history, session.
        """
        logger.info("LeaderCoordinator '%s' started for team '%s'", self.session_id, self.team.team_id)

        for round_num in range(1, max_rounds + 1):
            logger.info("Round %d/%d — invoking leader '%s'", round_num, max_rounds, self.team.leader_id)

            leader_input = self._build_leader_input(task, round_num)
            raw_leader = self._invoke_leader(leader_input)

            if not raw_leader.get("success"):
                logger.error("Leader agent failed on round %d: %s", round_num, raw_leader.get("error"))
                return {
                    "success": False,
                    "reason": "leader_agent_failed",
                    "error": raw_leader.get("error"),
                    "rounds": round_num,
                    "history": self.session.history,
                    "session": self.session,
                }

            brief = _parse_leader_brief(raw_leader, round_num)
            if brief is None:
                logger.error("Leader produced invalid JSON on round %d — aborting", round_num)
                return {
                    "success": False,
                    "reason": "leader_invalid_json",
                    "rounds": round_num,
                    "history": self.session.history,
                    "session": self.session,
                }

            if brief.done:
                self.session.status = ApprovalStatus.APPROVED
                logger.info("Team goal achieved in %d round(s). Final answer ready.", round_num)
                return {
                    "success": True,
                    "final_answer": brief.final_answer,
                    "rounds": round_num,
                    "history": self.session.history,
                    "session": self.session,
                }

            logger.info("Dispatching %d assignment(s) from round %d brief", len(brief.assignments), round_num)
            reports = self._execute_assignments(brief, task)

            self.session.history.append({
                "round": round_num,
                "brief": asdict(brief),
                "reports": [asdict(r) for r in reports],
            })
            self.session.iteration_count += 1

            if self.on_round_complete:
                self.on_round_complete(round_num, self.session.history)

        logger.warning("LeaderCoordinator: max_rounds (%d) exceeded without completion", max_rounds)
        return {
            "success": False,
            "reason": "max_rounds_exceeded",
            "rounds": max_rounds,
            "history": self.session.history,
            "session": self.session,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clone_agent_data_with_extra_prompt(agent_data: AgentData, suffix: str) -> AgentData:
    """Return a shallow copy of AgentData with *suffix* appended to the role description."""
    import copy
    clone = copy.copy(agent_data)
    clone.role = (agent_data.role or "") + "\n\n" + suffix
    return clone


__all__ = ["LeaderCoordinator"]
