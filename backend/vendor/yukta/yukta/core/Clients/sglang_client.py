from typing import List, Dict, Any, Optional
import json
import logging
import requests
from ..Chat.llm_response import LLMResponse
from openinference.semconv.trace import OpenInferenceSpanKindValues
from ...instrumentation.decorators import trace_yukta
from .base_client import BaseLLMClient, _extract_stream_content

logger = logging.getLogger(__name__)


class SGLangClient(BaseLLMClient):
    """
    Client for SGLang OpenAI-compatible API.
    SGLang provides fast, highly optimized serving for LLMs.
    """

    def __init__(
        self,
        model_name: str,
        base_url: str = "http://localhost:30000",
        **kwargs
    ):
        """
        Initialize SGLang client.

        Args:
            model_name: Model name (must be loaded in SGLang server)
            base_url: SGLang server URL (defaults to port 30000)
            **kwargs: Additional configuration
        """
        # Use default URL if empty string is provided
        if not base_url or base_url.strip() == "":
            base_url = "http://localhost:30000"
        super().__init__(model_name, base_url, **kwargs)
        self._context_window_cache: Optional[int] = None

    # Caller reports the model's real max_model_len below, but we cap what we return
    # from get_context_window(): the Agent's dynamic-output-budget calculation does
    # `max_tokens = context_window - prompt_tokens - buffer` and requests THAT as the
    # completion budget on every single call. Reporting the true value on a 131k-context
    # model means it requests ~130k tokens of output for a one-line reply - wasteful,
    # and it can outright 400 the server when its estimate of prompt_tokens is a little
    # low (tokenizer counting differences), since prompt+max_tokens then exceeds the
    # server's real limit. Capping this to a smaller "effective" window keeps the
    # requested completion budget always generous but bounded and safe.
    _EFFECTIVE_CONTEXT_WINDOW_CAP = 32768

    def get_context_window(self) -> int:
        """
        Get the model's (capped) context window size from SGLang's /v1/models endpoint
        (OpenAI-compatible, reports 'max_model_len'). Without querying this at all, the
        Agent's dynamic-output-budget calculation falls back to a hardcoded 8192 default,
        which silently starves the completion budget for any call with a non-trivial
        prompt - see _EFFECTIVE_CONTEXT_WINDOW_CAP above for why we still cap it.
        """
        if self._context_window_cache is not None:
            return self._context_window_cache
        try:
            headers = {}
            if "api_key" in self.config:
                headers["Authorization"] = f"Bearer {self.config['api_key']}"
            resp = requests.get(f"{self.base_url}/v1/models", headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            context_size = data[0].get("max_model_len", 8192) if data else 8192
        except Exception as e:
            logger.warning(f"Could not fetch context window from SGLang server, defaulting to 8192: {e}")
            context_size = 8192
        context_size = min(context_size, self._EFFECTIVE_CONTEXT_WINDOW_CAP)
        self._context_window_cache = context_size
        return context_size
    @trace_yukta(kind=OpenInferenceSpanKindValues.LLM)
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response using SGLang.
        """
        gen_params = self._generate_params(**kwargs)
        is_streaming = bool(gen_params.pop("stream", False))
        payload = {
            "model": self.model_name,
            "messages": messages,
            **gen_params,
        }

        # Add tools if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            # SGLang natively supports the standard OpenAI completions endpoint
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
            logger.info(f"[SGLang Response] Model: {self.model_name}")
            logger.info(f"[SGLang Response] Content length: {len(content)} chars")
            logger.info(f"[SGLang Response] Tool calls: {len(tool_calls)}")
            logger.info(f"[SGLang Response] Tokens - Prompt: {normalized_usage['prompt_tokens']}, "
                       f"Completion: {normalized_usage['completion_tokens']}, "
                       f"Total: {normalized_usage['total_tokens']}, "
                       f"Cached: {normalized_usage['cached_tokens']}")
            logger.info(f"[SGLang Response] Finish reason: {finish_reason}")
            logger.debug(
                f"[SGLang Response] Response summary: finish_reason={finish_reason}, "
                f"tool_calls={len(tool_calls)}, total_tokens={normalized_usage['total_tokens']}"
            )
            
            return response_obj
            
        except Exception as e:
            raise RuntimeError(f"SGLang API error: {str(e)}")
 