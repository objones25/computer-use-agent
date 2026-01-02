"""Credential request tool for human-in-the-loop authentication."""

from typing import Any, Literal

from .base import BaseTool, ToolResult


CredentialType = Literal["username", "password", "2fa", "custom"]


class CredentialTool(BaseTool):
    """Tool for requesting credentials from the user.

    This tool allows Claude to prompt the user for login credentials
    during authentication flows.
    """

    def __init__(self, human_handler: Any):
        """Initialize the credential tool.

        Args:
            human_handler: HumanLoopHandler instance for prompting
        """
        self.human_handler = human_handler

    @property
    def name(self) -> str:
        return "credential"

    def get_tool_definition(self) -> dict[str, Any]:
        """Get the tool definition for the API."""
        return {
            "name": self.name,
            "description": (
                "Request credentials from the user for authentication. "
                "Use this tool when you encounter a login form and need the user's "
                "username, password, or 2FA code. The user will be prompted securely."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "credential_type": {
                        "type": "string",
                        "enum": ["username", "password", "2fa", "custom"],
                        "description": (
                            "Type of credential to request: "
                            "'username' for login ID/email, "
                            "'password' for password (hidden input), "
                            "'2fa' for two-factor authentication code, "
                            "'custom' for other input"
                        ),
                    },
                    "service_name": {
                        "type": "string",
                        "description": (
                            "Name of the service/website for context "
                            "(e.g., 'Cool Math Games', 'Amazon')"
                        ),
                    },
                    "custom_message": {
                        "type": "string",
                        "description": (
                            "Custom message to display when credential_type is 'custom'"
                        ),
                    },
                },
                "required": ["credential_type", "service_name"],
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the credential request.

        Args:
            credential_type: Type of credential (username, password, 2fa, custom)
            service_name: Name of the service for context
            custom_message: Optional message for custom credential type

        Returns:
            ToolResult with the credential value or error
        """
        credential_type: CredentialType = kwargs.get("credential_type", "username")
        service_name: str = kwargs.get("service_name", "the service")
        custom_message: str = kwargs.get("custom_message", "")

        try:
            if credential_type == "username":
                result = await self.human_handler.prompt_username(service_name)
            elif credential_type == "password":
                result = await self.human_handler.prompt_password(service_name)
            elif credential_type == "2fa":
                result = await self.human_handler.prompt_2fa_code()
            elif credential_type == "custom":
                message = custom_message or f"Please enter the requested information for {service_name}"
                result = await self.human_handler.prompt_custom(message)
            else:
                return ToolResult(error=f"Unknown credential type: {credential_type}")

            if result.cancelled:
                return ToolResult(error="User cancelled the credential request")

            return ToolResult(output=result.value)

        except Exception as e:
            return ToolResult(error=f"Error requesting credential: {str(e)}")
