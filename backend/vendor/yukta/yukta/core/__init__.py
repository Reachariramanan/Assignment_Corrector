"""
Core module for Yukta Agent System.
Contains agent, memory, message, and LLM client functionality.
"""

# Import storage at module level (no circular dependencies)
from .storage import BaseStorageBackend, JSONFileStorage, StorageCorruptionError

# Lazy imports to avoid circular dependencies are handled by importing directly
# in submodules and main package __init__.py

__all__ = [
    'BaseStorageBackend',
    'JSONFileStorage',
    'StorageCorruptionError',
]
