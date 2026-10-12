"""
Sample 2: Testing Remote MCP Tools from localhost:8000
========================================================

Simple test script for the 5 MCP tools available on localhost:8000:
- add_numbers: Add two numbers
- get_weather: Return mock weather for a city
- summarize_text: Simple text summary
- convert_currency: Convert currency using given rate
- get_definition: Return a simple definition

Prerequisites:
- localhost:8000 must be running with these tool endpoints
"""

import json
from yukta.tools import create_remote_mcp_tool, ToolProcessor


def setup_remote_tools():
    """Setup Remote MCP tools pointing to localhost:8000."""
    tools_processor = ToolProcessor()
    
    # 1. Add Numbers Tool
    add_numbers_tool = create_remote_mcp_tool(
        name="add_numbers",
        description="Add two numbers",
        endpoint="http://localhost:8000/tools/add_numbers",
        parameters=[
            {"name": "a", "type": "number", "required": True},
            {"name": "b", "type": "number", "required": True}
        ]
    )
    tools_processor.add_tool(add_numbers_tool)
    
    # 2. Get Weather Tool
    get_weather_tool = create_remote_mcp_tool(
        name="get_weather",
        description="Return mock weather for a city",
        endpoint="http://localhost:8000/tools/get_weather",
        parameters=[
            {"name": "city", "type": "string", "required": True}
        ]
    )
    tools_processor.add_tool(get_weather_tool)
    
    # 3. Summarize Text Tool
    summarize_text_tool = create_remote_mcp_tool(
        name="summarize_text",
        description="Simple text summary",
        endpoint="http://localhost:8000/tools/summarize_text",
        parameters=[
            {"name": "text", "type": "string", "required": True},
            {"name": "max_length", "type": "integer", "required": False, "default": 100}
        ]
    )
    tools_processor.add_tool(summarize_text_tool)
    
    # 4. Convert Currency Tool
    convert_currency_tool = create_remote_mcp_tool(
        name="convert_currency",
        description="Convert currency using given rate",
        endpoint="http://localhost:8000/tools/convert_currency",
        parameters=[
            {"name": "amount", "type": "number", "required": True},
            {"name": "from_currency", "type": "string", "required": True},
            {"name": "to_currency", "type": "string", "required": True},
            {"name": "rate", "type": "number", "required": True}
        ]
    )
    tools_processor.add_tool(convert_currency_tool)
    
    # 5. Get Definition Tool
    get_definition_tool = create_remote_mcp_tool(
        name="get_definition",
        description="Return a simple definition",
        endpoint="http://localhost:8000/tools/get_definition",
        parameters=[
            {"name": "term", "type": "string", "required": True}
        ]
    )
    tools_processor.add_tool(get_definition_tool)
    
    return tools_processor


def test_tools(tools_processor):
    """Test all MCP tools."""
    print("Testing Remote MCP Tools from localhost:8000\n")
    
    tests = [
        {
            "name": "add_numbers",
            "args": {"a": 10, "b": 20},
            "description": "Add 10 + 20"
        },
        {
            "name": "get_weather",
            "args": {"city": "New York"},
            "description": "Get weather for New York"
        },
        {
            "name": "summarize_text",
            "args": {"text": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed."},
            "description": "Summarize ML text"
        },
        {
            "name": "convert_currency",
            "args": {"amount": 100, "from_currency": "USD", "to_currency": "EUR", "rate": 0.92},
            "description": "Convert 100 USD to EUR"
        },
        {
            "name": "get_definition",
            "args": {"term": "algorithm"},
            "description": "Get definition of algorithm"
        }
    ]
    
    for i, test in enumerate(tests, 1):
        print(f"[{i}] {test['description']}")
        print(f"    Tool: {test['name']}")
        print(f"    Args: {test['args']}")
        
        result = tools_processor.execute_tool(test['name'], test['args'])
        
        if "error" in result:
            print(f"    Error: {result['error']}")
        else:
            print(f"    Result: {json.dumps(result, indent=8)}")
        
        print()


if __name__ == "__main__":
    tools = setup_remote_tools()
    print(f"Loaded {len(tools.list_tools())} tools: {', '.join(tools.list_tools())}\n")
    test_tools(tools)
