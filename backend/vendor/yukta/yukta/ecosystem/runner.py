"""
Runner module - executes tools from ecosystem.
"""

import sys
import inspect
from pathlib import Path
from typing import Dict, Any, Callable

from .exceptions import ToolNotFoundError, EcosystemError
from .loader import load_tool
from .resolver import load_tool_function


def run_tool(
    tool_name: str, 
    ecosystem_path: Path, 
    params: Dict[str, Any] = None
) -> str:
    """
    Run a tool from the ecosystem.
    
    Args:
        tool_name: Name of the tool to run
        ecosystem_path: Path to ecosystem directory
        params: Parameters to pass to the tool
    
    Returns:
        Tool execution result
    
    Raises:
        ToolNotFoundError: If tool doesn't exist
        EcosystemError: If execution fails
    """
    if params is None:
        params = {}
    
    ecosystem_path = Path(ecosystem_path)
    
    if not ecosystem_path.exists():
        raise EcosystemError(f"Ecosystem path does not exist: {ecosystem_path}")
    
    tool_config = load_tool(tool_name, str(ecosystem_path))
    
    try:
        tool_function = load_tool_function(tool_config, ecosystem_path)
        
        sig = inspect.signature(tool_function)
        
        filtered_params = {}
        for param_name in sig.parameters:
            if param_name in params:
                filtered_params[param_name] = params[param_name]
        
        result = tool_function(**filtered_params)
        
        if result is None:
            return "(no output)"
        
        return str(result)
    
    except Exception as e:
        raise EcosystemError(f"Tool execution failed: {e}")


def list_available_tools(ecosystem_path: Path) -> list:
    """
    List all available tools in an ecosystem.
    
    Args:
        ecosystem_path: Path to ecosystem directory
    
    Returns:
        List of tool names
    """
    ecosystem_path = Path(ecosystem_path)
    tools_dir = ecosystem_path / "tools"
    
    if not tools_dir.exists():
        return []
    
    return [f.stem for f in tools_dir.glob("*.yaml")]


__all__ = ["run_tool", "list_available_tools"]