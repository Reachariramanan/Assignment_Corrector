"""
Storage Module
Defines abstract storage backends for persisting chat and memory data.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import json
from pathlib import Path
import logging
import threading
import tempfile
import shutil
import os

logger = logging.getLogger(__name__)


class StorageCorruptionError(IOError):
    """Raised when a storage file exists but cannot be parsed (corrupted data)."""


class BaseStorageBackend(ABC):
    """Abstract base class for all memory/chat storage backends."""
    
    @abstractmethod
    def save(self, session_id: str, data: Dict[str, Any]) -> str:
        """Save session data and return the storage identifier/path."""
        raise NotImplementedError("Subclasses must implement save()")
    
    @abstractmethod
    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session data by ID. Return None if not found."""
        raise NotImplementedError("Subclasses must implement load()")
    
    @abstractmethod
    def delete(self, session_id: str) -> bool:
        """Delete a session. Return True if successful."""
        raise NotImplementedError("Subclasses must implement delete()")
    
    @abstractmethod
    def list_sessions(self) -> List[str]:
        """List all available session IDs."""
        raise NotImplementedError("Subclasses must implement list_sessions()")


class JSONFileStorage(BaseStorageBackend):
    """Saves chat sessions as local JSON files with error handling and concurrency safety."""

    def __init__(self, storage_dir: str = ""):
        if not storage_dir:
            import os
            from pathlib import Path as _Path
            _base = os.environ.get("YUKTA_DATA_DIR", "").strip()
            _default = (_Path(_base) if _base else _Path.home() / ".yukta") / "agent_chats"
            storage_dir = str(_default)
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()  # Thread-safe concurrent save protection
        
    def _validate_serializable(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Pre-flight check: validate that data can be serialized to JSON.
        
        Args:
            data: Data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            json.dumps(data, ensure_ascii=False)
            return True, None
        except TypeError as e:
            error_msg = f"Serialization failed (type error): {str(e)}"
            logger.warning(f"[SERIALIZE] {error_msg}")
            return False, error_msg
        except ValueError as e:
            error_msg = f"Serialization failed (value error): {str(e)}"
            logger.warning(f"[SERIALIZE] {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Serialization failed (unexpected): {str(e)}"
            logger.warning(f"[SERIALIZE] {error_msg}")
            return False, error_msg
    
    def save(self, session_id: str, data: Dict[str, Any]) -> str:
        """
        Save session data with retry logic and atomic writes.
        
        Args:
            session_id: ID of the session
            data: Data to save
            
        Returns:
            Path to saved file
            
        Raises:
            IOError: If save fails after retries
        """
        filepath = self.storage_dir / f"{session_id}.json"
        max_retries = 3
        retry_count = 0
        
        with self._write_lock:
            while retry_count < max_retries:
                try:
                    # Pre-flight validation
                    is_valid, error_msg = self._validate_serializable(data)
                    if not is_valid:
                        logger.error(f"[SAVE] Validation failed for {session_id}: {error_msg}")
                        raise ValueError(error_msg)
                    
                    # Atomic write: save to temp file first, then rename
                    temp_fd, temp_path = tempfile.mkstemp(
                        dir=self.storage_dir,
                        prefix=f".{session_id}_",
                        suffix=".json.tmp"
                    )
                    
                    try:
                        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        
                        # Atomic rename
                        shutil.move(temp_path, str(filepath))
                        logger.debug(f"[SAVE] Successfully saved {session_id} to {filepath}")
                        return str(filepath)
                    
                    except Exception as write_err:
                        # Clean up temp file if write failed
                        try:
                            if os.path.exists(temp_path):
                                os.unlink(temp_path)
                        except OSError as cleanup_err:
                            logger.warning(f"Failed to cleanup temp file: {cleanup_err}")
                        raise write_err
                
                except IOError as io_err:
                    retry_count += 1
                    if "No space left on device" in str(io_err):
                        logger.error(f"[SAVE] Disk full when saving {session_id}: {io_err}")
                        raise
                    elif "Permission denied" in str(io_err):
                        logger.error(f"[SAVE] Permission denied saving {session_id}: {io_err}")
                        raise
                    elif retry_count < max_retries:
                        logger.warning(f"[SAVE] Retry {retry_count}/{max_retries} for {session_id}: {io_err}")
                        continue
                    else:
                        logger.error(f"[SAVE] Failed after {max_retries} retries: {io_err}")
                        raise
                
                except (TypeError, ValueError, json.JSONDecodeError) as ser_err:
                    logger.error(f"[SAVE] Serialization error for {session_id}: {ser_err}")
                    raise IOError(f"Cannot serialize session data: {ser_err}") from ser_err
                
                except Exception as e:
                    logger.error(f"[SAVE] Unexpected error saving {session_id}: {e}")
                    raise IOError(f"Unexpected error during save: {e}") from e
        
        # Should not reach here
        raise IOError(f"Failed to save {session_id} after {max_retries} attempts")
        
    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session data from JSON file."""
        filepath = self.storage_dir / f"{session_id}.json"
        
        if not filepath.exists():
            logger.debug(f"[LOAD] Session file not found: {filepath}")
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"[LOAD] Successfully loaded {session_id}")
                return data
        
        except json.JSONDecodeError as e:
            logger.error(f"[LOAD] Corrupted JSON for {session_id}: {e}")
            raise StorageCorruptionError(
                f"Session file for '{session_id}' exists but contains invalid JSON: {e}"
            ) from e
        except IOError as e:
            logger.error(f"[LOAD] IO error loading {session_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"[LOAD] Unexpected error loading {session_id}: {e}")
            return None
            
    def delete(self, session_id: str) -> bool:
        """Delete a session file."""
        filepath = self.storage_dir / f"{session_id}.json"
        
        try:
            if filepath.exists():
                filepath.unlink()
                logger.debug(f"[DELETE] Deleted {session_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"[DELETE] Error deleting {session_id}: {e}")
            return False
        
    def list_sessions(self) -> List[str]:
        """List all available session files."""
        try:
            return [f.stem for f in self.storage_dir.glob("*.json")]
        except Exception as e:
            logger.error(f"[LIST] Error listing sessions: {e}")
            return []