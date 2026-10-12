"""
transformer.py — Convert ecosystem objects to yukta package objects.

Takes AgentData, ToolData, SkillData and converts them to
yukta's Agent, Tool, SystemPrompt, AgentConfig, ToolParameter, ToolProcessor.
"""

import importlib
import logging
from typing import List, Optional, Dict, Any, Type

# Try flexible imports - support both editable and non-editable installs
Agent = None
AgentConfig = None
SystemPrompt = None
create_agent = None
Tool = None
ToolType = None
ToolParameter = None
ToolProcessor = None

# Try multiple import paths
_import_errors = []

# Try 1: from yukta (non-editable install)
try:
    from yukta import Agent as _A1, AgentConfig as _AC1, SystemPrompt as _SP1, create_agent as _CA1
    from yukta.tools import Tool as _T1, ToolParameter as _TP1, ToolProcessor as _TPROC1
    from yukta.tools import ToolType as _TT1
    Agent, AgentConfig, SystemPrompt, create_agent = _A1, _AC1, _SP1, _CA1
    Tool, ToolParameter, ToolProcessor = _T1, _TP1, _TPROC1
    ToolType = _TT1
except ImportError as e1:
    _import_errors.append(str(e1))

# If first try failed, try 2: from yukta.core (editable install or direct import)
if Agent is None:
    try:
        from yukta.core.Agent.agent import Agent as _A2, create_agent as _CA2
        from yukta.config.agent_config import AgentConfig as _AC2
        from yukta.config.system_prompt import SystemPrompt as _SP2
        from yukta.tools.tools_pro import Tool as _T2, ToolParameter as _TP2, ToolProcessor as _TPROC2
        from yukta.tools import ToolType as _TT2
        Agent, create_agent, AgentConfig, SystemPrompt = _A2, _CA2, _AC2, _SP2
        Tool, ToolParameter, ToolProcessor = _T2, _TP2, _TPROC2
        ToolType = _TT2
    except ImportError as e2:
        _import_errors.append(str(e2))

# If both failed, raise clear error
if Agent is None:
    raise ImportError(
        "The 'yukta' package is required. "
        f"Tried imports: {'; '.join(_import_errors)}. "
        "Install with: pip install yukta"
    )

from .models import (
    AgentData,
    ToolData,
    SkillData,
    BootstrapConfig,
    SystemConfig,
    ToolType as EcoToolType,
)

logger = logging.getLogger(__name__)


def _map_tool_type(eco_type: EcoToolType) -> Any:
    """Map ecosystem ToolType to yukta ToolType."""
    if ToolType is None:
        return None
    mapping = {
        EcoToolType.CUSTOM: ToolType.CUSTOM,
        EcoToolType.BUILTIN: ToolType.BUILTIN,
        EcoToolType.REMOTE_MCP: ToolType.REMOTE_MCP,
    }
    return mapping.get(eco_type, ToolType.BUILTIN)


def _validate_function_path(function_path: str) -> bool:
    """Validate the function_path format."""
    if not function_path or ":" not in function_path:
        raise ValueError(
            f"Invalid function_path '{function_path}'. "
            "Expected format: 'module.submodule:function_name'"
        )
    module_path, func_name = function_path.rsplit(":", 1)
    if not module_path or not func_name:
        raise ValueError(
            f"Invalid function_path '{function_path}'. "
            "Module path and function name cannot be empty."
        )
    if not func_name.isidentifier():
        raise ValueError(
            f"Invalid function_path '{function_path}'. "
            f"'{func_name}' is not a valid Python identifier."
        )
    return True


def transform_tool(tool_data: ToolData) -> Tool:
    """Convert a ToolData to a yukta Tool."""
    parameters = [
        ToolParameter(
            name=p.name,
            type=p.type,
            description=p.description,
            required=p.required,
            default=p.default,
            enum=p.enum,
        )
        for p in tool_data.parameters
    ]

    function = None
    if tool_data.function_path:
        try:
            _validate_function_path(tool_data.function_path)
        except ValueError as e:
            raise ValueError(f"Tool '{tool_data.tool_id}': {e}") from e

        try:
            module_path, func_name = tool_data.function_path.rsplit(":", 1)
            module = importlib.import_module(module_path)
            function = getattr(module, func_name)
        except ModuleNotFoundError as e:
            raise ImportError(f"Tool '{tool_data.tool_id}': Module '{module_path}' not found") from e
        except AttributeError as e:
            raise AttributeError(f"Tool '{tool_data.tool_id}': Function '{func_name}' not found") from e
        except Exception as e:
            raise RuntimeError(f"Tool '{tool_data.tool_id}': Failed to load function: {e}") from e

    return Tool(
        name=tool_data.tool_id,
        description=tool_data.description,
        parameters=parameters,
        tool_type=_map_tool_type(tool_data.tool_type),
        function=function,
        metadata={"tool_id": tool_data.tool_id, "version": tool_data.version},
    )


def transform_tools_processor(tool_data_list: List[ToolData], fail_fast: bool = False) -> ToolProcessor:
    """Build a yukta ToolProcessor from a list of ToolData."""
    processor = ToolProcessor()
    for tool_data in tool_data_list:
        try:
            tool = transform_tool(tool_data)
            processor.add_tool(tool)
        except Exception as e:
            if fail_fast:
                raise
            logger.warning(f"Failed to transform tool '{tool_data.tool_id}': {e}")
    return processor


def transform_bootstrap(bootstrap: BootstrapConfig, skill: Optional[SkillData]) -> SystemPrompt:
    """Build the bootstrap SystemPrompt from BootstrapConfig and the bootstrap skill."""
    if skill:
        text = f"<EXTREMELY-IMPORTANT>\n{skill.to_system_prompt_text()}\n</EXTREMELY-IMPORTANT>"
    else:
        logger.warning(
            f"Bootstrap skill '{bootstrap.bootstrap_skill}' not found. "
            "Agent will start without the essential 'using-yukta' guidance."
        )
        text = "<EXTREMELY-IMPORTANT>\nYou are operating inside the yukta-ecosystem.\n</EXTREMELY-IMPORTANT>"

    if bootstrap.additional_context:
        text += f"\n\n{bootstrap.additional_context}"

    return SystemPrompt(
        prompt_name="bootstrap",
        prompt_text=text,
        metadata={"bootstrap_skill": bootstrap.bootstrap_skill},
    )


def transform_agent_system_prompt(
    agent_data: AgentData,
    loaded_skills: List[SkillData],
    bootstrap_prompt: Optional[SystemPrompt] = None,
) -> SystemPrompt:
    """Build a yukta SystemPrompt for an agent."""
    skill_map: Dict[str, SkillData] = {s.skill_id: s for s in loaded_skills}
    parts: List[str] = []

    if bootstrap_prompt:
        parts.append(bootstrap_prompt.prompt_text)

    parts.append(agent_data.build_system_prompt_text())

    assigned_skill_contents = []
    for skill_id in sorted(agent_data.skills):
        if skill_id in skill_map:
            assigned_skill_contents.append(skill_map[skill_id].to_system_prompt_text())
    if assigned_skill_contents:
        parts.append("\n## Your Assigned Skills\n")
        parts.extend(assigned_skill_contents)

    full_text = "\n\n".join(parts)

    return SystemPrompt(
        prompt_name=agent_data.agent_id,
        prompt_text=full_text,
        metadata={
            "agent_id": agent_data.agent_id,
            "role": agent_data.role,
            "level": agent_data.level.value,
        },
    )


def transform_agent_config(system_config: SystemConfig) -> AgentConfig:
    """Build a yukta AgentConfig from the ecosystem SystemConfig."""
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    log_level_int = log_level_map.get(system_config.log_level.upper(), logging.INFO)

    return AgentConfig(
        enable_logging=system_config.enable_logging,
        log_level=log_level_int,
        enable_memory_logging=system_config.enable_memory_logging,
        memory_log_level=log_level_int,
        auto_save_chat_history=system_config.auto_save_chat,
        chat_history_dir=system_config.chat_history_dir,
        max_iter=system_config.max_iter,
    )


def transform_agent(
    agent_data: AgentData,
    loaded_skills: List[SkillData],
    loaded_tools: List[ToolData],
    system_config: SystemConfig,
    bootstrap_prompt: Optional[SystemPrompt] = None,
    fail_fast: bool = True,
    memory: Any = None,
) -> Agent:
    """Build a fully configured yukta Agent from AgentData."""
    logger.info(f"Building agent '{agent_data.agent_id}'...")

    tool_map: Dict[str, ToolData] = {t.tool_id: t for t in loaded_tools}
    agent_tools = []
    for tid in agent_data.tools:
        if tid in tool_map:
            agent_tools.append(tool_map[tid])
        else:
            logger.warning(
                "Agent '%s' declares tool '%s' but it was not found in the ecosystem — skipping.",
                agent_data.agent_id, tid,
            )

    logger.info(f"Loading {len(agent_tools)} tools for agent...")

    tools_processor = transform_tools_processor(agent_tools, fail_fast=fail_fast)

    logger.info("Building agent system prompt...")

    system_prompt = transform_agent_system_prompt(agent_data, loaded_skills, bootstrap_prompt)
    config = transform_agent_config(system_config)

    logger.info(f"Agent '{agent_data.agent_id}' built with {len(agent_tools)} tools")

    _level_to_perm = {"junior": "basic", "senior": "extended", "lead": "admin"}
    permission_level = _level_to_perm.get(agent_data.level.value.lower(), "basic")

    return create_agent(
        name=agent_data.agent_id,
        system_prompt=system_prompt,
        tools_processor=tools_processor,
        config=config,
        memory=memory,
        permission_level=permission_level,
    )


__all__ = [
    "transform_tool",
    "transform_tools_processor",
    "transform_bootstrap",
    "transform_agent_system_prompt",
    "transform_agent_config",
    "transform_agent",
]