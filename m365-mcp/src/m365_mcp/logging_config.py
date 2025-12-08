"""
Comprehensive logging configuration for Microsoft MCP Server.

This module provides structured logging with rotation, detailed formatting,
and separate log levels for different components.
"""

import logging
import logging.handlers
import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
import json


class StructuredFormatter(logging.Formatter):
    """JSON structured formatter for machine-readable logs."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        for key in ["account_id", "tool_name", "operation_id", "duration_ms"]:
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class HumanReadableFormatter(logging.Formatter):
    """Human-readable formatter with colors for console output."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",
    }

    def format(self, record: logging.LogRecord) -> str:
        # Add color if outputting to terminal
        if sys.stderr.isatty():
            color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
            reset = self.COLORS["RESET"]
            record.levelname = f"{color}{record.levelname}{reset}"

        # Format: timestamp [LEVEL] logger.module.function:line - message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        location = f"{record.module}.{record.funcName}:{record.lineno}"

        formatted = f"{timestamp} [{record.levelname}] {record.name}.{location} - {record.getMessage()}"

        # Add exception info if present
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


def archive_existing_logs(log_dir: Path) -> dict[str, Any]:
    """
    Archive existing log files to a timestamped folder.

    This ensures each server run gets fresh log files while preserving
    previous logs for historical reference.

    Args:
        log_dir: Directory containing log files to archive

    Returns:
        Dictionary with archival information:
        - 'archived': bool - Whether logs were archived
        - 'archive_dir': str or None - Archive directory path if archived
        - 'file_count': int - Number of files archived
    """
    result = {"archived": False, "archive_dir": None, "file_count": 0}

    if not log_dir.exists():
        return result

    # Check if any log files exist
    log_files = list(log_dir.glob("*.log*")) + list(log_dir.glob("*.jsonl*"))
    if not log_files:
        return result

    # Create archive directory with timestamp
    archive_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_dir = log_dir / "archives" / archive_timestamp
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Move all log files to archive
    archived_count = 0
    for log_file in log_files:
        try:
            dest = archive_dir / log_file.name
            shutil.move(str(log_file), str(dest))
            archived_count += 1
        except Exception as e:
            # Print to stderr since logging isn't setup yet
            print(f"Warning: Failed to archive {log_file.name}: {e}", file=sys.stderr)

    result["archived"] = archived_count > 0
    result["archive_dir"] = (
        str(archive_dir.relative_to(log_dir)) if archived_count > 0 else None
    )
    result["file_count"] = archived_count

    return result


def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 10,
) -> None:
    """
    Setup comprehensive logging for the MCP server.

    Existing log files are automatically archived to a timestamped folder
    under logs/archives/ on each startup, ensuring fresh logs for each run.

    Args:
        log_dir: Directory to store log files
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup log files to keep
    """
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Archive existing logs before starting new run
    archive_info = archive_existing_logs(log_path)

    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels, filter per handler

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # === File Handler: All logs (JSON structured) ===
    all_logs_file = log_path / "mcp_server_all.jsonl"
    all_handler = logging.handlers.RotatingFileHandler(
        all_logs_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    all_handler.setLevel(logging.DEBUG)
    all_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(all_handler)

    # === File Handler: Error logs only (JSON structured) ===
    error_logs_file = log_path / "mcp_server_errors.jsonl"
    error_handler = logging.handlers.RotatingFileHandler(
        error_logs_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(error_handler)

    # === File Handler: Human-readable logs ===
    readable_logs_file = log_path / "mcp_server.log"
    readable_handler = logging.handlers.RotatingFileHandler(
        readable_logs_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    readable_handler.setLevel(numeric_level)
    readable_handler.setFormatter(HumanReadableFormatter())
    root_logger.addHandler(readable_handler)

    # === Console Handler: Human-readable (stderr) ===
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(HumanReadableFormatter())
    root_logger.addHandler(console_handler)

    # Set specific log levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Log the startup
    logger = logging.getLogger("microsoft_mcp.logging")

    # Log archival status first
    if archive_info["archived"]:
        logger.info(
            f"Previous logs archived: {archive_info['file_count']} file(s) → "
            f"{archive_info['archive_dir']}"
        )
    else:
        logger.info("Fresh start: No previous logs found")

    logger.info(f"Logging initialized - Level: {log_level}")
    logger.info(f"Log directory: {log_path.absolute()}")
    logger.info(f"All logs: {all_logs_file.name}")
    logger.info(f"Error logs: {error_logs_file.name}")
    logger.info(f"Readable logs: {readable_logs_file.name}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
