"""Base tool interface for computer use tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """Result from executing a tool action."""

    output: str | None = None
    error: str | None = None
    base64_image: str | None = None

    @property
    def is_error(self) -> bool:
        """Check if the result is an error."""
        return self.error is not None

    def to_api_result(self) -> str | list[dict[str, Any]]:
        """Convert to API-compatible tool result format.

        Returns:
            Either a string (for simple text) or a list of content blocks
            (for images or mixed content). The API expects one of these two formats.
        """
        if self.is_error:
            return self.error or "An error occurred"

        # If we have an image, return a list of content blocks
        if self.base64_image:
            content = []
            if self.output:
                content.append({"type": "text", "text": self.output})
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": self.base64_image,
                },
            })
            return content

        # For text-only results, return a string
        if self.output:
            return self.output

        return "Action completed successfully."


class BaseTool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tool name."""
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the given parameters."""
        ...

    def get_tool_definition(self) -> dict[str, Any]:
        """Get the tool definition for the API.

        Override this method for schema-less tools like computer use.
        """
        raise NotImplementedError("Subclass must implement get_tool_definition")
