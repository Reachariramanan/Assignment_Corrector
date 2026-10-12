"""
allocator.py — Dynamic skill/task allocation across agents and teams.

This module handles allocating skills and tasks to agents based on their
roles, levels, and permissions.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from .models import AgentData, SkillData, TeamData, AgentLevel

logger = logging.getLogger(__name__)


def get_available_skills_for_agent(
    agent: AgentData,
    all_skills: List[SkillData],
) -> List[SkillData]:
    """Get all skills available to an agent based on their role/level."""
    if not all_skills:
        logger.warning(f"No skills available for agent {agent.agent_id}")
    return all_skills


def get_agent_tools(
    agent: AgentData,
    all_tools: List[Any],
) -> List[Any]:
    """Get tools assigned to an agent."""
    if not all_tools:
        logger.warning(f"No tools available for agent {agent.agent_id}")
    return all_tools


def allocate_skills_for_task(
    task_description: str,
    agent: AgentData,
    available_skills: List[SkillData],
) -> Tuple[List[str], str]:
    """
    Determine which skills to allocate for a task based on task type.
    
    Returns:
        Tuple of (skill_ids, allocation_method): 
            - skill_ids: list of skill IDs to assign
            - allocation_method: how skills were selected ('matched', 'role_based', 'fallback', 'none')
    """
    if not task_description:
        logger.warning("Empty task description, using fallback")
        return _fallback_allocation(agent), "fallback"
    
    task_lower = task_description.lower()
    allocated = []
    allocation_method = "matched"
    
    # First pass: match skills that the agent already has
    agent_skill_ids = agent.skills or []
    for skill in available_skills:
        if skill.skill_id in agent_skill_ids:
            if _skill_applies_to_task(skill, task_lower):
                allocated.append(skill.skill_id)
    
    # Second pass: if no matches, try skills by category match
    if not allocated:
        allocation_method = "category_based"
        category = _infer_category_from_task(task_lower)
        for skill in available_skills:
            if skill.category.lower() == category:
                allocated.append(skill.skill_id)
                if len(allocated) >= 3:
                    break
    
    # Third pass: fallback to agent's assigned skills or any available
    if not allocated:
        allocation_method = "role_based"
        if agent_skill_ids:
            allocated = list(agent_skill_ids[:3])
        elif available_skills:
            allocated = [s.skill_id for s in available_skills[:3]]
        else:
            allocation_method = "none"
            logger.warning(f"No skills available for task: {task_description[:50]}")
    
    return allocated, allocation_method


def _infer_category_from_task(task: str) -> str:
    """Infer skill category from task description."""
    if "debug" in task or "bug" in task or "fix" in task:
        return "implementation"
    if "test" in task or "verify" in task:
        return "implementation"
    if "plan" in task or "design" in task:
        return "meta"
    if "review" in task or "check" in task:
        return "team"
    return "process"


def _skill_applies_to_task(skill: SkillData, task: str) -> bool:
    """Check if a skill applies to a task."""
    skill_cat = (skill.category or "process").lower()
    
    if "debug" in task or "bug" in task or "fix" in task:
        return skill_cat in ["process", "implementation"]
    if "test" in task or "verify" in task:
        return skill_cat in ["process", "implementation"]
    if "plan" in task or "design" in task:
        return skill_cat in ["process", "meta"]
    if "review" in task:
        return skill_cat in ["team", "process"]
    
    return True


def _fallback_allocation(agent: AgentData) -> List[str]:
    """Fallback allocation when no task info available."""
    if agent.skills:
        return list(agent.skills[:3])
    return []


def can_agent_perform_action(
    agent: AgentData,
    action: str,
    required_level: AgentLevel = AgentLevel.JUNIOR,
) -> Tuple[bool, str]:
    """
    Check if an agent can perform an action based on their level.
    
    Returns:
        Tuple of (allowed, reason)
    """
    if agent.level >= required_level:
        return True, "level sufficient"
    
    return False, f"level {agent.level.value} insufficient, requires {required_level.value}"


def check_agent_permission(
    agent: AgentData,
    permission: str,
) -> Tuple[bool, str]:
    """Check if agent has a specific permission."""
    if not agent.permissions:
        return False, "agent has no permissions"
    
    if permission in agent.permissions:
        return True, "permission granted"
    
    return False, f"permission '{permission}' not found"


def get_team_capabilities(
    team: TeamData,
) -> List[str]:
    """Get all capabilities of a team."""
    return team.capabilities or []


def can_team_perform(
    team: TeamData,
    capability: str,
) -> bool:
    """Check if team has a capability."""
    return capability in (team.capabilities or [])


__all__ = [
    "get_available_skills_for_agent",
    "get_agent_tools",
    "allocate_skills_for_task",
    "can_agent_perform_action",
    "check_agent_permission",
    "get_team_capabilities",
    "can_team_perform",
]