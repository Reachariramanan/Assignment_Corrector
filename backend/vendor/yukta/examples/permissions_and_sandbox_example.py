"""
Permission Enforcement and Sandbox Isolation Examples
======================================================

Demonstrates runtime permission checks and sandboxed tool execution.

Each Tool has a required_permission field: "basic", "extended", or "admin".
Each Agent has a permission_level checked against that field before any tool
executes.  Agents with insufficient permission receive an error dict — the
tool function is never called.

Sandboxed tools (trust_level="sandbox") run in an isolated subprocess via
ToolSandbox, protecting the main process from crashes, infinite loops, or
other side effects from untrusted tool code.

Examples:
1. Permission levels — access matrix across basic / extended / admin agents
2. Permission denied — inspect the exact error response structure
3. Runtime promotion — escalate permission_level without rebuilding the agent
4. Sandbox isolation — trust_level='sandbox' with permission gate combined
"""

import logging
from typing import Dict, Any

from yukta.core.Agent.agent import Agent
from yukta.config.system_prompt import SystemPrompt
from yukta.config.agent_config import AgentConfig
from yukta.tools.tools_pro import ToolProcessor
from yukta.tools.tool import Tool, ToolType, ToolParameter

logging.disable(logging.CRITICAL)


# ============================================================================
# MOCK TOOLS — Varying Permission Levels
# ============================================================================

def get_public_info(topic: str) -> Dict[str, Any]:
    return {"topic": topic, "data": f"Public information about {topic}", "level": "public"}


def get_internal_docs(doc_id: str) -> Dict[str, Any]:
    return {"doc_id": doc_id, "content": f"Internal document: {doc_id}", "level": "internal"}


def admin_reset_system(component: str) -> Dict[str, Any]:
    return {"component": component, "status": "reset", "level": "admin"}


def compute_sum(n: int) -> Dict[str, Any]:
    """Compute-heavy operation — suitable for sandbox isolation."""
    total = sum(range(n))
    return {"n": n, "sum": total}


# ============================================================================
# SETUP HELPERS
# ============================================================================

def _make_processor_with_permissions() -> ToolProcessor:
    p = ToolProcessor()

    p.add_tool(Tool(
        name="get_public_info",
        description="Retrieve public information on a topic",
        parameters=[ToolParameter("topic", "string", "Topic name", required=True)],
        tool_type=ToolType.CUSTOM,
        function=get_public_info,
        required_permission="basic",    # Any agent can call this
    ))
    p.add_tool(Tool(
        name="get_internal_docs",
        description="Retrieve internal company documents",
        parameters=[ToolParameter("doc_id", "string", "Document ID", required=True)],
        tool_type=ToolType.CUSTOM,
        function=get_internal_docs,
        required_permission="extended", # Requires extended or admin
    ))
    p.add_tool(Tool(
        name="admin_reset_system",
        description="Reset a system component (admin only)",
        parameters=[ToolParameter("component", "string", "Component to reset", required=True)],
        tool_type=ToolType.CUSTOM,
        function=admin_reset_system,
        required_permission="admin",    # Admin only
    ))

    return p


def _make_agent(permission_level: str, name: str) -> Agent:
    return Agent(
        agent_name=name,
        system_prompt=SystemPrompt("perm_demo", "You are a permission-aware agent."),
        tools_processor=_make_processor_with_permissions(),
        config=AgentConfig(enable_logging=False),
        permission_level=permission_level,
    )


# ============================================================================
# EXAMPLE 1: Permission Levels — Access Matrix
# ============================================================================

def example_1_permission_levels():
    """
    Example 1: Permission Levels — Access Matrix

    Builds three agents (basic / extended / admin) and attempts each tool.
    The permission rank is: basic(0) < extended(1) < admin(2).
    An agent can only call tools whose required_permission rank ≤ its own.
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Permission Levels — Access Matrix")
    print("="*70)

    agents = [
        _make_agent("basic",    "JuniorAgent"),
        _make_agent("extended", "SeniorAgent"),
        _make_agent("admin",    "LeadAgent"),
    ]

    tools = [
        ("get_public_info",    {"topic": "Python"},       "basic"),
        ("get_internal_docs",  {"doc_id": "ARCH-001"},    "extended"),
        ("admin_reset_system", {"component": "cache"},    "admin"),
    ]

    col_w = 16
    print(f"\n{'Tool':<25} {'Requires':<12} {'basic':<{col_w}} {'extended':<{col_w}} {'admin'}")
    print("─" * (25 + 12 + col_w * 2 + 10))

    for tool_name, args, required in tools:
        row = f"{tool_name:<25} {required:<12}"
        for agent in agents:
            result = agent.execute_tool(tool_name, args)
            row += f"{'✓ ok':<{col_w}}" if result.get("success") else f"{'✗ denied':<{col_w}}"
        print(row)

    print("\nPermission rank: basic(0) < extended(1) < admin(2)")
    print("An agent can call any tool whose rank ≤ its own rank.")


# ============================================================================
# EXAMPLE 2: Permission Denied — Error Response Structure
# ============================================================================

def example_2_permission_denied():
    """
    Example 2: Permission Denied — Error Response Structure

    When execute_tool() blocks a call due to insufficient permission, it returns
    a dict with success=False, an 'error' string, and the 'tool' name.
    The tool function is never invoked.
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Permission Denied — Response Structure")
    print("="*70)

    junior = _make_agent("basic", "JuniorBot")

    print(f"\nAgent permission_level: {junior.permission_level!r}")
    print("\nAttempting admin-only operation:\n")

    result = junior.execute_tool("admin_reset_system", {"component": "database"})

    print(f"  result['success']:  {result['success']}")
    print(f"  result['tool']:     {result['tool']}")
    print(f"  result['error']:    {result['error']}")

    assert result["success"] is False, "Expected failure"
    assert "insufficient" in result["error"]
    print("\n✓ Tool function was NOT called — system state untouched")

    print("\nAttempting extended tool as basic agent:")
    r2 = junior.execute_tool("get_internal_docs", {"doc_id": "ARCH-001"})
    print(f"  extended tool blocked:  {'✓' if not r2['success'] else '✗'}")

    print("\nAttempting basic tool (should succeed):")
    r3 = junior.execute_tool("get_public_info", {"topic": "security"})
    print(f"  basic tool accessible:  {'✓' if r3['success'] else '✗'}")
    print(f"  result:  {r3['result']}")


# ============================================================================
# EXAMPLE 3: Runtime Permission Promotion
# ============================================================================

def example_3_runtime_promotion():
    """
    Example 3: Runtime Promotion — Changing permission_level at Runtime

    Agent.permission_level is a plain string attribute.  Updating it instantly
    changes which tools the agent can access — no need to rebuild the agent.
    Useful for escalation workflows that grant temporary elevated access.
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Runtime Permission Promotion")
    print("="*70)

    agent = _make_agent("basic", "PromotableAgent")

    print(f"\nStarting permission_level: {agent.permission_level!r}")

    r1 = agent.execute_tool("get_internal_docs", {"doc_id": "ARCH-001"})
    print(f"\nBefore promotion  → get_internal_docs:  {'✓ ok' if r1['success'] else '✗ denied'}")

    # Escalate to extended
    agent.permission_level = "extended"
    print(f"\nEscalated to: {agent.permission_level!r}")

    r2 = agent.execute_tool("get_internal_docs", {"doc_id": "ARCH-001"})
    print(f"After extension   → get_internal_docs:  {'✓ ok' if r2['success'] else '✗ denied'}")

    r3 = agent.execute_tool("admin_reset_system", {"component": "logs"})
    print(f"Admin tool still  → admin_reset_system:  {'✓ ok' if r3['success'] else '✗ denied'}")

    # Escalate to admin
    agent.permission_level = "admin"
    r4 = agent.execute_tool("admin_reset_system", {"component": "logs"})
    print(f"\nEscalated to admin → admin_reset_system:  {'✓ ok' if r4['success'] else '✗ denied'}")

    print(f"\n✓ Permission changes take effect immediately — no agent rebuild required")


# ============================================================================
# EXAMPLE 4: Sandbox Isolation Combined with Permission Gate
# ============================================================================

def example_4_sandbox_isolation():
    """
    Example 4: Sandbox Isolation — trust_level='sandbox'

    Tools with trust_level='sandbox' execute in an isolated subprocess via
    ToolSandbox.  The main process is protected from untrusted code.

    This example registers two tools with the same function:
      - trusted_compute  → direct execution (default trust_level='trusted')
      - sandboxed_compute → subprocess execution (trust_level='sandbox')

    The sandboxed tool also requires extended permission, showing both
    features working in combination.
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Sandbox Isolation + Permission Gate")
    print("="*70)

    p = ToolProcessor()

    p.add_tool(Tool(
        name="trusted_compute",
        description="Direct execution (trusted)",
        parameters=[ToolParameter("n", "integer", "Upper bound for range sum", required=True)],
        tool_type=ToolType.CUSTOM,
        function=compute_sum,
        trust_level="trusted",          # Default — runs in-process
        required_permission="basic",
    ))

    p.add_tool(Tool(
        name="sandboxed_compute",
        description="Subprocess execution (sandboxed)",
        parameters=[ToolParameter("n", "integer", "Upper bound for range sum", required=True)],
        tool_type=ToolType.CUSTOM,
        function=compute_sum,
        trust_level="sandbox",          # Runs in isolated subprocess
        required_permission="extended",
    ))

    agent = Agent(
        agent_name="SandboxDemo",
        system_prompt=SystemPrompt("sandbox", "You are a sandboxed computation agent."),
        tools_processor=p,
        config=AgentConfig(enable_logging=False),
        permission_level="extended",
    )

    print(f"\nAgent permission_level: {agent.permission_level!r}\n")

    print("1. Trusted tool (in-process):")
    r1 = agent.execute_tool("trusted_compute", {"n": 1000})
    if r1["success"]:
        print(f"   ✓ sum(0..999) = {r1['result']['sum']}")
    else:
        print(f"   ✗ {r1.get('error')}")

    print("\n2. Sandboxed tool (subprocess):")
    r2 = agent.execute_tool("sandboxed_compute", {"n": 1000})
    if r2["success"]:
        print(f"   ✓ sum(0..999) = {r2['result']['sum']}  (isolated process)")
    else:
        print(f"   ✗ {r2.get('error')}")
        print("   Note: ToolSandbox requires pickle-serialisable functions.")

    print("\n3. Sandboxed tool with insufficient permission (basic < extended):")
    agent.permission_level = "basic"
    r3 = agent.execute_tool("sandboxed_compute", {"n": 1000})
    print(f"   Permission gate fired before sandbox:  {'✓' if not r3['success'] else '✗'}")
    if not r3["success"]:
        print(f"   Error: {r3['error']}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  PERMISSIONS & SANDBOX — COMPREHENSIVE EXAMPLES".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")

    try:
        example_1_permission_levels()
        example_2_permission_denied()
        example_3_runtime_promotion()
        example_4_sandbox_isolation()

        print("\n" + "="*70)
        print("✓ All examples completed successfully!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()
