"""
Remote MCP Tool Module
Handles remote tool execution via HTTP endpoints (Model Context Protocol compliant).
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import httpx
import asyncio
import sys

from .tool import Tool, ToolType, ToolParameter

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@dataclass
class RemoteMCPTool(Tool):
    """
    Represents a tool hosted on a remote MCP server.
    
    This tool type communicates with remote servers via HTTP/REST endpoints.
    The server is responsible for tool execution and returning results.
    
    Attributes:
        name: Tool name/identifier
        description: What the tool does
        parameters: List of tool parameters
        endpoint: URL of the MCP server tool endpoint (e.g., http://localhost:8080/mcp/tools/search)
        method: HTTP method to use (default: POST)
        timeout: Request timeout in seconds (default: 15.0)
        metadata: Additional metadata about the tool
    """
    
    endpoint: str = ""
    method: str = "POST"
    timeout: float = 15.0
    ssl_verify: bool = True

    def __post_init__(self):
        """Initialize RemoteMCPTool, ensuring tool_type is set correctly."""
        if not self.endpoint:
            raise ValueError("RemoteMCPTool requires 'endpoint' URL")
        
        # Ensure tool_type is set to REMOTE_MCP
        self.tool_type = ToolType.REMOTE_MCP
        
        # Store remote-specific metadata
        if not self.metadata:
            self.metadata = {}
        self.metadata.update({
            "endpoint": self.endpoint,
            "method": self.method,
            "timeout": self.timeout,
            "ssl_verify": self.ssl_verify,
        })
    
    async def execute_async(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the remote tool asynchronously.
        
        Args:
            args: Tool arguments to send to the remote endpoint
            
        Returns:
            Dictionary with tool execution result or error
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=self.ssl_verify) as client:
                if self.method.upper() == "POST":
                    response = await client.post(
                        self.endpoint,
                        json=args
                    )
                elif self.method.upper() == "GET":
                    response = await client.get(
                        self.endpoint,
                        params=args
                    )
                elif self.method.upper() == "PUT":
                    response = await client.put(
                        self.endpoint,
                        json=args
                    )
                elif self.method.upper() == "PATCH":
                    response = await client.patch(
                        self.endpoint,
                        json=args
                    )
                else:
                    return {"error": f"Unsupported HTTP method: {self.method}"}
                
                response.raise_for_status()
                return response.json()
                
        except asyncio.TimeoutError:
            return {"error": f"Request timed out after {self.timeout}s", "tool": self.name}
        except httpx.HTTPError as e:
            return {"error": f"HTTP Error: {str(e)}", "tool": self.name, "status_code": getattr(e.response, "status_code", None)}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {str(e)}", "tool": self.name}
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the remote tool synchronously (wrapper around async execution).
        
        Args:
            args: Tool arguments to send to the remote endpoint
            
        Returns:
            Dictionary with tool execution result or error
        """
        return asyncio.run(self.execute_async(args))
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert tool to dictionary format for LLM consumption.
        
        Returns:
            Dictionary representation of the tool
        """
        tool_dict = super().to_dict()
        # Add remote-specific metadata to output
        tool_dict["metadata"]["endpoint"] = self.endpoint
        tool_dict["metadata"]["method"] = self.method
        return tool_dict


def create_remote_mcp_tool(
    name: str,
    description: str,
    endpoint: str,
    parameters: Optional[List[Dict[str, Any]]] = None,
    method: str = "POST",
    timeout: float = 15.0
) -> RemoteMCPTool:
    """
    Helper function to create a Remote MCP tool.
    
    Args:
        name: Tool name
        description: Tool description
        endpoint: URL of the remote MCP endpoint
        parameters: Optional list of parameter dictionaries
        method: HTTP method (default: POST)
        timeout: Request timeout in seconds (default: 15.0)
        
    Returns:
        RemoteMCPTool instance
        
    Example:
        tool = create_remote_mcp_tool(
            name="search_docs",
            description="Search documentation using MCP",
            endpoint="http://localhost:8080/mcp/tools/search",
            parameters=[
                {"name": "query", "type": "string", "description": "Search query", "required": True}
            ]
        )
    """
    if parameters is None:
        parameters = []
    
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
    
    return RemoteMCPTool(
        name=name,
        description=description,
        parameters=tool_params,
        endpoint=endpoint,
        method=method,
        timeout=timeout
    )
