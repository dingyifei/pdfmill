"""Logging configuration for pdfmill."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Package-level logger name
LOGGER_NAME = "pdfmill"


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger for a pdfmill module.

    Args:
        name: Module name (e.g., __name__). If None, returns root pdfmill logger.

    Returns:
        Logger instance
    """
    if name is None:
        return logging.getLogger(LOGGER_NAME)
    # Handle both 'pdfmill.processor' and 'processor' styles
    if name.startswith("pdfmill."):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


class ConsoleFormatter(logging.Formatter):
    """Custom formatter for user-friendly console output."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record based on level.

        INFO: Just the message (mimics current print behavior)
        WARNING: Prefix with "Warning:"
        ERROR: Prefix with "Error:"
        DEBUG: Include [debug] prefix
        """
        if record.levelno == logging.INFO:
            return record.getMessage()
        elif record.levelno == logging.WARNING:
            return f"Warning: {record.getMessage()}"
        elif record.levelno == logging.ERROR:
            return f"Error: {record.getMessage()}"
        elif record.levelno == logging.DEBUG:
            return f"[debug] {record.getMessage()}"
        return super().format(record)


class InfoFilter(logging.Filter):
    """Filter that only allows records below WARNING level."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.WARNING


def setup_logging(
    verbosity: int = 0,
    quiet: bool = False,
    log_file: Path | None = None,
) -> None:
    """Configure logging for pdfmill CLI.

    Args:
        verbosity: 0=normal, 1=verbose (-v), 2=debug (-vv)
        quiet: If True, suppress all output except errors
        log_file: Optional file path for logging
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()

    # Determine console level
    if quiet:
        console_level = logging.ERROR
    elif verbosity >= 2:
        console_level = logging.DEBUG
    elif verbosity >= 1:
        console_level = logging.INFO
    else:
        console_level = logging.INFO

    # Capture everything at logger level, filter at handlers
    logger.setLevel(logging.DEBUG)

    # Stdout handler for INFO and DEBUG (below WARNING)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(console_level)
    stdout_handler.setFormatter(ConsoleFormatter())
    stdout_handler.addFilter(InfoFilter())
    logger.addHandler(stdout_handler)

    # Stderr handler for WARNING and above
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(ConsoleFormatter())
    logger.addHandler(stderr_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)


def is_quiet_mode() -> bool:
    """Check if logging is in quiet mode (only ERROR level visible on console).

    Used for progress display to skip printing when --quiet is set.
    """
    logger = logging.getLogger(LOGGER_NAME)
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            return handler.level >= logging.ERROR
    return False
