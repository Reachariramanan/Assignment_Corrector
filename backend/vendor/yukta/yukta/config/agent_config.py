from typing import Optional, Dict, Any
import logging
from ..core.storage import BaseStorageBackend, JSONFileStorage
from .config import Config

logger = logging.getLogger(__name__)

class AgentConfig:
    """
    Configuration class for agent settings.
    
    Attributes:
        temperature: LLM temperature setting
        verbose: Whether to print verbose output
        timeout: Timeout in seconds for agent operations
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        enable_logging: Whether to enable logging
        auto_save_chat: Whether to automatically save chat after each interaction
        chat_save_dir: Directory to save chat sessions
        auto_save_chat_history: Whether to automatically save chat history with agent-name folder structure
        chat_history_dir: Directory to save chat history (default: ./chats)
        log_file: Path to log file (None for console only)
        memory_log_level: Logging level for memory module (DEBUG, INFO, WARNING, ERROR)
        enable_memory_logging: Whether to enable memory logging
        memory_log_file: Optional separate log file for memory operations
        max_iter: Maximum number of iterations for agent loop (prevents endless loops, 0 = unlimited, default 10)
        additional_settings: Dictionary for any additional settings
    """
    
    def __init__(
        self,
        temperature: float = 0.7,
        verbose: bool = False,
        timeout: int = 300,
        log_level: int = logging.INFO,
        enable_logging: bool = True,
        auto_save_chat: bool = False,
        chat_save_dir: str = "",
        auto_save_chat_history: bool = True,
        chat_history_dir: str = "",
        log_file: Optional[str] = None,
        memory_log_level: int = logging.INFO,
        enable_memory_logging: bool = True,
        memory_log_file: Optional[str] = None,
        storage_backend: Optional[BaseStorageBackend] = None,
        enable_parallel_tools: bool = False,
        parallel_tool_workers: int = 3,
        enable_serialize_audit: bool = False,
        max_iter: int = 10,
        require_sandbox: bool = True,
        max_history: int = 1000,
        **additional_settings
    ):
        # Validate ranges
        if not (0.0 <= temperature <= 2.0):
            raise ValueError(f"temperature must be between 0.0 and 2.0, got {temperature}")
        if max_iter < 0:
            raise ValueError(f"max_iter must be >= 0 (0 = unlimited), got {max_iter}")
        if max_history < 1:
            raise ValueError(f"max_history must be >= 1, got {max_history}")

        self.temperature = temperature
        self.verbose = verbose
        self.timeout = timeout
        self.log_level = log_level
        self.enable_logging = enable_logging
        self.auto_save_chat = auto_save_chat
        self.chat_save_dir = chat_save_dir
        self.auto_save_chat_history = auto_save_chat_history
        self.chat_history_dir = chat_history_dir or Config.CHAT_HISTORY_DIR
        self.log_file = log_file
        self.memory_log_level = memory_log_level
        self.enable_memory_logging = enable_memory_logging
        self.memory_log_file = memory_log_file
        self.max_iter = max_iter
        self.require_sandbox = require_sandbox
        self.max_history = max_history
        self.additional_settings = additional_settings
        
        # Initialize storage backend with proper default directory
        storage_path = self.chat_save_dir if self.chat_save_dir else Config.CHAT_STORAGE_DIR
        self.storage_backend = storage_backend or JSONFileStorage(storage_path)
        
        # Configure logging lazily (on first use) to avoid import side-effects
        self._logging_configured = False
        
        # Parallel tool execution settings
        self.enable_parallel_tools = enable_parallel_tools
        self.parallel_tool_workers = parallel_tool_workers
        self.enable_serialize_audit = enable_serialize_audit
    
    def _configure_logging(self) -> None:
        """Configure logging based on settings. Called lazily."""
        if self._logging_configured:
            return
        
        self._logging_configured = True
        
        if self.enable_logging:
            try:
                from ..core.Agent.agent import set_agent_logging_level
                set_agent_logging_level(self.log_level)
                
                if self.log_file:
                    file_handler = logging.FileHandler(self.log_file)
                    file_handler.setFormatter(logging.Formatter(
                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S'
                    ))
                    logger.addHandler(file_handler)
                    logger.info(f"Logging to file: {self.log_file}")
            except ImportError as e:
                logger.warning(f"Could not configure agent logging: {e}")
        
        if self.enable_memory_logging:
            try:
                from ..core.memory import set_memory_logging_level
                set_memory_logging_level(self.memory_log_level)
                
                if self.memory_log_file:
                    memory_logger = logging.getLogger('memory')
                    memory_file_handler = logging.FileHandler(self.memory_log_file)
                    memory_file_handler.setFormatter(logging.Formatter(
                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S'
                    ))
                    memory_logger.addHandler(memory_file_handler)
                    logger.info(f"Memory logging to file: {self.memory_log_file}")
            except ImportError as e:
                logger.warning(f"Could not configure memory logging: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "temperature": self.temperature,
            "verbose": self.verbose,
            "timeout": self.timeout,
            "log_level": logging.getLevelName(self.log_level),
            "enable_logging": self.enable_logging,
            "auto_save_chat": self.auto_save_chat,
            "chat_save_dir": self.chat_save_dir,
            "auto_save_chat_history": self.auto_save_chat_history,
            "chat_history_dir": self.chat_history_dir,
            "log_file": self.log_file,
            "enable_parallel_tools": self.enable_parallel_tools,
            "parallel_tool_workers": self.parallel_tool_workers,
            "enable_serialize_audit": self.enable_serialize_audit,
            **self.additional_settings
        }

