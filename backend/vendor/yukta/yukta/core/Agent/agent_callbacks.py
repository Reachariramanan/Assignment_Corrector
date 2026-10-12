"""
Agent lifecycle callbacks — observe LLM calls, tool execution, and run events.

Subclass AgentCallbackHandler and override any method to hook into the agent's execution.
All methods are no-ops by default — safe to call without overriding.
"""

from typing import Any, Dict, List


class AgentCallbackHandler:
    """
    Base class for observing agent lifecycle events.

    Override any method to react to specific events.
    All methods are no-ops by default.

    Example::

        class MyHandler(AgentCallbackHandler):
            def on_tool_start(self, tool_name: str, args: dict) -> None:
                print(f"Calling tool: {tool_name}")

            def on_run_end(self, result: dict) -> None:
                print(f"Run finished: {result.get('iterations')} iterations")

        agent = create_agent("MyAgent", ..., callbacks=MyHandler())
    """

    def on_llm_start(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> None:
        """Called just before an LLM generate() call."""

    def on_llm_end(self, response: Any) -> None:
        """Called after a successful LLM generate() call. response is an LLMResponse."""

    def on_tool_start(self, tool_name: str, args: Dict[str, Any]) -> None:
        """Called just before a tool function is executed."""

    def on_tool_end(self, tool_name: str, result: Dict[str, Any], duration_ms: float) -> None:
        """Called after a tool finishes executing (success or failure)."""

    def on_iteration_end(self, iteration: int, response_text: str) -> None:
        """Called at the end of each agent loop iteration."""

    def on_run_end(self, result: Dict[str, Any]) -> None:
        """Called when agent.run() is about to return its final result."""

    def on_error(self, error: Exception, context: str) -> None:
        """Called when an error occurs. context describes where the error happened."""
