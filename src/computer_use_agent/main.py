"""Main entry point for the computer use agent."""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .agent import ComputerUseAgent
from .config import Config, HumanLoopMode


console = Console()


def check_docker_running() -> bool:
    """Check if Docker is running and the container exists."""
    try:
        result = subprocess.run(
            ["docker", "ps", "-q", "-f", "name=computer-use-desktop"],
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())
    except FileNotFoundError:
        return False


def start_docker_container() -> bool:
    """Start the Docker container if not running."""
    console.print("[yellow]Docker container not running. Starting...[/yellow]")
    try:
        subprocess.run(
            ["docker-compose", "up", "-d"],
            check=True,
            capture_output=True,
        )
        # Wait for container to be ready
        import time
        time.sleep(5)
        return check_docker_running()
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to start container: {e}[/red]")
        return False
    except FileNotFoundError:
        console.print("[red]docker-compose not found. Please install Docker.[/red]")
        return False


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Computer Use Agent - Control a computer with Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a simple task
  computer-use-agent "Open Firefox and go to google.com"

  # Login to a website
  computer-use-agent "Go to amazon.com and log into my account"

  # With custom settings
  computer-use-agent --mode always_confirm "Make a purchase on amazon"
""",
    )

    parser.add_argument(
        "task",
        nargs="?",
        help="The task to perform (can also be provided interactively)",
    )

    parser.add_argument(
        "--mode",
        choices=["always_confirm", "sensitive_only", "minimal"],
        default=None,
        help="Human-in-the-loop mode (overrides env variable)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=50,
        help="Maximum number of agent loop iterations (default: 50)",
    )

    parser.add_argument(
        "--no-docker-check",
        action="store_true",
        help="Skip Docker container check",
    )

    parser.add_argument(
        "--container",
        default="computer-use-desktop",
        help="Docker container name (default: computer-use-desktop)",
    )

    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Path to .env file (default: .env in current directory)",
    )

    return parser.parse_args()


async def run_agent(
    task: str,
    config: Config,
    container: str,
    max_iterations: int,
) -> None:
    """Run the agent with the given task."""
    agent = ComputerUseAgent(config=config, docker_container=container)

    console.print(Panel(
        f"[bold]Task:[/bold] {task}\n"
        f"[dim]Model: {config.model}[/dim]\n"
        f"[dim]Mode: {config.human_loop_mode.value}[/dim]",
        title="[bold blue]Computer Use Agent[/bold blue]",
        border_style="blue",
    ))

    try:
        result = await agent.run(task, max_iterations=max_iterations)
        console.print("\n")
        console.print(Panel(
            result,
            title="[bold green]Task Complete[/bold green]",
            border_style="green",
        ))
    except KeyboardInterrupt:
        console.print("\n[yellow]Task cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise


def interactive_task_prompt() -> str | None:
    """Prompt the user for a task interactively."""
    console.print(Panel(
        "Enter the task you want the agent to perform.\n"
        "Examples:\n"
        "  - Open Firefox and go to google.com\n"
        "  - Log into my Amazon account\n"
        "  - Search for 'python tutorials' on YouTube",
        title="[bold blue]Computer Use Agent[/bold blue]",
        border_style="blue",
    ))

    try:
        from rich.prompt import Prompt
        task = Prompt.ask("\n[bold]Task[/bold]")
        return task if task.strip() else None
    except KeyboardInterrupt:
        return None


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Load configuration
    try:
        config = Config.from_env(args.env_file)
    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print("[dim]Make sure you have set ANTHROPIC_API_KEY in your .env file[/dim]")
        sys.exit(1)

    # Override mode if specified
    if args.mode:
        config.human_loop_mode = HumanLoopMode(args.mode)

    # Check Docker container
    if not args.no_docker_check:
        if not check_docker_running():
            if not start_docker_container():
                console.print(
                    "[red]Please start the Docker container first:[/red]\n"
                    "  docker-compose up -d"
                )
                sys.exit(1)
        console.print("[green]Docker container is running[/green]")

    # Get task
    task = args.task
    if not task:
        task = interactive_task_prompt()
        if not task:
            console.print("[yellow]No task provided. Exiting.[/yellow]")
            sys.exit(0)

    # Run the agent
    asyncio.run(run_agent(
        task=task,
        config=config,
        container=args.container,
        max_iterations=args.max_iterations,
    ))


if __name__ == "__main__":
    main()
