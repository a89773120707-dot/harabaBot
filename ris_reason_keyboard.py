"""Inline-кнопки для выбора причины реакции."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


REASONS_BY_TYPE = {
    "buy": [
        [
            InlineKeyboardButton("💰 Хорошая цена", callback_data="reason:good_price"),
            InlineKeyboardButton("📏 Низкий пробег", callback_data="reason:good_mileage"),
        ],
        [
            InlineKeyboardButton("⚙️ Комплектация", callback_data="reason:good_equipment"),
            InlineKeyboardButton("📍 Регион", callback_data="reason:good_region"),
        ],
        [
            InlineKeyboardButton("🚗 Модель", callback_data="reason:good_model"),
            InlineKeyboardButton("📞 Звонить сейчас", callback_data="reason:call_now"),
        ],
    ],
    "skip": [
        [
            InlineKeyboardButton("💸 Дорого", callback_data="reason:expensive"),
            InlineKeyboardButton("📏 Большой пробег", callback_data="reason:high_mileage"),
        ],
        [
            InlineKeyboardButton("⚙️ Плохая комплектация", callback_data="reason:bad_equipment"),
            InlineKeyboardButton("📍 Неудобный регион", callback_data="reason:bad_region"),
        ],
        [
            InlineKeyboardButton("🚗 Плохая модель", callback_data="reason:bad_model"),
            InlineKeyboardButton("⚖️ Юр. риски", callback_data="reason:legal_risk"),
        ],
        [
            InlineKeyboardButton("📉 Низкая ликвидность", callback_data="reason:low_liquidity"),
        ],
    ],
    "watch": [
        [
            InlineKeyboardButton("💎 Редкое предложение", callback_data="reason:rare_offer"),
            InlineKeyboardButton("📉 Ниже рынка", callback_data="reason:below_market"),
        ],
        [
            InlineKeyboardButton("💰 Высокая маржа", callback_data="reason:high_margin"),
            InlineKeyboardButton("📞 Срочно звонить", callback_data="reason:urgent_call"),
        ],
    ],
}


def reason_keyboard(action: str) -> InlineKeyboardMarkup:
    """Клавиатура с причинами для типа реакции."""
    buttons = REASONS_BY_TYPE.get(action, [])
    # Кнопка пропуска
    buttons.append([InlineKeyboardButton("⏭ Без причины", callback_data="reason:none")])
    return InlineKeyboardMarkup(buttons)


def reason_selected_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после выбора причины."""
    keyboard = [[InlineKeyboardButton("✅ Понятно", callback_data="reason_done")]]
    return InlineKeyboardMarkup(keyboard)
