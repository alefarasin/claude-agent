# AGENTS.md

This file provides context to AI agents (including Claude Code) operating inside this repository.

## Project overview

Claude Agent is a Telegram bot that receives natural language instructions and executes them autonomously on a target GitHub repository using the Claude Code CLI. The bot manages a per-chat task queue, maintains conversation history with automatic compaction, and runs entirely inside Docker.

## Repository structure

```
claude-agent/
├── bot.py              # Telegram bot — task queue, history, Claude execution
├── entrypoint.sh       # Container init: git credentials, OAuth token check
├── Dockerfile          # Ubuntu 24.04 + Node.js 20 + Claude Code CLI + Python venv
├── docker-compose.yml  # Single service, named volume for workspace persistence
├── requirements.txt    # python-telegram-bot, python-dotenv
├── .env.example        # Environment variable template
└── CLAUDE.md           # Claude Code project guidance (references this file)
```

## Architecture

```
Telegram user
     │  natural language instruction
     ▼
bot.py — handle_message()
     │  enqueue_task() + ensure_worker()
     ▼
chat_worker()  ─── asyncio background task, one per active chat
     │
     ├── setup_workspace()     clone / pull GitHub repo into ~/workspace/<REPO_NAME>
     ├── compact_history_if_needed()   summarise old turns via claude --print
     ├── _heartbeat()          sends "still running" every 60s
     └── run_claude_code()
              │
              └── _run_claude()   subprocess: claude --print --dangerously-skip-permissions
```

Key design decisions:
- **No hard timeout** on tasks — long-running operations are supported; use `/cancel` to abort.
- **Sequential execution per chat** — tasks from the same chat run one at a time to avoid race conditions on the workspace.
- **In-memory state** — history and task queue are not persisted; a container restart clears them.
- **Single workspace per bot instance** — `WORKSPACE_DIR = ~/workspace/<REPO_NAME>` is shared across all tasks.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Token from @BotFather |
| `TELEGRAM_CHAT_ID` | ✅ | Authorised chat ID (only this chat can use the bot) |
| `CLAUDE_CODE_OAUTH_TOKEN` | ✅ | OAuth token from Claude Pro subscription (not an API key) |
| `GITHUB_TOKEN` | ✅ | Personal Access Token with `repo` scope |
| `GITHUB_USERNAME` | ✅ | GitHub username used to clone the repo |
| `REPO_NAME` | ❌ | Repository to work on (default: `claude-agent`) |

## Build and run

```bash
# First run — obtain the OAuth token
docker compose run --rm claude-agent claude setup-token
# Paste the token into .env as CLAUDE_CODE_OAUTH_TOKEN

# Start the bot
docker compose up -d --build

# View logs
docker compose logs -f

# Stop and remove the workspace volume (full reset)
docker compose down -v
```

## Telegram commands

| Command | Handler | Description |
|---|---|---|
| `/start` | `start()` | Welcome message |
| `/status` | `status()` | Git status of the workspace |
| `/log` | `log()` | Last 5 commits |
| `/tasks` | `tasks_cmd()` | Running task (elapsed time) + pending queue |
| `/cancel` | `cancel_cmd()` | Cancel running task and clear queue |
| `/reset` | `reset()` | Clear conversation history |
| `/help` | `help_command()` | Usage guide |

## Agent guidelines

When Claude Code operates inside this repository via the bot:

- **Commit all changes** after completing a task. Use concise, descriptive commit messages.
- **Never modify `.env`** — credentials must not be touched or logged.
- **Work inside `WORKSPACE_DIR`** (`~/workspace/<REPO_NAME>`). Do not write outside this directory.
- **Prefer editing existing files** over creating new ones unless the task explicitly requires new files.
- **Run tests if present** before committing. If no test suite exists, verify the change manually where possible.
- **Keep commits atomic** — one logical change per commit.

## History and compaction

Conversation history is stored in `conversation_history: dict[int, list[dict]]` keyed by `chat_id`. Each entry has `role` (`user`, `assistant`, or `system`) and `content`.

When `len(history) > MAX_HISTORY_LEN` (default 20), `compact_history_if_needed()` summarises the oldest `N - HISTORY_KEEP_RECENT` messages via `claude --print` and replaces them with a single `system` summary message. The most recent `HISTORY_KEEP_RECENT` (default 6) messages are always kept verbatim.

## Constraints

- Only one chat ID is authorised (`ALLOWED_CHAT_ID`). All other senders are silently ignored.
- The subprocess running `claude` is killed via `process.kill()` when a task is cancelled (`CancelledError`).
- The heartbeat interval is `HEARTBEAT_INTERVAL = 60` seconds and is configurable at module level.
