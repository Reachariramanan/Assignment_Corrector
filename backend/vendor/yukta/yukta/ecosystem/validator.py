"""
Validator module for ecosystem configurations.
Validates YAML files and checks for required fields.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml


VALID_AGENT_LEVELS = {"junior", "senior", "lead"}
VALID_TOOL_TYPES = {"builtin", "custom", "remote_mcp"}
VALID_TEAM_STRUCTURES = {"hierarchical", "flat", "dynamic"}
VALID_SKILL_CATEGORIES = {"bootstrap", "process", "implementation", "team", "meta"}
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}
VALID_STORAGE_BACKENDS = {"json", "sqlite"}
VALID_INDEX_KEYS = {"skills", "tools", "agents", "teams"}
REQUIRED_CONFIG_SECTIONS = {"system", "permissions", "logging", "agent", "storage", "monitoring", "ecosystem"}


def _load_yaml(file_path: Path) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        return None, [f"Invalid YAML in {file_path.name}: {exc}"]
    except OSError as exc:
        return None, [f"Failed to read {file_path}: {exc}"]

    if data is None:
        return {}, []
    if not isinstance(data, dict):
        return None, [f"{file_path.name}: expected a YAML mapping at the top level"]
    return data, []


def validate_ecosystem(ecosystem_path: Path) -> List[str]:
    """
    Validate an ecosystem directory.

    Args:
        ecosystem_path: Path to ecosystem directory

    Returns:
        List of error messages (empty if valid)
    """
    errors: List[str] = []
    ecosystem_path = Path(ecosystem_path)

    if not ecosystem_path.exists():
        return [f"Path does not exist: {ecosystem_path}"]

    config_file = ecosystem_path / "config" / "main.yaml"
    bootstrap_file = ecosystem_path / "bootstrap" / "using-yukta.yaml"
    index_file = ecosystem_path / "skills-box" / "index.yaml"
    agents_dir = ecosystem_path / "agents"
    skills_dir = ecosystem_path / "skills"
    tools_dir = ecosystem_path / "tools"
    teams_dir = ecosystem_path / "teams"

    if not config_file.exists():
        errors.append("config/main.yaml not found")
    else:
        errors.extend(validate_config(config_file))

    if not bootstrap_file.exists():
        errors.append("bootstrap/using-yukta.yaml not found")
    else:
        errors.extend(validate_bootstrap(bootstrap_file))

    if not index_file.exists():
        errors.append("skills-box/index.yaml not found")
    else:
        errors.extend(validate_index(index_file))

    skill_dirs = [path for path in skills_dir.iterdir() if path.is_dir()] if skills_dir.exists() else []
    tool_files = list(tools_dir.glob("*.yaml")) if tools_dir.exists() else []
    agent_files = list(agents_dir.glob("*.yaml")) if agents_dir.exists() else []
    team_files = list(teams_dir.glob("*.yaml")) if teams_dir.exists() else []

    known_skill_ids = {directory.name for directory in skill_dirs}
    known_tool_ids = set()
    known_agent_ids = set()

    for tool_file in tool_files:
        data, yaml_errors = _load_yaml(tool_file)
        errors.extend(yaml_errors)
        if data:
            tool_id = data.get("tool_id")
            if isinstance(tool_id, str) and tool_id:
                known_tool_ids.add(tool_id)

    for agent_file in agent_files:
        data, yaml_errors = _load_yaml(agent_file)
        errors.extend(yaml_errors)
        if data:
            agent_id = data.get("agent_id")
            if isinstance(agent_id, str) and agent_id:
                known_agent_ids.add(agent_id)

    for skill_dir in skill_dirs:
        errors.extend(validate_skill(skill_dir))

    for tool_file in tool_files:
        errors.extend(validate_tool(tool_file))

    for agent_file in agent_files:
        errors.extend(validate_agent(agent_file, known_skill_ids, known_tool_ids))

    for team_file in team_files:
        errors.extend(validate_team(team_file, known_agent_ids))

    return errors


def validate_agent(agent_file: Path, known_skills: Optional[Set[str]] = None, known_tools: Optional[Set[str]] = None) -> List[str]:
    """Validate an agent YAML file."""
    errors: List[str] = []

    data, yaml_errors = _load_yaml(agent_file)
    errors.extend(yaml_errors)
    if not data:
        if data == {}:
            errors.append(f"{agent_file.name}: Empty file")
        return errors

    for field in ("agent_id", "role", "level"):
        if field not in data:
            errors.append(f"{agent_file.name}: Missing required field '{field}'")

    level = data.get("level")
    if level and level not in VALID_AGENT_LEVELS:
        errors.append(f"{agent_file.name}: invalid level '{level}'")

    skills = data.get("skills", [])
    tools = data.get("tools", [])

    if skills and not isinstance(skills, list):
        errors.append(f"{agent_file.name}: skills must be a list")
        skills = []
    if tools and not isinstance(tools, list):
        errors.append(f"{agent_file.name}: tools must be a list")
        tools = []

    if not skills and not tools:
        errors.append(f"{agent_file.name}: Agent has no skills or tools defined")

    if known_skills is not None:
        for skill_id in skills:
            if skill_id not in known_skills:
                errors.append(f"{agent_file.name}: unknown skill '{skill_id}'")

    if known_tools is not None:
        for tool_id in tools:
            if tool_id not in known_tools:
                errors.append(f"{agent_file.name}: unknown tool '{tool_id}'")

    return errors


def validate_tool(tool_file: Path) -> List[str]:
    """Validate a tool YAML file."""
    errors: List[str] = []

    data, yaml_errors = _load_yaml(tool_file)
    errors.extend(yaml_errors)
    if not data:
        if data == {}:
            errors.append(f"{tool_file.name}: Empty file")
        return errors

    for field in ("tool_id", "description"):
        if field not in data:
            errors.append(f"{tool_file.name}: Missing required field '{field}'")

    tool_type = data.get("tool_type", "builtin")
    if tool_type not in VALID_TOOL_TYPES:
        errors.append(f"{tool_file.name}: invalid tool_type '{tool_type}'")

    function_path = data.get("function_path", "")
    if tool_type in {"custom", "remote_mcp"} and not function_path:
        errors.append(f"{tool_file.name}: type is {tool_type} but no function_path")
    if function_path and ":" not in function_path:
        errors.append(f"{tool_file.name}: function_path must be in format 'module:function'")

    parameters = data.get("parameters", [])
    if parameters and not isinstance(parameters, list):
        errors.append(f"{tool_file.name}: parameters must be a list")
        parameters = []
    for index, parameter in enumerate(parameters):
        if not isinstance(parameter, dict):
            errors.append(f"{tool_file.name}: parameter[{index}] must be a mapping")
            continue
        if not parameter.get("name"):
            errors.append(f"{tool_file.name}: parameter[{index}] has no name")
        if parameter.get("type") not in {"string", "integer", "number", "boolean", "object", "array"}:
            errors.append(f"{tool_file.name}: parameter[{index}] has invalid type '{parameter.get('type')}'")

    return errors


def validate_team(team_file: Path, known_agents: Optional[Set[str]] = None) -> List[str]:
    """Validate a team YAML file."""
    errors: List[str] = []

    data, yaml_errors = _load_yaml(team_file)
    errors.extend(yaml_errors)
    if not data:
        if data == {}:
            errors.append(f"{team_file.name}: Empty file")
        return errors

    for field in ("team_id", "name", "leader_id", "structure"):
        if field not in data:
            errors.append(f"{team_file.name}: Missing required field '{field}'")

    structure = data.get("structure")
    if structure and structure not in VALID_TEAM_STRUCTURES:
        errors.append(f"{team_file.name}: invalid structure '{structure}'")

    members = data.get("members", [])
    if members and not isinstance(members, list):
        errors.append(f"{team_file.name}: members must be a list")
        members = []
    if not members:
        errors.append(f"{team_file.name}: team must define at least one member")

    leader_id = data.get("leader_id")
    if leader_id and known_agents is not None and leader_id not in known_agents:
        errors.append(f"{team_file.name}: leader '{leader_id}' not found")

    if known_agents is not None:
        for member_id in members:
            if member_id not in known_agents:
                errors.append(f"{team_file.name}: member '{member_id}' not found")

    return errors


def validate_skill(skill_dir: Path) -> List[str]:
    """Validate a skill directory."""
    errors: List[str] = []

    skill_file = skill_dir / "SKILL.md"

    if not skill_file.exists():
        errors.append(f"{skill_dir.name}: SKILL.md not found")
        return errors

    try:
        content = skill_file.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{skill_dir.name}: Failed to read SKILL.md: {exc}"]

    if not content.strip():
        errors.append(f"{skill_dir.name}: SKILL.md is empty")
        return errors

    if not content.startswith("---"):
        errors.append(f"{skill_dir.name}: Missing YAML frontmatter")
        return errors

    parts = content.split("---", 2)
    if len(parts) < 3:
        errors.append(f"{skill_dir.name}: Invalid YAML frontmatter delimiter")
        return errors

    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        errors.append(f"{skill_dir.name}: Invalid frontmatter YAML: {exc}")
        return errors

    if not isinstance(frontmatter, dict):
        errors.append(f"{skill_dir.name}: Frontmatter must be a mapping")
        return errors

    for field in ("name", "description", "version", "category"):
        if not frontmatter.get(field):
            errors.append(f"{skill_dir.name}: Missing required frontmatter field '{field}'")

    if frontmatter.get("name") and frontmatter.get("name") != skill_dir.name:
        errors.append(f"{skill_dir.name}: frontmatter name '{frontmatter.get('name')}' does not match directory name")

    description = frontmatter.get("description", "")
    if isinstance(description, str) and len(description) > 150:
        errors.append(f"{skill_dir.name}: description exceeds 150 chars")

    if frontmatter.get("category") and frontmatter.get("category") not in VALID_SKILL_CATEGORIES:
        errors.append(f"{skill_dir.name}: unknown category '{frontmatter.get('category')}'")

    body = parts[2].strip()
    if not body:
        errors.append(f"{skill_dir.name}: markdown body is empty")

    return errors


def validate_index(index_file: Path) -> List[str]:
    """Validate the skills-box index file."""
    errors: List[str] = []

    data, yaml_errors = _load_yaml(index_file)
    errors.extend(yaml_errors)
    if not data:
        return errors

    for key in data:
        if key not in VALID_INDEX_KEYS:
            errors.append(f"index.yaml: Unknown key '{key}'")

    for section in VALID_INDEX_KEYS:
        entries = data.get(section, [])
        if entries and not isinstance(entries, list):
            errors.append(f"index.yaml: '{section}' must be a list")
            continue
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"index.yaml: {section}[{idx}] must be a mapping")
                continue
            if not entry.get("id"):
                errors.append(f"index.yaml: {section}[{idx}] missing id")
            if section != "teams" and not entry.get("path"):
                errors.append(f"index.yaml: {section}[{idx}] missing path")

    return errors


def validate_config(config_file: Path) -> List[str]:
    errors: List[str] = []
    data, yaml_errors = _load_yaml(config_file)
    errors.extend(yaml_errors)
    if not data:
        return errors

    for section in REQUIRED_CONFIG_SECTIONS:
        if section not in data:
            errors.append(f"config/main.yaml: Missing required section '{section}'")

    system = data.get("system", {})
    if not isinstance(system, dict):
        errors.append("config/main.yaml: system section must be a mapping")
    else:
        if not system.get("name"):
            errors.append("config/main.yaml: system.name is required")
        if not system.get("version"):
            errors.append("config/main.yaml: system.version is required")

    permissions = data.get("permissions", {})
    if not isinstance(permissions, dict):
        errors.append("config/main.yaml: permissions section must be a mapping")
    else:
        default_level = permissions.get("default_level")
        if default_level not in {"basic", "extended", "admin"}:
            errors.append("config/main.yaml: permissions.default_level must be basic, extended, or admin")
        if not permissions.get("admin_role"):
            errors.append("config/main.yaml: permissions.admin_role is required")

    logging_section = data.get("logging", {})
    if not isinstance(logging_section, dict):
        errors.append("config/main.yaml: logging section must be a mapping")
    else:
        if logging_section.get("level") not in VALID_LOG_LEVELS:
            errors.append("config/main.yaml: logging.level must be DEBUG, INFO, WARNING, or ERROR")

    agent = data.get("agent", {})
    if not isinstance(agent, dict):
        errors.append("config/main.yaml: agent section must be a mapping")
    else:
        max_iter = agent.get("max_iter")
        if max_iter is not None and not isinstance(max_iter, int):
            errors.append("config/main.yaml: agent.max_iter must be an integer")

    storage = data.get("storage", {})
    if not isinstance(storage, dict):
        errors.append("config/main.yaml: storage section must be a mapping")
    else:
        backend = storage.get("backend")
        if backend not in VALID_STORAGE_BACKENDS:
            errors.append("config/main.yaml: storage.backend must be json or sqlite")

    ecosystem = data.get("ecosystem", {})
    if not isinstance(ecosystem, dict):
        errors.append("config/main.yaml: ecosystem section must be a mapping")
    else:
        for field in ("skills_path", "skills_box", "agents_path", "tools_path", "teams_path", "bootstrap_path"):
            if not ecosystem.get(field):
                errors.append(f"config/main.yaml: ecosystem.{field} is required")

    return errors


def validate_bootstrap(bootstrap_file: Path) -> List[str]:
    errors: List[str] = []
    data, yaml_errors = _load_yaml(bootstrap_file)
    errors.extend(yaml_errors)
    if not data:
        return errors

    for field in ("bootstrap_skill", "skill_path", "inject_at_start"):
        if field not in data:
            errors.append(f"bootstrap/using-yukta.yaml: Missing required field '{field}'")

    if data.get("inject_at_start") not in {True, False}:
        errors.append("bootstrap/using-yukta.yaml: inject_at_start must be a boolean")

    return errors


__all__ = [
    "validate_ecosystem",
    "validate_agent",
    "validate_tool",
    "validate_team",
    "validate_skill",
    "validate_index",
    "validate_config",
    "validate_bootstrap",
]