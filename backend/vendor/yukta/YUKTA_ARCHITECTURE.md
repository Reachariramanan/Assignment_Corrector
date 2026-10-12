# Yukta Package Architecture

```mermaid
flowchart TB
    subgraph "yukta Package (v2.1.0)"
        subgraph "core/"
            subgraph "Agent/"
                agent["Agent<br/>Main agent class"]
                agent_builder["AgentBuilder<br/>Builder pattern"]
            end
            
            subgraph "Clients/"
                base_client["BaseLLMClient<br/>Abstract base"]
                ollama["OllamaClient"]
                vllm["vLLMClient"]
                hf["HuggingFaceClient"]
                lmstudio["LMStudioClient"]
                sglang["SGLangClient"]
                remote["RemoteClient"]
                factory["LLMClientFactory"]
            end
            
            subgraph "Chat/"
                chat["Chat<br/>Conversation container"]
                message["Message<br/>Chat message"]
                llm_response["LLMResponse<br/>LLM response wrapper"]
            end
            
            memory["Memory<br/>Context management"]
            storage["Storage<br/>Persistence backend"]
        end
        
        subgraph "config/"
            agent_config["AgentConfig<br/>Agent settings"]
            system_prompt["SystemPrompt<br/>System prompts"]
            memory_config["MemoryConfig<br/>Memory settings"]
            config["Config<br/>Main config"]
        end
        
        subgraph "tools/"
            tools_pro["ToolProcessor<br/>Tool execution"]
            tool["Tool<br/>Tool definition"]
            mcp_tool["MCPTool<br/>Remote tools"]
            tool_utils["Utils<br/>Helper functions"]
        end
        
        subgraph "api/"
            loader["Loader<br/>Load entities"]
            compiler["Compiler<br/>Compile ecosystem"]
            validator["Validator<br/>Validate YAML"]
            orchestrator["Orchestrator<br/>Coordination"]
            runner["Runner<br/>Execute tools"]
            transformer["Transformer<br/>Data transform"]
            resolver["Resolver<br/>Dependency resolve"]
            allocator["Allocator<br/>Resource allocation"]
        end
        
        subgraph "ecosystem/"
            eco_loader["loader.py"]
            eco_compiler["compiler.py"]
            eco_validator["validator.py"]
            eco_runner["runner.py"]
        end
        
        subgraph "cli/"
            main["main.py<br/>CLI entry"]
            templates["templates.py"]
        end
        
        subgraph "instrumentation/"
            tracer["Tracer<br/>Tracing"]
            decorators["Decorators<br/>Tracing decorators"]
            extractors["Extractors<br/>Data extraction"]
            tracing["tracing.py"]
        end
        
        init["__init__.py<br/>Public API exports"]
    end
    
    %% Relationships
    agent --> agent_builder
    agent --> base_client
    agent --> memory
    agent --> chat
    agent --> tools_pro
    
    base_client --> ollama
    base_client --> vllm
    base_client --> hf
    base_client --> lmstudio
    base_client --> sglang
    base_client --> remote
    base_client --> factory
    
    tool --> tools_pro
    mcp_tool --> tools_pro
    
    loader --> compiler
    loader --> validator
    loader --> orchestrator
    loader --> transformer
    
    eco_loader --> loader
    eco_compiler --> compiler
    eco_validator --> validator
    eco_runner --> runner
    
    init --> agent
    init --> tools_pro
    init --> memory
    init --> config
```

---

## Hierarchical Structure

```mermaid
graph TD
    Yukta[Yukta v2.1.0<br/>Modular AI Agent Framework]
    
    PublicAPI[Public API<br/>__init__.py exports]
    
    subgraph "Core Runtime"
        AgentCore[Agent System]
        MemoryCore[Memory System]
        ChatCore[Chat System]
        ClientCore[LLM Clients]
        StorageCore[Storage Backends]
    end
    
    subgraph "Configuration"
        AgentConfig[AgentConfig]
        SystemPrompt[SystemPrompt]
        MemoryConfig[MemoryConfig]
        Config[Config]
    end
    
    subgraph "Tools System"
        ToolDef[Tool Definitions]
        ToolProc[Tool Processor]
        MCPTools[MCP Tools]
    end
    
    subgraph "Ecosystem"
        EcoAPI[Ecosystem API]
        EcoLoader[Ecosystem Loader]
        EcoCompiler[Ecosystem Compiler]
        EcoValidator[Ecosystem Validator]
    end
    
    subgraph "CLI"
        CLI[Command Line Interface]
    end
    
    subgraph "Instrumentation"
        Tracing[Tracing/Observability]
        Decorators[Decorators]
        Extractors[Attribute Extractors]
    end
    
    Yukta --> PublicAPI
    PublicAPI --> AgentCore
    PublicAPI --> MemoryCore
    PublicAPI --> ChatCore
    PublicAPI --> ClientCore
    PublicAPI --> ToolProc
    PublicAPI --> Config
    PublicAPI --> EcoAPI
    
    AgentCore --> AgentConfig
    AgentCore --> SystemPrompt
    AgentCore --> MemoryCore
    AgentCore --> ToolProc
    AgentCore --> ClientCore
    
    MemoryCore --> MemoryConfig
    MemoryCore --> StorageCore
    
    ClientCore --> Ollama[Ollama]
    ClientCore --> VLLM[vLLM]
    ClientCore --> HF[HuggingFace]
    ClientCore --> LMStudio[LM Studio]
    ClientCore --> SGLang[SGLang]
    
    ToolProc --> ToolDef
    ToolProc --> MCPTools
    
    EcoAPI --> EcoLoader
    EcoAPI --> EcoCompiler
    EcoAPI --> EcoValidator
    
    AgentCore -.-> Tracing
    MemoryCore -.-> Tracing
```

---

## Package Structure

```mermaid
graph TB
    subgraph "yukta/"
        init["__init__.py<br/>v2.1.0 Exports<br/>create_agent, AgentBuilder<br/>Memory, Tool, Chat"]
    end
    
    subgraph "core/"
        subgraph "Agent/"
            agent["agent.py<br/>Agent class<br/>invoke(), add_tool()"]
            agent_builder["agent_builder.py<br/>AgentBuilder<br/>Builder pattern"]
        end
        
        subgraph "Clients/"
            factory["llmclientfactory.py<br/>LLMClientFactory<br/>ModelType enum"]
            base["base_client.py<br/>BaseLLMClient (ABC)"]
            clients["ollama_client.py<br/>vllm_client.py<br/>hf_client.py<br/>lmstudio_client.py<br/>sglang_client.py<br/>remote_client.py"]
        end
        
        subgraph "Chat/"
            chat["chat.py<br/>Chat, ChatManager"]
            message["message.py<br/>Message class"]
            llm_resp["llm_response.py<br/>LLMResponse"]
        end
        
        memory["memory.py<br/>Memory, create_memory()"]
        storage["storage.py<br/>JSONFileStorage, BaseStorageBackend"]
    end
    
    subgraph "config/"
        agent_cfg["agent_config.py<br/>AgentConfig"]
        sys_prompt["system_prompt.py<br/>SystemPrompt"]
        mem_cfg["memory_config.py<br/>MemoryConfig"]
        cfg["config.py<br/>Config class"]
    end
    
    subgraph "tools/"
        tool_pro["tools_pro.py<br/>ToolProcessor<br/>ToolType enum"]
        tool["tool.py<br/>Tool, ToolParameter"]
        mcp["mcp_tool.py<br/>MCP Tool support"]
        utils["utils.py<br/>setup_logging, load_json"]
    end
    
    subgraph "api/"
        loader["loader.py<br/>load_agent, load_tool<br/>load_skill, load_team"]
        compiler["compiler.py<br/>compile_ecosystem()"]
        validator["validator.py<br/>validate_ecosystem()"]
        orchestrator["orchestrator.py"]
        runner["runner.py"]
        transformer["transformer.py"]
        resolver["resolver.py"]
        allocator["allocator.py"]
        exceptions["exceptions.py"]
        models["models.py"]
        logger["modern_logger.py"]
    end
    
    subgraph "ecosystem/"
        eco_loader["loader.py<br/>Ecosystem loader"]
        eco_compiler["compiler.py<br/>Ecosystem compiler"]
        eco_validator["validator.py<br/>Ecosystem validator"]
        eco_runner["runner.py<br/>Tool runner"]
        eco_exc["exceptions.py"]
    end
    
    subgraph "cli/"
        main_cli["main.py<br/>CLI entry point"]
        templates["templates.py<br/>Project templates"]
    end
    
    subgraph "instrumentation/"
        tracer["tracer.py<br/>Tracer class"]
        decorators["decorators.py<br/>@trace_yukta"]
        extractors["extractors.py<br/>Attribute extractors"]
        tracing["tracing.py<br/>Tracing utilities"]
    end
    
    init --> agent
    init --> memory
    init --> tool_pro
    init --> agent_cfg
    init --> cfg
    
    agent --> memory
    agent --> chat
    agent --> tool_pro
    agent --> clients
```

---

## Class Relationships

```mermaid
classDiagram
    class Agent {
        +str agent_name
        +SystemPrompt system_prompt
        +ToolProcessor tools_processor
        +AgentConfig config
        +Memory memory
        +BaseLLMClient llm_client
        +invoke(input, use_llm, max_iterations)
        +add_tool(tool)
        +set_memory(memory)
        +get_chat_history()
    }
    
    class AgentBuilder {
        +build() Agent
        +with_name(name)
        +with_system_prompt(prompt)
        +with_llm_client(client)
        +with_tools(tools)
        +with_config(config)
    }
    
    class Memory {
        +str system_prompt
        +int max_tokens
        +add_message(role, content)
        +get_context() str
        +search(query)
    }
    
    class ToolProcessor {
        +Dict[str, Tool] _tools
        +bool parallel
        +add_tool(tool)
        +remove_tool(name)
        +execute_tool(name, kwargs)
        +list_tools()
    }
    
    class Tool {
        +str name
        +str description
        +List[ToolParameter] parameters
        +ToolType tool_type
        +Callable function
    }
    
    class Chat {
        +str agent_name
        +List[Message] messages
        +add_message(role, content)
        +get_history()
    }
    
    class BaseLLMClient {
        +str model_name
        +complete(prompt, tools)
        +chat(messages)
    }
    
    class OllamaClient {
        +complete()
        +chat()
    }
    
    class vLLMClient {
        +complete()
        +chat()
    }
    
    Agent --> SystemPrompt
    Agent --> ToolProcessor
    Agent --> AgentConfig
    Agent --> Memory
    Agent --> BaseLLMClient
    Agent --> Chat
    
    AgentBuilder --> Agent
    
    ToolProcessor --> Tool
    
    Memory --> MemoryConfig
    
    BaseLLMClient <|-- OllamaClient
    BaseLLMClient <|-- vLLMClient
    BaseLLMClient <|-- HuggingFaceClient
    BaseLLMClient <|-- LMStudioClient
    BaseLLMClient <|-- SGLangClient
    BaseLLMClient <|-- RemoteClient
```

---

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Memory
    participant ToolProcessor
    participant LLMClient
    participant Chat
    
    User->>Agent: invoke("query")
    Agent->>Memory: get_context()
    Memory-->>Agent: context string
    
    Agent->>LLMClient: chat(messages, tools)
    LLMClient-->>Agent: LLMResponse (may include tool_call)
    
    alt has tool_call
        Agent->>ToolProcessor: execute_tool(tool_name, args)
        ToolProcessor->>ToolProcessor: find and run tool
        ToolProcessor-->>Agent: tool_result
        Agent->>LLMClient: chat(messages + result)
        LLMClient-->>Agent: final response
    end
    
    Agent->>Chat: add_message(user_query)
    Agent->>Chat: add_message(assistant_response)
    Chat-->>Agent: saved
    
    Agent-->>User: response
```

---

## LLM Client Architecture

```mermaid
graph LR
    subgraph "LLM Client Factory"
        factory[LLMClientFactory<br/>create_client()]
    end
    
    subgraph "Base"
        base[BaseLLMClient<br/>(Abstract)]
    end
    
    subgraph "Implementations"
        Ollama[OllamaClient]
        VLLM[vLLMClient]
        HF[HuggingFaceClient]
        LMStudio[LMStudioClient]
        SGLang[SGLangClient]
        Remote[RemoteClient]
    end
    
    factory --> base
    base --> Ollama
    base --> VLLM
    base --> HF
    base --> LMStudio
    base --> SGLang
    base --> Remote
```

---

## Tool Processing Flow

```mermaid
flowchart LR
    subgraph "Tool System"
        LLM[LLM Response]
        TC[Tool Call<br/>name + args]
        TP[ToolProcessor]
        Registry[(Tool Registry)]
        Tool1[Tool 1]
        Tool2[Tool 2]
        ToolN[Tool N]
        Result[Result]
        
        LLM --> TC
        TC --> TP
        TP --> Registry
        Registry --> Tool1
        Registry --> Tool2
        Registry --> ToolN
        Tool1 --> Result
        Tool2 --> Result
        ToolN --> Result
    end
```

---

## Ecosystem Architecture

```mermaid
flowchart TB
    subgraph "Ecosystem Project"
        agents[agents/<br/>YAML configs]
        skills[skills/<br/>Markdown]
        tools[tools/<br/>YAML descriptors]
        teams[teams/<br/>Team configs]
        config[config/<br/>Ecosystem config]
    end
    
    subgraph "Build Process"
        validator[Validator]
        compiler[Compiler]
        index[skills-box/]
        build[build/<br/>ecosystem.yaml]
    end
    
    subgraph "Runtime"
        loader[Loader]
        resolver[Resolver]
        runner[Runner]
    end
    
    agents --> validator
    skills --> validator
    tools --> validator
    teams --> validator
    
    validator --> compiler
    compiler --> index
    compiler --> build
    
    loader --> resolver
    resolver --> runner
```

---

# Yukta vs Other AI Agent Frameworks

```mermaid
flowchart TB
    subgraph "AI Agent Framework Landscape"
        LCG["LangChain<br/>Industry Standard<br/>95k+ GitHub Stars"]
        CRW["CrewAI<br/>Role-Based Teams<br/>20k+ GitHub Stars"]
        AG["AutoGen<br/>Multi-Agent Chat<br/>30k+ GitHub Stars"]
        LI["LlamaIndex<br/>RAG-Focused<br/>35k+ GitHub Stars"]
        YT["Yukta v2.1.0<br/>Lightweight Agents<br/>Your Package"]
    end
```

---

## Comparison Overview

```mermaid
graph TD
    subgraph "Framework Positioning"
        Complexity["Complexity / Features"]
        Purpose["Primary Purpose"]
        
        LangChain_Type[LangChain<br/>High Complexity<br/>General Purpose]
        CrewAI_Type[CrewAI<br/>Medium Complexity<br/>Multi-Agent Teams]
        AutoGen_Type[AutoGen<br/>Medium Complexity<br/>Conversational]
        LlamaIndex_Type[LlamaIndex<br/>Medium Complexity<br/>RAG/Data]
        Yukta_Type[Yukta<br/>Low-Medium Complexity<br/>Lightweight Agents]
    end
    
    LangChain_Type --- |Position| Complexity
    CrewAI_Type --- |Position| Complexity
    AutoGen_Type --- |Position| Complexity
    LlamaIndex_Type --- |Position| Complexity
    Yukta_Type --- |Position| Complexity
```

---

## Feature Comparison Table

```mermaid
classDiagram
    class Framework {
        +str name
        +int stars
        +str primary_focus
        +int integrations
        +str learning_curve
        +bool production_ready
    }
    
    class Yukta {
        +name = "Yukta"
        +stars = "Your Package"
        +primary_focus = "Lightweight modular agents"
        +integrations = "6 LLM clients"
        +learning_curve = "Low"
        +production_ready = "Yes"
    }
    
    class LangChain {
        +name = "LangChain"
        +stars = "95k+"
        +primary_focus = "LLM integration & chains"
        +integrations = "500+"
        +learning_curve = "High"
        +production_ready = "Yes"
    }
    
    class CrewAI {
        +name = "CrewAI"
        +stars = "20k+"
        +primary_focus = "Role-based multi-agent"
        +integrations = "~50"
        +learning_curve = "Low"
        +production_ready = "Growing"
    }
    
    class AutoGen {
        +name = "AutoGen"
        +stars = "30k+"
        +primary_focus = "Multi-agent collaboration"
        +integrations = "~30"
        +learning_curve = "Medium"
        +production_ready = "Research-grade"
    }
    
    class LlamaIndex {
        +name = "LlamaIndex"
        +stars = "35k+"
        +primary_focus = "RAG & data integration"
        +integrations = "100+"
        +learning_curve = "Medium"
        +production_ready = "Yes"
    }
```

---

## Detailed Comparison Matrix

| Feature | Yukta | LangChain | CrewAI | AutoGen | LlamaIndex |
|---------|-------|-----------|--------|---------|------------|
| **Version** | v2.1.0 | Latest | Latest | Latest | Latest |
| **GitHub Stars** | - | 95k+ | 20k+ | 30k+ | 35k+ |
| **LLM Clients** | 6 (local + remote) | 100+ | Via LiteLLM | Multiple | Multiple |
| **Multi-Agent** | Via ecosystem | Via LangGraph | Native | Native | No |
| **Tool Support** | Custom + MCP | 500+ tools | Custom | Function calling | Via tools |
| **Memory** | Built-in | Multiple options | Built-in | Chat history | Via data |
| **RAG** | Via tools | Built-in | Via tools | Via tools | Native |
| **Observability** | OpenTelemetry | LangSmith | Limited | Basic | Limited |
| **CLI** | Yes | LangServe | No | No | No |
| **Code Execution** | Via tools | Via tools | Via tools | Built-in | Via tools |
| **Python Only** | Yes | No (JS/TS) | Yes | Yes | No (TS) |
| **Learning Curve** | Low | High | Low | Medium | Medium |
| **Production Ready** | Yes | Yes | Growing | Research | Yes |

---

## Architecture Comparison

```mermaid
graph TB
    subgraph "LangChain Architecture"
        LCM["Models"]
        LCP["Prompts"]
        LCC["Chains"]
        LCMem["Memory"]
        LCA["Agents"]
        LCI["Indexes"]
    end
    
    subgraph "CrewAI Architecture"
        CRA["Agents<br/>Role/Goal/Backstory"]
        CRC["Crews"]
        CRT["Tasks"]
        CRP["Processes<br/>Sequential/Parallel"]
    end
    
    subgraph "AutoGen Architecture"
        AGA["Assistant Agent"]
        AGU["User Proxy"]
        AGG["GroupChat"]
        AGE["Code Executor"]
    end
    
    subgraph "Yukta Architecture"
        YTA["Agent"]
        YTM["Memory"]
        YTT["ToolProcessor"]
        YTC["LLM Clients"]
        YTE["Ecosystem"]
    end
```

---

## When to Choose Yukta

```mermaid
flowchart LR
    Start["Your Needs"] --> Simple{Simple Agent?}
    
    Simple --> |Yes| Local{Local LLM?}
    Simple --> |No| Complex{Complex Workflow?}
    
    Local --> |Yes| Yukta[Yukta ✓]
    Local --> |No| Cloud{Cloud LLM?}
    
    Cloud --> |No| Yukta
    Cloud --> |Yes| LangChain
    
    Complex --> |Multi-agent| CrewAI
    Complex --> |Conversational| AutoGen
    Complex --> |RAG Focus| LlamaIndex
```

### Choose Yukta When:

- ✅ You need a **lightweight** agent framework
- ✅ You prefer **local LLMs** (Ollama, vLLM, LM Studio)
- ✅ You want **built-in memory** without external dependencies
- ✅ You need **CLI ecosystem** for YAML-based agent management
- ✅ You want **simple API** like `create_agent()` and `invoke()`
- ✅ You need **tool processing** with MCP support

### Choose LangChain When:

- ✅ You need **500+ integrations** with external services
- ✅ You want **LangGraph** for complex workflow orchestration
- ✅ You need **LangSmith** for production observability
- ✅ You're building **enterprise RAG** systems

### Choose CrewAI When:

- ✅ Your workflow maps to **role-based teams**
- ✅ You want **fast prototyping** with minimal code
- ✅ You need **task delegation** between agents

### Choose AutoGen When:

- ✅ You need **multi-agent conversation** dynamics
- ✅ You want **built-in code execution**
- ✅ You're building **research prototypes**

### Choose LlamaIndex When:

- ✅ Your primary focus is **RAG pipelines**
- ✅ You need **advanced retrieval** strategies
- ✅ You're building **knowledge base** systems

---

## Yukta Strengths vs Competitors

```mermaid
radarChart
    title "Framework Feature Comparison"
    axes "LLM Flexibility", "Tool Support", "Memory", "Multi-Agent", "Simplicity", "CLI"
    
    "Yukta": [5, 4, 5, 3, 5, 5]
    "LangChain": [5, 5, 4, 4, 3, 3]
    "CrewAI": [3, 3, 3, 5, 4, 2]
    "AutoGen": [3, 3, 3, 5, 3, 2]
    "LlamaIndex": [3, 3, 2, 2, 3, 2]
```

### Yukta's Unique Advantages:

1. **Lightweight & Fast**
   - No heavy dependencies
   - Simple setup: `pip install yukta`
   - Minimal boilerplate code

2. **Local LLM Focus**
   - Native support for Ollama, vLLM, LM Studio, SGLang
   - Easy deployment without cloud API keys
   - Privacy-first architecture

3. **Built-in Memory**
   - Token-based context management
   - No external vector DB required
   - Simple JSON persistence

4. **CLI Ecosystem**
   - `yukta init ecosystem`
   - `yukta validate`
   - `yukta tool run`
   - YAML-based agent definitions

5. **Tool Processing**
   - Custom tool registration
   - MCP (Model Context Protocol) support
   - Parallel tool execution

---

## Code Comparison

### Yukta - Simple & Direct
```python
from yukta import create_agent

agent = create_agent(
    name="Assistant",
    system_prompt="You are helpful."
)
response = agent.invoke("Hello")
```

### LangChain - More Verbose
```python
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate

# More setup required
```

### CrewAI - Role-Based
```python
from crewai import Agent, Task, Crew

researcher = Agent(role="Researcher", goal="Research", backstory="...")
task = Task(description="Research AI", agent=researcher)
crew = Crew(agents=[researcher], tasks=[task])
```

---

## Ecosystem Comparison

```mermaid
graph TD
    subgraph "Ecosystem Size"
        LC_Eco["LangChain<br/>500+ integrations<br/>100+ LLM providers"]
        CR_Eco["CrewAI<br/>50+ integrations<br/>Via LangChain"]
        AG_Eco["AutoGen<br/>30+ integrations<br/>Microsoft-backed"]
        LI_Eco["LlamaIndex<br/>100+ integrations<br/>Vector stores focus"]
        YT_Eco["Yukta<br/>6 LLM clients<br/>MCP tools<br/>Custom tools"]
    end
```

---

## Summary Table

| Module | Components | Purpose |
|--------|------------|---------|
| **core/Agent** | Agent, AgentBuilder | Main agent with invoke(), tools, memory |
| **core/Clients** | 6 implementations | Ollama, vLLM, HF, LM Studio, SGLang, Remote |
| **core/Memory** | Memory, MemoryConfig | Context management with token limits |
| **core/Chat** | Chat, ChatManager, Message | Conversation persistence |
| **core/Storage** | JSONFileStorage, BaseStorageBackend | Persistence layer |
| **tools/** | ToolProcessor, Tool, MCPTool | Tool definitions and execution |
| **config/** | AgentConfig, SystemPrompt, Config | Configuration management |
| **api/** | Loader, Compiler, Validator, Runner | Ecosystem integration |
| **ecosystem/** | Legacy ecosystem modules | Backward compatibility |
| **cli/** | main.py, templates.py | Command-line interface |
| **instrumentation/** | Tracer, Decorators, Extractors | OpenTelemetry observability |

---

## Verdict

Yukta occupies a unique position in the AI agent framework landscape:

- **Smaller & lighter** than LangChain
- **Simpler API** than CrewAI/AutoGen
- **Local LLM focused** (unlike cloud-first frameworks)
- **Built-in memory** (unlike LlamaIndex which needs external setup)
- **CLI included** (unique among these frameworks)

Yukta is ideal for:
- Developers wanting a **minimal dependency** agent framework
- Projects using **local LLMs** (Ollama, vLLM, etc.)
- Teams needing **quick prototyping** with memory
- Applications requiring **CLI-based ecosystem** management