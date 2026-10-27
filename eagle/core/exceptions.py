"""Custom exception hierarchy for the EAGLE voice assistant."""

from typing import Any


class EagleError(Exception):
    """Base exception for all EAGLE-specific errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"[EAGLE] {self.message} | Details: {self.details}"
        return f"[EAGLE] {self.message}"


# =====================================================================
# Configuration Exceptions
# =====================================================================


class ConfigurationError(EagleError):
    """Raised when there is an issue loading or validating configuration."""


class MissingConfigError(ConfigurationError):
    """Raised when a required configuration key or file is missing."""


class InvalidConfigError(ConfigurationError):
    """Raised when configuration values fail schema validation."""


# =====================================================================
# Audio & Speech Exceptions
# =====================================================================


class AudioError(EagleError):
    """Base class for audio capture, playback, and processing failures."""


class MicrophoneNotFoundError(AudioError):
    """Raised when no operational input microphone is detected."""


class MicrophonePermissionError(AudioError):
    """Raised when OS permissions deny microphone access."""


class TranscriptionError(AudioError):
    """Raised when Speech-to-Text conversion fails."""


class SynthesisError(AudioError):
    """Raised when Text-to-Speech generation fails."""


class WakeWordError(AudioError):
    """Raised when wake word detection fails to initialize or run."""


# =====================================================================
# AI Provider Exceptions
# =====================================================================


class AIProviderError(EagleError):
    """Base class for AI reasoning engine and API client failures."""


class AuthenticationError(AIProviderError):
    """Raised when AI provider credentials/API keys are invalid or missing."""


class ModelUnavailableError(AIProviderError):
    """Raised when the specified model or endpoint is unreachable."""


class RateLimitExceededError(AIProviderError):
    """Raised when provider rate limits or quotas are hit."""


class NetworkTimeoutError(AIProviderError):
    """Raised when an AI provider request times out."""


class InvalidResponseError(AIProviderError):
    """Raised when the AI model returns malformed or unparseable output."""


# =====================================================================
# Tool & Security Exceptions
# =====================================================================


class ToolError(EagleError):
    """Base class for tool execution failures."""


class ToolNotFoundError(ToolError):
    """Raised when an unregistered or unallowed tool is requested."""


class InvalidToolArgumentsError(ToolError):
    """Raised when tool arguments fail validation against its schema."""


class ToolExecutionError(ToolError):
    """Raised when a tool encounters an error during execution."""


class SecurityViolationError(ToolError):
    """Raised when an operation attempts unauthorized actions or path traversal."""


class PermissionDeniedError(ToolError):
    """Raised when an operation is cancelled or rejected by user confirmation."""
