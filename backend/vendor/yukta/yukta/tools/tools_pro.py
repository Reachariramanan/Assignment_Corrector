"""
Tools Processing Module
Handles MCP (Model Context Protocol) tools processing and formatting.
Includes parallel execution support for concurrent tool calls.
"""

from typing import List, Dict, Any, Optional, Callable, Tuple
import json
import asyncio
import sys
import httpx
import logging
import time
from concurrent.futures import ThreadPoolExecutor

# Import Tool classes from tool.py
from .tool import Tool, ToolType, ToolParameter

# Configure logging
logger = logging.getLogger(__name__)

# Lazy imports for optional dependencies
_mcp_available = False
_openinference_available = False

try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    _mcp_available = True
except ImportError:
    logger.debug("MCP not available - some features disabled")

try:
    from openinference.semconv.trace import OpenInferenceSpanKindValues
    _openinference_available = True
except ImportError:
    logger.debug("OpenInference not available - tracing disabled")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class ToolProcessor:
    """
    Processes and manages tools for agent use.
    Handles MCP tools formatting and custom tool registration.
    Supports parallel execution of multiple tool calls.
    
    Attributes:
        parallel: Enable parallel execution mode
        num_parallel: Number of concurrent workers (capped at number of tools)
        timeout_per_tool: Timeout in seconds per tool execution
    """
    
    def __init__(
        self,
        parallel: bool = False,
        num_parallel: int = 3,
        timeout_per_tool: float = 30.0
    ):
        """
        Initialize the tool processor.
        
        Args:
            parallel: Enable parallel execution (default: False for backward compatibility)
            num_parallel: Number of concurrent workers (default: 3)
            timeout_per_tool: Timeout per tool in seconds (default: 30)
        """
        self._tools: Dict[str, Tool] = {}
        self._tool_groups: Dict[str, List[str]] = {}
        
        # Parallel execution configuration
        self.parallel = parallel
        self.num_parallel = max(1, num_parallel)  # Ensure at least 1
        self.timeout_per_tool = timeout_per_tool
        
        # Execution statistics
        self._execution_stats = {
            "total_parallel_calls": 0,
            "total_sequential_calls": 0,
            "total_tools_executed": 0,
            "total_tools_failed": 0,
            "total_execution_time": 0.0,
            "estimated_sequential_time": 0.0,
            "last_speedup": 1.0,
            "execution_history": []
        }
        
        logger.info(f"ToolProcessor initialized: parallel={parallel}, num_workers={num_parallel}, timeout={timeout_per_tool}s")
    
    def add_tool(self, tool: Tool) -> None:
        """
        Add a tool to the processor.
        
        Args:
            tool: Tool instance to add
        """
        self._tools[tool.name] = tool
    
    def remove_tool(self, tool_name: str) -> bool:
        """
        Remove a tool from the processor.
        
        Args:
            tool_name: Name of the tool to remove
            
        Returns:
            True if removed, False if not found
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            return True
        return False
    
    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """
        Get a tool by name.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(tool_name)
    
    def list_tools(self, tool_type: Optional[ToolType] = None) -> List[str]:
        """
        List all available tools, optionally filtered by type.
        
        Args:
            tool_type: Optional filter by tool type
            
        Returns:
            List of tool names
        """
        if tool_type is None:
            return list(self._tools.keys())
        return [
            name for name, tool in self._tools.items() 
            if tool.tool_type == tool_type
        ]
    
    def create_tool_group(self, group_name: str, tool_names: List[str]) -> None:
        """
        Create a named group of tools.
        
        Args:
            group_name: Name for the tool group
            tool_names: List of tool names to include
        """
        self._tool_groups[group_name] = tool_names
    
    def get_tool_group(self, group_name: str) -> List[Tool]:
        """
        Get all tools in a named group.
        
        Args:
            group_name: Name of the tool group
            
        Returns:
            List of Tool instances
        """
        tool_names = self._tool_groups.get(group_name, [])
        return [self._tools[name] for name in tool_names if name in self._tools]
    

    def parse_mcp_tool(self, mcp_tool_data: Dict[str, Any], host: str) -> Tool:
        """
        Parse MCP tool data into a Tool instance.
        
        Args:
            mcp_tool_data: MCP tool data in dictionary format
            host: Host URL for the MCP tool
            
        Returns:
            Tool instance
        """
        name = mcp_tool_data.get("name", "")
        description = mcp_tool_data.get("description", "")
        tool_type=ToolType.MCP
        
        # Parse parameters
        parameters = []
        input_schema = mcp_tool_data.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        for param_name, param_info in properties.items():
            param = ToolParameter(
                name=param_name,
                type=param_info.get("type", "string"),
                description=param_info.get("description", ""),
                required=param_name in required,
                default=param_info.get("default"),
                enum=param_info.get("enum")
            )
            parameters.append(param)
        
        
        return Tool(
            name=name,
            description=description,
            parameters=parameters,
            tool_type=ToolType.MCP,
            metadata={"original_schema": mcp_tool_data, "host": host,"tool_type": tool_type.value}
        )
    
    def load_mcp_tools(self, mcp_tools: List[Dict[str, Any]], host: str) -> int:
        """
        Load multiple MCP tools at once.
        
        Args:
            mcp_tools: List of MCP tool data dictionaries
            host: Host URL for the MCP tools
            
        Returns:
            Number of tools successfully loaded
        """
        count = 0
        for tool_data in mcp_tools:
            try:
                tool = self.parse_mcp_tool(tool_data, host)
                self.add_tool(tool)
                count += 1
            except Exception as e:
                logger.error("Error loading tool %s: %s", tool_data.get('name', 'unknown'), e)
        return count
    

    def format_for_llm(self, tool_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Format tools for LLM consumption.
        
        Args:
            tool_names: Optional list of specific tools to format. If None, formats all.
            
        Returns:
            List of formatted tool dictionaries
        """
        if tool_names is None:
            tools_to_format = self._tools.values()
        else:
            tools_to_format = [self._tools[name] for name in tool_names if name in self._tools]
        
        return [tool.to_dict() for tool in tools_to_format]
    
    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool by name with the given arguments.
        
        This method handles all tool types uniformly from the agent's perspective:
        - CUSTOM tools: Calls the registered function
        - BUILTIN tools: Calls the registered function
        - REMOTE_MCP tools: Calls the remote endpoint
        
        Args:
            tool_name: Name of the tool to execute
            args: Dictionary of arguments to pass to the tool
            
        Returns:
            Dictionary with tool execution result or error
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found"}

        # Validate arguments (required params + type checking)
        is_valid, error_msg = tool.validate_args(args)
        if not is_valid:
            return {"error": error_msg, "tool": tool_name}

        _t0 = time.time()
        result: Dict[str, Any] = {}
        try:
            if tool.tool_type == ToolType.REMOTE_MCP:
                from .mcp_tool import RemoteMCPTool
                if isinstance(tool, RemoteMCPTool):
                    result = tool.execute(args)
                else:
                    result = {"error": f"Tool '{tool_name}' is marked as REMOTE_MCP but not a RemoteMCPTool instance", "tool": tool_name}

            elif tool.tool_type in (ToolType.CUSTOM, ToolType.BUILTIN):
                if tool.function is None:
                    result = {"error": f"Tool '{tool_name}' has no function registered", "tool": tool_name}
                elif getattr(tool, "trust_level", "trusted") == "sandbox":
                    from .sandbox import ToolSandbox
                    result = ToolSandbox().execute_callable(tool.function, args)
                else:
                    raw = tool.function(**args)
                    result = raw if isinstance(raw, dict) else {"result": raw}

            else:
                result = {"error": f"Unknown tool type: {tool.tool_type}", "tool": tool_name}

        except Exception as e:
            result = {"error": f"Tool execution failed: {type(e).__name__}: {str(e)}", "tool": tool_name}

        # Structured audit log — arg keys only (values may contain secrets)
        logger.info(
            "tool_exec tool=%s type=%s trust=%s success=%s duration_ms=%.1f args=%s",
            tool_name,
            tool.tool_type.value,
            getattr(tool, "trust_level", "trusted"),
            "error" not in result,
            (time.time() - _t0) * 1000,
            list(args.keys()),
        )
        return result
    
    async def execute_tool_async(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool asynchronously by name with the given arguments.
        
        Args:
            tool_name: Name of the tool to execute
            args: Dictionary of arguments to pass to the tool
            
        Returns:
            Dictionary with tool execution result or error
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found"}
        
        # Validate arguments
        is_valid, error_msg = tool.validate_args(args)
        if not is_valid:
            return {"error": error_msg, "tool": tool_name}
        
        try:
            if tool.tool_type == ToolType.REMOTE_MCP:
                # Import here to avoid circular imports
                from .mcp_tool import RemoteMCPTool
                
                if isinstance(tool, RemoteMCPTool):
                    return await tool.execute_async(args)
                else:
                    return {"error": f"Tool '{tool_name}' is marked as REMOTE_MCP but not a RemoteMCPTool instance", "tool": tool_name}
            
            elif tool.tool_type in (ToolType.CUSTOM, ToolType.BUILTIN):
                if tool.function is None:
                    return {"error": f"Tool '{tool_name}' has no function registered", "tool": tool_name}
                
                # Execute the function with unpacked arguments
                # If the function is async, await it
                result = tool.function(**args)
                if asyncio.iscoroutine(result):
                    result = await result
                return result if isinstance(result, dict) else {"result": result}
            
            else:
                return {"error": f"Unknown tool type: {tool.tool_type}", "tool": tool_name}
        
        except Exception as e:
            return {"error": f"Tool execution failed: {type(e).__name__}: {str(e)}", "tool": tool_name}
    
    async def execute_mcp_tool(self, tool_name: str, server_url: str, args: dict) -> Dict[str, Any]:
        """
        Execute an MCP tool asynchronously via HTTP endpoint
        
        Args:
            tool_name: Name of the tool to execute
            server_url: URL of the MCP server (e.g., http://localhost:8000)
            args: Arguments to pass to the tool
            
        Returns:
            Dictionary with tool execution result or error
        """
        try:
            # Construct the tool endpoint URL
            tool_endpoint = f"{server_url}/tools/{tool_name}"
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Make HTTP POST request to the MCP server tool endpoint
                response = await client.post(
                    tool_endpoint,
                    json=args,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()
                
        except asyncio.TimeoutError:
            return {"network_error": "Connection timed out after 15s"}
        except httpx.HTTPError as e:
            return {"network_error": f"HTTP Error: {e}"}
        except Exception as e:
            return {"network_error": f"{type(e).__name__}: {str(e)}"}
    
    def execute_mcp_tool_sync(self, tool_name: str, args: dict, use_sse: bool = False) -> Dict[str, Any]:
        """
        Execute an MCP tool synchronously (wrapper around async execution)
        
        Args:
            tool_name: Name of the tool to execute
            args: Arguments to pass to the tool
            use_sse: Whether to use SSE connection (default: False for HTTP)
            
        Returns:
            Dictionary with tool execution result or error
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found in registry"}
        
        tool_host = tool.metadata.get("host")
        if not tool_host:
            return {"error": f"Host URL not configured for tool '{tool_name}'"}
        
        if use_sse:
            # For SSE endpoint, append /sse to the base URL
            sse_url = f"{tool_host}/sse"
            return asyncio.run(self.execute_mcp_tool_sse(tool_name, sse_url, args))
        else:
            # For regular HTTP endpoint
            return asyncio.run(self.execute_mcp_tool(tool_name, tool_host, args))
        

    # ==================== PARALLEL EXECUTION METHODS ====================
    
    def execute_tools(
        self,
        tool_calls: List[Dict[str, Any]],
        force_parallel: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple tool calls from LLM.
        Automatically routes to sequential or parallel execution based on configuration.
        
        Args:
            tool_calls: List of tool call dicts from LLM with format:
                       {"function": {"name": "tool_name", "arguments": "json_string"}, "id": "..."}
            force_parallel: Override parallel setting for this call only
            
        Returns:
            List of result dicts in same order as input tool_calls.
            Each result has format: {"success": bool, "result": ..., "tool": "name", ...} or error dict
        """
        # Handle empty list
        if not tool_calls:
            return []
        
        # Single tool: no parallelization benefit
        if len(tool_calls) == 1:
            return self._execute_tools_sequential(tool_calls)
        
        # Determine execution mode
        use_parallel = force_parallel if force_parallel is not None else self.parallel
        
        if use_parallel:
            logger.debug(f"Executing {len(tool_calls)} tools in parallel mode (workers: {self.num_parallel})")
            return self._execute_tools_parallel(tool_calls)
        else:
            logger.debug(f"Executing {len(tool_calls)} tools in sequential mode")
            return self._execute_tools_sequential(tool_calls)
    
    def _execute_tools_sequential(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute tool calls sequentially (one after another).
        This is the default mode for backward compatibility.
        
        Args:
            tool_calls: List of tool call dicts
            
        Returns:
            List of result dicts
        """
        results = []
        start_time = time.time()
        total_sequential_time = 0.0
        
        for i, tool_call in enumerate(tool_calls):
            try:
                tool_tool_time = time.time()
                tool_name = tool_call.get("function", {}).get("name")
                tool_args_str = tool_call.get("function", {}).get("arguments", "{}")
                tool_call_id = tool_call.get("id", f"call_{i}")
                
                if not tool_name:
                    results.append({
                        "error": "Tool call missing function name",
                        "tool_call_id": tool_call_id,
                        "index": i
                    })
                    continue
                
                # Parse arguments
                try:
                    if isinstance(tool_args_str, dict):
                        tool_args = tool_args_str
                    else:
                        tool_args = json.loads(tool_args_str)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Failed to parse tool args for '%s', falling back to empty args. Raw: %r", tool_name, tool_args_str)
                    tool_args = {}

                # Execute tool
                result = self.execute_tool(tool_name, tool_args)
                result["tool_call_id"] = tool_call_id
                result["index"] = i
                results.append(result)
                
                tool_duration = time.time() - tool_tool_time
                total_sequential_time += tool_duration
                
            except Exception as e:
                results.append({
                    "error": f"Failed to process tool call: {str(e)}",
                    "tool_call_id": tool_call.get("id", f"call_{i}"),
                    "index": i
                })
        
        # Update statistics
        elapsed = time.time() - start_time
        self._execution_stats["total_sequential_calls"] += 1
        self._execution_stats["total_tools_executed"] += len([r for r in results if "result" in r])
        self._execution_stats["total_tools_failed"] += len([r for r in results if "error" in r])
        self._execution_stats["total_execution_time"] += elapsed
        self._execution_stats["estimated_sequential_time"] += total_sequential_time
        
        logger.debug(f"Sequential execution: {len(results)} tools in {elapsed:.3f}s")
        return results
    
    async def _execute_tool_safe_async(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        tool_call_id: str,
        index: int
    ) -> Dict[str, Any]:
        """
        Safely execute a single tool asynchronously with timeout and exception handling.
        
        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments for the tool
            tool_call_id: ID from LLM tool call
            index: Index in original tool_calls list
            
        Returns:
            Result dict with tool_call_id and index preserved
        """
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self.execute_tool_async(tool_name, tool_args),
                timeout=self.timeout_per_tool
            )
            result["tool_call_id"] = tool_call_id
            result["index"] = index
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"Tool '{tool_name}' timed out after {self.timeout_per_tool}s")
            return {
                "error": f"Tool execution timed out after {self.timeout_per_tool}s",
                "tool": tool_name,
                "tool_call_id": tool_call_id,
                "index": index
            }
        except Exception as e:
            logger.error(f"Tool '{tool_name}' failed: {type(e).__name__}: {str(e)}")
            return {
                "error": f"Tool execution failed: {type(e).__name__}: {str(e)}",
                "tool": tool_name,
                "tool_call_id": tool_call_id,
                "index": index
            }
    
    def _execute_tools_parallel(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute multiple tool calls concurrently using asyncio.
        Uses asyncio.gather() with fail-safe error handling (continues on partial failures).
        
        Args:
            tool_calls: List of tool call dicts
            
        Returns:
            List of result dicts in same order as input
        """
        start_time = time.time()
        
        # Cap workers at number of tools
        num_workers = min(self.num_parallel, len(tool_calls))
        
        # Prepare async tasks
        tasks = []
        task_indices = []  # Track which tool_call each task corresponds to
        
        for i, tool_call in enumerate(tool_calls):
            try:
                tool_name = tool_call.get("function", {}).get("name")
                tool_args_str = tool_call.get("function", {}).get("arguments", "{}")
                tool_call_id = tool_call.get("id", f"call_{i}")
                
                if not tool_name:
                    # Add error result synchronously for missing tool name
                    tasks.append(None)
                    task_indices.append(i)
                    continue
                
                # Parse arguments
                try:
                    if isinstance(tool_args_str, dict):
                        tool_args = tool_args_str
                    else:
                        tool_args = json.loads(tool_args_str)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Failed to parse tool args for '%s', falling back to empty args. Raw: %r", tool_name, tool_args_str)
                    tool_args = {}

                # Create async task
                task = self._execute_tool_safe_async(tool_name, tool_args, tool_call_id, i)
                tasks.append(task)
                task_indices.append(i)
                
            except Exception as e:
                logger.error(f"Failed to prepare tool call {i}: {str(e)}")
                tasks.append(None)
                task_indices.append(i)
        
        # Execute all tasks concurrently with fail-safe handling
        async def gather_tasks():
            return await asyncio.gather(
                *[t for t in tasks if t is not None],
                return_exceptions=True
            )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already inside an async context (e.g., Jupyter, FastAPI); create a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(asyncio.run, gather_tasks())
                    async_results = future.result()
            else:
                async_results = loop.run_until_complete(gather_tasks())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                async_results = loop.run_until_complete(gather_tasks())
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Parallel execution failed: {str(e)}")
            async_results = []
        
        # Merge results back in original order
        results = []
        async_result_idx = 0
        
        for i, task in enumerate(tasks):
            if task is None:
                # This was an error during preparation
                tool_call = tool_calls[i]
                results.append({
                    "error": "Tool call missing function name",
                    "tool_call_id": tool_call.get("id", f"call_{i}"),
                    "index": i
                })
            else:
                # Get result from async execution
                async_result = async_results[async_result_idx] if async_result_idx < len(async_results) else None
                async_result_idx += 1
                
                # Check if result is an exception
                if isinstance(async_result, Exception):
                    tool_call = tool_calls[i]
                    results.append({
                        "error": f"Async execution error: {str(async_result)}",
                        "tool_call_id": tool_call.get("id", f"call_{i}"),
                        "index": i
                    })
                else:
                    results.append(async_result)
        
        # Update statistics
        elapsed = time.time() - start_time
        sequential_estimate = sum(self.timeout_per_tool for _ in tool_calls) * 0.5  # Rough estimate
        speedup = sequential_estimate / elapsed if elapsed > 0 else 1.0
        
        self._execution_stats["total_parallel_calls"] += 1
        self._execution_stats["total_tools_executed"] += len([r for r in results if "result" in r])
        self._execution_stats["total_tools_failed"] += len([r for r in results if "error" in r])
        self._execution_stats["total_execution_time"] += elapsed
        self._execution_stats["estimated_sequential_time"] += sequential_estimate
        self._execution_stats["last_speedup"] = speedup
        
        logger.debug(f"Parallel execution: {len(results)} tools in {elapsed:.3f}s ({num_workers} workers, {speedup:.1f}x speedup)")
        
        return results
    
    # ==================== CONFIGURATION METHODS ====================
    
    def set_parallel_mode(self, parallel: bool, num_parallel: int = 3) -> None:
        """
        Configure parallel execution mode.
        
        Args:
            parallel: Enable/disable parallel execution
            num_parallel: Number of concurrent workers
        """
        self.parallel = parallel
        self.num_parallel = max(1, num_parallel)
        logger.info(f"Parallel mode set: enabled={parallel}, workers={self.num_parallel}")
    
    def enable_parallel(self, num_workers: int = 3) -> None:
        """
        Enable parallel execution mode.
        
        Args:
            num_workers: Number of concurrent workers (default: 3)
        """
        self.set_parallel_mode(True, num_workers)
    
    def disable_parallel(self) -> None:
        """Disable parallel execution mode (switch to sequential)."""
        self.set_parallel_mode(False)
    
    def set_timeout(self, timeout_seconds: float) -> None:
        """
        Set timeout per tool execution.
        
        Args:
            timeout_seconds: Timeout in seconds (default: 30)
        """
        self.timeout_per_tool = max(0.1, timeout_seconds)
        logger.info(f"Tool timeout set to {self.timeout_per_tool}s")
    
    def get_parallel_execution_stats(self) -> Dict[str, Any]:
        """
        Get parallel execution statistics and metrics.
        
        Returns:
            Dictionary with execution statistics including:
            - total_parallel_calls: Number of parallel batches executed
            - total_sequential_calls: Number of sequential batches executed
            - total_tools_executed: Total tools executed successfully
            - total_tools_failed: Total tools that failed
            - total_execution_time: Total time spent executing
            - estimated_sequential_time: Estimated sequential time for comparison
            - last_speedup: Speedup factor from most recent parallel execution
        """
        return {
            **self._execution_stats,
            "parallel_enabled": self.parallel,
            "current_workers": self.num_parallel,
            "timeout_per_tool": self.timeout_per_tool,
            "average_speedup": (
                self._execution_stats["estimated_sequential_time"] / self._execution_stats["total_execution_time"]
                if self._execution_stats["total_execution_time"] > 0 else 0.0
            )
        }
    
    def reset_stats(self) -> None:
        """Reset execution statistics to zero."""
        self._execution_stats = {
            "total_parallel_calls": 0,
            "total_sequential_calls": 0,
            "total_tools_executed": 0,
            "total_tools_failed": 0,
            "total_execution_time": 0.0,
            "estimated_sequential_time": 0.0,
            "last_speedup": 1.0,
            "execution_history": []
        }
        logger.info("Execution statistics reset")
    
    # ==================== END PARALLEL EXECUTION METHODS ====================

    def export_tools_json(self, filepath: str, tool_names: Optional[List[str]] = None) -> None:
        """
        Export tools to a JSON file.
        
        Args:
            filepath: Path to save JSON file
            tool_names: Optional list of specific tools to export
        """
        formatted_tools = self.format_for_llm(tool_names)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(formatted_tools, f, indent=2)
    

    def import_tools_json(self, filepath: str) -> int:
        """
        Import tools from a JSON file.
        
        Args:
            filepath: Path to JSON file
            
        Returns:
            Number of tools imported
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            tools_data = json.load(f)

        if not isinstance(tools_data, list):
            raise ValueError("Invalid tools JSON format: expected a list of tool definitions")
        
        return self.load_mcp_tools(tools_data, host="")
    
    def get_tool_info(self) -> Dict[str, Any]:
        """
        Get information about all loaded tools.
        
        Returns:
            Dictionary with tool statistics and information
        """
        return {
            "total_tools": len(self._tools),
            "by_type": {
                tool_type.value: len(self.list_tools(tool_type))
                for tool_type in ToolType
            },
            "tool_groups": list(self._tool_groups.keys()),
            "tools": list(self._tools.keys())
        }
    
    def __len__(self) -> int:
        """Return the number of tools."""
        return len(self._tools)
    
    def __repr__(self) -> str:
        return f"ToolProcessor(tools={len(self._tools)})"


def create_custom_tool(
    name: str,
    description: str,
    parameters: List[Dict[str, Any]],
    function: Optional[Callable] = None
) -> Tool:
    """
    Helper function to create a custom tool.
    
    Args:
        name: Tool name
        description: Tool description
        parameters: List of parameter dictionaries with keys:
                   - name (str): Parameter name
                   - type (str): Parameter type (string, number, integer, boolean, object, array)
                   - description (str): Parameter description
                   - required (bool, optional): Whether parameter is required (default: False)
                   - default (Any, optional): Default value if not required
                   - enum (List[Any], optional): List of allowed values
        function: Optional function to execute when tool is called
        
    Returns:
        Tool instance
        
    Example:
        tool = create_custom_tool(
            name="calculator",
            description="Perform basic arithmetic",
            parameters=[
                {"name": "a", "type": "number", "description": "First number", "required": True},
                {"name": "b", "type": "number", "description": "Second number", "required": True}
            ],
            function=lambda a, b: {"result": a + b}
        )
    """
    tool_params = []
    for param in parameters:
        tool_params.append(ToolParameter(
            name=param["name"],
            type=param.get("type", "string"),
            description=param.get("description", ""),
            required=param.get("required", False),
            default=param.get("default"),
            enum=param.get("enum")
        ))
    
    return Tool(
        name=name,
        description=description,
        parameters=tool_params,
        tool_type=ToolType.CUSTOM,
        function=function
    )
