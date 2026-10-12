# Quick YAML Reference Guide

A quick lookup reference for common YAML patterns in yukta-ecosystem.

---

## Agent Configuration

### Minimal Agent (Junior)
```yaml
agent_id: my-agent
role: My Agent
level: junior
version: "1.0.0"

skills:
  - using-yukta

tools:
  - file-editor

permissions:
  - skill-read
  - tool-use
  - agent-read
  - team-join

behaviors:
  - helpful
```

### Senior Agent with Self-Assignment
```yaml
agent_id: senior-dev
role: Senior Developer
level: senior
version: "1.0.0"

skills:
  - using-yukta
  - test-driven-development
  - systematic-debugging

tools:
  - file-editor
  - terminal
  - git

permissions:
  - skill-read
  - skill-assign
  - tool-use
  - tool-write
  - agent-read

behaviors:
  - methodical
  - test-first
```

### Lead Agent (Full Autonomy)
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

behaviors:
  - strategic
  - decision-making

team_memberships:
  - team-dev

team_leads:
  - team-dev
```

---

## Skill Configuration

### Basic Skill
```markdown
---
name: my-skill
description: "Short description under 150 chars"
version: "1.0.0"
category: process
---

# My Skill

## Overview
What this skill does.

## When to Use
When to invoke this skill.

## Checklist
- [ ] Step 1
- [ ] Step 2
```

### Advanced Skill with Process
```markdown
---
name: my-workflow
description: "Comprehensive workflow description"
version: "1.0.0"
category: implementation
---

# My Workflow

## Overview
Detailed overview here.

## When to Use
Specific scenarios for this skill.

## The Process

### Step 1: First Phase
Detailed instructions for step 1.

### Step 2: Second Phase
Detailed instructions for step 2.

## Checklist
- [ ] Verify first phase
- [ ] Verify second phase
- [ ] Final review
```

---

## Tool Configuration

### Simple Tool
```yaml
tool_id: my-tool
description: "What this tool does"
function_path: "ecosystem.tools-impl.my_tool:execute"
parameters:
  - name: input
    type: string
    required: true
    description: "Input parameter"
returns: string
tool_type: builtin
version: "1.0.0"
```

### Tool with Optional Parameters
```yaml
tool_id: advanced-tool
description: "Tool with optional parameters"
function_path: "ecosystem.tools-impl.advanced_tool:execute"
parameters:
  - name: required_field
    type: string
    required: true
    description: "Required parameter"
  - name: optional_field
    type: string
    required: false
    description: "Optional parameter with default"
    default: "default_value"
  - name: choice_field
    type: string
    required: false
    description: "Parameter with limited choices"
    enum: ["option1", "option2", "option3"]
returns: string
tool_type: builtin
version: "1.0.0"
```

### Custom Tool
```yaml
tool_id: custom-calculator
description: "Custom calculator tool"
function_path: "ecosystem.tools-impl.calculator:execute"
parameters:
  - name: operation
    type: string
    required: true
    description: "Operation to perform"
  - name: a
    type: number
    required: true
    description: "First number"
  - name: b
    type: number
    required: true
    description: "Second number"
returns: number
tool_type: custom
version: "1.0.0"
```

---

## Team Configuration

### Hierarchical Team
```yaml
team_id: team-hierarchical
name: Hierarchical Team
leader_id: lead-agent
structure: hierarchical
version: "1.0.0"

members:
  - junior-agent
  - senior-agent

purpose: "Waterfall-style development workflow"
capabilities:
  - planning
  - execution
  - review
```

### Flat Team
```yaml
team_id: team-flat
name: Flat Team
leader_id: lead-agent
structure: flat
version: "1.0.0"

members:
  - junior-agent
  - senior-agent
  - lead-agent

purpose: "Collaborative peer review workflow"
capabilities:
  - collaboration
  - code-review
  - decision-making
```

---

## Configuration Files

### Main Configuration (minimal)
```yaml
agent:
  max_iter: 10
  auto_save_chat_history: true
```

### Main Configuration (complete)
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

### Bootstrap Configuration
```yaml
bootstrap_skill: using-yukta
skill_path: skills-box/index.yaml
inject_at_start: true
version: "1.0.0"
```

---

## Skills Box Index

```yaml
skills:
  - id: using-yukta
    path: skills/using-yukta/SKILL.md
    version: "1.0.0"
    categories: [bootstrap]
    description: "Bootstraps the ecosystem"

tools:
  - id: file-editor
    path: tools/file-editor.yaml
    version: "1.0.0"
    description: "Read and write files"

agents:
  - id: developer
    path: agents/developer.yaml
    version: "1.0.0"

teams:
  - id: team-dev
    path: teams/team-dev.yaml
```

---

## Permission Levels

### Basic Level (Default)
```yaml
levels:
  basic:
    permissions:
      - skill-read
      - tool-use
      - agent-read
      - team-join
```

### Extended Level
```yaml
levels:
  extended:
    permissions:
      - skill-read
      - skill-assign
      - tool-use
      - tool-write
      - agent-read
      - agent-write
      - team-join
```

### Admin Level
```yaml
levels:
  admin:
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
```

---

## Tool Implementation (Python)

### Basic Implementation
```python
def execute(param1: str, param2: int = 0) -> dict:
    """Execute the tool and return result."""
    try:
        # Tool logic here
        result = f"Processed: {param1} with {param2}"
        return {"content": result, "success": True}
    except Exception as e:
        return {"error": str(e), "success": False}
```

### File Editor Implementation
```python
import os

def execute(action: str, path: str, content: str = None) -> dict:
    """Read or write files on the filesystem."""
    try:
        path = os.path.abspath(path)
        
        if action == "read":
            if not os.path.exists(path):
                return {"error": f"File not found: {path}", "success": False}
            with open(path, "r", encoding="utf-8") as f:
                return {"content": f.read(), "success": True}
        
        elif action == "write":
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content if content is not None else "")
            return {"message": f"Successfully wrote to {path}", "success": True}
        
        else:
            return {"error": f"Invalid action: {action}", "success": False}
    
    except Exception as e:
        return {"error": str(e), "success": False}
```

---

## Common Patterns

### Agent with All Default Skills
```yaml
agent_id: full-agent
role: Full Agent
level: senior
version: "1.0.0"

skills:
  - using-yukta
  - brainstorming
  - writing-plans
  - executing-plans
  - systematic-debugging
  - test-driven-development
  - verification-before-completion

tools:
  - file-editor
  - terminal
  - git
  - search

permissions:
  - skill-read
  - skill-assign
  - tool-use
  - tool-write
  - agent-read

behaviors:
  - methodical
  - thorough
```

### Team with Multiple Members
```yaml
team_id: full-team
name: Full Development Team
leader_id: architect
structure: hierarchical
version: "1.0.0"

members:
  - developer
  - senior-developer
  - reviewer
  - devops

purpose: "Complete development lifecycle from planning to deployment"
capabilities:
  - planning
  - development
  - review
  - deployment
```

---

## Validation

### Quick Validation Checklist

| Entity | Required Fields | Common Errors |
|--------|-----------------|---------------|
| Agent | `agent_id`, `role`, `level` | Missing level, invalid level value |
| Skill | `name`, `description`, `category` | Description too long (>150 chars) |
| Tool | `tool_id`, `description` | Missing parameters, invalid type |
| Team | `team_id`, `name`, `leader_id`, `structure` | Leader not in members |

---

**Version**: 1.0.0  
**Quick Reference**: YAML Patterns for yukta-ecosystem
