"""Unit tests for eagle.core.config."""

import json
from pathlib import Path

import pytest

from eagle.core.config import (
    EagleConfig,
    is_path_within_allowed,
    load_config,
    save_config,
)
from eagle.core.exceptions import InvalidConfigError


def test_default_config_instantiation() -> None:
    """Verify EagleConfig initializes with sensible, safe defaults."""
    config = EagleConfig()
    assert config.app_name == "EAGLE"
    assert config.version == "0.1.0"
    assert config.audio.sample_rate == 16000
    assert config.audio.channels == 1
    assert config.ai.provider == "mock"
    assert config.security.confirm_sensitive_actions is True
    assert "notepad" in config.security.allowed_applications


def test_load_config_from_valid_file(temp_config_file: Path) -> None:
    """Verify loading from a valid JSON file."""
    config = load_config(temp_config_file)
    assert config.app_name == "EAGLE"
    assert config.log_level == "DEBUG"
    assert config.audio.stt_model_size == "tiny"
    assert config.ai.model_name == "mock-model"


def test_load_config_fallback_when_file_not_found(tmp_path: Path) -> None:
    """Verify fallback to defaults if config file does not exist."""
    non_existent = tmp_path / "does_not_exist.json"
    config = load_config(non_existent)
    assert isinstance(config, EagleConfig)
    assert config.app_name == "EAGLE"


def test_load_config_invalid_json_raises_error(tmp_path: Path) -> None:
    """Verify InvalidConfigError is raised when reading corrupted JSON."""
    bad_file = tmp_path / "bad_config.json"
    bad_file.write_text("{ this is not valid json : 123", encoding="utf-8")

    with pytest.raises(InvalidConfigError) as exc_info:
        load_config(bad_file)
    assert "not valid JSON" in str(exc_info.value)


def test_load_config_invalid_schema_types(tmp_path: Path) -> None:
    """Verify validation error when schema types are violated."""
    bad_file = tmp_path / "invalid_schema.json"
    bad_data = {
        "audio": {
            "vad_threshold": 99.9  # Must be between 0.0 and 1.0
        }
    }
    bad_file.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(InvalidConfigError) as exc_info:
        load_config(bad_file)
    assert "validation failed" in str(exc_info.value).lower()


def test_save_and_reload_config(tmp_path: Path) -> None:
    """Verify saving a config to disk and reloading it preserves values."""
    target_path = tmp_path / "saved_config.json"
    config = EagleConfig()
    config.app_name = "EAGLE"
    config.log_level = "WARNING"
    config.audio.tts_rate = 210

    save_config(config, target_path)
    assert target_path.exists()

    reloaded = load_config(target_path)
    assert reloaded.app_name == "EAGLE"
    assert reloaded.log_level == "WARNING"
    assert reloaded.audio.tts_rate == 210


def test_is_path_within_allowed(tmp_path: Path) -> None:
    """Verify sandbox boundary checking and path traversal prevention."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    allowed_dirs = [str(sandbox)]

    safe_file = sandbox / "notes.txt"
    safe_sub_dir = sandbox / "sub" / "file.txt"
    traversal_attempt = sandbox / ".." / "secret.txt"
    outside_file = tmp_path / "other" / "data.txt"

    assert is_path_within_allowed(safe_file, allowed_dirs) is True
    assert is_path_within_allowed(safe_sub_dir, allowed_dirs) is True
    assert is_path_within_allowed(traversal_attempt, allowed_dirs) is False
    assert is_path_within_allowed(outside_file, allowed_dirs) is False
