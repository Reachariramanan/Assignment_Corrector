"""
LeaderCoordinator — Hierarchical Team Orchestration Examples
=============================================================

Demonstrates structured-rounds coordination for HIERARCHICAL teams using
LeaderCoordinator.

Protocol (per round):
  1. Leader receives the task + prior reports.  Must respond with a
     LeaderBrief JSON: { round, assignments, context, done, final_answer }
  2. Each assigned sub-agent responds with an AgentReport JSON:
     { agent_id, status, output, confidence }
  3. Reports feed back to the leader for the next round.
  4. When done=true the session ends and final_answer is returned.

PREREQUISITE:
  An Ollama server must be running with a model available.
  Default endpoint: http://localhost:11434
  Start server:     ollama serve
  Pull a model:     ollama pull qwen2.5

  To use a different LLM backend (vLLM, LMStudio, etc.) replace OllamaClient
  with the appropriate client from yukta.core.Clients.

Examples:
1. Object setup — build AgentData, SkillData, TeamData objects manually
2. LeaderCoordinator construction — assemble coordinator from ecosystem dict
3. Run a coordination session — requires Ollama server
4. Inspect structured rounds output — parse LeaderBrief and AgentReport history
"""

import logging
from typing import Dict, Any, List

from yukta.api.models import (
    AgentData,
    AgentLevel,
    SkillData,
    ToolData,
    TeamData,
    TeamStructure,
    SystemConfig,
)
from yukta.api.coordinator import LeaderCoordinator


# ============================================================================
# TEAM DEFINITION — Analyst team with a Lead + two Senior analysts
# ============================================================================

LEADER_ID   = "chief-analyst"
ANALYST_IDS = ["data-analyst", "report-writer"]


def _build_skill(skill_id: str, name: str, description: str, content: str) -> SkillData:
    return SkillData(
        skill_id=skill_id,
        name=name,
        description=description,
        content=content,
        category="analysis",
    )


def _build_ecosystem() -> Dict[str, Any]:
    """Build a minimal ecosystem dict from API model objects."""

    agents = [
        AgentData(
            agent_id=LEADER_ID,
            role="Chief Analyst",
            level=AgentLevel.LEAD,
            skills=["analysis-coordination"],
            tools=[],
            context=(
                "You coordinate a small analyst team.  Issue assignments each round "
                "and synthesise their outputs into a final recommendation."
            ),
        ),
        AgentData(
            agent_id="data-analyst",
            role="Data Analyst",
            level=AgentLevel.SENIOR,
            skills=["data-analysis"],
            tools=[],
            context=(
                "You analyse quantitative data and produce structured findings.  "
                "Always include key metrics and trends in your output."
            ),
        ),
        AgentData(
            agent_id="report-writer",
            role="Report Writer",
            level=AgentLevel.SENIOR,
            skills=["report-writing"],
            tools=[],
            context=(
                "You turn raw analysis into clear, concise written summaries.  "
                "Output must be readable by non-technical stakeholders."
            ),
        ),
    ]

    skills = [
        _build_skill(
            "analysis-coordination",
            "Analysis Coordination",
            "Coordinate multi-agent analysis workflows",
            "Break down complex analysis tasks and assign to specialists.",
        ),
        _build_skill(
            "data-analysis",
            "Data Analysis",
            "Quantitative data analysis and trend identification",
            "Apply statistical methods and identify trends in data.",
        ),
        _build_skill(
            "report-writing",
            "Report Writing",
            "Professional business report writing for stakeholders",
            "Translate technical findings into executive summaries.",
        ),
    ]

    config = SystemConfig(
        enable_logging=False,
        auto_save_chat=False,
        max_iter=5,
    )

    return {
        "agents": agents,
        "skills": skills,
        "tools":  [],
        "config": config,
    }


def _build_team() -> TeamData:
    return TeamData(
        team_id="analyst-team",
        name="Analyst Team",
        leader_id=LEADER_ID,
        structure=TeamStructure.HIERARCHICAL,
        members=[LEADER_ID] + ANALYST_IDS,
        purpose="Analyse data and produce written recommendations",
    )


# ============================================================================
# EXAMPLE 1: Object Setup — Inspect AgentData and TeamData
# ============================================================================

def example_1_object_setup():
    """
    Example 1: Object Setup — AgentData and TeamData Construction

    LeaderCoordinator consumes API model objects, not raw YAML files.
    This example builds them manually so you can inspect their structure
    without running any LLM.
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Object Setup — AgentData and TeamData Construction")
    print("="*70)

    ecosystem = _build_ecosystem()
    team = _build_team()

    print(f"\nTeam: {team.name!r} ({team.team_id})")
    print(f"  Structure:  {team.structure.value}")
    print(f"  Leader ID:  {team.leader_id}")
    print(f"  Members:    {team.members}")
    print(f"  Purpose:    {team.purpose}")

    print(f"\nAgents in ecosystem ({len(ecosystem['agents'])}):")
    for agent in ecosystem["agents"]:
        print(f"  [{agent.level.value:<8}] {agent.agent_id:<20} role={agent.role!r}")

    print(f"\nSkills ({len(ecosystem['skills'])}):")
    for skill in ecosystem["skills"]:
        print(f"  {skill.skill_id:<30} {skill.description}")

    print(f"\nSystemConfig (relevant keys):")
    cfg = ecosystem["config"]
    print(f"  max_iter:        {cfg.max_iter}")
    print(f"  enable_logging:  {cfg.enable_logging}")


# ============================================================================
# EXAMPLE 2: LeaderCoordinator Construction
# ============================================================================

def example_2_coordinator_construction():
    """
    Example 2: LeaderCoordinator Construction

    Assemble a LeaderCoordinator from the ecosystem dict and TeamData.
    No LLM call is made at construction time — the coordinator only needs
    the client when .run() is called.
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: LeaderCoordinator Construction")
    print("="*70)

    ecosystem = _build_ecosystem()
    team      = _build_team()

    # llm_client=None is valid at construction — error only at run() time
    coordinator = LeaderCoordinator(
        team=team,
        ecosystem=ecosystem,
        llm_client=None,
    )

    print(f"\nCoordinator ready:")
    print(f"  session_id:  {coordinator.session_id}")
    print(f"  team_id:     {coordinator.team.team_id}")
    print(f"  leader_id:   {coordinator.team.leader_id}")
    print(f"  members:     {coordinator.team.members}")

    print(f"\nSession state:")
    print(f"  status:          {coordinator.session.status}")
    print(f"  iteration_count: {coordinator.session.iteration_count}")

    print(f"\n✓ Coordinator constructed — call .run(task) when an LLM is available")


# ============================================================================
# EXAMPLE 3: Run a Coordination Session (requires Ollama)
# ============================================================================

def example_3_run_session(model: str = "qwen2.5") -> Dict[str, Any]:
    """
    Example 3: Run a Coordination Session

    Runs a full multi-round coordination session.  The leader issues task
    assignments each round; sub-agents return structured JSON reports.
    Session ends when the leader sets done=true.

    REQUIRES: Ollama server at http://localhost:11434 with the specified model.
    """
    print("\n" + "="*70)
    print(f"EXAMPLE 3: Run Session  (model={model!r})")
    print("="*70)

    # Import here so the file is importable without Ollama installed
    from yukta.core.Clients import OllamaClient   # noqa: PLC0415

    ecosystem = _build_ecosystem()
    team      = _build_team()

    llm = OllamaClient(model_name=model)

    coordinator = LeaderCoordinator(
        team=team,
        ecosystem=ecosystem,
        llm_client=llm,
    )

    task = (
        "Analyse Q1 performance for our SaaS product.  "
        "Identify the top 3 growth drivers and produce a one-paragraph executive summary."
    )

    print(f"\nTask: {task}")
    print(f"\nStarting coordination session (max 5 rounds)...")
    print("─" * 70)

    result = coordinator.run(task=task, max_rounds=5)

    print("─" * 70)
    print(f"\nSession complete:")
    print(f"  success:  {result.get('success')}")
    print(f"  rounds:   {result.get('rounds')}")

    final = result.get("final_answer", "")
    if final:
        print(f"\nFinal Answer:\n  {final}")

    return result


# ============================================================================
# EXAMPLE 4: Inspect Round History
# ============================================================================

def example_4_inspect_history(result: Dict[str, Any]) -> None:
    """
    Example 4: Inspect Round History

    The result dict from coordinator.run() contains a 'history' list.
    Each entry has a 'brief' (LeaderBrief fields) and 'reports' (per-agent).
    This example walks through the history to show what happened each round.
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Inspect Round History")
    print("="*70)

    history: List[Dict[str, Any]] = result.get("history", [])

    if not history:
        print("\n  (no history to display)")
        return

    print(f"\n  {len(history)} round(s) recorded:")

    for entry in history:
        round_num = entry.get("round", "?")
        brief     = entry.get("brief", {})
        reports   = entry.get("reports", [])

        print(f"\n  ── Round {round_num} ──")

        # Leader assignments
        assignments = brief.get("assignments", []) if isinstance(brief, dict) else []
        if assignments:
            print(f"  Leader assigned {len(assignments)} task(s):")
            for a in assignments:
                print(f"    → {a.get('agent_id'):<22} {a.get('task', '')[:60]}")
        else:
            print(f"  Leader issued no assignments (done={brief.get('done', '?') if isinstance(brief, dict) else '?'})")

        # Sub-agent reports
        if reports:
            print(f"  Sub-agent reports ({len(reports)}):")
            for r in reports:
                agent_id   = r.get("agent_id", "?")
                status     = r.get("status", "?")
                confidence = r.get("confidence", 0.0)
                output_snip = str(r.get("output", ""))[:60]
                print(f"    ← {agent_id:<22} status={status}  conf={confidence:.2f}")
                print(f"       {output_snip}...")

    print()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    import sys

    model_name = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5"

    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  LEADER COORDINATOR — HIERARCHICAL TEAM EXAMPLES".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    print(f"\n  Requires Ollama running at http://localhost:11434")
    print(f"  Model: {model_name!r}  (pass a different model as: python team_coordinator_example.py <model>)")

    try:
        example_1_object_setup()
        example_2_coordinator_construction()

        # Examples 3 and 4 require a live LLM — gracefully skip if unavailable
        try:
            result = example_3_run_session(model=model_name)
            example_4_inspect_history(result)
        except Exception as llm_err:
            print(f"\n  ✗ LLM session skipped: {llm_err}")
            print("    Start Ollama and run again to see examples 3–4.")

        print("\n" + "="*70)
        print("✓ All examples completed!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()
