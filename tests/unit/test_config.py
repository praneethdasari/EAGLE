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
from eagle.core.paths import get_default_config_path
from eagle.services.startup import SingleInstanceManager


def test_default_config_instantiation() -> None:
    """Verify EagleConfig initializes with sensible, safe defaults."""
    config = EagleConfig()
    assert config.app_name == "EAGLE"
    assert config.version == "0.1.0"
    assert config.audio.sample_rate == 16000
    assert config.audio.channels == 1
    assert config.ai.provider == "ollama"
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


def test_load_config_invalid_json_raises_when_requested(tmp_path: Path) -> None:
    """Verify InvalidConfigError is raised when reading corrupted JSON if raise_on_error=True."""
    bad_file = tmp_path / "bad_config.json"
    bad_file.write_text("{ this is not valid json : 123", encoding="utf-8")

    with pytest.raises(InvalidConfigError) as exc_info:
        load_config(bad_file, raise_on_error=True)
    assert "not valid JSON" in str(exc_info.value)


def test_load_config_invalid_schema_types_raises_when_requested(tmp_path: Path) -> None:
    """Verify validation error when schema types are violated and raise_on_error=True."""
    bad_file = tmp_path / "invalid_schema.json"
    bad_data = {
        "audio": {
            "vad_threshold": 99.9  # Must be between 0.0 and 1.0
        }
    }
    bad_file.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(InvalidConfigError) as exc_info:
        load_config(bad_file, raise_on_error=True)
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


def test_dynamic_documents_path_reconciliation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify stale Documents path (e.g. C: drive) is dynamically reconciled with current user folder."""
    import eagle.core.config as config_mod
    from eagle.core.config import SecurityConfig

    simulated_current_docs = tmp_path / "SimulatedDocs"
    simulated_current_docs.mkdir()
    monkeypatch.setattr(config_mod, "get_documents_dir", lambda: simulated_current_docs)

    # Config with stale C: documents path
    stale_dirs = ["C:\\Users\\old_user\\Documents", str(tmp_path / "workspace")]
    sec = SecurityConfig(allowed_directories=stale_dirs)

    # Stale C: path should be replaced with simulated_current_docs
    assert str(simulated_current_docs.resolve()) in sec.allowed_directories
    assert "C:\\Users\\old_user\\Documents" not in sec.allowed_directories
    assert str((tmp_path / "workspace").resolve()) in sec.allowed_directories


# ==============================================================================
# ATOMIC CONFIGURATION WRITES & BACKUP ROTATION TESTS
# ==============================================================================

def test_atomic_config_write_and_temp_cleanup(tmp_path: Path) -> None:
    """Verify save_config writes atomically without leaving orphaned .tmp files."""
    cfg_file = tmp_path / "config.json"
    cfg = EagleConfig()
    cfg.app_name = "EAGLE-ATOMIC-TEST"

    save_config(cfg, cfg_file)
    assert cfg_file.exists()

    # Verify no .tmp files remain in directory
    tmp_files = list(tmp_path.glob("*.tmp.*"))
    assert len(tmp_files) == 0

    # Verify loaded contents
    loaded = load_config(cfg_file)
    assert loaded.app_name == "EAGLE-ATOMIC-TEST"


def test_backup_created_before_overwrite(tmp_path: Path) -> None:
    """Verify that updating a valid configuration automatically rotates previous config to .bak."""
    cfg_file = tmp_path / "config.json"
    bak_file = tmp_path / "config.json.bak"

    # Step 1: Write initial configuration
    cfg1 = EagleConfig()
    cfg1.app_name = "INITIAL-CONFIG"
    cfg1.audio.tts_rate = 150
    save_config(cfg1, cfg_file)

    assert cfg_file.exists()
    assert not bak_file.exists()

    # Step 2: Save updated configuration
    cfg2 = EagleConfig()
    cfg2.app_name = "UPDATED-CONFIG"
    cfg2.audio.tts_rate = 220
    save_config(cfg2, cfg_file)

    assert cfg_file.exists()
    assert bak_file.exists()

    # Verify current file has updated config
    loaded_current = load_config(cfg_file)
    assert loaded_current.app_name == "UPDATED-CONFIG"
    assert loaded_current.audio.tts_rate == 220

    # Verify backup file has initial config
    loaded_bak = load_config(bak_file)
    assert loaded_bak.app_name == "INITIAL-CONFIG"
    assert loaded_bak.audio.tts_rate == 150


def test_corrupted_config_does_not_overwrite_valid_backup(tmp_path: Path) -> None:
    """Verify that if config.json is corrupted on disk, saving does not overwrite a valid .bak with garbage."""
    cfg_file = tmp_path / "config.json"
    bak_file = tmp_path / "config.json.bak"

    # 1. Establish valid backup
    good_cfg = EagleConfig()
    good_cfg.app_name = "SAFE-BACKUP"
    save_config(good_cfg, bak_file)

    # 2. Simulate corrupted active config
    cfg_file.write_text("CORRUPTED JUNK { NOT VALID JSON", encoding="utf-8")

    # 3. Save a new config
    new_cfg = EagleConfig()
    new_cfg.app_name = "NEW-RECOVERED"
    save_config(new_cfg, cfg_file)

    # Active config now has new_cfg
    assert load_config(cfg_file).app_name == "NEW-RECOVERED"

    # Backup MUST still contain the original safe backup, NOT the corrupted junk!
    assert load_config(bak_file).app_name == "SAFE-BACKUP"


# ==============================================================================
# AUTOMATIC CORRUPTION RECOVERY TESTS
# ==============================================================================

def test_load_config_recovers_from_backup_when_primary_corrupted(tmp_path: Path) -> None:
    """Verify load_config recovers from .bak when primary file contains invalid JSON."""
    cfg_file = tmp_path / "config.json"
    bak_file = tmp_path / "config.json.bak"

    # Valid backup
    valid_cfg = EagleConfig()
    valid_cfg.app_name = "RESTORED-FROM-BACKUP"
    valid_cfg.audio.tts_voice = "custom-voice"
    save_config(valid_cfg, bak_file)

    # Primary is corrupted
    cfg_file.write_text("MALFORMED JSON {{{", encoding="utf-8")

    # Loading should recover from backup
    recovered = load_config(cfg_file)
    assert recovered.app_name == "RESTORED-FROM-BACKUP"
    assert recovered.audio.tts_voice == "custom-voice"

    # Primary config file should now be restored with valid data
    assert cfg_file.exists()
    restored_on_disk = load_config(cfg_file)
    assert restored_on_disk.app_name == "RESTORED-FROM-BACKUP"

    # Corrupted file must be preserved with timestamp
    corrupted_files = list(tmp_path.glob("config.json.corrupted.*"))
    assert len(corrupted_files) >= 1
    assert "MALFORMED JSON" in corrupted_files[0].read_text(encoding="utf-8")


def test_load_config_recovers_from_backup_when_primary_empty(tmp_path: Path) -> None:
    """Verify load_config recovers from .bak when primary file is 0 bytes."""
    cfg_file = tmp_path / "config.json"
    bak_file = tmp_path / "config.json.bak"

    valid_cfg = EagleConfig()
    valid_cfg.app_name = "EMPTY-RECOVERY"
    save_config(valid_cfg, bak_file)

    # Empty 0-byte file
    cfg_file.write_text("", encoding="utf-8")

    recovered = load_config(cfg_file)
    assert recovered.app_name == "EMPTY-RECOVERY"
    assert cfg_file.stat().st_size > 0


def test_load_config_recovers_when_primary_missing_but_backup_exists(tmp_path: Path) -> None:
    """Verify load_config recreates primary from .bak if primary was deleted."""
    cfg_file = tmp_path / "config.json"
    bak_file = tmp_path / "config.json.bak"

    valid_cfg = EagleConfig()
    valid_cfg.app_name = "BACKUP-ONLY"
    save_config(valid_cfg, bak_file)

    assert not cfg_file.exists()

    recovered = load_config(cfg_file)
    assert recovered.app_name == "BACKUP-ONLY"
    assert cfg_file.exists()


def test_load_config_falls_back_to_defaults_when_both_invalid(tmp_path: Path) -> None:
    """Verify load_config returns safe defaults without crashing when both primary and backup are corrupt."""
    cfg_file = tmp_path / "config.json"
    bak_file = tmp_path / "config.json.bak"

    cfg_file.write_text("CORRUPTED PRIMARY", encoding="utf-8")
    bak_file.write_text("CORRUPTED BACKUP", encoding="utf-8")

    # Should not raise exception; falls back to default EagleConfig
    cfg = load_config(cfg_file)
    assert isinstance(cfg, EagleConfig)
    assert cfg.app_name == "EAGLE"

    # Both corrupted files should be preserved
    corrupt_primary = list(tmp_path.glob("config.json.corrupted.*"))
    corrupt_backup = list(tmp_path.glob("config.json.bak.corrupted.*"))
    assert len(corrupt_primary) >= 1
    assert len(corrupt_backup) >= 1


# ==============================================================================
# CONFIGURATION PATH OVERRIDES & PRECEDENCE TESTS
# ==============================================================================

def test_config_precedence_cli_over_env_and_appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify explicit CLI path argument overrides environment variable and default AppData."""
    cli_file = tmp_path / "cli_config.json"
    env_file = tmp_path / "env_config.json"

    cli_cfg = EagleConfig()
    cli_cfg.app_name = "CLI-PRECEDENCE"
    save_config(cli_cfg, cli_file)

    env_cfg = EagleConfig()
    env_cfg.app_name = "ENV-PRECEDENCE"
    save_config(env_cfg, env_file)

    monkeypatch.setenv("EAGLE_CONFIG_PATH", str(env_file))

    # Explicit config_path takes priority
    loaded = load_config(cli_file)
    assert loaded.app_name == "CLI-PRECEDENCE"


def test_config_precedence_env_var_over_portable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify EAGLE_CONFIG_PATH environment variable overrides portable mode and AppData."""
    env_file = tmp_path / "env_config.json"
    env_cfg = EagleConfig()
    env_cfg.app_name = "FROM-ENV-VAR"
    save_config(env_cfg, env_file)

    monkeypatch.setenv("EAGLE_CONFIG_PATH", str(env_file))

    # Call get_default_config_path() and load_config() without arguments
    default_path = get_default_config_path()
    assert default_path == env_file.resolve()

    loaded = load_config()
    assert loaded.app_name == "FROM-ENV-VAR"


def test_single_instance_lock_unaffected_by_config_recovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that configuration corruption and recovery operations never tamper with eagle.lock."""
    user_data_dir = tmp_path / "AppData" / "EAGLE"
    user_data_dir.mkdir(parents=True)
    monkeypatch.setattr("eagle.core.paths.get_user_data_dir", lambda: user_data_dir)

    lockfile = user_data_dir / "eagle.lock"
    cfg_file = user_data_dir / "config.json"
    bak_file = user_data_dir / "config.json.bak"

    # Acquire single-instance lock
    lock_mgr = SingleInstanceManager(lockfile_path=lockfile)
    acquired = lock_mgr.acquire()
    assert acquired is True
    assert lockfile.exists()

    # While locked, another instance cannot acquire the lock
    second_lock = SingleInstanceManager(lockfile_path=lockfile)
    assert second_lock.acquire() is False

    # Set up valid backup and corrupted primary
    valid_cfg = EagleConfig()
    valid_cfg.app_name = "LOCK-SAFE-CONFIG"
    save_config(valid_cfg, bak_file)
    cfg_file.write_text("CORRUPTED JUNK { NOT VALID", encoding="utf-8")

    # Trigger recovery
    recovered = load_config(cfg_file)
    assert recovered.app_name == "LOCK-SAFE-CONFIG"

    # Assert lockfile is completely untouched, still exists, and still held exclusively
    assert lockfile.exists()
    assert second_lock.acquire() is False

    # Clean release of initial lock
    lock_mgr.release()

    # Now that the first instance released, another instance can acquire
    assert second_lock.acquire() is True
    second_lock.release()
