
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import time
import requests
import json
import logging
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from ..Chat.llm_response import LLMResponse
from openinference.semconv.trace import OpenInferenceSpanKindValues
from ...instrumentation.decorators import trace_yukta

# Configure logging
logger = logging.getLogger(__name__)
_serialization_logger = logging.getLogger(__name__ + ".serialization")


def _make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert objects to JSON-serializable format.
    Handles protobuf objects, enums, repeated fields, and other non-serializable types.
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-serializable version of the object
    """
    # Handle None
    if obj is None:
        return None
    
    # Handle basic JSON-serializable types
    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    # Handle lists
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    
    # Handle dictionaries
    if isinstance(obj, dict):
        return {
            _make_json_serializable(k): _make_json_serializable(v)
            for k, v in obj.items()
        }
    
    # Handle protobuf objects
    if hasattr(obj, 'DESCRIPTOR'):
        return _make_json_serializable(obj.__dict__)
    
    # Handle protobuf repeated fields (RepeatedScalarContainer, RepeatedCompositeContainer)
    if type(obj).__name__ in ('RepeatedScalarContainer', 'RepeatedCompositeContainer'):
        return [_make_json_serializable(item) for item in obj]
    
    # Handle enums
    if hasattr(obj, 'value'):
        try:
            return str(obj.value)
        except Exception as e:
            _serialization_logger.warning("Failed to serialize enum value for %r: %s", type(obj).__name__, e)

    # Handle objects with __dict__
    if hasattr(obj, '__dict__'):
        try:
            return _make_json_serializable(obj.__dict__)
        except Exception as e:
            _serialization_logger.warning("Failed to serialize __dict__ for %r: %s", type(obj).__name__, e)

    # Fallback: convert to string
    try:
        return str(obj)
    except Exception as e:
        _serialization_logger.warning("str() fallback failed for %r: %s — returning empty string", type(obj).__name__, e)
        return ""


# Config keys used internally by BaseLLMClient — never forwarded to LLM API payloads.
_INTERNAL_CONFIG_KEYS: frozenset = frozenset({
    "api_key", "timeout", "connect_timeout", "max_retries",
    "retry_backoff_seconds", "endpoint", "model_info_cache_ttl",
    "allow_model_fallback",
})


def _extract_stream_content(response: requests.Response) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Collect SSE chat-completion chunks without quadratic string concatenation."""
    chunks: List[str] = []
    data: Optional[Dict[str, Any]] = None

    for line in response.iter_lines():
        if not line:
            continue

        if line.startswith(b"data: "):
            line = line[6:]
        elif line.startswith("data: "):
            line = line[6:]

        if line in (b"[DONE]", "[DONE]"):
            continue

        try:
            line_str = line.decode() if isinstance(line, bytes) else line
            chunk = json.loads(line_str)

            if "choices" in chunk and chunk["choices"]:
                delta = chunk["choices"][0].get("delta", {})
                content_piece = delta.get("content")
                if content_piece:
                    chunks.append(content_piece)

            data = chunk
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.debug(f"Skipped invalid streaming line: {line[:50]}")
            continue

    return "".join(chunks), data



class BaseLLMClient(ABC):
    """
    Abstract base class for LLM clients.
    """
    
    def __init__(
        self,
        model_name: str,
        base_url: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize the LLM client.
        
        Args:
            model_name: Name of the model to use
            base_url: Base URL for the API
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional configuration
        """
        self.model_name = model_name
        # Validate and normalize base URL
        if not base_url or not base_url.strip():
            raise ValueError("base_url cannot be empty. Please provide a valid URL (e.g., 'http://192.168.200.23:11642/v1')")
        parsed = urlparse(base_url.strip())
        _allowed_schemes = {"http", "https", "ws", "wss"}
        if parsed.scheme not in _allowed_schemes:
            raise ValueError(
                f"base_url has unsupported scheme '{parsed.scheme}'. "
                f"Allowed: {sorted(_allowed_schemes)}. Got: '{base_url}'"
            )
        if not parsed.netloc:
            raise ValueError(
                f"base_url is missing a host/netloc. Got: '{base_url}'. "
                f"Example: 'http://localhost:11434'"
            )
        self.base_url = base_url.rstrip('/')
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.config = kwargs
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
    
    def _generate_params(self, **call_kwargs) -> Dict[str, Any]:
        """
        Merge constructor-level generation config with call-time overrides.

        Priority (lowest → highest): self.config defaults < self.temperature /
        self.max_tokens < call_kwargs.  None-valued call_kwargs are ignored so
        that an unset dynamic_max_tokens doesn't clobber the instance default.
        """
        params: Dict[str, Any] = {}
        for k, v in self.config.items():
            if k not in _INTERNAL_CONFIG_KEYS:
                params[k] = v
        params["temperature"] = self.temperature
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens
        params.update({k: v for k, v in call_kwargs.items() if v is not None})
        return params

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        **kwargs
    ) -> "LLMResponse":
        """
        Generate a response from the LLM.
        
        Args:
            messages: List of message dictionaries
            tools: Optional list of tools the model can use
            stream: Whether to stream the response
            
        Returns:
            LLMResponse object
            
        Raises:
            NotImplementedError: This is an abstract method
        """
        raise NotImplementedError("Subclasses must implement generate()")
    
    def _make_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        stream: bool = False,
        **kwargs
    ) -> requests.Response:
        """
        Make an HTTP request to the API.
        
        Args:
            endpoint: API endpoint to call (appended to base_url)
            payload: Request payload
            stream: Whether to stream the response
            
        Returns:
            Response object
            
        Raises:
            ConnectionError: If cannot connect to API server
            RuntimeError: If API returns error response
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Content-Type": "application/json"
        }

        timeout = self.config.get("timeout", 300)
        connect_timeout = self.config.get("connect_timeout", 10)
        if isinstance(timeout, (tuple, list)) and len(timeout) == 2:
            request_timeout = (timeout[0], timeout[1])
        elif isinstance(timeout, dict):
            request_timeout = (
                timeout.get("connect", connect_timeout),
                timeout.get("read", 300),
            )
        else:
            request_timeout = (connect_timeout, timeout)

        max_retries = int(self.config.get("max_retries", 3))
        backoff_base = float(self.config.get("retry_backoff_seconds", 0.5))
        retry_statuses = {429, 500, 502, 503, 504}
        
        # Add API key if provided
        if "api_key" in self.config:
            headers["Authorization"] = f"Bearer {self.config['api_key']}"
        
        # Fast path: Try to validate payload with json.dumps (C-level, very fast)
        # If payload is already serializable (common case), skip recursive walk.
        try:
            json.dumps(payload)
            clean_payload = payload
        except (TypeError, ValueError):
            # Slow path: Fallback to recursive conversion for non-serializable objects.
            clean_payload = _make_json_serializable(payload)

        logger.debug(f"Sending request to {url}")
        logger.debug(f"Payload keys: {list(clean_payload.keys())}")
        logger.debug(f"Messages: {len(clean_payload.get('messages', []))}")
        if 'tools' in clean_payload:
            logger.debug(f"Tools: {len(clean_payload['tools'])} tools included")

        attempt = 0
        last_error: Optional[BaseException] = None

        while attempt <= max_retries:
            try:
                response = self._session.post(
                    url,
                    json=clean_payload,
                    headers=headers,
                    stream=stream,
                    timeout=request_timeout,
                    **kwargs
                )
                if response.status_code in retry_statuses and attempt < max_retries:
                    raise requests.exceptions.HTTPError(response=response)

                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else None
                if status_code in retry_statuses and attempt < max_retries:
                    last_error = e
                    delay = backoff_base * (2 ** attempt)
                    logger.warning(
                        f"HTTP {status_code} from {self.base_url}; retrying in {delay:.2f}s "
                        f"({attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                    attempt += 1
                    continue

                error_text = e.response.text if e.response is not None else "No response body"
                logger.error(f"HTTP error {status_code or 'unknown'}: {error_text}")
                logger.error(f"Request URL: {url}")
                logger.debug(f"Full payload sent: {json.dumps(clean_payload, indent=2, default=str)}")
                raise RuntimeError(
                    f"API error ({status_code or 'unknown'}): {str(e)}. "
                    f"URL: {url}. "
                    f"Response: {error_text}"
                ) from e
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                last_error = e
                if attempt >= max_retries:
                    break
                delay = backoff_base * (2 ** attempt)
                logger.warning(
                    f"Request to {self.base_url} failed ({type(e).__name__}); retrying in {delay:.2f}s "
                    f"({attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
                attempt += 1

        if isinstance(last_error, requests.exceptions.Timeout):
            logger.error(f"Timeout error: {last_error}")
            raise TimeoutError(
                f"Request to {self.base_url} timed out after {request_timeout[1]}s. "
                f"The service may be overloaded. Error: {last_error}"
            ) from last_error

        if isinstance(last_error, requests.exceptions.ConnectionError):
            logger.error(f"Connection error to {self.base_url}: {last_error}")
            raise ConnectionError(
                f"Failed to connect to {self.base_url}. Please ensure the service is running. Error: {last_error}"
            ) from last_error

        if last_error is not None:
            raise RuntimeError(f"Unexpected API error: {last_error}") from last_error

        raise RuntimeError("Request failed without a captured error")

