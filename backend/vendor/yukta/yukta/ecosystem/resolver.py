"""
Resolver module - resolves skills and tools for agents.
"""

import sys
import warnings
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


def load_tool_function(tool_config: Dict[str, Any], ecosystem_path: Path, require_sandbox: bool = True):
    """
    Load and return a tool function from its implementation.
    
    Args:
        tool_config: Tool configuration dict
        ecosystem_path: Path to ecosystem directory
    
    Returns:
        Callable tool function
    """
    trust_level = tool_config.get("trust_level", "trusted")
    if trust_level != "sandbox":
        if require_sandbox:
            warnings.warn(
                f"Tool '{tool_config.get('name', 'unknown')}' is loaded from a dynamic module "
                f"with trust_level='{trust_level}'. Set trust_level='sandbox' in the tool config "
                f"or pass require_sandbox=False to suppress this warning. "
                f"Executing untrusted code without sandboxing is a security risk.",
                UserWarning,
                stacklevel=2,
            )
        else:
            logger.warning(
                "Loading dynamic tool '%s' with trust_level='%s' and sandboxing disabled. "
                "Ensure the ecosystem source is trusted.",
                tool_config.get("name", "unknown"),
                trust_level,
            )

    function_path = tool_config.get("function_path")

    if not function_path:
        raise ToolNotFoundError("Tool has no function_path defined")
    
    try:
        module_path, function_name = function_path.split(":")
    except ValueError:
        raise ToolNotFoundError(
            f"Invalid function_path format: {function_path}. Expected: 'module:function'"
        )
    
    ecosystem_path_str = str(ecosystem_path.absolute())
    
    if ecosystem_path_str not in sys.path:
        sys.path.insert(0, ecosystem_path_str)
    
    tools_impl_path = ecosystem_path / "tools-impl"
    tools_impl_str = str(tools_impl_path.absolute())
    
    if tools_impl_str not in sys.path:
        sys.path.insert(0, tools_impl_str)
    
    try:
        spec = importlib.util.find_spec(module_path)
        if spec is None:
            raise ModuleNotFoundError(f"Module '{module_path}' not found")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if not hasattr(module, function_name):
            raise AttributeError(
                f"Function '{function_name}' not found in module '{module_path}'"
            )
        
        return getattr(module, function_name)
    
    except Exception as e:
        raise ToolNotFoundError(f"Failed to load tool function: {e}")


__all__ = [
    "resolve_agent_skills",
    "resolve_agent_tools",
    "load_tool_function",
]