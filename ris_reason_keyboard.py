"""Inline-кнопки для выбора причины реакции — Feedback V2.

Реакции: 👀 review, 🤔 think, ⏭ skip
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


REASONS_BY_TYPE = {
    "review": [
        [
            InlineKeyboardButton("💰 Хорошая цена", callback_data="reason:good_price"),
            InlineKeyboardButton("🚗 Хорошее состояние", callback_data="reason:good_condition"),
        ],
        [
            InlineKeyboardButton("📉 Небольшой пробег", callback_data="reason:low_mileage"),
            InlineKeyboardButton("👤 Мало владельцев", callback_data="reason:few_owners"),
        ],
        [
            InlineKeyboardButton("📋 Хорошая история", callback_data="reason:good_history"),
            InlineKeyboardButton("⚙ Хорошая комплектация", callback_data="reason:good_equipment"),
        ],
        [
            InlineKeyboardButton("🔥 Ликвидная модель", callback_data="reason:liquid_model"),
            InlineKeyboardButton("📍 Хороший регион", callback_data="reason:good_region"),
        ],
        [
            InlineKeyboardButton("⭐ Другое", callback_data="reason:review_other"),
        ],
    ],
    "think": [
        [
            InlineKeyboardButton("💸 Высокая цена", callback_data="reason:high_price"),
            InlineKeyboardButton("📈 Большой пробег", callback_data="reason:high_mileage"),
        ],
        [
            InlineKeyboardButton("👥 Много владельцев", callback_data="reason:many_owners"),
            InlineKeyboardButton("🎨 Не нравится цвет", callback_data="reason:bad_color"),
        ],
        [
            InlineKeyboardButton("⚙ Слабая комплектация", callback_data="reason:poor_equipment"),
            InlineKeyboardButton("📋 Вопросы по истории", callback_data="reason:history_questions"),
        ],
        [
            InlineKeyboardButton("🚗 Неудачная модификация", callback_data="reason:bad_modification"),
            InlineKeyboardButton("📍 Неудобный регион", callback_data="reason:bad_region"),
        ],
        [
            InlineKeyboardButton("❓ Нужно изучить подробнее", callback_data="reason:need_more_info"),
        ],
        [
            InlineKeyboardButton("⭐ Другое", callback_data="reason:think_other"),
        ],
    ],
    "skip": [
        [
            InlineKeyboardButton("❌ Не моя модель", callback_data="reason:not_my_model"),
            InlineKeyboardButton("❌ Не мой сегмент", callback_data="reason:not_my_segment"),
        ],
        [
            InlineKeyboardButton("❌ Слишком дорого", callback_data="reason:too_expensive"),
            InlineKeyboardButton("❌ Слишком большой пробег", callback_data="reason:too_mileage"),
        ],
        [
            InlineKeyboardButton("❌ Плохое состояние", callback_data="reason:bad_condition"),
            InlineKeyboardButton("❌ Юр. риски", callback_data="reason:legal_risk"),
        ],
        [
            InlineKeyboardButton("❌ Неликвид", callback_data="reason:illiquid"),
        ],
        [
            InlineKeyboardButton("⭐ Другое", callback_data="reason:skip_other"),
        ],
    ],
}


def reason_keyboard(action: str) -> InlineKeyboardMarkup:
    """Клавиатура с причинами для типа реакции."""
    buttons = REASONS_BY_TYPE.get(action, [])
    # Кнопка пропуска выбора причины
    buttons.append([InlineKeyboardButton("⏭ Без причины", callback_data="reason:none")])
    return InlineKeyboardMarkup(buttons)


def reason_selected_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после выбора причины."""
    keyboard = [[InlineKeyboardButton("✅ Понятно", callback_data="reason_done")]]
    return InlineKeyboardMarkup(keyboard)
