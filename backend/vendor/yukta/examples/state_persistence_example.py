"""
Agent State Persistence Examples
==================================

Demonstrates saving and restoring agent execution state across process restarts.

Agent.run() auto-saves state + stats + history to:
    {chat_history_dir}/{agent_name}/run_state.json
when auto_save_chat_history=True (the default in AgentConfig).

Agent.load_run_state() restores that snapshot into any agent instance,
enabling crash recovery and session continuity.

Persisted fields:
  state   — status, iterations, timestamps, last_activity
  stats   — tool_calls, successful_tool_calls, llm_calls, token counts
  history — ordered list of add_to_history() entries with timestamps

Examples:
1. Manual save — call _save_run_state() at a checkpoint
2. State file structure — inspect the JSON payload on disk
3. Load and restore — restore state into a fresh agent instance
4. Resume pattern — crash-recovery across a multi-phase pipeline
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any

from yukta.core.Agent.agent import Agent
from yukta.config.system_prompt import SystemPrompt
from yukta.config.agent_config import AgentConfig
from yukta.tools.tools_pro import ToolProcessor
from yukta.tools.tool import Tool, ToolType, ToolParameter

logging.disable(logging.CRITICAL)


# ============================================================================
# MOCK TOOLS
# ============================================================================

def fetch_data(source: str) -> Dict[str, Any]:
    return {"source": source, "records": 42, "status": "fetched"}


def process_data(record_count: int) -> Dict[str, Any]:
    return {"processed": record_count, "output": f"{record_count} records processed"}


# ============================================================================
# SETUP HELPERS
# ============================================================================

def _make_processor() -> ToolProcessor:
    p = ToolProcessor()
    p.add_tool(Tool(
        name="fetch_data",
        description="Fetch data from a source",
        parameters=[ToolParameter("source", "string", "Data source URI", required=True)],
        tool_type=ToolType.CUSTOM,
        function=fetch_data,
    ))
    p.add_tool(Tool(
        name="process_data",
        description="Process fetched records",
        parameters=[ToolParameter("record_count", "integer", "Number of records", required=True)],
        tool_type=ToolType.CUSTOM,
        function=process_data,
    ))
    return p


def _make_agent(tmpdir: str, name: str = "PersistenceDemo") -> Agent:
    config = AgentConfig(
        enable_logging=False,
        auto_save_chat_history=True,
        chat_history_dir=tmpdir,
    )
    return Agent(
        agent_name=name,
        system_prompt=SystemPrompt("persist", "You are a data-pipeline agent."),
        tools_processor=_make_processor(),
        config=config,
    )


def _do_work(agent: Agent) -> None:
    """Run two tools and record them in history, simulating a real execution."""
    r1 = agent.execute_tool("fetch_data", {"source": "db://analytics/events"})
    agent.add_to_history({"type": "tool_call", "tool": "fetch_data",    "result": r1})

    r2 = agent.execute_tool("process_data", {"record_count": 42})
    agent.add_to_history({"type": "tool_call", "tool": "process_data",  "result": r2})

    agent.state["status"] = "completed"
    agent.state["iterations"] = 2


# ============================================================================
# EXAMPLE 1: Manual Save — Checkpoint at Any Point
# ============================================================================

def example_1_manual_save():
    """
    Example 1: Manual Save

    Call agent._save_run_state() explicitly to persist state at any milestone.
    Useful for long pipelines that want fine-grained checkpoints independent
    of run() completion.
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Manual Save")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        agent = _make_agent(tmpdir)
        _do_work(agent)

        print(f"\nBefore save:")
        print(f"  state.status:     {agent.state['status']!r}")
        print(f"  state.iterations: {agent.state['iterations']}")
        print(f"  history entries:  {len(agent.history)}")
        print(f"  tool_calls:       {agent.stats['tool_calls']}")

        agent._save_run_state()

        state_file = Path(tmpdir) / agent.agent_name / "run_state.json"
        print(f"\n✓ State saved to: {state_file}")
        print(f"  File exists: {state_file.exists()}")
        print(f"  File size:   {state_file.stat().st_size} bytes")


# ============================================================================
# EXAMPLE 2: State File Structure — Inspect the JSON Payload
# ============================================================================

def example_2_state_file_structure():
    """
    Example 2: State File Structure

    run_state.json contains: agent_id, agent_name, state, stats, history,
    and a saved_at ISO timestamp.  This example saves then reads the file
    to show the exact layout.
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: State File Structure")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        agent = _make_agent(tmpdir)
        _do_work(agent)
        agent._save_run_state()

        state_file = Path(tmpdir) / agent.agent_name / "run_state.json"
        payload = json.loads(state_file.read_text())

        print(f"\nTop-level keys:  {list(payload.keys())}")
        print(f"\nagent_id:    {payload['agent_id'][:16]}...")
        print(f"agent_name:  {payload['agent_name']!r}")
        print(f"saved_at:    {payload['saved_at']}")

        print(f"\nstate dict:")
        for k, v in payload["state"].items():
            print(f"  {k:<20} {v!r}")

        print(f"\nstats dict (tool counters):")
        for k in ("tool_calls", "successful_tool_calls", "failed_tool_calls", "llm_calls"):
            print(f"  {k:<30} {payload['stats'][k]}")

        print(f"\nhistory ({len(payload['history'])} entries):")
        for entry in payload["history"]:
            ts = entry.get("timestamp", "")[:19]
            print(f"  [{entry.get('type')}]  tool={entry.get('tool')}  at={ts}")


# ============================================================================
# EXAMPLE 3: Load and Restore — Fresh Agent from Saved State
# ============================================================================

def example_3_load_and_restore():
    """
    Example 3: Load and Restore

    A brand-new Agent instance can fully restore history and stats from a
    prior agent's run_state.json using Agent.load_run_state().
    The default path is {chat_history_dir}/{agent_name}/run_state.json.
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Load and Restore")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Original agent: work and save
        original = _make_agent(tmpdir, name="ResearchAgent")
        _do_work(original)
        original._save_run_state()

        orig_history = len(original.history)
        orig_calls   = original.stats["tool_calls"]

        print(f"\nOriginal agent:")
        print(f"  history entries: {orig_history}")
        print(f"  tool_calls:      {orig_calls}")
        print(f"  status:          {original.state['status']!r}")

        # Fresh agent: same name → same default path
        fresh = _make_agent(tmpdir, name="ResearchAgent")

        print(f"\nFresh agent (before load):")
        print(f"  history entries: {len(fresh.history)}")
        print(f"  tool_calls:      {fresh.stats['tool_calls']}")

        loaded = fresh.load_run_state()

        print(f"\nAfter load_run_state()  (success={loaded}):")
        print(f"  history entries: {len(fresh.history)}")
        print(f"  tool_calls:      {fresh.stats['tool_calls']}")
        print(f"  status:          {fresh.state['status']!r}")

        assert len(fresh.history) == orig_history
        assert fresh.stats["tool_calls"] == orig_calls
        print("\n✓ State fully restored into fresh agent instance")


# ============================================================================
# EXAMPLE 4: Resume Pattern — Crash Recovery Across Pipeline Phases
# ============================================================================

def example_4_resume_pattern():
    """
    Example 4: Resume Pattern — Crash Recovery

    A three-phase pipeline checkpoints after Phase 1.  When the process
    crashes and restarts, the new agent reloads the checkpoint and resumes
    from Phase 2, without repeating Phase 1 work.
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Resume Pattern — Crash Recovery")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Phase 1 — fetch and checkpoint
        agent = _make_agent(tmpdir, name="PipelineAgent")

        print("\nPhase 1 — fetching data...")
        r1 = agent.execute_tool("fetch_data", {"source": "s3://data-lake/raw"})
        agent.add_to_history({"type": "phase", "phase": 1, "result": r1})
        agent.state["status"] = "phase_1_complete"
        agent.state["iterations"] = 1
        agent._save_run_state()   # Checkpoint
        print(f"  ✓ Fetched {r1['result']['records']} records — checkpoint saved")

        # Simulate crash: new agent instance, all in-memory state lost
        print("\nSimulated crash — process restarted...")
        restarted = _make_agent(tmpdir, name="PipelineAgent")

        loaded = restarted.load_run_state()
        print(f"  Checkpoint loaded:  {'✓' if loaded else '✗'}")
        print(f"  Restored status:    {restarted.state['status']!r}")
        print(f"  History entries:    {len(restarted.history)}")

        # Phase 2 — resume from checkpoint
        print("\nPhase 2 — processing (continuing from checkpoint)...")
        if restarted.state.get("status") == "phase_1_complete":
            prior_records = restarted.history[0]["result"]["result"]["records"]
            r2 = restarted.execute_tool("process_data", {"record_count": prior_records})
            restarted.add_to_history({"type": "phase", "phase": 2, "result": r2})
            restarted.state["status"] = "complete"
            restarted.state["iterations"] = 2
            restarted._save_run_state()
            print(f"  ✓ Processed {r2['result']['processed']} records")

        print(f"\n✓ Pipeline complete with crash recovery")
        print(f"  Final status:  {restarted.state['status']!r}")
        print(f"  Total history: {len(restarted.history)} entries")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  AGENT STATE PERSISTENCE — COMPREHENSIVE EXAMPLES".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")

    try:
        example_1_manual_save()
        example_2_state_file_structure()
        example_3_load_and_restore()
        example_4_resume_pattern()

        print("\n" + "="*70)
        print("✓ All examples completed successfully!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()
