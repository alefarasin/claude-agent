# AGENTS.md

This file provides context to AI agents (including Claude Code) operating inside this repository.

## Project overview

Claude Agent is a Telegram bot that receives natural language instructions and executes them autonomously on a target GitHub repository using the Claude Code CLI. The bot manages a per-chat task queue and maintains conversation context via a persistent file, running entirely inside Docker.

## Repository structure

```
claude-agent/
├── bot.py                  # Entry point: builds Application, registers handlers
├── config.py               # Config dataclass — all env vars validated at startup
├── agent/
│   ├── executor.py         # run(), run_raw(), context file management
│   ├── queue.py            # AgentTask, _worker, heartbeat, enqueue/cancel/remove
│   └── workspace.py        # setup(), pull() — async git workspace management
├── handlers/
│   ├── commands.py         # /start /status /log /tasks /cancel /compact /reset /help
│   └── messages.py         # handle() — incoming text messages
├── pyproject.toml          # Poetry dependencies and scripts
├── poetry.lock             # Locked dependency tree (always committed)
├── entrypoint.sh           # Container init: git credentials, OAuth token check
├── Dockerfile              # Ubuntu 24.04 + Node.js 20 + Claude Code + Poetry
├── docker-compose.yml      # Single service, named volume for workspace persistence
├── .env.example            # Environment variable template
└── CLAUDE.md               # Claude Code project guidance (references this file)
```

## Architecture

```
Telegram user
     │  natural language instruction
     ▼
handlers/messages.py — handle()
     │  agent/queue.enqueue() + ensure_worker()
     ▼
agent/queue._worker()  ── asyncio background task, one per active chat
     │
     ├── agent/workspace.setup()     async clone / pull GitHub repo into ~/workspace/<REPO_NAME>
     ├── agent/queue._heartbeat()    sends "still running" every 60s
     └── agent/executor.run()
              │  reads context.md, prepends it to instruction, calls run_raw()
              │  appends instruction + response to context.md
              └── agent/executor.run_raw()
                       └── subprocess: claude --print --dangerously-skip-permissions
```

Key design decisions:
- **No hard timeout** on tasks — long-running operations are supported; use `/cancel` to abort.
- **Sequential execution per chat** — tasks from the same chat run one at a time to avoid workspace race conditions.
- **File-based conversation context** — `executor.py` maintains `context.md` in the workspace volume (at `~/workspace/context.md`, outside the repo). The file survives container restarts and is prepended to every Claude invocation. `/compact` asks Claude to condense it; `/reset` deletes it.
- **Config injected via `bot_data`** — `context.bot_data["cfg"]` carries the `Config` instance into every handler, avoiding global state.
- **All git operations are async** — `workspace.setup()` and `workspace.pull()` use `asyncio.create_subprocess_exec` to avoid blocking the PTB polling event loop.
- **Non-root user with sudo** — the container runs as user `claude` (required for `--dangerously-skip-permissions`) with passwordless `sudo`, allowing Claude Code to install system packages during task execution.
- **GPU passthrough** — if an NVIDIA GPU is present, it is forwarded to the container via `deploy.resources.reservations.devices` (`count: all`); the container starts normally on machines without a GPU.

## Container environment

The following toolchains are pre-installed in the image:

| Language | Tools |
|---|---|
| C / C++ | `gcc`, `g++`, `clang`, `lld`, `cmake`, `gdb`, `libssl-dev`, `pkg-config` |
| Rust | `rustc`, `cargo`, `rustfmt` |
| Python | system Python 3 + Poetry |
| Node.js | Node 20 (required by Claude Code CLI) |

Additional packages can be installed at runtime with `sudo apt install <package>`.

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

### Updating dependencies (requires Poetry on host)

```bash
poetry add <package>       # add a dependency
poetry update              # update all
# always commit pyproject.toml and poetry.lock together
```

## Telegram commands

| Command | Handler | Description |
|---|---|---|
| `/start` | `commands.start` | Welcome message |
| `/status` | `commands.status` | Git status of the workspace |
| `/log` | `commands.log` | Last 5 commits |
| `/tasks` | `commands.tasks` | Running task (elapsed time) + pending queue |
| `/cancel` | `commands.cancel` | Cancel running task and clear the entire queue |
| `/cancel <id>` | `commands.cancel` | Remove a specific pending task by ID |
| `/compact` | `commands.compact_cmd` | Ask Claude to condense the conversation context |
| `/reset` | `commands.reset` | Delete context.md and start a new session |
| `/help` | `commands.help_cmd` | Usage guide |

## Agent guidelines

When Claude Code operates inside this repository via the bot:

- **Commit all changes** after completing a task. Use concise, descriptive commit messages.
- **Never modify `.env`** — credentials must not be touched or logged.
- **Work inside `cfg.workspace_dir`** (`~/workspace/<REPO_NAME>`). Do not write outside this directory.
- **Prefer editing existing files** over creating new ones unless the task explicitly requires new files.
- **Run tests if present** before committing. If no test suite exists, verify the change manually where possible.
- **Keep commits atomic** — one logical change per commit.

## Conversation context

Conversation context is stored in `~/workspace/context.md` (on the persistent Docker volume, outside the git repo). Each completed task appends:

```markdown
### User
<instruction>

### Claude
<response>
```

`executor.run()` reads this file and prepends it to every Claude invocation so the model has full session context. The file grows indefinitely until the user runs `/compact` (which rewrites it as a condensed summary via Claude) or `/reset` (which deletes it).

## Task lifecycle

```
PENDING → RUNNING → DONE
                 ↘ CANCELLED
```

Each `AgentTask` is created by `queue.enqueue()` and processed by `queue._worker()`. Cancellation via `/cancel` triggers `asyncio.Task.cancel()` on the worker, which propagates `CancelledError` into `executor.run_raw()`, where the claude subprocess is killed via `process.kill()`. `/cancel <id>` calls `queue.remove_task()`, which cancels the worker if the task is running or splices it from the pending list if it is still queued.

## Constraints

- Only one chat ID is authorised (`cfg.allowed_chat_id`). All other senders are silently ignored.
- The heartbeat interval is `cfg.heartbeat_interval` (default 60s), configurable via `Config`.
- `poetry.lock` must always be committed alongside `pyproject.toml` to guarantee reproducible Docker builds.
