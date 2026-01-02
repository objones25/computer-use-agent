"""Configuration management for the computer use agent."""

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv


class HumanLoopMode(Enum):
    """Mode for human-in-the-loop interactions."""

    ALWAYS_CONFIRM = "always_confirm"  # Confirm every action
    SENSITIVE_ONLY = "sensitive_only"  # Only prompt for login/payment actions
    MINIMAL = "minimal"  # Only prompt when explicitly requested


@dataclass
class Config:
    """Configuration for the computer use agent."""

    # API Keys
    anthropic_api_key: str
    capmonster_api_key: str

    # Display settings
    display_width: int = 1024
    display_height: int = 768

    # Human-in-the-loop settings
    human_loop_mode: HumanLoopMode = HumanLoopMode.SENSITIVE_ONLY

    # Model settings
    model: str = "claude-sonnet-4-5"
    max_tokens: int = 4096

    # Tool settings
    tool_version: str = "computer_20250124"
    beta_flag: str = "computer-use-2025-01-24"

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Config":
        """Load configuration from environment variables."""
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        capmonster_key = os.getenv("CAPMONSTER_API_KEY", "")

        human_loop_str = os.getenv("HUMAN_LOOP_MODE", "sensitive_only")
        try:
            human_loop_mode = HumanLoopMode(human_loop_str)
        except ValueError:
            human_loop_mode = HumanLoopMode.SENSITIVE_ONLY

        return cls(
            anthropic_api_key=anthropic_key,
            capmonster_api_key=capmonster_key,
            display_width=int(os.getenv("DISPLAY_WIDTH", "1024")),
            display_height=int(os.getenv("DISPLAY_HEIGHT", "768")),
            human_loop_mode=human_loop_mode,
        )
