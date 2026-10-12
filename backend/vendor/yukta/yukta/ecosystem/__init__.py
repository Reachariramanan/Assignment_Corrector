"""
Ecosystem module for Yukta.

DEPRECATED: This module is deprecated. Please use `yukta.api` instead.

Migration:
  - from yukta.ecosystem import load_agent
  - to   from yukta.api import load_agent

The functionality here is now available in yukta.api with improved features.
"""

import warnings
import sys

__version__ = "2.1.0"

# Emit deprecation warning when module is imported
def __getattr__(name):
    """Emit deprecation warning for any attribute access."""
    if name in _deprecated_attrs:
        warnings.warn(
            f"yukta.ecosystem.{name} is deprecated. "
            f"Use 'yukta.api.{_deprecated_attrs[name]}' instead. "
            "This module will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        # Try to forward to the new api module
        try:
            from .. import api
            return getattr(api, _deprecated_attrs[name])
        except ImportError:
            pass
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


_deprecated_attrs = {
    # Loader functions
    "load_agent": "load_agent",
    "load_skill": "load_skill",
    "load_tool": "load_tool",
    "load_team": "load_team",
    "list_agents": "list_agents",
    "list_skills": "list_skills",
    "list_tools": "list_tools",
    "list_teams": "list_teams",
    "load_index": "load_index",
    "clear_cache": "clear_cache",
    # Validator & Compiler
    "validate_ecosystem": "validate_ecosystem",
    "generate_index": "generate_index",
    "compile_ecosystem": "compile_ecosystem",
    # Runner
    "run_tool": "run_tool",
    # Exceptions
    "EcosystemError": "EcosystemError",
    "AgentNotFoundError": "AgentNotFoundError",
    "SkillNotFoundError": "SkillNotFoundError",
    "ToolNotFoundError": "ToolNotFoundError",
    "TeamNotFoundError": "TeamNotFoundError",
    "ValidationError": "ValidationError",
    "EcoValidationError": "ValidationError",
}

# For backwards compatibility, still export everything but through forwarding
__all__ = list(_deprecated_attrs.keys())

# Check for replacement module availability
try:
    from .. import api
    _api_available = True
except ImportError:
    _api_available = False
    # If api is not available, fall back to importing directly from submodule files
    from .loader import (
        load_agent,
        load_skill,
        load_tool,
        load_team,
        list_agents,
        list_skills,
        list_tools,
        list_teams,
        load_index,
        clear_cache,
    )
    from .validator import validate_ecosystem
    from .compiler import generate_index, compile_ecosystem
    from .runner import run_tool
    from .exceptions import (
        EcosystemError,
        AgentNotFoundError,
        SkillNotFoundError,
        ToolNotFoundError,
        TeamNotFoundError,
        ValidationError as EcoValidationError,
    )


def __dir__():
    """Return list of available attributes."""
    return list(_deprecated_attrs.keys())