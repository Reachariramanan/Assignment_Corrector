"""
Loader module for ecosystem entities.
Loads agents, skills, tools, and teams from ecosystem path.
Supports both individual YAML files and compiled ecosystem.yaml.
"""

import os
import sys
import yaml
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Dict, Any, List

from .exceptions import (
    EcosystemError,
    AgentNotFoundError,
    SkillNotFoundError,
    ToolNotFoundError,
    TeamNotFoundError,
)
from .resolver import resolve_agent_skills, resolve_agent_tools


# Cache for compiled ecosystem data (LRU, max 20 entries)
_CACHE_MAX_SIZE = 20
_compiled_cache: OrderedDict = OrderedDict()
_compiled_index: Dict[str, Dict[str, Dict[str, Any]]] = {}


def _build_index(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build O(1) lookup dicts for each entity type in compiled ecosystem data."""
    return {
        "agents": {a["agent_id"]: a for a in data.get("agents", []) if "agent_id" in a},
        "skills": {s["skill_id"]: s for s in data.get("skills", []) if "skill_id" in s},
        "tools":  {t["tool_id"]: t for t in data.get("tools", []) if "tool_id" in t},
        "teams":  {tm["team_id"]: tm for tm in data.get("teams", []) if "team_id" in tm},
    }


def _load_compiled(ecosystem_path: str) -> Dict[str, Any]:
    """Load compiled ecosystem data from build/ecosystem.yaml."""
    global _compiled_cache, _compiled_index

    path_key = str(Path(ecosystem_path).absolute())

    if path_key in _compiled_cache:
        _compiled_cache.move_to_end(path_key)
        return _compiled_cache[path_key]

    compiled_file = Path(ecosystem_path) / "build" / "ecosystem.yaml"

    if not compiled_file.exists():
        return {}

    try:
        with open(compiled_file, "r") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise RuntimeError(f"Failed to parse '{compiled_file}': {e}") from e

    _compiled_cache[path_key] = data
    _compiled_cache.move_to_end(path_key)
    _compiled_index[path_key] = _build_index(data)

    if len(_compiled_cache) > _CACHE_MAX_SIZE:
        oldest_key, _ = _compiled_cache.popitem(last=False)
        _compiled_index.pop(oldest_key, None)

    return data


def _lookup_compiled(ecosystem_path: str, entity_type: str, name: str) -> Optional[Dict[str, Any]]:
    """O(1) lookup of an entity in the compiled ecosystem index."""
    path_key = str(Path(ecosystem_path).absolute())
    return _compiled_index.get(path_key, {}).get(entity_type, {}).get(name)


def load_agent(name: str, path: str, use_compiled: bool = True) -> Dict[str, Any]:
    """
    Load an agent configuration from ecosystem.
    
    Args:
        name: Agent ID (without .yaml extension)
        path: Path to ecosystem directory (relative or absolute)
        use_compiled: If True, try to use build/ecosystem.yaml first
    
    Returns:
        Dict containing agent configuration
    
    Raises:
        AgentNotFoundError: If agent doesn't exist
        EcosystemError: If path is invalid
    """
    # Resolve to absolute path for consistency
    ecosystem_path = Path(path).resolve()
    
    if not ecosystem_path.exists():
        raise EcosystemError(f"Ecosystem path does not exist: {path}")
    
    if use_compiled:
        _load_compiled(path)
        agent = _lookup_compiled(path, "agents", name)
        if agent is not None:
            agent_data = agent.copy()
            skill_data = resolve_agent_skills(agent_data.get("skills", []), ecosystem_path)
            tool_data = resolve_agent_tools(agent_data.get("tools", []), ecosystem_path)
            agent_data["_skill_data"] = skill_data
            agent_data["_tool_data"] = tool_data
            return agent_data
    
    agent_file = ecosystem_path / "agents" / f"{name}.yaml"
    
    if not agent_file.exists():
        raise AgentNotFoundError(f"Agent '{name}' not found in {path}")
    
    with open(agent_file, "r") as f:
        agent_config = yaml.safe_load(f)
    
    skill_data = resolve_agent_skills(agent_config.get("skills", []), ecosystem_path)
    tool_data = resolve_agent_tools(agent_config.get("tools", []), ecosystem_path)
    
    agent_config["_skill_data"] = skill_data
    agent_config["_tool_data"] = tool_data
    
    return agent_config


def load_skill(name: str, path: str, use_compiled: bool = True) -> Dict[str, Any]:
    """
    Load a skill workflow from ecosystem.
    
    Args:
        name: Skill ID
        path: Path to ecosystem directory
        use_compiled: If True, try to use build/ecosystem.yaml first
    
    Returns:
        Dict containing skill configuration and content
    
    Raises:
        SkillNotFoundError: If skill doesn't exist
    """
    ecosystem_path = Path(path)
    
    if not ecosystem_path.exists():
        raise EcosystemError(f"Ecosystem path does not exist: {path}")
    
    if use_compiled:
        _load_compiled(path)
        skill = _lookup_compiled(path, "skills", name)
        if skill is not None:
            return skill
    
    skill_dir = ecosystem_path / "skills" / name
    
    if not skill_dir.exists():
        raise SkillNotFoundError(f"Skill '{name}' not found in {path}")
    
    skill_file = skill_dir / "SKILL.md"
    
    if not skill_file.exists():
        raise SkillNotFoundError(f"SKILL.md not found for skill '{name}'")
    
    content = skill_file.read_text()
    
    frontmatter = {}
    body = content
    
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter_yaml = parts[1].strip()
            frontmatter = yaml.safe_load(frontmatter_yaml) or {}
            body = parts[2].strip()
    
    return {
        "skill_id": name,
        "frontmatter": frontmatter,
        "content": body,
        "steps": frontmatter.get("steps", []),
        "category": frontmatter.get("category", "general"),
        "description": frontmatter.get("description", ""),
    }


def load_tool(name: str, path: str, use_compiled: bool = True) -> Dict[str, Any]:
    """
    Load a tool descriptor from ecosystem.
    
    Args:
        name: Tool ID
        path: Path to ecosystem directory
        use_compiled: If True, try to use build/ecosystem.yaml first
    
    Returns:
        Dict containing tool configuration
    
    Raises:
        ToolNotFoundError: If tool doesn't exist
    """
    ecosystem_path = Path(path)
    
    if not ecosystem_path.exists():
        raise EcosystemError(f"Ecosystem path does not exist: {path}")
    
    if use_compiled:
        _load_compiled(path)
        tool = _lookup_compiled(path, "tools", name)
        if tool is not None:
            return tool
    
    tool_file = ecosystem_path / "tools" / f"{name}.yaml"
    
    if not tool_file.exists():
        raise ToolNotFoundError(f"Tool '{name}' not found in {path}")
    
    with open(tool_file, "r") as f:
        tool_config = yaml.safe_load(f)
    
    return tool_config


def load_team(name: str, path: str, use_compiled: bool = True) -> Dict[str, Any]:
    """
    Load a team configuration from ecosystem.
    
    Args:
        name: Team ID
        path: Path to ecosystem directory
        use_compiled: If True, try to use build/ecosystem.yaml first
    
    Returns:
        Dict containing team configuration
    
    Raises:
        TeamNotFoundError: If team doesn't exist
    """
    ecosystem_path = Path(path)
    
    if not ecosystem_path.exists():
        raise EcosystemError(f"Ecosystem path does not exist: {path}")
    
    if use_compiled:
        _load_compiled(path)
        team = _lookup_compiled(path, "teams", name)
        if team is not None:
            return team
    
    team_file = ecosystem_path / "teams" / f"{name}.yaml"
    
    if not team_file.exists():
        raise TeamNotFoundError(f"Team '{name}' not found in {path}")
    
    with open(team_file, "r") as f:
        team_config = yaml.safe_load(f)
    
    return team_config


def list_agents(path: str, use_compiled: bool = True) -> List[str]:
    """List all agents in ecosystem."""
    if use_compiled:
        compiled = _load_compiled(path)
        if compiled and "agents" in compiled:
            return [a.get("agent_id") for a in compiled.get("agents", [])]
    
    ecosystem_path = Path(path)
    agents_dir = ecosystem_path / "agents"
    
    if not agents_dir.exists():
        return []
    
    return [f.stem for f in agents_dir.glob("*.yaml")]


def list_skills(path: str, use_compiled: bool = True) -> List[str]:
    """List all skills in ecosystem."""
    if use_compiled:
        compiled = _load_compiled(path)
        if compiled and "skills" in compiled:
            return [s.get("skill_id") for s in compiled.get("skills", [])]
    
    ecosystem_path = Path(path)
    skills_dir = ecosystem_path / "skills"
    
    if not skills_dir.exists():
        return []
    
    return [d.name for d in skills_dir.iterdir() if d.is_dir()]


def list_tools(path: str, use_compiled: bool = True) -> List[str]:
    """List all tools in ecosystem."""
    if use_compiled:
        compiled = _load_compiled(path)
        if compiled and "tools" in compiled:
            return [t.get("tool_id") for t in compiled.get("tools", [])]
    
    ecosystem_path = Path(path)
    tools_dir = ecosystem_path / "tools"
    
    if not tools_dir.exists():
        return []
    
    return [f.stem for f in tools_dir.glob("*.yaml")]


def list_teams(path: str, use_compiled: bool = True) -> List[str]:
    """List all teams in ecosystem."""
    if use_compiled:
        compiled = _load_compiled(path)
        if compiled and "teams" in compiled:
            return [t.get("team_id") for t in compiled.get("teams", [])]
    
    ecosystem_path = Path(path)
    teams_dir = ecosystem_path / "teams"
    
    if not teams_dir.exists():
        return []
    
    return [f.stem for f in teams_dir.glob("*.yaml")]


def load_index(path: str) -> Dict[str, Any]:
    """
    Load the skills-box index from ecosystem.
    
    Args:
        path: Path to ecosystem directory
    
    Returns:
        Dict containing index data
    """
    ecosystem_path = Path(path)
    index_file = ecosystem_path / "skills-box" / "index.yaml"
    
    if not index_file.exists():
        return {"skills": [], "tools": [], "agents": [], "teams": []}
    
    with open(index_file, "r") as f:
        return yaml.safe_load(f) or {}


def clear_cache():
    """Clear the compiled cache."""
    global _compiled_cache
    _compiled_cache = {}


__all__ = [
    "load_agent",
    "load_skill", 
    "load_tool",
    "load_team",
    "list_agents",
    "list_skills",
    "list_tools",
    "list_teams",
    "load_index",
    "clear_cache",
]