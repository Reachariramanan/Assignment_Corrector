"""
MemoryConfig - Configuration for memory management.
"""

from typing import Optional, Union
from ..core.storage import BaseStorageBackend, JSONFileStorage
from .config import Config

class MemoryConfig:
    """
    Configuration for memory management.
    
    Attributes:
        max_tokens: Maximum tokens in active memory before saving
        max_messages: Maximum messages in active memory (None for unlimited)
        kv_cache_size: Number of recent messages to keep in KV cache
        auto_save: Whether to auto-save when limit exceeded
        storage_backend: Storage backend for persistence
    """
    
    def __init__(
        self,
        max_tokens: int = 4096,
        max_messages: Optional[int] = None,
        kv_cache_size: int = 10,
        auto_save: bool = True,
        storage_backend: Optional[BaseStorageBackend] = None,
        storage_dir: str = "",
        max_archive_size: int = 500,
    ):
        """
        Initialize memory configuration.

        Args:
            max_tokens: Maximum tokens in active memory before saving
            max_messages: Maximum messages in active memory (None for unlimited)
            kv_cache_size: Number of recent messages to keep in KV cache
            auto_save: Whether to auto-save when limit exceeded
            storage_dir: Directory to save chat sessions
            max_archive_size: Maximum number of archived (overflowed) messages to retain in memory
        """
        # Validate types
        if not isinstance(max_tokens, int) or max_tokens < 0:
            raise ValueError(f"max_tokens must be a non-negative int, got {max_tokens}")
        if max_messages is not None and (not isinstance(max_messages, int) or max_messages < 0):
            raise ValueError(f"max_messages must be a non-negative int or None, got {max_messages}")
        if not isinstance(kv_cache_size, int) or kv_cache_size < 0:
            raise ValueError(f"kv_cache_size must be a non-negative int, got {kv_cache_size}")
        if not isinstance(max_archive_size, int) or max_archive_size < 1:
            raise ValueError(f"max_archive_size must be a positive int, got {max_archive_size}")

        self.max_tokens = max_tokens
        self.max_messages = max_messages
        self.kv_cache_size = kv_cache_size
        self.auto_save = auto_save
        self.max_archive_size = max_archive_size
        
        # Initialize backend with proper default directory
        storage_path = storage_dir if storage_dir else Config.MEMORY_STORAGE_DIR
        if storage_backend:
            self.storage_backend = storage_backend
        else:
            self.storage_backend = JSONFileStorage(storage_path)
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "max_tokens": self.max_tokens,
            "max_messages": self.max_messages,
            "kv_cache_size": self.kv_cache_size,
            "auto_save": self.auto_save,
            "max_archive_size": self.max_archive_size,
        }
    
    def __repr__(self) -> str:
        return f"MemoryConfig(tokens={self.max_tokens}, messages={self.max_messages}, cache={self.kv_cache_size})"