# Claude Agent

Telegram bot that receives natural language instructions and executes them on a GitHub repository using the Claude Code CLI — all running inside Docker.

## How it works

1. You send a message to your Telegram bot
2. The bot clones (or updates) the target repository inside the container
3. Claude Code executes the instruction with full conversation context
4. The response is returned via Telegram (truncated at 3800 chars if needed)

Conversation context is accumulated in a `context.md` file on the persistent volume and prepended to every Claude Code invocation, so Claude remembers the full session. Use `/compact` to ask Claude to condense the accumulated context, and `/reset` to start fresh.

Tasks run in the background with no hard timeout — use `/cancel` to abort. Claude Code runs with `--dangerously-skip-permissions` so it can operate fully autonomously inside the container. Multiple instructions can be sent at once: they are queued and executed sequentially. Every 60 seconds a heartbeat message confirms the task is still running.

## Requirements

- Docker + Docker Compose
- Claude Pro account (OAuth token — **not** an API key)
- Telegram bot token (via [@BotFather](https://t.me/BotFather))
- GitHub Personal Access Token with `repo` scope
- [Poetry](https://python-poetry.org) (only needed on the host to update dependencies)

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR-USERNAME/claude-agent.git
cd claude-agent
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your values:

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID (get it from [@userinfobot](https://t.me/userinfobot)) |
| `CLAUDE_CODE_OAUTH_TOKEN` | OAuth token from your Claude Pro subscription |
| `GITHUB_TOKEN` | Personal Access Token with `repo` scope |
| `GITHUB_USERNAME` | Your GitHub username |
| `REPO_NAME` | Repository the bot will work on (default: `claude-agent`) |

> Never commit `.env` to GitHub.

### 3. Get the Claude OAuth token

```bash
docker compose run --rm claude-agent claude setup-token
```

Copy the token into `.env` as `CLAUDE_CODE_OAUTH_TOKEN`.

### 4. Launch

```bash
docker compose up -d
```

To rebuild after code changes:

```bash
docker compose up -d --build
```

### Updating dependencies

```bash
# Add a package
poetry add <package>

# Update all packages
poetry update

# Always commit pyproject.toml and poetry.lock together
```

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Start the bot and show welcome message |
| `/status` | Current workspace branch and pending changes |
| `/log` | Last 5 commits |
| `/tasks` | Show running task (with elapsed time) and pending queue |
| `/cancel` | Cancel the running task and clear the entire queue |
| `/cancel <id>` | Remove a specific task from the queue (use the ID shown by `/tasks`) |
| `/compact` | Ask Claude to condense the accumulated conversation context |
| `/reset` | Clear the conversation context and start a new session |
| `/help` | Usage guide with examples |

Or send any natural language instruction directly:

- `Create a fibonacci function in Python with tests`
- `Refactor main.py using dataclasses`
- `Add error handling to utils.py`
- `Write documentation for all functions`

You can send multiple instructions without waiting — they are queued and run one after another. Use `/tasks` to monitor progress, `/cancel <id>` to drop a specific pending task, or `/cancel` to abort everything.

## Container environment

The container runs as a non-root user (`claude`) with passwordless `sudo`, so Claude Code can install system packages during task execution:

```
sudo apt install <package>
```

The following build toolchains are pre-installed:

| Language | Tools |
|---|---|
| C / C++ | `gcc`, `g++`, `clang`, `lld`, `cmake`, `gdb`, `libssl-dev` |
| Rust | `rustc`, `cargo`, `rustfmt` |
| Python | system Python 3 + Poetry |
| Node.js | Node 20 (required by Claude Code CLI) |

If an NVIDIA GPU is available, it is automatically passed through to the container via the NVIDIA Container Toolkit.

## Portability

The container runs identically on:

- Laptop (Mac / Linux / Windows with Docker Desktop)
- VPS (Hetzner, DigitalOcean, etc.)
- Any machine with Docker installed

## Notes for WSL2 users

On WSL2 (Ubuntu 24.04), use `docker compose` (the V2 plugin) instead of `docker-compose` (the legacy Python tool). The legacy version 1.29.2 is incompatible with recent Docker Engine versions and will produce `ContainerConfig` or `KeyError: 'id'` errors.

Install the plugin if not already available:

```bash
sudo apt-get install docker-compose-v2
```

Verify the installation:

```bash
docker compose version
```

All commands in this guide use `docker compose` (with a space).
