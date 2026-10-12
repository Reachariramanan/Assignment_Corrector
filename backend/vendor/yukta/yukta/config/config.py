"""
Configuration Module
Centralized configuration for the agent system.
Loads settings from .env file if available.
"""

import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logger.info(f"Loaded configuration from {env_path}")
    else:
        load_dotenv()
except ImportError:
    logger.warning("python-dotenv not installed. Using system environment variables only.")


def _default_yukta_dir() -> Path:
    """Return the base data directory for yukta, respecting YUKTA_DATA_DIR env var."""
    env_val = os.environ.get("YUKTA_DATA_DIR", "").strip()
    return Path(env_val) if env_val else Path.home() / ".yukta"


class Config:
    """
    Global configuration settings for the agent system.
    """

    # User-configurable base directory — override via YUKTA_DATA_DIR env var
    YUKTA_DATA_DIR: Path = _default_yukta_dir()

    # Project paths
    BASE_DIR = Path(__file__).parent.resolve()
    DATA_DIR = BASE_DIR / "data"
    LOGS_DIR = BASE_DIR / "logs"
    EXPORTS_DIR = BASE_DIR / "exports"
    
    # Agent defaults
    DEFAULT_AGENT_NAME = os.getenv("DEFAULT_AGENT_NAME", "Yukta Agent")
    DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))
    DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT", "300"))
    
    # Tool settings
    MAX_TOOLS_PER_AGENT = int(os.getenv("MAX_TOOLS_PER_AGENT", "100"))
    TOOL_CACHE_ENABLED = os.getenv("TOOL_CACHE_ENABLED", "true").lower() == "true"
    
    # Memory settings
    MEMORY_MAX_TOKENS = int(os.getenv("MEMORY_MAX_TOKENS", "4096"))
    MEMORY_KV_CACHE_SIZE = int(os.getenv("MEMORY_KV_CACHE_SIZE", "10"))
    MEMORY_AUTO_SAVE = os.getenv("MEMORY_AUTO_SAVE", "true").lower() == "true"
    MEMORY_STORAGE_DIR = os.getenv(
        "MEMORY_STORAGE_DIR",
        str(_default_yukta_dir() / "memory_sessions")
    )

    # Chat settings
    CHAT_STORAGE_DIR = os.getenv(
        "CHAT_STORAGE_DIR",
        str(_default_yukta_dir() / "agent_chats")
    )
    CHAT_HISTORY_DIR = os.getenv(
        "CHAT_HISTORY_DIR",
        str(_default_yukta_dir() / "chats")
    )
    CHAT_AUTO_SAVE = os.getenv("CHAT_AUTO_SAVE", "false").lower() == "true"
    
    # Logging settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    AGENT_LOG_LEVEL = os.getenv("AGENT_LOG_LEVEL", "INFO")
    MEMORY_LOG_LEVEL = os.getenv("MEMORY_LOG_LEVEL", "INFO")
    ENABLE_LOGGING = os.getenv("ENABLE_LOGGING", "true").lower() == "true"
    ENABLE_MEMORY_LOGGING = os.getenv("ENABLE_MEMORY_LOGGING", "true").lower() == "true"
    LOG_FILE = os.getenv("LOG_FILE", None)
    MEMORY_LOG_FILE = os.getenv("MEMORY_LOG_FILE", None)
    
    # LLM Model settings
    # Ollama
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama2")
    
    # vLLM
    VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://192.168.200.23:11642")
    VLLM_DEFAULT_MODEL = os.getenv("VLLM_MODEL", "qwen36-35b")
    
    # Remote Endpoint (OpenAI, Azure, etc.)
    REMOTE_BASE_URL = os.getenv("REMOTE_BASE_URL", "https://api.openai.com")
    REMOTE_API_KEY = os.getenv("REMOTE_API_KEY", "")
    REMOTE_DEFAULT_MODEL = os.getenv("REMOTE_MODEL", "gpt-4")
    
    # Model generation settings
    MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.7"))
    MODEL_MAX_TOKENS = int(os.getenv("MODEL_MAX_TOKENS", "2048"))
    MODEL_TIMEOUT = int(os.getenv("MODEL_TIMEOUT", "300"))
    
    # Logging format
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # File settings
    EXPORT_FORMAT = os.getenv("EXPORT_FORMAT", "json")
    ENCODING = os.getenv("ENCODING", "utf-8")
    
    # Directory creation settings
    AUTO_CREATE_DIRS = os.getenv("AUTO_CREATE_DIRS", "false").lower() == "true"
    
    # API settings (if needed)
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    
    @classmethod
    def create_directories(cls, force: bool = False) -> None:
        """
        Create necessary directories if they don't exist.
        
        Args:
            force: Force creation even if AUTO_CREATE_DIRS is False
        """
        if force or cls.AUTO_CREATE_DIRS:
            cls.DATA_DIR.mkdir(exist_ok=True)
            cls.LOGS_DIR.mkdir(exist_ok=True)
            cls.EXPORTS_DIR.mkdir(exist_ok=True)
            logger.info(f"Created directories: {cls.DATA_DIR}, {cls.LOGS_DIR}, {cls.EXPORTS_DIR}")
    
    @classmethod
    def ensure_directory(cls, directory: Path) -> None:
        """
        Ensure a specific directory exists (lazy creation).
        Only creates if AUTO_CREATE_DIRS is True or on-demand.
        
        Args:
            directory: Path to directory to ensure exists
        """
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """
        Get configuration as a dictionary.
        
        Returns:
            Dictionary of configuration settings
        """
        return {
            "base_dir": str(cls.BASE_DIR),
            "data_dir": str(cls.DATA_DIR),
            "logs_dir": str(cls.LOGS_DIR),
            "exports_dir": str(cls.EXPORTS_DIR),
            "default_agent_name": cls.DEFAULT_AGENT_NAME,
            "default_temperature": cls.DEFAULT_TEMPERATURE,
            "log_level": cls.LOG_LEVEL,
            "memory_max_tokens": cls.MEMORY_MAX_TOKENS,
            "memory_auto_save": cls.MEMORY_AUTO_SAVE,
            "chat_auto_save": cls.CHAT_AUTO_SAVE,
            "enable_logging": cls.ENABLE_LOGGING,
        }
    
    @classmethod
    def get_logging_level(cls, level_name: Optional[str] = None) -> int:
        """
        Convert string log level to logging constant.
        
        Args:
            level_name: Log level name (DEBUG, INFO, WARNING, ERROR)
        
        Returns:
            Logging level constant
        """
        import logging
        level_name = level_name or cls.LOG_LEVEL
        return getattr(logging, level_name.upper(), logging.INFO)
    
    @classmethod
    def reload_env(cls) -> None:
        """
        Reload environment variables from .env file.
        Useful for runtime configuration updates.
        """
        try:
            from dotenv import load_dotenv
            env_path = Path(__file__).parent / ".env"
            load_dotenv(dotenv_path=env_path, override=True)
            logger.info(f"Reloaded configuration from {env_path}")
        except ImportError:
            logger.warning("python-dotenv not installed. Cannot reload .env file.")


# Only create directories if AUTO_CREATE_DIRS is enabled
if Config.AUTO_CREATE_DIRS:
    Config.create_directories()
