from __future__ import annotations
import os
import subprocess
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from agent import queue as q
from agent import history


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
        "/reset — resetta la sessione corrente\n"
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
    if not q.cancel_all(update.effective_chat.id):
        await update.message.reply_text("Nessun task in esecuzione.")
        return
    await update.message.reply_text("🚫 Annullamento in corso...")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    if not authorized(update, cfg.allowed_chat_id):
        return
    history.clear(update.effective_chat.id)
    await update.message.reply_text("🔄 Sessione resettata. Puoi iniziare un nuovo argomento.")


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
        "/reset — nuova sessione su argomento diverso",
        parse_mode="Markdown",
    )
