from typing import List, Dict, Any, Optional
import requests
import json
from ..Chat.llm_response import LLMResponse
from openinference.semconv.trace import OpenInferenceSpanKindValues
from ...instrumentation.decorators import trace_yukta
from .base_client import BaseLLMClient


class OllamaClient(BaseLLMClient):
    """
    Client for Ollama API.
    Ollama runs models locally on your machine.
    """
    
    def __init__(
        self,
        model_name: str = "llama2",
        base_url: str = "http://localhost:11434",
        **kwargs
    ):
        """
        Initialize Ollama client.
        
        Args:
            model_name: Ollama model name (e.g., 'llama2', 'mistral', 'codellama')
            base_url: Ollama server URL (defaults to http://localhost:11434)
            **kwargs: Additional configuration
        """
        # Use default URL if empty string is provided
        if not base_url or base_url.strip() == "":
            base_url = "http://localhost:11434"
        super().__init__(model_name, base_url, **kwargs)
        self._data = {}
        self._params = {}
    def _parse_parameters(self, param_str: str) -> Dict[str, Any]:
        params = {}

        for line in param_str.splitlines():
            parts = line.strip().split()
            if len(parts) == 2:
                key, value = parts
                try:
                    if "." in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    pass
                params[key] = value

        return params

    def _fetch_model_data(self, model: str):
        res = requests.post(
            f"{self.base_url}/api/show",
            json={"name": model}
        )
        res.raise_for_status()

        self._data = res.json()
        self._params = self._parse_parameters(
            self._data.get("parameters", "")
        )

    def _ensure_model_metadata(self, model: Optional[str] = None) -> None:
        if self._data and self._params:
            return

        try:
            self._fetch_model_data(model or self.model_name)
        except Exception:
            # Fall back to defaults if the metadata endpoint is unavailable.
            if not hasattr(self, "_data"):
                self._data = {}
            if not hasattr(self, "_params"):
                self._params = {}

    def get_context_window(self) -> Optional[int]:
        self._ensure_model_metadata()

        # Priority 1: num_ctx
        if "num_ctx" in self._params:
            return self._params["num_ctx"]

        # Priority 2: model_info fallback
        model_info = self._data.get("model_info", {})
        for k, v in model_info.items():
            if "context_length" in k:
                return v

        return 8192

    def get_max_context(self) -> Optional[int]:
        self._ensure_model_metadata()

        model_info = self._data.get("model_info", {})
        for k, v in model_info.items():
            if "context_length" in k:
                return v
        return 8192

    def get_model_info(self, model: str) -> Dict[str, Any]:
        # fetch + store internally
        self._ensure_model_metadata(model)

        context_window = self.get_context_window()
        max_context = self.get_max_context()

        caps = self._data.get("capabilities", [])

        return {
            "model": model,
            "context_window": context_window,      # ✅ uses self
            "max_context_window": max_context,
            "default_params": self._params,
            "supports_stream": True,
            "supports_tools": "tools" in caps,
            "supports_reasoning": "thinking" in caps,
            "provider": "ollama"
        }
    @trace_yukta(kind=OpenInferenceSpanKindValues.LLM)
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response using Ollama.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            tools: Optional tools for function calling
            **kwargs: Additional arguments for the API call
            
        Returns:
            LLMResponse object
        """
        gen_params = self._generate_params(**kwargs)
        stream = bool(gen_params.pop("stream", False))

        # Build options dict. User can pass options={...} directly or rely on
        # the two universal mappings: temperature and max_tokens → num_predict.
        options: Dict[str, Any] = gen_params.pop("options", {})
        options.setdefault("temperature", gen_params.pop("temperature", self.temperature))
        if "max_tokens" in gen_params:
            options.setdefault("num_predict", gen_params.pop("max_tokens"))
        elif self.max_tokens:
            options.setdefault("num_predict", self.max_tokens)

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
            **gen_params,  # remaining top-level Ollama params (format, keep_alive, etc.)
        }
        if options:
            payload["options"] = options

        # Add tools if provided (Ollama supports function calling in newer versions)
        if tools:
            payload["tools"] = tools
        
        try:
            response = self._make_request("api/chat", payload, stream=stream)
            
            # Ollama can return a single JSON object or newline-delimited JSON frames.
            # Prefer the last frame that actually carries content, thinking, or tool calls.
            data = None
            parse_error = None
            candidate_frames: List[Dict[str, Any]] = []
            try:
                parsed = response.json()
                if isinstance(parsed, dict):
                    candidate_frames = [parsed]
            except Exception as json_err:
                parse_error = json_err

            if not candidate_frames:
                response_text = response.text.strip()
                for line in response_text.split("\n"):
                    if not line.strip():
                        continue
                    try:
                        frame = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(frame, dict):
                        candidate_frames.append(frame)

                if not candidate_frames:
                    raise RuntimeError(
                        "Failed to parse Ollama response. "
                        f"Original error: {parse_error}. "
                        f"Response snippet: {response.text.strip()[:200]}"
                    )

            def _has_usable_message(frame: Dict[str, Any]) -> bool:
                message = frame.get("message")
                if not isinstance(message, dict):
                    return False
                content = message.get("content", "")
                thinking = message.get("thinking", "")
                tool_calls = message.get("tool_calls")
                return bool(
                    (isinstance(content, str) and content.strip())
                    or (isinstance(thinking, str) and thinking.strip())
                    or tool_calls
                )

            data = next(
                (frame for frame in reversed(candidate_frames) if _has_usable_message(frame)),
                candidate_frames[-1],
            )
            
            # Validate response data
            if not isinstance(data, dict) or data is None:
                raise ValueError(f"Invalid response format: expected dict, got {type(data).__name__}")
            
            # Parse response
            content = ""
            tool_calls = []

            if "message" in data:
                message = data.get("message", {})
                if isinstance(message, dict):
                    # First try to get content
                    content = message.get("content", "")
                    
                    # If content is empty, try thinking field (for reasoning models like Qwen)
                    if not content or not content.strip():
                        thinking = message.get("thinking", "")
                        if thinking:
                            content = f"[Thinking]\n{thinking}\n\n[Response]\n"
                    
                    # Check for tool calls
                    if "tool_calls" in message:
                        tool_calls = message["tool_calls"]

            if (not content or not content.strip()) and not tool_calls:
                for fallback_key in ("response", "output", "text"):
                    fallback_value = data.get(fallback_key, "")
                    if isinstance(fallback_value, str) and fallback_value.strip():
                        content = fallback_value
                        break

            if not content and not tool_calls:
                raise RuntimeError(
                    "Ollama response did not contain usable content, thinking, or tool calls. "
                    f"Finish reason: {data.get('done_reason', 'unknown')}"
                )
            
            # Extract usage data with comprehensive token tracking
            finish_reason = data.get("done_reason", "stop")
            prompt_tokens = int(data.get("prompt_eval_count", 0))
            completion_tokens = int(data.get("eval_count", 0))
            total_tokens = prompt_tokens + completion_tokens
            
            normalized_usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cached_tokens": 0,  # Ollama doesn't expose cache info yet
                "cache_read_input_tokens": 0
            }
            
            response_obj = LLMResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=normalized_usage,
                raw_response=data,
                cached_tokens=0,
                incomplete=(finish_reason == "length")
            )
            
            # Log response structure for Phoenix tracing
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[Ollama Response] Model: {self.model_name}")
            logger.info(f"[Ollama Response] Content length: {len(content)} chars")
            logger.info(f"[Ollama Response] Tool calls: {len(tool_calls)}")
            logger.info(f"[Ollama Response] Tokens - Prompt: {prompt_tokens}, "
                       f"Completion: {completion_tokens}, "
                       f"Total: {total_tokens}")
            logger.info(f"[Ollama Response] Finish reason: {finish_reason}")
            logger.debug(f"[Ollama Response] Full response object: {response_obj.to_dict()}")
            
            return response_obj
        
        except (ConnectionError, TimeoutError) as e:
            raise RuntimeError(f"Ollama connection error: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Ollama API error: {str(e)}")
    
    def list_models(self) -> List[str]:
        """
        List available Ollama models.
        
        Returns:
            List of model names
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except Exception as e:
            raise RuntimeError(f"Error listing Ollama models: {str(e)}")
