"""
modern_logger.py — Modern Aesthetic Logging System

Visual style: Muted, warm antique palette for high readability
Theme: Terminal (colored, structured) + File (machine-readable)

Usage:
    from yukta.api.modern_logger import setup_logging, info, warning, error

    setup_logging(level=logging.INFO)
    info("Operation completed")
    error("Something failed")

Color Palette (Muted, Warm, Antique-Inspired):
    - DEBUG:    Warm gray
    - INFO:     Muted teal
    - WARNING:  Antique gold
    - ERROR:    Dusty red
    - CRITICAL: Deep red (slightly bold)
"""

import logging
import sys
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path


# ANSI Color Codes (Modern/Muted Aesthetic Theme)
class ModernColors:
    """Modern aesthetic ANSI color codes - muted, warm palette."""

    DEBUG = "\033[38;5;244m"
    INFO = "\033[38;5;72m"
    WARNING = "\033[38;5;178m"
    ERROR = "\033[38;5;124m"
    CRITICAL = "\033[38;5;160m"

    TIMESTAMP = "\033[38;5;240m"
    FILE_LINE = "\033[38;5;81m"
    FUNCTION = "\033[38;5;147m"
    CONTEXT = "\033[38;5;180m"
    MESSAGE = "\033[38;5;250m"
    SEPARATOR = "\033[38;5;235m"
    WARM_SILVER = "\033[38;5;188m"

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    TOP_LEFT = "┌"
    TOP_RIGHT = "┐"
    BOTTOM_LEFT = "└"
    BOTTOM_RIGHT = "┘"
    HORIZONTAL = "─"
    VERTICAL = "│"


class ModernFormatter(logging.Formatter):
    """Modern aesthetic log formatter."""

    def __init__(self, use_color: bool = True, show_context: bool = False):
        super().__init__()
        self.use_color = use_color
        self.show_context = show_context

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with ANSI colour codes and a compact timestamp."""
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")

        level_colors = {
            logging.DEBUG: ModernColors.DEBUG,
            logging.INFO: ModernColors.INFO,
            logging.WARNING: ModernColors.WARNING,
            logging.ERROR: ModernColors.ERROR,
            logging.CRITICAL: ModernColors.CRITICAL,
        }

        level_names = {
            logging.DEBUG: "DEBUG",
            logging.INFO: "INFO",
            logging.WARNING: "WARN",
            logging.ERROR: "ERROR",
            logging.CRITICAL: "CRIT",
        }

        level = record.levelname
        level_name = level_names.get(record.levelno, level)
        color = level_colors.get(record.levelno, "")

        parts = []

        if self.use_color:
            parts.append(f"{ModernColors.TIMESTAMP}{timestamp}{ModernColors.RESET}")
            parts.append(f"{color}{level_name.ljust(5)}{ModernColors.RESET}")
        else:
            parts.append(f"[{timestamp}]")
            parts.append(f"[{level_name.ljust(5)}]")

        if self.show_context and hasattr(record, 'pathname'):
            try:
                rel_path = Path(record.pathname).relative_to(Path.cwd())
                file_info = f"{rel_path}:{record.lineno}"
                if self.use_color:
                    parts.append(f"{ModernColors.FILE_LINE}{file_info}{ModernColors.RESET}")
                else:
                    parts.append(f"[{file_info}]")
            except ValueError:
                pass

        if self.use_color:
            parts.append(f"{ModernColors.MESSAGE}{record.getMessage()}{ModernColors.RESET}")
        else:
            parts.append(record.getMessage())

        return " ".join(parts)


def generate_event_banner(
    level: str,
    message: str,
    source_file: Optional[str] = None,
    source_line: Optional[int] = None,
    function: Optional[str] = None,
) -> str:
    """Generate a styled event banner with border art."""
    if level.upper() in ["ERROR", "CRITICAL"]:
        border_color = ModernColors.ERROR
        label = " ERROR "
    elif level.upper() == "WARNING":
        border_color = ModernColors.WARNING
        label = " WARN "
    elif level.upper() == "INFO":
        border_color = ModernColors.INFO
        label = " INFO "
    else:
        border_color = ModernColors.DEBUG
        label = " DEBUG "

    lines = message.split("\n")
    max_width = max(len(line) for line in lines)
    width = max(max_width + 4, 20)

    banner_lines = []

    banner_lines.append(f"{border_color}{ModernColors.TOP_LEFT}{ModernColors.HORIZONTAL * width}{ModernColors.TOP_RIGHT}{ModernColors.RESET}")

    banner_lines.append(f"{border_color}{ModernColors.VERTICAL}{ModernColors.RESET}{border_color}{label}{ModernColors.RESET}{' ' * (width - len(label))}{border_color}{ModernColors.VERTICAL}{ModernColors.RESET}")

    for line in lines:
        padding = width - len(line)
        banner_lines.append(f"{border_color}{ModernColors.VERTICAL}{ModernColors.RESET} {line}{' ' * padding}{border_color}{ModernColors.VERTICAL}{ModernColors.RESET}")

    banner_lines.append(f"{border_color}{ModernColors.BOTTOM_LEFT}{ModernColors.HORIZONTAL * width}{ModernColors.BOTTOM_RIGHT}{ModernColors.RESET}")

    return "\n".join(banner_lines)


def setup_logging(
    name: Optional[str] = None,
    level: int = logging.INFO,
    use_color: bool = True,
    show_context: bool = False,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Setup modern aesthetic logging."""
    logger = logging.getLogger(name or "yukta")
    logger.setLevel(level)
    logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(ModernFormatter(use_color=use_color, show_context=show_context))
    logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


def debug(message: str, **kwargs):
    """Log debug message."""
    logging.getLogger("yukta").debug(message, **kwargs)


def info(message: str, **kwargs):
    """Log info message."""
    logging.getLogger("yukta").info(message, **kwargs)


def warning(message: str, **kwargs):
    """Log warning message."""
    logging.getLogger("yukta").warning(message, **kwargs)


def error(message: str, **kwargs):
    """Log error message."""
    logging.getLogger("yukta").error(message, **kwargs)


def critical(message: str, **kwargs):
    """Log critical message."""
    logging.getLogger("yukta").critical(message, **kwargs)


def log_event(level: str, message: str, **kwargs):
    """Log an event with specified level."""
    logger = logging.getLogger("yukta")
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message, **kwargs)


__all__ = [
    "ModernColors",
    "ModernFormatter",
    "generate_event_banner",
    "setup_logging",
    "get_logger",
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "log_event",
]