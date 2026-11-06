"""Windows startup management, single-instance protection, and session greeting lifecycle."""

import datetime
import os
import sys
import threading
from pathlib import Path
from typing import Any

from eagle.core.logging import get_logger
from eagle.core.paths import get_user_data_dir

logger = get_logger("services.startup")

RUN_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "EAGLE"


class WindowsStartupManager:
    """Manages Windows automatic login startup via HKCU Run registry key."""

    @staticmethod
    def is_startup_enabled() -> bool:
        """Check whether EAGLE is registered in Windows Startup."""
        if sys.platform != "win32":
            return False

        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, RUN_REG_KEY, 0, winreg.KEY_READ
            ) as key:
                val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
                return bool(val)
        except (FileNotFoundError, OSError):
            return False
        except Exception as exc:
            logger.debug("Failed querying Windows startup registry: %s", exc)
            return False

    @staticmethod
    def enable_startup(executable_path: Path | str | None = None) -> bool:
        """Register EAGLE executable in Windows Startup (HKCU Run key)."""
        if sys.platform != "win32":
            return False

        try:
            import winreg

            if executable_path:
                target_str = f'"{Path(executable_path).resolve()}"'
            elif getattr(sys, "frozen", False):
                target_str = f'"{sys.executable}"'
            else:
                # Source mode: pythonw/python -m eagle.main
                target_str = f'"{sys.executable}" -m eagle.main'

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, RUN_REG_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, target_str)

            logger.info("Enabled Windows startup entry: %s", target_str)
            return True
        except Exception as exc:
            logger.warning("Failed enabling Windows startup entry: %s", exc)
            return False

    @staticmethod
    def disable_startup() -> bool:
        """Remove EAGLE registration from Windows Startup."""
        if sys.platform != "win32":
            return False

        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, RUN_REG_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                    logger.info("Disabled Windows startup entry for EAGLE.")
                    return True
                except FileNotFoundError:
                    return True
        except Exception as exc:
            logger.warning("Failed disabling Windows startup entry: %s", exc)
            return False


def get_time_based_greeting(
    current_dt: datetime.datetime | None = None,
    user_title: str = "boss",
) -> str:
    """Return context-appropriate greeting based on the current local hour.

    Morning:   05:00 - 11:59 -> "Good morning, boss!"
    Afternoon: 12:00 - 16:59 -> "Good afternoon, boss!"
    Evening:   17:00 - 21:59 -> "Good evening, boss!"
    Night:     22:00 - 04:59 -> "Good night, boss!"
    """
    now = current_dt or datetime.datetime.now()
    hour = now.hour
    title = user_title.strip() if user_title else "boss"

    if 5 <= hour < 12:
        return f"Good morning, {title}!"
    elif 12 <= hour < 17:
        return f"Good afternoon, {title}!"
    elif 17 <= hour < 22:
        return f"Good evening, {title}!"
    else:
        return f"Good night, {title}!"


class SessionGreetingTracker:
    """Tracks session-level greeting delivery to avoid repeated greetings after internal restarts."""

    _instance: "SessionGreetingTracker | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._greeted = False

    @classmethod
    def get_instance(cls) -> "SessionGreetingTracker":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def has_greeted(self) -> bool:
        return self._greeted

    def mark_greeted(self) -> None:
        self._greeted = True

    def reset(self) -> None:
        self._greeted = False


class SingleInstanceManager:
    """Provides single-instance execution protection using an isolated lockfile."""

    def __init__(self, lockfile_path: Path | None = None) -> None:
        self.lockfile = lockfile_path or (get_user_data_dir() / "eagle.lock")
        self._lock_handle: Any = None
        self._is_locked = False

    def acquire(self) -> bool:
        """Attempt to acquire exclusive lock. Returns True if successful, False if already running."""
        try:
            self.lockfile.parent.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                import msvcrt

                self._lock_handle = open(self.lockfile, "w")
                msvcrt.locking(self._lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl  # type: ignore[import-not-found, import-untyped]

                self._lock_handle = open(self.lockfile, "w")
                fcntl.flock(self._lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore[attr-defined]

            # Write active PID
            self._lock_handle.write(f"{os.getpid()}\n")
            self._lock_handle.flush()
            self._is_locked = True
            return True
        except OSError:
            logger.warning("Another instance of EAGLE is already running.")
            return False

    def release(self) -> None:
        """Release the instance lock and clean up the lockfile."""
        if not self._is_locked:
            return

        try:
            if sys.platform == "win32" and self._lock_handle:
                import msvcrt

                try:
                    self._lock_handle.seek(0)
                    msvcrt.locking(self._lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            elif self._lock_handle:
                import fcntl  # type: ignore[import-not-found, import-untyped]

                try:
                    fcntl.flock(self._lock_handle, fcntl.LOCK_UN)  # type: ignore[attr-defined]
                except Exception:
                    pass

            if self._lock_handle:
                self._lock_handle.close()
                self._lock_handle = None

            if self.lockfile.exists():
                try:
                    self.lockfile.unlink()
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("Error releasing lockfile: %s", exc)
        finally:
            self._is_locked = False

