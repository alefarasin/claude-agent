import asyncio
import logging
import os
from telegram import Update
from telegram.error import Conflict
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from config import Config
from handlers import commands, messages

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_CONFLICT_WAIT = 35


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, Conflict):
        logger.warning(
            "Conflict Telegram: altra sessione di polling attiva. "
            "Attendo %ds prima del riavvio...",
            _CONFLICT_WAIT,
        )
        await asyncio.sleep(_CONFLICT_WAIT)
        os._exit(1)
    logger.error("Errore non gestito: %s", context.error, exc_info=context.error)


def main() -> None:
    cfg = Config.from_env()

    app = Application.builder().token(cfg.telegram_bot_token).build()
    app.bot_data["cfg"] = cfg

    app.add_error_handler(_error_handler)
    app.add_handler(CommandHandler("start", commands.start))
    app.add_handler(CommandHandler("status", commands.status))
    app.add_handler(CommandHandler("log", commands.log))
    app.add_handler(CommandHandler("tasks", commands.tasks))
    app.add_handler(CommandHandler("cancel", commands.cancel))
    app.add_handler(CommandHandler("reset", commands.reset))
    app.add_handler(CommandHandler("help", commands.help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages.handle))

    logger.info("Bot in ascolto...")
    app.run_polling(allowed_updates=["message"], drop_pending_updates=True)


if __name__ == "__main__":
    main()
