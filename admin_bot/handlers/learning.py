"""Handler: 🧠 Обучение — learning_report, learning_reasons, config_report."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from admin_bot.permissions import is_admin
from admin_bot.handlers.menu import safe_edit
from admin_bot.keyboards import back_keyboard
from ris_analytics import get_learning_report, get_learning_reasons, get_config_report


async def learning_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок раздела 🧠 Обучение."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        await safe_edit(query, "⛔ Нет доступа.")
        return

    data = query.data

    if data == "menu_learning":
        # Главное меню обучения
        keyboard = [
            [InlineKeyboardButton("📊 Learning Report", callback_data="learning_report")],
            [InlineKeyboardButton("📋 Причины", callback_data="learning_reasons")],
            [InlineKeyboardButton("⚙️ Config Report", callback_data="config_report")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")],
        ]
        text = "🧠 Обучение\n\nВыберите отчёт:"
        await safe_edit(query, text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "learning_report":
        report = get_learning_report()
        text = _format_learning_report(report)
        await safe_edit(query, text, reply_markup=back_keyboard())
        return

    if data == "learning_reasons":
        reasons = get_learning_reasons()
        text = _format_learning_reasons(reasons)
        await safe_edit(query, text, reply_markup=back_keyboard())
        return

    if data == "config_report":
        config = get_config_report()
        text = _format_config_report(config)
        await safe_edit(query, text, reply_markup=back_keyboard())
        return


def _format_learning_report(report: dict) -> str:
    """Форматировать learning report."""
    total = report["total"]
    if total == 0:
        return "📊 Learning Report\n\nРеакций пока нет. Отправьте карточки и соберите реакции."

    by_type = report.get("by_type", {})
    review = by_type.get("review", 0)
    think = by_type.get("think", 0)
    skip = by_type.get("skip", 0)

    lines = [
        f"📊 Learning Report\n\n"
        f"Всего реакций: {total}\n\n"
        f"👀 Посмотреть: {review}\n"
        f"🤔 Подумать: {think}\n"
        f"⏭ Скип: {skip}\n",
        f"Без причины: {report.get('without_reason', 0)}\n",
    ]

    # Топ модели
    top_models = report.get("top_models", [])
    if top_models:
        lines.append("Топ модели:")
        for m in top_models[:5]:
            icon = {"review": "👀", "think": "🤔", "skip": "⏭"}.get(m["action"], "•")
            lines.append(f"  {icon} {m['model_id']}: {m['cnt']}")

    # Топ причины
    top_reasons = report.get("top_reasons", [])
    if top_reasons:
        lines.append("\nТоп причины:")
        for r in top_reasons[:5]:
            lines.append(f"  {r['title']}: {r['cnt']}")

    return "\n".join(lines)


def _format_learning_reasons(reasons: dict) -> str:
    """Форматировать причины по группам."""
    lines = ["📋 Причины по группам\n"]

    for group_name, group_key, emoji in [
        ("👀 ПОСМОТРЕТЬ", "review", "👀"),
        ("🤔 ПОДУМАТЬ", "think", "🤔"),
        ("⏭ СКИП", "skip", "⏭"),
    ]:
        items = reasons.get(group_key, [])
        lines.append(f"\n{group_name}")
        if items:
            for r in items:
                lines.append(f"  {r['title']}: {r['cnt']}")
        else:
            lines.append("  (нет данных)")

    return "\n".join(lines)


def _format_config_report(config: dict) -> str:
    """Форматировать config report."""
    if not config:
        return "⚙️ Config Report\n\nРеакций по конфигам пока нет."

    lines = ["⚙️ Config Report\n"]

    for model_id, data in sorted(config.items(), key=lambda x: x[1]["reaction_count"], reverse=True):
        review = data["review"]
        think = data["think"]
        skip = data["skip"]
        total = data["reaction_count"]

        lines.append(f"\n📦 {model_id} ({total})")
        lines.append(f"  👀 {review} | 🤔 {think} | ⏭ {skip}")

        # Топ причины
        reasons = data.get("reasons", [])
        if reasons:
            for r in reasons[:3]:
                icon = {"review": "👀", "think": "🤔", "skip": "⏭"}.get(r["reaction_type"], "•")
                lines.append(f"  {icon} {r['title']}: {r['cnt']}")

    return "\n".join(lines)
