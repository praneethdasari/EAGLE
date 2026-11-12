"""Configuration management subsystem for EAGLE using Pydantic v2 schemas."""

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from eagle.core.exceptions import ConfigurationError, InvalidConfigError
from eagle.core.logging import get_logger
from eagle.core.paths import (
    get_default_config_path,
    get_documents_dir,
)

logger = get_logger("core.config")


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
        current_docs = str(get_documents_dir().resolve())
        resolved: list[str] = []
        has_documents_entry = False

        for d in dirs:
            try:
                p = Path(d).resolve()
                p_str = str(p)
                # Check if this entry represents a Windows Documents directory
                if p.name.lower() == "documents" or p_str.lower() == current_docs.lower():
                    # If it points to an old, non-existent, or different Documents location, reconcile
                    if not p.exists() or p_str.lower() != current_docs.lower():
                        if current_docs not in resolved:
                            resolved.append(current_docs)
                        has_documents_entry = True
                        continue
                    else:
                        has_documents_entry = True

                if p_str not in resolved:
                    resolved.append(p_str)
            except Exception:
                if d not in resolved:
                    resolved.append(d)

        # Ensure current dynamic Documents directory is always present
        if not has_documents_entry and current_docs not in resolved:
            resolved.append(current_docs)

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


def _cleanup_stale_temp_files(directory: Path, base_name: str, max_age_seconds: float = 300.0) -> None:
    """Safely remove leftover temporary files older than max_age_seconds."""
    try:
        prefix = f"{base_name}.tmp."
        bak_prefix = f"{base_name}.bak.tmp."
        now = time.time()
        for item in directory.iterdir():
            if item.is_file() and (item.name.startswith(prefix) or item.name.startswith(bak_prefix)):
                try:
                    if (now - item.stat().st_mtime) > max_age_seconds:
                        item.unlink()
                except OSError:
                    pass
    except OSError:
        pass


def _validate_config_file(path: Path) -> tuple[EagleConfig | None, Exception | None]:
    """Read and validate a configuration file against EagleConfig schema.

    Returns:
        (EagleConfig, None) if valid.
        (None, Exception) if missing, empty, invalid JSON, or schema validation failed.
    """
    if not path.exists() or not path.is_file():
        return None, FileNotFoundError(f"Configuration file '{path}' does not exist.")

    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return None, InvalidConfigError(f"Configuration file '{path}' is empty (0 bytes).")
        raw_data = json.loads(content)
    except json.JSONDecodeError as exc:
        return None, InvalidConfigError(f"Configuration file '{path}' is not valid JSON: {exc}")
    except OSError as exc:
        return None, ConfigurationError(f"Failed to read configuration file '{path}': {exc}")

    try:
        cfg = EagleConfig.model_validate(raw_data)
        return cfg, None
    except Exception as exc:
        return None, InvalidConfigError(f"Configuration validation failed for '{path}': {exc}")


def load_config(
    config_path: Path | str | None = None,
    raise_on_error: bool = False,
) -> EagleConfig:
    """Load and validate EAGLE configuration from disk with automatic corruption recovery.

    Recovery Workflow:
    1. Resolve target path (config_path override or get_default_config_path()).
    2. Attempt to load and validate primary configuration.
    3. If primary is missing, empty, or corrupted, attempt recovery from backup (<path>.bak).
    4. If recovery succeeds:
       - Preserve the corrupted primary file as <path>.corrupted.<timestamp> for inspection.
       - Restore the primary configuration atomically using save_config().
       - Log the recovery event.
    5. If both primary and backup are invalid or missing:
       - Preserve any corrupted files as <file>.corrupted.<timestamp>.
       - Log the critical recovery failure.
       - If raise_on_error is True, raise InvalidConfigError.
       - Otherwise, return a safe default EagleConfig instance to ensure startup succeeds.
    6. Reconcile dynamic system paths (such as Documents folder) if needed.
    """
    path = (Path(config_path) if config_path else get_default_config_path()).resolve()
    target_dir = path.parent
    bak_path = target_dir / f"{path.name}.bak"

    # Clean up stale temp files
    if target_dir.exists():
        _cleanup_stale_temp_files(target_dir, path.name)

    # 1. Neither primary nor backup exists -> default fresh installation
    if not path.exists() and not bak_path.exists():
        logger.debug("No configuration file found at '%s'. Using safe defaults.", path)
        return EagleConfig()

    # 2. Attempt loading primary configuration
    primary_cfg: EagleConfig | None = None
    primary_err: Exception | None = None

    if path.exists():
        primary_cfg, primary_err = _validate_config_file(path)

    if primary_cfg is not None:
        # Reconcile persisted config if allowed directories changed (e.g. relocated Documents)
        try:
            with open(path, encoding="utf-8") as f:
                raw_data = json.load(f)
            if (
                raw_data.get("security", {}).get("allowed_directories")
                != primary_cfg.security.allowed_directories
            ):
                save_config(primary_cfg, path)
        except Exception as save_err:
            logger.debug("Could not automatically re-save reconciled config: %s", save_err)
        return primary_cfg

    # 3. Primary failed or is missing -> Attempt recovery from backup
    if path.exists():
        logger.warning(
            "Primary configuration '%s' is corrupted or invalid (%s). Attempting automatic recovery from '%s'...",
            path,
            primary_err,
            bak_path,
        )
    else:
        logger.warning(
            "Primary configuration '%s' is missing. Attempting automatic recovery from backup '%s'...",
            path,
            bak_path,
        )

    bak_cfg: EagleConfig | None = None
    bak_err: Exception | None = None

    if bak_path.exists():
        bak_cfg, bak_err = _validate_config_file(bak_path)

    timestamp = int(time.time())

    def _preserve_corrupt(file_path: Path) -> Path | None:
        try:
            if file_path.exists():
                if file_path.stat().st_size > 0:
                    dest = target_dir / f"{file_path.name}.corrupted.{timestamp}"
                    if dest.exists():
                        dest = target_dir / f"{file_path.name}.corrupted.{timestamp}_{uuid.uuid4().hex[:4]}"
                    os.replace(file_path, dest)
                    logger.info("Preserved corrupted file '%s' as '%s'.", file_path, dest)
                    return dest
                else:
                    file_path.unlink()
        except OSError as preserve_err:
            logger.warning("Could not preserve corrupted file '%s': %s", file_path, preserve_err)
        return None

    if bak_cfg is not None:
        # Recovery from backup succeeded!
        logger.info(
            "Automatic recovery succeeded: restoring configuration from backup '%s' to '%s'.",
            bak_path,
            path,
        )

        # Preserve corrupted primary file for user inspection if it existed and had bytes
        _preserve_corrupt(path)

        # Restore valid configuration atomically to primary path
        try:
            save_config(bak_cfg, path)
        except Exception as restore_err:
            logger.warning("Failed to persist recovered configuration to '%s': %s", path, restore_err)

        return bak_cfg

    # 4. Both primary and backup failed (or are corrupted)
    logger.error(
        "Configuration recovery failed for '%s'. Primary error: %s; Backup error: %s. Preserving files and falling back to safe defaults.",
        path,
        primary_err,
        bak_err,
    )

    # Preserve corrupted files so user data is never lost
    _preserve_corrupt(path)
    _preserve_corrupt(bak_path)

    if raise_on_error:
        raise InvalidConfigError(
            f"Configuration recovery failed for '{path}'. Primary error: {primary_err}; Backup error: {bak_err}"
        )

    return EagleConfig()


def save_config(config: EagleConfig, config_path: Path | str | None = None) -> None:
    """Save configuration object to disk using atomic writes and automatic backup rotation.

    Guarantees:
    1. Backup Rotation: If a valid configuration already exists at the target path,
       it is safely preserved to <path>.bak before replacement. Corrupted existing
       configurations never overwrite a valid backup.
    2. Atomic Writes: Writes to a unique temporary file in the same directory, flushes
       and fsyncs buffers, validates schema integrity, and replaces atomically with os.replace.
    3. Cleanup: Temporary files are cleaned up reliably on success or failure.
    """
    path = (Path(config_path) if config_path else get_default_config_path()).resolve()
    target_dir = path.parent
    bak_path = target_dir / f"{path.name}.bak"

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Failed to create configuration directory '{target_dir}': {exc}") from exc

    # Clean up any abandoned temporary files from previous interrupted writes
    _cleanup_stale_temp_files(target_dir, path.name)

    # Serialize and validate the new configuration before touching disk
    try:
        json_data = config.model_dump_json(indent=2)
        # Pre-validate dumped JSON
        EagleConfig.model_validate_json(json_data)
    except Exception as exc:
        raise ConfigurationError(f"Failed to serialize configuration for '{path}': {exc}") from exc

    # Backup rotation: preserve existing valid configuration
    if path.exists() and path.is_file():
        existing_cfg, _ = _validate_config_file(path)
        if existing_cfg is not None:
            # Existing configuration is valid; rotate it safely to .bak
            bak_tmp = target_dir / f"{path.name}.bak.tmp.{os.getpid()}_{uuid.uuid4().hex[:8]}"
            try:
                shutil.copy2(path, bak_tmp)
                with open(bak_tmp, "a", encoding="utf-8") as bf:
                    bf.flush()
                    os.fsync(bf.fileno())
                os.replace(bak_tmp, bak_path)
            except Exception as bak_err:
                logger.warning("Failed to rotate configuration backup to '%s': %s", bak_path, bak_err)
            finally:
                if bak_tmp.exists():
                    try:
                        bak_tmp.unlink()
                    except OSError:
                        pass
        else:
            logger.warning(
                "Existing configuration '%s' is corrupted or invalid; preserving existing backup '%s' intact.",
                path,
                bak_path,
            )

    # Atomic write to temporary file
    tmp_path = target_dir / f"{path.name}.tmp.{os.getpid()}_{uuid.uuid4().hex[:8]}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(json_data)
            f.flush()
            os.fsync(f.fileno())

        # Validate on-disk temporary file before replacing active configuration
        verified_cfg, verify_err = _validate_config_file(tmp_path)
        if verified_cfg is None:
            raise ConfigurationError(f"Temporary configuration verification failed: {verify_err}")

        # Atomic replacement on Windows NTFS
        os.replace(tmp_path, path)
    except Exception as exc:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise ConfigurationError(f"Failed to save configuration atomically to '{path}': {exc}") from exc
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
