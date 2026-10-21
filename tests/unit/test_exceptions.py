"""Unit tests for eagle.core.exceptions."""

import pytest

from eagle.core.exceptions import (
    AudioError,
    ConfigurationError,
    EagleError,
    InvalidConfigError,
    MicrophoneNotFoundError,
    PermissionDeniedError,
    SecurityViolationError,
    ToolError,
    ToolNotFoundError,
)


def test_base_eagle_error_formatting() -> None:
    """Verify EagleError message and optional details string formatting."""
    err_simple = EagleError("Something went wrong")
    assert str(err_simple) == "[EAGLE] Something went wrong"

    err_detailed = EagleError("Operation blocked", details={"reason": "unauthorized"})
    assert "[EAGLE] Operation blocked" in str(err_detailed)
    assert "unauthorized" in str(err_detailed)
    assert err_detailed.details["reason"] == "unauthorized"


def test_exception_inheritance_hierarchies() -> None:
    """Verify that specific exceptions are catchable by their respective subsystem base."""
    # Config hierarchy
    cfg_err = InvalidConfigError("Bad config value")
    assert isinstance(cfg_err, ConfigurationError)
    assert isinstance(cfg_err, EagleError)

    # Audio hierarchy
    audio_err = MicrophoneNotFoundError("No mic detected")
    assert isinstance(audio_err, AudioError)
    assert isinstance(audio_err, EagleError)

    # Tool and security hierarchy
    sec_err = SecurityViolationError("Path traversal attempt")
    assert isinstance(sec_err, ToolError)
    assert isinstance(sec_err, EagleError)

    perm_err = PermissionDeniedError("User cancelled action")
    assert isinstance(perm_err, ToolError)
    assert isinstance(perm_err, EagleError)


def test_catching_polymorphically() -> None:
    """Verify polymorphic exception handling works as expected."""

    def raise_tool_error() -> None:
        raise ToolNotFoundError("unknown_tool")

    with pytest.raises(EagleError) as exc_info:
        raise_tool_error()
    assert isinstance(exc_info.value, ToolError)
    assert isinstance(exc_info.value, ToolNotFoundError)
