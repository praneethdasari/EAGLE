"""Unit tests for Windows startup, session greeting deduplication, and single-instance locking."""

import datetime
from pathlib import Path
from unittest.mock import patch

from eagle.services.startup import (
    SessionGreetingTracker,
    SingleInstanceManager,
    WindowsStartupManager,
    get_time_based_greeting,
)


def test_time_based_greeting_hours() -> None:
    """Verify time-based greetings map accurately to local hour intervals."""
    # Morning (5am - 11:59am)
    m1 = datetime.datetime(2026, 11, 6, 5, 0, 0)
    m2 = datetime.datetime(2026, 11, 6, 11, 59, 59)
    assert get_time_based_greeting(m1, user_title="boss") == "Good morning, boss!"
    assert get_time_based_greeting(m2, user_title="chief") == "Good morning, chief!"

    # Afternoon (12pm - 4:59pm)
    a1 = datetime.datetime(2026, 11, 6, 12, 0, 0)
    a2 = datetime.datetime(2026, 11, 6, 16, 59, 59)
    assert get_time_based_greeting(a1, user_title="boss") == "Good afternoon, boss!"
    assert get_time_based_greeting(a2, user_title="boss") == "Good afternoon, boss!"

    # Evening (5pm - 9:59pm)
    e1 = datetime.datetime(2026, 11, 6, 17, 0, 0)
    e2 = datetime.datetime(2026, 11, 6, 21, 59, 59)
    assert get_time_based_greeting(e1, user_title="boss") == "Good evening, boss!"
    assert get_time_based_greeting(e2, user_title="boss") == "Good evening, boss!"

    # Night (10pm - 4:59am)
    n1 = datetime.datetime(2026, 11, 6, 22, 0, 0)
    n2 = datetime.datetime(2026, 11, 6, 3, 30, 0)
    assert get_time_based_greeting(n1, user_title="boss") == "Good night, boss!"
    assert get_time_based_greeting(n2, user_title="boss") == "Good night, boss!"


def test_session_greeting_tracker() -> None:
    """Verify greeting is delivered only once per session and tracks delivery state."""
    tracker = SessionGreetingTracker.get_instance()
    tracker.reset()

    assert tracker.has_greeted() is False
    tracker.mark_greeted()
    assert tracker.has_greeted() is True

    # Subsequent check still reports greeted
    assert tracker.has_greeted() is True
    tracker.reset()
    assert tracker.has_greeted() is False


def test_single_instance_manager(tmp_path: Path) -> None:
    """Verify single instance lock file acquisition and release."""
    lock_file = tmp_path / "test_eagle.lock"
    mgr1 = SingleInstanceManager(lockfile_path=lock_file)
    mgr2 = SingleInstanceManager(lockfile_path=lock_file)

    # First instance acquires lock
    assert mgr1.acquire() is True
    assert lock_file.exists()

    # Second instance fails to acquire lock
    assert mgr2.acquire() is False

    # First instance releases lock
    mgr1.release()

    # Second instance can now acquire lock
    assert mgr2.acquire() is True
    mgr2.release()


def test_windows_startup_manager_mocked() -> None:
    """Verify registry startup manager enable, check, and disable operations."""
    with patch("sys.platform", "win32"):
        with patch("winreg.OpenKey", create=True):
            with patch("winreg.QueryValueEx", return_value=('"C:\\path\\EAGLE.exe"', 1)):
                assert WindowsStartupManager.is_startup_enabled() is True

            with patch("winreg.SetValueEx") as mock_set:
                assert WindowsStartupManager.enable_startup("C:\\EAGLE\\EAGLE.exe") is True
                assert mock_set.called

            with patch("winreg.DeleteValue") as mock_del:
                assert WindowsStartupManager.disable_startup() is True
                assert mock_del.called

