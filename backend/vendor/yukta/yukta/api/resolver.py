"""
Resolver module - resolves skills and tools for agents.
"""

import sys
import importlib.util
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from .exceptions import ToolNotFoundError, EcosystemError

logger = logging.getLogger(__name__)


def resolve_agent_skills(skill_names: List[str], ecosystem_path: Path) -> List[Dict[str, Any]]:
    """Load skill data for an agent."""
    from .loader import load_skill

    skills = []
    for skill_name in skill_names:
        try:
            skill_data = load_skill(skill_name, str(ecosystem_path))
            skills.append(skill_data)
        except Exception as e:
            logger.warning(f"Could not load skill '%s': %s", skill_name, e)

    return skills


def resolve_agent_tools(tool_names: List[str], ecosystem_path: Path) -> List[Dict[str, Any]]:
    """Load tool data for an agent."""
    from .loader import load_tool

    tools = []
    for tool_name in tool_names:
        try:
            tool_data = load_tool(tool_name, str(ecosystem_path))
            tools.append(tool_data)
        except Exception as e:
            logger.warning(f"Could not load tool '%s': %s", tool_name, e)

    return tools


def load_tool_function(tool_config: Dict[str, Any], ecosystem_path: Path):
    """
    Load and return a tool function from its implementation.

    Args:
        tool_config: Tool configuration dict
        ecosystem_path: Path to ecosystem directory

    Returns:
        Callable tool function
    """
    function_path = tool_config.get("function_path")

    if not function_path:
        raise ToolNotFoundError("Tool has no function_path defined")

    try:
        module_path, function_name = function_path.split(":")
    except ValueError:
        raise ToolNotFoundError(
            f"Invalid function_path format: {function_path}. Expected: 'module:function'"
        )

    ecosystem_path_abs = ecosystem_path.resolve()
    ecosystem_path_str = str(ecosystem_path_abs)
    tools_impl_path = ecosystem_path_abs / "tools-impl"
    tools_impl_str = str(tools_impl_path)

    allowed_roots = {ecosystem_path_str, tools_impl_str}

    if ecosystem_path_str not in sys.path:
        sys.path.insert(0, ecosystem_path_str)
    if tools_impl_str not in sys.path:
        sys.path.insert(0, tools_impl_str)

    try:
        spec = importlib.util.find_spec(module_path)
        if spec is None:
            raise ModuleNotFoundError(f"Module '{module_path}' not found")

        # Reject modules whose source file resolves outside the ecosystem directory.
        # This blocks stdlib modules (os, subprocess, etc.) and any path-traversal attempt.
        module_origin = spec.origin
        if module_origin:
            module_origin_resolved = str(Path(module_origin).resolve())
            if not any(module_origin_resolved.startswith(root) for root in allowed_roots):
                raise ToolNotFoundError(
                    f"Module '{module_path}' resolves outside the ecosystem directory "
                    f"({module_origin_resolved!r}). Only modules inside the ecosystem "
                    f"'tools-impl/' folder are allowed."
                )

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, function_name):
            raise AttributeError(
                f"Function '{function_name}' not found in module '{module_path}'"
            )

        return getattr(module, function_name)

    except ToolNotFoundError:
        raise
    except Exception as e:
        raise ToolNotFoundError(f"Failed to load tool function: {e}")


__all__ = [
    "resolve_agent_skills",
    "resolve_agent_tools",
    "load_tool_function",
]
