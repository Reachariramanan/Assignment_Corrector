"""
models.py — Base Data Structures for yukta-api

This module defines all the dataclasses and enums that represent
the core entities of the ecosystem.

These are the internal representations that flow through:
  reader.py → validator.py → allocator.py → transformer.py → runner.py

Hierarchy:
  SkillData   — A reusable workflow (loaded from skills/<name>/SKILL.md)
  ToolData    — A callable capability (loaded from tools/<name>.yaml)
  AgentData   — An actor with role, skills, tools, permissions (from agents/<name>.yaml)
  TeamData    — A group of agents with a leader (from teams/<name>.yaml)
  BootstrapConfig — System startup config (from bootstrap/using-yukta.yaml)
  SystemConfig    — Global system settings (from config/main.yaml)
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
from pathlib import Path


def _yukta_dir() -> Path:
    """Return the base yukta data directory, respecting YUKTA_DATA_DIR env var."""
    env_val = os.environ.get("YUKTA_DATA_DIR", "").strip()
    return Path(env_val) if env_val else Path.home() / ".yukta"


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class AgentLevel(str, Enum):
    """
    Hierarchical level of an agent.

    Determines what the agent is allowed to do autonomously:
    - JUNIOR: Can read skills and use assigned tools. Cannot self-assign.
    - SENIOR: Can self-assign skills and create tools. Needs leader approval for self-generation.
    - LEAD:   Full autonomy. Can form teams, create agents, and lead.
    """
    JUNIOR = "junior"
    SENIOR = "senior"
    LEAD = "lead"

    @classmethod
    def from_str(cls, value: str) -> "AgentLevel":
        """Parse string to AgentLevel, case-insensitive."""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid agent level: '{value}'. Must be one of: {[e.value for e in cls]}")

    def rank(self) -> int:
        """Return numeric rank for comparison (higher = more capable)."""
        return {AgentLevel.JUNIOR: 0, AgentLevel.SENIOR: 1, AgentLevel.LEAD: 2}[self]

    def __lt__(self, other: "AgentLevel") -> bool:
        if not isinstance(other, AgentLevel):
            return NotImplemented
        return self.rank() < other.rank()

    def __le__(self, other: "AgentLevel") -> bool:
        if not isinstance(other, AgentLevel):
            return NotImplemented
        return self.rank() <= other.rank()

    def __ge__(self, other: "AgentLevel") -> bool:
        if not isinstance(other, AgentLevel):
            return NotImplemented
        return self.rank() >= other.rank()

    def __gt__(self, other: "AgentLevel") -> bool:
        if not isinstance(other, AgentLevel):
            return NotImplemented
        return self.rank() > other.rank()


class ToolType(str, Enum):
    """
    Type of a tool, mapped to yukta's ToolType enum.

    - CUSTOM:     User-defined Python function
    - BUILTIN:    Built-in tool (file-editor, terminal, git, search)
    - REMOTE_MCP: Remote Model Context Protocol tool (HTTP endpoint)
    """
    CUSTOM = "custom"
    BUILTIN = "builtin"
    REMOTE_MCP = "remote_mcp"

    @classmethod
    def from_str(cls, value: str) -> "ToolType":
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid tool type: '{value}'. Must be one of: {[e.value for e in cls]}")


class TeamStructure(str, Enum):
    """
    Collaboration structure of a team.

    - HIERARCHICAL: Clear chain of command, leader assigns tasks
    - FLAT:         Collaborative, no formal hierarchy, peer review style
    - DYNAMIC:      Fluid roles, context-dependent leadership
    """
    HIERARCHICAL = "hierarchical"
    FLAT = "flat"
    DYNAMIC = "dynamic"

    @classmethod
    def from_str(cls, value: str) -> "TeamStructure":
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid team structure: '{value}'. Must be one of: {[e.value for e in cls]}")


class PermissionLevel(str, Enum):
    """
    Broad access control levels for the ecosystem.

    - BASIC:    Read skills, use assigned tools, join teams
    - EXTENDED: Create/update tools, self-assign skills
    - ADMIN:    Full control over all entities
    """
    BASIC = "basic"
    EXTENDED = "extended"
    ADMIN = "admin"


class ApprovalStatus(str, Enum):
    """
    Status of an agent's work within a team workflow.
    """
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"


class HitlMode(str, Enum):
    """
    Human-in-the-Loop intervention frequency.
    """
    OFF = "off"
    EVERY_TURN = "every_turn"
    ON_APPROVAL = "on_approval"


# ─────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────

@dataclass
class SkillData:
    """
    Represents a skill loaded from skills/<skill-name>/SKILL.md.

    A skill is a reusable, composable workflow that teaches an agent
    HOW to approach a specific type of task.

    Attributes:
        skill_id:     Unique identifier (matches directory name, e.g., "brainstorming")
        name:         Human-readable name from YAML frontmatter
        description:  Trigger condition and purpose (max 150 chars)
        version:      Semantic version string (e.g., "1.0.0")
        category:     Category tag (process, implementation, team, meta, bootstrap)
        content:      Full markdown body of the skill (after frontmatter)
        file_path:    Absolute path to the SKILL.md file
        metadata:     Any extra fields from YAML frontmatter
    """
    skill_id: str
    name: str
    description: str
    version: str = "1.0.0"
    category: str = "process"
    content: str = ""
    file_path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if len(self.description) > 150:
            raise ValueError(
                f"Skill '{self.skill_id}' description exceeds 150 chars "
                f"({len(self.description)} chars). Shorten it."
            )

    def to_system_prompt_text(self) -> str:
        """Return the skill's content formatted for injection into a system prompt."""
        header = f"# Skill: {self.name}\n\n**Description:** {self.description}\n\n"
        return header + self.content

    def __repr__(self) -> str:
        return f"SkillData(id='{self.skill_id}', category='{self.category}', version='{self.version}')"


@dataclass
class ToolParameterData:
    """
    Represents a single parameter for a tool.

    Attributes:
        name:        Parameter name (used as Python kwarg)
        type:        JSON schema type (string, integer, boolean, number, object, array)
        description: What this parameter does
        required:    Whether this parameter is mandatory
        default:     Default value if not provided
        enum:        Allowed values (restricts input to a fixed set)
    """
    name: str
    type: str
    description: str
    required: bool = False
    default: Any = None
    enum: Optional[List[Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict format for yukta's ToolParameter."""
        d: Dict[str, Any] = {
            "type": self.type,
            "description": self.description,
        }
        if self.default is not None:
            d["default"] = self.default
        if self.enum:
            d["enum"] = self.enum
        return d


@dataclass
class ToolData:
    """
    Represents a tool loaded from tools/<tool-name>.yaml.

    Tools are callable capabilities that agents invoke to interact
    with the world (read files, run commands, call APIs, etc.).

    Attributes:
        tool_id:       Unique identifier (e.g., "file-editor")
        description:   What the tool does
        parameters:    List of ToolParameterData instances
        returns:       Return type description
        tool_type:     ToolType enum value
        version:       Semantic version string
        function_path: Optional "module:function" path for CUSTOM tools
        metadata:      Any extra fields from YAML
    """
    tool_id: str
    description: str
    parameters: List[ToolParameterData] = field(default_factory=list)
    returns: str = "string"
    tool_type: ToolType = ToolType.BUILTIN
    version: str = "1.0.0"
    function_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_required_params(self) -> List[str]:
        """Return names of all required parameters."""
        return [p.name for p in self.parameters if p.required]

    def get_optional_params(self) -> List[str]:
        """Return names of all optional parameters."""
        return [p.name for p in self.parameters if not p.required]

    def __repr__(self) -> str:
        return f"ToolData(id='{self.tool_id}', type='{self.tool_type.value}', params={len(self.parameters)})"


@dataclass
class AgentData:
    """
    Represents an agent loaded from agents/<agent-name>.yaml.

    Agents are the primary actors in the ecosystem. They have roles,
    levels, assigned skills, available tools, and permissions.

    Attributes:
        agent_id:         Unique identifier (e.g., "architect")
        role:             Human-readable role name (e.g., "Architect")
        level:            AgentLevel (junior, senior, lead)
        skills:           List of skill IDs assigned to this agent
        tools:            List of tool IDs this agent can use
        permissions:      List of permission strings
        behaviors:        Optional list of behavior descriptors
        context:          Optional project/workspace context string
        team_memberships: List of team IDs this agent belongs to
        team_leads:       List of team IDs this agent leads (lead-level only)
        version:          Schema version
        metadata:         Any extra fields from YAML
    """
    agent_id: str
    role: str
    level: AgentLevel
    skills: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    behaviors: List[str] = field(default_factory=list)
    context: str = ""
    team_memberships: List[str] = field(default_factory=list)
    team_leads: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_permission(self, permission: str) -> bool:
        """Check if agent has a specific permission (ignores temp expiry — use validator for that)."""
        return permission in self.permissions

    def has_skill(self, skill_id: str) -> bool:
        """Check if agent has a specific skill assigned."""
        return skill_id in self.skills

    def has_tool(self, tool_id: str) -> bool:
        """Check if agent has access to a specific tool."""
        return tool_id in self.tools

    def is_at_least(self, level: AgentLevel) -> bool:
        """Check if agent meets or exceeds a required level."""
        return self.level >= level

    def is_leader_of(self, team_id: str) -> bool:
        """Check if agent leads a specific team."""
        return team_id in self.team_leads

    def get_temp_permissions(self) -> List[str]:
        """Get all temporary permissions (those ending with '-temp')."""
        return [p for p in self.permissions if p.endswith("-temp")]

    def build_system_prompt_text(self) -> str:
        """
        Generate the base system prompt text for this agent.
        Used by transformer.py to create a yukta SystemPrompt.
        """
        lines = [
            f"You are {self.role} (agent_id: {self.agent_id}).",
            f"Level: {self.level.value}.",
        ]
        if self.context:
            lines.append(f"Context: {self.context}")
        if self.behaviors:
            lines.append(f"Behaviors: {', '.join(self.behaviors)}.")
        if self.skills:
            lines.append(f"\nYou have been assigned the following skills: {', '.join(self.skills)}.")
            lines.append("Always check if a skill applies before responding.")
        if self.tools:
            lines.append(f"\nYou have access to these tools: {', '.join(self.tools)}.")
        if self.team_memberships:
            lines.append(f"\nYou are a member of: {', '.join(self.team_memberships)}.")
        if self.team_leads:
            lines.append(f"You lead the following teams: {', '.join(self.team_leads)}.")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"AgentData(id='{self.agent_id}', role='{self.role}', level='{self.level.value}')"


@dataclass
class TeamData:
    """
    Represents a team loaded from teams/<team-name>.yaml.

    Teams group agents under a leader for coordinated task execution.

    Attributes:
        team_id:    Unique identifier (e.g., "team-dev")
        name:       Human-readable team name
        leader_id:  agent_id of the team leader
        structure:  TeamStructure enum value
        members:    List of agent_ids in this team
        purpose:    Optional description of what this team does
        capabilities: Optional list of capability tags
        version:    Schema version
        metadata:   Any extra fields from YAML
    """
    team_id: str
    name: str
    leader_id: str
    structure: TeamStructure
    members: List[str] = field(default_factory=list)
    purpose: str = ""
    capabilities: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_member(self, agent_id: str) -> bool:
        """Check if an agent is a member of this team."""
        return agent_id in self.members

    def __repr__(self) -> str:
        return f"TeamData(id='{self.team_id}', leader='{self.leader_id}', members={len(self.members)})"


@dataclass
class TeamSession:
    """
    Represents the active state of a running team execution.
    
    Attributes:
        session_id:      Shared yukta memory session ID for all agents in the team.
        team_id:         ID of the team executing the task.
        current_speaker: agent_id of the agent currently holding the floor.
        iteration_count: Number of turns taken so far.
        status:          Current status of the team task.
        history:         Shared log of who spoke when (internal state).
        hitl_interventions: Number of times a human intervened.
    """
    session_id: str
    team_id: str
    current_speaker: Optional[str] = None
    iteration_count: int = 0
    status: ApprovalStatus = ApprovalStatus.PENDING
    history: List[Dict[str, str]] = field(default_factory=list)
    hitl_interventions: int = 0


@dataclass
class LeaderBrief:
    """
    Structured task brief issued by the leader each coordination round.

    The leader agent must output ONLY a JSON object matching this structure.
    When *done* is True the coordinator stops and returns *final_answer*.
    """
    round: int
    assignments: List[Dict[str, Any]]  # [{"agent_id": str, "task": str, "expected_output": str}]
    context: str
    done: bool = False
    final_answer: str = ""


@dataclass
class AgentReport:
    """
    Structured response returned by a sub-agent after executing a task.

    Sub-agents must output ONLY a JSON object matching this structure.
    """
    agent_id: str
    status: str          # "done" | "blocked" | "needs_help"
    output: str
    confidence: float    # 0.0 – 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BootstrapConfig:
    """
    Bootstrap configuration loaded from bootstrap/using-yukta.yaml.

    Defines the skill to inject at every session start and how
    to locate the skills box.

    Attributes:
        bootstrap_skill:    Skill ID to inject at start (always "using-yukta")
        skill_path:         Relative path to skills-box/index.yaml
        inject_at_start:    Whether to inject at session start (default: True)
        additional_context: Extra text to inject alongside the bootstrap skill
        version:            Schema version
        file_path:          Absolute path to the bootstrap YAML file (for debugging)
    """
    bootstrap_skill: str = "using-yukta"
    skill_path: str = "skills-box/index.yaml"
    inject_at_start: bool = True
    additional_context: str = ""
    version: str = "1.0.0"
    file_path: str = ""

    def __repr__(self) -> str:
        return f"BootstrapConfig(skill='{self.bootstrap_skill}', inject={self.inject_at_start})"


@dataclass
class SystemConfig:
    """
    System-wide configuration loaded from config/main.yaml.

    Controls global ecosystem behavior, logging, storage,
    and paths to all ecosystem directories.

    Attributes:
        system_name:        Name of the system
        system_version:     Version of the system
        default_permission: Default permission level for new agents
        admin_role:         Role name for admin access
        log_level:          Logging verbosity (DEBUG, INFO, WARNING, ERROR)
        log_output:         Log output destination (stdout, file path)
        enable_logging:     Whether to enable logging
        enable_memory_logging: Whether to enable memory logging
        auto_save_chat:     Whether to auto-save chat history
        chat_history_dir:   Directory for chat history files
        max_iter:           Max iterations per agent run (0 = unlimited)
        storage_backend:    Storage type (json, sqlite)
        storage_path:       Path to storage directory
        open_telemetry:     Whether to enable OpenTelemetry tracing
        phoenix_endpoint:   Phoenix OTEL endpoint URL
        ecosystem_root:     Root path of the ecosystem directory
        skills_path:        Path to skills/ directory
        skills_box:         Path to skills-box/index.yaml
        agents_path:        Path to agents/ directory
        tools_path:         Path to tools/ directory
        teams_path:        Path to teams/ directory
        bootstrap_path:     Path to bootstrap config YAML
        metadata:           Any extra fields from YAML
    """
    system_name: str = "yukta-ecosystem"
    system_version: str = "1.0.0"
    schema_version: str = "1.0.0"
    default_permission: str = "basic"
    admin_role: str = "system-admin"
    log_level: str = "INFO"
    log_output: str = "stdout"
    enable_logging: bool = True
    enable_memory_logging: bool = True
    auto_save_chat: bool = True
    chat_history_dir: str = field(default_factory=lambda: str(_yukta_dir() / "chats"))
    max_iter: int = 10
    storage_backend: str = "json"
    storage_path: str = field(default_factory=lambda: str(_yukta_dir() / "data"))
    open_telemetry: bool = False
    phoenix_endpoint: str = "http://localhost:6007/v1/traces"
    ecosystem_root: str = "./ecosystem"
    skills_path: str = "./ecosystem/skills"
    skills_box: str = "./ecosystem/skills-box/index.yaml"
    agents_path: str = "./ecosystem/agents"
    tools_path: str = "./ecosystem/tools"
    teams_path: str = "./ecosystem/teams"
    bootstrap_path: str = "./ecosystem/bootstrap/using-yukta.yaml"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"SystemConfig(name='{self.system_name}', version='{self.system_version}', schema='{self.schema_version}')"


__all__ = [
    "AgentLevel",
    "ToolType",
    "TeamStructure",
    "PermissionLevel",
    "ApprovalStatus",
    "HitlMode",
    "SkillData",
    "ToolParameterData",
    "ToolData",
    "AgentData",
    "TeamData",
    "TeamSession",
    "LeaderBrief",
    "AgentReport",
    "BootstrapConfig",
    "SystemConfig",
]