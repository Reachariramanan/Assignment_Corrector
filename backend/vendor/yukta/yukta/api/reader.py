"""
reader.py — Read and Parse Ecosystem Files

Reads YAML and Markdown files from the ecosystem directory structure
and returns typed data structures (from models.py).

Functions:
    read_config_yaml(path)          → SystemConfig
    read_bootstrap_yaml(path)       → BootstrapConfig
    read_skill_md(path)             → SkillData
    read_tool_yaml(path)            → ToolData
    read_agent_yaml(path)           → AgentData
    read_team_yaml(path)            → TeamData
    load_skills_from_index(path)    → List[SkillData]
    load_all_tools(tools_dir)       → List[ToolData]
    load_all_agents(agents_dir)     → List[AgentData]
    load_all_teams(teams_dir)       → List[TeamData]
    load_ecosystem(config_path)     → dict (full loaded ecosystem)
"""

import yaml
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple

from .models import (
    SystemConfig,
    BootstrapConfig,
    SkillData,
    ToolData,
    ToolParameterData,
    ToolType,
    AgentData,
    AgentLevel,
    TeamData,
    TeamStructure,
)

logger = logging.getLogger(__name__)


def _load_yaml_file(path: str) -> Dict[str, Any]:
    """Load a YAML file and return the parsed dict. Raises FileNotFoundError if missing."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def _parse_yaml_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Extract YAML frontmatter and markdown body from a markdown file.

    Returns:
        (frontmatter_dict, markdown_body)
    """
    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(pattern, content, re.DOTALL)
    if match:
        frontmatter_text = match.group(1)
        body = match.group(2).strip()
        frontmatter = yaml.safe_load(frontmatter_text) or {}
        return frontmatter, body
    return {}, content.strip()


def read_config_yaml(path: str) -> SystemConfig:
    """Read config/main.yaml and return a SystemConfig."""
    data = _load_yaml_file(path)

    system = data.get("system", {})
    permissions = data.get("permissions", {})
    logging_cfg = data.get("logging", {})
    agent_cfg = data.get("agent", {})
    storage = data.get("storage", {})
    monitoring = data.get("monitoring", {})
    ecosystem = data.get("ecosystem", {})

    return SystemConfig(
        system_name=system.get("name", "yukta-ecosystem"),
        system_version=system.get("version", "1.0.0"),
        default_permission=permissions.get("default_level", "basic"),
        admin_role=permissions.get("admin_role", "system-admin"),
        log_level=logging_cfg.get("level", "INFO"),
        log_output=logging_cfg.get("output", "stdout"),
        enable_logging=logging_cfg.get("enable_logging", True),
        enable_memory_logging=logging_cfg.get("enable_memory_logging", True),
        auto_save_chat=agent_cfg.get("auto_save_chat_history", True),
        chat_history_dir=agent_cfg.get("chat_history_dir", "./chats"),
        max_iter=agent_cfg.get("max_iter", 10),
        storage_backend=storage.get("backend", "json"),
        storage_path=storage.get("path", "./data"),
        open_telemetry=monitoring.get("open_telemetry", False),
        phoenix_endpoint=monitoring.get("phoenix_endpoint", "http://localhost:6007/v1/traces"),
        skills_path=ecosystem.get("skills_path", "skills"),
        skills_box=ecosystem.get("skills_box", "skills-box/index.yaml"),
        agents_path=ecosystem.get("agents_path", "agents"),
        tools_path=ecosystem.get("tools_path", "tools"),
        teams_path=ecosystem.get("teams_path", "teams"),
        bootstrap_path=ecosystem.get("bootstrap_path", "bootstrap/using-yukta.yaml"),
        metadata=data,
    )


def read_bootstrap_yaml(path: str) -> BootstrapConfig:
    """Read bootstrap/using-yukta.yaml and return a BootstrapConfig."""
    data = _load_yaml_file(path)
    return BootstrapConfig(
        bootstrap_skill=data.get("bootstrap_skill", "using-yukta"),
        skill_path=data.get("skill_path", "skills-box/index.yaml"),
        inject_at_start=data.get("inject_at_start", True),
        additional_context=data.get("additional_context", ""),
        version=data.get("version", "1.0.0"),
        file_path=str(Path(path).resolve()),
    )


def read_skill_md(path: str) -> SkillData:
    """Read a SKILL.md file and return a SkillData."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"SKILL.md not found: {path}")

    content = p.read_text(encoding="utf-8")
    frontmatter, body = _parse_yaml_frontmatter(content)

    skill_id = frontmatter.get("skill_id") or frontmatter.get("name") or p.parent.name
    name = frontmatter.get("name", skill_id)

    try:
        return SkillData(
            skill_id=skill_id,
            name=name,
            description=frontmatter.get("description", ""),
            version=frontmatter.get("version", "1.0.0"),
            category=frontmatter.get("category", "process"),
            content=body,
            file_path=str(p.resolve()),
            metadata=frontmatter,
        )
    except ValueError as e:
        raise ValueError(f"Skill '{skill_id}' validation failed: {e}")


def load_skills_from_index(index_path: str) -> List[SkillData]:
    """Load all skills listed in skills-box/index.yaml.
    
    The index_path can be absolute or relative. If relative, it's resolved
    against the ecosystem root (parent of skills-box/ directory).
    """
    index_path_obj = Path(index_path)
    
    if index_path_obj.is_absolute():
        skills_box_dir = index_path_obj.parent
        ecosystem_root = skills_box_dir.parent
    else:
        # Relative path - need to find ecosystem root
        # Assume we're in ecosystem/skills-box/index.yaml
        # So ecosystem root is 2 levels up
        index_path_resolved = Path(index_path).resolve()
        skills_box_dir = index_path_resolved.parent
        ecosystem_root = skills_box_dir.parent
    
    logger.debug(f"Skills box dir: {skills_box_dir}")
    logger.debug(f"Ecosystem root: {ecosystem_root}")
    
    if not (ecosystem_root / "skills").exists():
        logger.warning(f"Could not find skills directory at '{ecosystem_root / 'skills'}'")

    data = _load_yaml_file(index_path)
    skills_entries = data.get("skills", [])

    skills: List[SkillData] = []
    for entry in skills_entries:
        skill_path_str = entry.get("path", "")
        if not skill_path_str:
            logger.warning(f"Skill entry missing 'path': {entry}")
            continue
            
        skill_path = ecosystem_root / skill_path_str
        try:
            skill = read_skill_md(str(skill_path))
            skills.append(skill)
            logger.debug(f"Loaded skill: {skill.skill_id}")
        except FileNotFoundError as e:
            logger.warning(f"Skill file not found (skipping): {e}")
        except Exception as e:
            logger.warning(f"Failed to load skill '{entry.get('id', '?')}': {e}")

    return skills


def read_tool_yaml(path: str) -> ToolData:
    """Read a tool YAML file and return a ToolData."""
    data = _load_yaml_file(path)

    tool_id = data.get("tool_id", Path(path).stem)
    if not tool_id or not tool_id.strip():
        raise ValueError(f"Tool YAML '{path}': tool_id is empty or missing")
    
    description = data.get("description", "").strip()
    if not description:
        raise ValueError(f"Tool '{tool_id}': description is empty or missing")

    raw_params = data.get("parameters", [])
    seen_param_names = set()
    parameters = []
    for i, p in enumerate(raw_params):
        param_name = p.get("name", "").strip() if isinstance(p.get("name"), str) else ""
        if not param_name:
            raise ValueError(f"Tool '{tool_id}': parameter[{i}] has no name")
        
        if param_name in seen_param_names:
            raise ValueError(f"Tool '{tool_id}': duplicate parameter name '{param_name}'")
        seen_param_names.add(param_name)
        
        param_type = p.get("type", "string")
        valid_param_types = {"string", "integer", "number", "boolean", "object", "array"}
        if param_type not in valid_param_types:
            raise ValueError(
                f"Tool '{tool_id}': parameter '{param_name}' has invalid type '{param_type}'. "
                f"Must be one of: {sorted(valid_param_types)}"
            )
        
        parameters.append(ToolParameterData(
            name=param_name,
            type=param_type,
            description=p.get("description", ""),
            required=p.get("required", False),
            default=p.get("default"),
            enum=p.get("enum"),
        ))

    tool_type_str = data.get("tool_type", "builtin")
    try:
        tool_type = ToolType.from_str(tool_type_str)
    except ValueError as e:
        raise ValueError(f"Tool '{tool_id}': {e}")

    return ToolData(
        tool_id=tool_id,
        description=description,
        parameters=parameters,
        returns=data.get("returns", "string"),
        tool_type=tool_type,
        version=data.get("version", "1.0.0"),
        function_path=data.get("function_path"),
        metadata=data,
    )


def load_all_tools(tools_dir: str) -> List[ToolData]:
    """Load all tool YAML files from the tools/ directory."""
    tools_path = Path(tools_dir)
    if not tools_path.exists():
        return []

    tools: List[ToolData] = []
    seen_tool_ids = set()
    for yaml_file in sorted(tools_path.glob("*.yaml")):
        try:
            tool = read_tool_yaml(str(yaml_file))
            if tool.tool_id in seen_tool_ids:
                logger.warning(f"Duplicate tool_id '{tool.tool_id}' found in '{yaml_file.name}'. Skipping.")
                continue
            seen_tool_ids.add(tool.tool_id)
            tools.append(tool)
        except Exception as e:
            logger.warning(f"Failed to load tool '{yaml_file.name}': {e}")
    return tools


def read_agent_yaml(path: str) -> AgentData:
    """Read an agent YAML file and return an AgentData."""
    data = _load_yaml_file(path)

    agent_id = data.get("agent_id", Path(path).stem)
    if not agent_id or not agent_id.strip():
        raise ValueError(f"Agent YAML '{path}': agent_id is empty or missing")

    role = data.get("role", "").strip() if data.get("role") else ""
    if not role:
        raise ValueError(f"Agent '{agent_id}': role is empty or missing")

    level_str = data.get("level", "junior")
    try:
        level = AgentLevel.from_str(level_str)
    except ValueError as e:
        raise ValueError(f"Agent '{agent_id}': {e}")

    return AgentData(
        agent_id=agent_id,
        role=role,
        level=level,
        skills=data.get("skills", []),
        tools=data.get("tools", []),
        permissions=data.get("permissions", []),
        behaviors=data.get("behaviors", []),
        context=data.get("context", ""),
        team_memberships=data.get("team_memberships", []),
        team_leads=data.get("team_leads", []),
        version=data.get("version", "1.0.0"),
        metadata=data,
    )


def load_all_agents(agents_dir: str) -> List[AgentData]:
    """Load all agent YAML files from the agents/ directory."""
    agents_path = Path(agents_dir)
    if not agents_path.exists():
        return []

    agents: List[AgentData] = []
    for yaml_file in sorted(agents_path.glob("*.yaml")):
        try:
            agent = read_agent_yaml(str(yaml_file))
            agents.append(agent)
        except Exception as e:
            logger.warning(f"Failed to load agent '{yaml_file.name}': {e}")
    return agents


def read_team_yaml(path: str) -> TeamData:
    """Read a team YAML file and return a TeamData."""
    data = _load_yaml_file(path)

    return TeamData(
        team_id=data.get("team_id", Path(path).stem),
        name=data.get("name", "Unknown Team"),
        leader_id=data.get("leader_id", ""),
        structure=TeamStructure.from_str(data.get("structure", "hierarchical")),
        members=data.get("members", []),
        purpose=data.get("purpose", ""),
        capabilities=data.get("capabilities", []),
        version=data.get("version", "1.0.0"),
        metadata=data,
    )


def load_all_teams(teams_dir: str) -> List[TeamData]:
    """Load all team YAML files from the teams/ directory."""
    teams_path = Path(teams_dir)
    if not teams_path.exists():
        return []

    teams: List[TeamData] = []
    for yaml_file in sorted(teams_path.glob("*.yaml")):
        try:
            team = read_team_yaml(str(yaml_file))
            teams.append(team)
        except Exception as e:
            logger.warning(f"Failed to load team '{yaml_file.name}': {e}")
    return teams


def load_ecosystem(config_path: str, validate_schema: bool = True) -> Dict[str, Any]:
    """Load the entire ecosystem from a config/main.yaml path.
    
    Relative paths in the config are resolved against the ecosystem root directory.
    The ecosystem root is the parent directory of the config/ folder.
    """
    config_file = Path(config_path).resolve()
    config_dir = config_file.parent
    ecosystem_root = config_dir.parent
    
    logger.info(f"Loading ecosystem from: {config_path}")
    logger.info(f"Ecosystem root: {ecosystem_root}")
    
    config = read_config_yaml(config_path)
    
    def _resolve_path(relative_path: str) -> Path:
        """Resolve a relative path against the ecosystem root directory."""
        p = Path(relative_path)
        if p.is_absolute():
            return p
        resolved = ecosystem_root / p
        logger.debug(f"Resolved path '{relative_path}' → {resolved}")
        return resolved
    
    bootstrap_path = _resolve_path(config.bootstrap_path)
    skills_box = _resolve_path(config.skills_box)
    tools_path = _resolve_path(config.tools_path)
    agents_path = _resolve_path(config.agents_path)
    teams_path = _resolve_path(config.teams_path)
    
    logger.info(f"Loading bootstrap from: {bootstrap_path}")
    bootstrap = read_bootstrap_yaml(str(bootstrap_path))
    
    logger.info(f"Loading skills from: {skills_box}")
    skills = load_skills_from_index(str(skills_box))
    logger.info(f"Loaded {len(skills)} skills")
    
    logger.info(f"Loading tools from: {tools_path}")
    tools = load_all_tools(str(tools_path))
    logger.info(f"Loaded {len(tools)} tools")
    
    logger.info(f"Loading agents from: {agents_path}")
    agents = load_all_agents(str(agents_path))
    logger.info(f"Loaded {len(agents)} agents")
    
    logger.info(f"Loading teams from: {teams_path}")
    teams = load_all_teams(str(teams_path))
    logger.info(f"Loaded {len(teams)} teams")

    result = {
        "config": config,
        "bootstrap": bootstrap,
        "skills": skills,
        "tools": tools,
        "agents": agents,
        "teams": teams,
    }

    if validate_schema:
        is_valid, msg = _validate_ecosystem_schema_version(config)
        if not is_valid:
            logger.warning(f"Schema validation warning: {msg}")
        else:
            logger.info("Ecosystem schema validation passed")

    logger.info(f"Ecosystem loaded successfully: {len(agents)} agents, {len(skills)} skills, {len(tools)} tools")
    return result


def _validate_ecosystem_schema_version(config: SystemConfig, expected_version: str = "1.0.0") -> Tuple[bool, str]:
    """Validate that ecosystem schema version is compatible."""
    actual_version = getattr(config, "schema_version", None)
    if actual_version is None:
        return True, "No schema version specified, skipping validation"
    
    if actual_version != expected_version:
        return False, f"Expected schema version '{expected_version}', got '{actual_version}'"
    return True, f"Schema version validated: {actual_version}"


__all__ = [
    "read_config_yaml",
    "read_bootstrap_yaml",
    "read_skill_md",
    "read_tool_yaml",
    "read_agent_yaml",
    "read_team_yaml",
    "load_skills_from_index",
    "load_all_tools",
    "load_all_agents",
    "load_all_teams",
    "load_ecosystem",
]