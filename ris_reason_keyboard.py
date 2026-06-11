"""Inline-кнопки для выбора причины реакции — Feedback V2 (v3).

Реакции: 👀 review, 🤔 think, ⏭ skip
Каждая реакция: 4 основные причины + 💬 Комментарий
Нет "Без причины", нет "Ещё причины"
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ═══════════════════════════════════════════════════════════
# Основные причины для каждой реакции
# ═══════════════════════════════════════════════════════════
MAIN_REASONS = {
    "review": [
        [
            InlineKeyboardButton("💰 Хорошая цена", callback_data="reason:good_price"),
            InlineKeyboardButton("📉 Небольшой пробег", callback_data="reason:low_mileage"),
        ],
        [
            InlineKeyboardButton("🔥 Ликвидная модель", callback_data="reason:liquid_model"),
            InlineKeyboardButton("⚙ Хорошая комплектация", callback_data="reason:good_equipment"),
        ],
        [
            InlineKeyboardButton("💬 Написать комментарий", callback_data="reason:comment"),
        ],
    ],
    "think": [
        [
            InlineKeyboardButton("💸 Высокая цена", callback_data="reason:high_price"),
            InlineKeyboardButton("📈 Большой пробег", callback_data="reason:high_mileage"),
        ],
        [
            InlineKeyboardButton("👥 Много владельцев", callback_data="reason:many_owners"),
            InlineKeyboardButton("⚙ Слабая комплектация", callback_data="reason:poor_equipment"),
        ],
        [
            InlineKeyboardButton("💬 Написать комментарий", callback_data="reason:comment"),
        ],
    ],
    "skip": [
        [
            InlineKeyboardButton("❌ Слишком дорого", callback_data="reason:too_expensive"),
            InlineKeyboardButton("❌ Слишком большой пробег", callback_data="reason:too_mileage"),
        ],
        [
            InlineKeyboardButton("❌ Плохое состояние", callback_data="reason:bad_condition"),
            InlineKeyboardButton("❌ Юр. риски", callback_data="reason:legal_risk"),
        ],
        [
            InlineKeyboardButton("💬 Написать комментарий", callback_data="reason:comment"),
        ],
    ],
}

# ═══════════════════════════════════════════════════════════
# ДОПОЛНИТЕЛЬНЫЕ причины (под "Ещё причины")
# ═══════════════════════════════════════════════════════════
EXTRA_REASONS = {
    "review": [
        [
            InlineKeyboardButton("🚗 Хорошее состояние", callback_data="reason:good_condition"),
            InlineKeyboardButton("📋 Хорошая история", callback_data="reason:good_history"),
        ],
        [
            InlineKeyboardButton("👤 Мало владельцев", callback_data="reason:few_owners"),
            InlineKeyboardButton("📍 Хороший регион", callback_data="reason:good_region"),
        ],
        [
            InlineKeyboardButton("⭐ Другое", callback_data="reason:review_other"),
        ],
    ],
    "think": [
        [
            InlineKeyboardButton("📋 Вопросы по истории", callback_data="reason:history_questions"),
            InlineKeyboardButton("🎨 Не нравится цвет", callback_data="reason:bad_color"),
        ],
        [
            InlineKeyboardButton("🚗 Неудачная модификация", callback_data="reason:bad_modification"),
            InlineKeyboardButton("📍 Неудобный регион", callback_data="reason:bad_region"),
        ],
        [
            InlineKeyboardButton("❓ Нужно изучить подробнее", callback_data="reason:need_more_info"),
            InlineKeyboardButton("⭐ Другое", callback_data="reason:think_other"),
        ],
    ],
    "skip": [
        [
            InlineKeyboardButton("❌ Не моя модель", callback_data="reason:not_my_model"),
            InlineKeyboardButton("❌ Не мой сегмент", callback_data="reason:not_my_segment"),
        ],
        [
            InlineKeyboardButton("❌ Неликвид", callback_data="reason:illiquid"),
        ],
        [
            InlineKeyboardButton("⭐ Другое", callback_data="reason:skip_other"),
        ],
    ],
}

# ═══════════════════════════════════════════════════════════
# Веса причин (хранить в БД, не использовать для скоринга)
# ═══════════════════════════════════════════════════════════
REASON_WEIGHTS = {
    # review
    "good_price": 10,
    "good_condition": 7,
    "low_mileage": 8,
    "few_owners": 5,
    "good_history": 9,
    "good_equipment": 4,
    "liquid_model": 8,
    "good_region": 3,
    "review_other": 1,
    # think
    "high_price": 10,
    "high_mileage": 8,
    "many_owners": 7,
    "bad_color": 2,
    "poor_equipment": 5,
    "history_questions": 9,
    "bad_modification": 4,
    "bad_region": 3,
    "need_more_info": 6,
    "think_other": 1,
    # skip
    "not_my_model": 5,
    "not_my_segment": 4,
    "too_expensive": 10,
    "too_mileage": 8,
    "bad_condition": 7,
    "legal_risk": 9,
    "illiquid": 6,
    "skip_other": 1,
}

# ═══════════════════════════════════════════════════════════
# Промпты для каждой реакции
# ═══════════════════════════════════════════════════════════
REACTION_PROMPTS = {
    "review": "👀 Посмотреть\n\nЧто понравилось?",
    "think": "🤔 Подумать\n\nЧто мешает принять решение?",
    "skip": "⏭ Скип\n\nПочему пропускаем?",
}


def reason_keyboard(action: str, show_extra: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура с причинами для типа реакции.

    Args:
        action: review / think / skip
        show_extra: если True — показать дополнительные причины
    """
    if show_extra:
        buttons = list(EXTRA_REASONS.get(action, []))
        buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"reasons_main:{action}")])
    else:
        buttons = list(MAIN_REASONS.get(action, []))

    return InlineKeyboardMarkup(buttons)


def reason_selected_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после выбора причины."""
    keyboard = [[InlineKeyboardButton("✅ Понятно", callback_data="reason_done")]]
    return InlineKeyboardMarkup(keyboard)
