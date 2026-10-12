"""
validator.py — Validation Layer for yukta-api

Validates all ecosystem entities before they are transformed and executed.
All functions return (is_valid: bool, errors: List[str]).

Functions:
    validate_skill(skill)                         → (bool, List[str])
    validate_tool(tool)                           → (bool, List[str])
    validate_agent(agent, known_skills, known_tools) → (bool, List[str])
    validate_team(team, known_agents)             → (bool, List[str])
    validate_agent_permissions(agent, permission) → (bool, str)
    validate_agent_level(agent, required_level)   → (bool, str)
    validate_tool_access(agent, tool_id)          → (bool, str)
    validate_skill_assignment(agent, skill_id)    → (bool, str)
    validate_ecosystem(ecosystem_dict)            → (bool, List[str])
"""

from typing import List, Tuple, Set
import logging

from .models import (
    AgentData,
    AgentLevel,
    SkillData,
    ToolData,
    TeamData,
    SystemConfig,
    ToolType,
)

logger = logging.getLogger(__name__)


def validate_skill(skill: SkillData) -> Tuple[bool, List[str]]:
    """Validate a SkillData instance."""
    errors: List[str] = []
    known_categories = {"bootstrap", "process", "implementation", "team", "meta"}

    if not skill.skill_id:
        errors.append("skill_id is empty")
    if not skill.description:
        errors.append(f"Skill '{skill.skill_id}': description is empty")
    elif len(skill.description) > 150:
        errors.append(f"Skill '{skill.skill_id}': description exceeds 150 chars")
    if not skill.content:
        errors.append(f"Skill '{skill.skill_id}': markdown body is empty")
    if skill.category not in known_categories:
        errors.append(f"Skill '{skill.skill_id}': unknown category '{skill.category}'")

    return len(errors) == 0, errors


def validate_tool(tool: ToolData) -> Tuple[bool, List[str]]:
    """Validate a ToolData instance."""
    errors: List[str] = []
    valid_param_types = {"string", "integer", "number", "boolean", "object", "array"}

    if not tool.tool_id:
        errors.append("tool_id is empty")
    if not tool.description:
        errors.append(f"Tool '{tool.tool_id}': description is empty")

    for i, param in enumerate(tool.parameters):
        if not param.name:
            errors.append(f"Tool '{tool.tool_id}': parameter[{i}] has no name")
        if param.type not in valid_param_types:
            errors.append(f"Tool '{tool.tool_id}': invalid type '{param.type}'")

    if tool.tool_type == ToolType.CUSTOM and not tool.function_path:
        errors.append(f"Tool '{tool.tool_id}': type is CUSTOM but no function_path")

    return len(errors) == 0, errors


def validate_agent(
    agent: AgentData,
    known_skills: Set[str],
    known_tools: Set[str],
) -> Tuple[bool, List[str]]:
    """Validate an AgentData instance."""
    errors: List[str] = []

    if not agent.agent_id:
        errors.append("agent_id is empty")
    if not agent.role:
        errors.append(f"Agent '{agent.agent_id}': role is empty")

    for skill_id in agent.skills:
        if skill_id not in known_skills:
            errors.append(f"Agent '{agent.agent_id}': unknown skill '{skill_id}'")

    for tool_id in agent.tools:
        if tool_id not in known_tools:
            errors.append(f"Agent '{agent.agent_id}': unknown tool '{tool_id}'")

    if agent.level >= AgentLevel.LEAD and not agent.team_leads:
        logger.warning(f"Agent '{agent.agent_id}' is LEAD but has no team_leads")

    return len(errors) == 0, errors


def validate_team(team: TeamData, known_agents: Set[str]) -> Tuple[bool, List[str]]:
    """Validate a TeamData instance."""
    errors: List[str] = []

    if not team.team_id:
        errors.append("team_id is empty")
    if not team.name:
        errors.append(f"Team '{team.team_id}': name is empty")
    if not team.leader_id:
        errors.append(f"Team '{team.team_id}': leader_id is empty")
    elif team.leader_id not in known_agents:
        errors.append(f"Team '{team.team_id}': leader '{team.leader_id}' not found")

    for member_id in team.members:
        if member_id not in known_agents:
            errors.append(f"Team '{team.team_id}': member '{member_id}' not found")

    return len(errors) == 0, errors


def validate_agent_permissions(agent: AgentData, permission: str) -> Tuple[bool, str]:
    """Validate agent has specific permission."""
    if agent.has_permission(permission):
        return True, ""
    return False, f"Agent '{agent.agent_id}' lacks permission '{permission}'"


def validate_agent_level(agent: AgentData, required_level: AgentLevel) -> Tuple[bool, str]:
    """Validate agent meets required level."""
    if agent.is_at_least(required_level):
        return True, ""
    return False, f"Agent '{agent.agent_id}' level '{agent.level.value}' is below required '{required_level.value}'"


def validate_tool_access(agent: AgentData, tool_id: str) -> Tuple[bool, str]:
    """Validate agent has access to tool."""
    if agent.has_tool(tool_id):
        return True, ""
    return False, f"Agent '{agent.agent_id}' does not have access to tool '{tool_id}'"


def validate_skill_assignment(agent: AgentData, skill_id: str) -> Tuple[bool, str]:
    """Validate agent has skill assigned."""
    if agent.has_skill(skill_id):
        return True, ""
    return False, f"Agent '{agent.agent_id}' does not have skill '{skill_id}'"


def validate_ecosystem(ecosystem_dict: dict) -> Tuple[bool, List[str]]:
    """Validate full ecosystem."""
    all_errors: List[str] = []

    skills = ecosystem_dict.get("skills", [])
    tools = ecosystem_dict.get("tools", [])
    agents = ecosystem_dict.get("agents", [])
    teams = ecosystem_dict.get("teams", [])

    known_skills = {s.skill_id for s in skills}
    known_tools = {t.tool_id for t in tools}
    known_agents = {a.agent_id for a in agents}

    for skill in skills:
        is_valid, errors = validate_skill(skill)
        if not is_valid:
            all_errors.extend(errors)

    for tool in tools:
        is_valid, errors = validate_tool(tool)
        if not is_valid:
            all_errors.extend(errors)

    for agent in agents:
        is_valid, errors = validate_agent(agent, known_skills, known_tools)
        if not is_valid:
            all_errors.extend(errors)

    for team in teams:
        is_valid, errors = validate_team(team, known_agents)
        if not is_valid:
            all_errors.extend(errors)

    return len(all_errors) == 0, all_errors


__all__ = [
    "validate_skill",
    "validate_tool",
    "validate_agent",
    "validate_team",
    "validate_agent_permissions",
    "validate_agent_level",
    "validate_tool_access",
    "validate_skill_assignment",
    "validate_ecosystem",
]