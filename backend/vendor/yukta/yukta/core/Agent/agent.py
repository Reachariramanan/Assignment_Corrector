"""
Agent Module
Main agent class that integrates system prompts and tools processing.
"""

from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
import uuid
import json
import logging
from pathlib import Path
import time
from openinference.semconv.trace import OpenInferenceSpanKindValues
from .agent_callbacks import AgentCallbackHandler
from ...instrumentation.decorators import trace_yukta
from ...instrumentation.extractors import (
    extract_agent_attributes,
    extract_llm_attributes,
    extract_tool_attributes,
    extract_token_budget_attributes,
    extract_continuation_attributes
)
from ..storage import BaseStorageBackend, JSONFileStorage
from ...config.system_prompt import SystemPrompt
from ...tools.tools_pro import ToolProcessor, Tool, ToolType
from ...config.agent_config import AgentConfig
from ..Chat.llm_response import LLMResponse
from ..Clients.llmclientfactory import BaseLLMClient, format_tools_for_api, parse_tool_call_arguments
from ..memory import Memory
from ..Chat.chat import Chat, ChatManager
# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def set_agent_logging_level(level: int) -> None:
    """
    Set the logging level for agent module.
    
    Args:
        level: Logging level (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR)
    
    Examples:
        # Set to DEBUG for detailed logs
        set_agent_logging_level(logging.DEBUG)
        
        # Set to WARNING for fewer logs
        set_agent_logging_level(logging.WARNING)
    """
    logger.setLevel(level)
    logger.info(f"Agent logging level set to: {logging.getLevelName(level)}")





class Agent:
    """
    Main Agent class that combines system prompts and tools.
    
    This class represents an AI agent that can:
    - Use a defined system prompt
    - Access and utilize various tools
    - Execute tasks with context
    - Track its state and history
    
    Attributes:
        agent_id: Unique identifier for the agent
        agent_name: Human-readable name for the agent
        system_prompt: SystemPrompt instance defining agent behavior
        tools_processor: ToolProcessor instance managing available tools
        config: AgentConfig instance with agent settings
        state: Current state of the agent
        history: List of interaction history
    """
    
    def __init__(
        self,
        agent_name: str,
        system_prompt: SystemPrompt,
        tools_processor: ToolProcessor,
        config: Optional[AgentConfig] = None,
        agent_id: Optional[str] = None,
        llm_client: Optional['BaseLLMClient'] = None,
        memory: Optional['Memory'] = None,
        use_memory_cache: bool = False,
        callbacks: Optional[AgentCallbackHandler] = None,
        permission_level: str = "basic"
    ):
        """
        Initialize an Agent instance.
        
        Args:
            agent_name: Name of the agent
            system_prompt: SystemPrompt instance for the agent
            tools_processor: ToolProcessor instance with available tools
            config: Optional AgentConfig instance (uses defaults if not provided)
            agent_id: Optional custom agent ID (generates UUID if not provided)
            llm_client: Optional LLM client for agent execution
            memory: Optional Memory instance for advanced memory management with KV cache
            use_memory_cache: Whether to use Memory class for KV cache tracking
        """
        self.agent_id = agent_id or str(uuid.uuid4())
        self.agent_name = agent_name
        self.system_prompt = system_prompt
        self.tools_processor = tools_processor
        self.config = config or AgentConfig()
        self.llm_client = llm_client
        self.memory = memory
        self.use_memory_cache = use_memory_cache and memory is not None
        self.callbacks = callbacks
        self.permission_level = permission_level

        # Apply memory logging configuration if memory is provided
        if self.memory and self.config.enable_memory_logging:
            from ..memory import set_memory_logging_level
            set_memory_logging_level(self.config.memory_log_level)
        
        logger.info(f"Initializing agent: name='{agent_name}', id={self.agent_id[:8]}..., tools={len(tools_processor)}")
        
        # Chat management (primary conversation manager)
        self.chat: Optional[Chat] = None
        self.chat_manager: Optional[ChatManager] = None
        
        if self.config.auto_save_chat or self.config.auto_save_chat_history:
            # Initialize chat with system prompt
            system_prompt_text = self.system_prompt.get_prompt(agent_name=self.agent_name)
            
            # Get context window from LLM client if available
            context_window = 8192  # Default
            if hasattr(self.llm_client, 'get_context_window'):
                try:
                    context_window = self.llm_client.get_context_window()
                    logger.info(f"[{self.agent_id[:8]}] Using LLM context window: {context_window} tokens")
                except Exception as e:
                    logger.warning(f"[{self.agent_id[:8]}] Failed to get LLM context window: {str(e)}")
            else:
                logger.debug(f"[{self.agent_id[:8]}] LLM client doesn't support get_context_window(), using default: {context_window}")
            
            # Create Chat with context window management
            self.chat = Chat(
                system_prompt=system_prompt_text,
                chat_id=self.agent_id,
                metadata={"agent_name": self.agent_name},
                context_window=context_window,
                context_buffer=512  # Reserve 512 tokens for output
            )
            self.chat_manager = ChatManager(storage_backend=self.config.storage_backend)
            logger.debug(f'Chat save directory: %s', self.config.chat_save_dir)
            # Register chat with manager
            self.chat_manager.chats[self.chat.chat_id] = self.chat
            logger.debug(f"[{self.agent_id[:8]}] Chat enabled with ID: {self.chat.chat_id}")
        
        # Agent state
        self.state = {
            "status": "initialized",
            "created_at": datetime.now().isoformat(),
            "iterations": 0,
            "last_activity": None
        }
        
        # Interaction history
        self.history: List[Dict[str, Any]] = []
        
        # Message history for LLM conversations (legacy mode, fallback)
        self.messages: List[Dict[str, str]] = []
        
        # Statistics
        self.stats = {
            "total_interactions": 0,
            "tool_calls": 0,
            "successful_tool_calls": 0,
            "failed_tool_calls": 0,
            "llm_calls": 0,
            "total_tokens": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_cached_tokens": 0,
            "cache_cost_savings": 0.0
        }
        
        if self.config.verbose:
            logger.info(f"Agent '%s' initialized with ID: %s", self.agent_id, self.agent_id)
            logger.debug("Available tools: %s", self.tools_processor.list_tools())
            if self.llm_client:
                logger.debug(f"LLM client configured: {self.llm_client.model_name}")

        if self.chat is not None:
            logger.debug(f"Chat enabled with ID: {self.chat.chat_id}")

        if self.memory is not None:
            logger.debug(f"Memory cache enabled with session: {self.memory.session_id}")

        logger.info(f"[{self.agent_id[:8]}] Agent initialized successfully: llm={self.llm_client is not None}, memory={self.use_memory_cache}, auto_save_chat={self.config.auto_save_chat}")
    
    def get_system_prompt(self, **kwargs) -> str:
        """
        Get the formatted system prompt for the agent.
        
        Args:
            **kwargs: Additional variables to pass to the prompt
            
        Returns:
            Formatted system prompt string
        """
        return self.system_prompt.get_prompt(
            agent_name=self.agent_name,
            **kwargs
        )
    
    def get_available_tools(self, tool_type: Optional[ToolType] = None) -> List[str]:
        """
        Get list of available tools.
        
        Args:
            tool_type: Optional filter by tool type
            
        Returns:
            List of tool names
        """
        return self.tools_processor.list_tools(tool_type)
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool information dictionary or None if not found
        """
        tool = self.tools_processor.get_tool(tool_name)
        if tool:
            return tool.to_dict()
        return None
    
    def add_tool(self, tool: Tool) -> None:
        """
        Add a tool to the agent's tool processor.
        
        Args:
            tool: Tool instance to add
        """
        self.tools_processor.add_tool(tool)
        logger.info(f"[{self.agent_id[:8]}] Tool added: '{tool.name}' ({tool.tool_type.value})")
        if self.config.verbose:
            logger.debug(f"Tool '%s' added to agent '%s'", tool.name, self.agent_name)
    
    def remove_tool(self, tool_name: str) -> bool:
        """
        Remove a tool from the agent.
        
        Args:
            tool_name: Name of the tool to remove
            
        Returns:
            True if removed, False if not found
        """
        result = self.tools_processor.remove_tool(tool_name)
        if result:
            logger.info(f"[{self.agent_id[:8]}] Tool removed: '{tool_name}'")
            if self.config.verbose:
                logger.debug(f"Tool '%s' removed from agent '%s'", tool_name, self.agent_name)
        return result
    
    def validate_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate a tool call before execution.
        
        Args:
            tool_name: Name of the tool to validate
            arguments: Arguments to pass to the tool
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        tool = self.tools_processor.get_tool(tool_name)
        if not tool:
            return False, f"Tool '{tool_name}' not found"
        
        return tool.validate_args(arguments)
    
    @trace_yukta(kind=OpenInferenceSpanKindValues.TOOL)
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with given arguments.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            
        Returns:
            Dictionary with execution result
        """
        # Validate tool call
        is_valid, error_msg = self.validate_tool_call(tool_name, arguments)
        
        if not is_valid:
            self.stats["failed_tool_calls"] += 1
            logger.warning(f"[{self.agent_id[:8]}] Tool validation failed: {tool_name} - {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "tool": tool_name
            }
        
        # Get tool
        tool = self.tools_processor.get_tool(tool_name)

        # Permission check
        required = getattr(tool, "required_permission", "basic")
        _perm_rank = {"basic": 0, "extended": 1, "admin": 2}
        if _perm_rank.get(self.permission_level, 2) < _perm_rank.get(required, 0):
            self.stats["failed_tool_calls"] += 1
            logger.warning(
                f"[{self.agent_id[:8]}] Permission denied: tool '{tool_name}' requires "
                f"'{required}', agent has '{self.permission_level}'"
            )
            return {
                "success": False,
                "error": (
                    f"Agent permission '{self.permission_level}' insufficient for tool "
                    f"'{tool_name}' (requires '{required}')"
                ),
                "tool": tool_name
            }

        self.stats["tool_calls"] += 1

        logger.debug(f"[{self.agent_id[:8]}] Executing tool: {tool_name} with args: {list(arguments.keys())}")

        # If tool has a function, execute it
        if tool.function:
            self._emit("on_tool_start", tool_name=tool_name, args=arguments)
            _t0 = time.monotonic()
            try:
                if getattr(tool, "trust_level", "trusted") == "sandbox":
                    from ...tools.sandbox import ToolSandbox
                    _sandbox_result = ToolSandbox().execute_callable(tool.function, arguments)
                    if "error" in _sandbox_result:
                        raise RuntimeError(_sandbox_result["error"])
                    result = _sandbox_result.get("result", _sandbox_result)
                else:
                    result = tool.function(**arguments)
                _duration_ms = (time.monotonic() - _t0) * 1000
                self.stats["successful_tool_calls"] += 1

                try:
                    json.dumps(result, default=str)
                    logger.debug(f"[{self.agent_id[:8]}] Tool result is JSON-serializable")
                except TypeError:
                    logger.warning(f"[{self.agent_id[:8]}] Tool result not JSON-serializable, will convert on format")

                logger.info(f"[{self.agent_id[:8]}] Tool executed successfully: {tool_name}")
                _ok_result = {"success": True, "result": result, "tool": tool_name}
                self._emit("on_tool_end", tool_name=tool_name, result=_ok_result, duration_ms=_duration_ms)
                return _ok_result
            except Exception as e:
                _duration_ms = (time.monotonic() - _t0) * 1000
                self.stats["failed_tool_calls"] += 1
                logger.error(f"[{self.agent_id[:8]}] Tool execution failed: {tool_name} - {str(e)}")
                _err_result = {"success": False, "error": str(e)[:1000], "tool": tool_name}
                self._emit("on_tool_end", tool_name=tool_name, result=_err_result, duration_ms=_duration_ms)
                return _err_result
        else:
            # Tool doesn't have executable function
            self.stats["successful_tool_calls"] += 1
            return {
                "success": True,
                "message": f"Tool '{tool_name}' validated successfully",
                "tool": tool_name,
                "arguments": arguments
            }
    
    def add_to_history(self, interaction: Dict[str, Any]) -> None:
        """
        Add an interaction to the agent's history.
        
        Args:
            interaction: Dictionary containing interaction details
        """
        interaction["timestamp"] = datetime.now().isoformat()
        self.history.append(interaction)
        self.state["last_activity"] = interaction["timestamp"]
        self.stats["total_interactions"] += 1
        logger.debug(f"[{self.agent_id[:8]}] Interaction added to history: {interaction.get('type', 'unknown')}")
        # Trim to prevent unbounded growth
        max_history = getattr(self.config, "max_history", 1000)
        if len(self.history) > max_history:
            self.history = self.history[-max_history:]
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get agent interaction history.
        
        Args:
            limit: Optional limit on number of history items to return
            
        Returns:
            List of interaction dictionaries
        """
        if limit:
            return self.history[-limit:]
        return self.history
    
    def clear_history(self) -> None:
        """Clear the agent's interaction history."""
        count = len(self.history)
        self.history.clear()
        logger.info(f"[{self.agent_id[:8]}] History cleared: {count} interactions removed")
        if self.config.verbose:
            logger.debug("History cleared for agent '%s'", self.agent_name)
    
    def update_state(self, **kwargs) -> None:
        """
        Update the agent's state.
        
        Args:
            **kwargs: Key-value pairs to update in state
        """
        self.state.update(kwargs)
        self.state["last_activity"] = datetime.now().isoformat()
        logger.debug(f"[{self.agent_id[:8]}] State updated: {list(kwargs.keys())}")
    
    def get_agent_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about the agent.
        
        Returns:
            Dictionary with agent information
        """
        info = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "system_prompt": self.system_prompt.get_info(),
            "tools": self.tools_processor.get_tool_info(),
            "config": self.config.to_dict(),
            "state": self.state,
            "stats": self.stats,
            "history_length": len(self.history),
            "memory_enabled": self.use_memory_cache
        }
        
        # Add memory cache info if available
        if self.use_memory_cache:
            info["memory_cache"] = self.get_cache_info()
        
        return info
    
    def export_agent(self, filepath: str) -> None:
        """
        Export agent configuration to a JSON file.
        
        Args:
            filepath: Path to save the agent configuration
        """
        agent_data = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "system_prompt": {
                "name": self.system_prompt.prompt_name,
                "text": self.system_prompt.prompt_text,
                "variables": self.system_prompt.variables
            },
            "tools": self.tools_processor.format_for_llm(),
            "config": self.config.to_dict(),
            "state": self.state,
            "stats": self.stats
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(agent_data, f, indent=2)
        
        if self.config.verbose:
            logger.info(f"Agent configuration exported to: %s", filepath)
    
    def reset(self) -> None:
        """Reset the agent to initial state."""
        self.state = {
            "status": "initialized",
            "created_at": self.state["created_at"],
            "iterations": 0,
            "last_activity": None
        }
        self.history.clear()
        self.messages.clear()
        self.stats = {
            "total_interactions": 0,
            "tool_calls": 0,
            "successful_tool_calls": 0,
            "failed_tool_calls": 0,
            "llm_calls": 0,
            "total_tokens": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_cached_tokens": 0,
            "cache_cost_savings": 0.0
        }
        
        # Reset memory if using cache
        if self.use_memory_cache and self.memory:
            self.memory.clear(keep_system=True)
        
        # Reset chat if using it
        if self.chat is not None:
            self.chat.clear_messages(keep_system=True)
        
        if self.config.verbose:
            logger.info("Agent '%s' has been reset", self.agent_name)
    
    # ========== LLM Integration Methods ==========
    
    def set_llm_client(self, llm_client: 'BaseLLMClient') -> None:
        """
        Set or update the LLM client for the agent.
        
        Args:
            llm_client: LLM client instance
        """
        self.llm_client = llm_client
        if self.config.verbose:
            logger.debug("LLM client set: %s", llm_client.model_name)
    
    def set_memory(self, memory: 'Memory', enable_cache: bool = True) -> None:
        """
        Set or update the Memory instance for the agent.
        
        Args:
            memory: Memory instance
            enable_cache: Whether to enable KV cache tracking
        """
        self.memory = memory
        self.use_memory_cache = enable_cache
        
        # Apply memory logging configuration
        if self.config.enable_memory_logging:
            from ..memory import set_memory_logging_level
            set_memory_logging_level(self.config.memory_log_level)
            logger.debug(f"[{self.agent_id[:8]}] Memory logging configured: level={logging.getLevelName(self.config.memory_log_level)}")
        
        if self.config.verbose:
            logger.debug("Memory set: session=%s, cache_enabled=%s", memory.session_id, enable_cache)
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get KV cache information from memory or agent stats.
        
        Returns:
            Dictionary with cache statistics
        """
        if self.use_memory_cache:
            return self.memory.get_llm_cache_info()
        else:
            # Return basic cache stats from agent
            total_requests = self.stats["cache_hits"] + self.stats["cache_misses"]
            return {
                "cache_hits": self.stats["cache_hits"],
                "cache_misses": self.stats["cache_misses"],
                "cache_hit_rate": self.stats["cache_hits"] / total_requests if total_requests > 0 else 0.0,
                "total_cached_tokens": self.stats["total_cached_tokens"],
                "cache_cost_savings": self.stats["cache_cost_savings"]
            }
    
    def _initialize_conversation(self) -> None:
        """Initialize conversation with system prompt."""
        if self.use_memory_cache:
            # Memory handles system prompt internally
            return
        
        if self.chat is not None:
            # Chat handles system prompt internally
            return
        
        # Legacy mode: use messages list
        if not self.messages:
            system_prompt = self.get_system_prompt()
            self.messages = [
                {"role": "system", "content": system_prompt}
            ]
    
    def _format_tool_result(self, tool_result: Dict[str, Any]) -> str:
        """
        Format tool execution result for LLM with full content preservation.
        
        Args:
            tool_result: Result from execute_tool
            
        Returns:
            Formatted JSON string with complete result
        """
        if tool_result.get("success"):
            result = tool_result.get("result", tool_result.get("message", "Success"))
            
            try:
                # Format with full content, using default=str for non-serializable objects
                formatted = json.dumps(result, indent=2, default=str)
                logger.debug(f"Tool result formatted successfully, {len(formatted)} chars")
                return formatted
            except Exception as e:
                logger.warning(f"Failed to JSON serialize tool result: {e}. Converting to string.")
                return str(result)
        else:
            error_msg = f"Error: {tool_result.get('error', 'Unknown error')}"
            return error_msg
    
    def _emit(self, method_name: str, **kwargs) -> None:
        """Call a callback method if a handler is registered. Errors in callbacks are suppressed."""
        if self.callbacks is None:
            return
        try:
            getattr(self.callbacks, method_name)(**kwargs)
        except Exception as cb_err:
            logger.debug(f"[{self.agent_id[:8]}] Callback '{method_name}' raised: {cb_err}")

    def _save_run_state(self) -> None:
        """Persist state, stats, and history to {chat_history_dir}/{agent_name}/run_state.json."""
        if not self.config.auto_save_chat_history:
            return
        from pathlib import Path as _Path
        dir_ = _Path(self.config.chat_history_dir) / self.agent_name
        dir_.mkdir(parents=True, exist_ok=True)
        payload = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "state": self.state,
            "stats": self.stats,
            "history": self.history,
            "saved_at": datetime.now().isoformat(),
        }
        try:
            (dir_ / "run_state.json").write_text(json.dumps(payload, indent=2, default=str))
            logger.debug(f"[{self.agent_id[:8]}] Run state saved to {dir_ / 'run_state.json'}")
        except Exception as e:
            logger.warning(f"[{self.agent_id[:8]}] Failed to save run state: {e}")

    def load_run_state(self, path: Optional[str] = None) -> bool:
        """
        Restore state, stats, and history from a previously saved run_state.json.

        Args:
            path: Path to run_state.json (defaults to {chat_history_dir}/{agent_name}/run_state.json)

        Returns:
            True if loaded successfully, False otherwise
        """
        from pathlib import Path as _Path
        if path is None:
            path = str(_Path(self.config.chat_history_dir) / self.agent_name / "run_state.json")
        try:
            with open(path, "r") as f:
                payload = json.load(f)
            self.state = payload.get("state", self.state)
            self.stats = payload.get("stats", self.stats)
            self.history = payload.get("history", self.history)
            logger.info(f"[{self.agent_id[:8]}] Run state loaded from {path}")
            return True
        except FileNotFoundError:
            logger.warning(f"[{self.agent_id[:8]}] Run state file not found: {path}")
            return False
        except Exception as e:
            logger.error(f"[{self.agent_id[:8]}] Failed to load run state: {e}")
            return False

    def run(
        self,
        user_message: str,
        reset_conversation: bool = False,
        llm_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run the agent with an LLM to process user message and execute tools.

        Args:
            user_message: User's input message
            reset_conversation: Whether to reset conversation history
            llm_kwargs: Extra generation parameters forwarded to every
                llm_client.generate() call this turn (e.g. temperature,
                top_p, seed, stop).  Call-time values override the client's
                constructor defaults.

        Returns:
            Dictionary with final response and execution details

        Raises:
            RuntimeError: If no LLM client is configured
        """
        if not self.llm_client:
            raise RuntimeError("No LLM client configured. Set one using set_llm_client() or pass in constructor.")
        
        # Initialize error tracking early to prevent UnboundLocalError in exception handlers
        tool_execution_errors: List[Dict[str, Any]] = []
        
        logger.info(f"[{self.agent_id[:8]}] Starting agent run: user_message_len={len(user_message)}")
        
        # Reset conversation if requested
        if reset_conversation:
            logger.debug(f"[{self.agent_id[:8]}] Resetting conversation history")
            if self.use_memory_cache:
                self.memory.clear(keep_system=True)
            elif self.chat is not None:
                self.chat.clear_messages(keep_system=True)
            else:
                self.messages.clear()
            # Also reset run-specific state so callers don't see stale iterations/status
            self.state["iterations"] = 0
            self.state["status"] = "initialized"
        
        # Initialize conversation with system prompt
        self._initialize_conversation()
        
        # Add user message
        if self.use_memory_cache:
            self.memory.add_user_message(user_message)
        elif self.chat is not None:
            self.chat.add_user_message(user_message)
            self._auto_save_chat_if_enabled()  # Auto-save after user message
        else:
            self.messages.append({"role": "user", "content": user_message})
            # Trim legacy messages list to prevent unbounded growth
            max_history = getattr(self.config, "max_history", 1000)
            if len(self.messages) > max_history:
                # Keep system prompt (index 0) + most recent messages
                self.messages = self.messages[:1] + self.messages[-(max_history - 1):]

        # Add to history
        self.add_to_history({
            "type": "user_message",
            "content": user_message
        })
        
        iterations = 0
        final_response = ""
        tool_calls_made = []
        
        if self.config.verbose:
            logger.info(f"\n{'='*60}")
            logger.info(f"Agent '%s' started", self.agent_name)
            logger.info(f"User: %s", user_message)
            logger.info(f"{'='*60}\n")
        
        self.update_state(status="running")
        
        while True:
            iterations += 1
            self.state["iterations"] = iterations
            
            # Check if max_iter limit is reached
            if self.config.max_iter > 0 and iterations > self.config.max_iter:
                error_msg = f"Maximum iterations limit ({self.config.max_iter}) reached. Agent loop terminated to prevent endless loop."
                logger.warning(f"[{self.agent_id[:8]}] {error_msg}")
                if self.config.verbose:
                    logger.warning(f"\n⚠️  %s\n", error_msg)
                
                # Add to history
                self.add_to_history({
                    "type": "iteration_limit_reached",
                    "max_iter": self.config.max_iter,
                    "iterations": iterations
                })
                
                self.update_state(status="stopped", reason="max_iter_reached")
                _limit_result = {
                    "success": False,
                    "error": error_msg,
                    "iterations": iterations,
                    "tool_calls": tool_calls_made
                }
                self._emit("on_run_end", result=_limit_result)
                self._save_run_state()
                return _limit_result
            
            if self.config.verbose:
                logger.debug("[Iteration %d]", iterations)
            
            # Get tools in API format
            tools = format_tools_for_api(self.tools_processor.format_for_llm())
            
            # Get messages in LLM format
            if self.use_memory_cache:
                messages = self.memory.get_messages()
            elif self.chat is not None:
                messages = self.chat.get_messages(include_system=True)
            else:
                messages = self.messages
            
            # Calculate dynamic token budget for this generation
            # This ensures the model respects context limits BEFORE generation
            dynamic_max_tokens = None
            if self.chat is not None:
                try:
                    context_window = self.chat.context_window
                    current_tokens = self.chat.get_token_count()
                    context_buffer = self.chat.context_buffer
                    
                    # Available tokens: context_window - current_used - output_buffer
                    tokens_available = context_window - current_tokens - context_buffer
                    
                    # Ensure minimum generation space (at least 512 tokens)
                    dynamic_max_tokens = context_window - current_tokens - context_buffer
                    
                    logger.debug(
                        f"[{self.agent_id[:8]}] Token budget - Context: {context_window}, "
                        f"Used: {current_tokens}, Buffer: {context_buffer}, "
                        f"Available for generation: {tokens_available}, Allocating: {dynamic_max_tokens}"
                    )
                    
                    if self.config.verbose:
                        logger.info(f"  📊 Token budget: {current_tokens}/{context_window} used, "
                              f"allocating {dynamic_max_tokens} tokens for this turn")
                    
                    # 🔔 TRACE: Token budget debugging to Phoenix
                    try:
                        from ...instrumentation.tracer import yukta_tracer
                        current_span = getattr(yukta_tracer, '_current_span', None)
                        if current_span:
                            extract_token_budget_attributes(
                                current_span,
                                context_window, current_tokens, context_buffer, dynamic_max_tokens
                            )
                    except Exception as trace_err:
                        logger.debug(f"Failed to trace token budget: {trace_err}")
                        
                except Exception as e:
                    logger.warning(f"[{self.agent_id[:8]}] Failed to calculate token budget: {e}")
                    dynamic_max_tokens = None
            
            # Call LLM
            try:
                self._emit("on_llm_start", messages=messages, tools=tools or [])
                response: LLMResponse = self.llm_client.generate(
                    messages=messages,
                    tools=tools if tools else None,
                    max_tokens=dynamic_max_tokens,
                    **(llm_kwargs or {}),
                )
                
                # Handle incomplete responses due to max_tokens
                continuation_count = 0
                accumulated_content = response.content
                _original_content_length = len(response.content)  # capture before accumulation
                continuation_tool_calls = []
                
                while response.is_incomplete() and continuation_count < 3:  # Max 3 continuations
                    continuation_count += 1

                    if self.config.verbose:
                        logger.warning(f"\n  ⚠️  Response incomplete (finish_reason='%s')\n", response.finish_reason)
                        logger.info(f"  🔄 Continuing response [attempt %d/3]...\n", continuation_count)

                    logger.info(
                        f"[{self.agent_id[:8]}] Response incomplete due to max_tokens. "
                        f"Auto-continuing with tool support (attempt {continuation_count}/3)"
                    )
                    
                    # Build continuation message chain
                    messages.append({
                        "role": "assistant",
                        "content": accumulated_content,
                        "tool_calls": response.tool_calls if response.tool_calls else None
                    })
                    
                    # Add continuation prompt
                    continuation_prompt = {
                        "role": "user",
                        "content": f"Please continue your previous response from where you left off. "
                                   f"Continue naturally without repeating what you already said. "
                                   f"Use tools if needed to complete the response."
                    }
                    messages.append(continuation_prompt)
                    
                    # Recalculate token budget for continuation
                    new_dynamic_max_tokens = dynamic_max_tokens
                    if self.chat is not None:
                        try:
                            context_window = self.chat.context_window
                            current_tokens = self.chat.get_token_count()
                            context_buffer = self.chat.context_buffer
                            tokens_available = context_window - current_tokens - context_buffer
                            new_dynamic_max_tokens = max(512, min(tokens_available, 4096))
                            
                            logger.debug(f"[{self.agent_id[:8]}] Continuation budget: {new_dynamic_max_tokens} tokens")
                        except Exception as e:
                            logger.warning(f"Failed to recalculate continuation budget: {e}")
                    
                    # Get continuation (WITH TOOLS AVAILABLE)
                    try:
                        response = self.llm_client.generate(
                            messages=messages,
                            tools=tools if tools else None,  # KEEP tools available for continuation
                            max_tokens=new_dynamic_max_tokens,
                            **(llm_kwargs or {}),
                        )
                        
                        # Check if continuation response has tool calls
                        if response.has_tool_calls():
                            if self.config.verbose:
                                logger.warning(f"  🔧 Continuation requested %d tool call(s)", len(response.tool_calls))
                            
                            logger.info(
                                f"[{self.agent_id[:8]}] Continuation response contains "
                                f"{len(response.tool_calls)} tool call(s)"
                            )

                            continuation_assistant_message = {
                                "role": "assistant",
                                "content": response.content or "",
                                "tool_calls": response.tool_calls
                            }
                            messages.append(continuation_assistant_message)
                            
                            # Execute tool calls from continuation
                            for tool_call in response.tool_calls:
                                tool_name = tool_call.get("function", {}).get("name")
                                tool_args_str = tool_call.get("function", {}).get("arguments", "{}")
                                
                                if not tool_name:
                                    continue
                                
                                # Parse arguments
                                try:
                                    if isinstance(tool_args_str, str):
                                        tool_args = json.loads(tool_args_str)
                                    else:
                                        tool_args = tool_args_str
                                except Exception as e:
                                    tool_args = {}
                                    if self.config.verbose:
                                        logger.info(f"    ⚠️  Error parsing arguments: {e}")
                                
                                # Execute tool
                                tool_result = self.execute_tool(tool_name, tool_args)
                                
                                # Format and add tool result
                                tool_result_content = self._format_tool_result(tool_result)
                                
                                # Calculate token count for context management
                                tool_result_tokens = max(1, len(tool_result_content) // 4)
                                
                                # Trim context if tool result would exceed context window (for continuation loop)
                                if self.chat is not None:
                                    current_tokens = self.chat.get_token_count()
                                    if current_tokens + tool_result_tokens > self.chat.max_input_tokens:
                                        self.chat.trim_messages_to_context(min_required=tool_result_tokens)
                                elif self.use_memory_cache and self.memory is not None:
                                    current_tokens = self.memory.chat.get_token_count()
                                    if current_tokens + tool_result_tokens > self.memory.config.max_tokens:
                                        self.memory.chat.trim_messages_to_context(min_required=tool_result_tokens)
                                
                                messages.append({
                                    "role": "tool",
                                    "content": tool_result_content,
                                    "tool_call_id": tool_call.get("id", "")
                                })
                                
                                continuation_tool_calls.append({
                                    "tool": tool_name,
                                    "arguments": tool_args
                                })
                                
                                logger.debug(f"[{self.agent_id[:8]}] Executed continuation tool: {tool_name}")
                            
                            # Get final response after tool execution
                            try:
                                response = self.llm_client.generate(
                                    messages=messages,
                                    tools=tools if tools else None,
                                    max_tokens=new_dynamic_max_tokens,
                                    **(llm_kwargs or {}),
                                )
                                logger.debug(f"[{self.agent_id[:8]}] Got final response after tool execution in continuation")
                            except Exception as e:
                                logger.warning(f"[{self.agent_id[:8]}] Failed to get response after tool call in continuation: {e}")
                                response.incomplete = True
                                break
                        
                        # Append continuation content to accumulated
                        accumulated_content += response.content
                        response.content = accumulated_content
                        response.continuation_count = continuation_count
                        
                        logger.debug(
                            f"[{self.agent_id[:8]}] Continuation successful: "
                            f"+{len(response.content)} chars, tools_used={len(continuation_tool_calls)}"
                        )
                        
                    except Exception as e:
                        logger.error(f"[{self.agent_id[:8]}] Continuation failed: {e}")
                        response.incomplete = True
                        break
                
                # Add completion signal to content if there were continuations
                if continuation_count > 0:
                    tool_note = f" with {len(continuation_tool_calls)} tool call(s)" if continuation_tool_calls else ""
                    
                    if response.is_incomplete():
                        response.content += f"\n\n[⚠️  Response still incomplete after {continuation_count} continuations{tool_note}]"
                        if self.config.verbose:
                            logger.info(f"\n  ⚠️  Max continuations reached. Response may still be incomplete.")
                    else:
                        response.content += f"\n\n[✅ Response completed with {continuation_count} continuation(s){tool_note}]"
                        if self.config.verbose:
                            logger.info(f"\n  ✅ Response successfully completed with {continuation_count} "
                                  f"continuation(s){tool_note}")
                    
                    # 🔔 TRACE: Continuation session debugging to Phoenix
                    try:
                        from ...instrumentation.tracer import yukta_tracer
                        current_span = getattr(yukta_tracer, '_current_span', None)
                        if current_span:
                            continuation_tool_names = [tc.get("tool", "") for tc in continuation_tool_calls]
                            extract_continuation_attributes(
                                current_span,
                                continuation_count,
                                continuation_tool_calls,
                                _original_content_length,  # original length before accumulation
                                len(response.content)  # final total length after all continuations
                            )
                    except Exception as trace_err:
                        logger.debug(f"Failed to trace continuation session: {trace_err}")
                
                self.stats["llm_calls"] += 1
                self._emit("on_llm_end", response=response)
                self.stats["total_tokens"] += response.usage.get("total_tokens", 0)
                tokens_used = response.usage.get("total_tokens", 0)
                
                logger.debug(f"[{self.agent_id[:8]}] LLM call completed: tokens={tokens_used}, finish_reason={response.finish_reason}")
                
                # Track cache hits from LLM response
                if response.has_cache_hit():
                    self.stats["cache_hits"] += 1
                    cache_info = response.get_cache_info()
                    cached = cache_info.get("cached_tokens", 0)
                    self.stats["total_cached_tokens"] += cached
                    logger.info(f"[{self.agent_id[:8]}] LLM cache hit: {cached} tokens cached")
                else:
                    self.stats["cache_misses"] += 1
                
            except Exception as e:
                error_msg = f"LLM error: {str(e)}"
                logger.error(f"[{self.agent_id[:8]}] {error_msg}")
                if self.config.verbose:
                    logger.info(f"❌ {error_msg}")
                self.update_state(status="error")
                self._emit("on_error", error=e, context="llm_generate")
                _llm_err_result = {
                    "success": False,
                    "error": error_msg,
                    "iterations": iterations,
                    "tool_calls": tool_calls_made
                }
                self._emit("on_run_end", result=_llm_err_result)
                self._save_run_state()
                return _llm_err_result
            
            # Check if model wants to use tools
            if response.has_tool_calls():
                if self.config.verbose:
                    logger.info(f"🔧 Model requested {len(response.tool_calls)} tool call(s)")
                
                # Add assistant message with tool calls
                if self.use_memory_cache:
                    self.memory.add_agent_message(
                        content=response.content or "",
                        tool_calls=response.tool_calls, 
                        llm_response=response.raw_response
                    )
                elif self.chat is not None:
                    self.chat.add_agent_message(
                        content=response.content or "",
                        tool_calls=response.tool_calls
                    )
                    self._auto_save_chat_if_enabled()  # Auto-save after agent message with tool calls
                else:
                    self.messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": response.tool_calls
                    })
                
                # Execute each tool call with outer exception guard
                try:
                    for tool_call in response.tool_calls:
                        try:
                            tool_name = tool_call.get("function", {}).get("name")
                            tool_args_str = tool_call.get("function", {}).get("arguments", "{}")
                            
                            if not tool_name:
                                if self.config.verbose:
                                    logger.info(f"    ⚠️ Tool call missing name, skipping")
                                continue
                            
                            if self.config.verbose:
                                logger.info(f"  • Calling tool: {tool_name}")
                            
                            # Parse arguments
                            try:
                                # Check if arguments are already a dict
                                if isinstance(tool_args_str, dict):
                                    tool_args = tool_args_str
                                else:
                                    tool_args = parse_tool_call_arguments(tool_args_str)
                            except Exception as e:
                                tool_args = {}
                                if self.config.verbose:
                                    logger.warning("    ⚠️ Error parsing arguments: %s", e)
                            
                            # Execute tool
                            tool_result = self.execute_tool(tool_name, tool_args)
                            
                            if self.config.verbose:
                                if tool_result.get("success"):
                                    logger.info(f"    ✓ Tool executed successfully")
                                else:
                                    logger.info(f"    ✗ Tool execution failed: {tool_result.get('error')}")
                            
                            # Add tool result to messages
                            tool_result_content = self._format_tool_result(tool_result)
                            
                            # Calculate token count of tool result for context management
                            tool_result_tokens = max(1, len(tool_result_content) // 4)
                            
                            # Trim context if tool result would exceed context window
                            if self.chat is not None:
                                current_tokens = self.chat.get_token_count()
                                if current_tokens + tool_result_tokens > self.chat.max_input_tokens:
                                    logger.info(
                                        f"[{self.agent_id[:8]}] Tool result ({tool_result_tokens} tokens) would exceed "
                                        f"context ({current_tokens}/{self.chat.max_input_tokens}), trimming..."
                                    )
                                    self.chat.trim_messages_to_context(min_required=tool_result_tokens)
                            elif self.use_memory_cache and self.memory is not None:
                                current_tokens = self.memory.chat.get_token_count()
                                if current_tokens + tool_result_tokens > self.memory.config.max_tokens:
                                    logger.info(
                                        f"[{self.agent_id[:8]}] Tool result ({tool_result_tokens} tokens) would exceed "
                                        f"context ({current_tokens}/{self.memory.config.max_tokens}), trimming..."
                                    )
                                    self.memory.chat.trim_messages_to_context(min_required=tool_result_tokens)
                            
                            # Track tool call (BEFORE attempting to add message)
                            tool_calls_made.append({
                                "tool": tool_name,
                                "arguments": tool_args,
                                "result": tool_result,
                                "message_persisted": False  # Will update if successful
                            })
                            
                            # Try to add tool message with robust error handling
                            message_added = False
                            try:
                                if self.use_memory_cache:
                                    self.memory.add_tool_message(
                                        content=tool_result_content,
                                        tool_call_id=tool_call.get("id", ""),
                                        metadata={"name": tool_name} 
                                    )
                                    message_added = True
                                    logger.info(f"[{self.agent_id[:8]}] Tool message persisted to memory for '{tool_name}'")
                                    
                                elif self.chat is not None:
                                    self.chat.add_tool_message(
                                        content=tool_result_content,
                                        tool_call_id=tool_call.get("id", ""),
                                        metadata={"name": tool_name}  
                                    )
                                    message_added = True
                                    self._auto_save_chat_if_enabled()
                                    logger.info(f"[{self.agent_id[:8]}] Tool message persisted to chat for '{tool_name}'")
                                    
                                else:
                                    tool_message = {
                                        "role": "tool",
                                        "tool_call_id": tool_call.get("id", ""),
                                        "name": tool_name,
                                        "content": tool_result_content
                                    }
                                    self.messages.append(tool_message)
                                    message_added = True
                                    logger.info(f"[{self.agent_id[:8]}] Tool message added to message list for '{tool_name}'")

                            except Exception as msg_err:
                                logger.warning(
                                    f"[{self.agent_id[:8]}] ⚠️  Tool message persistence failed for '{tool_name}': {msg_err}. "
                                    f"Tool result may not be available to LLM for next iteration."
                                )
                                if self.config.verbose:
                                    logger.info(f"    ⚠️  WARNING: Tool message could not be persisted: {msg_err}")
                                message_added = False

                            # Update tracking with persistence status
                            tool_calls_made[-1]["message_persisted"] = message_added
                            if not message_added:
                                logger.error(
                                    f"[{self.agent_id[:8]}] ❌ CRITICAL: Tool message for '{tool_name}' NOT persisted! "
                                    f"Tool result will NOT reach LLM! Check chat/memory configuration."
                                )
                        
                        except Exception as e:
                            logger.error(f"[AGENT] Unexpected error processing tool call: {e}")
                            if self.config.verbose:
                                logger.info(f"    ✗ Error processing tool call: {e}")
                
                # Outer exception handler for entire tool execution loop
                except Exception as loop_err:
                    logger.error(f"[AGENT] Critical error in tool execution loop: {loop_err}")
                    # Attempt emergency save of chat state
                    try:
                        if self.use_memory_cache and self.memory:
                            self.memory.save()
                        elif self.chat is not None:
                            self._auto_save_chat_if_enabled()
                        logger.info("[AGENT] Emergency chat save completed after tool loop error")
                    except Exception as save_err:
                        logger.critical(
                            f"[AGENT] EMERGENCY SAVE FAILED after tool loop error — conversation state may be lost. "
                            f"Save error: {save_err}. Original error: {loop_err}"
                        )
                    
                    # Record the error in response
                    tool_execution_errors.append({
                        "error": str(loop_err),
                        "type": type(loop_err).__name__,
                        "stage": "tool_execution_loop"
                    })
                    if self.config.verbose:
                        logger.info(f"    ✗ CRITICAL ERROR in tool execution: {loop_err}")

                
                # Continue loop to get next response from model
                self._emit("on_iteration_end", iteration=iterations, response_text=response.content or "")
                continue
            
            else:
                # Model provided final response
                final_response = response.content
                
                # Add assistant message
                if self.use_memory_cache:
                    self.memory.add_agent_message(
                        content=final_response,
                        llm_response=response.raw_response
                    )
                elif self.chat is not None:
                    self.chat.add_agent_message(content=final_response)
                    self._auto_save_chat_if_enabled()  # Auto-save after final agent message
                else:
                    self.messages.append({
                        "role": "assistant",
                        "content": final_response
                    })
                
                if self.config.verbose:
                    logger.info(f"💬 Agent: {final_response}")
                
                # Add to history
                self.add_to_history({
                    "type": "agent_response",
                    "content": final_response,
                    "tool_calls": tool_calls_made,
                    "iterations": iterations
                })

                self._emit("on_iteration_end", iteration=iterations, response_text=final_response)
                break
        
        self.update_state(status="completed")
        
        if self.config.verbose:
            logger.info(f"\n{'='*60}")
            logger.info(f"Agent completed in {iterations} iteration(s)")
            logger.info(f"{'='*60}\n")
        
        logger.info(f"[{self.agent_id[:8]}] Agent run completed: iterations={iterations}, tool_calls={len(tool_calls_made)}, tokens={self.stats['total_tokens']}")
        
        # Get cache info for result
        cache_info = self.get_cache_info() if self.use_memory_cache else None
        
        result = {
            "success": True if not tool_execution_errors else False,
            "response": final_response,
            "iterations": iterations,
            "tool_calls": tool_calls_made,
            "tokens_used": self.stats["total_tokens"]
        }
        
        # Include execution errors if any occurred
        if tool_execution_errors:
            result["execution_errors"] = tool_execution_errors
            logger.warning(f"[{self.agent_id[:8]}] Agent completed with {len(tool_execution_errors)} execution error(s)")
        
        # Add cache info if available
        if cache_info:
            result["cache_info"] = cache_info
        
        # Auto-save chat if enabled
        if self.config.auto_save_chat and self.chat is not None:
            try:
                saved_path = self.save_chat()
                logger.info(f"[{self.agent_id[:8]}] Chat auto-saved to: {saved_path}")
            except Exception as e:
                logger.warning(f"[{self.agent_id[:8]}] Failed to auto-save chat: {e}")

        self._emit("on_run_end", result=result)
        self._save_run_state()
        return result
    
    @trace_yukta(kind=OpenInferenceSpanKindValues.CHAIN)
    def invoke(
        self,
        input: str,
        tool_name: Optional[str] = None,
        tool_arguments: Optional[Dict[str, Any]] = None,
        use_llm: bool = True,
        reset_conversation: bool = False,
        return_full_response: bool = False,
        llm_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Invoke the agent to process input and generate a response.
        
        This is a flexible method that can:
        1. Use the LLM to reason and call tools automatically (default mode)
        2. Execute a specific tool directly without LLM
        3. Generate a text response using LLM without tools
        
        Args:
            input: User input or task description
            tool_name: Optional tool name for direct tool execution (bypasses LLM)
            tool_arguments: Arguments for direct tool execution (used with tool_name)
            use_llm: Whether to use LLM for generation (default: True)
            reset_conversation: Whether to reset conversation history before invocation
            return_full_response: Whether to return full response dict or just the result/response
            
        Returns:
            Response from the agent. Format depends on mode:
            - LLM mode: String response or full dict (if return_full_response=True)
            - Direct tool mode: Tool execution result or full dict
            
        Examples:
            # LLM-based reasoning with automatic tool calling
            result = agent.invoke("What's the weather in New York?")
            
            # Direct tool execution
            result = agent.invoke(
                input="Get weather data",
                tool_name="get_weather",
                tool_arguments={"city": "New York"},
                use_llm=False
            )
            
            # Get full response with metadata
            result = agent.invoke(
                input="Analyze this data",
                return_full_response=True
            )
        """
        # Mode 1: Direct tool execution (no LLM)
        if tool_name is not None:
            if self.config.verbose:
                logger.info(f"🔧 Invoking tool directly: {tool_name}")
            
            tool_args = tool_arguments or {}
            tool_result = self.execute_tool(tool_name, tool_args)
            
            # Add to history
            self.add_to_history({
                "type": "direct_tool_call",
                "tool": tool_name,
                "arguments": tool_args,
                "result": tool_result,
                "input": input
            })
            
            if return_full_response:
                return {
                    "success": tool_result.get("success", False),
                    "result": tool_result.get("result"),
                    "error": tool_result.get("error"),
                    "tool": tool_name,
                    "mode": "direct_tool"
                }
            else:
                if tool_result.get("success"):
                    return tool_result.get("result")
                else:
                    error_msg = tool_result.get("error", "Tool execution failed")
                    if self.config.verbose:
                        logger.info(f"❌ Tool error: {error_msg}")
                    raise RuntimeError(f"Tool '{tool_name}' failed: {error_msg}")
        
        # Mode 2: LLM-based execution with automatic tool calling
        elif use_llm:
            if not self.llm_client:
                raise RuntimeError(
                    "No LLM client configured. Either set an LLM client using set_llm_client() "
                    "or specify tool_name and tool_arguments for direct tool execution."
                )
            
            if self.config.verbose:
                logger.info(f"🤖 Invoking agent with LLM: {self.agent_name}")
            
            result = self.run(
                user_message=input,
                reset_conversation=reset_conversation,
                llm_kwargs=llm_kwargs,
            )

            if return_full_response:
                result["mode"] = "llm_with_tools"
                return result
            else:
                # Return response if successful, error if failed
                if result.get("success"):
                    return result.get("response", "")
                else:
                    # Return error message if failed
                    return result.get("error", f"Agent failed after {result.get('iterations', 0)} iterations")
        
        # Mode 3: Simple text generation (LLM without tools)
        else:
            if not self.llm_client:
                raise RuntimeError("No LLM client configured for text generation.")
            
            if self.config.verbose:
                logger.info(f"💬 Generating response without tools")
            
            # Temporarily clear tools for this call
            original_tools = self.tools_processor._tools.copy()
            self.tools_processor._tools = {}
            
            try:
                result = self.run(
                    user_message=input,
                    reset_conversation=reset_conversation,
                    llm_kwargs=llm_kwargs,
                )

                if return_full_response:
                    result["mode"] = "llm_no_tools"
                    return result
                else:
                    return result.get("response", "")
            finally:
                # Restore original tools
                self.tools_processor._tools = original_tools
    
    def send_message(self, message: str) -> str:
        """
        Simple chat interface that returns just the response text.
        Renamed from 'chat' to avoid conflict with self.chat attribute.
        
        Args:
            message: User message
            
        Returns:
            Agent's text response
        """
        result = self.run(message, reset_conversation=False)
        return result.get("response", "")
    
    def clear_conversation(self) -> None:
        """Clear the conversation history (messages)."""
        if self.use_memory_cache and self.memory:
            self.memory.clear(keep_system=True)
        elif self.chat is not None:
            self.chat.clear_messages(keep_system=True)
        else:
            self.messages.clear()
        if self.config.verbose:
            logger.info("Conversation history cleared")
    
    def save_memory(self, force: bool = True) -> Optional[str]:
        """
        Save memory session to disk (if using memory cache).
        
        Args:
            force: Force save even if auto-save disabled
            
        Returns:
            Path to saved file or None
        """
        if self.use_memory_cache:
            logger.info(f"[{self.agent_id[:8]}] Saving memory session")
            path = self.memory.save(force=force)
            if self.config.verbose:
                logger.info(f"Memory saved to: {path}")
            return path
        return None
    
    def save_chat(self, storage_dir: Optional[str] = None) -> Optional[str]:
        """
        Save chat session to disk (if using chat).
        
        Args:
            storage_dir: Directory to save chat (uses default if not provided)
            
        Returns:
            Path to saved file or None
        """
        if self.chat is not None and self.chat_manager is not None:
            # Ensure chat is registered with manager
            self.chat_manager.chats[self.chat.chat_id] = self.chat
            # Save using manager
            logger.info(f"[{self.agent_id[:8]}] Saving chat session: {self.chat.get_message_count()} messages")
            path = self.chat_manager.save_chat(self.chat.chat_id)
            if self.config.verbose:
                logger.info(f"Chat saved to: {path}")
            return path
        return None
    
    def save_chat_history(self, chat_folder: str = "./chats") -> Optional[str]:
        """
        Save chat history with auto-generated filename based on first message.
        
        Chat files are organized in agent-specific subfolders:
        {chat_folder}/{agent_name}/{generated_filename}.json
        
        This method generates a meaningful filename from the agent's first user message
        and saves the complete chat history to a JSON file in an agent-specific subfolder.
        
        Args:
            chat_folder: Base directory for chats (default: ./chats)
                        Final path will be: {chat_folder}/{agent_name}/{filename}.json
            
        Returns:
            Path to saved chat file or None if no chat available
            
        Examples:
            # Save chat history to chats/{agent_name}/ folder
            saved_path = agent.save_chat_history()
            # Result: ./chats/TestAgent1/what_will_be_the_price_20260316_143022.json
            
            # Save to custom base folder
            saved_path = agent.save_chat_history(chat_folder="./chat_archives")
            # Result: ./chat_archives/TestAgent1/what_will_be_the_price_20260316_143022.json
        """
        if self.chat is not None and self.chat_manager is not None:
            try:
                # Ensure chat is registered with manager
                self.chat_manager.chats[self.chat.chat_id] = self.chat
                # Save with auto-generated filename based on first message
                # and agent-specific subfolder
                path = self.chat_manager.save_chat_with_generated_filename(
                    self.chat.chat_id, 
                    chat_folder=chat_folder,
                    agent_name=self.agent_name
                )
                return path
            except Exception as e:
                logger.error(f"[{self.agent_id[:8]}] Failed to save chat history: {e}")
                return None
        else:
            return None
    
    def _auto_save_chat_if_enabled(self) -> None:
        """
        Auto-save chat history if auto_save_chat_history is enabled.
        Called after each message is added.
        """
        if self.config.auto_save_chat_history and self.chat is not None:
            try:
                saved_path = self.save_chat_history(chat_folder=self.config.chat_history_dir)
                if saved_path and self.config.verbose:
                    logger.debug(f"[{self.agent_id[:8]}] Chat auto-saved: {saved_path}")
            except Exception as e:
                logger.warning(f"[{self.agent_id[:8]}] Failed to auto-save chat: {e}")
    
    def load_chat(self, chat_id: str, storage_dir: Optional[str] = None) -> bool:
        """
        Load chat session from disk.
        
        Args:
            chat_id: Chat ID to load
            storage_dir: Directory to load from (uses default if not provided)
            
        Returns:
            True if loaded successfully
        """
        
        if not self.chat_manager:
            self.chat_manager = ChatManager(storage_dir=storage_dir or "")
        elif storage_dir:
            self.chat_manager.storage_dir = Path(storage_dir)
        
        try:
            logger.info(f"[{self.agent_id[:8]}] Loading chat session: {chat_id}")
            loaded_chat = self.chat_manager.load_chat(chat_id)
            self.chat = loaded_chat
            # Update agent_id to match loaded chat
            self.agent_id = chat_id
            logger.info(f"[{self.agent_id[:8]}] Chat loaded successfully: {self.chat.get_message_count()} messages")
            if self.config.verbose:
                logger.info(f"Chat loaded: {chat_id} ({self.chat.get_message_count()} messages)")
            return True
        except Exception as e:
            logger.error(f"[{self.agent_id[:8]}] Failed to load chat: {e}")
            if self.config.verbose:
                logger.info(f"Failed to load chat: {e}")
            return False
    
    def get_memory_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get memory statistics (if using memory cache).
        
        Returns:
            Memory stats dictionary or None
        """
        if self.use_memory_cache:
            return self.memory.get_stats()
        return None
    
    def get_chat_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get chat statistics (if using chat).
        
        Returns:
            Chat stats dictionary or None
        """
        if self.chat is not None:
            return self.chat.get_stats()
        return None
    
    def get_message_count(self) -> int:
        """
        Get total message count.
        
        Returns:
            Number of messages in conversation
        """
        if self.use_memory_cache and self.memory:
            return len(self.memory.chat.messages)
        elif self.chat is not None:
            return self.chat.get_message_count()
        else:
            return len(self.messages)
    
    def get_token_count(self) -> int:
        """
        Get estimated token count.
        
        Returns:
            Total tokens in conversation
        """
        if self.use_memory_cache and self.memory:
            return self.memory.chat.get_token_count()
        elif self.chat is not None:
            return self.chat.get_token_count()
        else:
            # Estimate from messages list
            total = 0
            for msg in self.messages:
                total += len(msg.get("content", "")) // 4
            return total
    
    def __repr__(self) -> str:
        return f"Agent(name='{self.agent_name}', id='{self.agent_id}', tools={len(self.tools_processor)})"
    
    def __str__(self) -> str:
        return f"Agent: {self.agent_name}\nTools: {len(self.tools_processor)}\nStatus: {self.state['status']}"




def create_agent(
    name: str,
    system_prompt: Optional[SystemPrompt] = None,
    tools_processor: Optional[ToolProcessor] = None,
    config: Optional[AgentConfig] = None,
    agent_id: Optional[str] = None,
    llm_client: Optional['BaseLLMClient'] = None,
    memory: Optional['Memory'] = None,
    use_memory_cache: bool = False,
    callbacks: Optional[AgentCallbackHandler] = None,
    permission_level: str = "admin"
) -> Agent:
    """
    Quick helper function to create an agent with defaults.
    
    Args:
        name: Agent name
        system_prompt: Optional system prompt to use (creates default if not provided)
        tools_processor: Optional tool processor to use (creates empty if not provided)
        config: Optional agent configuration (uses defaults if not provided)
        agent_id: Optional custom agent ID
        llm_client: Optional LLM client for agent execution
        memory: Optional Memory instance for advanced memory management
        use_memory_cache: Whether to use Memory class for KV cache tracking
        
    Returns:
        Configured Agent instance
    """
    # Create defaults if not provided
    if system_prompt is None:
        system_prompt = SystemPrompt("default", f"You are {name}, a helpful AI assistant.")
    
    if tools_processor is None:
        tools_processor = ToolProcessor()
    
    return Agent(
        agent_name=name,
        system_prompt=system_prompt,
        tools_processor=tools_processor,
        config=config,
        agent_id=agent_id,
        llm_client=llm_client,
        memory=memory,
        use_memory_cache=use_memory_cache,
        callbacks=callbacks,
        permission_level=permission_level
    )
