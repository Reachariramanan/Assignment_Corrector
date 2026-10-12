from typing import List, Dict, Any, Optional
import json
from ..Chat.llm_response import LLMResponse
from openinference.semconv.trace import OpenInferenceSpanKindValues
from ...instrumentation.decorators import trace_yukta
from .base_client import BaseLLMClient, _extract_stream_content
class LMStudioClient(BaseLLMClient):
    """
    Client for LM Studio local API.
    LM Studio provides a GUI for running local models with an OpenAI-compatible server.
    """
    
    def __init__(
        self,
        model_name: str,
        base_url: str = "http://localhost:1234",
        **kwargs
    ):
        """
        Initialize LM Studio client.
        
        Args:
            model_name: Model name (must be loaded and running in LM Studio)
            base_url: LM Studio server URL (defaults to port 1234)
            **kwargs: Additional configuration
        """
        # Use default URL if empty string is provided
        if not base_url or base_url.strip() == "":
            base_url = "http://localhost:1234"
            
        # LM Studio doesn't strictly require an API key, but some OpenAI clients expect one
        if "api_key" not in kwargs:
            kwargs["api_key"] = "lm-studio"
            
        super().__init__(model_name, base_url, **kwargs)
    @trace_yukta(kind=OpenInferenceSpanKindValues.LLM)
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response using LM Studio's local server.
        """
        gen_params = self._generate_params(**kwargs)
        is_streaming = bool(gen_params.pop("stream", False))
        payload = {
            "model": self.model_name,
            "messages": messages,
            **gen_params,
        }

        # Add tools if provided (Requires a tool-calling capable model loaded in LM Studio)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            # LM Studio uses the standard OpenAI chat completions endpoint
            response = self._make_request("v1/chat/completions", payload, stream=is_streaming)
            
            # Handle streaming vs non-streaming responses
            if is_streaming:
                accumulated_content, data = _extract_stream_content(response)

                if data is None:
                    raise ValueError("No valid JSON data received from streaming response")
                
                # Update data with accumulated content for proper response building
                if accumulated_content and "choices" in data:
                    if data["choices"]:
                        data["choices"][0]["message"] = {
                            "content": accumulated_content,
                            "role": "assistant"
                        }
            else:
                data = response.json()
            
            # Validate response data
            if not isinstance(data, dict) or data is None:
                raise ValueError(f"Invalid response format: expected dict, got {type(data).__name__}")
            
            if "choices" not in data or not data["choices"]:
                raise ValueError("Response missing 'choices' field or empty choices list")
            
            # Parse OpenAI-compatible response
            choice = data["choices"][0]
            message = choice.get("message", {})
            
            if not isinstance(message, dict):
                raise ValueError(f"Invalid message format: expected dict, got {type(message).__name__}")
            
            content = message.get("content", "") or ""
            tool_calls = []
            
            # Parse tool calls if present
            if "tool_calls" in message and message["tool_calls"]:
                for tc in message["tool_calls"]:
                    fn = tc.get("function")
                    if not isinstance(fn, dict):
                        logger.warning("Skipping malformed tool call (missing 'function' key): %r", tc)
                        continue
                    tool_calls.append({
                        "id": tc.get("id", ""),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": fn.get("name", ""),
                            "arguments": fn.get("arguments", "{}"),
                        },
                    })
            
            usage = data.get("usage", {}) or {}
            cached = 0
            if isinstance(usage, dict) and "prompt_tokens_details" in usage:
                details = usage.get("prompt_tokens_details", {})
                if isinstance(details, dict):
                    cached = details.get("cached_tokens", 0)
            
            # Normalize usage format for consistent token tracking
            normalized_usage = {
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "total_tokens": int(usage.get("total_tokens", 0)),
                "cached_tokens": cached,
                "cache_read_input_tokens": int(usage.get("cache_read_input_tokens", 0) or 0)
            }
            
            # Recalculate total if missing
            if normalized_usage["total_tokens"] == 0:
                normalized_usage["total_tokens"] = (
                    normalized_usage["prompt_tokens"] + normalized_usage["completion_tokens"]
                )
            
            finish_reason = choice.get("finish_reason", "stop")
            response_obj = LLMResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=normalized_usage,
                raw_response=data,
                cached_tokens=cached,
                incomplete=(finish_reason == "length")
            )
            
            # Log response structure for Phoenix tracing
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[LM Studio Response] Model: {self.model_name}")
            logger.info(f"[LM Studio Response] Content length: {len(content)} chars")
            logger.info(f"[LM Studio Response] Tool calls: {len(tool_calls)}")
            logger.info(f"[LM Studio Response] Tokens - Prompt: {normalized_usage['prompt_tokens']}, "
                       f"Completion: {normalized_usage['completion_tokens']}, "
                       f"Total: {normalized_usage['total_tokens']}, "
                       f"Cached: {normalized_usage['cached_tokens']}")
            logger.info(f"[LM Studio Response] Finish reason: {finish_reason}")
            logger.debug(
                f"[LM Studio Response] Response summary: finish_reason={finish_reason}, "
                f"tool_calls={len(tool_calls)}, total_tokens={normalized_usage['total_tokens']}"
            )
            
            return response_obj
            
        except Exception as e:
            raise RuntimeError(f"LM Studio API error: {str(e)}")
