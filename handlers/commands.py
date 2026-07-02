from __future__ import annotations
import os
import subprocess
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from agent import queue as q


def authorized(update: Update, allowed_chat_id: int) -> bool:
    return update.effective_chat.id == allowed_chat_id


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    if not authorized(update, cfg.allowed_chat_id):
        return
    await update.message.reply_text(
        "👋 Claude Agent attivo!\n\n"
        "Inviami un'istruzione e la eseguirò sul repository.\n\n"
        "Comandi disponibili:\n"
        "/status — stato del workspace\n"
        "/log — ultimi commit\n"
        "/tasks — task in coda o in esecuzione\n"
        "/cancel — annulla il task corrente e svuota la coda\n"
        "/cancel <id> — rimuove un task specifico dalla coda\n"
        "/compact — compatta il contesto della sessione\n"
        "/reset — azzera il contesto e inizia una nuova sessione\n"
        "/help — guida rapida"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    if not authorized(update, cfg.allowed_chat_id):
        return
    if not os.path.exists(cfg.workspace_dir):
        await update.message.reply_text("⚠️ Workspace non inizializzato. Invia un'istruzione per iniziare.")
        return
    result = subprocess.run(["git", "status", "--short"], cwd=cfg.workspace_dir, capture_output=True, text=True)
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=cfg.workspace_dir, capture_output=True, text=True)
    await update.message.reply_text(
        f"📁 Workspace: `{cfg.workspace_dir}`\n"
        f"🌿 Branch: `{branch.stdout.strip()}`\n"
        f"📝 Modifiche:\n`{result.stdout or 'Nessuna modifica pendente'}`",
        parse_mode="Markdown",
    )


async def log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    if not authorized(update, cfg.allowed_chat_id):
        return
    if not os.path.exists(cfg.workspace_dir):
        await update.message.reply_text("⚠️ Workspace non inizializzato.")
        return
    result = subprocess.run(["git", "log", "--oneline", "-5"], cwd=cfg.workspace_dir, capture_output=True, text=True)
    await update.message.reply_text(
        f"📜 Ultimi commit:\n`{result.stdout or 'Nessun commit'}`",
        parse_mode="Markdown",
    )


async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    if not authorized(update, cfg.allowed_chat_id):
        return
    chat_id = update.effective_chat.id
    running, pending = q.queue_status(chat_id)
    if not running and not pending:
        await update.message.reply_text("Nessun task attivo.")
        return
    lines = []
    if running:
        elapsed = int((datetime.now() - running.started_at).total_seconds() / 60)
        lines.append(f"🔄 #{running.id} ({elapsed}min) — {running.instruction[:60]}")
    for t in pending:
        lines.append(f"⏳ #{t.id} — {t.instruction[:60]}")
    await update.message.reply_text("*Task attivi:*\n" + "\n".join(lines), parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    if not authorized(update, cfg.allowed_chat_id):
        return
    chat_id = update.effective_chat.id
    if context.args:
        try:
            task_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Uso: `/cancel` oppure `/cancel <id>`", parse_mode="Markdown")
            return
        result = q.remove_task(chat_id, task_id)
        if result == "running":
            await update.message.reply_text(f"🚫 Task #{task_id} (in esecuzione) annullato.")
        elif result == "removed":
            await update.message.reply_text(f"🗑️ Task #{task_id} rimosso dalla coda.")
        else:
            await update.message.reply_text(f"Task #{task_id} non trovato.")
        return
    if not q.cancel_all(chat_id):
        await update.message.reply_text("Nessun task in esecuzione.")
        return
    await update.message.reply_text("🚫 Annullamento in corso...")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    if not authorized(update, cfg.allowed_chat_id):
        return
    from agent import executor
    executor.reset_context(cfg)
    await update.message.reply_text("🔄 Sessione resettata. Puoi iniziare un nuovo argomento.")


async def compact_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    if not authorized(update, cfg.allowed_chat_id):
        return
    from agent import executor
    if not executor.read_context(cfg):
        await update.message.reply_text("Nessun contesto da compattare.")
        return
    await update.message.reply_text("🗜️ Compattazione in corso...")
    await executor.compact_context(cfg)
    await update.message.reply_text("✅ Contesto compattato.")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    if not authorized(update, cfg.allowed_chat_id):
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
        "/cancel <id> — rimuove un task specifico dalla coda\n"
        "/compact — chiede a Claude di condensare il contesto accumulato\n"
        "/reset — azzera il contesto e inizia una nuova sessione",
        parse_mode="Markdown",
    )
