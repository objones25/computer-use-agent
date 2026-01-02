# Computer Use Agent

A Python-based autonomous computer control agent using Claude's Computer Use API. This agent can interact with a virtual desktop environment to perform complex tasks like web browsing, form filling, and handling authentication flows with human-in-the-loop capabilities.

## Features

- **Claude Computer Use API**: Full desktop automation via Claude's computer use beta API (computer_20250124)
- **Automated CAPTCHA Solving**: CapMonster Cloud integration for solving various CAPTCHA types
- **Human-in-the-Loop**: CLI prompts for credentials, 2FA codes, and manual interventions
- **Docker Environment**: Isolated containerized desktop with Firefox, Xvfb, and automation tools
- **Optional VNC**: Live viewing of the virtual desktop via VNC client

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Host Machine                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                 Python Application                       ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ ││
│  │  │ Agent Loop   │  │ Tool Handler │  │ CLI Interface │ ││
│  │  │ (Claude API) │  │ (Actions)    │  │ (Human Input) │ ││
│  │  └──────────────┘  └──────────────┘  └───────────────┘ ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Docker Container                            ││
│  │  ┌─────────┐  ┌──────────┐  ┌────────────────────────┐ ││
│  │  │ Xvfb    │  │ Browser  │  │ VNC Server (optional)  │ ││
│  │  │ Display │  │ (Firefox)│  │ for live viewing       │ ││
│  │  └─────────┘  └──────────┘  └────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.11+
- Docker Desktop
- [uv](https://docs.astral.sh/uv/) package manager
- Anthropic API key
- CapMonster Cloud API key (optional, for CAPTCHA solving)

## Installation

```bash
# Clone the repository
git clone https://github.com/objones25/computer-use-agent.git
cd computer-use-agent

# Install dependencies with uv
uv sync

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys
```

## Configuration

Create a `.env` file with the following variables:

```bash
# Required
ANTHROPIC_API_KEY=your-anthropic-api-key

# Optional - for automated CAPTCHA solving
CAPMONSTER_API_KEY=your-capmonster-api-key

# Display settings (optional)
DISPLAY_WIDTH=1024
DISPLAY_HEIGHT=768

# Human-in-the-loop mode (optional)
# Options: always_confirm, sensitive_only, minimal
HUMAN_LOOP_MODE=sensitive_only
```

## Usage

### Start the Docker Environment

```bash
# Start the container in background
docker compose up -d

# Optional: Enable VNC for live viewing
ENABLE_VNC=true docker compose up -d

# View container logs
docker logs -f computer-use-desktop
```

### Run the Agent

```bash
# Run with a task
uv run computer-use-agent "Go to amazon.com and search for wireless headphones"

# Or use the Python module directly
uv run python -m computer_use_agent "Take a screenshot of the desktop"
```

### Connect via VNC (Optional)

If VNC is enabled, connect with any VNC client to `localhost:5900` (no password required).

## Project Structure

```
computer-use-agent/
├── pyproject.toml              # Project dependencies and metadata
├── Dockerfile                  # Container environment setup
├── docker-compose.yml          # Container orchestration
├── docker-entrypoint.sh        # Container startup script
├── .env.example                # Environment variables template
├── src/
│   └── computer_use_agent/
│       ├── __init__.py
│       ├── main.py             # CLI entry point
│       ├── agent.py            # Main agent loop
│       ├── config.py           # Configuration management
│       ├── captcha.py          # CAPTCHA solving integration
│       ├── human_loop.py       # Human-in-the-loop handlers
│       └── tools/
│           ├── __init__.py
│           ├── base.py         # Base tool interface
│           ├── computer.py     # Computer use tool (screenshot, click, type)
│           └── bash.py         # Bash command execution
└── tests/
    └── __init__.py
```

## Human-in-the-Loop Modes

| Mode | Description |
|------|-------------|
| `always_confirm` | Prompts for confirmation before every action |
| `sensitive_only` | Only prompts for login, payment, and sensitive actions |
| `minimal` | Only prompts when Claude explicitly requests human input |

### Example Login Flow

1. Agent navigates to login page
2. Agent detects username field
3. **CLI Prompt**: "Enter your username/email:"
4. Agent types the provided username
5. Agent detects password field
6. **CLI Prompt**: "Enter your password:" (hidden input)
7. Agent types the password and submits
8. If CAPTCHA appears → Automated solving via CapMonster
9. If 2FA required → **CLI Prompt**: "Enter 2FA code:"
10. Agent completes login

## CAPTCHA Solving

The agent supports automated CAPTCHA solving via CapMonster Cloud:

- **Amazon WAF**: AWS WAF challenges
- **reCAPTCHA v2/v3**: Google reCAPTCHA
- **Cloudflare Turnstile**: Cloudflare challenges
- **Image CAPTCHAs**: Text recognition from images

If automated solving fails, the user is prompted for manual input.

## Tools

### Computer Tool (`computer_20250124`)

| Action | Description |
|--------|-------------|
| `screenshot` | Capture the current display |
| `left_click` | Click at coordinates |
| `right_click` | Right-click at coordinates |
| `double_click` | Double-click at coordinates |
| `type` | Type text |
| `key` | Press key combination (e.g., "ctrl+c") |
| `scroll` | Scroll up/down/left/right |
| `mouse_move` | Move cursor to coordinates |
| `left_click_drag` | Drag from start to end coordinates |

### Bash Tool (`bash_20250124`)

Execute shell commands inside the container for tasks like:
- Opening applications
- File operations
- System queries

## API Reference

This agent uses Claude's Computer Use API with:
- **Model**: `claude-sonnet-4-5` (configurable)
- **Tool Version**: `computer_20250124`
- **Beta Flag**: `computer-use-2025-01-24`

## Troubleshooting

### Container keeps restarting

Check the entrypoint script permissions:
```bash
chmod +x docker-entrypoint.sh
docker compose build --no-cache
```

### Screenshot not working

Ensure the container is running and Xvfb is started:
```bash
docker logs computer-use-desktop
```

### VNC connection refused

Make sure VNC is enabled:
```bash
ENABLE_VNC=true docker compose up -d
```

## License

MIT

## Acknowledgments

- [Anthropic Claude](https://www.anthropic.com/) - Computer Use API
- [CapMonster Cloud](https://capmonster.cloud/) - CAPTCHA solving service
