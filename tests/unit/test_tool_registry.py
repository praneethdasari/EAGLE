"""Unit tests for eagle.tools.base and eagle.tools.registry."""

import pytest
from pydantic import BaseModel, Field

from eagle.core.exceptions import (
    InvalidToolArgumentsError,
    ToolNotFoundError,
)
from eagle.tools.base import BaseTool, EmptyParameters, ToolResult
from eagle.tools.registry import ToolRegistry


class EchoArgs(BaseModel):
    message: str = Field(description="Message to echo")
    repeat: int = Field(default=1, ge=1, le=5, description="Number of times to repeat")


class EchoTool(BaseTool):
    name = "echo_tool"
    description = "Repeats a message a specified number of times."
    parameters_schema: type[BaseModel] = EchoArgs
    is_sensitive = False

    def run(self, validated_args: BaseModel) -> ToolResult:
        args: EchoArgs = validated_args  # type: ignore[assignment]
        return ToolResult(
            success=True,
            output=" ".join([args.message] * args.repeat),
        )


class SensitiveTool(BaseTool):
    name = "delete_temp_cache"
    description = "Deletes temporary cache files."
    parameters_schema: type[BaseModel] = EmptyParameters
    is_sensitive = True

    def run(self, validated_args: BaseModel) -> ToolResult:
        return ToolResult(success=True, output="Cache cleared successfully.")


def test_tool_registration_and_retrieval() -> None:
    """Verify tools can be registered and retrieved from the registry."""
    registry = ToolRegistry()
    tool = EchoTool()

    registry.register(tool)
    assert registry.has_tool("echo_tool") is True
    assert registry.get_tool("echo_tool") is tool
    assert registry.list_tools() == ["echo_tool"]

    # Tool spec generation
    specs = registry.get_tool_specs()
    assert len(specs) == 1
    assert specs[0]["function"]["name"] == "echo_tool"


def test_tool_unregistration() -> None:
    """Verify tool unregistration removes it from registry."""
    registry = ToolRegistry()
    registry.register(EchoTool())
    assert registry.has_tool("echo_tool") is True

    removed = registry.unregister("echo_tool")
    assert removed is not None
    assert registry.has_tool("echo_tool") is False


def test_unregistered_tool_execution_raises_error() -> None:
    """Verify executing an unregistered tool raises ToolNotFoundError."""
    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError) as exc_info:
        registry.execute("malicious_shell_cmd", {"command": "whoami"})
    assert "not in the approved EAGLE allowlist" in str(exc_info.value)


def test_tool_argument_validation() -> None:
    """Verify argument schema validation enforces constraints."""
    registry = ToolRegistry()
    registry.register(EchoTool())

    # Valid execution
    result = registry.execute("echo_tool", {"message": "Eagle", "repeat": 2})
    assert result.success is True
    assert result.output == "Eagle Eagle"

    # Missing required argument
    with pytest.raises(InvalidToolArgumentsError) as exc_missing:
        registry.execute("echo_tool", {"repeat": 2})
    assert "Invalid arguments" in str(exc_missing.value)

    # Argument violates range (repeat > 5)
    with pytest.raises(InvalidToolArgumentsError) as exc_range:
        registry.execute("echo_tool", {"message": "Hello", "repeat": 10})
    assert "Invalid arguments" in str(exc_range.value)


def test_sensitive_tool_requires_confirmation() -> None:
    """Verify sensitive tools are blocked without confirmation."""
    registry = ToolRegistry(confirm_sensitive_actions=True)
    registry.register(SensitiveTool())

    # Attempt without confirmation
    blocked_result = registry.execute("delete_temp_cache", {}, confirmed=False)
    assert blocked_result.success is False
    assert blocked_result.requires_confirmation is True
    assert "requires explicit user confirmation" in (blocked_result.error or "")

    # Execute with explicit confirmation
    confirmed_result = registry.execute("delete_temp_cache", {}, confirmed=True)
    assert confirmed_result.success is True
    assert "Cache cleared" in confirmed_result.output
