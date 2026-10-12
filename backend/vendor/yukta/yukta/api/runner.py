"""
runner.py — Execute agents via the yukta engine.

Functions:
    run_agent(agent, user_message)             → Dict[str, Any]
    run_agent_with_task(agent, task)           → Dict[str, Any]
    aggregate_results(results)                 → Dict[str, Any]
    build_and_run_agent(agent_id, ecosystem, llm_client, user_message) → Dict[str, Any]
    run_tool(tool_name, ecosystem_path, params) → str
    list_available_tools(ecosystem_path)       → list
"""

from typing import Dict, Any, List, Optional, Callable
import sys
import inspect
from pathlib import Path
import logging

try:
    from yukta import Agent
    from yukta.core.Clients.llmclientfactory import BaseLLMClient
except ImportError as e:
    raise ImportError(
        "The 'yukta' package is required but not installed. "
        "Install it by running: pip install yukta"
    ) from e

from .models import AgentData, SkillData, ToolData, SystemConfig, BootstrapConfig
from .transformer import transform_agent
from .exceptions import ToolNotFoundError, EcosystemError
from .loader import load_tool
from .resolver import load_tool_function

logger = logging.getLogger(__name__)


class CallbackHandler(logging.Handler):
    """Logging handler that redirects logs to a callback function."""
    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        try:
            msg = self.format(record)
            self.callback(msg)
        except Exception:
            self.handleError(record)


def run_agent(agent: Agent, user_message: str, log_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Execute a configured yukta Agent with a user message."""
    if not agent.llm_client:
        logger.error(f"Agent '{agent.agent_name}' has no llm_client set!")
        raise RuntimeError(
            f"Agent '{agent.agent_name}' has no llm_client set. "
            "Use agent.set_llm_client(client) before calling run_agent()."
        )

    handler = None
    if log_callback:
        handler = CallbackHandler(log_callback)
        yukta_logger = logging.getLogger("yukta")
        yukta_logger.addHandler(handler)

    try:
        return agent.run(user_message)
    finally:
        if handler:
            logging.getLogger("yukta").removeHandler(handler)


def run_agent_with_task(agent: Agent, task: Dict[str, Any]) -> Dict[str, Any]:
    """Run a yukta Agent with a structured task dict."""
    user_input: str = task.get("input", "")
    context: str = task.get("context", "")
    reset: bool = task.get("reset", False)

    if not user_input:
        return {"success": False, "error": "Task has no 'input' field"}

    if context:
        full_message = f"{context}\n\n{user_input}"
    else:
        full_message = user_input

    return agent.run(full_message, reset_conversation=reset)


def aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate results from multiple agent runs."""
    if not results:
        return {"total": 0, "successful": 0, "failed": 0, "responses": [], "errors": [], "all_tool_calls": []}
    
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    logger.info(f"Aggregation complete: {len(successful)} successful, {len(failed)} failed")

    return {
        "total": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "responses": [r.get("response", r.get("final_response", "")) for r in successful],
        "errors": [r.get("error", "Unknown error") for r in failed],
        "all_tool_calls": [tc for r in results for tc in r.get("tool_calls", [])],
    }


def build_and_run_agent(
    agent_id: str,
    ecosystem: Dict[str, Any],
    llm_client: BaseLLMClient,
    user_message: str,
    log_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Full pipeline: find agent → transform → set LLM client → run."""
    agents: List[AgentData] = ecosystem.get("agents", [])
    skills: List[SkillData] = ecosystem.get("skills", [])
    tools: List[ToolData] = ecosystem.get("tools", [])
    config: SystemConfig = ecosystem.get("config")
    bootstrap: BootstrapConfig = ecosystem.get("bootstrap")

    agent_data = next((a for a in agents if a.agent_id == agent_id), None)
    if not agent_data:
        logger.error(f"Agent '{agent_id}' not found in ecosystem!")
        return {"success": False, "error": f"Agent '{agent_id}' not found in ecosystem"}

    logger.info(f"Agent '{agent_id}' found: {agent_data.role}")

    bootstrap_skill = next((s for s in skills if s.skill_id == bootstrap.bootstrap_skill), None)
    bootstrap_prompt = None

    yukta_agent = transform_agent(agent_data, skills, tools, config, bootstrap_prompt)
    yukta_agent.set_llm_client(llm_client)

    if hasattr(yukta_agent, 'tools_processor'):
        try:
            registered_tools = yukta_agent.tools_processor.list_tools()
            for tool_name in registered_tools:
                logger.info(f"Tool registered: {tool_name}")
        except Exception:
            pass

    logger.info(f"Agent '{yukta_agent.agent_name}' ready with {len(tools)} tools")

    return run_agent(yukta_agent, user_message, log_callback=log_callback)


def run_tool(
    tool_name: str,
    ecosystem_path: Path,
    params: Optional[Dict[str, Any]] = None
) -> str:
    """
    Run a tool from the ecosystem.

    Args:
        tool_name: Name of the tool to run
        ecosystem_path: Path to ecosystem directory
        params: Parameters to pass to the tool

    Returns:
        Tool execution result
    """
    if params is None:
        params = {}
    elif not isinstance(params, dict):
        raise TypeError(f"params must be a dict or None, got {type(params).__name__}")

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


def list_available_tools(ecosystem_path: Path) -> List[str]:
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


__all__ = [
    "run_agent",
    "run_agent_with_task",
    "aggregate_results",
    "build_and_run_agent",
    "run_tool",
    "list_available_tools",
]