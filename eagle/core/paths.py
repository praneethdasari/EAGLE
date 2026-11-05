"""Filesystem path resolution, frozen packaging detection, and user data isolation."""

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """Return True if running inside a PyInstaller frozen bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_app_root() -> Path:
    """Return the base application directory.

    In development mode: returns repository root containing 'eagle'.
    In frozen PyInstaller mode: returns the temporary bundle extraction directory (_MEIPASS).
    """
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # In source mode: eagle/core/paths.py -> parent(core) -> parent(eagle) -> parent(repo root)
    return Path(__file__).resolve().parent.parent.parent


def get_executable_dir() -> Path:
    """Return directory containing the active executable or Python interpreter."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def get_user_data_dir() -> Path:
    """Return persistent user data directory outside the application/executable directory.

    On Windows: %APPDATA%/EAGLE
    On other platforms: ~/.eagle
    """
    appdata = os.environ.get("APPDATA")
    if appdata and sys.platform == "win32":
        path = Path(appdata) / "EAGLE"
    else:
        path = Path.home() / ".eagle"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


def get_user_cache_dir() -> Path:
    """Return persistent user cache directory for offline models and temporary data.

    On Windows: %LOCALAPPDATA%/EAGLE
    On other platforms: ~/.cache/eagle
    """
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata and sys.platform == "win32":
        path = Path(local_appdata) / "EAGLE"
    else:
        path = Path.home() / ".cache" / "eagle"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


def get_default_config_path() -> Path:
    """Return path to primary configuration file.

    Priority:
    1. If './config.json' exists in the current working directory, use it (portable mode).
    2. Otherwise, use persistent user data directory: '%APPDATA%/EAGLE/config.json'.
    """
    local_cfg = Path("config.json")
    if local_cfg.is_file():
        return local_cfg.resolve()
    return get_user_data_dir() / "config.json"


def get_logs_dir() -> Path:
    """Return directory for persistent application log files."""
    logs_dir = get_user_data_dir() / "logs"
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return logs_dir


def get_models_dir() -> Path:
    """Return directory for local offline models (faster-whisper, openWakeWord)."""
    models_dir = get_user_cache_dir() / "models"
    try:
        models_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return models_dir
