"""
Parallel Tool Execution Examples
=================================

Demonstrates how to use ToolProcessor parallel execution feature.
Tools can be executed sequentially (default) or in parallel for better performance.

Examples:
1. Sequential execution (backward compatible)
2. Parallel execution with default settings
3. Parallel execution with custom workers
4. Manual tool call format from LLM
5. Performance comparison
6. Error handling in parallel mode
7. Statistics and monitoring
"""

import time
import json
import asyncio
from typing import Dict, Any, List

from yukta.tools.tools_pro import ToolProcessor
from yukta.tools.tool import Tool, ToolType, ToolParameter


# ============================================================================
# MOCK TOOLS FOR DEMONSTRATION (Simulate API calls)
# ============================================================================

def mock_get_weather(city: str, units: str = "celsius") -> Dict[str, Any]:
    """Mock weather API call - simulates 1 second network latency."""
    time.sleep(1)  # Simulate network delay
    return {
        "city": city,
        "temperature": 25,
        "units": units,
        "conditions": "Sunny",
        "humidity": 60
    }


def mock_get_stock_price(symbol: str) -> Dict[str, Any]:
    """Mock stock API call - simulates 0.8 second network latency."""
    time.sleep(0.8)  # Simulate network delay
    return {
        "symbol": symbol,
        "price": 150.25,
        "currency": "USD",
        "change": 2.5,
        "timestamp": "2026-04-15T10:30:00Z"
    }


def mock_get_news(topic: str, limit: int = 3) -> Dict[str, Any]:
    """Mock news API call - simulates 0.5 second network latency."""
    time.sleep(0.5)  # Simulate network delay
    return {
        "topic": topic,
        "articles": [
            {"title": f"Article 1 about {topic}", "source": "TechNews"},
            {"title": f"Article 2 about {topic}", "source": "DataBlog"},
            {"title": f"Article 3 about {topic}", "source": "AIToday"}
        ][:limit],
        "total_found": 100
    }


def mock_get_crypto_price(coin: str) -> Dict[str, Any]:
    """Mock crypto API call - simulates 0.6 second network latency."""
    time.sleep(0.6)  # Simulate network delay
    return {
        "coin": coin,
        "price_usd": 45000,
        "market_cap": 900000000000,
        "volume_24h": 30000000000,
        "change_24h": 5.2
    }


def mock_get_currency_rate(from_currency: str, to_currency: str) -> Dict[str, Any]:
    """Mock currency exchange API - simulates 0.4 second network latency."""
    time.sleep(0.4)  # Simulate network delay
    return {
        "from": from_currency,
        "to": to_currency,
        "rate": 1.10,
        "timestamp": "2026-04-15T10:30:00Z"
    }


# ============================================================================
# SETUP: Create ToolProcessor with tools
# ============================================================================

def setup_tools() -> ToolProcessor:
    """Create and configure tool processor with sample tools."""
    processor = ToolProcessor(
        parallel=False,  # Start with sequential (will change in examples)
        num_parallel=3,
        timeout_per_tool=10.0
    )
    
    # Add weather tool
    processor.add_tool(Tool(
        name="get_weather",
        description="Get current weather for a city",
        parameters=[
            ToolParameter(name="city", type="string", description="City name", required=True),
            ToolParameter(name="units", type="string", description="celsius or fahrenheit", required=False, default="celsius")
        ],
        tool_type=ToolType.CUSTOM,
        function=mock_get_weather
    ))
    
    # Add stock price tool
    processor.add_tool(Tool(
        name="get_stock_price",
        description="Get current stock price",
        parameters=[
            ToolParameter(name="symbol", type="string", description="Stock ticker symbol", required=True)
        ],
        tool_type=ToolType.CUSTOM,
        function=mock_get_stock_price
    ))
    
    # Add news tool
    processor.add_tool(Tool(
        name="get_news",
        description="Get news articles on a topic",
        parameters=[
            ToolParameter(name="topic", type="string", description="Topic to search", required=True),
            ToolParameter(name="limit", type="integer", description="Number of articles", required=False, default=3)
        ],
        tool_type=ToolType.CUSTOM,
        function=mock_get_news
    ))
    
    # Add crypto tool
    processor.add_tool(Tool(
        name="get_crypto_price",
        description="Get cryptocurrency price",
        parameters=[
            ToolParameter(name="coin", type="string", description="Cryptocurrency symbol", required=True)
        ],
        tool_type=ToolType.CUSTOM,
        function=mock_get_crypto_price
    ))
    
    # Add currency tool
    processor.add_tool(Tool(
        name="get_currency_rate",
        description="Get currency exchange rate",
        parameters=[
            ToolParameter(name="from_currency", type="string", description="Source currency", required=True),
            ToolParameter(name="to_currency", type="string", description="Target currency", required=True)
        ],
        tool_type=ToolType.CUSTOM,
        function=mock_get_currency_rate
    ))
    
    return processor


# ============================================================================
# EXAMPLE 1: Sequential Execution (Default - Backward Compatible)
# ============================================================================

def example_1_sequential():
    """
    Example 1: Sequential Tool Execution
    
    Tools are executed one after another.
    Total time ≈ sum of all tool execution times.
    Default mode for backward compatibility.
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Sequential Execution (Default)")
    print("="*70)
    
    processor = setup_tools()
    processor.set_parallel_mode(parallel=False)  # Explicitly disable parallel
    
    # Tool calls from LLM (as it would come from the model)
    tool_calls = [
        {
            "id": "call_1",
            "function": {
                "name": "get_weather",
                "arguments": json.dumps({"city": "New York", "units": "fahrenheit"})
            }
        },
        {
            "id": "call_2",
            "function": {
                "name": "get_stock_price",
                "arguments": json.dumps({"symbol": "AAPL"})
            }
        },
        {
            "id": "call_3",
            "function": {
                "name": "get_news",
                "arguments": json.dumps({"topic": "AI", "limit": 5})
            }
        }
    ]
    
    print(f"Executing {len(tool_calls)} tools sequentially...")
    print(f"Expected time: ~2.3 seconds (1.0 + 0.8 + 0.5)")
    print()
    
    start_time = time.time()
    results = processor.execute_tools(tool_calls)
    elapsed = time.time() - start_time
    
    print(f"✓ Completed in {elapsed:.2f} seconds")
    print(f"\nResults:")
    for i, result in enumerate(results, 1):
        tool_name = tool_calls[i-1]["function"]["name"]
        status = "✓ Success" if "result" in result else "✗ Error"
        print(f"  {i}. {tool_name}: {status}")
        if "result" in result:
            print(f"     Result: {result.get('result', {})}")
    
    print(f"\nStats: {processor.get_parallel_execution_stats()}")


# ============================================================================
# EXAMPLE 2: Parallel Execution (Basic)
# ============================================================================

def example_2_parallel_basic():
    """
    Example 2: Parallel Tool Execution (Basic)
    
    Tools are executed concurrently.
    Total time ≈ longest tool execution time.
    3x faster than sequential for this example.
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Parallel Execution (Basic)")
    print("="*70)
    
    processor = setup_tools()
    processor.set_parallel_mode(parallel=True, num_parallel=3)
    
    tool_calls = [
        {
            "id": "call_1",
            "function": {
                "name": "get_weather",
                "arguments": json.dumps({"city": "London"})
            }
        },
        {
            "id": "call_2",
            "function": {
                "name": "get_stock_price",
                "arguments": json.dumps({"symbol": "GOOGL"})
            }
        },
        {
            "id": "call_3",
            "function": {
                "name": "get_crypto_price",
                "arguments": json.dumps({"coin": "BTC"})
            }
        }
    ]
    
    print(f"Executing {len(tool_calls)} tools in parallel...")
    print(f"Expected time: ~1.0 seconds (max of 1.0, 0.8, 0.6)")
    print(f"Speedup: ~2.4x vs sequential")
    print()
    
    start_time = time.time()
    results = processor.execute_tools(tool_calls)
    elapsed = time.time() - start_time
    
    print(f"✓ Completed in {elapsed:.2f} seconds")
    print(f"\nResults:")
    for i, result in enumerate(results, 1):
        tool_name = tool_calls[i-1]["function"]["name"]
        status = "✓ Success" if "result" in result else "✗ Error"
        print(f"  {i}. {tool_name}: {status}")
    
    stats = processor.get_parallel_execution_stats()
    print(f"\nSpeedup: {stats['last_speedup']:.1f}x")


# ============================================================================
# EXAMPLE 3: Parallel Execution with Custom Worker Count
# ============================================================================

def example_3_parallel_custom_workers():
    """
    Example 3: Parallel Execution with Custom Worker Count
    
    Demonstrates limiting concurrent workers.
    Useful for rate-limited APIs.
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Parallel with Custom Workers")
    print("="*70)
    
    processor = setup_tools()
    processor.set_parallel_mode(parallel=True, num_parallel=2)  # Only 2 concurrent workers
    
    tool_calls = [
        {"id": "call_1", "function": {"name": "get_weather", "arguments": json.dumps({"city": "Paris"})}},
        {"id": "call_2", "function": {"name": "get_stock_price", "arguments": json.dumps({"symbol": "MSFT"})}},
        {"id": "call_3", "function": {"name": "get_news", "arguments": json.dumps({"topic": "Blockchain"})}},
        {"id": "call_4", "function": {"name": "get_crypto_price", "arguments": json.dumps({"coin": "ETH"})}}
    ]
    
    print(f"Executing {len(tool_calls)} tools with {processor.num_parallel} workers...")
    print(f"Tools will be executed in batches of 2")
    print()
    
    start_time = time.time()
    results = processor.execute_tools(tool_calls)
    elapsed = time.time() - start_time
    
    print(f"✓ Completed in {elapsed:.2f} seconds")
    print(f"Sequential would be: ~2.9 seconds")
    print(f"Speedup: ~{2.9/elapsed:.1f}x")
    
    stats = processor.get_parallel_execution_stats()
    print(f"\nExecution config: {processor.num_parallel} workers (capped at {len(tool_calls)} tools)")


# ============================================================================
# EXAMPLE 4: Error Handling in Parallel Mode (Fail-Safe)
# ============================================================================

def example_4_error_handling():
    """
    Example 4: Error Handling in Parallel Mode
    
    Demonstrates fail-safe error handling.
    If one tool fails, others continue executing.
    All results are returned, including errors.
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Error Handling (Fail-Safe)")
    print("="*70)
    
    processor = setup_tools()
    processor.set_parallel_mode(parallel=True, num_parallel=3)
    processor.set_timeout(2.0)  # 2 second timeout
    
    tool_calls = [
        {"id": "call_1", "function": {"name": "get_weather", "arguments": json.dumps({"city": "Tokyo"})}},
        {
            "id": "call_2",
            "function": {"name": "invalid_tool", "arguments": json.dumps({})}  # ← This will fail
        },
        {"id": "call_3", "function": {"name": "get_stock_price", "arguments": json.dumps({"symbol": "TSLA"})}},
    ]
    
    print(f"Executing {len(tool_calls)} tools (one will fail)...")
    print()
    
    results = processor.execute_tools(tool_calls)
    
    print(f"✓ Completed (with 1 error)")
    print(f"\nResults:")
    for i, result in enumerate(results, 1):
        tool_name = tool_calls[i-1]["function"]["name"]
        if "result" in result:
            print(f"  {i}. {tool_name}: ✓ Success")
        else:
            print(f"  {i}. {tool_name}: ✗ Error - {result.get('error', 'Unknown error')}")
    
    print(f"\nNote: Error in call 2 didn't stop execution of calls 1 and 3")


# ============================================================================
# EXAMPLE 5: Performance Comparison
# ============================================================================

def example_5_performance_comparison():
    """
    Example 5: Sequential vs Parallel Performance Comparison
    
    Runs the same tools with both execution modes and compares performance.
    """
    print("\n" + "="*70)
    print("EXAMPLE 5: Performance Comparison")
    print("="*70)
    
    tool_calls = [
        {"id": f"call_{i+1}", "function": {"name": name, "arguments": json.dumps(args)}}
        for i, (name, args) in enumerate([
            ("get_weather", {"city": "NYC"}),
            ("get_stock_price", {"symbol": "AAPL"}),
            ("get_news", {"topic": "AI"}),
            ("get_crypto_price", {"coin": "BTC"}),
            ("get_currency_rate", {"from_currency": "USD", "to_currency": "EUR"})
        ])
    ]
    
    # Sequential execution
    print(f"\n1. Sequential Mode ({len(tool_calls)} tools):")
    processor_seq = setup_tools()
    processor_seq.set_parallel_mode(parallel=False)
    
    start = time.time()
    processor_seq.execute_tools(tool_calls)
    seq_time = time.time() - start
    print(f"   Time: {seq_time:.2f} seconds")
    
    # Parallel execution
    print(f"\n2. Parallel Mode ({len(tool_calls)} tools, 3 workers):")
    processor_par = setup_tools()
    processor_par.set_parallel_mode(parallel=True, num_parallel=3)
    
    start = time.time()
    processor_par.execute_tools(tool_calls)
    par_time = time.time() - start
    print(f"   Time: {par_time:.2f} seconds")
    
    # Comparison
    speedup = seq_time / par_time
    print(f"\n{'─'*70}")
    print(f"Speedup: {speedup:.1f}x faster")
    print(f"Time saved: {seq_time - par_time:.2f} seconds")
    print(f"Efficiency: {(1 - (par_time * len(tool_calls) / seq_time)) * 100:.1f}%")


# ============================================================================
# EXAMPLE 6: Configuration Options
# ============================================================================

def example_6_configuration():
    """
    Example 6: Configuration Options
    
    Demonstrates various configuration methods.
    """
    print("\n" + "="*70)
    print("EXAMPLE 6: Configuration Options")
    print("="*70)
    
    processor = setup_tools()
    
    print("\n1. Default configuration:")
    print(f"   parallel: {processor.parallel}")
    print(f"   num_parallel: {processor.num_parallel}")
    print(f"   timeout_per_tool: {processor.timeout_per_tool}s")
    
    print("\n2. Enable parallel with 4 workers:")
    processor.enable_parallel(num_workers=4)
    print(f"   parallel: {processor.parallel}")
    print(f"   num_parallel: {processor.num_parallel}")
    
    print("\n3. Set custom timeout:")
    processor.set_timeout(5.0)
    print(f"   timeout_per_tool: {processor.timeout_per_tool}s")
    
    print("\n4. Disable parallel:")
    processor.disable_parallel()
    print(f"   parallel: {processor.parallel}")
    
    print("\n5. Current statistics:")
    stats = processor.get_parallel_execution_stats()
    for key, value in stats.items():
        if key != "execution_history":
            print(f"   {key}: {value}")


# ============================================================================
# EXAMPLE 7: Statistics and Monitoring
# ============================================================================

def example_7_statistics():
    """
    Example 7: Statistics and Monitoring
    
    Demonstrates how to monitor and track execution statistics.
    """
    print("\n" + "="*70)
    print("EXAMPLE 7: Statistics and Monitoring")
    print("="*70)
    
    processor = setup_tools()
    processor.enable_parallel(num_workers=3)
    
    # Execute multiple batches
    batches = [
        [
            {"id": "call_1", "function": {"name": "get_weather", "arguments": json.dumps({"city": "NYC"})}},
            {"id": "call_2", "function": {"name": "get_stock_price", "arguments": json.dumps({"symbol": "AAPL"})}},
        ],
        [
            {"id": "call_3", "function": {"name": "get_news", "arguments": json.dumps({"topic": "AI"})}},
            {"id": "call_4", "function": {"name": "get_crypto_price", "arguments": json.dumps({"coin": "BTC"})}},
            {"id": "call_5", "function": {"name": "get_currency_rate", "arguments": json.dumps({"from_currency": "USD", "to_currency": "EUR"})}},
        ]
    ]
    
    print(f"Executing {len(batches)} batches...")
    for batch_num, batch in enumerate(batches, 1):
        print(f"  Batch {batch_num}: {len(batch)} tools")
        processor.execute_tools(batch)
    
    print(f"\nFinal Statistics:")
    stats = processor.get_parallel_execution_stats()
    print(f"  Total parallel calls: {stats['total_parallel_calls']}")
    print(f"  Total sequential calls: {stats['total_sequential_calls']}")
    print(f"  Total tools executed: {stats['total_tools_executed']}")
    print(f"  Total tools failed: {stats['total_tools_failed']}")
    print(f"  Total execution time: {stats['total_execution_time']:.2f}s")
    print(f"  Average speedup: {stats['average_speedup']:.1f}x")
    print(f"  Success rate: {(stats['total_tools_executed'] / (stats['total_tools_executed'] + stats['total_tools_failed']) * 100):.1f}%")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  PARALLEL TOOL EXECUTION - COMPREHENSIVE EXAMPLES".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    try:
        example_1_sequential()
        example_2_parallel_basic()
        example_3_parallel_custom_workers()
        example_4_error_handling()
        example_5_performance_comparison()
        example_6_configuration()
        example_7_statistics()
        
        print("\n" + "="*70)
        print("✓ All examples completed successfully!")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()
