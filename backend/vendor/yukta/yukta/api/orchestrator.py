"""
orchestrator.py — Moderator and execution logic for Team workflows.

Provides team orchestration capabilities for multi-agent collaboration.
"""

import logging
from typing import Dict, Any, List, Optional, Callable
import uuid

logger = logging.getLogger("yukta.orchestrator")

# Try to import from yukta, with fallback
try:
    from yukta.core.memory import create_memory
    from yukta.core.Clients.llmclientfactory import BaseLLMClient
    YUKTA_AVAILABLE = True
except ImportError:
    YUKTA_AVAILABLE = False
    BaseLLMClient = Any
    create_memory = None

from .models import TeamData, AgentData, TeamStructure, TeamSession, ApprovalStatus, HitlMode
from .runner import run_agent
from .transformer import transform_agent
from .coordinator import LeaderCoordinator


class SpeakerSelector:
    """Decides who speaks next in a group chat."""

    @staticmethod
    def select_next(team: TeamData, session: TeamSession) -> Optional[str]:
        """Determine the next speaker based on team structure."""
        if team.structure == TeamStructure.HIERARCHICAL:
            if session.iteration_count == 0:
                return team.leader_id
            elif session.status == ApprovalStatus.REVISION_REQUESTED:
                return team.members[0] if team.members else None
            elif session.current_speaker != team.leader_id:
                return team.leader_id
            else:
                # Cycle through members in order
                if not team.members:
                    return team.leader_id
                member_idx = ((session.iteration_count - 1) // 2) % len(team.members)
                return team.members[member_idx]

        elif team.structure == TeamStructure.FLAT:
            all_agents = [team.leader_id] + team.members
            if not session.current_speaker:
                return all_agents[0]

            try:
                curr_idx = all_agents.index(session.current_speaker)
                return all_agents[(curr_idx + 1) % len(all_agents)]
            except ValueError:
                return all_agents[0]

        return team.leader_id


class GroupChatSession:
    """Manages the lifecycle of a multi-agent team execution."""

    def __init__(self, team: TeamData, ecosystem: Dict[str, Any], llm_client: Any = None):
        if not YUKTA_AVAILABLE:
            raise RuntimeError("Yukta package is required for team orchestration")

        self.team = team
        self.ecosystem = ecosystem
        self.llm_client = llm_client
        self.session_id = f"team_{team.team_id}_{uuid.uuid4().hex[:8]}"
        self.session = TeamSession(
            session_id=self.session_id,
            team_id=team.team_id
        )

        self.shared_memory = create_memory(
            system_prompt="[Group Chat Bus Initialization]",
            session_id=self.session_id
        )

        self.built_agents = {}

    def _build_agent(self, agent_id: str):
        """Build or retrieve a cached yukta Agent with shared memory."""
        if agent_id in self.built_agents:
            return self.built_agents[agent_id]

        agents: List[AgentData] = self.ecosystem.get("agents", [])
        agent_data = next((a for a in agents if a.agent_id == agent_id), None)

        if not agent_data:
            raise ValueError(f"Agent '{agent_id}' not found in ecosystem.")

        if "group-collaboration" not in agent_data.skills:
            agent_data.skills.append("group-collaboration")

        skills = self.ecosystem.get("skills", [])
        tools = self.ecosystem.get("tools", [])
        config = self.ecosystem.get("config")

        yukta_agent = transform_agent(
            agent_data=agent_data,
            loaded_skills=skills,
            loaded_tools=tools,
            system_config=config,
            bootstrap_prompt=None,
            memory=self.shared_memory
        )

        if self.llm_client:
            yukta_agent.set_llm_client(self.llm_client)

        yukta_agent.config.max_iter = 1
        yukta_agent.set_memory(self.shared_memory, enable_cache=True)

        self.built_agents[agent_id] = yukta_agent
        return yukta_agent

    def _build_role_cue(self, agent_id: str) -> str:
        """Build a minimal instruction cue for the agent's turn."""
        return (
            f"You are [{agent_id}] in this team. "
            f"Review the conversation history above carefully and perform your role. "
            f"If you are a leader, assess the work done and either approve it "
            f"or request specific revisions with clear instructions. "
            f"If you are a member, complete the task or address the feedback given."
        )

    def run(
        self,
        initial_task: str,
        max_iterations: int = 10,
        hitl_mode: HitlMode = HitlMode.OFF,
        hitl_callback: Optional[Callable[[str, str], Optional[str]]] = None,
    ) -> Dict[str, Any]:
        """Execute the team workflow using a two-mode message strategy."""
        logger.info(f"Starting Team Session '{self.session_id}' for team '{self.team.team_id}'")

        pending_human_feedback: Optional[str] = None
        is_first_turn = True

        while self.session.iteration_count < max_iterations:
            next_speaker_id = SpeakerSelector.select_next(self.team, self.session)
            if not next_speaker_id:
                logger.error("SpeakerSelector failed to find next speaker. Aborting.")
                break

            self.session.current_speaker = next_speaker_id
            logger.info(f"Floor passed to: [{next_speaker_id}]")

            agent = self._build_agent(next_speaker_id)

            if is_first_turn:
                user_message = initial_task
                is_first_turn = False
            elif pending_human_feedback:
                role_cue = self._build_role_cue(next_speaker_id)
                user_message = f"{pending_human_feedback}\n\n{role_cue}"
                pending_human_feedback = None
            else:
                user_message = self._build_role_cue(next_speaker_id)

            result = run_agent(agent, user_message)

            if not result.get("success"):
                logger.error(f"Agent '{next_speaker_id}' failed: {result.get('error')}")
                break

            response_text = result.get("response", "")

            self.session.history.append({
                "agent": next_speaker_id,
                "message": response_text
            })

            self.session.iteration_count += 1

            if (
                self.team.structure == TeamStructure.HIERARCHICAL
                and self.session.iteration_count > 1
                and next_speaker_id == self.team.leader_id
            ):
                is_approval = (
                    "approve" in response_text.lower()
                    or "looks good" in response_text.lower()
                    or "[approved]" in response_text.lower()
                )

                if is_approval:
                    self.session.status = ApprovalStatus.APPROVED
                    logger.info("Team Leader approved the task.")
                    break
                else:
                    self.session.status = ApprovalStatus.REVISION_REQUESTED
                    logger.info("Team Leader requested revisions.")

        return {
            "success": self.session.status == ApprovalStatus.APPROVED or self.team.structure == TeamStructure.FLAT,
            "session": self.session,
            "final_response": self.session.history[-1]["message"] if self.session.history else "",
        }


def run_team(
    team_id: str,
    ecosystem: Dict[str, Any],
    llm_client: Any,
    task: str,
    max_iterations: int = 10,
) -> Dict[str, Any]:
    """
    Convenience function to run a team workflow.

    HIERARCHICAL teams use the structured LeaderCoordinator (JSON briefs + reports).
    FLAT and DYNAMIC teams continue to use the GroupChatSession round-robin.
    """
    if not YUKTA_AVAILABLE:
        raise RuntimeError("Yukta package is required for team execution")

    teams = ecosystem.get("teams", [])
    team_data = next((t for t in teams if t.team_id == team_id), None)

    if not team_data:
        raise ValueError(f"Team '{team_id}' not found in ecosystem")

    if team_data.structure == TeamStructure.HIERARCHICAL:
        coordinator = LeaderCoordinator(team_data, ecosystem, llm_client)
        return coordinator.run(task, max_rounds=max_iterations)

    session = GroupChatSession(team_data, ecosystem, llm_client)
    return session.run(task, max_iterations=max_iterations)


__all__ = [
    "SpeakerSelector",
    "GroupChatSession",
    "run_team",
    "LeaderCoordinator",
]