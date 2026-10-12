from typing import List, Dict, Any, Optional

class LLMResponse:
    """
    Represents a response from an LLM.
    
    Attributes:
        content: The text content of the response
        tool_calls: List of tool calls requested by the model
        finish_reason: Reason for completion (stop, tool_calls, length, etc.)
        usage: Token usage information (including cache data)
        raw_response: Raw response from the API
        cached_tokens: Number of tokens served from KV cache
    """
    
    def __init__(
        self,
        content: str = "",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        finish_reason: str = "stop",
        usage: Optional[Dict[str, int]] = None,
        raw_response: Optional[Dict[str, Any]] = None,
        cached_tokens: int = 0,
        incomplete: bool = False,
        continuation_count: int = 0
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.finish_reason = finish_reason
        self.usage = usage or {}
        self.raw_response = raw_response or {}
        self.cached_tokens = cached_tokens
        self.incomplete = incomplete
        self.continuation_count = continuation_count
    
    def has_tool_calls(self) -> bool:
        """Check if the response contains tool calls."""
        return len(self.tool_calls) > 0
    
    def has_cache_hit(self) -> bool:
        """Check if response used KV cache."""
        return self.cached_tokens > 0 or self._extract_cached_tokens() > 0
    
    def _extract_cached_tokens(self) -> int:
        """Extract cached token count from usage data."""
        # OpenAI format
        if "prompt_tokens_details" in self.usage:
            details = self.usage["prompt_tokens_details"]
            if isinstance(details, dict):
                return details.get("cached_tokens", 0)
        
        # Anthropic format
        if "cache_read_input_tokens" in self.usage:
            return self.usage.get("cache_read_input_tokens", 0)
        
        # vLLM/generic format
        if "cached_tokens" in self.usage:
            return self.usage.get("cached_tokens", 0)
        
        return self.cached_tokens
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information from response."""
        cached = self._extract_cached_tokens()
        total_prompt = self.usage.get("prompt_tokens", 0)
        
        return {
            "cached_tokens": cached,
            "cache_hit": cached > 0,
            "cache_hit_rate": cached / total_prompt if total_prompt > 0 else 0.0,
            "prompt_tokens": total_prompt,
            "uncached_tokens": total_prompt - cached
        }
    
    def is_incomplete(self) -> bool:
        """Check if response was cut off due to max_tokens."""
        return self.finish_reason == "length" or self.incomplete
    
    def get_completion_status(self) -> Dict[str, Any]:
        """Get response completion details."""
        return {
            "is_complete": not self.is_incomplete(),
            "finish_reason": self.finish_reason,
            "continuations": self.continuation_count,
            "status": "INCOMPLETE - continued" if self.is_incomplete() else "COMPLETE"
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "content": self.content,
            "tool_calls": self.tool_calls,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "cached_tokens": self.cached_tokens,
            "incomplete": self.incomplete,
            "continuation_count": self.continuation_count,
            "cache_info": self.get_cache_info(),
            "completion_status": self.get_completion_status()
        }
