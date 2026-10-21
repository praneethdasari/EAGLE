"""Unit tests for eagle.core.logging."""

from pathlib import Path

from eagle.core.logging import RedactingFilter, get_logger, setup_logging


def test_redacting_filter_patterns() -> None:
    """Verify that sensitive patterns are scrubbed by RedactingFilter."""
    filter_ = RedactingFilter()

    # OpenAI-style key
    text_openai = "Connecting with sk-proj1234567890abcdef1234567890 to endpoint"
    assert "sk-proj" not in filter_.redact(text_openai)
    assert "[REDACTED]" in filter_.redact(text_openai)

    # Groq-style key
    text_groq = "Groq initialization with gsk_abcdef1234567890abcdef123456"
    assert "gsk_" not in filter_.redact(text_groq)
    assert "[REDACTED]" in filter_.redact(text_groq)

    # Anthropic-style key
    text_anthropic = "Anthropic secret sk-ant-api03-abcdef1234567890abcdef1234567890"
    assert "sk-ant" not in filter_.redact(text_anthropic)
    assert "[REDACTED]" in filter_.redact(text_anthropic)

    # Bearer token
    text_bearer = "Authorization: Bearer mySecretToken1234567890abcdef"
    assert "mySecretToken" not in filter_.redact(text_bearer)
    assert "[REDACTED]" in filter_.redact(text_bearer)

    # Harmless text should remain untouched
    harmless = "Application EAGLE started successfully on port 8000"
    assert filter_.redact(harmless) == harmless


def test_setup_logging_creates_file(tmp_path: Path) -> None:
    """Verify that setup_logging writes structured records to the log directory."""
    log_dir = tmp_path / "logs"
    logger = setup_logging(
        level="DEBUG",
        log_dir=log_dir,
        log_file_name="test_eagle.log",
        enable_console=False,
    )

    logger.info("Test log entry: EAGLE initialization test")
    logger.info("Test secret scrubbing: sk-live1234567890abcdef1234567890")

    log_file = log_dir / "test_eagle.log"
    assert log_file.exists()

    content = log_file.read_text(encoding="utf-8")
    assert "EAGLE initialization test" in content
    assert "sk-live" not in content
    assert "[REDACTED]" in content


def test_get_logger_prefix() -> None:
    """Verify logger names are appropriately prefixed with 'eagle.'."""
    log1 = get_logger("core.config")
    assert log1.name == "eagle.core.config"

    log2 = get_logger("eagle.tools.files")
    assert log2.name == "eagle.tools.files"
