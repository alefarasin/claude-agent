import logging
import time
from telegram.error import Conflict
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from config import Config
from handlers import commands, messages

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_CONFLICT_RETRY_DELAY = 35


def _build_app(cfg: Config, error_handler) -> Application:
    app = Application.builder().token(cfg.telegram_bot_token).build()
    app.bot_data["cfg"] = cfg
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", commands.start))
    app.add_handler(CommandHandler("status", commands.status))
    app.add_handler(CommandHandler("log", commands.log))
    app.add_handler(CommandHandler("tasks", commands.tasks))
    app.add_handler(CommandHandler("cancel", commands.cancel))
    app.add_handler(CommandHandler("compact", commands.compact_cmd))
    app.add_handler(CommandHandler("reset", commands.reset))
    app.add_handler(CommandHandler("help", commands.help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages.handle))
    return app


def main() -> None:
    cfg = Config.from_env()

    while True:
        conflict = []

        async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
            if isinstance(context.error, Conflict):
                conflict.append(True)
                logger.warning(
                    "Conflict Telegram: altra sessione attiva, riprovo tra %ds...",
                    _CONFLICT_RETRY_DELAY,
                )
            else:
                logger.error("Errore: %s", context.error, exc_info=context.error)

        logger.info("Bot in ascolto...")
        _build_app(cfg, _error_handler).run_polling(
            allowed_updates=["message"], drop_pending_updates=True
        )

        if not conflict:
            break
        time.sleep(_CONFLICT_RETRY_DELAY)


if __name__ == "__main__":
    main()
