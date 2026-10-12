"""
Example: Using Remote MCP Tools with Yukta Agents
==================================================

This example demonstrates how to add and execute Remote MCP tools
in a Yukta agent. Remote MCP tools allow agents to execute tools
hosted on remote servers via HTTP/REST endpoints.
"""

from yukta.tools.mcp_tool import RemoteMCPTool, create_remote_mcp_tool
from yukta.tools.tools_pro import ToolProcessor
from yukta.tools import Tool, ToolType, ToolParameter


# ============================================================================
# EXAMPLE 1: Creating a RemoteMCPTool directly
# ============================================================================

def example_1_direct_creation():
    """
    Create a Remote MCP tool by directly instantiating RemoteMCPTool.
    """
    
    # Create a tool that searches documentation
    search_tool = RemoteMCPTool(
        name="search_docs",
        description="Search documentation using MCP protocol",
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="Search query",
                required=True
            ),
            ToolParameter(
                name="max_results",
                type="integer",
                description="Maximum number of results to return",
                required=False,
                default=10
            )
        ],
        endpoint="http://localhost:8080/mcp/tools/search",
        method="POST",
        timeout=15.0
    )
    
    return search_tool


# ============================================================================
# EXAMPLE 2: Using the helper function (Recommended)
# ============================================================================

def example_2_using_helper():
    """
    Create a Remote MCP tool using the helper function.
    This is the recommended approach.
    """
    
    search_tool = create_remote_mcp_tool(
        name="search_docs",
        description="Search documentation using MCP protocol",
        endpoint="http://localhost:8080/mcp/tools/search",
        parameters=[
            {
                "name": "query",
                "type": "string",
                "description": "Search query",
                "required": True
            },
            {
                "name": "max_results",
                "type": "integer",
                "description": "Maximum number of results",
                "required": False,
                "default": 10
            }
        ]
    )
    
    return search_tool


# ============================================================================
# EXAMPLE 3: Adding Remote MCP Tools to ToolProcessor
# ============================================================================

def example_3_tool_processor():
    """
    Add Remote MCP tools to a ToolProcessor and use them.
    """
    
    # Create tool processor
    tools_processor = ToolProcessor()
    
    # Create multiple Remote MCP tools
    search_tool = create_remote_mcp_tool(
        name="search_docs",
        description="Search documentation",
        endpoint="http://localhost:8080/mcp/tools/search",
        parameters=[
            {"name": "query", "type": "string", "description": "Search query", "required": True}
        ]
    )
    
    calculate_tool = create_remote_mcp_tool(
        name="calculate",
        description="Perform calculations on a remote service",
        endpoint="http://localhost:9000/mcp/tools/calc",
        parameters=[
            {"name": "expression", "type": "string", "description": "Math expression", "required": True}
        ]
    )
    
    # Add tools to processor
    tools_processor.add_tool(search_tool)
    tools_processor.add_tool(calculate_tool)
    
    # List all tools
    all_tools = tools_processor.list_tools()
    print(f"Available tools: {all_tools}")
    
    # Get tools by type
    remote_tools = tools_processor.list_tools(ToolType.REMOTE_MCP)
    print(f"Remote MCP tools: {remote_tools}")
    
    return tools_processor


# ============================================================================
# EXAMPLE 4: Executing Remote MCP Tools
# ============================================================================

def example_4_execute_tool():
    """
    Execute a Remote MCP tool using ToolProcessor.
    """
    
    # Create and setup tools
    tools_processor = ToolProcessor()
    
    search_tool = create_remote_mcp_tool(
        name="search_docs",
        description="Search documentation",
        endpoint="http://localhost:8080/mcp/tools/search",
        parameters=[
            {"name": "query", "type": "string", "description": "Search query", "required": True},
            {"name": "max_results", "type": "integer", "description": "Max results", "required": False}
        ]
    )
    
    tools_processor.add_tool(search_tool)
    
    # Execute the tool
    result = tools_processor.execute_tool(
        tool_name="search_docs",
        args={
            "query": "memory caching",
            "max_results": 5
        }
    )
    
    print(f"Search result: {result}")
    
    return result


# ============================================================================
# EXAMPLE 5: Using Remote MCP Tools with Agent
# ============================================================================

def example_5_agent_integration():
    """
    Integrate Remote MCP tools with a Yukta agent.
    """
    from yukta.core.Agent.agent import Agent
    from yukta.config.system_prompt import SystemPrompt
    from yukta.config.agent_config import AgentConfig
    
    # Create tool processor with remote MCP tools
    tools_processor = ToolProcessor()
    
    search_tool = create_remote_mcp_tool(
        name="search_docs",
        description="Search documentation for information",
        endpoint="http://localhost:8080/mcp/tools/search_docs",
        parameters=[
            {"name": "query", "type": "string", "description": "Search query", "required": True}
        ]
    )
    
    retrieve_tool = create_remote_mcp_tool(
        name="retrieve_content",
        description="Retrieve the full content of a document",
        endpoint="http://localhost:8080/mcp/tools/get_doc",
        parameters=[
            {"name": "doc_id", "type": "string", "description": "Document ID", "required": True}
        ]
    )
    
    tools_processor.add_tool(search_tool)
    tools_processor.add_tool(retrieve_tool)
    
    # Create system prompt
    system_prompt = SystemPrompt(
        role="Documentation Assistant",
        goals="Help users find and retrieve documentation efficiently",
        personality="Professional and helpful"
    )
    
    # Create agent
    agent = Agent(
        agent_name="DocsAssistant",
        system_prompt=system_prompt,
        tools_processor=tools_processor,
        config=AgentConfig()
    )
    
    # Agent can now use Remote MCP tools in invoke() calls
    # The invoke() method will automatically call ToolProcessor.execute_tool()
    # when the LLM selects a Remote MCP tool
    
    return agent


# ============================================================================
# EXAMPLE 6: Mixed Tool Types
# ============================================================================

def example_6_mixed_tools():
    """
    Use Custom, Builtin, and Remote MCP tools together in one processor.
    """
    from yukta.tools import create_custom_tool
    
    tools_processor = ToolProcessor()
    
    # Custom tool (local function)
    def add_numbers(a: float, b: float) -> dict:
        """Add two numbers."""
        return {"result": a + b}
    
    custom_calc = create_custom_tool(
        name="add",
        description="Add two numbers",
        parameters=[
            {"name": "a", "type": "number", "description": "First number", "required": True},
            {"name": "b", "type": "number", "description": "Second number", "required": True}
        ],
        function=add_numbers
    )
    
    # Remote MCP tool
    remote_calc = create_remote_mcp_tool(
        name="advanced_calc",
        description="Perform advanced calculations on remote service",
        endpoint="http://localhost:9000/mcp/tools/advanced_calc",
        parameters=[
            {"name": "expression", "type": "string", "description": "Math expression", "required": True}
        ]
    )
    
    # Add both to processor
    tools_processor.add_tool(custom_calc)
    tools_processor.add_tool(remote_calc)
    
    # Both can be executed uniformly through execute_tool()
    local_result = tools_processor.execute_tool("add", {"a": 5, "b": 3})
    print(f"Local calculation: {local_result}")
    
    remote_result = tools_processor.execute_tool(
        "advanced_calc",
        {"expression": "(5 + 3) * 2"}
    )
    print(f"Remote calculation: {remote_result}")
    
    return tools_processor


# ============================================================================
# EXAMPLE 7: Async Execution of Remote MCP Tools
# ============================================================================

async def example_7_async_execution():
    """
    Asynchronously execute Remote MCP tools.
    """
    tools_processor = ToolProcessor()
    
    api_tool = create_remote_mcp_tool(
        name="fetch_data",
        description="Fetch data from remote API",
        endpoint="http://localhost:8080/mcp/tools/fetch",
        parameters=[
            {"name": "resource", "type": "string", "description": "Resource to fetch", "required": True}
        ]
    )
    
    tools_processor.add_tool(api_tool)
    
    # Execute asynchronously
    result = await tools_processor.execute_tool_async(
        "fetch_data",
        {"resource": "users"}
    )
    
    print(f"Async result: {result}")
    return result


# ============================================================================
# EXAMPLE 8: Error Handling
# ============================================================================

def example_8_error_handling():
    """
    Handle errors when executing Remote MCP tools.
    """
    tools_processor = ToolProcessor()
    
    api_tool = create_remote_mcp_tool(
        name="fetch_data",
        description="Fetch data from API",
        endpoint="http://localhost:8080/mcp/tools/fetch",
        parameters=[
            {"name": "resource", "type": "string", "description": "Resource", "required": True}
        ]
    )
    
    tools_processor.add_tool(api_tool)
    
    # Case 1: Tool not found
    result = tools_processor.execute_tool("nonexistent", {})
    if "error" in result:
        print(f"Error: {result['error']}")
    
    # Case 2: Missing required parameters
    result = tools_processor.execute_tool("fetch_data", {})
    if "error" in result:
        print(f"Parameter error: {result['error']}")
    
    # Case 3: Remote server error (network failure, timeout, etc.)
    # The execute_tool method catches exceptions and returns error dict
    result = tools_processor.execute_tool("fetch_data", {"resource": "users"})
    if "error" in result:
        print(f"Execution error: {result['error']}")


# ============================================================================
# EXAMPLE 9: Tool Schemas for LLM
# ============================================================================

def example_9_tool_schemas_for_llm():
    """
    Export tool schemas for LLM consumption.
    Remote MCP tools appear the same as other tools to the LLM.
    """
    tools_processor = ToolProcessor()
    
    # Add various tools
    search_tool = create_remote_mcp_tool(
        name="search",
        description="Search documentation",
        endpoint="http://localhost:8080/search",
        parameters=[
            {"name": "query", "type": "string", "description": "Search query", "required": True}
        ]
    )
    
    tools_processor.add_tool(search_tool)
    
    # Get formatted tools for LLM
    # Remote MCP tools appear just like other tools
    llm_tools = tools_processor.format_for_llm()
    
    import json
    print("Tools available to LLM:")
    print(json.dumps(llm_tools, indent=2))
    
    return llm_tools


# ============================================================================
# EXAMPLE 10: Configuration and Setup Pattern
# ============================================================================

def example_10_setup_pattern():
    """
    Recommended setup pattern for using Remote MCP tools.
    """
    
    def setup_tools():
        """Initialize all tools."""
        tools_processor = ToolProcessor()
        
        # Define all Remote MCP endpoints
        ENDPOINTS = {
            "search": "http://localhost:8080/mcp/tools/search",
            "retrieve": "http://localhost:8080/mcp/tools/retrieve",
            "analyze": "http://localhost:9000/mcp/tools/analyze"
        }
        
        # Create tools from config
        tools_config = [
            {
                "name": "search_docs",
                "description": "Search documentation",
                "endpoint": ENDPOINTS["search"],
                "parameters": [
                    {"name": "query", "type": "string", "description": "Search query", "required": True}
                ]
            },
            {
                "name": "get_document",
                "description": "Retrieve a document",
                "endpoint": ENDPOINTS["retrieve"],
                "parameters": [
                    {"name": "doc_id", "type": "string", "description": "Document ID", "required": True}
                ]
            }
        ]
        
        # Add all tools
        for config in tools_config:
            tool = create_remote_mcp_tool(
                name=config["name"],
                description=config["description"],
                endpoint=config["endpoint"],
                parameters=config["parameters"]
            )
            tools_processor.add_tool(tool)
        
        return tools_processor
    
    tools = setup_tools()
    print(f"Setup complete. Tools: {tools.list_tools()}")
    return tools


# ============================================================================
# Main - Run examples
# ============================================================================

if __name__ == "__main__":
    print("Yukta Remote MCP Tools Examples")
    print("=" * 50)
    print()
    
    print("Example 1: Direct Creation")
    print("-" * 50)
    tool1 = example_1_direct_creation()
    print(f"Created tool: {tool1.name}")
    print()
    
    print("Example 2: Using Helper Function")
    print("-" * 50)
    tool2 = example_2_using_helper()
    print(f"Created tool: {tool2.name}")
    print()
    
    print("Example 3: ToolProcessor with Multiple Tools")
    print("-" * 50)
    processor = example_3_tool_processor()
    print()
    
    print("Example 6: Mixed Tool Types")
    print("-" * 50)
    mixed_processor = example_6_mixed_tools()
    print()
    
    print("Example 8: Error Handling")
    print("-" * 50)
    example_8_error_handling()
    print()
    
    print("Example 9: Tool Schemas for LLM")
    print("-" * 50)
    example_9_tool_schemas_for_llm()
    print()
    
    print("Example 10: Setup Pattern")
    print("-" * 50)
    example_10_setup_pattern()
