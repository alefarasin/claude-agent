from __future__ import annotations
import logging
from telegram import Update
from telegram.ext import ContextTypes
from agent import queue as q
from handlers.commands import authorized

logger = logging.getLogger(__name__)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    if not authorized(update, cfg.allowed_chat_id):
        logger.warning(f"Accesso non autorizzato da chat_id: {update.effective_chat.id}")
        return

    chat_id = update.effective_chat.id
    instruction = update.message.text
    logger.info(f"Istruzione ricevuta: {instruction}")

    task = q.enqueue(chat_id, instruction)
    q.ensure_worker(chat_id, context.bot, cfg)
