"""Точка входа админ-бота Haraba Mini."""

import logging

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from admin_bot.config import ADMIN_BOT_TOKEN, validate
from admin_bot.services.db_service import ensure_tables, ensure_owner_exists

from admin_bot.handlers.start import start_handler, unknown_handler
from admin_bot.handlers.menu import menu_callback_handler, user_callback_handler

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    """Запуск админ-бота."""
    # Проверка конфига
    if not validate():
        logger.error("Config validation failed. Set ADMIN_BOT_TOKEN in .env")
        return

    # Миграции БД
    logger.info("Running database migrations...")
    ensure_tables()
    ensure_owner_exists()
    logger.info("Database migrations complete.")

    # Приложение
    application = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("menu", start_handler))  # /menu = /start

    # Callback-кнопки (меню + действия с пользователями)
    application.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^(menu_|back_to_menu)"))
    application.add_handler(CallbackQueryHandler(user_callback_handler, pattern="^user_"))

    # Неизвестные команды
    application.add_handler(MessageHandler(filters.COMMAND, unknown_handler))

    # Запуск
    logger.info("Admin bot starting...")
    application.run_polling()


if __name__ == "__main__":
    main()
