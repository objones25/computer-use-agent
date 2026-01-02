"""Computer use tool for screenshot and mouse/keyboard control."""

import asyncio
import base64
import subprocess
from pathlib import Path
from typing import Any, Literal

from .base import BaseTool, ToolResult


ActionType = Literal[
    "screenshot",
    "left_click",
    "right_click",
    "middle_click",
    "double_click",
    "triple_click",
    "left_click_drag",
    "type",
    "key",
    "mouse_move",
    "scroll",
    "wait",
    "left_mouse_down",
    "left_mouse_up",
    "hold_key",
]

ScrollDirection = Literal["up", "down", "left", "right"]


class ComputerTool(BaseTool):
    """Tool for interacting with a computer display via xdotool and scrot."""

    def __init__(
        self,
        display_width: int = 1024,
        display_height: int = 768,
        display_num: int = 1,
        docker_container: str | None = None,
    ):
        """Initialize the computer tool.

        Args:
            display_width: Width of the virtual display
            display_height: Height of the virtual display
            display_num: X11 display number
            docker_container: Docker container name to run commands in (optional)
        """
        self.display_width = display_width
        self.display_height = display_height
        self.display_num = display_num
        self.docker_container = docker_container
        self._screenshot_dir = Path("/tmp/screenshots")

    @property
    def name(self) -> str:
        return "computer"

    def get_tool_definition(self) -> dict[str, Any]:
        """Get the computer use tool definition for the API."""
        return {
            "type": "computer_20250124",
            "name": self.name,
            "display_width_px": self.display_width,
            "display_height_px": self.display_height,
            "display_number": self.display_num,
        }

    async def _run_command(self, cmd: list[str]) -> tuple[str, str, int]:
        """Run a command, optionally in Docker container."""
        if self.docker_container:
            cmd = ["docker", "exec", self.docker_container] + cmd

        env_cmd = ["env", f"DISPLAY=:{self.display_num}"] + cmd

        process = await asyncio.create_subprocess_exec(
            *env_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return stdout.decode(), stderr.decode(), process.returncode or 0

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a computer action."""
        action: ActionType = kwargs.get("action", "screenshot")

        try:
            if action == "screenshot":
                return await self._screenshot()
            elif action == "left_click":
                return await self._click(kwargs.get("coordinate"), button=1)
            elif action == "right_click":
                return await self._click(kwargs.get("coordinate"), button=3)
            elif action == "middle_click":
                return await self._click(kwargs.get("coordinate"), button=2)
            elif action == "double_click":
                return await self._click(kwargs.get("coordinate"), button=1, clicks=2)
            elif action == "triple_click":
                return await self._click(kwargs.get("coordinate"), button=1, clicks=3)
            elif action == "left_click_drag":
                return await self._drag(
                    kwargs.get("start_coordinate"),
                    kwargs.get("end_coordinate"),
                )
            elif action == "type":
                return await self._type(kwargs.get("text", ""))
            elif action == "key":
                return await self._key(kwargs.get("key", ""))
            elif action == "mouse_move":
                return await self._mouse_move(kwargs.get("coordinate"))
            elif action == "scroll":
                return await self._scroll(
                    kwargs.get("coordinate"),
                    kwargs.get("scroll_direction", "down"),
                    kwargs.get("scroll_amount", 3),
                )
            elif action == "wait":
                return await self._wait(kwargs.get("duration", 1))
            elif action == "left_mouse_down":
                return await self._mouse_button("mousedown", 1)
            elif action == "left_mouse_up":
                return await self._mouse_button("mouseup", 1)
            elif action == "hold_key":
                return await self._hold_key(
                    kwargs.get("key", ""),
                    kwargs.get("duration", 0.5),
                )
            else:
                return ToolResult(error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(error=f"Error executing {action}: {str(e)}")

    async def _screenshot(self) -> ToolResult:
        """Take a screenshot of the current display."""
        screenshot_path = "/tmp/screenshot.png"

        # Create directory and take screenshot inside the container
        mkdir_cmd = ["mkdir", "-p", "/tmp"]
        await self._run_command(mkdir_cmd)

        # Use scrot to take screenshot
        cmd = ["scrot", "-o", screenshot_path]
        stdout, stderr, returncode = await self._run_command(cmd)

        if returncode != 0:
            return ToolResult(error=f"Screenshot failed: {stderr}")

        # Read the screenshot from inside the container
        if self.docker_container:
            # Use docker exec cat to read the file and base64 encode it
            read_cmd = ["docker", "exec", self.docker_container, "base64", screenshot_path]
            process = await asyncio.create_subprocess_exec(
                *read_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await process.communicate()
            if process.returncode != 0:
                return ToolResult(error=f"Failed to read screenshot: {stderr_bytes.decode()}")
            # Remove newlines from base64 output
            image_data = stdout_bytes.decode().replace("\n", "")
            return ToolResult(base64_image=image_data)
        else:
            # Local file read
            try:
                with open(screenshot_path, "rb") as f:
                    image_data = base64.standard_b64encode(f.read()).decode("utf-8")
                return ToolResult(base64_image=image_data)
            except FileNotFoundError:
                return ToolResult(error="Screenshot file not found")

    async def _click(
        self,
        coordinate: list[int] | None,
        button: int = 1,
        clicks: int = 1,
    ) -> ToolResult:
        """Click at the specified coordinates."""
        if not coordinate or len(coordinate) != 2:
            return ToolResult(error="Invalid coordinate format")

        x, y = coordinate

        # Validate coordinates
        if not (0 <= x < self.display_width and 0 <= y < self.display_height):
            return ToolResult(
                error=f"Coordinates ({x}, {y}) outside display bounds "
                f"({self.display_width}x{self.display_height})"
            )

        # Move mouse and click
        cmd = [
            "xdotool",
            "mousemove",
            str(x),
            str(y),
            "click",
            "--repeat",
            str(clicks),
            str(button),
        ]
        stdout, stderr, returncode = await self._run_command(cmd)

        if returncode != 0:
            return ToolResult(error=f"Click failed: {stderr}")

        return ToolResult(output=f"Clicked at ({x}, {y})")

    async def _drag(
        self,
        start_coordinate: list[int] | None,
        end_coordinate: list[int] | None,
    ) -> ToolResult:
        """Drag from start to end coordinates."""
        if not start_coordinate or len(start_coordinate) != 2:
            return ToolResult(error="Invalid start coordinate format")
        if not end_coordinate or len(end_coordinate) != 2:
            return ToolResult(error="Invalid end coordinate format")

        x1, y1 = start_coordinate
        x2, y2 = end_coordinate

        # Move to start, press, move to end, release
        cmd = [
            "xdotool",
            "mousemove",
            str(x1),
            str(y1),
            "mousedown",
            "1",
            "mousemove",
            str(x2),
            str(y2),
            "mouseup",
            "1",
        ]
        stdout, stderr, returncode = await self._run_command(cmd)

        if returncode != 0:
            return ToolResult(error=f"Drag failed: {stderr}")

        return ToolResult(output=f"Dragged from ({x1}, {y1}) to ({x2}, {y2})")

    async def _type(self, text: str) -> ToolResult:
        """Type text using xdotool."""
        if not text:
            return ToolResult(error="No text provided to type")

        cmd = ["xdotool", "type", "--clearmodifiers", "--", text]
        stdout, stderr, returncode = await self._run_command(cmd)

        if returncode != 0:
            return ToolResult(error=f"Type failed: {stderr}")

        return ToolResult(output=f"Typed {len(text)} characters")

    async def _key(self, key: str) -> ToolResult:
        """Press a key or key combination."""
        if not key:
            return ToolResult(error="No key provided")

        # Convert common key names to xdotool format
        key_mapping = {
            "return": "Return",
            "enter": "Return",
            "tab": "Tab",
            "escape": "Escape",
            "esc": "Escape",
            "backspace": "BackSpace",
            "delete": "Delete",
            "space": "space",
            "up": "Up",
            "down": "Down",
            "left": "Left",
            "right": "Right",
            "home": "Home",
            "end": "End",
            "pageup": "Page_Up",
            "pagedown": "Page_Down",
        }

        # Handle key combinations like "ctrl+c"
        keys = key.split("+")
        xdotool_keys = []
        for k in keys:
            k_lower = k.lower().strip()
            if k_lower in key_mapping:
                xdotool_keys.append(key_mapping[k_lower])
            elif k_lower in ("ctrl", "control"):
                xdotool_keys.append("ctrl")
            elif k_lower == "alt":
                xdotool_keys.append("alt")
            elif k_lower in ("shift", "super", "meta"):
                xdotool_keys.append(k_lower)
            else:
                xdotool_keys.append(k)

        key_combo = "+".join(xdotool_keys)
        cmd = ["xdotool", "key", "--clearmodifiers", key_combo]
        stdout, stderr, returncode = await self._run_command(cmd)

        if returncode != 0:
            return ToolResult(error=f"Key press failed: {stderr}")

        return ToolResult(output=f"Pressed key: {key}")

    async def _mouse_move(self, coordinate: list[int] | None) -> ToolResult:
        """Move mouse to coordinates without clicking."""
        if not coordinate or len(coordinate) != 2:
            return ToolResult(error="Invalid coordinate format")

        x, y = coordinate
        cmd = ["xdotool", "mousemove", str(x), str(y)]
        stdout, stderr, returncode = await self._run_command(cmd)

        if returncode != 0:
            return ToolResult(error=f"Mouse move failed: {stderr}")

        return ToolResult(output=f"Moved mouse to ({x}, {y})")

    async def _scroll(
        self,
        coordinate: list[int] | None,
        direction: ScrollDirection,
        amount: int,
    ) -> ToolResult:
        """Scroll at the specified coordinates."""
        # Move to coordinates first if provided
        if coordinate and len(coordinate) == 2:
            x, y = coordinate
            move_cmd = ["xdotool", "mousemove", str(x), str(y)]
            await self._run_command(move_cmd)

        # Map direction to xdotool button
        button_map = {
            "up": "4",
            "down": "5",
            "left": "6",
            "right": "7",
        }
        button = button_map.get(direction, "5")

        cmd = ["xdotool", "click", "--repeat", str(amount), button]
        stdout, stderr, returncode = await self._run_command(cmd)

        if returncode != 0:
            return ToolResult(error=f"Scroll failed: {stderr}")

        return ToolResult(output=f"Scrolled {direction} by {amount}")

    async def _wait(self, duration: float) -> ToolResult:
        """Wait for the specified duration."""
        await asyncio.sleep(duration)
        return ToolResult(output=f"Waited {duration} seconds")

    async def _mouse_button(self, action: str, button: int) -> ToolResult:
        """Press or release mouse button."""
        cmd = ["xdotool", action, str(button)]
        stdout, stderr, returncode = await self._run_command(cmd)

        if returncode != 0:
            return ToolResult(error=f"Mouse {action} failed: {stderr}")

        return ToolResult(output=f"Mouse button {button} {action}")

    async def _hold_key(self, key: str, duration: float) -> ToolResult:
        """Hold a key for a specified duration."""
        cmd_down = ["xdotool", "keydown", key]
        await self._run_command(cmd_down)

        await asyncio.sleep(duration)

        cmd_up = ["xdotool", "keyup", key]
        stdout, stderr, returncode = await self._run_command(cmd_up)

        if returncode != 0:
            return ToolResult(error=f"Hold key failed: {stderr}")

        return ToolResult(output=f"Held key {key} for {duration}s")
