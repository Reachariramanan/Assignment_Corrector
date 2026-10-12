"""
Utilities Module
Helper functions for the agent system.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

from ..config.config import Config


def setup_logging(name: str = "agent_system", level: Optional[str] = None) -> logging.Logger:
    """
    Set up logging for the application.
    
    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger instance
    """
    log_level = level or Config.LOG_LEVEL
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    formatter = logging.Formatter(Config.LOG_FORMAT)
    console_handler.setFormatter(formatter)
    
    # File handler
    log_file = Config.LOGS_DIR / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding=Config.ENCODING)
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger


def load_json(filepath: str) -> Any:
    """
    Load data from a JSON file.
    
    Args:
        filepath: Path to the JSON file
        
    Returns:
        Parsed JSON data
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    with open(filepath, 'r', encoding=Config.ENCODING) as f:
        return json.load(f)


def save_json(data: Any, filepath: str, indent: int = 2) -> None:
    """
    Save data to a JSON file.
    
    Args:
        data: Data to save
        filepath: Path to save the file
        indent: JSON indentation level
    """
    # Create directory if it doesn't exist
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, 'w', encoding=Config.ENCODING) as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def format_timestamp(timestamp: Optional[datetime] = None) -> str:
    """
    Format a timestamp to ISO format string.
    
    Args:
        timestamp: Datetime object (uses current time if None)
        
    Returns:
        ISO formatted timestamp string
    """
    dt = timestamp or datetime.now()
    return dt.isoformat()


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse an ISO format timestamp string.
    
    Args:
        timestamp_str: ISO formatted timestamp string
        
    Returns:
        Datetime object
    """
    return datetime.fromisoformat(timestamp_str)


def validate_dict_keys(data: Dict[str, Any], required_keys: List[str]) -> tuple[bool, Optional[str]]:
    """
    Validate that a dictionary contains required keys.
    
    Args:
        data: Dictionary to validate
        required_keys: List of required key names
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        return False, f"Missing required keys: {', '.join(missing_keys)}"
    return True, None


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple dictionaries, with later dictionaries overriding earlier ones.
    
    Args:
        *dicts: Variable number of dictionaries to merge
        
    Returns:
        Merged dictionary
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result


def safe_get(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Safely get a nested value from a dictionary.
    
    Args:
        data: Dictionary to get value from
        *keys: Nested keys to traverse
        default: Default value if key path doesn't exist
        
    Returns:
        Value at the key path or default
        
    Example:
        safe_get(data, "user", "profile", "name", default="Unknown")
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length.
    
    Args:
        text: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_size(bytes_size: int) -> str:
    """
    Format byte size to human-readable string.
    
    Args:
        bytes_size: Size in bytes
        
    Returns:
        Formatted size string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def get_file_info(filepath: str) -> Dict[str, Any]:
    """
    Get information about a file.
    
    Args:
        filepath: Path to the file
        
    Returns:
        Dictionary with file information
        
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    stats = path.stat()
    return {
        "name": path.name,
        "path": str(path.absolute()),
        "size": format_size(stats.st_size),
        "size_bytes": stats.st_size,
        "created": datetime.fromtimestamp(stats.st_ctime).isoformat(),
        "modified": datetime.fromtimestamp(stats.st_mtime).isoformat(),
        "is_file": path.is_file(),
        "is_dir": path.is_dir()
    }


def list_files(directory: str, pattern: str = "*", recursive: bool = False) -> List[str]:
    """
    List files in a directory matching a pattern.
    
    Args:
        directory: Directory path
        pattern: Glob pattern to match (e.g., "*.json")
        recursive: Whether to search recursively
        
    Returns:
        List of file paths
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return []
    
    if recursive:
        return [str(p) for p in dir_path.rglob(pattern) if p.is_file()]
    else:
        return [str(p) for p in dir_path.glob(pattern) if p.is_file()]


def clean_dict(data: Dict[str, Any], remove_none: bool = True, remove_empty: bool = False) -> Dict[str, Any]:
    """
    Clean a dictionary by removing None or empty values.
    
    Args:
        data: Dictionary to clean
        remove_none: Remove keys with None values
        remove_empty: Remove keys with empty values (empty strings, lists, dicts)
        
    Returns:
        Cleaned dictionary
    """
    cleaned = {}
    for key, value in data.items():
        if remove_none and value is None:
            continue
        if remove_empty and not value and value != 0 and value is not False:
            continue
        cleaned[key] = value
    return cleaned


class Timer:
    """
    Context manager for timing code execution.
    
    Example:
        with Timer("my operation") as timer:
            # code to time
            pass
        print(f"Elapsed: {timer.elapsed}s")
    """
    
    def __init__(self, name: str = "Operation"):
        """Initialize timer with a name."""
        self.name = name
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.elapsed: Optional[float] = None
    
    def __enter__(self) -> 'Timer':
        """Start the timer."""
        import time
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the timer and calculate elapsed time."""
        import time
        self.end_time = time.time()
        self.elapsed = self.end_time - self.start_time
        print(f"{self.name} completed in {self.elapsed:.4f}s")


def pretty_print_json(data: Any, indent: int = 2) -> None:
    """
    Pretty print JSON data.
    
    Args:
        data: Data to print
        indent: Indentation level
    """
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def generate_id(prefix: str = "") -> str:
    """
    Generate a unique ID with optional prefix.
    
    Args:
        prefix: Optional prefix for the ID
        
    Returns:
        Unique ID string
    """
    import uuid
    uid = str(uuid.uuid4())[:8]
    return f"{prefix}{uid}" if prefix else uid
