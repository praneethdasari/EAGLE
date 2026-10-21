"""Tool registry enforcing strict allowlisting and validation."""

from typing import Any

from eagle.core.exceptions import (
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
)
from eagle.core.logging import get_logger
from eagle.tools.base import BaseTool, ToolResult

logger = get_logger("tools.registry")


class ToolRegistry:
    """Central registry and executor for allowlisted EAGLE desktop tools."""

    def __init__(self, confirm_sensitive_actions: bool = True) -> None:
        self._tools: dict[str, BaseTool] = {}
        self.confirm_sensitive_actions = confirm_sensitive_actions

    def register(self, tool: BaseTool) -> None:
        """Register a tool in the allowlist."""
        if not tool.name:
            raise ValueError("Tool name must not be empty.")
        if tool.name in self._tools:
            logger.warning("Overwriting existing tool registration for: %s", tool.name)
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def unregister(self, name: str) -> BaseTool | None:
        """Remove a tool from the allowlist."""
        return self._tools.pop(name, None)

    def get_tool(self, name: str) -> BaseTool:
        """Retrieve a registered tool by name.

        Raises:
            ToolNotFoundError: If tool is not in the allowlist.
        """
        tool = self._tools.get(name)
        if not tool:
            raise ToolNotFoundError(
                f"Tool '{name}' is not in the approved EAGLE allowlist.",
                details={"requested_tool": name, "available_tools": list(self._tools.keys())},
            )
        return tool

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def list_tools(self) -> list[str]:
        """Return list of all registered tool names."""
        return sorted(self._tools.keys())

    def get_tool_specs(self) -> list[dict[str, Any]]:
        """Return schema specifications for all registered tools."""
        return [tool.to_tool_spec() for tool in self._tools.values()]

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        confirmed: bool = False,
    ) -> ToolResult:
        """Validate and execute an allowlisted tool.

        Args:
            name: Name of the registered tool.
            arguments: Dictionary of input arguments.
            confirmed: Whether the user has explicitly confirmed the action (for sensitive tools).

        Returns:
            ToolResult with execution status and output.

        Raises:
            ToolNotFoundError: If the tool is not registered.
            PermissionDeniedError: If a sensitive tool is executed without user confirmation.
        """
        tool = self.get_tool(name)

        if tool.is_sensitive and self.confirm_sensitive_actions and not confirmed:
            logger.info("Sensitive tool '%s' blocked awaiting user confirmation.", name)
            return ToolResult(
                success=False,
                error=f"Operation '{name}' is sensitive and requires explicit user confirmation.",
                requires_confirmation=True,
            )

        logger.info("Executing tool '%s' with arguments: %s", name, arguments)
        try:
            result = tool.execute(arguments)
            logger.info("Tool '%s' executed successfully: %s", name, result.success)
            return result
        except Exception as exc:
            logger.error("Error executing tool '%s': %s", name, exc, exc_info=True)
            if isinstance(exc, ToolError):
                raise
            raise ToolExecutionError(f"Execution failed for tool '{name}': {exc}") from exc
