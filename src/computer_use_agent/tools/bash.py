"""Bash tool for executing shell commands."""

import asyncio
from typing import Any

from .base import BaseTool, ToolResult


class BashTool(BaseTool):
    """Tool for executing bash commands in the container."""

    def __init__(
        self,
        docker_container: str | None = None,
        timeout: float = 120.0,
    ):
        """Initialize the bash tool.

        Args:
            docker_container: Docker container name to run commands in (optional)
            timeout: Command timeout in seconds
        """
        self.docker_container = docker_container
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "bash"

    def get_tool_definition(self) -> dict[str, Any]:
        """Get the bash tool definition for the API."""
        return {
            "type": "bash_20250124",
            "name": self.name,
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a bash command."""
        command = kwargs.get("command", "")
        restart = kwargs.get("restart", False)

        if restart:
            # For now, just return a message since we don't maintain shell state
            return ToolResult(output="Shell restarted (stateless mode)")

        if not command:
            return ToolResult(error="No command provided")

        try:
            return await self._run_command(command)
        except asyncio.TimeoutError:
            return ToolResult(error=f"Command timed out after {self.timeout}s")
        except Exception as e:
            return ToolResult(error=f"Error executing command: {str(e)}")

    async def _run_command(self, command: str) -> ToolResult:
        """Run a bash command."""
        if self.docker_container:
            full_cmd = [
                "docker",
                "exec",
                self.docker_container,
                "bash",
                "-c",
                command,
            ]
        else:
            full_cmd = ["bash", "-c", command]

        process = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            raise

        stdout_str = stdout.decode() if stdout else ""
        stderr_str = stderr.decode() if stderr else ""

        # Combine output
        output_parts = []
        if stdout_str:
            output_parts.append(stdout_str)
        if stderr_str:
            output_parts.append(f"stderr: {stderr_str}")

        output = "\n".join(output_parts) if output_parts else "(no output)"

        # Check return code
        if process.returncode != 0:
            return ToolResult(
                error=f"Command failed with exit code {process.returncode}\n{output}"
            )

        return ToolResult(output=output)
