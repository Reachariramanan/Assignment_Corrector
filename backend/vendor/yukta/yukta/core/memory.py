"""
Memory Module
Smart memory management with chat persistence and KV caching.
Automatically saves chats when memory limits are exceeded and maintains KV cache.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
import threading
from .Chat.chat import ChatManager
from .storage import BaseStorageBackend
from ..config.memory_config import MemoryConfig
# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def set_memory_logging_level(level: int) -> None:
    """
    Set the logging level for memory module.
    
    Args:
        level: Logging level (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR)
    
    Examples:
        # Set to DEBUG for detailed logs
        set_memory_logging_level(logging.DEBUG)
        
        # Set to WARNING for fewer logs
        set_memory_logging_level(logging.WARNING)
    """
    logger.setLevel(level)
    logger.info(f"Memory logging level set to: {logging.getLevelName(level)}")




class Memory:
    """
    Smart memory manager that integrates with Chat for persistence.
    
    Features:
    - Automatic chat persistence when memory limits exceeded
    - KV cache management for efficient context retrieval
    - Session-based storage with unique IDs
    - Sliding window of recent messages
    """
    
    def __init__(
        self,
        system_prompt: str,
        config: Optional[MemoryConfig] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize memory manager.
        
        Args:
            system_prompt: System prompt for the chat
            config: Memory configuration
            session_id: Optional session ID (auto-generated if not provided)
            metadata: Optional metadata for the session
        """
        self.config = config or MemoryConfig()
        
        # Create chat manager for persistence
        self.chat_manager = ChatManager(storage_backend=self.config.storage_backend)
        
        # Initialize chat session
        self.chat = self.chat_manager.create_chat(
            system_prompt=system_prompt,
            chat_id=session_id,
            metadata=metadata or {}
        )
        
        self.session_id = self.chat.chat_id
        
        logger.info(f"Memory initialized: session_id={self.session_id}, max_tokens={self.config.max_tokens}, max_messages={self.config.max_messages}")
        
        # Thread safety: RLock for concurrent save/add operations
        self._state_lock = threading.RLock()
        
        # KV Cache: Store indices of cached messages
        self._kv_cache: List[int] = []
        self._cache_valid = True
        self._last_cache_update = 0
        
        # LLM KV Cache tracking
        self._llm_cached_tokens = 0  # Tokens cached by LLM
        self._llm_cache_creation_tokens = 0  # Tokens used to create cache
        self._llm_cache_read_tokens = 0  # Tokens read from cache
        self._last_llm_response: Optional[Dict[str, Any]] = None
        
        # Statistics
        self.stats = {
            "total_messages_added": 0,
            "total_tokens_processed": 0,
            "saves_triggered": 0,
            "cache_updates": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "messages_archived": 0,
            "llm_cache_hits": 0,  # From LLM response
            "llm_cache_misses": 0,  # From LLM response
            "total_cached_tokens": 0,  # Total tokens cached by LLM
            "cache_cost_savings": 0.0  # Estimated cost savings
        }
        
        # Archive storage for old messages
        self._archived_messages: List[Dict[str, Any]] = []
    
    def add_user_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add a user message to memory (thread-safe).

        Args:
            content: User message content
            metadata: Optional metadata
        """
        with self._state_lock:
            msg = self.chat.add_user_message(content, metadata)
            self.stats["total_messages_added"] += 1
            self.stats["total_tokens_processed"] += msg.token_count

            logger.debug(f"[{self.session_id[:8]}] User message added: {len(content)} chars, ~{msg.token_count} tokens")

            # Invalidate cache when new message added
            self._cache_valid = False

            # Check if we need to save
            self._check_and_save()
    
    def add_agent_message(
        self,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        llm_response: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an agent message to memory (thread-safe).

        Args:
            content: Agent message content
            tool_calls: Optional tool calls
            metadata: Optional metadata
            llm_response: Optional LLM response with usage/cache data
        """
        with self._state_lock:
            msg = self.chat.add_agent_message(content, tool_calls, metadata)
            self.stats["total_messages_added"] += 1
            self.stats["total_tokens_processed"] += msg.token_count

            logger.debug(f"[{self.session_id[:8]}] Agent message added: {len(content)} chars, ~{msg.token_count} tokens, tool_calls={len(tool_calls) if tool_calls else 0}")

            # Update LLM KV cache info if provided
            if llm_response:
                self._update_llm_cache_from_response(llm_response)

            # Invalidate cache
            self._cache_valid = False

            # Check if we need to save
            self._check_and_save()
    
    def add_tool_message(
        self,
        content: str,
        tool_call_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a tool response message to memory (thread-safe).
        
        Args:
            content: Tool response content
            tool_call_id: ID of the tool call
            metadata: Optional metadata
        """
        with self._state_lock:
            try:
                msg = self.chat.add_tool_message(content, tool_call_id, metadata)
                self.stats["total_messages_added"] += 1
                self.stats["total_tokens_processed"] += msg.token_count
                
                logger.debug(f"[{self.session_id[:8]}] Tool message added: tool_call_id={tool_call_id}, ~{msg.token_count} tokens")
                
                # Invalidate cache
                self._cache_valid = False
                
                # Check if we need to save (this also uses the lock)
                self._check_and_save()
            except Exception as e:
                logger.error(f"[{self.session_id[:8]}] Error adding tool message: {e}")
                raise
    
    def _check_and_save(self) -> None:
        """
        Check if memory limits exceeded and save if necessary.
        """
        if not self.config.auto_save:
            return
        
        token_count = self.chat.get_token_count()
        message_count = self.chat.get_message_count()
        
        # Check token limit
        if token_count > self.config.max_tokens:
            logger.info(f"[{self.session_id[:8]}] Token limit exceeded: {token_count}/{self.config.max_tokens} - triggering overflow handling")
            self._handle_memory_overflow()
        
        # Check message limit
        elif self.config.max_messages and message_count > self.config.max_messages:
            logger.info(f"[{self.session_id[:8]}] Message limit exceeded: {message_count}/{self.config.max_messages} - triggering overflow handling")
            self._handle_memory_overflow()
    
    def _handle_memory_overflow(self) -> None:
        """
        Handle memory overflow by archiving old messages and saving (with transactional semantics).
        Uses lock to prevent concurrent modifications during archiving.
        """
        with self._state_lock:
            logger.warning(f"[{self.session_id[:8]}] Memory overflow detected - archiving older messages")
            
            # Save current state FIRST - before archiving
            try:
                self.save()
                logger.debug(f"[{self.session_id[:8]}] Saved current state before archiving")
            except Exception as save_err:
                logger.error(f"[{self.session_id[:8]}] Failed to save before archiving: {save_err}")
                # Don't continue with archiving if we can't save
                raise
            
            # Archive old messages (keep only recent N in active memory)
            messages_to_keep = self.config.kv_cache_size
            total_messages = len(self.chat.messages)
            
            if total_messages > messages_to_keep:
                # Archive older messages
                messages_to_archive = total_messages - messages_to_keep
                
                logger.info(f"[{self.session_id[:8]}] Archiving {messages_to_archive} messages (keeping {messages_to_keep} in active memory)")
                
                # Track messages we're about to remove in case we need to rollback
                removed_messages = []
                
                try:
                    for _ in range(messages_to_archive):
                        if self.chat.messages:
                            archived_msg = self.chat.messages[0]  # Get first message
                            removed_messages.append(archived_msg)  # Track for potential rollback
                            self._archived_messages.append(archived_msg.to_full_dict())
                            self.chat.messages.pop(0)  # Remove from active memory
                            self.stats["messages_archived"] += 1

                    # Enforce archive size cap to prevent unbounded memory growth
                    max_archive = getattr(self.config, "max_archive_size", 500)
                    if len(self._archived_messages) > max_archive:
                        excess = len(self._archived_messages) - max_archive
                        self._archived_messages = self._archived_messages[excess:]
                        logger.debug(f"[{self.session_id[:8]}] Archive trimmed: removed {excess} oldest entries (cap={max_archive})")

                    logger.info(f"[{self.session_id[:8]}] Archived {messages_to_archive} messages. Total archived: {len(self._archived_messages)}")
                
                except Exception as archive_err:
                    logger.error(f"[{self.session_id[:8]}] Error during archiving: {archive_err}")
                    # Attempt rollback: re-add removed messages in original order
                    rollback_failed = False
                    for msg in reversed(removed_messages):
                        try:
                            self.chat.messages.insert(0, msg)
                        except Exception as rollback_err:
                            rollback_failed = True
                            logger.error(
                                f"[{self.session_id[:8]}] Rollback FAILED — message may be lost: {rollback_err}"
                            )
                    if rollback_failed:
                        raise RuntimeError(
                            f"Archiving failed and rollback was incomplete — potential message loss. "
                            f"Original error: {archive_err}"
                        ) from archive_err
                    raise Exception(f"Archiving failed and rolled back: {archive_err}") from archive_err
                
                # Update chat stats after successful archiving
                self.chat.stats["total_messages"] = len(self.chat.messages)
        
        # Update KV cache
        self._update_kv_cache()
        
        self.stats["saves_triggered"] += 1
    
    def get_messages(self, include_system: bool = True) -> List[Dict[str, Any]]:
        """
        Get messages in LLM API format.
        System prompt is included once at the beginning.
        
        Args:
            include_system: Whether to include system prompt
            
        Returns:
            List of message dictionaries
        """
        return self.chat.get_messages(include_system=include_system)
    
    def get_kv_cached_messages(self) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Get messages optimized with KV cache.
        
        Returns:
            Tuple of (messages, is_cache_valid)
        """
        messages = self.get_messages()
        
        if self._cache_valid:
            self.stats["cache_hits"] += 1
            logger.debug(f"[{self.session_id[:8]}] Cache hit: reusing {len(self._kv_cache)} cached messages")
        else:
            self.stats["cache_misses"] += 1
            logger.debug(f"[{self.session_id[:8]}] Cache miss: rebuilding cache")
            self._update_kv_cache()
        
        return messages, self._cache_valid
    
    def _update_kv_cache(self) -> None:
        """
        Update KV cache with current message indices.
        Cache is updated every N messages based on kv_cache_size.
        """
        current_msg_count = len(self.chat.messages)
        logger.debug(f"[{self.session_id[:8]}] Updating KV cache with {current_msg_count} messages")
        
        # Determine which messages are cached
        if current_msg_count <= self.config.kv_cache_size:
            # Cache all messages
            self._kv_cache = list(range(current_msg_count))
        else:
            # Cache only recent N messages
            start_idx = current_msg_count - self.config.kv_cache_size
            self._kv_cache = list(range(start_idx, current_msg_count))
        
        self._cache_valid = True
        self._last_cache_update = current_msg_count
        self.stats["cache_updates"] += 1
        logger.debug(f"[{self.session_id[:8]}] KV cache updated: {len(self._kv_cache)} messages cached")
    
    def _update_llm_cache_from_response(self, llm_response: Dict[str, Any]) -> None:
        """
        Update KV cache information from LLM response.
        
        Args:
            llm_response: LLM response containing usage/cache information
        """
        self._last_llm_response = llm_response
        
        # Handle different response formats
        usage = llm_response.get("usage", {})
        
        # OpenAI/Anthropic prompt caching format
        if "prompt_tokens_details" in usage and usage["prompt_tokens_details"] is not None:
            details = usage["prompt_tokens_details"]
            cached = details.get("cached_tokens", 0)
            
            if cached > 0:
                self._llm_cached_tokens = cached
                self.stats["llm_cache_hits"] += 1
                self.stats["total_cached_tokens"] += cached
                logger.info(f"[{self.session_id[:8]}] LLM cache hit: {cached} tokens reused from cache")
            else:
                self.stats["llm_cache_misses"] += 1
                logger.debug(f"[{self.session_id[:8]}] LLM cache miss: no cached tokens")
        
        # Anthropic cache format
        elif "cache_creation_input_tokens" in usage:
            self._llm_cache_creation_tokens = usage.get("cache_creation_input_tokens", 0)
            self._llm_cache_read_tokens = usage.get("cache_read_input_tokens", 0)
            
            if self._llm_cache_read_tokens > 0:
                self._llm_cached_tokens = self._llm_cache_read_tokens
                self.stats["llm_cache_hits"] += 1
                self.stats["total_cached_tokens"] += self._llm_cache_read_tokens
                logger.info(f"[{self.session_id[:8]}] Anthropic cache hit: {self._llm_cache_read_tokens} tokens read from cache")
            else:
                self.stats["llm_cache_misses"] += 1
                logger.debug(f"[{self.session_id[:8]}] Anthropic cache miss")
        
        # vLLM cached tokens format
        elif "cached_tokens" in usage:
            cached = usage.get("cached_tokens", 0)
            if cached > 0:
                self._llm_cached_tokens = cached
                self.stats["llm_cache_hits"] += 1
                self.stats["total_cached_tokens"] += cached
                logger.info(f"[{self.session_id[:8]}] vLLM cache hit: {cached} tokens reused from cache")
            else:
                self.stats["llm_cache_misses"] += 1
                logger.debug(f"[{self.session_id[:8]}] vLLM cache miss")
        
        # Calculate cost savings (assume $1 per 1M input tokens, 90% cache discount)
        if self._llm_cached_tokens > 0:
            original_cost = (usage.get("prompt_tokens", 0) / 1_000_000) * 1.0
            cached_cost = (self._llm_cached_tokens / 1_000_000) * 0.1  # 90% discount
            savings = original_cost - cached_cost
            self.stats["cache_cost_savings"] += savings
            logger.info(f"[{self.session_id[:8]}] Cache cost savings: ${savings:.6f} (total: ${self.stats['cache_cost_savings']:.4f})")
    
    def get_llm_cache_info(self) -> Dict[str, Any]:
        """
        Get LLM KV cache information.
        
        Returns:
            Dictionary with LLM cache statistics
        """
        total_llm_requests = self.stats["llm_cache_hits"] + self.stats["llm_cache_misses"]
        llm_cache_hit_rate = (
            self.stats["llm_cache_hits"] / total_llm_requests
            if total_llm_requests > 0
            else 0.0
        )
        
        return {
            "llm_cached_tokens": self._llm_cached_tokens,
            "llm_cache_creation_tokens": self._llm_cache_creation_tokens,
            "llm_cache_read_tokens": self._llm_cache_read_tokens,
            "total_cached_tokens": self.stats["total_cached_tokens"],
            "llm_cache_hits": self.stats["llm_cache_hits"],
            "llm_cache_misses": self.stats["llm_cache_misses"],
            "llm_cache_hit_rate": llm_cache_hit_rate,
            "cache_cost_savings": self.stats["cache_cost_savings"],
            "last_response": self._last_llm_response
        }
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get KV cache information (application-level cache).
        
        Returns:
            Dictionary with cache statistics
        """
        total_messages = len(self.chat.messages)
        cached_count = len(self._kv_cache)
        new_messages = total_messages - self._last_cache_update if self._cache_valid else total_messages
        
        return {
            "total_messages": total_messages,
            "cached_messages": cached_count,
            "new_messages_since_cache": new_messages,
            "cache_valid": self._cache_valid,
            "cache_size_limit": self.config.kv_cache_size,
            "cache_hit_rate": (
                self.stats["cache_hits"] / (self.stats["cache_hits"] + self.stats["cache_misses"])
                if (self.stats["cache_hits"] + self.stats["cache_misses"]) > 0
                else 0.0
            ),
            "llm_cache": self.get_llm_cache_info()
        }
    
    def save(self, force: bool = False) -> str:
        """
        Save chat session to disk.
        
        Args:
            force: Force save even if auto_save is False
            
        Returns:
            Path to saved file
        """
        if not self.config.auto_save and not force:
            logger.debug(f"[{self.session_id[:8]}] Save skipped")
            return ""
        
        logger.info(f"[{self.session_id[:8]}] Saving session: {len(self.chat.messages)} active messages")
        
        # Save active chat
        saved_path = self.chat_manager.save_chat(self.session_id)
        
        # Save archived messages using the storage backend
        if self._archived_messages:
            logger.info(f"[{self.session_id[:8]}] Saving {len(self._archived_messages)} archived messages")
            archive_data = {
                "session_id": self.session_id,
                "archived_at": datetime.now().isoformat(),
                "archived_messages": self._archived_messages,
                "stats": self.stats
            }
            self.chat_manager.storage.save(f"{self.session_id}_archive", archive_data)
            
        return saved_path
    
    def load(self, session_id: str) -> None:
        """
        Load chat session from disk.
        
        Args:
            session_id: Session ID to load
        """
        logger.info(f"Loading session: {session_id}")
        
        # Load active chat
        self.chat = self.chat_manager.load_chat(session_id)
        self.session_id = session_id
        
        # Load archived messages using the storage backend
        archive_data = self.chat_manager.storage.load(f"{session_id}_archive")
        if archive_data:
            self._archived_messages = archive_data.get("archived_messages", [])
            if "stats" in archive_data:
                self.stats.update(archive_data["stats"])
            logger.info(f"[{self.session_id[:8]}] Loaded {len(self._archived_messages)} archived messages")
            
        # Update KV cache after loading
        self._cache_valid = False
        self._update_kv_cache()
    
    def get_full_history(self) -> List[Dict[str, Any]]:
        """
        Get full conversation history including archived messages.
        
        Returns:
            List of all messages (archived + active)
        """
        full_history = []
        
        # Add archived messages
        full_history.extend(self._archived_messages)
        
        # Add active messages
        for msg in self.chat.messages:
            full_history.append(msg.to_full_dict())
        
        return full_history
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive memory statistics.
        
        Returns:
            Dictionary of statistics
        """
        chat_stats = self.chat.get_stats()
        cache_info = self.get_cache_info()
        llm_cache_info = self.get_llm_cache_info()
        
        return {
            "session_id": self.session_id,
            "active_messages": len(self.chat.messages),
            "archived_messages": len(self._archived_messages),
            "total_messages": len(self.chat.messages) + len(self._archived_messages),
            "total_tokens": self.chat.get_token_count(),
            "max_tokens": self.config.max_tokens,
            "memory_usage_percent": (self.chat.get_token_count() / self.config.max_tokens) * 100,
            "kv_cache": cache_info,
            "llm_kv_cache": llm_cache_info,
            "statistics": self.stats,
            "chat_stats": chat_stats,
            "auto_save_enabled": self.config.auto_save
        }
    
    def clear(self, keep_system: bool = True, keep_archived: bool = False) -> None:
        """
        Clear memory.
        
        Args:
            keep_system: Whether to keep system prompt
            keep_archived: Whether to keep archived messages
        """
        logger.info(f"[{self.session_id[:8]}] Clearing memory: keep_system={keep_system}, keep_archived={keep_archived}")
        
        self.chat.clear_messages(keep_system=keep_system)
        
        if not keep_archived:
            archived_count = len(self._archived_messages)
            self._archived_messages.clear()
            logger.info(f"[{self.session_id[:8]}] Cleared {archived_count} archived messages")
        
        # Reset cache
        self._kv_cache.clear()
        self._cache_valid = False
        self._last_cache_update = 0
        logger.info(f"[{self.session_id[:8]}] Memory cleared successfully")
    
    def get_context_window(self, num_messages: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get a specific window of recent messages.
        
        Args:
            num_messages: Number of recent messages (None for all active)
            
        Returns:
            List of recent messages
        """
        if num_messages is None:
            return self.get_messages()
        
        return self.chat.get_recent_messages(num_messages)
    
    def get_messages_for_llm(
        self,
        include_system: bool = True,
        optimize_for_cache: bool = True
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Get messages optimized for LLM with KV cache reuse.
        
        Args:
            include_system: Whether to include system prompt
            optimize_for_cache: Whether to optimize for KV cache
            
        Returns:
            Tuple of (messages, cache_metadata)
        """
        messages = self.get_messages(include_system=include_system)
        
        cache_metadata = {
            "cacheable_messages": len(self._kv_cache) if self._cache_valid else 0,
            "new_messages": len(messages) - len(self._kv_cache) if self._cache_valid else len(messages),
            "cache_valid": self._cache_valid,
            "total_messages": len(messages)
        }
        
        if optimize_for_cache and self._cache_valid:
            # Mark which messages can be cached
            # This helps LLM providers optimize KV cache reuse
            cache_metadata["cache_breakpoint"] = len(self._kv_cache)
        
        return messages, cache_metadata
    
    def export_session(self, include_archived: bool = True) -> Dict[str, Any]:
        """
        Export complete session data.
        
        Args:
            include_archived: Whether to include archived messages
            
        Returns:
            Complete session data
        """
        data = {
            "session_id": self.session_id,
            "config": {
                "max_tokens": self.config.max_tokens,
                "max_messages": self.config.max_messages,
                "kv_cache_size": self.config.kv_cache_size
            },
            "chat": self.chat.to_dict(),
            "stats": self.get_stats(),
            "exported_at": datetime.now().isoformat()
        }
        
        if include_archived:
            data["archived_messages"] = self._archived_messages
        
        return data
    
    def __repr__(self) -> str:
        """String representation."""
        return (f"Memory(session={self.session_id[:8]}..., "
                f"active={len(self.chat.messages)}, "
                f"archived={len(self._archived_messages)}, "
                f"tokens={self.chat.get_token_count()}/{self.config.max_tokens})")
    
    def __len__(self) -> int:
        """Return active message count."""
        return len(self.chat.messages)


# Convenience functions

def create_memory(
    system_prompt: str,
    max_tokens: int = 4096,
    max_messages: Optional[int] = None,
    kv_cache_size: int = 10,
    storage_backend: Optional['BaseStorageBackend'] = None,
    storage_dir: str = "",
    session_id: Optional[str] = None
) -> Memory:
    """
    Create a memory instance with configuration.
    
    Args:
        system_prompt: System prompt
        max_tokens: Maximum tokens before auto-save
        max_messages: Maximum messages before auto-save
        kv_cache_size: Number of messages in KV cache
        storage_dir: Directory for session storage
        session_id: Optional session ID
        
    Returns:
        Configured Memory instance
    """
    logger.info(f"Creating new memory instance: max_tokens={max_tokens}, kv_cache_size={kv_cache_size}")
    
    config = MemoryConfig(
        max_tokens=max_tokens,
        max_messages=max_messages,
        kv_cache_size=kv_cache_size,
        auto_save=True,
        storage_backend=storage_backend,
        storage_dir=storage_dir
    )
    return Memory(system_prompt=system_prompt, config=config, session_id=session_id)


def load_memory(
    session_id: str, 
    storage_backend: Optional['BaseStorageBackend'] = None,
    storage_dir: str = ""
) -> Memory:
    """
    Load a memory session from disk.
    
    Args:
        session_id: Session ID to load
        storage_dir: Storage directory
        
    Returns:
        Loaded Memory instance
    """
    logger.info(f"Loading memory from disk: session_id={session_id}, storage_dir={storage_dir}")
    
    # Create temporary memory to load the session
    config = MemoryConfig(storage_backend=storage_backend, storage_dir=storage_dir)
    memory = Memory(system_prompt="", config=config)  # Temporary
    memory.load(session_id)
    return memory
