# Claude Agent

Telegram bot that receives natural language instructions and executes them on a GitHub repository using the Claude Code CLI — all running inside Docker.

## How it works

1. You send a message to your Telegram bot
2. The bot clones (or updates) the target repository inside the container
3. Claude Code executes the instruction autonomously
4. Output is returned via Telegram (truncated at 3800 chars if needed)

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
| `/cancel` | Cancel the running task and clear the queue |
| `/reset` | Clear conversation history and start a new session |
| `/mode` | Show current model; `/mode claude` or `/mode ollama` to switch |
| `/help` | Usage guide with examples |

Or send any natural language instruction directly:

- `Create a fibonacci function in Python with tests`
- `Refactor main.py using dataclasses`
- `Add error handling to utils.py`
- `Write documentation for all functions`

You can send multiple instructions without waiting — they are queued and run one after another. Use `/tasks` to monitor progress and `/cancel` to abort.

## Portability

The container runs identically on:

- Laptop (Mac / Linux / Windows with Docker Desktop)
- VPS (Hetzner, DigitalOcean, etc.)
- Any machine with Docker installed

## Ollama fallback (local LLM)

When Claude Pro tokens are exhausted, the bot can automatically fall back to a local model running via [Ollama](https://ollama.com). The default model is `qwen2.5-coder:14b`, which runs entirely on GPU and requires no internet connection.

### Requirements

- NVIDIA GPU with CUDA drivers for WSL2 (verify with `nvidia-smi`)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

```bash
# Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Verify GPU passthrough works:

```bash
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

> **Troubleshooting:** If `nvidia-smi` is not found inside WSL2, the issue is at the Windows driver level — install the NVIDIA Game Ready or Studio driver (version 515+) on the Windows host. This driver includes WSL2 GPU support automatically; no separate Linux driver installation is needed.

### Enable fallback

1. Start the stack (Ollama starts automatically as a sidecar):

```bash
docker compose up -d
```

2. Pull the model inside the Ollama container (one-time, ~8 GB):

```bash
docker compose exec ollama ollama pull qwen2.5-coder:14b
```

3. Enable the fallback in `.env`:

```
OLLAMA_FALLBACK=true
```

4. Restart the bot:

```bash
docker compose restart claude-agent
```

From this point on, if Claude Code exits with an error (e.g. quota exceeded), the instruction is automatically re-sent to Ollama and the reply is tagged with the model name.

> **Note:** Ollama is a plain language model — it can suggest and explain code but cannot autonomously read/write files or run git commands like Claude Code CLI does.

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