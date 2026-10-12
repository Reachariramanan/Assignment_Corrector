from yukta import create_agent, AgentConfig
import os
# os.environ['PHOENIX_GRPC_PORT'] = "6007"
# os.environ['OTEL_EXPORTER_OTLP_ENDPOINT'] = 'localhost:4317'
# os.environ['OTEL_EXPORTER_OTLP_PROTOCOL'] = 'grpc'

import phoenix.otel as otel
from opentelemetry import trace
import logging
from yukta.config import SystemPrompt,AgentConfig,MemoryConfig
from yukta.tools import Tool, ToolType, ToolProcessor, ToolParameter
from yukta.config import Config
from yukta.core.Clients import OllamaClient, VLLMClient,RemoteEndpointClient,HuggingFaceClient,SGLangClient,LMStudioClient

# System prompt for the agent
sp = SystemPrompt("yukta", "you are a agent that can analyze stock data and provide investment advice.")

# Setup tools for the agent
tools_orchestrator = ToolProcessor()
tools_orchestrator.add_tool(
    Tool(
        name="stock_price_analyzer",
        description="Analyze stock data and provide investment advice",
        parameters=[
            ToolParameter(
                name="stock_symbol",
                type="string",
                description="Stock ticker symbol (e.g., AAPL, GOOGL)",
                required=True
            )
        ],
        tool_type=ToolType.CUSTOM,
        function=lambda stock_symbol: f"Current price of {stock_symbol}: $150 (mock data)"
    )
)

# Agent configuration
config = AgentConfig(
    auto_save_chat=False,  # Disable old UUID-based chat saving
    auto_save_chat_history=True,  # Enable new agent-name based chat history saving
    chat_history_dir="./chats",  # Directory for auto-saved chat histories
    log_level=logging.DEBUG,
    enable_logging=False,
    memory_log_level=logging.INFO,
    enable_memory_logging=False,
    verbose=True  # Enable verbose output to see what's happening
)
tracer_provider = otel.register(
        project_name=os.getenv("PHOENIX_PROJECT_NAME", "test-project"),
        endpoint=os.getenv("PHOENIX_ENDPOINT", "http://localhost:6007/v1/traces"),
    )
tracer = tracer_provider.get_tracer(__name__)
# Initialize Ollama LLM client
# llm1 = VLLMClient(model_name="minimax-m2.5",base_url="http://192.168.*****",optioms_override={"think":False})
llm=OllamaClient(model_name="qwenown")
# print(llm.get_model_info()) # Test connection and print model info
# Create agent with Ollama client
agent1 = create_agent(
    name="TestAgent1",
    system_prompt=sp,
    tools_processor=tools_orchestrator,
    llm_client=llm,
    config=config
)

# ===== Multi-turn conversation with actual LLM invocations =====
print("\n" + "="*70)
print("STARTING MULTI-TURN CONVERSATION WITH OLLAMA CLIENT")
print("="*70 + "\n")

# List of questions to ask the agent
questions = [
    "What was the price of AAPL stock today?",
    "Please analyze the stock price for GOOGL and give me your recommendation.",
    "Based on your analysis, should I invest in tech stocks?"
]

# Run multi-turn conversation
for i, question in enumerate(questions, 1):
    print(f"\n--- Turn {i} ---")
    print(f"User: {question}\n")
    
    try:
        # Invoke the agent with the question
        # This will actually call the Ollama model using the llm_client
        response = agent1.invoke(
            input=question,
            use_llm=True  # Use LLM for reasoning and response
        )
        
        print(f"Agent: {response}\n")
        
    except Exception as e:
        print(f"Error during agent invocation: {e}\n")

# Display chat statistics
print("\n" + "="*70)
print("CHAT STATISTICS")
print("="*70 + "\n")

chat_stats = agent1.get_chat_stats()
if chat_stats:
    print(f"Total Messages: {chat_stats['total_messages']}")
    print(f"User Messages: {chat_stats['user_messages']}")
    print(f"Agent Messages: {chat_stats['agent_messages']}")
    print(f"Tool Calls: {chat_stats['tool_calls']}")
    print(f"Total Tokens: {chat_stats['total_tokens']}")
else:
    print("No chat statistics available")

print("\n" + "="*70)
print("CONVERSATION COMPLETE")
print("="*70)
print("\nNote: Chat history was automatically saved in real-time to:")
print(f"  ./chats/{agent1.agent_name}/[generated_filename].json")
print("\nThe chat file was updated after each message (user, agent, tool).")

