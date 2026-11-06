"""Configuration management subsystem for EAGLE using Pydantic v2 schemas."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from eagle.core.exceptions import ConfigurationError, InvalidConfigError
from eagle.core.paths import (
    get_default_config_path,
    get_documents_dir,
)


class AudioConfig(BaseModel):
    """Audio capture and synthesis configuration."""

    sample_rate: int = Field(default=16000, description="Sampling rate in Hz for STT")
    channels: int = Field(default=1, description="Audio channels (1 = mono)")
    device_index: int | None = Field(default=None, description="Audio input device index")
    vad_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="VAD sensitivity threshold"
    )
    stt_model_size: str = Field(
        default="base", description="Whisper model size (tiny, base, small, medium)"
    )
    tts_voice: str = Field(default="default", description="TTS voice identifier or 'mock'")
    tts_rate: int = Field(default=175, ge=50, le=400, description="TTS words per minute")
    tts_volume: float = Field(default=1.0, ge=0.0, le=1.0, description="TTS volume")
    wake_word_enabled: bool = Field(
        default=True, description="Whether wake word listening is enabled"
    )
    wake_word_phrase: str = Field(default="hey eagle", description="Wake word phrase")
    wake_word_engine: str = Field(
        default="local_stt",
        description="Wake word engine ('local_stt', 'openwakeword', 'mock')",
    )
    wake_word_sensitivity: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Wake word detection sensitivity"
    )
    command_timeout_seconds: float = Field(
        default=8.0,
        ge=1.0,
        le=30.0,
        description="Maximum duration in seconds to capture command speech",
    )
    silence_timeout_seconds: float = Field(
        default=1.5,
        ge=0.5,
        le=10.0,
        description="Duration of trailing silence in seconds to finish command capture",
    )
    continuous_listening: bool = Field(
        default=True,
        description="Whether to resume listening for wake word automatically after command processing",
    )
    followup_timeout_seconds: float = Field(
        default=5.0,
        ge=2.0,
        le=30.0,
        description="Duration of follow-up response window in seconds before returning to sleep",
    )
    user_title: str = Field(
        default="boss",
        description="User honorific/title used in spoken interactions (e.g. 'boss')",
    )
    startup_greeting: bool = Field(
        default=True,
        description="Deliver time-based spoken greeting upon Windows startup",
    )
    start_with_windows: bool = Field(
        default=True,
        description="Automatically start EAGLE upon Windows user sign-in",
    )


# Alias for backward and voice-subsystem compatibility
VoiceConfig = AudioConfig


class AIConfig(BaseModel):
    """AI reasoning engine configuration."""

    provider: str = Field(
        default="ollama",
        description="Active AI provider ('ollama', 'auto', 'openai', 'gemini', 'anthropic', 'groq', 'mock')",
    )
    model_name: str = Field(default="qwen2.5:3b", description="Model identifier")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=1024, ge=1, le=8192, description="Maximum generation tokens")
    system_prompt: str = Field(
        default=(
            "You are EAGLE (Enhanced Autonomous General-purpose Local Executive), "
            "a helpful, precise, and secure AI desktop voice assistant. "
            "You speak concisely, answer questions accurately, and only execute approved computer tools. "
            "Never attempt dangerous or destructive operations without explicit confirmation."
        ),
        description="Base persona prompt",
    )
    api_key: str | None = Field(
        default=None, description="Optional API key override (prefers environment variable)"
    )
    base_url: str | None = Field(
        default=None, description="Custom base URL for OpenAI-compatible providers or local Ollama"
    )
    timeout_seconds: float = Field(
        default=30.0, ge=1.0, le=120.0, description="Network timeout in seconds"
    )
    max_conversation_turns: int = Field(
        default=20, ge=1, le=100, description="Maximum conversation history turns to retain"
    )
    max_tool_iterations: int = Field(
        default=3, ge=1, le=10, description="Maximum consecutive tool call loops per query"
    )
    offline_mode: bool = Field(
        default=False,
        description="Enforce strict offline mode (prohibits cloud AI and network requests)",
    )


class SecurityConfig(BaseModel):
    """Security boundaries, allowlists, and permission policies."""

    allowed_directories: list[str] = Field(
        default_factory=lambda: [str(get_documents_dir()), str(Path.cwd())],
        description="Directories where file operations are authorized",
    )
    allowed_applications: dict[str, str] = Field(
        default_factory=lambda: {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "explorer": "explorer.exe",
            "browser": "msedge.exe",
            "paint": "mspaint.exe",
        },
        description="Registry of allowed applications and their executable names",
    )
    allowed_domains: list[str] = Field(
        default_factory=lambda: [
            "google.com",
            "github.com",
            "wikipedia.org",
            "python.org",
            "stackoverflow.com",
        ],
        description="Allowed domains for direct web launching",
    )
    confirm_sensitive_actions: bool = Field(
        default=True,
        description="Require explicit confirmation before file deletion, overwrite, or system changes",
    )

    @field_validator("allowed_directories", mode="after")
    @classmethod
    def resolve_allowed_directories(cls, dirs: list[str]) -> list[str]:
        resolved: list[str] = []
        for d in dirs:
            try:
                res_path = str(Path(d).resolve())
                if res_path not in resolved:
                    resolved.append(res_path)
            except Exception:
                if d not in resolved:
                    resolved.append(d)
        return resolved


class UIConfig(BaseModel):
    """PySide6 desktop interface appearance and layout configuration."""

    theme: str = Field(default="eagle_dark", description="UI theme identifier")
    window_title: str = Field(
        default="EAGLE — Voice Assistant", description="Application window title"
    )
    window_width: int = Field(default=950, ge=600, le=3840)
    window_height: int = Field(default=680, ge=400, le=2160)
    show_visualizer: bool = Field(default=True, description="Render live audio visualizer")
    start_minimized: bool = Field(default=False, description="Start minimized to system tray")


class EagleConfig(BaseModel):
    """Root configuration object for EAGLE."""

    version: str = Field(default="0.1.0", description="Configuration schema version")
    app_name: str = Field(default="EAGLE", description="Branded application name")
    log_level: str = Field(default="INFO", description="Global logging level")
    audio: AudioConfig = Field(default_factory=AudioConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    ui: UIConfig = Field(default_factory=UIConfig)

    def __init__(self, **data: Any) -> None:
        if "voice" in data and "audio" not in data:
            data["audio"] = data.pop("voice")
        super().__init__(**data)

    @property
    def voice(self) -> AudioConfig:
        """Alias property for audio configuration."""
        return self.audio


DEFAULT_CONFIG_PATH = get_default_config_path()


def is_path_within_allowed(target_path: Path | str, allowed_dirs: list[str]) -> bool:
    """Check if target_path resolves strictly inside one of the allowed directories.

    Prevents directory traversal and symlink escapes.
    """
    try:
        resolved_target = Path(target_path).resolve()
        for allowed in allowed_dirs:
            resolved_allowed = Path(allowed).resolve()
            # If target equals or is relative to allowed dir
            try:
                resolved_target.relative_to(resolved_allowed)
                return True
            except ValueError:
                continue
        return False
    except (OSError, RuntimeError):
        return False


def load_config(config_path: Path | str | None = None) -> EagleConfig:
    """Load and validate EAGLE configuration from disk, falling back to defaults if missing.

    Raises:
        InvalidConfigError: If JSON syntax or schema validation fails.
    """
    path = Path(config_path) if config_path else get_default_config_path()

    if not path.exists():
        return EagleConfig()

    try:
        with open(path, encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as exc:
        raise InvalidConfigError(f"Configuration file '{path}' is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise ConfigurationError(f"Failed to read configuration file '{path}': {exc}") from exc

    try:
        return EagleConfig.model_validate(raw_data)
    except Exception as exc:
        raise InvalidConfigError(f"Configuration validation failed for '{path}': {exc}") from exc


def save_config(config: EagleConfig, config_path: Path | str | None = None) -> None:
    """Save configuration object to disk as formatted JSON."""
    path = Path(config_path) if config_path else get_default_config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(config.model_dump_json(indent=2))
    except OSError as exc:
        raise ConfigurationError(f"Failed to save configuration to '{path}': {exc}") from exc
