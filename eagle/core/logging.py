"""Structured logging subsystem with automatic secret redaction for EAGLE."""

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Regex patterns matching potential API keys and secrets
SENSITIVE_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),  # OpenAI & generic sk- keys
    re.compile(r"gsk_[a-zA-Z0-9_-]{20,}", re.IGNORECASE),  # Groq keys
    re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),  # Anthropic keys
    re.compile(r"AIza[0-9A-Za-z-_]{35}", re.IGNORECASE),  # Google API keys
    re.compile(r"(api[_-]?key\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-]{16,})(['\"]?)", re.IGNORECASE),
    re.compile(r"(bearer\s+)([a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-]{16,})(['\"]?)", re.IGNORECASE),
]

REDACTED_REPLACEMENT = "[REDACTED]"


class RedactingFilter(logging.Filter):
    """Logging filter that scrubs sensitive keys and tokens from all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._sanitize_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._sanitize_value(v) for v in record.args)
        return True

    @classmethod
    def redact(cls, text: str) -> str:
        """Replace all matched sensitive patterns with REDACTED_REPLACEMENT."""
        sanitized = text
        for pattern in SENSITIVE_PATTERNS:
            sanitized = pattern.sub(REDACTED_REPLACEMENT, sanitized)
        return sanitized

    @classmethod
    def _sanitize_value(cls, val: object) -> object:
        if isinstance(val, str):
            return cls.redact(val)
        return val


def setup_logging(
    level: str = "INFO",
    log_dir: Path | str | None = None,
    log_file_name: str = "eagle.log",
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 3,
    enable_console: bool = True,
) -> logging.Logger:
    """Configures the root logger for EAGLE with console and rotating file output.

    Args:
        level: Log level name (e.g. DEBUG, INFO, WARNING, ERROR).
        log_dir: Directory where log files are stored. Defaults to ./logs.
        log_file_name: Base filename for the log.
        max_bytes: Max size in bytes before rotating.
        backup_count: Number of rotated log archives to keep.
        enable_console: Whether to emit logs to stderr/stdout.

    Returns:
        The configured root EAGLE logger.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger("eagle")
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if root_logger.handlers:
        root_logger.handlers.clear()

    redactor = RedactingFilter()
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(redactor)
        root_logger.addHandler(console_handler)

    # Rotating File Handler
    if log_dir is not None:
        target_dir = Path(log_dir)
    else:
        target_dir = Path("logs")

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / log_file_name
        file_handler = RotatingFileHandler(
            filename=str(file_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redactor)
        root_logger.addHandler(file_handler)
    except (OSError, PermissionError) as exc:
        # If file logging cannot be initialized, warn via console
        root_logger.warning("Failed to initialize file logger in %s: %s", target_dir, exc)

    return root_logger


def get_logger(subsystem_name: str) -> logging.Logger:
    """Return a namespaced logger under the 'eagle' hierarchy.

    Args:
        subsystem_name: Subsystem identifier (e.g., 'core.config', 'tools.files').
    """
    if subsystem_name.startswith("eagle."):
        return logging.getLogger(subsystem_name)
    return logging.getLogger(f"eagle.{subsystem_name}")
