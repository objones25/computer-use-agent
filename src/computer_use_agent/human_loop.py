"""Human-in-the-loop interaction handling."""

import asyncio
import base64
import getpass
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

from .config import HumanLoopMode


console = Console()


class InteractionType(Enum):
    """Types of human interactions."""

    CREDENTIAL_USERNAME = "credential_username"
    CREDENTIAL_PASSWORD = "credential_password"
    TWO_FACTOR_CODE = "two_factor_code"
    CAPTCHA_MANUAL = "captcha_manual"
    CONFIRMATION = "confirmation"
    CUSTOM_INPUT = "custom_input"


@dataclass
class HumanInput:
    """Result from human input."""

    value: str
    cancelled: bool = False


class HumanLoopHandler:
    """Handler for human-in-the-loop interactions."""

    def __init__(
        self,
        mode: HumanLoopMode = HumanLoopMode.SENSITIVE_ONLY,
        on_screenshot: Callable[[str], None] | None = None,
    ):
        """Initialize the human loop handler.

        Args:
            mode: How often to prompt for human input
            on_screenshot: Optional callback to display screenshots
        """
        self.mode = mode
        self.on_screenshot = on_screenshot
        self._pending_confirmations: list[str] = []

    def should_prompt_for_action(self, action_description: str) -> bool:
        """Determine if we should prompt before an action.

        Args:
            action_description: Description of the action to take

        Returns:
            True if we should prompt for confirmation
        """
        if self.mode == HumanLoopMode.ALWAYS_CONFIRM:
            return True

        if self.mode == HumanLoopMode.MINIMAL:
            return False

        # SENSITIVE_ONLY mode - check for sensitive actions
        sensitive_keywords = [
            "login", "sign in", "signin", "password", "credential",
            "payment", "purchase", "buy", "checkout", "credit card",
            "bank", "transfer", "submit", "confirm", "delete",
            "remove", "unsubscribe", "cancel",
        ]

        action_lower = action_description.lower()
        return any(keyword in action_lower for keyword in sensitive_keywords)

    async def prompt_confirmation(
        self,
        action_description: str,
        screenshot_base64: str | None = None,
    ) -> bool:
        """Prompt the user to confirm an action.

        Args:
            action_description: Description of what will happen
            screenshot_base64: Optional screenshot to show

        Returns:
            True if user confirms, False otherwise
        """
        # Display screenshot if provided and we have a handler
        if screenshot_base64 and self.on_screenshot:
            self.on_screenshot(screenshot_base64)

        console.print()
        console.print(Panel(
            Text(action_description, style="yellow"),
            title="[bold blue]Action Confirmation[/bold blue]",
            border_style="blue",
        ))

        return Confirm.ask("[bold]Proceed with this action?[/bold]", default=True)

    async def prompt_username(
        self,
        service_name: str = "the service",
    ) -> HumanInput:
        """Prompt for username/email.

        Args:
            service_name: Name of the service for context

        Returns:
            HumanInput with the username
        """
        console.print()
        console.print(Panel(
            f"Please enter your username/email for [bold]{service_name}[/bold]",
            title="[bold green]Login Required[/bold green]",
            border_style="green",
        ))

        try:
            value = Prompt.ask("[bold]Username/Email[/bold]")
            return HumanInput(value=value)
        except KeyboardInterrupt:
            return HumanInput(value="", cancelled=True)

    async def prompt_password(
        self,
        service_name: str = "the service",
    ) -> HumanInput:
        """Prompt for password (hidden input).

        Args:
            service_name: Name of the service for context

        Returns:
            HumanInput with the password
        """
        console.print()
        console.print(Panel(
            f"Please enter your password for [bold]{service_name}[/bold]",
            title="[bold green]Password Required[/bold green]",
            border_style="green",
        ))

        try:
            # Use getpass for secure password input
            value = getpass.getpass("Password: ")
            return HumanInput(value=value)
        except KeyboardInterrupt:
            return HumanInput(value="", cancelled=True)

    async def prompt_2fa_code(
        self,
        method: str = "your device",
    ) -> HumanInput:
        """Prompt for two-factor authentication code.

        Args:
            method: Description of how the code was sent

        Returns:
            HumanInput with the 2FA code
        """
        console.print()
        console.print(Panel(
            f"A verification code was sent to [bold]{method}[/bold].\n"
            "Please enter the code to continue.",
            title="[bold cyan]Two-Factor Authentication[/bold cyan]",
            border_style="cyan",
        ))

        try:
            value = Prompt.ask("[bold]2FA Code[/bold]")
            return HumanInput(value=value)
        except KeyboardInterrupt:
            return HumanInput(value="", cancelled=True)

    async def prompt_captcha(
        self,
        screenshot_base64: str | None = None,
        captcha_image_base64: str | None = None,
    ) -> HumanInput:
        """Prompt for manual CAPTCHA solution.

        Args:
            screenshot_base64: Full page screenshot
            captcha_image_base64: Cropped CAPTCHA image

        Returns:
            HumanInput with the CAPTCHA solution
        """
        console.print()

        # Display the CAPTCHA image if possible
        image_to_show = captcha_image_base64 or screenshot_base64
        if image_to_show:
            await self._display_image(image_to_show, "CAPTCHA Image")

        console.print(Panel(
            "Please solve the CAPTCHA shown above/in the viewer.\n"
            "If automated solving failed, enter the solution manually.",
            title="[bold red]CAPTCHA Required[/bold red]",
            border_style="red",
        ))

        try:
            value = Prompt.ask("[bold]CAPTCHA Solution[/bold]")
            return HumanInput(value=value)
        except KeyboardInterrupt:
            return HumanInput(value="", cancelled=True)

    async def prompt_custom(
        self,
        message: str,
        title: str = "Input Required",
        is_password: bool = False,
    ) -> HumanInput:
        """Prompt for custom input.

        Args:
            message: The message to display
            title: Title for the prompt panel
            is_password: Whether to hide input

        Returns:
            HumanInput with the user's input
        """
        console.print()
        console.print(Panel(
            message,
            title=f"[bold magenta]{title}[/bold magenta]",
            border_style="magenta",
        ))

        try:
            if is_password:
                value = getpass.getpass("Input: ")
            else:
                value = Prompt.ask("[bold]Input[/bold]")
            return HumanInput(value=value)
        except KeyboardInterrupt:
            return HumanInput(value="", cancelled=True)

    async def _display_image(
        self,
        image_base64: str,
        title: str = "Image",
    ) -> None:
        """Display an image to the user.

        This saves the image to a temp file and shows the path.
        In a real implementation, you might use a GUI viewer.

        Args:
            image_base64: Base64-encoded image
            title: Title for the image
        """
        try:
            # Decode and save to temp file
            image_data = base64.standard_b64decode(image_base64)
            with tempfile.NamedTemporaryFile(
                suffix=".png",
                delete=False,
                prefix="captcha_",
            ) as f:
                f.write(image_data)
                temp_path = f.name

            console.print(f"\n[dim]Image saved to: {temp_path}[/dim]")
            console.print("[dim]Open this file to view the image.[/dim]\n")

            # If we have a custom screenshot handler, use it
            if self.on_screenshot:
                self.on_screenshot(image_base64)

        except Exception as e:
            console.print(f"[red]Could not display image: {e}[/red]")

    def show_status(self, message: str, style: str = "blue") -> None:
        """Show a status message to the user.

        Args:
            message: The message to display
            style: Rich style for the message
        """
        console.print(f"[{style}]{message}[/{style}]")

    def show_error(self, message: str) -> None:
        """Show an error message to the user.

        Args:
            message: The error message
        """
        console.print(f"[bold red]Error: {message}[/bold red]")

    def show_success(self, message: str) -> None:
        """Show a success message to the user.

        Args:
            message: The success message
        """
        console.print(f"[bold green]{message}[/bold green]")

    def show_thinking(self, message: str) -> None:
        """Show Claude's thinking/reasoning to the user.

        Args:
            message: Claude's thinking content
        """
        console.print(Panel(
            message,
            title="[bold yellow]Claude's Reasoning[/bold yellow]",
            border_style="yellow",
        ))
