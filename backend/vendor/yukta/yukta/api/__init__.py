"""
yukta-api — Python API for ecosystem operations

This module provides the full wrapper functionality for creating,
managing, and running ecosystem-based AI agents.

Modules:
    models       - Data structures (AgentData, ToolData, SkillData, TeamData)
    reader       - Read and parse ecosystem files
    validator   - Validation layer
    transformer - Convert ecosystem objects to yukta objects
    allocator   - Dynamic skill/task allocation
    runner       - Execute agents via yukta engine
    compiler     - Compile ecosystem and generate indices

Usage:
    from yukta.api import (
        load_ecosystem,
        transform_agent,
        run_agent,
        build_and_run_agent,
    )
"""

__version__ = "2.1.0"

from .models import (
    AgentLevel,
    ToolType,
    TeamStructure,
    PermissionLevel,
    ApprovalStatus,
    HitlMode,
    SkillData,
    ToolParameterData,
    ToolData,
    AgentData,
    TeamData,
    TeamSession,
    LeaderBrief,
    AgentReport,
    BootstrapConfig,
    SystemConfig,
)

from .reader import (
    read_config_yaml,
    read_bootstrap_yaml,
    read_skill_md,
    read_tool_yaml,
    read_agent_yaml,
    read_team_yaml,
    load_skills_from_index,
    load_all_tools,
    load_all_agents,
    load_all_teams,
    load_ecosystem,
)

from .validator import (
    validate_skill,
    validate_tool,
    validate_agent,
    validate_team,
    validate_agent_permissions,
    validate_agent_level,
    validate_tool_access,
    validate_skill_assignment,
    validate_ecosystem,
)

from .transformer import (
    transform_tool,
    transform_tools_processor,
    transform_bootstrap,
    transform_agent_system_prompt,
    transform_agent_config,
    transform_agent,
)

from .allocator import (
    get_available_skills_for_agent,
    get_agent_tools,
    allocate_skills_for_task,
    can_agent_perform_action,
)

from .runner import (
    run_agent,
    run_agent_with_task,
    aggregate_results,
    build_and_run_agent,
)

from .compiler import (
    compile_ecosystem,
    generate_index,
)

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

from .runner import (
    run_tool,
    list_available_tools,
)

from .modern_logger import (
    ModernColors,
    ModernFormatter,
    generate_event_banner,
    setup_logging,
    get_logger,
    debug,
    info,
    warning,
    error,
    critical,
    log_event,
)

from .orchestrator import (
    SpeakerSelector,
    GroupChatSession,
    run_team,
    LeaderCoordinator,
)
from .coordinator import LeaderCoordinator  # noqa: F811 — explicit re-export
from ..core.Agent.agent_callbacks import AgentCallbackHandler

__all__ = [
    # Models
    "AgentLevel",
    "ToolType",
    "TeamStructure", 
    "PermissionLevel",
    "ApprovalStatus",
    "HitlMode",
    "SkillData",
    "ToolParameterData",
    "ToolData",
    "AgentData",
    "TeamData",
    "TeamSession",
    "LeaderBrief",
    "AgentReport",
    "BootstrapConfig",
    "SystemConfig",
    # Reader
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
    # Validator
    "validate_skill",
    "validate_tool",
    "validate_agent",
    "validate_team",
    "validate_agent_permissions",
    "validate_agent_level",
    "validate_tool_access",
    "validate_skill_assignment",
    "validate_ecosystem",
    # Transformer
    "transform_tool",
    "transform_tools_processor",
    "transform_bootstrap",
    "transform_agent_system_prompt",
    "transform_agent_config",
    "transform_agent",
    # Allocator
    "get_available_skills_for_agent",
    "get_agent_tools",
    "allocate_skills_for_task",
    "can_agent_perform_action",
    # Runner
    "run_agent",
    "run_agent_with_task",
    "aggregate_results",
    "build_and_run_agent",
    "run_tool",
    "list_available_tools",
    # Compiler
    "compile_ecosystem",
    "generate_index",
    # Loader
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
    # Modern Logger
    "ModernColors",
    "ModernFormatter",
    "generate_event_banner",
    "setup_logging",
    "get_logger",
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "log_event",
    # Orchestrator
    "SpeakerSelector",
    "GroupChatSession",
    "run_team",
    "LeaderCoordinator",
    # Callbacks
    "AgentCallbackHandler",
]