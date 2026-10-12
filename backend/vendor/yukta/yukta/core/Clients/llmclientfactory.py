"""
LLM Client Module
Handles integration with various LLM backends: Ollama, vLLM, and remote endpoints.
Supports tool calling and streaming responses.
"""

import json
from typing import List, Dict, Any, Optional
from enum import Enum
from .base_client import BaseLLMClient
from .ollama_client import OllamaClient
from .vllm_client import VLLMClient
from .remote_client import RemoteEndpointClient
from .hf_client import HuggingFaceClient
from .sglang_client import SGLangClient
from .lmstudio_client import LMStudioClient


class ModelType(Enum):
    """Enumeration of supported model types."""
    OLLAMA = "ollama"
    VLLM = "vllm"
    REMOTE = "remote"
    OPENAI_COMPATIBLE = "openai_compatible"
    HUGGINGFACE = "huggingface"
    SGLANG = "sglang"
    LM_STUDIO = "lm_studio"

class LLMClientFactory:
    """
    Factory class for creating LLM clients.
    """
    
    @staticmethod
    def create_client(
        model_type: str,
        model_name: str,
        base_url: Optional[str] = None,
        **kwargs
    ) -> BaseLLMClient:
        """
        Create an LLM client based on the model type.
        
        Args:
            model_type: Type of model (Ollama, vLLM, Remote, LM Studio)
            model_name: Name of the model
            base_url: Base URL for the API (uses defaults if not provided)
            **kwargs: Additional configuration
            
        Returns:
            LLM client instance
        """
        if model_type == ModelType.OLLAMA:
            url = base_url or "http://localhost:11434"
            return OllamaClient(model_name, url, **kwargs)
        
        elif model_type == ModelType.VLLM:
            url = base_url or "http://192.168.200.23:11642/v1"
            return VLLMClient(model_name, url, **kwargs)
        
        elif model_type in [ModelType.REMOTE, ModelType.OPENAI_COMPATIBLE]:
            if not base_url:
                raise ValueError("base_url is required for remote endpoints")
            return RemoteEndpointClient(model_name, base_url, **kwargs)
        
        elif model_type == ModelType.HUGGINGFACE:
            token = kwargs.get("api_key") or kwargs.get("hf_token")
            if not token:
                raise ValueError("hf_token or api_key is required for Hugging Face endpoints")
            return HuggingFaceClient(model_name, hf_token=token, base_url=base_url, **kwargs)
        
        elif model_type == ModelType.SGLANG:
            url = base_url or "http://localhost:30000"
            return SGLangClient(model_name, url, **kwargs)
        
        elif model_type == ModelType.LM_STUDIO:
            url = base_url or "http://localhost:1234"
            return LMStudioClient(model_name, url, **kwargs)
        
        else:
            raise ValueError(f"Unsupported model type: {model_type}")
    
    @staticmethod
    def create_ollama(model_name: str = "llama2", **kwargs) -> OllamaClient:
        """Quick helper to create Ollama client."""
        return OllamaClient(model_name, **kwargs)
    
    @staticmethod
    def create_vllm(model_name: str, base_url: str = "http://192.168.200.23:11642/v1", **kwargs) -> VLLMClient:
        """Quick helper to create vLLM client."""
        return VLLMClient(model_name, base_url, **kwargs)
    
    @staticmethod
    def create_remote(model_name: str, base_url: str, api_key: Optional[str] = None, **kwargs) -> RemoteEndpointClient:
        """Quick helper to create remote endpoint client."""
        return RemoteEndpointClient(model_name, base_url, api_key, **kwargs)
    
    @staticmethod
    def create_huggingface(model_name: str, hf_token: str, base_url: Optional[str] = None, **kwargs) -> HuggingFaceClient:
        """Quick helper to create Hugging Face client."""
        return HuggingFaceClient(model_name, hf_token, base_url, **kwargs)
    
    @staticmethod
    def create_sglang(model_name: str, base_url: str = "http://localhost:30000", **kwargs) -> SGLangClient:
        """Quick helper to create SGLang client."""
        return SGLangClient(model_name, base_url, **kwargs)
    
    @staticmethod
    def create_lm_studio(model_name: str, base_url: str = "http://localhost:1234", **kwargs) -> LMStudioClient:
        """Quick helper to create LM Studio client."""
        return LMStudioClient(model_name, base_url, **kwargs)

def format_tools_for_api(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format tools for OpenAI-compatible API.
    
    Args:
        tools: List of tool dictionaries from ToolProcessor
        
    Returns:
        Formatted tools list
    """
    formatted = []
    for tool in tools:
        formatted.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
        })
    return formatted


def parse_tool_call_arguments(arguments_str: str) -> Dict[str, Any]:
    """
    Parse tool call arguments from JSON string.
    
    Args:
        arguments_str: JSON string of arguments
        
    Returns:
        Parsed arguments dictionary
    """
    try:
        return json.loads(arguments_str)
    except json.JSONDecodeError:
        return {}
