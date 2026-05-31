# Claude Agent 🤖

Telegram bot that executes natural language instructions on your repository using the Claude Code CLI.

## Quick Setup

### 1. Clone the repo
```bash
git clone https://github.com/YOUR-USERNAME/claude-agent.git
cd claude-agent
```

### 2. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Launch with Docker
```bash
docker compose up -d
```

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Start the bot |
| `/status` | Workspace status |
| `/log` | Last 5 commits |
| `/help` | Quick guide |

Or send any natural language instruction:
- `Create a fibonacci function with tests`
- `Refactor main.py`
- `Add documentation to all functions`

## Requirements

- Docker + Docker Compose
- Anthropic account (Pro plan or API key)
- Telegram bot (via @BotFather)
- GitHub Personal Access Token

## Portability

The container runs identically on:
- Laptop (Mac/Linux/Windows with Docker Desktop)
- VPS (Hetzner, DigitalOcean, etc.)
- Any machine with Docker installed
