"""Handler: /start — приветствие + меню."""

from telegram import Update
from telegram.ext import ContextTypes

from admin_bot.permissions import is_admin
from admin_bot.keyboards import main_menu_keyboard
from admin_bot.formatting import format_welcome
from admin_bot.services.users_service import upsert_user


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка /start."""
    user = update.effective_user
    user_id = user.id

    if not is_admin(user_id):
        await update.message.reply_text("⛔ Нет доступа.")
        return

    # Автосоздать/обновить пользователя в БД
    upsert_user(user_id, user.username, user.first_name)

    text = format_welcome(user.username)
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def unknown_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка неизвестных команд."""
    user = update.effective_user
    if not is_admin(user.id):
        return
    await update.message.reply_text("Неизвестная команда. Используйте /start или /menu.")
