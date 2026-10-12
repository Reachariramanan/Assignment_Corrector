from typing import List, Dict, Any, Optional
import json
import logging
import time
import requests
from ..Chat.llm_response import LLMResponse
from openinference.semconv.trace import OpenInferenceSpanKindValues
from ...instrumentation.decorators import trace_yukta
from .base_client import BaseLLMClient, _extract_stream_content

# Configure logging
logger = logging.getLogger(__name__)


class VLLMClient(BaseLLMClient):
    """
    Client for vLLM OpenAI-compatible API.
    vLLM provides high-throughput serving for LLMs.
    """
    
    def __init__(
        self,
        model_name: str,
        base_url: str = "http://192.168.200.23:11642/v1",
        **kwargs
    ):
        """
        Initialize vLLM client.

        Args:
            model_name: Model name (must be loaded in vLLM server)
            base_url: vLLM server URL (defaults to http://192.168.200.23:11642/v1)
            **kwargs: Additional configuration
        """
        # Use default URL if empty string is provided
        if not base_url or base_url.strip() == "":
            base_url = "http://192.168.200.23:11642/v1"
        super().__init__(model_name, base_url, **kwargs)
        self._model_info_cache: Optional[Dict[str, Any]] = None
        self._model_info_cache_ts: float = 0.0
        self._model_info_cache_ttl: float = float(self.config.get("model_info_cache_ttl", 300))
        self._allow_model_fallback: bool = bool(self.config.get("allow_model_fallback", False))

    def _model_info_cache_is_valid(self) -> bool:
        if not self._model_info_cache:
            return False
        if self._model_info_cache_ttl <= 0:
            return True
        return (time.monotonic() - self._model_info_cache_ts) < self._model_info_cache_ttl
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Fetch model information from vLLM server.
        
        Includes context length, max tokens, and other model capabilities.
        Results are cached for efficiency.
        
        Returns:
            Dictionary with model info including 'max_model_len'
        """
        if self._model_info_cache_is_valid():
            return self._model_info_cache
        
        try:
            url = f"{self.base_url}/models"
            response = self._session.get(url, timeout=(5, 10))
            response.raise_for_status()
            
            data = response.json()
            
            if "data" not in data or not data["data"]:
                logger.warning(f"No models found in vLLM response")
                return {}
            
            # Find the current model in the list
            for model in data["data"]:
                if model.get("id") == self.model_name:
                    self._model_info_cache = model
                    self._model_info_cache_ts = time.monotonic()
                    logger.debug(f"Model info fetched: {self.model_name}")
                    logger.debug(f"Model max_model_len: {model.get('max_model_len', 'unknown')}")
                    return model
            
            # Safety-first default: fail fast on model mismatch unless explicit fallback is enabled.
            if not self._allow_model_fallback:
                available = [m.get("id", "unknown") for m in data["data"]]
                raise ValueError(
                    f"Model {self.model_name} not found in vLLM. Available models: {available}"
                )

            logger.warning(f"Model {self.model_name} not found in vLLM, using first available model info")
            self._model_info_cache = data["data"][0]
            self._model_info_cache_ts = time.monotonic()
            return self._model_info_cache
            
        except ValueError:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch model info from vLLM: {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"Failed to fetch model info from vLLM: {str(e)}")
            return {}
    
    def get_context_window(self) -> int:
        """
        Get the model's context window size.
        
        Returns:
            Context window size in tokens. Defaults to 8192 if unavailable.
        """
        model_info = self.get_model_info()
        logger.debug(f"Model info: {model_info}")
        context_size = model_info.get("max_model_len", 8192)
        logger.info(f"Using context window: {context_size} tokens")
        return context_size
    
    @trace_yukta(kind=OpenInferenceSpanKindValues.LLM)
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response using vLLM.
        
        Args:
            messages: List of message dictionaries
            tools: Optional tools for function calling
            **kwargs: Additional arguments for the API call
            
        Returns:
            LLMResponse object with complete response data for tracing
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

        # Debug: Log the payload
        logger.debug(f"vLLM Request Payload: {payload}")
        logger.debug(f"Number of messages: {len(messages)}, Tools: {len(tools) if tools else 0}")

        try:
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
            
            logger.debug(f"vLLM Response Status: {response.status_code}")
            logger.debug(f"vLLM Response Keys: {data.keys() if isinstance(data, dict) else type(data)}")
            
            # Validate response data
            if not isinstance(data, dict) or data is None:
                logger.error(f"Invalid response format: expected dict, got {type(data).__name__}")
                raise ValueError(f"Invalid response format: expected dict, got {type(data).__name__}")
            
            if "choices" not in data or not data["choices"]:
                logger.error(f"Response missing 'choices' or empty: {data}")
                raise ValueError("Response missing 'choices' field or empty choices list")
            
            # Parse OpenAI-compatible response
            choice = data["choices"][0]
            message = choice.get("message", {})
            
            if not isinstance(message, dict):
                logger.error(f"Invalid message format: expected dict, got {type(message).__name__}")
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
            
            logger.debug(f"Parsed {len(tool_calls)} tool calls from response")
            
            # Extract usage data with comprehensive token tracking
            usage = data.get("usage", {}) or {}
            
            # Normalize usage format for consistent token tracking
            # vLLM sends: prompt_tokens, completion_tokens, total_tokens
            normalized_usage = {
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "total_tokens": int(usage.get("total_tokens", 0)),
                "cached_tokens": int(usage.get("cached_tokens", 0) or 0),
                "cache_read_input_tokens": int(usage.get("cache_read_input_tokens", 0) or 0),
            }
            
            # Recalculate total if missing
            if normalized_usage["total_tokens"] == 0:
                normalized_usage["total_tokens"] = (
                    normalized_usage["prompt_tokens"] + normalized_usage["completion_tokens"]
                )
            
            # Create LLMResponse with all extracted data
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
            logger.info(f"[vLLM Response] Model: {self.model_name}")
            logger.info(f"[vLLM Response] Content length: {len(content)} chars")
            logger.info(f"[vLLM Response] Tool calls: {len(tool_calls)}")
            logger.info(f"[vLLM Response] Tokens - Prompt: {normalized_usage['prompt_tokens']}, "
                       f"Completion: {normalized_usage['completion_tokens']}, "
                       f"Total: {normalized_usage['total_tokens']}, "
                       f"Cached: {normalized_usage['cached_tokens']}")
            logger.info(f"[vLLM Response] Finish reason: {finish_reason}")
            logger.debug(
                f"[vLLM Response] Response summary: finish_reason={finish_reason}, "
                f"tool_calls={len(tool_calls)}, total_tokens={normalized_usage['total_tokens']}"
            )
            
            return response_obj
        
        except Exception as e:
            logger.error(f"vLLM API error details: {str(e)}", exc_info=True)
            raise RuntimeError(f"vLLM API error: {str(e)}")

