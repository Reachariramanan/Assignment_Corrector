# decorators.py
import functools
import time
import inspect
from openinference.semconv.trace import OpenInferenceSpanKindValues
from openinference.semconv.trace import SpanAttributes as OI

from .tracer import yukta_tracer, safe_json_dumps
from .extractors import extract_agent_attributes, extract_llm_attributes, extract_tool_attributes, extract_llm_input_details

def trace_yukta(kind: OpenInferenceSpanKindValues):
    def decorator(func):
        span_name = f"{func.__qualname__}"

        # -------- async wrapper --------
        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            start_time = time.perf_counter()
            with yukta_tracer.start_span(span_name, kind) as span:
                try:
                    tool_name, tool_args = None, None

                    if kind == OpenInferenceSpanKindValues.CHAIN and hasattr(self, "agent_name"):
                        user_input = kwargs.get("user_message") or kwargs.get("input") or (args[0] if args else "")
                        extract_agent_attributes(span, self, user_input)

                    elif kind == OpenInferenceSpanKindValues.TOOL:
                        tool_name = kwargs.get("tool_name") or (args[0] if args else "unknown")
                        tool_args = kwargs.get("arguments") or (args[1] if len(args) > 1 else {})

                    # For LLM spans, trace all input parameters BEFORE execution
                    if kind == OpenInferenceSpanKindValues.LLM:
                        messages = kwargs.get("messages") or (args[0] if args else [])
                        tools = kwargs.get("tools") or (args[1] if len(args) > 1 else None)
                        # Filter out messages and tools from kwargs to avoid duplicate arguments
                        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ["messages", "tools"]}
                        extract_llm_input_details(span, self, messages, tools, **filtered_kwargs)

                    result = await func(self, *args, **kwargs)

                    if kind == OpenInferenceSpanKindValues.LLM:
                        messages = kwargs.get("messages") or (args[0] if args else [])
                        tools = kwargs.get("tools") or (args[1] if len(args) > 1 else None)
                        extract_llm_attributes(span, self, messages, result, input_tools=tools)

                    elif kind == OpenInferenceSpanKindValues.TOOL:
                        extract_tool_attributes(span, tool_name, tool_args, result)

                    elif kind == OpenInferenceSpanKindValues.CHAIN and hasattr(self, "agent_name"):
                        span.set_attribute("yukta.agent.final_response", safe_json_dumps(result))
                        # also set standard output for chain
                        span.set_attribute(OI.OUTPUT_VALUE, safe_json_dumps(result))

                    span.set_attribute("yukta.latency_ms", (time.perf_counter() - start_time) * 1000)
                    return result

                except Exception as e:
                    yukta_tracer.record_exception(span, e)
                    raise

        # -------- sync wrapper --------
        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            start_time = time.perf_counter()
            with yukta_tracer.start_span(span_name, kind) as span:
                try:
                    tool_name, tool_args = None, None

                    if kind == OpenInferenceSpanKindValues.CHAIN and hasattr(self, "agent_name"):
                        user_input = kwargs.get("user_message") or kwargs.get("input") or (args[0] if args else "")
                        extract_agent_attributes(span, self, user_input)

                    elif kind == OpenInferenceSpanKindValues.TOOL:
                        tool_name = kwargs.get("tool_name") or (args[0] if args else "unknown")
                        tool_args = kwargs.get("arguments") or (args[1] if len(args) > 1 else {})

                    # For LLM spans, trace all input parameters BEFORE execution
                    if kind == OpenInferenceSpanKindValues.LLM:
                        messages = kwargs.get("messages") or (args[0] if args else [])
                        tools = kwargs.get("tools") or (args[1] if len(args) > 1 else None)
                        # Filter out messages and tools from kwargs to avoid duplicate arguments
                        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ["messages", "tools"]}
                        extract_llm_input_details(span, self, messages, tools, **filtered_kwargs)

                    result = func(self, *args, **kwargs)

                    if kind == OpenInferenceSpanKindValues.LLM:
                        messages = kwargs.get("messages") or (args[0] if args else [])
                        tools = kwargs.get("tools") or (args[1] if len(args) > 1 else None)
                        extract_llm_attributes(span, self, messages, result, input_tools=tools)

                    elif kind == OpenInferenceSpanKindValues.TOOL:
                        extract_tool_attributes(span, tool_name, tool_args, result)

                    elif kind == OpenInferenceSpanKindValues.CHAIN and hasattr(self, "agent_name"):
                        span.set_attribute("yukta.agent.final_response", safe_json_dumps(result))
                        span.set_attribute(OI.OUTPUT_VALUE, safe_json_dumps(result))

                    span.set_attribute("yukta.latency_ms", (time.perf_counter() - start_time) * 1000)
                    return result

                except Exception as e:
                    yukta_tracer.record_exception(span, e)
                    raise

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
    return decorator