#!/usr/bin/env python3
"""
Claude Agent - Telegram Bot
Riceve istruzioni via Telegram e le esegue con Claude Code CLI.
"""

import os
import asyncio
import subprocess
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

# Configurazione
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))
CLAUDE_CODE_OAUTH_TOKEN = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
REPO_NAME = os.getenv("REPO_NAME", "claude-agent")
WORKSPACE_DIR = os.path.expanduser(f"~/workspace/{REPO_NAME}")

MAX_HISTORY_LEN = 20
HISTORY_KEEP_RECENT = 6
HEARTBEAT_INTERVAL = 60  # secondi tra i messaggi "ancora in esecuzione"

conversation_history: dict[int, list[dict]] = {}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- Task queue ---

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"


@dataclass
class AgentTask:
    id: int
    instruction: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None


_task_counter = 0
task_queues: dict[int, list[AgentTask]] = {}
running_tasks: dict[int, AgentTask | None] = {}
worker_tasks: dict[int, asyncio.Task | None] = {}


def _next_task_id() -> int:
    global _task_counter
    _task_counter += 1
    return _task_counter


def enqueue_task(chat_id: int, instruction: str) -> AgentTask:
    task = AgentTask(id=_next_task_id(), instruction=instruction)
    task_queues.setdefault(chat_id, []).append(task)
    return task


def ensure_worker(chat_id: int, bot) -> None:
    w = worker_tasks.get(chat_id)
    if w is None or w.done():
        worker_tasks[chat_id] = asyncio.create_task(chat_worker(chat_id, bot))


# --- History helpers ---

def get_history(chat_id: int) -> list[dict]:
    return conversation_history.setdefault(chat_id, [])


def add_to_history(chat_id: int, role: str, content: str) -> None:
    get_history(chat_id).append({"role": role, "content": content})


def reset_history(chat_id: int) -> None:
    conversation_history[chat_id] = []


def build_context(chat_id: int) -> str:
    lines = []
    for msg in get_history(chat_id):
        if msg["role"] == "system":
            lines.append(msg["content"])
        elif msg["role"] == "user":
            lines.append(f"User: {msg['content']}")
        else:
            lines.append(f"Assistant: {msg['content']}")
    return "\n".join(lines)


# --- Claude execution ---

async def _run_claude(instruction: str, cwd: str) -> str:
    env = os.environ.copy()
    env["CLAUDE_CODE_OAUTH_TOKEN"] = CLAUDE_CODE_OAUTH_TOKEN
    env.pop("ANTHROPIC_API_KEY", None)
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            "claude", "--print", "--dangerously-skip-permissions", instruction,
            cwd=cwd, env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode("utf-8", errors="replace")
        errors = stderr.decode("utf-8", errors="replace")
        if process.returncode != 0 and errors:
            return f"⚠️ Output:\n{output}\n\nErrori:\n{errors}"
        return output if output else "✅ Completato senza output."
    except asyncio.CancelledError:
        if process:
            process.kill()
            await process.wait()
        raise
    except Exception as e:
        return f"❌ Errore: {str(e)}"


async def compact_history_if_needed(chat_id: int) -> None:
    history = get_history(chat_id)
    if len(history) <= MAX_HISTORY_LEN:
        return
    to_summarize = history[:-HISTORY_KEEP_RECENT]
    recent = history[-HISTORY_KEEP_RECENT:]
    conv_text = "\n".join(
        msg["content"] if msg["role"] == "system"
        else f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
        for msg in to_summarize
    )
    summary = await _run_claude(
        f"Summarize this conversation concisely, preserving key context, decisions, and technical details:\n\n{conv_text}",
        cwd=os.path.expanduser("~")
    )
    conversation_history[chat_id] = [
        {"role": "system", "content": f"[Summary of previous conversation]: {summary}"}
    ] + recent
    logger.info(f"History compacted for chat_id {chat_id}: {len(to_summarize)} messages → summary")


async def run_claude_code(instruction: str, chat_id: int | None = None) -> str:
    context = build_context(chat_id) if chat_id is not None else ""
    full_instruction = f"{context}\n\nCurrent instruction: {instruction}" if context else instruction
    return await _run_claude(full_instruction, cwd=WORKSPACE_DIR)


# --- Worker ---

async def _heartbeat(chat_id: int, task: AgentTask, bot) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        elapsed = int((datetime.now() - task.started_at).total_seconds() / 60)
        try:
            await bot.send_message(chat_id, f"⏳ Task #{task.id} ancora in esecuzione ({elapsed}min)...")
        except Exception:
            pass


async def chat_worker(chat_id: int, bot) -> None:
    try:
        while True:
            queue = task_queues.get(chat_id, [])
            if not queue:
                break

            task = queue.pop(0)
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            running_tasks[chat_id] = task

            try:
                await bot.send_message(
                    chat_id,
                    f"▶️ Task #{task.id} in esecuzione...\n_{task.instruction[:80]}_",
                    parse_mode="Markdown"
                )

                if not setup_workspace():
                    await bot.send_message(chat_id, "❌ Errore workspace. Controlla il GitHub token.")
                    task.status = TaskStatus.DONE
                    continue

                subprocess.run(["git", "pull"], cwd=WORKSPACE_DIR, capture_output=True)
                await compact_history_if_needed(chat_id)

                heartbeat = asyncio.create_task(_heartbeat(chat_id, task, bot))
                try:
                    result = await run_claude_code(task.instruction, chat_id=chat_id)
                finally:
                    heartbeat.cancel()
                    try:
                        await heartbeat
                    except asyncio.CancelledError:
                        pass

                task.status = TaskStatus.DONE
                add_to_history(chat_id, "user", task.instruction)
                add_to_history(chat_id, "assistant", result)

                display = result[:3800] + "\n\n... _(output troncato)_" if len(result) > 3800 else result
                await bot.send_message(
                    chat_id,
                    f"✅ *Task #{task.id} completato!*\n\n{display}",
                    parse_mode="Markdown"
                )

            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                task_queues[chat_id] = []
                asyncio.create_task(
                    bot.send_message(chat_id, f"🚫 Task #{task.id} annullato.")
                )
                raise

            finally:
                running_tasks[chat_id] = None

    finally:
        worker_tasks[chat_id] = None


# --- Workspace ---

def is_authorized(update: Update) -> bool:
    return update.effective_chat.id == ALLOWED_CHAT_ID


def setup_workspace() -> bool:
    if not os.path.exists(WORKSPACE_DIR):
        os.makedirs(os.path.dirname(WORKSPACE_DIR), exist_ok=True)
        repo_url = f"https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@github.com/{GITHUB_USERNAME}/{REPO_NAME}.git"
        result = subprocess.run(
            ["git", "clone", repo_url, WORKSPACE_DIR],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.error(f"Errore clone repo: {result.stderr}")
            return False
        subprocess.run(["git", "config", "user.email", "claude-agent@bot.local"], cwd=WORKSPACE_DIR)
        subprocess.run(["git", "config", "user.name", "Claude Agent"], cwd=WORKSPACE_DIR)
    return True


# --- Command handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "👋 Claude Agent attivo!\n\n"
        "Inviami un'istruzione e la eseguirò sul repository.\n\n"
        "Comandi disponibili:\n"
        "/status — stato del workspace\n"
        "/log — ultimi commit\n"
        "/tasks — task in coda o in esecuzione\n"
        "/cancel — annulla il task corrente e svuota la coda\n"
        "/reset — resetta la sessione corrente\n"
        "/help — guida rapida"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    if not os.path.exists(WORKSPACE_DIR):
        await update.message.reply_text("⚠️ Workspace non inizializzato. Invia un'istruzione per iniziare.")
        return
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=WORKSPACE_DIR, capture_output=True, text=True
    )
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=WORKSPACE_DIR, capture_output=True, text=True
    )
    await update.message.reply_text(
        f"📁 Workspace: `{WORKSPACE_DIR}`\n"
        f"🌿 Branch: `{branch.stdout.strip()}`\n"
        f"📝 Modifiche:\n`{result.stdout or 'Nessuna modifica pendente'}`",
        parse_mode="Markdown"
    )


async def log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    if not os.path.exists(WORKSPACE_DIR):
        await update.message.reply_text("⚠️ Workspace non inizializzato.")
        return
    result = subprocess.run(
        ["git", "log", "--oneline", "-5"],
        cwd=WORKSPACE_DIR, capture_output=True, text=True
    )
    await update.message.reply_text(
        f"📜 Ultimi commit:\n`{result.stdout or 'Nessun commit'}`",
        parse_mode="Markdown"
    )


async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    chat_id = update.effective_chat.id
    running = running_tasks.get(chat_id)
    pending = task_queues.get(chat_id, [])

    if not running and not pending:
        await update.message.reply_text("Nessun task attivo.")
        return

    lines = []
    if running:
        elapsed = int((datetime.now() - running.started_at).total_seconds() / 60)
        lines.append(f"🔄 #{running.id} ({elapsed}min) — {running.instruction[:60]}")
    for t in pending:
        lines.append(f"⏳ #{t.id} — {t.instruction[:60]}")

    await update.message.reply_text(
        "*Task attivi:*\n" + "\n".join(lines),
        parse_mode="Markdown"
    )


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    chat_id = update.effective_chat.id
    w = worker_tasks.get(chat_id)
    if not w or w.done():
        await update.message.reply_text("Nessun task in esecuzione.")
        return
    task_queues[chat_id] = []
    w.cancel()
    await update.message.reply_text("🚫 Annullamento in corso...")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "📖 *Guida Claude Agent*\n\n"
        "Invia qualsiasi istruzione in linguaggio naturale:\n\n"
        "• `Crea una funzione fibonacci in Python con i test`\n"
        "• `Fai il refactoring di main.py usando le dataclass`\n"
        "• `Aggiungi gestione degli errori a utils.py`\n"
        "• `Scrivi la documentazione per tutte le funzioni`\n\n"
        "Puoi inviare più istruzioni: vengono eseguite in sequenza.\n\n"
        "/tasks — vedi cosa è in coda\n"
        "/cancel — annulla il task corrente e svuota la coda\n"
        "/reset — nuova sessione su argomento diverso",
        parse_mode="Markdown"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    reset_history(update.effective_chat.id)
    await update.message.reply_text("🔄 Sessione resettata. Puoi iniziare un nuovo argomento.")


# --- Message handler ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        logger.warning(f"Accesso non autorizzato da chat_id: {update.effective_chat.id}")
        return

    chat_id = update.effective_chat.id
    instruction = update.message.text
    logger.info(f"Istruzione ricevuta: {instruction}")

    task = enqueue_task(chat_id, instruction)
    is_busy = bool(running_tasks.get(chat_id))

    if is_busy:
        pos = len(task_queues.get(chat_id, []))
        await update.message.reply_text(
            f"⏳ Task #{task.id} in coda (posizione {pos}).\n_{instruction[:80]}_",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"🚀 Task #{task.id} ricevuto.\n_{instruction[:80]}_",
            parse_mode="Markdown"
        )

    ensure_worker(chat_id, context.bot)


# --- Entry point ---

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN non configurato")
    if not CLAUDE_CODE_OAUTH_TOKEN:
        raise ValueError("CLAUDE_CODE_OAUTH_TOKEN non configurato")
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN non configurato")

    logger.info("Avvio Claude Agent Bot...")
    setup_workspace()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("log", log))
    app.add_handler(CommandHandler("tasks", tasks_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot in ascolto...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
