#!/usr/bin/env python3
"""
Claude Agent - Telegram Bot
Riceve istruzioni via Telegram e le esegue con Claude Code CLI.
"""

import os
import asyncio
import subprocess
import logging
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def is_authorized(update: Update) -> bool:
    """Verifica che il messaggio venga dall'utente autorizzato."""
    return update.effective_chat.id == ALLOWED_CHAT_ID


def setup_workspace() -> bool:
    """Clona il repo se non esiste già."""
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
        # Configura git
        subprocess.run(["git", "config", "user.email", "claude-agent@bot.local"], cwd=WORKSPACE_DIR)
        subprocess.run(["git", "config", "user.name", "Claude Agent"], cwd=WORKSPACE_DIR)
    return True


async def run_claude_code(instruction: str) -> str:
    """Esegue Claude Code con l'istruzione ricevuta."""
    env = os.environ.copy()
    # Usa il token OAuth dell'abbonamento (NON la API key)
    env["CLAUDE_CODE_OAUTH_TOKEN"] = CLAUDE_CODE_OAUTH_TOKEN
    # Rimuovi eventuale API key per evitare che abbia precedenza
    env.pop("ANTHROPIC_API_KEY", None)

    try:
        process = await asyncio.create_subprocess_exec(
            "claude",
            "--print",
            "--dangerously-skip-permissions",
            instruction,
            cwd=WORKSPACE_DIR,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=300  # 5 minuti max
        )
        output = stdout.decode("utf-8", errors="replace")
        errors = stderr.decode("utf-8", errors="replace")

        if process.returncode != 0 and errors:
            return f"⚠️ Output:\n{output}\n\nErrori:\n{errors}"
        return output if output else "✅ Completato senza output."

    except asyncio.TimeoutError:
        return "⏱️ Timeout: il task ha superato 5 minuti."
    except Exception as e:
        return f"❌ Errore: {str(e)}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start."""
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "👋 Claude Agent attivo!\n\n"
        "Inviami un'istruzione e la eseguirò sul repository.\n\n"
        "Comandi disponibili:\n"
        "/status — stato del workspace\n"
        "/log — ultimi commit\n"
        "/help — guida rapida"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /status — mostra stato del workspace."""
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
    """Comando /log — ultimi 5 commit."""
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


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help."""
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "📖 *Guida Claude Agent*\n\n"
        "Invia qualsiasi istruzione in linguaggio naturale:\n\n"
        "• `Crea una funzione fibonacci in Python con i test`\n"
        "• `Fai il refactoring di main.py usando le dataclass`\n"
        "• `Aggiungi gestione degli errori a utils.py`\n"
        "• `Scrivi la documentazione per tutte le funzioni`\n\n"
        "Claude Code eseguirà il task, testerà il codice e committa automaticamente.\n\n"
        "⏱️ Timeout massimo: 5 minuti per task.",
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce i messaggi in arrivo."""
    if not is_authorized(update):
        logger.warning(f"Accesso non autorizzato da chat_id: {update.effective_chat.id}")
        return

    instruction = update.message.text
    logger.info(f"Istruzione ricevuta: {instruction}")

    # Inizializza workspace se necessario
    await update.message.reply_text("⚙️ Inizializzazione workspace...")
    if not setup_workspace():
        await update.message.reply_text("❌ Errore nell'inizializzazione del workspace. Controlla il GitHub token.")
        return

    # Aggiorna il repo
    subprocess.run(["git", "pull"], cwd=WORKSPACE_DIR, capture_output=True)

    await update.message.reply_text(f"🤖 Sto eseguendo:\n_{instruction}_\n\nAttendi...", parse_mode="Markdown")

    # Esegui Claude Code
    result = await run_claude_code(instruction)

    # Tronca se troppo lungo per Telegram (limite 4096 caratteri)
    if len(result) > 3800:
        result = result[:3800] + "\n\n... _(output troncato)_"

    await update.message.reply_text(f"✅ *Completato!*\n\n{result}", parse_mode="Markdown")


def main():
    """Avvia il bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN non configurato")
    if not CLAUDE_CODE_OAUTH_TOKEN:
        raise ValueError("CLAUDE_CODE_OAUTH_TOKEN non configurato")
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN non configurato")

    logger.info("Avvio Claude Agent Bot...")

    # Inizializza workspace subito
    setup_workspace()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("log", log))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot in ascolto...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
