"""
Message Module
Defines message structure and roles for agent conversations.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from enum import Enum
import json
import logging
import base64

logger = logging.getLogger(__name__)


def _make_json_serializable(obj: Any, warnings: Optional[List[str]] = None) -> Tuple[Any, List[str]]:
    """
    Recursively convert objects to JSON-serializable format.
    Handles protobuf objects, enums, repeated fields, NumPy arrays, PyTorch tensors, bytes, and other non-serializable types.
    
    Args:
        obj: Object to convert
        warnings: List to accumulate warning messages (created if None)
        
    Returns:
        Tuple of (JSON-serializable version of object, list of warnings)
    """
    if warnings is None:
        warnings = []
    
    # Handle None
    if obj is None:
        return None, warnings
    
    # Handle basic JSON-serializable types
    if isinstance(obj, (str, int, float, bool)):
        return obj, warnings
    
    # Handle bytes - convert to base64
    if isinstance(obj, bytes):
        try:
            result = base64.b64encode(obj).decode('ascii')
            warnings.append(f"Bytes object converted to base64 string (size: {len(obj)} bytes)")
            return result, warnings
        except Exception as e:
            warnings.append(f"Failed to convert bytes: {e}")
            return str(obj), warnings
    
    # Handle lists and tuples
    if isinstance(obj, (list, tuple)):
        result = []
        for item in obj:
            converted, _ = _make_json_serializable(item, warnings)
            result.append(converted)
        return result, warnings
    
    # Handle dictionaries
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            converted_key, _ = _make_json_serializable(k, warnings)
            converted_val, _ = _make_json_serializable(v, warnings)
            result[converted_key] = converted_val
        return result, warnings
    
    # Handle NumPy arrays
    try:
        import numpy as np
        if isinstance(obj, np.ndarray):
            try:
                result = obj.tolist()
                warnings.append(f"NumPy array {obj.shape} converted to list (dtype: {obj.dtype})")
                return result, warnings
            except Exception as e:
                warnings.append(f"Failed to convert NumPy array: {e}")
                return f"<numpy.ndarray shape={obj.shape} dtype={obj.dtype}>", warnings
    except ImportError:
        logger.debug("numpy not available, skipping NumPy array conversion")
    
    # Handle PyTorch tensors
    try:
        import torch
        if isinstance(obj, torch.Tensor):
            try:
                result = obj.detach().cpu().tolist() if obj.numel() < 10000 else f"<torch.Tensor shape={tuple(obj.shape)}>"
                if isinstance(result, str):
                    warnings.append(f"Large PyTorch tensor {tuple(obj.shape)} converted to shape descriptor (too large to convert)")
                else:
                    warnings.append(f"PyTorch tensor {tuple(obj.shape)} converted to list")
                return result, warnings
            except Exception as e:
                warnings.append(f"Failed to convert PyTorch tensor: {e}")
                return f"<torch.Tensor shape={tuple(obj.shape)}>", warnings
    except ImportError:
        logger.debug("torch not available, skipping PyTorch tensor conversion")
    
    # Handle protobuf objects with DESCRIPTOR
    if hasattr(obj, 'DESCRIPTOR'):
        try:
            result, _ = _make_json_serializable(obj.__dict__, warnings)
            return result, warnings
        except Exception as e:
            warnings.append(f"Failed to convert protobuf object: {e}")
            return str(obj), warnings
    
    # Handle protobuf repeated fields (RepeatedScalarContainer, RepeatedCompositeContainer)
    if type(obj).__name__ in ('RepeatedScalarContainer', 'RepeatedCompositeContainer'):
        result = []
        for item in obj:
            converted, _ = _make_json_serializable(item, warnings)
            result.append(converted)
        return result, warnings
    
    # Handle enums
    if hasattr(obj, 'value'):
        try:
            return str(obj.value), warnings
        except (AttributeError, TypeError) as e:
            warnings.append(f"Failed to convert enum: {e}")
            return str(obj), warnings
    
    # Handle datetime objects
    if isinstance(obj, datetime):
        return obj.isoformat(), warnings
    
    # Handle objects with __dict__
    if hasattr(obj, '__dict__'):
        try:
            result, _ = _make_json_serializable(obj.__dict__, warnings)
            return result, warnings
        except Exception as e:
            warnings.append(f"Failed to convert object with __dict__: {e}")
            return str(obj), warnings
    
    # Fallback: convert to string
    try:
        result = str(obj)
        warnings.append(f"Converted {type(obj).__name__} object to string (lossy conversion)")
        return result, warnings
    except Exception as e:
        warnings.append(f"Failed to convert {type(obj).__name__} object: {e}")
        return None, warnings



class Role(Enum):
    """Message roles in conversation."""
    SYSTEM = "system"
    USER = "user"
    AGENT = "agent"
    TOOL = "tool"


class Message:
    """
    Represents a single message in a conversation.
    
    A message contains the role (system/user/agent/tool), content,
    optional tool calls, and metadata for tracking and analysis.
    
    Attributes:
        role: Message role (system, user, agent, tool)
        content: Message content/text
        tool_calls: Optional list of tool calls made by agent
        tool_call_id: Optional ID if this is a tool response
        metadata: Additional metadata (tags, context, etc.)
        timestamp: When the message was created
        token_count: Estimated token count
        message_id: Unique message identifier
        sanitization_log: Audit log of any sanitization/conversion performed
    """
    
    def __init__(
        self,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_call_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None
    ):
        """
        Initialize a message.
        
        Args:
            role: Message role (system, user, agent, tool)
            content: Message content (will be converted to string if not already)
            tool_calls: Tool calls if agent is requesting tool use
            tool_call_id: ID of tool call this message responds to
            metadata: Additional metadata
            message_id: Unique ID (auto-generated if not provided)
        """
        # Validate role
        if role not in [r.value for r in Role]:
            raise ValueError(f"Invalid role: {role}. Must be one of {[r.value for r in Role]}")
        
        self.role = role
        
        # Audit log for tracking sanitization/conversions
        self.sanitization_log: List[str] = []
        
        # Ensure content is always a string
        if not isinstance(content, str):
            # Clean non-serializable objects first
            try:
                cleaned_content, warnings = _make_json_serializable(content)
                if warnings:
                    logger.debug(f"[MESSAGE] Content sanitization warnings: {'; '.join(warnings)}")
                    self.sanitization_log.extend([f"content: {w}" for w in warnings])
                self.content = json.dumps(cleaned_content) if isinstance(cleaned_content, (dict, list)) else str(cleaned_content)
            except Exception as e:
                msg = f"Failed to sanitize content (fallback to string): {e}"
                logger.warning(f"[MESSAGE] {msg}")
                self.sanitization_log.append(f"content: {msg}")
                self.content = str(content)
        else:
            self.content = content
        
        # Sanitize tool_calls
        self.tool_calls = []
        if tool_calls:
            try:
                for i, tool_call in enumerate(tool_calls):
                    cleaned_call, warnings = _make_json_serializable(tool_call)
                    if warnings:
                        logger.debug(f"[MESSAGE] Tool call {i} sanitization warnings: {'; '.join(warnings)}")
                        self.sanitization_log.extend([f"tool_call[{i}]: {w}" for w in warnings])
                    self.tool_calls.append(cleaned_call)
            except Exception as e:
                msg = f"Failed to sanitize tool_calls (using original): {e}"
                logger.warning(f"[MESSAGE] {msg}")
                self.sanitization_log.append(f"tool_calls: {msg}")
                self.tool_calls = tool_calls
        
        # Sanitize metadata
        self.metadata = {}
        if metadata:
            try:
                cleaned_meta, warnings = _make_json_serializable(metadata)
                if warnings:
                    logger.debug(f"[MESSAGE] Metadata sanitization warnings: {'; '.join(warnings)}")
                    self.sanitization_log.extend([f"metadata: {w}" for w in warnings])
                self.metadata = cleaned_meta if isinstance(cleaned_meta, dict) else {}
            except Exception as e:
                msg = f"Failed to sanitize metadata (using original dict): {e}"
                logger.warning(f"[MESSAGE] {msg}")
                self.sanitization_log.append(f"metadata: {msg}")
                self.metadata = metadata if isinstance(metadata, dict) else {}
        
        self.tool_call_id = tool_call_id
        self.timestamp = datetime.now()
        self.message_id = message_id or self._generate_id()
        self.token_count = self._estimate_tokens()
    
    def _generate_id(self) -> str:
        """Generate a unique message ID."""
        return f"msg_{self.timestamp.strftime('%Y%m%d_%H%M%S_%f')}"
    
    def _estimate_tokens(self) -> int:
        """
        Estimate token count for the message.
        Uses simple heuristic: ~4 characters per token on average.
        
        Returns:
            Estimated token count
        """
        # Ensure content is a string (should always be, but be safe)
        content_str = self.content if isinstance(self.content, str) else str(self.content)
        char_count = len(content_str)
        # Approximation: ~4 chars/token works for English prose; accuracy drops for code,
        # JSON, and non-Latin scripts. Inject a real tokenizer via tokenizer_fn if precision matters.
        token_count = max(1, char_count // 4)
        
        # Add tokens for tool calls
        if self.tool_calls:
            try:
                tool_calls_str = json.dumps(self.tool_calls)
                token_count += max(1, len(tool_calls_str) // 4)
            except (TypeError, ValueError) as e:
                logger.warning(f"Failed to calculate tool call tokens: {e}")
        
        # Minimum 1 token
        return max(1, token_count)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert message to dictionary format for LLM API.
        
        Returns standard format compatible with OpenAI-style APIs.
        
        Returns:
            Dictionary with role and content (and tool_calls if present)
        """
        # Map internal "agent" role to OpenAI-compatible "assistant" role
        role = "assistant" if self.role == "agent" else self.role
        
        msg = {
            "role": role,
            "content": self.content
        }
        
        # Add tool calls if present
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        
        # Add tool_call_id if this is a tool response
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        
        return msg
    
    def to_full_dict(self) -> Dict[str, Any]:
        """
        Convert message to full dictionary with all fields.
        
        Includes metadata, timestamps, IDs, and audit logs for persistence.
        
        Returns:
            Complete dictionary representation
        """
        result = {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "tool_call_id": self.tool_call_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "token_count": self.token_count
        }
        
        # Include sanitization audit log if there were any conversions
        if self.sanitization_log:
            result["sanitization_log"] = self.sanitization_log
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """
        Create a Message from a dictionary.
        
        Args:
            data: Dictionary containing message data
            
        Returns:
            Message instance
        """
        msg = cls(
            role=data["role"],
            content=data["content"],
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
            metadata=data.get("metadata"),
            message_id=data.get("message_id")
        )
        
        # Restore timestamp if provided
        if "timestamp" in data:
            try:
                msg.timestamp = datetime.fromisoformat(data["timestamp"])
            except (ValueError, TypeError):
                pass  # Keep auto-generated timestamp

        if "token_count" in data:
            try:
                msg.token_count = int(data["token_count"])
            except (ValueError, TypeError):
                msg.token_count = msg._estimate_tokens()
        
        # Restore sanitization log if provided (audit trail)
        if "sanitization_log" in data:
            try:
                msg.sanitization_log = data.get("sanitization_log", [])
            except (TypeError, KeyError) as e:
                logger.warning(f"Failed to restore sanitization_log: {e}")
        
        return msg
    
    def is_system(self) -> bool:
        """Check if this is a system message."""
        return self.role == Role.SYSTEM.value
    
    def is_user(self) -> bool:
        """Check if this is a user message."""
        return self.role == Role.USER.value
    
    def is_agent(self) -> bool:
        """Check if this is an agent message."""
        return self.role == Role.AGENT.value
    
    def is_tool(self) -> bool:
        """Check if this is a tool message."""
        return self.role == Role.TOOL.value
    
    def has_tool_calls(self) -> bool:
        """Check if message contains tool calls."""
        return len(self.tool_calls) > 0
    
    def add_metadata(self, key: str, value: Any) -> None:
        """
        Add metadata to the message.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get metadata value.
        
        Args:
            key: Metadata key
            default: Default value if key not found
            
        Returns:
            Metadata value or default
        """
        return self.metadata.get(key, default)
    
    def __repr__(self) -> str:
        """String representation of message."""
        role_display = self.role.upper()
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        tools = f", tools={len(self.tool_calls)}" if self.tool_calls else ""
        return f"Message({role_display}: {content_preview}, tokens={self.token_count}{tools})"
    
    def __str__(self) -> str:
        """User-friendly string representation."""
        return f"[{self.role}] {self.content}"
    
    def __len__(self) -> int:
        """Return token count when len() is called."""
        return self.token_count
    
    def __eq__(self, other: object) -> bool:
        """Check equality based on message_id."""
        if not isinstance(other, Message):
            return False
        return self.message_id == other.message_id


# Convenience functions for creating messages

def system_message(content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
    """
    Create a system message.
    
    Args:
        content: System message content
        metadata: Optional metadata
        
    Returns:
        System Message instance
    """
    return Message(Role.SYSTEM.value, content, metadata=metadata)


def user_message(content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
    """
    Create a user message.
    
    Args:
        content: User message content
        metadata: Optional metadata
        
    Returns:
        User Message instance
    """
    return Message(Role.USER.value, content, metadata=metadata)


def agent_message(
    content: str,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Message:
    """
    Create an agent message.
    
    Args:
        content: Agent message content
        tool_calls: Optional tool calls
        metadata: Optional metadata
        
    Returns:
        Agent Message instance
    """
    return Message(Role.AGENT.value, content, tool_calls=tool_calls, metadata=metadata)


def tool_message(
    content: str,
    tool_call_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Message:
    """
    Create a tool response message.
    
    Args:
        content: Tool response content
        tool_call_id: ID of the tool call this responds to
        metadata: Optional metadata
        
    Returns:
        Tool Message instance
    """
    return Message(
        Role.TOOL.value,
        content,
        tool_call_id=tool_call_id,
        metadata=metadata
    )


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for arbitrary text.
    
    Args:
        text: Text to estimate
        
    Returns:
        Estimated token count
    """
    return max(1, len(text) // 4)
