# Yukta Ecosystem YAML Structure Reference

A complete reference guide to all YAML file structures in the yukta-ecosystem.

---

## Table of Contents

1. [Overview](#overview)
2. [Agent Configuration](#agent-configuration)
3. [Skill Configuration](#skill-configuration)
4. [Tool Configuration](#tool-configuration)
5. [Team Configuration](#team-configuration)
6. [System Configuration](#system-configuration)
7. [Bootstrap Configuration](#bootstrap-configuration)
8. [Skills Box Index](#skills-box-index)
9. [Permission Configuration](#permission-configuration)
10. [Complete Examples](#complete-examples)

---

## Overview

The yukta-ecosystem uses YAML files for **declarative configuration** of all entities. The ecosystem is organized into directories:

```
ecosystem/
├── agents/          # Agent YAML configurations
├── skills/          # Skill workflows (Markdown with YAML frontmatter)
├── tools/           # Tool descriptors (YAML)
├── tools-impl/      # Tool implementations (Python)
├── teams/           # Team configurations (YAML)
├── config/          # Global system configuration
├── bootstrap/       # Bootstrap configuration
└── skills-box/      # Index registry for all skills/tools/agents
```

---

## Agent Configuration

### File Location
`ecosystem/agents/{agent_id}.yaml`

### Schema
```yaml
agent_id: <string>              # Unique identifier
role: <string>                  # Human-readable role name
level: junior | senior | lead   # Hierarchical level
version: <string>               # Schema version (default: "1.0.0")

skills:                         # List of skill IDs assigned
  - <skill_id_1>
  - <skill_id_2>

tools:                          # List of tool IDs available
  - <tool_id_1>
  - <tool_id_2>

permissions:                    # Access control permissions
  - <permission_1>
  - <permission_2>

behaviors:                      # Personality traits (optional)
  - <trait_1>
  - <trait_2>

context: <string>               # Project/workspace context (optional)
team_memberships:               # Teams this agent belongs to
  - <team_id_1>
  - <team_id_2>

team_leads:                     # Teams this agent leads (LEAD level only)
  - <team_id_1>
```

### Example: Developer Agent
```yaml
agent_id: developer
role: Developer
level: junior
version: "1.0.0"

skills:
  - using-yukta
  - executing-plans
  - verification-before-completion

tools:
  - file-editor
  - terminal
  - git

permissions:
  - skill-read
  - tool-use
  - agent-read
  - team-join

behaviors:
  - methodical
  - test-first

team_memberships:
  - team-dev
```

### Example: Architect Agent (LEAD Level)
```yaml
agent_id: architect
role: Architect
level: lead
version: "1.0.0"

skills:
  - using-yukta
  - brainstorming
  - writing-plans
  - executing-plans
  - systematic-debugging
  - test-driven-development
  - subagent-driven-development
  - dispatching-parallel-agents
  - verification-before-completion
  - writing-skills

tools:
  - file-editor
  - terminal
  - git
  - search

permissions:
  - skill-read
  - skill-assign
  - skill-write
  - tool-use
  - tool-write
  - agent-read
  - agent-write
  - team-read
  - team-lead
  - team-assign
  - team-join
  - create-agent
  - team-membership-manage

behaviors:
  - strategic
  - decision-making
  - team-coordination

team_memberships:
  - team-dev

team_leads:
  - team-dev
```

### Level Hierarchy

| Level | Rank | Capabilities |
|-------|------|--------------|
| `junior` | 0 | Read skills, use assigned tools, join teams |
| `senior` | 1 | Self-assign skills, create/update tools |
| `lead` | 2 | Full autonomy: form teams, create agents, lead |

### Permission Types

#### Basic Level (Default)
- `skill-read` - View skill content
- `tool-use` - Use assigned tools
- `agent-read` - View agent configurations
- `team-join` - Join teams

#### Extended Level
- All basic permissions
- `skill-assign` - Assign skills to agents
- `tool-write` - Create/modify tools
- `agent-write` - Create/modify agents

#### Admin Level
- All extended permissions
- `skill-write` - Create/modify skills
- `team-read` - View team configurations
- `team-lead` - Lead teams
- `team-assign` - Assign tasks within teams
- `create-agent` - Create new agents
- `team-membership-manage` - Add/remove team members

---

## Skill Configuration

### File Location
`ecosystem/skills/<skill_id>/SKILL.md`

### Format

Skills use **Markdown with YAML frontmatter**:

```markdown
---
name: <skill_id>                # Must match directory name
description: <string>           # Max 150 chars
version: <string>               # Semantic version (default: "1.0.0")
category: process | implementation | team | bootstrap | meta
---                             # End of frontmatter

# <Skill Title>

## Overview
Description of what this skill does.

## When to Use
When to invoke this skill.

## The Process
Step-by-step instructions.

## Checklist
- [ ] Item 1
- [ ] Item 2
```

### Example: test-driven-development Skill

```markdown
---
name: test-driven-development
description: "Use when implementing any feature or bugfix - write tests before implementation code"
version: "1.0.0"
category: process
---

# Test-Driven Development (TDD)

## Overview

Write the test first. Watch it fail. Write minimal code to pass.

**Core Principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

## Red-Green-Refactor

### RED — Write Failing Test
Write one minimal test showing what should happen.

### Verify RED — Watch It Fail
**MANDATORY. Never skip.**

```bash
python -m pytest path/to/test.py -v
```

Confirm:
- Test fails (not errors)
- Failure message is expected
- Fails because feature is missing (not typos)

### GREEN — Minimal Code
Write the simplest code to pass the test.

### Verify GREEN — Watch It Pass
**MANDATORY.**

```bash
python -m pytest path/to/test.py -v
```

### REFACTOR — Clean Up
After green only: remove duplication, improve names, extract helpers.

## Red Flags — STOP and Start Over

- Code before test
- Test added after implementation
- Test passes immediately without changes
- Can't explain why the test failed
- Rationalizing "just this once"

## Checklist

- [ ] Wrote failing test first
- [ ] Watched it fail with expected message
- [ ] Wrote minimal implementation
- [ ] Watched test pass
- [ ] Refactored without breaking tests
- [ ] All tests still pass
```

### Skill Categories

| Category | Purpose | Examples |
|----------|---------|----------|
| `bootstrap` | System-level guidance | `using-yukta` |
| `process` | Methodologies and workflows | `tdd`, `debugging`, `planning` |
| `implementation` | Technical implementation guides | `git-worktrees`, `branch-finish` |
| `team` | Multi-agent coordination | `group-collaboration`, `code-review` |
| `meta` | Skill creation and management | `writing-skills` |

---

## Tool Configuration

### File Location
`ecosystem/tools/<tool_id>.yaml`

### Schema
```yaml
tool_id: <string>               # Unique identifier
description: <string>           # What the tool does
parameters:                     # List of parameter definitions
  - name: <param_name>
    type: string | integer | number | boolean | object | array
    required: true | false
    description: <string>
    default: <value>            # Optional default value
    enum:                       # Optional: allowed values
      - <value_1>
      - <value_2>
returns: <string>               # Return type description
tool_type: builtin | custom | remote_mcp  # Tool type
version: <string>               # Semantic version (default: "1.0.0")

function_path: <string>         # Required for CUSTOM tools: module:function
metadata:                       # Optional extra fields
  key: value
```

### Example: file-editor Tool
```yaml
tool_id: file-editor
description: "Read and write files on the filesystem"
function_path: "ecosystem.tools-impl.file_editor:execute"
parameters:
  - name: action
    type: string
    required: true
    description: "Action to perform: read, write, append, delete"
    enum: [read, write, append, delete]
  - name: path
    type: string
    required: true
    description: "File path to operate on"
  - name: content
    type: string
    required: false
    description: "Content to write (required for write/append actions)"
returns: string
tool_type: builtin
version: "1.0.0"
```

### Example: search Tool
```yaml
tool_id: search
description: "Search codebase for patterns using grep/ripgrep"
function_path: "ecosystem.tools-impl.search:execute"
parameters:
  - name: pattern
    type: string
    required: true
    description: "Search pattern (supports regex)"
  - name: path
    type: string
    required: false
    description: "Directory or file to search in (default: project root)"
  - name: file_type
    type: string
    required: false
    description: "File extension filter (e.g., py, yaml, md)"
  - name: case_sensitive
    type: boolean
    required: false
    description: "Whether search is case-sensitive (default: false)"
returns: string
tool_type: builtin
version: "1.0.0"
```

### Example: terminal Tool
```yaml
tool_id: terminal
description: "Execute shell commands in the project directory"
function_path: "ecosystem.tools-impl.terminal:execute"
parameters:
  - name: command
    type: string
    required: true
    description: "Shell command to execute"
  - name: cwd
    type: string
    required: false
    description: "Working directory for the command (default: project root)"
  - name: timeout
    type: number
    required: false
    description: "Command timeout in seconds (default: 60)"
returns: string
tool_type: builtin
version: "1.0.0"
```

### Tool Types

| Type | Description | Required `function_path` |
|------|-------------|--------------------------|
| `builtin` | Built-in tools (file-editor, terminal, git, search) | No |
| `custom` | User-defined Python functions | Yes |
| `remote_mcp` | Remote MCP tools | Yes |

### Tool Implementation Format

Custom tools require a Python implementation at `ecosystem/tools-impl/<tool_impl>.py`:

```python
def execute(param1: str, param2: int = 0) -> dict:
    """
    Execute the tool with given parameters.
    
    Args:
        param1: Description of param1
        param2: Description of param2 (optional)
    
    Returns:
        A dictionary with result or error message.
    """
    try:
        # Tool logic here
        return {"content": result, "success": True}
    except Exception as e:
        return {"error": str(e), "success": False}
```

---

## Team Configuration

### File Location
`ecosystem/teams/<team_id>.yaml`

### Schema
```yaml
team_id: <string>               # Unique identifier
name: <string>                  # Human-readable team name
leader_id: <agent_id>           # Agent ID of the team leader
structure: hierarchical | flat | dynamic  # Collaboration structure
version: <string>               # Semantic version (default: "1.0.0")

members:                        # List of member agent IDs
  - <agent_id_1>
  - <agent_id_2>

purpose: <string>               # Team purpose (optional)
capabilities:                   # Team capabilities (optional)
  - <capability_1>
  - <capability_2>

metadata:                       # Optional extra fields
  key: value
```

### Example: team-dev (Hierarchical)
```yaml
team_id: team-dev
name: Development Team
leader_id: architect
structure: hierarchical
version: "1.0.0"

members:
  - developer
  - senior-developer
  - architect

purpose: "Feature development and implementation"
capabilities:
  - feature-development
  - code-review
  - testing
  - planning
```

### Example: team-review (Flat)
```yaml
team_id: team-review
name: Code Review Team
leader_id: reviewer
structure: flat
version: "1.0.0"

members:
  - reviewer
  - senior-developer

purpose: "Code review workflow and quality assurance"
capabilities:
  - code-review
  - quality-assurance
  - feedback
```

### Team Structures

| Structure | Flow | Use Case |
|-----------|------|----------|
| `hierarchical` | Leader → Member → Leader review | Waterfall-style workflows |
| `flat` | Round-robin peer collaboration | Agile/Scrum teams |
| `dynamic` | Context-dependent leadership | Specialized workflows |

---

## System Configuration

### File Location
`ecosystem/config/main.yaml`

### Schema
```yaml
system:
  name: <string>                # System name
  version: <string>             # System version

permissions:                    # Permission defaults
  default_level: basic | extended | admin
  admin_role: <string>

logging:                        # Logging configuration
  level: DEBUG | INFO | WARNING | ERROR
  output: stdout | <file_path>
  enable_logging: true | false
  enable_memory_logging: true | false

agent:                          # Agent defaults
  auto_save_chat_history: true | false
  chat_history_dir: <string>
  max_iter: <integer>           # Max iterations per run (0 = unlimited)

storage:                        # Storage configuration
  backend: json | sqlite
  path: <string>

monitoring:                     # Observability
  open_telemetry: true | false
  phoenix_endpoint: <string>

ecosystem:                      # Ecosystem paths
  skills_path: <string>
  skills_box: <string>
  agents_path: <string>
  tools_path: <string>
  teams_path: <string>
  bootstrap_path: <string>
```

### Example Configuration
```yaml
system:
  name: yukta-ecosystem
  version: "1.0.0"

permissions:
  default_level: basic
  admin_role: system-admin

logging:
  level: INFO
  output: stdout
  enable_logging: true
  enable_memory_logging: true

agent:
  auto_save_chat_history: true
  chat_history_dir: "./chats"
  max_iter: 10

storage:
  backend: json
  path: "./data"

monitoring:
  open_telemetry: false
  phoenix_endpoint: "http://localhost:6007/v1/traces"

ecosystem:
  skills_path: "./ecosystem/skills"
  skills_box: "./ecosystem/skills-box/index.yaml"
  agents_path: "./ecosystem/agents"
  tools_path: "./ecosystem/tools"
  teams_path: "./ecosystem/teams"
  bootstrap_path: "./ecosystem/bootstrap/using-yukta.yaml"
```

---

## Bootstrap Configuration

### File Location
`ecosystem/bootstrap/using-yukta.yaml`

### Schema
```yaml
bootstrap_skill: <skill_id>     # Skill to inject at session start
skill_path: <string>            # Path to skills-box index
inject_at_start: true | false   # Whether to inject at session start
additional_context: <string>    # Extra text to inject (optional)
version: <string>               # Semantic version (default: "1.0.0")
```

### Example Bootstrap Config
```yaml
bootstrap_skill: using-yukta
skill_path: skills-box/index.yaml
inject_at_start: true
version: "1.0.0"
additional_context: |
  You are operating inside the yukta-ecosystem.
  Read skills from the skills/ directory.
  Use the skills-box/index.yaml to discover available skills.
```

### Bootstrap Skill: using-yukta

This skill establishes core ecosystem rules:
- How to find and use skills
- Skill injection format
- Tool execution workflow
- Team participation guidelines

---

## Skills Box Index

### File Location
`ecosystem/skills-box/index.yaml`

### Schema
```yaml
skills:                         # List of available skills
  - id: <skill_id>
    path: <skill_path>
    version: <string>
    categories: [category_1, category_2]
    description: <string>

tools:                          # List of available tools
  - id: <tool_id>
    path: <tool_path>
    version: <string>
    description: <string>

agents:                         # List of available agents
  - id: <agent_id>
    path: <agent_path>
    version: <string>

teams:                          # List of available teams
  - id: <team_id>
    path: <team_path>
```

### Example Index File
```yaml
skills:
  - id: using-yukta
    path: skills/using-yukta/SKILL.md
    version: "1.0.0"
    categories: [bootstrap]
    description: "Use when starting any conversation - establishes how to find and use skills"

  - id: group-collaboration
    path: skills/group-collaboration/SKILL.md
    version: "1.0.0"
    categories: [team]
    description: "Core skill for participating in multi-agent group chats."

  - id: brainstorming
    path: skills/brainstorming/SKILL.md
    version: "1.0.0"
    categories: [process]
    description: "Use before any creative work - explores requirements and proposes solutions"

tools:
  - id: file-editor
    path: tools/file-editor.yaml
    version: "1.0.0"
    description: "Read and write files"

  - id: terminal
    path: tools/terminal.yaml
    version: "1.0.0"
    description: "Execute shell commands"

  - id: git
    path: tools/git.yaml
    version: "1.0.0"
    description: "Git operations"

agents:
  - id: developer
    path: agents/developer.yaml
    version: "1.0.0"

  - id: architect
    path: agents/architect.yaml
    version: "1.0.0"

teams:
  - id: team-dev
    path: teams/team-dev.yaml

  - id: team-review
    path: teams/team-review.yaml
```

---

## Permission Configuration

### File Location
`ecosystem/config/permissions.yaml`

### Schema
```yaml
levels:
  <level_name>:                 # basic, extended, admin
    description: <string>
    permissions:
      - <permission_1>
      - <permission_2>

permission_types:               # All available permission types
  - name: <permission_name>
    description: <string>

temporary_permission_format: <string>
temporary_permission_example: <string>
```

### Example Permissions File
```yaml
# Permission Policies

levels:
  basic:
    description: "Default level - read skills, use assigned tools"
    permissions:
      - skill-read
      - tool-use
      - agent-read
      - team-join

  extended:
    description: "Can create/update tools, self-assign skills"
    permissions:
      - skill-read
      - skill-assign
      - tool-use
      - tool-write
      - agent-read
      - agent-write
      - team-join

  admin:
    description: "Full access to manage agents, skills, tools, permissions"
    permissions:
      - skill-read
      - skill-write
      - skill-assign
      - tool-read
      - tool-write
      - tool-use
      - agent-read
      - agent-write
      - team-read
      - team-lead
      - team-assign
      - team-join
      - create-agent
      - team-membership-manage

permission_types:
  - name: skill-read
    description: "View skill content"
  - name: skill-write
    description: "Create or modify skills"
  - name: skill-assign
    description: "Assign skills to agents"
  - name: tool-read
    description: "View tool definitions"
  - name: tool-write
    description: "Create or modify tools"
  - name: tool-use
    description: "Use specific tools"
  - name: agent-read
    description: "View agent configurations"
  - name: agent-write
    description: "Create or modify agents"
  - name: team-read
    description: "View team configurations"
  - name: team-join
    description: "Join teams"
  - name: team-lead
    description: "Lead teams"
  - name: team-assign
    description: "Assign tasks within a team"
  - name: create-agent
    description: "Create new agents"
  - name: team-membership-manage
    description: "Add/remove team members"

temporary_permission_format: "permission-type:item:expiry-timestamp"
temporary_permission_example: "tool-use-temp:calculator:2026-05-10T18:00:00"
```

### Temporary Permissions

Format: `permission-type:item:expiry-timestamp`

Example: `tool-use-temp:calculator:2026-05-10T18:00:00`

This grants temporary access to the `calculator` tool until the specified timestamp.

---

## Complete Examples

### Full Ecosystem Setup

Here's a complete example of a minimal ecosystem:

```
ecosystem/
├── agents/
│   └── assistant.yaml
├── skills/
│   └── basic-interaction/
│       └── SKILL.md
├── tools/
│   └── echo.yaml
├── tools-impl/
│   └── echo.py
├── teams/
│   └── team-assist.yaml
├── config/
│   ├── main.yaml
│   └── permissions.yaml
├── bootstrap/
│   └── using-yukta.yaml
└── skills-box/
    └── index.yaml
```

### agents/assistant.yaml
```yaml
agent_id: assistant
role: Assistant
level: junior
version: "1.0.0"

skills:
  - using-yukta
  - basic-interaction

tools:
  - echo
  - file-editor

permissions:
  - skill-read
  - tool-use
  - agent-read
  - team-join

behaviors:
  - helpful
  - responsive

team_memberships:
  - team-assist
```

### skills/basic-interaction/SKILL.md
```markdown
---
name: basic-interaction
description: "Use for standard Q&A and information retrieval"
version: "1.0.0"
category: process
---

# Basic Interaction Protocol

## Overview

Standard protocol for answering questions and providing information.

## The Process

1. Understand the user's question
2. Provide clear, concise answer
3. Offer follow-up suggestions if relevant

## Checklist

- [ ] Understood the question
- [ ] Provided clear answer
- [ ] Offered follow-up suggestions
```

### tools/echo.yaml
```yaml
tool_id: echo
description: "Echo back the input string"
function_path: "ecosystem.tools-impl.echo:execute"
parameters:
  - name: message
    type: string
    required: true
    description: "Message to echo back"
returns: string
tool_type: builtin
version: "1.0.0"
```

### tools-impl/echo.py
```python
def execute(message: str) -> dict:
    """Echo the input message back."""
    return {"content": message, "success": True}
```

### teams/team-assist.yaml
```yaml
team_id: team-assist
name: Assistant Team
leader_id: assistant
structure: flat
version: "1.0.0"

members:
  - assistant

purpose: "General assistance and information retrieval"
capabilities:
  - qna
  - information-retrieval
```

### config/main.yaml
```yaml
system:
  name: my-ecosystem
  version: "1.0.0"

permissions:
  default_level: basic
  admin_role: system-admin

logging:
  level: INFO
  output: stdout
  enable_logging: true
  enable_memory_logging: true

agent:
  auto_save_chat_history: true
  chat_history_dir: "./chats"
  max_iter: 5

storage:
  backend: json
  path: "./data"

monitoring:
  open_telemetry: false
  phoenix_endpoint: "http://localhost:6007/v1/traces"

ecosystem:
  skills_path: "./ecosystem/skills"
  skills_box: "./ecosystem/skills-box/index.yaml"
  agents_path: "./ecosystem/agents"
  tools_path: "./ecosystem/tools"
  teams_path: "./ecosystem/teams"
  bootstrap_path: "./ecosystem/bootstrap/using-yukta.yaml"
```

### bootstrap/using-yukta.yaml
```yaml
bootstrap_skill: using-yukta
skill_path: skills-box/index.yaml
inject_at_start: true
version: "1.0.0"
additional_context: |
  You are operating inside the yukta-ecosystem.
  Read skills from the skills/ directory.
```

---

## Validation Rules

All YAML files are validated by `wrapper/validator.py`:

| Entity | Validation Checks |
|--------|-------------------|
| **Agent** | Required fields, valid level, skills/tools exist, valid permissions |
| **Skill** | Required frontmatter fields, description ≤150 chars, non-empty content |
| **Tool** | Required fields, valid parameter types, CUSTOM requires function_path |
| **Team** | Leader exists, all members exist, has at least one member |
| **Config** | Valid log levels, valid paths, proper YAML structure |

---

## Summary

| File | Purpose | Required Fields |
|------|---------|-----------------|
| `agents/{id}.yaml` | Agent persona and capabilities | `agent_id`, `role`, `level` |
| `skills/{id}/SKILL.md` | Reusable workflows | `name`, `description`, `category` |
| `tools/{id}.yaml` | Tool definitions | `tool_id`, `description` |
| `teams/{id}.yaml` | Team structure | `team_id`, `name`, `leader_id`, `structure` |
| `config/main.yaml` | System settings | All sections are optional with defaults |
| `bootstrap/using-yukta.yaml` | Session startup | `bootstrap_skill` |
| `skills-box/index.yaml` | Registry | `skills`, `tools`, `agents`, `teams` |
| `config/permissions.yaml` | Access control | `levels`, `permission_types` |

---

**Version**: 1.0.0  
**Last Updated**: May 2026  
**Ecosystem Version**: yukta-ecosystem v2.1.0
