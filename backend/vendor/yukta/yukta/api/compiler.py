"""
Compiler module - generates the skills-box index file and compiles ecosystem.
Scans ecosystem and creates index.yaml and build/ecosystem.yaml.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def generate_index(ecosystem_path: Path) -> None:
    """
    Generate skills-box index from ecosystem files.

    Args:
        path: Path to ecosystem directory
    """
    ecosystem_path = Path(ecosystem_path)
    index = {
        "skills": [],
        "tools": [],
        "agents": [],
        "teams": [],
    }

    agents_dir = ecosystem_path / "agents"
    if agents_dir.exists():
        for agent_file in agents_dir.glob("*.yaml"):
            try:
                with open(agent_file, "r") as f:
                    data = yaml.safe_load(f) or {}
                index["agents"].append({
                    "id": data.get("agent_id", agent_file.stem),
                    "path": f"agents/{agent_file.name}",
                    "version": data.get("version", "1.0.0"),
                })
            except Exception as e:
                logger.warning(f"Failed to load agent {agent_file.name}: {e}")

    skills_dir = ecosystem_path / "skills"
    if skills_dir.exists():
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    try:
                        content = skill_file.read_text()
                        frontmatter = {}
                        if content.startswith("---"):
                            parts = content.split("---", 2)
                            if len(parts) >= 2:
                                frontmatter = yaml.safe_load(parts[1]) or {}

                        index["skills"].append({
                            "id": frontmatter.get("skill_id", skill_dir.name),
                            "path": f"skills/{skill_dir.name}/SKILL.md",
                            "version": frontmatter.get("version", "1.0.0"),
                            "categories": frontmatter.get("categories", []),
                            "description": frontmatter.get("description", ""),
                        })
                    except Exception as e:
                        logger.warning(f"Failed to load skill in {skill_dir.name}: {e}")

    tools_dir = ecosystem_path / "tools"
    if tools_dir.exists():
        for tool_file in tools_dir.glob("*.yaml"):
            try:
                with open(tool_file, "r") as f:
                    data = yaml.safe_load(f) or {}
                index["tools"].append({
                    "id": data.get("tool_id", tool_file.stem),
                    "path": f"tools/{tool_file.name}",
                    "version": data.get("version", "1.0.0"),
                    "description": data.get("description", ""),
                })
            except Exception as e:
                logger.warning(f"Failed to load tool {tool_file.name}: {e}")

    teams_dir = ecosystem_path / "teams"
    if teams_dir.exists():
        for team_file in teams_dir.glob("*.yaml"):
            try:
                with open(team_file, "r") as f:
                    data = yaml.safe_load(f) or {}
                index["teams"].append({
                    "id": data.get("team_id", team_file.stem),
                    "path": f"teams/{team_file.name}",
                })
            except Exception as e:
                logger.warning(f"Failed to load team {team_file.name}: {e}")

    index_file = ecosystem_path / "skills-box" / "index.yaml"
    index_file.parent.mkdir(parents=True, exist_ok=True)

    with open(index_file, "w") as f:
        yaml.safe_dump({"skills": index["skills"], "tools": index["tools"],
                    "agents": index["agents"], "teams": index["teams"]}, f,
                    default_flow_style=False, sort_keys=False)


def compile_ecosystem(ecosystem_path: Path) -> Path:
    """
    Compile ecosystem to a single YAML file.

    Args:
        path: Path to ecosystem directory

    Returns:
        Path to the compiled file (build/ecosystem.yaml)
    """
    ecosystem_path = Path(ecosystem_path)
    build_dir = ecosystem_path / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    config_file = ecosystem_path / "config" / "main.yaml"
    project_name = "ecosystem"
    version = "1.0.0"

    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                config = yaml.safe_load(f) or {}
                project_name = config.get("name", "ecosystem")
                version = config.get("version", "1.0.0")
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")

    compiled = {
        "version": version,
        "project_name": project_name,
        "generated_at": datetime.now().isoformat(),
        "agents": [],
        "skills": [],
        "tools": [],
        "teams": [],
    }

    agents_dir = ecosystem_path / "agents"
    if agents_dir.exists():
        for agent_file in agents_dir.glob("*.yaml"):
            try:
                with open(agent_file, "r") as f:
                    data = yaml.safe_load(f) or {}
                if data:
                    compiled["agents"].append(data)
            except Exception as e:
                logger.warning(f"Failed to compile agent {agent_file.name}: {e}")

    skills_dir = ecosystem_path / "skills"
    if skills_dir.exists():
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    try:
                        content = skill_file.read_text()
                        skill_data = {
                            "skill_id": skill_dir.name,
                            "file_path": f"skills/{skill_dir.name}/SKILL.md",
                            "content": content,
                        }

                        if content.startswith("---"):
                            parts = content.split("---", 2)
                            if len(parts) >= 2:
                                try:
                                    frontmatter = yaml.safe_load(parts[1]) or {}
                                    skill_data["frontmatter"] = frontmatter
                                except Exception as e:
                                    logger.warning(f"Failed to parse frontmatter for {skill_dir.name}: {e}")

                        compiled["skills"].append(skill_data)
                    except Exception as e:
                        logger.warning(f"Failed to compile skill {skill_dir.name}: {e}")

    tools_dir = ecosystem_path / "tools"
    if tools_dir.exists():
        for tool_file in tools_dir.glob("*.yaml"):
            try:
                with open(tool_file, "r") as f:
                    data = yaml.safe_load(f) or {}
                if data:
                    compiled["tools"].append(data)
            except Exception as e:
                logger.warning(f"Failed to compile tool {tool_file.name}: {e}")

    teams_dir = ecosystem_path / "teams"
    if teams_dir.exists():
        for team_file in teams_dir.glob("*.yaml"):
            try:
                with open(team_file, "r") as f:
                    data = yaml.safe_load(f) or {}
                if data:
                    compiled["teams"].append(data)
            except Exception as e:
                logger.warning(f"Failed to compile team {team_file.name}: {e}")

    output_file = build_dir / "ecosystem.yaml"
    with open(output_file, "w") as f:
        yaml.safe_dump(compiled, f, default_flow_style=False, sort_keys=False)

    return output_file


__all__ = ["generate_index", "compile_ecosystem"]
