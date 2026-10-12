"""
Templates for ecosystem initialization.
These are used by `yukta ecosystem init` to create new ecosystem projects.
"""

def get_agent_template(project_name: str) -> str:
    """Generate agent template with project name."""
    return f"""---
# Agent Configuration Template
# Edit this file to define your agent

agent_id: my-agent
role: Developer
level: junior
version: "1.0.0"

# Skills this agent can use
skills:
  - skill-name

# Tools available to this agent
tools:
  - my-tool

# Permissions for this agent
permissions:
  - skill-read
  - tool-use
  - agent-read
  - team-join

# Behaviors/traits for this agent
behaviors:
  - helpful
"""


def get_skill_template(project_name: str) -> str:
    """Generate skill template with project name."""
    return """---
name: skill-name
description: "Describe what this skill does"
version: "1.0.0"
category: process
---

# Skill Name

## Overview
This skill provides a structured workflow for [your use case].

## When to Use
Use this skill when you need to [specific scenario].

## The Process

### Step 1: First Phase
Detailed instructions for step 1.

### Step 2: Second Phase
Detailed instructions for step 2.

## Checklist
- [ ] Verify first phase
- [ ] Verify second phase
- [ ] Final review
"""


def get_tool_template(project_name: str) -> str:
    """Generate tool template with project name."""
    return f"""---
# Tool Descriptor Template
# Defines a tool that agents can use

tool_id: my-tool
description: "Describe what this tool does"
function_path: "{project_name}.tools_impl.tool_impl:my_tool"

# Parameters this tool accepts
parameters:
  - name: param1
    type: string
    required: true
    description: "Description of param1"
  - name: param2
    type: integer
    required: false
    description: "Description of param2 (optional)"

returns: string
tool_type: custom
version: "1.0.0"
"""


def get_tool_impl_template(project_name: str) -> str:
    """Generate tool implementation template with project name."""
    return f'''"""Tool Implementations for {project_name} ecosystem.
Add your tool functions here.

Function format:
def my_tool(param1: str, param2: int = None) -> str:
    \'\'\'Tool description\'\'\'
    # Implementation
    return result
"""


def {project_name}_my_tool(param1: str, param2: int = None) -> str:
    """
    My custom tool.
    
    Args:
        param1: Description of param1
        param2: Description of param2 (optional)
    
    Returns:
        Description of return value
    """
    # TODO: Implement your tool logic here
    result = f"Tool executed with param1={{param1}}, param2={{param2}}"
    return result


# Add more tools below:
# def another_tool(...) -> str:
#     ...
'''


def get_team_template(project_name: str) -> str:
    """Generate team template with project name."""
    return """---
# Team Configuration Template

team_id: my-team
name: "My Team"
leader_id: my-agent
structure: hierarchical
version: "1.0.0"

members:
  - my-agent

purpose: "Example team configuration"
capabilities:
  - collaboration
"""


def get_config_template(project_name: str) -> str:
    """Generate config template with project name."""
    return f"""---
# Ecosystem Configuration

system:
  name: {project_name}
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
  skills_path: "./skills"
  skills_box: "./skills-box/index.yaml"
  agents_path: "./agents"
  tools_path: "./tools"
  teams_path: "./teams"
  bootstrap_path: "./bootstrap/using-yukta.yaml"
"""


def get_index_template(project_name: str) -> str:
    """Generate index template with project name."""
    return """---
# Skills Box Index
# Auto-generated file - do not edit manually

skills:
  - id: skill-name
    path: skills/skill-name/SKILL.md
    version: "1.0.0"
    categories: [process]
    description: "Description of the skill"

tools:
  - id: my-tool
    path: tools/my-tool.yaml
    version: "1.0.0"
    description: "Description of the tool"

agents:
  - id: my-agent
    path: agents/my-agent.yaml
    version: "1.0.0"

teams:
  - id: my-team
    path: teams/my-team.yaml
"""


def get_bootstrap_template(project_name: str) -> str:
    """Generate bootstrap template with project name."""
    return f"""---
bootstrap_skill: using-yukta
skill_path: skills-box/index.yaml
inject_at_start: true
version: "1.0.0"
"""


def get_readme_template(project_name: str) -> str:
    """Generate README template with project name."""
    return f"""\
# {project_name}

Ecosystem project created with Yukta.

## Structure

```
{project_name}/
├── agents/          # Agent configurations
├── skills/          # Skill workflows
├── tools/          # Tool descriptors
├── tools-impl/     # Tool implementations
├── teams/          # Team configurations
├── skills-box/     # Index (auto-generated)
├── config/         # Configuration
└── build/         # Compiled ecosystem (auto-generated)
```

## Getting Started

1. Edit the agent configuration in `agents/agent.yaml`
2. Customize skills in `skills/skill-name/SKILL.md`
3. Define tools in `tools/tool.yaml` and implement in `tools-impl/tool_impl.py`
4. Validate: `yukta ecosystem validate ./`
5. Use: `from yukta import load_agent`

## Compile

After validation, the ecosystem is compiled to `build/ecosystem.yaml`.
Use this file for fast loading.

## Documentation

See the Yukta documentation for more details:
https://github.com/VCoder4646/yukta
"""


# Legacy templates (for backward compatibility)
AGENT_TEMPLATE = get_agent_template("my_ecosystem")
SKILL_TEMPLATE = get_skill_template("my_ecosystem")
TOOL_TEMPLATE = get_tool_template("my_ecosystem")
TOOL_IMPL_TEMPLATE = get_tool_impl_template("my_ecosystem")
TEAM_TEMPLATE = get_team_template("my_ecosystem")
CONFIG_TEMPLATE = get_config_template("my_ecosystem")
INDEX_TEMPLATE = get_index_template("my_ecosystem")
README_TEMPLATE = get_readme_template("my_ecosystem")

__all__ = [
    "get_agent_template",
    "get_skill_template",
    "get_tool_template",
    "get_tool_impl_template",
    "get_team_template",
    "get_config_template",
    "get_index_template",
    "get_readme_template",
]