"""Base tool abstractions and validation interfaces for EAGLE."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from eagle.core.exceptions import InvalidToolArgumentsError


class EmptyParameters(BaseModel):
    """Empty schema for tools that do not require parameters."""


@dataclass
class ToolResult:
    """Standardized result returned by tool execution."""

    success: bool
    output: Any = None
    error: str | None = None
    requires_confirmation: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "requires_confirmation": self.requires_confirmation,
            "metadata": self.metadata,
        }


class BaseTool(ABC):
    """Abstract base class for all allowlisted EAGLE desktop tools."""

    name: str
    description: str
    parameters_schema: type[BaseModel]
    is_sensitive: bool = False

    def validate_args(self, raw_args: dict[str, Any]) -> BaseModel:
        """Validate raw dictionary arguments against the tool's Pydantic schema.

        Raises:
            InvalidToolArgumentsError: If arguments violate schema constraints.
        """
        try:
            return self.parameters_schema.model_validate(raw_args)
        except ValidationError as exc:
            raise InvalidToolArgumentsError(
                f"Invalid arguments for tool '{self.name}': {exc}",
                details={"errors": exc.errors()},
            ) from exc

    @abstractmethod
    def run(self, validated_args: BaseModel) -> ToolResult:
        """Execute the tool logic using validated arguments."""
        raise NotImplementedError

    def execute(self, raw_args: dict[str, Any]) -> ToolResult:
        """Entry point that validates arguments and executes the tool safely."""
        validated = self.validate_args(raw_args)
        return self.run(validated)

    def to_tool_spec(self) -> dict[str, Any]:
        """Generate OpenAI/Gemini-compatible tool specification schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema.model_json_schema(),
            },
        }
