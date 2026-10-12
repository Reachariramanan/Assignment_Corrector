# Yukta — Modular AI Agent Framework

**Version:** 2.1.0 | **Python:** ≥ 3.8 | **License:** MIT

Yukta is a Python framework for building production-grade AI agents. It provides a composable runtime with pluggable LLM backends, a structured tool system, smart memory management, multi-agent team orchestration, a declarative ecosystem format, and full OpenTelemetry tracing — all wired together through a clean, consistent API.

---

## Table of Contents

1. [Installation](#installation)
2. [Package Layout](#package-layout)
3. [Quick Start](#quick-start)
4. [Core Concepts](#core-concepts)
   - [Agent](#agent)
   - [SystemPrompt](#systemprompt)
   - [AgentConfig](#agentconfig)
   - [LLM Clients](#llm-clients)
   - [Tools](#tools)
   - [Memory](#memory)
   - [Callbacks](#callbacks)
   - [Storage](#storage)
5. [Ecosystem](#ecosystem)
   - [CLI](#cli)
   - [Project Structure](#ecosystem-project-structure)
   - [Python API](#ecosystem-python-api)
   - [Team Orchestration](#team-orchestration)
6. [Instrumentation and Tracing](#instrumentation-and-tracing)
7. [Environment Variables](#environment-variables)
8. [Testing](#testing)
9. [Contributing](#contributing)

---

## Installation

```bash
# Standard install
pip install yukta

# Development install (editable, includes test tools)
git clone https://github.com/VCoder4646/yukta.git
cd yukta
pip install -e ".[dev]"
```

Verify the installation:

```bash
python -c "import yukta; print(yukta.__version__)"
```

---

## Package Layout

```
yukta/
├── core/
│   ├── Agent/          # Agent runtime, builder, callbacks
│   ├── Chat/           # Chat sessions, message management, LLMResponse
│   ├── Clients/        # LLM backend clients (Ollama, vLLM, HF, etc.)
│   ├── memory.py       # Memory manager with overflow and archiving
│   └── storage.py      # JSON file storage backend, StorageCorruptionError
├── config/
│   ├── agent_config.py # AgentConfig — all agent tunables
│   ├── memory_config.py# MemoryConfig — memory limits and storage
│   ├── system_prompt.py# SystemPrompt — templated system messages
│   └── config.py       # Config — global paths (YUKTA_DATA_DIR)
├── tools/
│   ├── tool.py         # Tool, ToolParameter, ToolType dataclasses
│   ├── tools_pro.py    # ToolProcessor — execution engine, parallel mode
│   ├── mcp_tool.py     # MCP (Model Context Protocol) remote tools
│   ├── sandbox.py      # Sandboxed tool execution via subprocess
│   └── utils.py        # Logging setup, JSON helpers
├── api/
│   ├── models.py       # Ecosystem data models (AgentData, ToolData, …)
│   ├── reader.py       # Parse ecosystem YAML/Markdown files
│   ├── validator.py    # Validate ecosystem structure and cross-references
│   ├── transformer.py  # Convert ecosystem objects → yukta runtime objects
│   ├── compiler.py     # Compile ecosystem → build/ecosystem.yaml
│   ├── loader.py       # O(1) cached load_agent / load_tool / …
│   ├── runner.py       # run_agent, run_tool, build_and_run_agent
│   ├── allocator.py    # Skill and task allocation helpers
│   ├── orchestrator.py # Multi-agent group chat (SpeakerSelector, GroupChatSession)
│   ├── coordinator.py  # Leader-driven team coordination (LeaderCoordinator)
│   └── modern_logger.py# Coloured structured logging helpers
├── ecosystem/          # Legacy loader/resolver (still functional)
├── cli/
│   ├── main.py         # Click CLI (yukta init / validate / tool run)
│   └── templates.py    # Scaffold templates for ecosystem projects
└── instrumentation/
    ├── tracer.py       # YuktaTracer — OpenTelemetry span management
    ├── decorators.py   # @trace_yukta decorator
    ├── tracing.py      # Phoenix / OTLP setup helpers
    └── extractors.py   # Span attribute extractors
```

---

## Quick Start

```python
from yukta import create_agent, SystemPrompt
from yukta.core.Clients.ollama_client import OllamaClient

agent = create_agent(
    name="Assistant",
    system_prompt=SystemPrompt("Assistant", "You are a helpful assistant."),
    llm_client=OllamaClient(model_name="llama3"),
)

response = agent.invoke("What is the capital of France?")
print(response)  # "Paris"
```

---

## Core Concepts

### Agent

`Agent` is the central runtime class. It manages the conversation loop, calls the LLM, dispatches tool calls, tracks history, and emits lifecycle events.

#### `create_agent` — functional constructor

```python
from yukta import create_agent, SystemPrompt, AgentConfig
from yukta.core.Clients.vllm_client import VLLMClient

agent = create_agent(
    name="Coder",
    system_prompt=SystemPrompt("Coder", "You are an expert Python developer."),
    llm_client=VLLMClient("qwen36-35b", base_url="http://192.168.200.23:11642/v1"),
    config=AgentConfig(verbose=True, max_iter=15),
)
```

#### `AgentBuilder` — fluent builder

```python
from yukta import AgentBuilder, SystemPrompt
from yukta.core.Clients.ollama_client import OllamaClient

agent = (
    AgentBuilder()
    .with_name("ResearchBot")
    .with_default_prompt(SystemPrompt("ResearchBot", "You are a research assistant."))
    .with_llm_client(OllamaClient("mistral"))
    .with_permission_level("extended")
    .build()
)
```

#### `Agent.run()` — full execution loop

```python
result = agent.run(
    user_message="Summarise the latest news on AI.",
    reset_conversation=False,
    llm_kwargs={"temperature": 0.2, "top_p": 0.9},   # forwarded to every LLM call this turn
)
# result keys: success, response, iterations, tool_calls, errors, tokens_used
print(result["response"])
```

#### `Agent.invoke()` — simplified interface

```python
# Mode 1: LLM reasoning with automatic tool calls (default)
response = agent.invoke("What files are in /tmp?")

# Mode 2: Call a specific tool directly, no LLM involved
result = agent.invoke(
    input="List files",
    tool_name="list_directory",
    tool_arguments={"path": "/tmp"},
    use_llm=False,
)

# Mode 3: Text generation only, tools suppressed
response = agent.invoke("Write a haiku about the ocean.", use_llm=True)

# Per-call generation parameters
response = agent.invoke(
    "Draft a cover letter.",
    llm_kwargs={"temperature": 0.8, "seed": 42},
)

# Return full metadata
result = agent.invoke("Explain recursion.", return_full_response=True)
# result["mode"], result["success"], result["response"], …
```

#### Other Agent methods

| Method | Description |
|--------|-------------|
| `agent.add_tool(tool)` | Register a Tool at runtime |
| `agent.remove_tool(name)` | Deregister a tool by name |
| `agent.set_llm_client(client)` | Swap LLM client without rebuilding |
| `agent.set_memory(memory)` | Attach or replace Memory instance |
| `agent.send_message(text)` | Thin chat wrapper — returns response string |
| `agent.clear_conversation()` | Wipe message history, keep system prompt |
| `agent.save_memory(force=True)` | Flush memory session to disk |
| `agent.get_stats()` | Token usage, iteration counts, cache hits |

---

### SystemPrompt

`SystemPrompt` wraps prompt text with optional variable templating. JSON-style braces (`{"key": "val"}`) are left untouched — only valid Python identifiers inside braces are substituted.

```python
from yukta import SystemPrompt

prompt = SystemPrompt(
    prompt_name="DataAgent",
    prompt_text="""You are a data analyst.
Always return results as JSON matching this schema: {"result": array, "count": number}.
Today's date is {today}. User context: {context}""",
    variables={"today": "2026-05-25"},
    metadata={"version": "1.0", "author": "VCoder4646"},
)

# Variable substitution — JSON braces untouched
system_text = prompt.get_prompt(context="sales data for Q1")

# Update or add variables
prompt.add_variables(today="2026-06-01")

# Inspect
print(prompt.get_info())  # name, created_at, variables list, metadata, length
```

---

### AgentConfig

`AgentConfig` controls every tunable of the agent runtime.

```python
from yukta import AgentConfig
import logging

config = AgentConfig(
    # Sampling (validated: 0.0 – 2.0)
    temperature=0.7,

    # Iteration guard (0 = unlimited; validated >= 0)
    max_iter=10,

    # History cap — oldest messages pruned first (validated >= 1)
    max_history=1000,

    # Security — raise UserWarning for dynamic tools without sandbox
    require_sandbox=True,

    # Chat persistence
    auto_save_chat_history=True,
    chat_history_dir="",           # defaults to YUKTA_DATA_DIR/chat_history

    # Logging
    log_level=logging.INFO,
    enable_logging=True,
    memory_log_level=logging.DEBUG,
    enable_memory_logging=True,
    log_file=None,                 # set a path to also write logs to file

    # Parallel tool execution
    enable_parallel_tools=False,
    parallel_tool_workers=3,

    # Output
    verbose=False,
)
```

`AgentConfig` raises `ValueError` at construction if `temperature`, `max_iter`, or `max_history` are out of range.

---

### LLM Clients

All clients extend `BaseLLMClient` and expose an identical `generate()` interface. Any keyword arguments passed at construction time that are not internal config keys (`api_key`, `timeout`, `max_retries`, etc.) are treated as generation defaults and forwarded to the API on every call.

#### Available clients

| Class | Backend | Default URL |
|-------|---------|-------------|
| `OllamaClient` | Ollama local server | `http://localhost:11434` |
| `VLLMClient` | vLLM OpenAI-compatible server | `http://192.168.200.23:11642/v1` |
| `SGLangClient` | SGLang server | `http://localhost:30000` |
| `LMStudioClient` | LM Studio local server | `http://localhost:1234` |
| `HuggingFaceClient` | HF Inference Endpoints / Serverless | `https://router.huggingface.co/hf-inference` |
| `RemoteEndpointClient` | Any OpenAI-compatible endpoint | user-supplied |

#### Direct construction

```python
from yukta.core.Clients.ollama_client import OllamaClient
from yukta.core.Clients.vllm_client import VLLMClient
from yukta.core.Clients.hf_client import HuggingFaceClient
from yukta.core.Clients.remote_client import RemoteEndpointClient

# Ollama — generation params go into options{} automatically
ollama = OllamaClient(
    model_name="llama3",
    temperature=0.5,
    options={"num_ctx": 8192, "top_p": 0.9},  # passed directly to Ollama options
)

# vLLM — params go top-level into the OpenAI-compatible payload
vllm = VLLMClient(
    model_name="qwen36-35b",
    base_url="http://192.168.200.23:11642/v1",
    temperature=0.3,
    top_p=0.95,
    seed=42,
)

# HuggingFace
hf = HuggingFaceClient(
    model_name="meta-llama/Meta-Llama-3-8B-Instruct",
    hf_token="hf_...",
    temperature=0.7,
)

# Any OpenAI-compatible remote
remote = RemoteEndpointClient(
    model_name="gpt-4o",
    base_url="https://api.openai.com",
    api_key="sk-...",
    temperature=0.5,
    max_tokens=2048,
)
```

#### Factory

```python
from yukta.core.Clients.llmclientfactory import LLMClientFactory, ModelType

client = LLMClientFactory.create_client(
    ModelType.VLLM,
    model_name="qwen36-35b",
    base_url="http://192.168.200.23:11642/v1",
    temperature=0.4,
)
```

#### Generation parameter precedence

Parameters flow from lowest to highest priority:

```
constructor kwargs  →  self.temperature / self.max_tokens  →  call-time llm_kwargs
```

Call-time values always win. Pass `llm_kwargs` to `agent.run()` or `agent.invoke()` to override on a per-turn basis:

```python
# Constructor sets default temperature=0.7
client = VLLMClient("qwen36-35b", base_url="http://192.168.200.23:11642/v1", temperature=0.7)
agent.set_llm_client(client)

# Override just for this turn
agent.run("Write a creative story.", llm_kwargs={"temperature": 1.2, "top_p": 0.95})

# Deterministic output for this turn
agent.run("What is 2+2?", llm_kwargs={"temperature": 0.0, "seed": 0})
```

For Ollama, pass extra options as a nested dict:

```python
agent.run("Hello", llm_kwargs={"options": {"temperature": 0.3, "num_ctx": 4096}})
```

#### Retry and timeout configuration

```python
client = VLLMClient(
    "qwen36-35b",
    base_url="http://192.168.200.23:11642/v1",
    timeout=120,            # read timeout in seconds
    connect_timeout=5,      # connection timeout in seconds
    max_retries=3,          # retry on 429/500/502/503/504
    retry_backoff_seconds=0.5,
)
```

---

### Tools

Tools give the agent the ability to take actions — call APIs, read files, run code, query databases, or anything else a Python function can do.

#### Defining a tool

```python
from yukta import Tool, ToolParameter, ToolType

get_weather = Tool(
    name="get_weather",
    description="Fetch current weather for a city. Returns temperature and conditions.",
    parameters=[
        ToolParameter(
            name="city",
            type="string",
            description="City name (e.g. 'London')",
            required=True,
        ),
        ToolParameter(
            name="unit",
            type="string",
            description="Temperature unit",
            required=False,
            default="celsius",
            enum=["celsius", "fahrenheit"],
        ),
    ],
    tool_type=ToolType.CUSTOM,
    function=lambda city, unit="celsius": {"temp": 22, "unit": unit, "city": city},
    required_permission="basic",
    trust_level="trusted",
)
```

#### `create_custom_tool` shorthand

```python
from yukta import create_custom_tool

def search_web(query: str, max_results: int = 5) -> list:
    ...

tool = create_custom_tool(
    name="search_web",
    description="Search the web for a query and return results.",
    parameters=[
        {"name": "query",       "type": "string",  "description": "Search query", "required": True},
        {"name": "max_results", "type": "integer", "description": "Max results",  "required": False},
    ],
    function=search_web,
)
```

#### `ToolProcessor` — managing and executing tools

```python
from yukta import ToolProcessor

processor = ToolProcessor(
    parallel=False,          # set True to execute multiple tool calls concurrently
    num_parallel=3,          # worker threads when parallel=True
    timeout_per_tool=30.0,   # seconds before a single tool call times out
)

processor.add_tool(get_weather)
processor.add_tool(search_web_tool)

# Attach to agent
agent = create_agent("Bot", system_prompt=..., tools_processor=processor)

# Inspect
print(processor.list_tools())        # ["get_weather", "search_web"]
print(processor.get_tool("get_weather"))

# Execute directly
result = processor.execute_tool("get_weather", city="Tokyo", unit="celsius")
```

#### Tool argument validation

`Tool.validate_args()` checks required params, rejects unknown params, enforces JSON Schema types, and validates enum constraints:

```python
ok, err = get_weather.validate_args({"city": "London", "unit": "kelvin"})
# ok=False, err="Parameter 'unit' value 'kelvin' is not one of the allowed values: ['celsius', 'fahrenheit']"
```

#### Permission levels

Tools carry a `required_permission` field. Agents have a `permission_level` (`"basic"`, `"extended"`, `"admin"`). The agent only calls tools whose `required_permission` is satisfied by its level. Default agent permission is `"basic"`.

#### Trust levels and sandboxing

Dynamic tools loaded from the ecosystem carry a `trust_level` (`"trusted"` or `"sandbox"`). When `AgentConfig.require_sandbox=True` (the default), loading a tool with `trust_level != "sandbox"` emits a `UserWarning`. Sandboxed tools run in an isolated subprocess via `tools/sandbox.py`.

---

### Memory

`Memory` is a smart context manager that wraps a `Chat` session. When the token count exceeds `max_tokens`, older messages are automatically archived to disk so the active window stays within budget.

```python
from yukta import create_memory, MemoryConfig

memory = create_memory(
    system_prompt="You are a helpful Python tutor.",
    config=MemoryConfig(
        max_tokens=4096,        # trigger overflow archiving above this
        max_messages=None,      # or cap by message count
        kv_cache_size=10,       # recent messages kept in KV cache
        auto_save=True,         # save on overflow
        max_archive_size=500,   # max archived messages kept in RAM
    ),
    session_id="session-abc",   # optional; auto-generated if omitted
)

agent.set_memory(memory)
agent = create_agent("Tutor", system_prompt=..., memory=memory)

# Persist to disk on demand
agent.save_memory(force=True)

# Load a previous session
from yukta import load_memory
memory = load_memory("session-abc")
```

`MemoryConfig` validates all numeric fields at construction time and raises `ValueError` for invalid values.

---

### Callbacks

`AgentCallbackHandler` lets you observe every stage of the agent's execution loop without modifying agent code. Subclass it and override only the events you care about.

```python
from yukta import AgentCallbackHandler, create_agent
import time

class MetricsHandler(AgentCallbackHandler):
    def __init__(self):
        self._t0 = None

    def on_llm_start(self, messages, tools):
        self._t0 = time.time()
        print(f"LLM call — {len(messages)} messages, {len(tools)} tools")

    def on_llm_end(self, response):
        elapsed = (time.time() - self._t0) * 1000
        print(f"LLM done in {elapsed:.0f}ms — {response.usage.get('total_tokens')} tokens")

    def on_tool_start(self, tool_name, args):
        print(f"Calling tool: {tool_name}({args})")

    def on_tool_end(self, tool_name, result, duration_ms):
        print(f"Tool {tool_name} finished in {duration_ms:.0f}ms")

    def on_run_end(self, result):
        print(f"Run complete — {result.get('iterations')} iterations")

    def on_error(self, error, context):
        print(f"Error in {context}: {error}")


agent = create_agent(
    "MyAgent",
    system_prompt=...,
    llm_client=...,
    callbacks=MetricsHandler(),
)
```

Available callback methods:

| Method | Triggered when |
|--------|---------------|
| `on_llm_start(messages, tools)` | Just before `llm_client.generate()` |
| `on_llm_end(response)` | After a successful LLM response |
| `on_tool_start(tool_name, args)` | Just before a tool function executes |
| `on_tool_end(tool_name, result, duration_ms)` | After a tool finishes (success or failure) |
| `on_iteration_end(iteration, response_text)` | End of each agent loop iteration |
| `on_run_end(result)` | When `agent.run()` is about to return |
| `on_error(error, context)` | When any error occurs |

---

### Storage

`JSONFileStorage` is the default persistence backend for both `Memory` and `Chat`. It is thread-safe (uses an `RLock`), writes atomically via a temp file + rename, and distinguishes file-not-found from corruption:

```python
from yukta.core.storage import JSONFileStorage, StorageCorruptionError

storage = JSONFileStorage(storage_dir="/data/sessions")

storage.save("session-1", {"messages": [...]})

try:
    data = storage.load("session-1")    # returns None if not found
except StorageCorruptionError as e:
    print(f"Corrupted session file: {e}")

storage.delete("session-1")
sessions = storage.list_sessions()
```

`StorageCorruptionError` is a subclass of `IOError` so callers can catch it specifically without swallowing all IO errors.

---

## Ecosystem

The ecosystem system lets you define entire agent deployments declaratively in YAML and Markdown. The CLI compiles and validates everything; the Python API loads and runs it.

### CLI

```bash
# Scaffold a new ecosystem project
yukta init ecosystem myproject

# Validate all YAML/Markdown files and compile to build/ecosystem.yaml
yukta validate ecosystem ./myproject

# Run a single tool by name
yukta tool run my_tool --path ./myproject --param city=London --param unit=celsius
```

### Ecosystem Project Structure

After `yukta init ecosystem myproject`:

```
myproject/
├── agents/
│   └── agent.yaml          # Agent definition (agent_id, skills, tools, config)
├── skills/
│   └── skill-name/
│       └── SKILL.md        # Skill workflow in Markdown
├── tools/
│   └── tool.yaml           # Tool descriptor (schema, function_path)
├── tools-impl/
│   ├── __init__.py
│   └── tool_impl.py        # Python implementations of tools
├── teams/
│   └── team.yaml           # Team configuration (leader, members, structure)
├── skills-box/
│   └── index.yaml          # Auto-generated skill index (do not edit)
├── config/
│   └── main.yaml           # Ecosystem-wide config
├── bootstrap/
│   └── using-yukta.yaml    # Runtime bootstrap configuration
└── build/
    └── ecosystem.yaml      # Compiled output (auto-generated)
```

#### agents/agent.yaml

```yaml
agent_id: my-agent
agent_name: My Agent
description: A helpful assistant agent
level: L1
permission_level: basic
skills:
  - skill-name
tools:
  - my-tool
config:
  max_iter: 10
  temperature: 0.7
  verbose: false
```

#### tools/tool.yaml

```yaml
tool_id: my-tool
name: my_tool
description: Does something useful
function_path: tool_impl:my_function
trust_level: trusted
parameters:
  - name: input
    type: string
    description: The input value
    required: true
```

#### skills/skill-name/SKILL.md

```markdown
# Skill Name

## Description
What this skill does.

## Steps
1. First, gather the necessary information.
2. Then process it.
3. Return the result.
```

#### Validation

`yukta validate ecosystem ./myproject` performs:

- Checks all required files exist with correct structure
- Validates agent → skill and agent → tool cross-references
- Generates `skills-box/index.yaml`
- Compiles everything into `build/ecosystem.yaml`

### Ecosystem Python API

```python
from yukta.api import (
    load_agent, load_skill, load_tool, load_team,
    list_agents, list_skills, list_tools, list_teams,
    load_ecosystem, validate_ecosystem,
    build_and_run_agent, run_agent,
)

ecosystem_path = "./myproject"

# List what's available
print(list_agents(ecosystem_path))   # ["my-agent", ...]
print(list_tools(ecosystem_path))    # ["my-tool", ...]

# Load individual entities (O(1) indexed lookup after first load)
agent_data = load_agent("my-agent", ecosystem_path)
tool_data  = load_tool("my-tool",  ecosystem_path)
skill_data = load_skill("skill-name", ecosystem_path)

# Run an agent end-to-end
from yukta.core.Clients.ollama_client import OllamaClient

result = build_and_run_agent(
    agent_id="my-agent",
    ecosystem_path=ecosystem_path,
    task="Summarise the latest Python release notes.",
    llm_client=OllamaClient("llama3"),
)
print(result)

# Validate programmatically
errors = validate_ecosystem(ecosystem_path)
if errors:
    for e in errors:
        print(e)
```

The API loader caches compiled ecosystem data using an LRU dict (max 20 entries) so repeated lookups across a long-running process are O(1) after the first load. Call `clear_cache()` to evict if the ecosystem files change at runtime.

### Team Orchestration

Teams let multiple agents collaborate on a task, with a leader directing member agents.

```yaml
# teams/team.yaml
team_id: research-team
team_name: Research Team
structure: hierarchical      # or flat
leader_id: lead-agent
members:
  - analyst-agent
  - writer-agent
```

```python
from yukta.api import run_team
from yukta.core.Clients.ollama_client import OllamaClient

result = run_team(
    team_id="research-team",
    ecosystem_path="./myproject",
    task="Write a report on quantum computing trends in 2026.",
    llm_client=OllamaClient("llama3"),
    max_iterations=5,
)
```

Teams support two structures:

- **Hierarchical** — the leader briefs member agents, collects reports, synthesises a final response
- **Flat** — agents take turns in a round-robin group chat

The `LeaderCoordinator` handles HITL (Human-in-the-loop) approval flows where the leader can request revisions from members before finalising output.

---

## Instrumentation and Tracing

Yukta ships with OpenTelemetry tracing wired into every LLM call and tool execution via the `@trace_yukta` decorator. Spans follow the OpenInference semantic conventions so they integrate natively with Arize Phoenix.

#### Setting up Phoenix

```python
import phoenix as px
from yukta.instrumentation.tracing import setup_tracing

# Launch Phoenix (or point at an existing collector)
session = px.launch_app()
setup_tracing(endpoint=session.url)

# All agent.run() calls now emit spans automatically
agent.run("Explain transformers.")
```

#### Custom spans in your code

```python
from yukta.instrumentation.tracer import yukta_tracer
from openinference.semconv.trace import OpenInferenceSpanKindValues

with yukta_tracer.start_span("my-custom-step", OpenInferenceSpanKindValues.CHAIN) as span:
    span.set_attribute("my.attribute", "value")
    result = do_work()
```

Each LLM span records: model name, messages, tools sent, response content, token counts (prompt, completion, cached), finish reason, and latency.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YUKTA_DATA_DIR` | `~/.yukta` | Base directory for all persistent data (chats, memory, storage) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | OpenTelemetry collector endpoint for tracing |

Setting `YUKTA_DATA_DIR` affects:
- `JSONFileStorage` default directory (`$YUKTA_DATA_DIR/agent_chats`)
- `MemoryConfig` storage directory (`$YUKTA_DATA_DIR/memory`)
- `AgentConfig` chat history directory (`$YUKTA_DATA_DIR/chat_history`)

```bash
export YUKTA_DATA_DIR=/data/myapp/yukta
```

All paths are resolved via `Config.YUKTA_DATA_DIR` at import time, so you can also set this in code before creating any agents:

```python
import os
os.environ["YUKTA_DATA_DIR"] = "/data/myapp/yukta"
import yukta  # paths now resolved from /data/myapp/yukta
```

---

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run the full test suite
pytest tests/

# Run with coverage report
pytest tests/ --cov=yukta --cov-report=html

# Run a specific module
pytest tests/test_core/ -v

# Skip tests that require external services
pytest tests/ -m "not network and not integration"
```

Test markers defined in `pyproject.toml`:

| Marker | Meaning |
|--------|---------|
| `integration` | Requires external services or file-system fixtures |
| `network` | Hits real network services (LLM servers, APIs) |
| `slow` | Expected to take longer than typical unit tests |

---

## Contributing

1. Fork the repository and create a feature branch:
   ```bash
   git checkout -b feature/my-feature
   ```
2. Implement your changes with tests for any new behaviour.
3. Format and lint:
   ```bash
   black yukta/ --line-length 100
   flake8 yukta/ --max-line-length 100
   mypy yukta/ --ignore-missing-imports
   ```
4. Run the test suite and ensure no regressions:
   ```bash
   pytest tests/ -q
   ```
5. Open a pull request with a clear description of the change and why it is needed.

---

## Links

- **Repository:** https://github.com/VCoder4646/yukta
- **Issues:** https://github.com/VCoder4646/yukta/issues
- **Author:** VCoder4646 — vasanthwork0475@gmail.com

---

*MIT License — see LICENSE for details.*
