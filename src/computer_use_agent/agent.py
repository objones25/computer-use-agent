"""Agent loop for Claude computer use."""

import asyncio
from typing import Any

import anthropic
from rich.console import Console

from .captcha import CaptchaSolver
from .config import Config, HumanLoopMode
from .human_loop import HumanLoopHandler
from .tools import BaseTool, BashTool, ComputerTool, ToolResult


console = Console()


class ComputerUseAgent:
    """Agent that uses Claude to control a computer."""

    def __init__(
        self,
        config: Config,
        docker_container: str = "computer-use-desktop",
    ):
        """Initialize the computer use agent.

        Args:
            config: Agent configuration
            docker_container: Name of the Docker container to control
        """
        self.config = config
        self.docker_container = docker_container

        # Initialize Anthropic client
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

        # Initialize tools
        self.computer_tool = ComputerTool(
            display_width=config.display_width,
            display_height=config.display_height,
            docker_container=docker_container,
        )
        self.bash_tool = BashTool(docker_container=docker_container)
        self.tools: list[BaseTool] = [self.computer_tool, self.bash_tool]

        # Initialize CAPTCHA solver
        self.captcha_solver: CaptchaSolver | None = None
        if config.capmonster_api_key:
            self.captcha_solver = CaptchaSolver(config.capmonster_api_key)

        # Initialize human-in-the-loop handler
        self.human_handler = HumanLoopHandler(mode=config.human_loop_mode)

        # Conversation history
        self.messages: list[dict[str, Any]] = []

    def _get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for the API."""
        return [tool.get_tool_definition() for tool in self.tools]

    def _get_tool_by_name(self, name: str) -> BaseTool | None:
        """Get a tool by its name."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> ToolResult:
        """Execute a tool and return the result.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            ToolResult from the tool execution
        """
        tool = self._get_tool_by_name(tool_name)
        if not tool:
            return ToolResult(error=f"Unknown tool: {tool_name}")

        # Check if we should prompt for confirmation
        action_desc = self._describe_action(tool_name, tool_input)
        if self.human_handler.should_prompt_for_action(action_desc):
            # Take a screenshot first to show context
            screenshot_result = await self.computer_tool.execute(action="screenshot")
            screenshot = screenshot_result.base64_image

            confirmed = await self.human_handler.prompt_confirmation(
                action_desc,
                screenshot_base64=screenshot,
            )
            if not confirmed:
                return ToolResult(error="Action cancelled by user")

        # Execute the tool
        return await tool.execute(**tool_input)

    def _describe_action(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> str:
        """Generate a human-readable description of an action.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters

        Returns:
            Human-readable description
        """
        if tool_name == "computer":
            action = tool_input.get("action", "unknown")
            if action == "screenshot":
                return "Take a screenshot"
            elif action == "left_click":
                coord = tool_input.get("coordinate", [0, 0])
                return f"Click at position ({coord[0]}, {coord[1]})"
            elif action == "type":
                text = tool_input.get("text", "")
                # Mask if it looks like a password (typing after password prompt)
                if len(text) > 0:
                    return f"Type text: {'*' * len(text)}"
                return "Type text"
            elif action == "key":
                return f"Press key: {tool_input.get('key', 'unknown')}"
            elif action == "scroll":
                direction = tool_input.get("scroll_direction", "down")
                return f"Scroll {direction}"
            else:
                return f"Computer action: {action}"
        elif tool_name == "bash":
            cmd = tool_input.get("command", "")
            return f"Run command: {cmd[:50]}..." if len(cmd) > 50 else f"Run command: {cmd}"
        else:
            return f"Execute {tool_name}"

    async def _handle_credential_request(
        self,
        credential_type: str,
        service_name: str = "",
    ) -> str | None:
        """Handle a request for credentials from Claude.

        Args:
            credential_type: Type of credential (username, password, 2fa)
            service_name: Name of the service

        Returns:
            The credential value or None if cancelled
        """
        if credential_type == "username":
            result = await self.human_handler.prompt_username(service_name)
        elif credential_type == "password":
            result = await self.human_handler.prompt_password(service_name)
        elif credential_type == "2fa":
            result = await self.human_handler.prompt_2fa_code()
        else:
            result = await self.human_handler.prompt_custom(
                f"Please enter {credential_type} for {service_name}"
            )

        if result.cancelled:
            return None
        return result.value

    async def _handle_captcha(
        self,
        website_url: str,
        page_html: str | None = None,
        screenshot_base64: str | None = None,
    ) -> str | None:
        """Handle CAPTCHA solving.

        Args:
            website_url: Current page URL
            page_html: Page HTML content
            screenshot_base64: Page screenshot

        Returns:
            CAPTCHA solution or None if failed
        """
        # Try automated solving first
        if self.captcha_solver:
            self.human_handler.show_status("Attempting automated CAPTCHA solving...")

            result = await self.captcha_solver.detect_and_solve(
                website_url,
                page_html=page_html,
                screenshot_base64=screenshot_base64,
            )

            if result.success and result.solution:
                self.human_handler.show_success("CAPTCHA solved automatically!")
                return result.solution
            else:
                self.human_handler.show_error(
                    f"Automated solving failed: {result.error}"
                )

        # Fall back to manual solving
        self.human_handler.show_status("Falling back to manual CAPTCHA solving...")
        manual_result = await self.human_handler.prompt_captcha(
            screenshot_base64=screenshot_base64,
        )

        if manual_result.cancelled:
            return None
        return manual_result.value

    async def run(
        self,
        task: str,
        max_iterations: int = 50,
    ) -> str:
        """Run the agent with a task.

        Args:
            task: The task to perform
            max_iterations: Maximum number of agent loop iterations

        Returns:
            Final response from Claude
        """
        # Add the initial user message
        self.messages = [{"role": "user", "content": task}]

        self.human_handler.show_status(f"Starting task: {task}")

        system_prompt = self._get_system_prompt()

        for iteration in range(max_iterations):
            console.print(f"\n[dim]--- Iteration {iteration + 1}/{max_iterations} ---[/dim]")

            try:
                # Call Claude API
                response = self.client.beta.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    system=system_prompt,
                    tools=self._get_tool_definitions(),
                    messages=self.messages,
                    betas=[self.config.beta_flag],
                )
            except anthropic.APIError as e:
                self.human_handler.show_error(f"API error: {e}")
                return f"API error: {e}"

            # Process the response
            assistant_content = response.content
            self.messages.append({"role": "assistant", "content": assistant_content})

            # Display any text content from Claude
            for block in assistant_content:
                if hasattr(block, "text"):
                    console.print(f"\n[bold]Claude:[/bold] {block.text}")
                elif hasattr(block, "thinking"):
                    self.human_handler.show_thinking(block.thinking)

            # Check if we're done (no tool use)
            if response.stop_reason == "end_turn":
                # Extract final text response
                final_text = ""
                for block in assistant_content:
                    if hasattr(block, "text"):
                        final_text += block.text
                return final_text

            # Process tool use requests
            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    console.print(f"\n[cyan]Tool: {tool_name}[/cyan]")
                    console.print(f"[dim]Input: {tool_input}[/dim]")

                    # Execute the tool
                    result = await self._execute_tool(tool_name, tool_input)

                    # Format result for API
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result.to_api_result(),
                        "is_error": result.is_error,
                    })

                    # Show result status
                    if result.is_error:
                        self.human_handler.show_error(f"Tool error: {result.error}")
                    elif result.output:
                        console.print(f"[green]Result: {result.output[:100]}...[/green]"
                                      if len(result.output or "") > 100
                                      else f"[green]Result: {result.output}[/green]")
                    elif result.base64_image:
                        console.print("[green]Screenshot captured[/green]")

            # Add tool results to conversation
            if tool_results:
                self.messages.append({"role": "user", "content": tool_results})

        self.human_handler.show_error("Maximum iterations reached")
        return "Task incomplete: maximum iterations reached"

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return f"""You are a computer use assistant that can control a desktop computer.
You have access to a virtual desktop running in a Docker container.

Display resolution: {self.config.display_width}x{self.config.display_height}

When performing tasks:
1. Always take a screenshot first to see the current state
2. Analyze the screenshot carefully before taking actions
3. Click precisely on UI elements you can see
4. Wait briefly after actions for the UI to update
5. Verify your actions worked by taking another screenshot

For login tasks:
- When you need credentials (username, password), describe what you need clearly
- The user will provide credentials when prompted
- Never guess or make up credentials
- For 2FA codes, wait for the user to provide them

For CAPTCHA challenges:
- If you detect a CAPTCHA, describe it and request solving
- The system will attempt to solve it automatically
- If automatic solving fails, the user will be prompted

Be careful with sensitive actions like:
- Clicking submit/confirm buttons
- Making purchases
- Deleting content
- Changing settings

Always explain what you're about to do before taking actions.
After each step, verify the result with a screenshot."""
