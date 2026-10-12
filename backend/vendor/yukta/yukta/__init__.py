"""
Yukta Agent System
A structured agent system with system prompts, tool integration,
memory management, and comprehensive logging.
"""

__version__ = "2.1.0"
__author__ = "VCoder4646"

# Import main classes for easy access
from .core.Agent.agent import (
    Agent,
    create_agent
)
from .core.Agent.agent_builder import AgentBuilder
from .core.Agent.agent_callbacks import AgentCallbackHandler
from .config.agent_config import AgentConfig


from .config.system_prompt import (
    SystemPrompt
)

from .tools.tools_pro import (
    Tool,
    ToolParameter,
    ToolProcessor,
    ToolType,
    create_custom_tool
)

from .config.config import Config
from .tools.utils import setup_logging, load_json, save_json

from .core.memory import (
    Memory,
    MemoryConfig,
    create_memory,
    load_memory,
    set_memory_logging_level
)
MEMORY_AVAILABLE = True

from .core.Chat.chat import Chat, ChatManager
CHAT_AVAILABLE = True

# Ecosystem exports - import from ecosystem module
# Note: The ecosystem module is deprecated but still functional
ECOSYSTEM_AVAILABLE = True
try:
    from .ecosystem.loader import (
        load_agent,
        load_skill,
        load_tool,
        load_team,
        list_agents,
        list_skills,
        list_tools,
        list_teams,
    )
except ImportError:
    load_agent = None
    load_skill = None
    load_tool = None
    load_team = None
    list_agents = None
    list_skills = None
    list_tools = None
    list_teams = None
    ECOSYSTEM_AVAILABLE = False

# API exports (from yukta.api) - for ecosystem operations
try:
    from .api import (
        validate_ecosystem,
        load_ecosystem,
        load_skills_from_index,
        load_all_tools,
        load_all_agents,
        load_all_teams,
        run_agent,
        build_and_run_agent,
    )
    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False

__all__ = [
    # Agent classes
    "Agent",
    "AgentBuilder",
    "AgentCallbackHandler",
    "AgentConfig",
    "create_agent",

    # System prompt classes
    "SystemPrompt",

    # Tool classes
    "Tool",
    "ToolParameter",
    "ToolProcessor",
    "ToolType",
    "create_custom_tool",

    # Memory classes
    "Memory",
    "MemoryConfig",
    "create_memory",
    "load_memory",
    "set_memory_logging_level",

    # Chat classes
    "Chat",
    "ChatManager",

    # Config and utils
    "Config",
    "setup_logging",
    "load_json",
    "save_json",

    # Availability flags
    "MEMORY_AVAILABLE",
    "CHAT_AVAILABLE",
    "ECOSYSTEM_AVAILABLE",
    "API_AVAILABLE",

    # Ecosystem (optional) - from ecosystem.loader
    "load_agent",
    "load_skill",
    "load_tool",
    "load_team",
    "list_agents",
    "list_skills",
    "list_tools",
    "list_teams",

    # API (optional) - from yukta.api
    "validate_ecosystem",
    "load_ecosystem",
    "load_skills_from_index",
    "load_all_tools",
    "load_all_agents",
    "load_all_teams",
    "run_agent",
    "build_and_run_agent",

    # Version and utilities
    "get_version",
    "quick_start",
]


def get_version():
    """Get the current version of the Yukta Agent System."""
    return __version__


def quick_start():
    """
    Quick start guide for new users.
    Prints basic usage information.
    """
    print(f"""
Yukta Agent System v{__version__}
{'=' * 50}

Quick Start:

1. Create a basic agent:
   from agent import create_agent
   agent = create_agent("MyAgent", "yukta")

2. Use agent builder:
   from agent import AgentBuilder
   agent = AgentBuilder().with_name("Agent").with_default_prompt("general_assistant").build()

3. Add custom tools:
   from tools_pro import create_custom_tool
   tool = create_custom_tool("my_tool", "Description", [...])
   agent.add_tool(tool)

4. Create agent with memory and logging:
   from agent import create_agent, AgentConfig
   from memory import create_memory
   import logging
   
   config = AgentConfig(
       log_level=logging.INFO,
       enable_logging=True,
       auto_save_chat=True,
       memory_log_level=logging.INFO
   )
   
   agent = create_agent("MyAgent", config=config)
   memory = create_memory("You are a helpful assistant.", max_tokens=1000)
   agent.set_memory(memory)

5. Use invoke method:
   result = agent.invoke("What's the weather?")

New Features:
✨ invoke() method - Flexible agent invocation (3 modes)
📝 Comprehensive logging - Agent and memory operations
💾 Auto-save chat - Session persistence
🧠 Memory module - Smart conversation management
📊 KV cache tracking - Cost optimization

Documentation:
- README.md - Overview and quick reference
- AGENT_LOGGING_DOCS.md - Logging configuration
- MEMORY_LOGGING_DOCS.md - Memory logging guide
- INVOKE_METHOD_DOCS.md - Invoke method details
- KV_CACHE_GUIDE.md - Cache optimization

Examples:
- example_agent_logging.py
- example_agent_memory_logging.py
- example_memory_logging.py
- example_invoke.py

{'=' * 50}
    """)


# Print version on import (optional - can be removed if not desired)
# print(f"Yukta Agent System v{__version__} loaded")
