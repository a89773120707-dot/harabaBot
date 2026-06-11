"""Inline-кнопки для админ-бота."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админ-бота."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Статистика", callback_data="menu_stats"),
            InlineKeyboardButton("👍 Реакции", callback_data="menu_reactions"),
        ],
        [
            InlineKeyboardButton("👥 Менеджеры", callback_data="menu_users"),
            InlineKeyboardButton("🚗 Карточки", callback_data="menu_cards"),
        ],
        [
            InlineKeyboardButton("🔍 Поиски", callback_data="menu_searches"),
            InlineKeyboardButton("🗄 База", callback_data="menu_db"),
        ],
        [
            InlineKeyboardButton("🧾 Логи", callback_data="menu_logs"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def users_list_keyboard(users: list[dict]) -> InlineKeyboardMarkup:
    """Кнопки для списка пользователей (быстрые действия)."""
    keyboard = []
    for u in users:
        status_icon = {"active": "✅", "paused": "⏸", "disabled": "❌", "pending": "⏳"}.get(u["status"], "?")
        label = f"{status_icon} {u.get('username', u['telegram_id'])} ({u['status']})"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"user_detail:{u['telegram_id']}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)


def user_detail_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    """Кнопки действий для конкретного пользователя."""
    keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"user_approve:{telegram_id}")],
        [InlineKeyboardButton("⏸ Pause", callback_data=f"user_pause:{telegram_id}")],
        [InlineKeyboardButton("▶️ Resume", callback_data=f"user_resume:{telegram_id}")],
        [InlineKeyboardButton("❌ Disable", callback_data=f"user_disable:{telegram_id}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu_users")],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка «Назад»."""
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]]
    return InlineKeyboardMarkup(keyboard)
