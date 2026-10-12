from typing import List, Dict, Any, Optional
import logging
import json
from ..Chat.llm_response import LLMResponse
from openinference.semconv.trace import OpenInferenceSpanKindValues
from ...instrumentation.decorators import trace_yukta
from .base_client import BaseLLMClient, _extract_stream_content

logger = logging.getLogger(__name__)
class RemoteEndpointClient(BaseLLMClient):
    """
    Generic client for remote OpenAI-compatible endpoints.
    Works with OpenAI API, Azure OpenAI, and other compatible services.
    """
    
    def __init__(
        self,
        model_name: str,
        base_url: str,
        api_key: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize remote endpoint client.
        
        Args:
            model_name: Model name
            base_url: API base URL
            api_key: API key for authentication
            **kwargs: Additional configuration
        """
        if api_key:
            kwargs["api_key"] = api_key
        super().__init__(model_name, base_url, **kwargs)
    @trace_yukta(kind=OpenInferenceSpanKindValues.LLM)
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response using remote endpoint.
        
        Args:
            messages: List of message dictionaries
            tools: Optional tools for function calling
            **kwargs: Additional arguments for the API call
            
        Returns:
            LLMResponse object
        """

        formatted_messages = []
        for msg in messages:
            formatted_msg = msg.copy()
            
            # Translate 'agent' to 'assistant' for OpenAI compatibility
            if formatted_msg.get("role") == "agent":
                formatted_msg["role"] = "assistant"
                
            if formatted_msg.get("role") == "assistant" and formatted_msg.get("tool_calls") and not formatted_msg.get("content"):
                formatted_msg["content"] = None
                
            formatted_messages.append(formatted_msg)
        
        gen_params = self._generate_params(**kwargs)
        is_streaming = bool(gen_params.pop("stream", False))
        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            **gen_params,
        }

        # Add tools if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            # Determine endpoint
            endpoint = self.config.get("endpoint", "/v1/chat/completions")
            response = self._make_request(endpoint, payload, stream=is_streaming)
            
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
            
            # Normalize usage format for consistent token tracking
            normalized_usage = {
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "total_tokens": int(usage.get("total_tokens", 0)),
                "cached_tokens": int(usage.get("cached_tokens", 0) or 0),
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
                cached_tokens=normalized_usage.get("cached_tokens", 0),
                incomplete=(finish_reason == "length")
            )
            
            # Log response structure for Phoenix tracing
            logger.info(f"[Remote Response] Model: {self.model_name}")
            logger.info(f"[Remote Response] Content length: {len(content)} chars")
            logger.info(f"[Remote Response] Tool calls: {len(tool_calls)}")
            logger.info(f"[Remote Response] Tokens - Prompt: {normalized_usage['prompt_tokens']}, "
                       f"Completion: {normalized_usage['completion_tokens']}, "
                       f"Total: {normalized_usage['total_tokens']}, "
                       f"Cached: {normalized_usage['cached_tokens']}")
            logger.info(f"[Remote Response] Finish reason: {finish_reason}")
            logger.debug(
                f"[Remote Response] Response summary: finish_reason={finish_reason}, "
                f"tool_calls={len(tool_calls)}, total_tokens={normalized_usage['total_tokens']}"
            )
            
            return response_obj
        
        except Exception as e:
            raise RuntimeError(f"Remote endpoint API error: {str(e)}")
 