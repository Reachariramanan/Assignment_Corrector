"""
Chat Module
Manages conversation history with system prompt and local persistence.
"""

from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from pathlib import Path
import json
import logging

from ..storage import BaseStorageBackend, JSONFileStorage
from .message import Message, Role, system_message, user_message, agent_message, tool_message

# Configure logging
logger = logging.getLogger(__name__)


class Chat:
    """
    Manages a conversation with system prompt and message history.
    
    The Chat class stores:
    - System prompt (stored once, not repeated)
    - Message history (user, agent, tool messages)
    - Conversation metadata
    - Ability to save/load from disk
    
    Features:
    - Single system prompt storage
    - Message management
    - Token tracking
    - Local persistence (JSON format)
    - Statistics and analytics
    """
    
    def __init__(
        self,
        system_prompt: Optional[str] = None,
        chat_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context_window: int = 8192,
        context_buffer: int = 512
    ):
        """
        Initialize a chat session.
        
        Args:
            system_prompt: System prompt for the conversation
            chat_id: Unique chat identifier (auto-generated if not provided)
            metadata: Additional metadata (tags, user_id, etc.)
            context_window: Model's context window size in tokens (default: 8192)
            context_buffer: Safety buffer to keep free (default: 512 for output tokens)
        """
        self.chat_id = chat_id or self._generate_chat_id()
        self.created_at = datetime.now()
        self.updated_at = self.created_at
        self.metadata = metadata or {}
        
        # Context window management
        self.context_window = context_window
        self.context_buffer = context_buffer  # Tokens reserved for output
        self.max_input_tokens = context_window - context_buffer
        
        # System prompt (stored once)
        self._system_prompt: Optional[Message] = None
        if system_prompt:
            self.set_system_prompt(system_prompt)
        
        # Message history (excludes system prompt)
        self.messages: List[Message] = []
        
        # Token count cache for O(1) lookups
        self._total_token_count: int = 0
        
        # Tool call ID set for O(1) validation (Issue #2 fix)
        self._tool_call_id_set: Set[str] = set()
        
        # Statistics
        self.stats = {
            "total_messages": 0,
            "user_messages": 0,
            "agent_messages": 0,
            "tool_calls": 0,
            "total_tokens": 0,
            "messages_trimmed": 0  # Track sliding window trims
        }
        
        logger.debug(f"Chat initialized with context window: {self.context_window}, buffer: {self.context_buffer}")
    
    def _generate_chat_id(self) -> str:
        """Generate a collision-free chat ID (UUID4 suffix)."""
        import uuid
        return f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    def set_system_prompt(self, prompt: str) -> None:
        """
        Set or update the system prompt.
        
        System prompt is stored separately and included once at the
        beginning of conversation context.
        
        Args:
            prompt: System prompt text
        """
        self._system_prompt = system_message(prompt)
        self.updated_at = datetime.now()
    
    def get_system_prompt(self) -> Optional[str]:
        """
        Get the system prompt text.
        
        Returns:
            System prompt text or None if not set
        """
        return self._system_prompt.content if self._system_prompt else None
    
    def add_message(self, message: Message) -> None:
        """
        Add a message to the chat.
        
        Args:
            message: Message to add
        """
        # Don't add system messages (use set_system_prompt instead)
        if message.is_system():
            raise ValueError("Use set_system_prompt() to set system messages")
        
        self.messages.append(message)
        self.updated_at = datetime.now()
        
        # Update token count cache
        self._total_token_count += message.token_count
        
        # Update statistics
        self.stats["total_messages"] += 1
        self.stats["total_tokens"] += message.token_count
        
        if message.is_user():
            self.stats["user_messages"] += 1
        elif message.is_agent():
            self.stats["agent_messages"] += 1
            if message.has_tool_calls():
                self.stats["tool_calls"] += len(message.tool_calls)
                # Add tool call IDs to set for O(1) validation (Issue #2 fix)
                for tool_call in message.tool_calls:
                    if isinstance(tool_call, dict) and tool_call.get("id"):
                        self._tool_call_id_set.add(tool_call["id"])
    
    def add_user_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
        """
        Add a user message.
        
        Args:
            content: User message content
            metadata: Optional metadata
            
        Returns:
            Created Message
        """
        msg = user_message(content, metadata)
        self.add_message(msg)
        return msg
    
    def add_agent_message(
        self,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Add an agent message.
        
        Args:
            content: Agent message content
            tool_calls: Optional tool calls
            metadata: Optional metadata
            
        Returns:
            Created Message
        """
        msg = agent_message(content, tool_calls, metadata)
        self.add_message(msg)
        return msg
    
    def add_tool_message(
        self,
        content: str,
        tool_call_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Add a tool response message.
        
        Args:
            content: Tool response content
            tool_call_id: ID of tool call this responds to
            metadata: Optional metadata
            
        Returns:
            Created Message
        """
        # Validate tool_call_id reference before adding
        if tool_call_id:
            if not self.validate_tool_call_id(tool_call_id):
                logger.warning(
                    f"[CHAT] Tool response with unmatched ID '{tool_call_id}'. "
                    f"No corresponding tool call found in conversation. "
                    f"This may indicate a context window trim or orphaned response."
                )
                if metadata is None:
                    metadata = {}
                metadata["orphaned_tool_call"] = True
        
        msg = tool_message(content, tool_call_id, metadata)
        self.add_message(msg)
        return msg
    
    def validate_tool_call_id(self, tool_call_id: str) -> bool:
        """
        Validate that a tool_call_id corresponds to an actual tool call in the conversation.
        
        Complexity: O(1) set membership test (was O(n·m) nested scan before Issue #2 fix).
        
        Args:
            tool_call_id: ID to validate
            
        Returns:
            True if a matching tool call exists, False otherwise
        """
        if not tool_call_id:
            return False
        
        # O(1) set lookup (Issue #2 fix: was O(n·m) nested loop)
        return tool_call_id in self._tool_call_id_set
    
    def scan_orphaned_tool_references(self) -> List[Dict[str, Any]]:
        """
        Scan for orphaned tool references (tool results without corresponding tool calls).
        
        This can happen due to context window trimming removing tool call requests
        while keeping tool responses.
        
        Returns:
            List of orphaned tool messages with details
        """
        orphaned = []
        
        for msg in self.messages:
            if msg.is_tool():
                tool_call_id = msg.tool_call_id
                if not self.validate_tool_call_id(tool_call_id):
                    orphaned.append({
                        "message_id": msg.message_id,
                        "tool_call_id": tool_call_id,
                        "timestamp": msg.timestamp.isoformat(),
                        "preview": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                    })
        
        if orphaned:
            logger.warning(f"[CHAT] Found {len(orphaned)} orphaned tool messages (likely due to context trimming)")
        
        return orphaned
    
    def get_messages(self, include_system: bool = True) -> List[Dict[str, Any]]:
        """
        Get messages in LLM API format.
        
        Automatically trims old messages if context window would be exceeded.
        Uses sliding window to keep most recent messages.
        
        Args:
            include_system: Whether to include system prompt
            
        Returns:
            List of message dictionaries ready for LLM
        """
        # Apply sliding window trim if needed before returning messages
        self.trim_messages_to_context()
        
        messages = []
        
        # Add system prompt first if requested and exists
        if include_system and self._system_prompt:
            messages.append(self._system_prompt.to_dict())
        
        # Add all other messages
        for msg in self.messages:
            messages.append(msg.to_dict())
        
        return messages
    def trim_messages_to_context(self, min_required: int = 0) -> None:
        """
        Implement sliding window to trim old messages when context exceeds limit.
        
        Args:
            min_required: Minimum tokens that must remain available after trimming
                       (default: 0). Use this to guarantee space for new content.
        
        Keeps:
        - System prompt (always)
        - Most recent messages within context_window - context_buffer
        
        Removes oldest messages first (user/agent pairs).
        This is called automatically from get_messages() to maintain context limits.
        
        Complexity: O(n) single pass with one slice operation (previously O(n²)).
        """
        # Calculate total tokens
        total_tokens = self.get_token_count()
        
        # Target limit: max available minus minimum required space
        target_limit = self.max_input_tokens - min_required
        
        # If under limit, nothing to trim
        if total_tokens <= target_limit:
            return
        
        logger.info(
            f"Context exceeded: {total_tokens} > {target_limit} "
            f"(window: {self.context_window}, buffer: {self.context_buffer}, min_required: {min_required}). "
            f"Trimming old messages..."
        )
        
        # Find cut index via forward scan (O(n) single pass)
        sys_tokens = self._system_prompt.token_count if self._system_prompt else 0
        cut = 0
        running_token_count = self._total_token_count
        
        while cut < len(self.messages) and (running_token_count + sys_tokens) > target_limit:
            msg = self.messages[cut]
            logger.debug(
                f"Will remove: {msg.role} - "
                f"{msg.content[:50]}... "
                f"(tokens={msg.token_count})"
            )
            # Remove tool call IDs from set if this is an agent message (Issue #2 fix)
            if msg.is_agent() and msg.has_tool_calls():
                for tool_call in msg.tool_calls:
                    if isinstance(tool_call, dict) and tool_call.get("id"):
                        self._tool_call_id_set.discard(tool_call["id"])
            running_token_count -= msg.token_count
            cut += 1
        
        # Apply trim with slice (O(n) single operation)
        if cut > 0:
            self.messages = self.messages[cut:]  # Slice replaces list with tail
            self._total_token_count = running_token_count
            self.stats["messages_trimmed"] += cut
            
            final_tokens = self.get_token_count()
            logger.info(
                f"Trimmed {cut} messages. "
                f"Final tokens: {final_tokens} "
                f"(target: {target_limit}, margin: {target_limit - final_tokens})"
            )
    def get_recent_messages(self, n: int, include_system: bool = True) -> List[Dict[str, Any]]:
        """
        Get the N most recent messages.
        
        Args:
            n: Number of recent messages to get
            include_system: Whether to include system prompt
            
        Returns:
            List of recent message dictionaries
        """
        messages = []
        
        if include_system and self._system_prompt:
            messages.append(self._system_prompt.to_dict())
        
        # Get last N messages
        recent = self.messages[-n:] if n < len(self.messages) else self.messages
        for msg in recent:
            messages.append(msg.to_dict())
        
        return messages
    
    def get_token_count(self) -> int:
        """
        Get total token count of conversation.
        
        Returns:
            Total tokens (including system prompt)
        """
        # O(1) lookup: use cached token count
        sys_tokens = self._system_prompt.token_count if self._system_prompt else 0
        return self._total_token_count + sys_tokens
    
    def get_message_count(self) -> int:
        """
        Get total number of messages (excluding system prompt).
        
        Returns:
            Message count
        """
        return len(self.messages)
    
    def clear_messages(self, keep_system: bool = True) -> None:
        """
        Clear all messages.
        
        Args:
            keep_system: Whether to keep system prompt
        """
        self.messages.clear()
        if not keep_system:
            self._system_prompt = None
        
        # Reset token count cache
        self._total_token_count = 0
        
        # Reset tool call ID set
        self._tool_call_id_set.clear()
        
        # Reset stats
        self.stats = {
            "total_messages": 0,
            "user_messages": 0,
            "agent_messages": 0,
            "tool_calls": 0,
            "total_tokens": 0
        }
        
        self.updated_at = datetime.now()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get conversation statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            **self.stats,
            "chat_id": self.chat_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "total_tokens": self.get_token_count(),
            "has_system_prompt": self._system_prompt is not None
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert chat to dictionary for persistence.
        
        Returns:
            Complete dictionary representation
        """
        return {
            "chat_id": self.chat_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "context_window": self.context_window,
            "context_buffer": self.context_buffer,
            "system_prompt": self._system_prompt.to_full_dict() if self._system_prompt else None,
            "messages": [msg.to_full_dict() for msg in self.messages],
            "stats": self.stats
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Chat':
        """
        Create a Chat from dictionary.
        
        Args:
            data: Dictionary containing chat data
            
        Returns:
            Chat instance
        """
        chat = cls(
            chat_id=data["chat_id"],
            metadata=data.get("metadata", {}),
            context_window=data.get("context_window", 8192),
            context_buffer=data.get("context_buffer", 512),
        )
        
        # Restore timestamps
        try:
            chat.created_at = datetime.fromisoformat(data["created_at"])
            chat.updated_at = datetime.fromisoformat(data["updated_at"])
        except (ValueError, TypeError, KeyError):
            pass
        
        # Restore system prompt
        if data.get("system_prompt"):
            chat._system_prompt = Message.from_dict(data["system_prompt"])
        
        # Restore messages
        for msg_data in data.get("messages", []):
            msg = Message.from_dict(msg_data)
            chat.messages.append(msg)
        
        # Rebuild token count cache from restored messages
        chat._total_token_count = sum(msg.token_count for msg in chat.messages)
        
        # Rebuild tool call ID set from restored messages (Issue #2 fix)
        chat._tool_call_id_set = set()
        for msg in chat.messages:
            if msg.is_agent() and msg.has_tool_calls():
                for tool_call in msg.tool_calls:
                    if isinstance(tool_call, dict) and tool_call.get("id"):
                        chat._tool_call_id_set.add(tool_call["id"])
        
        # Restore stats
        chat.stats = data.get("stats", chat.stats)
        
        return chat
    
    def save(self, filepath: str) -> None:
        """
        Save chat to a local JSON file.
        
        Args:
            filepath: Path to save file
        """
        path = Path(filepath)
        
        # Create directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save as JSON
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: str) -> 'Chat':
        """
        Load chat from a local JSON file.
        
        Args:
            filepath: Path to load file
            
        Returns:
            Chat instance
        """
        path = Path(filepath)
        
        if not path.exists():
            raise FileNotFoundError(f"Chat file not found: {filepath}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    def generate_filename_from_first_message(self, max_length: int = 50) -> str:
        """
        Generate a filename from the first user message.
        
        Args:
            max_length: Maximum length of the filename (excluding extension)
            
        Returns:
            Generated filename with .json extension
        """
        if not self.messages:
            # No messages yet, use timestamp
            return f"chat_{self.created_at.strftime('%Y%m%d_%H%M%S_%f')}.json"
        
        # Get first user message
        first_message = None
        for msg in self.messages:
            if msg.is_user():
                # Ensure content is a string (not dict or other type)
                content = msg.content
                if isinstance(content, dict):
                    # If content is a dict, extract text representation
                    content = str(content)
                if isinstance(content, str) and content.strip():
                    first_message = content
                    break
        
        if not first_message:
            # No user message found, use timestamp
            return f"chat_{self.created_at.strftime('%Y%m%d_%H%M%S_%f')}.json"
        
        # Clean and truncate message
        import re
        # Remove special characters and convert to lowercase
        cleaned = re.sub(r'[^\w\s]', '', first_message).lower()
        # Replace whitespace with underscores
        cleaned = re.sub(r'\s+', '_', cleaned).strip('_')
        # Limit length
        cleaned = cleaned[:max_length]
        
        # Add timestamp for uniqueness
        timestamp = self.created_at.strftime('%Y%m%d_%H%M%S')
        
        return f"{cleaned}_{timestamp}.json"
    
    def export_text(self, include_system: bool = True) -> str:
        """
        Export conversation as readable text.
        
        Args:
            include_system: Whether to include system prompt
            
        Returns:
            Formatted text representation
        """
        lines = []
        lines.append(f"=== Chat {self.chat_id} ===")
        lines.append(f"Created: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Updated: {self.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        if include_system and self._system_prompt:
            lines.append("[SYSTEM]")
            lines.append(self._system_prompt.content)
            lines.append("")
        
        for msg in self.messages:
            lines.append(f"[{msg.role.upper()}]")
            lines.append(msg.content)
            
            if msg.has_tool_calls():
                lines.append(f"  (Tool calls: {len(msg.tool_calls)})")
            
            lines.append("")
        
        lines.append(f"=== Stats: {self.get_message_count()} messages, {self.get_token_count()} tokens ===")
        
        return "\n".join(lines)
    
    def __repr__(self) -> str:
        """String representation."""
        return f"Chat(id={self.chat_id}, messages={len(self.messages)}, tokens={self.get_token_count()})"
    
    def __str__(self) -> str:
        """User-friendly string."""
        return self.export_text()
    
    def __len__(self) -> int:
        """Return message count."""
        return len(self.messages)


class ChatManager:
    """
    Manages multiple chat sessions with persistence.
    """
    
    def __init__(self, storage_backend: Optional[BaseStorageBackend] = None):
        """
        Initialize chat manager.
        
        Args:
            storage_dir: Directory to store chat files
        """
        self.storage = storage_backend or JSONFileStorage()
        self.chats: Dict[str, Chat] = {}
    
    def create_chat(
        self,
        system_prompt: Optional[str] = None,
        chat_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Chat:
        """
        Create a new chat session.
        
        Args:
            system_prompt: System prompt
            chat_id: Optional chat ID
            metadata: Optional metadata
            
        Returns:
            New Chat instance
        """
        chat = Chat(system_prompt, chat_id, metadata)
        self.chats[chat.chat_id] = chat
        return chat
    
    def get_chat(self, chat_id: str) -> Optional[Chat]:
        """
        Get a chat by ID.
        
        Args:
            chat_id: Chat identifier
            
        Returns:
            Chat instance or None
        """
        return self.chats.get(chat_id)
    
    def save_chat(self, chat_id: str) -> str:
        """Save a chat using the storage backend."""
        chat = self.chats.get(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")
        
       
        return self.storage.save(chat_id, chat.to_dict())
    
    def save_chat_with_generated_filename(self, chat_id: str, chat_folder: str = "./chats", agent_name: str = None) -> str:
        """
        Save a chat with auto-generated filename based on first message.
        Creates agent-specific subfolders within the chat folder.
        
        Args:
            chat_id: Chat identifier
            chat_folder: Base directory for chats (default: ./chats)
            agent_name: Agent name to create subfolder (if None, uses root of chat_folder)
            
        Returns:
            Path to saved chat file
        """
        chat = self.chats.get(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")
        
        # Create base chat folder if it doesn't exist
        from pathlib import Path
        folder_path = Path(chat_folder)
        
        # If agent_name provided, create agent-specific subfolder
        if agent_name:
            folder_path = folder_path / agent_name
        
        folder_path.mkdir(parents=True, exist_ok=True)
        
        # Generate filename from first message
        filename = chat.generate_filename_from_first_message()
        filepath = folder_path / filename
        
        # Save the chat
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(chat.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Chat saved with auto-generated filename: {filepath}")
        return str(filepath)
    
    def load_chat(self, chat_id: str) -> Chat:
        """
        Load a chat from disk.
        
        Args:
            chat_id: Chat identifier
            
        Returns:
            Loaded Chat instance
        """
        data = self.storage.load(chat_id)
        if data is None:
            raise FileNotFoundError(f"Chat session not found: {chat_id}")
            
        chat = Chat.from_dict(data)
        self.chats[chat.chat_id] = chat
        return chat
    
    def list_chats(self) -> List[str]:
        """
        List all saved chat IDs.
        
        Returns:
            List of chat IDs
        """
        return self.storage.list_sessions()
    
    def delete_chat(self, chat_id: str) -> None:
        """
        Delete a chat from memory and disk.
        
        Args:
            chat_id: Chat identifier
        """
        if chat_id in self.chats:
            del self.chats[chat_id]
        self.storage.delete(chat_id)
    
    def __repr__(self) -> str:
        """String representation."""
        return f"ChatManager(chats={len(self.chats)}, storage={self.storage.__class__.__name__})"
