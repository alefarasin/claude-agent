import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config import Config
from handlers import commands, messages

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    cfg = Config.from_env()

    app = Application.builder().token(cfg.telegram_bot_token).build()
    app.bot_data["cfg"] = cfg

    app.add_handler(CommandHandler("start", commands.start))
    app.add_handler(CommandHandler("status", commands.status))
    app.add_handler(CommandHandler("log", commands.log))
    app.add_handler(CommandHandler("tasks", commands.tasks))
    app.add_handler(CommandHandler("cancel", commands.cancel))
    app.add_handler(CommandHandler("reset", commands.reset))
    app.add_handler(CommandHandler("help", commands.help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages.handle))

    logger.info("Bot in ascolto...")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
