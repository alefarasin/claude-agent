# Claude Agent

Telegram bot that receives natural language instructions and executes them on a GitHub repository using the Claude Code CLI — all running inside Docker.

## How it works

1. You send a message to your Telegram bot
2. The bot clones (or updates) the target repository inside the container
3. Claude Code executes the instruction autonomously
4. Output is returned via Telegram (truncated at 3800 chars if needed)

Tasks have a 5-minute timeout. Claude Code runs with `--dangerously-skip-permissions` so it can operate fully autonomously inside the container.

## Requirements

- Docker + Docker Compose
- Claude Pro account (OAuth token — **not** an API key)
- Telegram bot token (via [@BotFather](https://t.me/BotFather))
- GitHub Personal Access Token with `repo` scope

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

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Start the bot and show welcome message |
| `/status` | Current workspace branch and pending changes |
| `/log` | Last 5 commits |
| `/help` | Usage guide with examples |

Or send any natural language instruction directly:

- `Create a fibonacci function in Python with tests`
- `Refactor main.py using dataclasses`
- `Add error handling to utils.py`
- `Write documentation for all functions`

## Portability

The container runs identically on:

- Laptop (Mac / Linux / Windows with Docker Desktop)
- VPS (Hetzner, DigitalOcean, etc.)
- Any machine with Docker installed