# Yukta - Project Structure

## Overview
This document describes the structured package layout of the Yukta agent system.

## Directory Structure

```
Yukta/
│
├── yukta/              # Main package directory
│   ├── __init__.py            # Package initialization and exports
│   │
│   ├── core/                  # Core functionality
│   │   ├── __init__.py       # Core module exports
│   │   ├── agent.py          # Agent class and builder
│   │   ├── memory.py         # Memory management with KV cache
│   │   ├── message.py        # Message handling
│   │   └── llm_client.py     # LLM client implementations
│   │
│   ├── tools/                 # Tools and utilities
│   │   ├── __init__.py       # Tools module exports
│   │   ├── tools_pro.py      # Tool processing and utilities
│   │   └── utils.py          # Helper utilities
│   │
│   ├── config/                # Configuration and prompts
│   │   ├── __init__.py       # Config module exports
│   │   ├── config.py         # Configuration management
│   │   └── system_prompt.py  # System prompt templating
│   │
│   └── cli/                   # Command-line interface
│       ├── __init__.py       # CLI module exports
│       └── chat.py           # Chat management
│
├── examples/                  # Example scripts and usage
│   ├── __init__.py
│   └── sample.py             # Sample implementation
│
├── tests/                     # Test suite
│   └── __init__.py
│
├── docs/                      # Documentation (if applicable)
│
├── README.md                  # Project overview and quick start
├── requirements.txt           # Python dependencies
├── setup.py                   # Package installation setup
├── pyproject.toml            # Modern Python packaging config
├── MANIFEST.in               # Package distribution files
├── .gitignore                # Git ignore patterns
└── PROJECT_STRUCTURE.md      # This file

```

## Module Organization

### Core Module (`yukta.core`)
Contains the fundamental components of the agent system:
- **Agent**: Main agent class with tools integration
- **Memory**: Smart memory management with persistence
- **Message**: Message formatting and handling
- **LLMClient**: Low-level LLM communication

### Tools Module (`yukta.tools`)
Tools and utility functions:
- **ToolProcessor**: Tool management and execution
- **Utils**: Logging, JSON handling, and helpers

### Config Module (`yukta.config`)
Configuration and system prompts:
- **Config**: Environment and settings management
- **SystemPrompt**: Flexible prompt templating

### CLI Module (`yukta.cli`)
Command-line and chat interfaces:
- **Chat**: Conversation management and persistence

## Installation

### From Source
```bash
# Clone the repository
git clone https://github.com/VCoder4646/yukta.git
cd yukta

# Install in development mode
pip install -e .

# Or install with extras
pip install -e ".[dev,llm,data]"
```

### Using pip (when published)
```bash
pip install yukta
```

## Usage

### Basic Import
```python
from yukta import Agent, Memory, SystemPrompt
from yukta.tools import ToolProcessor
from yukta.config import Config
```

### Using Submodules
```python
# Import from core
from yukta.core import Agent, Memory, Message, LLMClient

# Import from tools
from yukta.tools import ToolProcessor, Tool, ToolType

# Import from config
from yukta.config import SystemPrompt, Config

# Import from CLI
from yukta.cli import Chat, ChatManager
```

### Quick Start Example
```python
from yukta import create_agent, create_memory

# Create agent with memory
agent = create_agent("MyAgent", "yukta")
memory = create_memory("You are a helpful assistant.", max_tokens=1000)
agent.set_memory(memory)

# Use the agent
result = agent.invoke("Hello!")
print(result)
```

## Package Features

### Modular Design
- Clean separation of concerns
- Independent, reusable components
- Well-defined interfaces

### Professional Structure
- Standard Python package layout
- Proper namespace organization
- Comprehensive `__init__.py` files

### Easy Installation
- `setup.py` for package installation
- `pyproject.toml` for modern tooling
- Optional dependencies for different use cases

### Development Ready
- Test directory structure
- Examples directory with samples
- Documentation support

## Development

### Running Tests
```bash
pytest tests/
```

### Code Formatting
```bash
black yukta/
```

### Type Checking
```bash
mypy yukta/
```

### Building Distribution
```bash
python setup.py sdist bdist_wheel
```

## Migration Guide

If you were using the flat structure before, update your imports:

### Old Imports
```python
from agent import Agent
from memory import Memory
from tools_pro import ToolProcessor
```

### New Imports
```python
from yukta.core import Agent, Memory
from yukta.tools import ToolProcessor
```

Or use the convenience imports:
```python
from yukta import Agent, Memory, ToolProcessor
```

## Benefits of This Structure

1. **Scalability**: Easy to add new modules and features
2. **Maintainability**: Clear organization improves code navigation
3. **Professionalism**: Standard Python package structure
4. **Testability**: Isolated components are easier to test
5. **Distribution**: Ready for PyPI publication
6. **Documentation**: Better for auto-generated docs
7. **Collaboration**: Easier for teams to work on different modules

## Version Information

- Current Version: 2.1.0
- Python Requirements: >=3.8
- Package Status: Beta

## Support

For issues, questions, or contributions, please visit:
- GitHub: https://github.com/VCoder4646/yukta
- Issues: https://github.com/VCoder4646/yukta/issues
