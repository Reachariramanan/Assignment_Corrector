"""
Agent Callback Handler Examples
================================

Demonstrates how to observe agent lifecycle events using AgentCallbackHandler.
Subclass the handler and override any method to hook into LLM calls, tool
execution, and run lifecycle events without modifying agent code.

Examples:
1. BasicLogger — print every lifecycle event to stdout
2. MetricsCollector — accumulate per-tool timing and call counts
3. ProgressPrinter — compact CLI-style progress lines
4. AgentBuilder with .with_callbacks() and .with_permission_level()
"""

import time
import logging
from typing import Any, Dict, List

from yukta.core.Agent.agent_callbacks import AgentCallbackHandler
from yukta.core.Agent.agent import Agent
from yukta.core.Agent.agent_builder import AgentBuilder
from yukta.config.system_prompt import SystemPrompt
from yukta.config.agent_config import AgentConfig
from yukta.tools.tools_pro import ToolProcessor
from yukta.tools.tool import Tool, ToolType, ToolParameter

logging.disable(logging.CRITICAL)


# ============================================================================
# MOCK TOOLS FOR DEMONSTRATION
# ============================================================================

def mock_search(query: str, limit: int = 5) -> Dict[str, Any]:
    """Simulated search tool — 50ms latency."""
    time.sleep(0.05)
    return {"query": query, "results": [f"Result {i+1} for '{query}'" for i in range(limit)]}


def mock_summarize(text: str) -> Dict[str, Any]:
    """Simulated summarisation tool — 30ms latency."""
    time.sleep(0.03)
    return {"summary": f"Summary of: {text[:40]}...", "length": len(text)}


def mock_translate(text: str, target_lang: str = "es") -> Dict[str, Any]:
    """Simulated translation tool — 20ms latency."""
    time.sleep(0.02)
    return {"original": text, "translated": f"[{target_lang}] {text}", "lang": target_lang}


# ============================================================================
# SETUP HELPERS
# ============================================================================

def _make_processor() -> ToolProcessor:
    p = ToolProcessor()
    p.add_tool(Tool(
        name="search",
        description="Search for information",
        parameters=[
            ToolParameter("query", "string", "Search query", required=True),
            ToolParameter("limit", "integer", "Max results", required=False, default=5),
        ],
        tool_type=ToolType.CUSTOM,
        function=mock_search,
    ))
    p.add_tool(Tool(
        name="summarize",
        description="Summarise text",
        parameters=[ToolParameter("text", "string", "Text to summarise", required=True)],
        tool_type=ToolType.CUSTOM,
        function=mock_summarize,
    ))
    p.add_tool(Tool(
        name="translate",
        description="Translate text to another language",
        parameters=[
            ToolParameter("text", "string", "Text to translate", required=True),
            ToolParameter("target_lang", "string", "Language code", required=False, default="es"),
        ],
        tool_type=ToolType.CUSTOM,
        function=mock_translate,
    ))
    return p


def _make_agent(callbacks=None, permission_level: str = "admin", name: str = "DemoAgent") -> Agent:
    return Agent(
        agent_name=name,
        system_prompt=SystemPrompt("demo", "You are a demo agent."),
        tools_processor=_make_processor(),
        config=AgentConfig(enable_logging=False),
        callbacks=callbacks,
        permission_level=permission_level,
    )


# ============================================================================
# EXAMPLE 1: BasicLogger — Print Every Lifecycle Event
# ============================================================================

class BasicLogger(AgentCallbackHandler):
    """Prints a labelled line for every lifecycle event."""

    def on_llm_start(self, messages: List[Dict], tools: List[Dict]) -> None:
        print(f"  [LLM START]  messages={len(messages)}, tools_registered={len(tools)}")

    def on_llm_end(self, response: Any) -> None:
        print(f"  [LLM END]    response received")

    def on_tool_start(self, tool_name: str, args: Dict) -> None:
        arg_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        print(f"  [TOOL START] {tool_name}({arg_str})")

    def on_tool_end(self, tool_name: str, result: Dict, duration_ms: float) -> None:
        status = "✓" if result.get("success") else "✗"
        print(f"  [TOOL END]   {tool_name} {status} ({duration_ms:.1f}ms)")

    def on_iteration_end(self, iteration: int, response_text: str) -> None:
        print(f"  [ITER END]   iteration={iteration}")

    def on_run_end(self, result: Dict) -> None:
        print(f"  [RUN END]    iterations={result.get('iterations', '?')}")

    def on_error(self, error: Exception, context: str) -> None:
        print(f"  [ERROR]      {context}: {error}")


def example_1_basic_logger():
    """
    Example 1: BasicLogger — All Lifecycle Events

    Override every AgentCallbackHandler method to observe when each event fires.
    on_llm_start / on_llm_end require a real LLM client — the tool events fire
    from execute_tool() alone, which needs no LLM.
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: BasicLogger — All Lifecycle Events")
    print("="*70)

    agent = _make_agent(callbacks=BasicLogger())

    print("\nExecuting 3 tool calls (TOOL START / TOOL END callbacks fire):\n")

    r1 = agent.execute_tool("search", {"query": "yukta agent framework", "limit": 3})
    r2 = agent.execute_tool("summarize", {"text": "Yukta is a structured agent framework."})
    r3 = agent.execute_tool("translate", {"text": "Hello world", "target_lang": "fr"})

    print(f"\nResults:")
    print(f"  search:    {r1['result']['results'][0]}")
    print(f"  summarize: {r2['result']['summary']}")
    print(f"  translate: {r3['result']['translated']}")


# ============================================================================
# EXAMPLE 2: MetricsCollector — Accumulate Per-Tool Performance Data
# ============================================================================

class MetricsCollector(AgentCallbackHandler):
    """Accumulates per-tool call counts and duration lists."""

    def __init__(self):
        self.tool_calls: Dict[str, int] = {}
        self.tool_durations: Dict[str, List[float]] = {}
        self.errors: int = 0

    def on_tool_start(self, tool_name: str, args: Dict) -> None:
        self.tool_calls[tool_name] = self.tool_calls.get(tool_name, 0) + 1
        self.tool_durations.setdefault(tool_name, [])

    def on_tool_end(self, tool_name: str, result: Dict, duration_ms: float) -> None:
        self.tool_durations[tool_name].append(duration_ms)
        if not result.get("success"):
            self.errors += 1

    def on_error(self, error: Exception, context: str) -> None:
        self.errors += 1

    def report(self) -> str:
        lines = ["  Tool Performance Report:", f"  {'─'*44}"]
        for tool, calls in self.tool_calls.items():
            durations = self.tool_durations[tool]
            avg = sum(durations) / len(durations) if durations else 0.0
            lines.append(f"  {tool:<20} calls={calls:<4} avg_ms={avg:.1f}")
        lines.append(f"  {'─'*44}")
        lines.append(f"  Total errors: {self.errors}")
        return "\n".join(lines)


def example_2_metrics_collector():
    """
    Example 2: MetricsCollector — Timing and Call Counts

    MetricsCollector accumulates per-tool call counts and average durations
    across multiple execute_tool() invocations.  Call .report() at any time
    to get a formatted summary.
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: MetricsCollector — Performance Tracking")
    print("="*70)

    metrics = MetricsCollector()
    agent = _make_agent(callbacks=metrics)

    print("\nRunning 10 tool calls across 3 tools...")

    for i in range(4):
        agent.execute_tool("search", {"query": f"query-{i}", "limit": 2})
    for i in range(3):
        agent.execute_tool("summarize", {"text": f"Document {i} — content to summarise."})
    for i in range(3):
        agent.execute_tool("translate", {"text": f"Message {i}", "target_lang": "de"})

    print()
    print(metrics.report())


# ============================================================================
# EXAMPLE 3: ProgressPrinter — Compact CLI-Style Progress Lines
# ============================================================================

class ProgressPrinter(AgentCallbackHandler):
    """Prints a compact progress line per tool call."""

    def __init__(self, prefix: str = ""):
        self._prefix = prefix
        self._call_num = 0

    def on_tool_start(self, tool_name: str, args: Dict) -> None:
        self._call_num += 1
        preview = ", ".join(f"{k}={str(v)[:12]!r}" for k, v in list(args.items())[:2])
        print(f"  {self._prefix}[{self._call_num:02d}] → {tool_name}({preview})", end=" ", flush=True)

    def on_tool_end(self, tool_name: str, result: Dict, duration_ms: float) -> None:
        if result.get("success"):
            print(f"✓ {duration_ms:.0f}ms")
        else:
            print(f"✗ {result.get('error', 'failed')}")

    def on_error(self, error: Exception, context: str) -> None:
        print(f"\n  {self._prefix}[ERROR] {context}: {error}")


def example_3_progress_printer():
    """
    Example 3: ProgressPrinter — Compact CLI Output

    ProgressPrinter renders one line per tool call with tool name, argument
    preview, status symbol, and duration.  Suitable for pipeline scripts that
    need a running progress indicator.
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: ProgressPrinter — Compact CLI Output")
    print("="*70)

    agent = _make_agent(callbacks=ProgressPrinter(prefix="ResearchAgent "))

    tasks = [
        ("search",    {"query": "climate change",   "limit": 5}),
        ("search",    {"query": "renewable energy",  "limit": 3}),
        ("summarize", {"text": "Climate change and renewable energy are interconnected."}),
        ("translate", {"text": "Climate report done", "target_lang": "ja"}),
    ]

    print("\nRunning research pipeline:\n")
    for tool_name, args in tasks:
        agent.execute_tool(tool_name, args)

    print(f"\n✓ Pipeline complete — {len(tasks)} steps")


# ============================================================================
# EXAMPLE 4: AgentBuilder with Callbacks and Permission Level
# ============================================================================

class AuditLogger(AgentCallbackHandler):
    """Minimal audit trail — logs tool name, outcome, and timing only."""

    def __init__(self):
        self.audit_log: List[Dict] = []

    def on_tool_end(self, tool_name: str, result: Dict, duration_ms: float) -> None:
        self.audit_log.append({
            "tool":    tool_name,
            "success": result.get("success", False),
            "ms":      round(duration_ms, 1),
        })

    def on_run_end(self, result: Dict) -> None:
        print(f"  Run complete — {len(self.audit_log)} tools called")


def example_4_builder_pattern():
    """
    Example 4: AgentBuilder — Fluent Configuration

    AgentBuilder exposes .with_callbacks() and .with_permission_level() for a
    fluent builder experience.  The resulting agent behaves identically to one
    constructed via the Agent() constructor directly.
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: AgentBuilder — Fluent Configuration")
    print("="*70)

    audit = AuditLogger()

    agent = (
        AgentBuilder()
        .with_name("AuditedAgent")
        .with_default_prompt("You are a helpful research agent.")
        .with_tools_processor(_make_processor())
        .with_callbacks(audit)
        .with_permission_level("extended")
        .build()
    )

    print(f"\nAgent built:        {agent.agent_name!r}")
    print(f"permission_level:   {agent.permission_level!r}")
    print(f"Callbacks attached: {type(agent.callbacks).__name__}")

    print("\nExecuting tools via builder-configured agent:\n")
    agent.execute_tool("search",    {"query": "agent frameworks"})
    agent.execute_tool("translate", {"text": "Agent complete", "target_lang": "zh"})

    print(f"\nAudit log ({len(audit.audit_log)} entries):")
    for entry in audit.audit_log:
        status = "✓" if entry["success"] else "✗"
        print(f"  {status} {entry['tool']:<20} {entry['ms']:.1f}ms")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  AGENT CALLBACK HANDLER — COMPREHENSIVE EXAMPLES".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")

    try:
        example_1_basic_logger()
        example_2_metrics_collector()
        example_3_progress_printer()
        example_4_builder_pattern()

        print("\n" + "="*70)
        print("✓ All examples completed successfully!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()
