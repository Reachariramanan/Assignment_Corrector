# extractors.py
from typing import Any, Dict, List, Optional
from openinference.semconv.trace import SpanAttributes as OI
from .tracer import safe_json_dumps

def _ensure_messages_schema(messages: List[Dict]) -> List[Dict]:
    """
    Phoenix expects chat messages like:
    [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    Tool calls (if any) should live under "tool_calls".
    """
    cleaned = []
    for m in messages or []:
        if not isinstance(m, dict):
            cleaned.append({"role": "unknown", "content": str(m)})
            continue
        role = m.get("role", "unknown")
        content = m.get("content", "")
        out = {"role": role, "content": content}
        if "tool_calls" in m:
            out["tool_calls"] = m["tool_calls"]
        cleaned.append(out)
    return cleaned

def extract_llm_input_details(span, client, messages: List[Dict], tools: Optional[List[Dict]], **kwargs):
    """Extract comprehensive LLM input details BEFORE execution (like extract_agent_attributes for invoke)."""
    
    # 1. Client/Model information
    span.set_attribute("yukta.llm.model_name", getattr(client, "model_name", "unknown"))
    span.set_attribute("yukta.llm.base_url", getattr(client, "base_url", "unknown"))
    span.set_attribute("yukta.llm.temperature", kwargs.get("temperature", "default"))
    span.set_attribute("yukta.llm.max_tokens", kwargs.get("max_tokens", "unlimited"))
    
    # 2. COMPLETE MESSAGES - ALL content being sent
    span.set_attribute(OI.LLM_INPUT_MESSAGES, safe_json_dumps(_ensure_messages_schema(messages)))
    span.set_attribute("yukta.llm.messages.count", len(messages))
    
    # Estimate input tokens (rough approximation: 1 token ≈ 4 chars)
    total_input_chars = sum(len(m.get("content", "")) for m in messages)
    estimated_input_tokens = max(1, total_input_chars // 4)  # Rough estimate
    span.set_attribute("yukta.llm.messages.total_characters", total_input_chars)
    span.set_attribute("yukta.llm.tokens.estimated_input", estimated_input_tokens)
    
    # Trace each message individually for debugging
    for idx, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        span.set_attribute(f"yukta.llm.message.{idx}.role", role)
        span.set_attribute(f"yukta.llm.message.{idx}.length", len(content))
        if len(content) < 200:  # Only trace short messages inline
            span.set_attribute(f"yukta.llm.message.{idx}.preview", content[:200])
    
    # 3. COMPLETE TOOLS - ALL tools offered to model
    if tools:
        span.set_attribute(OI.LLM_INVOCATION_PARAMETERS, safe_json_dumps({"tools": tools}))
        span.set_attribute("yukta.llm.tools.count", len(tools))
        span.set_attribute("yukta.llm.tools.schema", safe_json_dumps(tools))
        
        # Trace each tool name
        for idx, tool in enumerate(tools):
            tool_name = tool.get("function", {}).get("name", "unknown")
            tool_desc = tool.get("function", {}).get("description", "")
            span.set_attribute(f"yukta.llm.tool.{idx}.name", tool_name)
            span.set_attribute(f"yukta.llm.tool.{idx}.description", tool_desc)
    else:
        span.set_attribute("yukta.llm.tools.count", 0)
    
    # 4. ALL PARAMETERS
    for key, value in kwargs.items():
        if key not in ["messages", "tools"]:  # Already handled
            if value is not None:
                span.set_attribute(f"yukta.llm.param.{key}", safe_json_dumps(value) if not isinstance(value, (int, float, bool, str)) else value)
    
    # 5. COMPREHENSIVE INPUT SNAPSHOT (for easy viewing)
    input_snapshot = {
        "model": getattr(client, "model_name", "unknown"),
        "messages_count": len(messages),
        "messages_total_chars": sum(len(m.get("content", "")) for m in messages),
        "tools_count": len(tools) if tools else 0,
        "tool_names": [t.get("function", {}).get("name") for t in tools] if tools else [],
        "parameters": kwargs,
        "messages": messages,
        "tools": tools
    }
    span.set_attribute("yukta.llm.input_snapshot", safe_json_dumps(input_snapshot))
    span.set_attribute(OI.INPUT_VALUE, safe_json_dumps(input_snapshot))

def extract_agent_attributes(span, agent, user_input: str):
    """Extract comprehensive agent/chain attributes for Phoenix tracing."""
    span.set_attribute(OI.INPUT_VALUE, user_input)
    span.set_attribute(OI.SESSION_ID, getattr(agent, "agent_id", "unknown"))
    span.set_attribute("yukta.agent.name", getattr(agent, "agent_name", "unknown"))
    
    # System prompt (verbose)
    system_prompt_text = getattr(agent.system_prompt, "prompt_text", "")
    span.set_attribute("yukta.agent.system_prompt", system_prompt_text)
    span.set_attribute("yukta.agent.system_prompt_length", len(system_prompt_text))

    cfg = agent.config.to_dict() if getattr(agent, "config", None) else {}
    span.set_attribute("yukta.agent.config", safe_json_dumps(cfg))

    # Available tools (detailed)
    tools_dict = agent.tools_processor.format_for_llm() if getattr(agent, "tools_processor", None) else {}
    span.set_attribute("yukta.agent.available_tools", safe_json_dumps(tools_dict))
    span.set_attribute("yukta.agent.available_tools_count", len(tools_dict.get("tools", [])) if isinstance(tools_dict, dict) else 0)

    # Memory info
    if getattr(agent, "use_memory_cache", False) and getattr(agent, "memory", None):
        span.set_attribute("yukta.memory.session_id", getattr(agent.memory, "session_id", ""))
        span.set_attribute("yukta.memory.cache_enabled", True)
    
    # Chat session info
    if getattr(agent, "chat", None):
        chat = agent.chat
        span.set_attribute("yukta.chat.session_id", getattr(chat, "chat_id", ""))
        span.set_attribute("yukta.chat.message_count", len(getattr(chat, "messages", [])))
        span.set_attribute("yukta.chat.context_window", getattr(chat, "context_window", 8192))
        span.set_attribute("yukta.chat.max_input_tokens", getattr(chat, "max_input_tokens", 7680))

def extract_llm_attributes(span, client, messages: List[Dict], response: Any, 
                          input_tools: Optional[List[Dict]] = None, **input_params):
    """Extract comprehensive LLM attributes including model inputs, outputs, and tool calls."""
    span.set_attribute(OI.LLM_MODEL_NAME, getattr(client, "model_name", "unknown"))
    span.set_attribute("yukta.llm.base_url", getattr(client, "base_url", "unknown"))
    
    # Trace requested tools schema
    if input_tools:
        span.set_attribute("yukta.llm.requested_tools_count", len(input_tools))
        span.set_attribute("yukta.llm.requested_tools_schema", safe_json_dumps(input_tools))

    # Normalized input messages (verbose)
    normalized = _ensure_messages_schema(messages)
    span.set_attribute(OI.LLM_INPUT_MESSAGES, safe_json_dumps(normalized))
    span.set_attribute("yukta.llm.input_message_count", len(normalized))
    
    # Calculate total input characters
    total_input_chars = sum(len(m.get("content", "")) for m in normalized)
    span.set_attribute("yukta.llm.input_character_count", total_input_chars)

    if not response:
        return

    # Output text
    content = getattr(response, "content", None)
    if content:
        span.set_attribute(OI.OUTPUT_VALUE, content)
        span.set_attribute("yukta.llm.output_length", len(content))

    # Tool calls (detailed)
    tool_calls = getattr(response, "tool_calls", None)
    if tool_calls:
        # Phoenix usually expects output messages containing tool_calls
        out_messages = [{"role": "assistant", "content": "", "tool_calls": tool_calls}]
        span.set_attribute(OI.LLM_OUTPUT_MESSAGES, safe_json_dumps(out_messages))
        
        # Detailed tool call tracking
        span.set_attribute("yukta.llm.tool_calls_count", len(tool_calls))
        for idx, tc in enumerate(tool_calls):
            tool_name = tc.get("function", {}).get("name", "unknown")
            tool_args = tc.get("function", {}).get("arguments", "{}")
            tool_id = tc.get("id", "")
            span.set_attribute(f"yukta.llm.tool_call_{idx}.name", tool_name)
            span.set_attribute(f"yukta.llm.tool_call_{idx}.id", tool_id)
            span.set_attribute(f"yukta.llm.tool_call_{idx}.arguments", safe_json_dumps(tool_args))

    # Usage (detailed)
    usage = getattr(response, "usage", None)
    if isinstance(usage, dict):
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        total_tokens = int(usage.get("total_tokens", 0))
        
        # Calculate total_tokens if not provided by API
        if total_tokens == 0 and (prompt_tokens > 0 or completion_tokens > 0):
            total_tokens = prompt_tokens + completion_tokens
        
        # Cache consideration: cache tokens are already included in prompt_tokens usually
        # but we track them separately for clarity
        cached_tokens = int(usage.get("cached_tokens", 0))
        cache_read_tokens = int(usage.get("cache_read_input_tokens", 0))
        total_cached = cached_tokens + cache_read_tokens
        
        span.set_attribute(OI.LLM_TOKEN_COUNT_PROMPT, prompt_tokens)
        span.set_attribute(OI.LLM_TOKEN_COUNT_COMPLETION, completion_tokens)
        span.set_attribute(OI.LLM_TOKEN_COUNT_TOTAL, total_tokens)
        
        # Additional token tracking with cache breakdown
        span.set_attribute("yukta.llm.tokens.prompt", prompt_tokens)
        span.set_attribute("yukta.llm.tokens.completion", completion_tokens)
        span.set_attribute("yukta.llm.tokens.total", total_tokens)
        span.set_attribute("yukta.llm.tokens.cached", total_cached)
        span.set_attribute("yukta.llm.tokens.prompt_uncached", prompt_tokens - total_cached if total_cached > 0 else prompt_tokens)

    # Cache info (detailed)
    if hasattr(response, "get_cache_info"):
        cache_info = response.get_cache_info() or {}
        if cache_info:
            cached_tokens = int(cache_info.get("cached_tokens", 0))
            hit_rate = float(cache_info.get("cache_hit_rate", 0.0))
            span.set_attribute("yukta.cache.cached_tokens", cached_tokens)
            span.set_attribute("yukta.cache.hit_rate", hit_rate)
            span.set_attribute("yukta.cache.hit", cached_tokens > 0)

    # Response completion status (NEW)
    finish_reason = getattr(response, "finish_reason", "stop")
    span.set_attribute("yukta.llm.finish_reason", finish_reason)
    
    # Continuation tracking (NEW)
    if hasattr(response, "is_incomplete"):
        span.set_attribute("yukta.llm.is_incomplete", response.is_incomplete())
    
    if hasattr(response, "continuation_count"):
        span.set_attribute("yukta.llm.continuation_count", response.continuation_count)
    
    if hasattr(response, "get_completion_status"):
        completion_status = response.get_completion_status()
        span.set_attribute("yukta.llm.completion_status", safe_json_dumps(completion_status))

def extract_tool_attributes(span, tool_name: str, arguments: Dict, result: Any):
    """Extract comprehensive tool call attributes including inputs and outputs."""
    span.set_attribute(OI.TOOL_NAME, tool_name)
    span.set_attribute(OI.INPUT_VALUE, safe_json_dumps(arguments))
    span.set_attribute(OI.OUTPUT_VALUE, safe_json_dumps(result))
    
    # Detailed tool tracking
    span.set_attribute("yukta.tool.name", tool_name)
    span.set_attribute("yukta.tool.arguments", safe_json_dumps(arguments))
    span.set_attribute("yukta.tool.arguments_count", len(arguments) if isinstance(arguments, dict) else 0)
    
    # Tool result details
    if isinstance(result, dict):
        span.set_attribute("yukta.tool.result_success", result.get("success", False))
        span.set_attribute("yukta.tool.result_type", "dict")
        
        if result.get("success"):
            result_data = result.get("result")
            span.set_attribute("yukta.tool.result_data", safe_json_dumps(result_data))
            # Track result size
            if isinstance(result_data, list):
                span.set_attribute("yukta.tool.result_items_count", len(result_data))
        else:
            error = result.get("error", "unknown error")
            span.set_attribute("yukta.tool.result_error", str(error))
    else:
        span.set_attribute("yukta.tool.result_type", type(result).__name__)
        span.set_attribute("yukta.tool.result_data", safe_json_dumps(result))

def extract_token_budget_attributes(span, context_window: int, current_tokens: int, 
                                   context_buffer: int, dynamic_max_tokens: int):
    """Extract token budgeting information for detailed debugging."""
    span.set_attribute("yukta.token_budget.context_window", context_window)
    span.set_attribute("yukta.token_budget.current_tokens_used", current_tokens)
    span.set_attribute("yukta.token_budget.context_buffer", context_buffer)
    span.set_attribute("yukta.token_budget.max_input_tokens", context_window - context_buffer)
    span.set_attribute("yukta.token_budget.tokens_available", context_window - current_tokens - context_buffer)
    span.set_attribute("yukta.token_budget.dynamic_max_tokens_allocated", dynamic_max_tokens)
    utilization = (current_tokens / context_window * 100) if context_window > 0 else 0
    span.set_attribute("yukta.token_budget.utilization_percent", utilization)

def extract_continuation_attributes(span, continuation_count: int, continuation_tool_calls: List[Dict],
                                   original_content_length: int, final_content_length: int):
    """Extract continuation/auto-recovery attributes."""
    span.set_attribute("yukta.continuation.count", continuation_count)
    span.set_attribute("yukta.continuation.tool_calls_made", len(continuation_tool_calls))
    span.set_attribute("yukta.continuation.original_response_length", original_content_length)
    span.set_attribute("yukta.continuation.final_response_length", final_content_length)
    span.set_attribute("yukta.continuation.content_added", final_content_length - original_content_length)
    
    # Track each tool called in continuation
    for idx, tc in enumerate(continuation_tool_calls):
        tool_name = tc.get("tool", "unknown")
        span.set_attribute(f"yukta.continuation.tool_{idx}", tool_name)