# Yukta - Quick Import Reference

## Package Layout
```
yukta/
├── core/       # Agent, Memory, Message, LLMClient
├── tools/      # ToolProcessor, Tool, Utils
├── config/     # Config, SystemPrompt
└── cli/        # Chat, ChatManager
```

## Common Imports

### Option 1: Use convenience imports from main package
```python
from yukta import (
    Agent, AgentBuilder, AgentConfig,
    Memory, MemoryConfig,
    SystemPrompt, SystemPromptLibrary,
    Tool, ToolProcessor, ToolType,
    Config, Chat
)
```

### Option 2: Import from specific modules
```python
# Core functionality
from yukta.core import Agent, Memory, Message, LLMClient

# Tools
from yukta.tools import ToolProcessor, Tool, ToolType, setup_logging

# Configuration
from yukta.config import Config, SystemPrompt

# CLI
from yukta.cli import Chat, ChatManager
```

## Quick Examples

### Create Agent
```python
from yukta import create_agent
agent = create_agent("MyAgent", "yukta")
```

### Create Agent with Memory
```python
from yukta import create_agent, create_memory

agent = create_agent("MyAgent")
memory = create_memory("You are helpful.", max_tokens=1000)
agent.set_memory(memory)
```

### Custom System Prompt
```python
from yukta.config import SystemPrompt

prompt = SystemPrompt("agent_name", "Custom instructions here")
```

### Working with JSON in Prompts
The formatter intelligently handles JSON and other content with braces. Only valid Python identifiers in braces are treated as variables - everything else (including JSON) is left unchanged.

```python
from yukta.config import SystemPrompt

# ✅ JSON works naturally without any escaping!
prompt = SystemPrompt(
    "DataAgent",
    """Return JSON with this structure:
    {
      "status": "success",
      "data": {output_data},
      "count": 0
    }
    
    Input: {user_input}"""
)

# Only {output_data} and {user_input} are replaced
result = prompt.get_prompt(
    output_data='[1, 2, 3]',
    user_input='find all items'
)
# Output JSON stays intact, variables are replaced
```

**Key Rule:** Only `{valid_python_identifier}` is replaced. Everything else (like `{"key": "value"}`) is untouched.

## Installation

### Development Mode
```bash
pip install -e .
```

### With Optional Dependencies
```bash
# All extras
pip install -e ".[all]"

# Specific extras
pip install -e ".[dev,llm,data]"
```

## Module Purpose

| Module | Purpose |
|--------|---------|
| `core` | Core agent functionality (Agent, Memory, Message, LLMClient) |
| `tools` | Tool processing and utility functions |
| `config` | Configuration and system prompt management |
| `cli` | Command-line interface and chat management |

## File Locations

| File | Old Location | New Location |
|------|-------------|--------------|
| agent.py | root | yukta/core/ |
| memory.py | root | yukta/core/ |
| message.py | root | yukta/core/ |
| llm_client.py | root | yukta/core/ |
| tools_pro.py | root | yukta/tools/ |
| utils.py | root | yukta/tools/ |
| config.py | root | yukta/config/ |
| system_prompt.py | root | yukta/config/ |
| chat.py | root | yukta/cli/ |

## Context Window Management

### Automatic Context Trimming
The framework automatically manages token limits using a **sliding window** mechanism when conversation history exceeds the model's context window.

```python
# NO CONFIGURATION NEEDED!
# Agent automatically:
# 1. Fetches model context size from vLLM
# 2. Tracks cumulative tokens
# 3. Removes old messages when approaching limit
# 4. Preserves system prompt and recent context

agent = create_agent("MyAgent", "MyRole")
# Chat will automatically trim old messages if needed!
```

### How It Works
- **Default**: 8192 token context, 512 token output buffer
- **Trimming**: Removes oldest messages first (keeps system prompt)
- **Logging**: Shows what was trimmed and final token count
- **Automatic**: Triggered in `get_messages()` before sending to LLM

### Example: Custom Configuration
```python
from yukta import Chat

# If you're creating Chat manually
chat = Chat(
    system_prompt="You are a helpful assistant",
    context_window=8192,     # Model's max context
    context_buffer=512       # Space reserved for output
)
# Available for input: 7680 tokens (8192 - 512)
```

### Monitoring Token Usage
```python
# After agent runs, check statistics
print(f"Total tokens used: {agent.chat.stats['total_tokens']}")
print(f"Messages trimmed: {agent.chat.stats['messages_trimmed']}")
print(f"Max input allowed: {agent.chat.max_input_tokens}")
```

### Why This Matters
✅ No more "context exceeded" errors  
✅ Long conversations work automatically  
✅ System prompt always preserved  
✅ Recent messages kept for coherence  
✅ Full visibility in logs  

See `CONTEXT_WINDOW_MANAGEMENT.md` for detailed documentation.

## Key Benefits
✅ Professional package structure
✅ Clear module organization
✅ Easy to install and distribute
✅ Better IDE support and autocomplete
✅ Scalable architecture
✅ Proper namespace management
✅ **Automatic context window management** - never exceed token limits!

## Need Help?
- See `PROJECT_STRUCTURE.md` for detailed documentation
- See `README.md` for feature overview
- See `CONTEXT_WINDOW_MANAGEMENT.md` for token limit handling
- Check `examples/sample.py` for usage examples
