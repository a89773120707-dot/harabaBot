"""Handlers and Telegram formatting for the learning section."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from admin_bot.config import DB_PATH
from admin_bot.handlers.menu import safe_edit
from admin_bot.keyboards import back_keyboard
from admin_bot.permissions import is_admin
from ris_analytics import get_config_report, get_learning_reasons, get_learning_report
from ris_manager_config_report import get_manager_config_report


logger = logging.getLogger(__name__)
MAX_TELEGRAM_MESSAGE_LENGTH = 3800


def _learning_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 Learning Report", callback_data="learning_report")],
            [InlineKeyboardButton("📋 Причины", callback_data="learning_reasons")],
            [InlineKeyboardButton("⚙️ Config Report", callback_data="config_report")],
            [
                InlineKeyboardButton(
                    "👥 Manager Config Report",
                    callback_data="learning_manager_config_report",
                )
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")],
        ]
    )


def _learning_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ К обучению", callback_data="menu_learning")]]
    )


async def learning_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback buttons in the learning section."""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await safe_edit(query, "⛔ Нет доступа.")
        return

    data = query.data
    if data == "menu_learning":
        await safe_edit(
            query,
            "🧠 Обучение\n\nВыберите отчёт:",
            reply_markup=_learning_keyboard(),
        )
        return

    if data == "learning_report":
        await safe_edit(
            query,
            _format_learning_report(get_learning_report()),
            reply_markup=back_keyboard(),
        )
        return

    if data == "learning_reasons":
        await safe_edit(
            query,
            _format_learning_reasons(get_learning_reasons()),
            reply_markup=back_keyboard(),
        )
        return

    if data == "config_report":
        await safe_edit(
            query,
            _format_config_report(get_config_report()),
            reply_markup=back_keyboard(),
        )
        return

    if data == "learning_manager_config_report":
        await handle_manager_config_report(update, context)


async def manager_config_report_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handle /manager_config_report with the same access rules as callbacks."""
    await handle_manager_config_report(update, context)


async def handle_manager_config_report(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Build and send the read-only manager config report."""
    user = update.effective_user
    if user is None or not is_admin(user.id):
        await _send_access_denied(update)
        return

    try:
        report = get_manager_config_report(DB_PATH)
        text = format_manager_config_report_telegram(report)
        parts = split_telegram_messages(text)
        await _send_report_parts(update, parts)
    except (sqlite3.Error, OSError):
        logger.exception("Manager Config Report database error")
        await _send_report_error(update)
    except Exception:
        logger.exception("Manager Config Report generation error")
        await _send_report_error(update)


async def _send_access_denied(update: Update) -> None:
    query = update.callback_query
    if query is not None:
        await safe_edit(query, "⛔ Нет доступа.")
    elif update.message is not None:
        await update.message.reply_text("⛔ Нет доступа.")


async def _send_report_error(update: Update) -> None:
    text = "⚠️ Manager Config Report временно недоступен."
    query = update.callback_query
    if query is not None:
        await safe_edit(query, text, reply_markup=_learning_back_keyboard())
    elif update.message is not None:
        await update.message.reply_text(text, reply_markup=_learning_back_keyboard())


async def _send_report_parts(update: Update, parts: list[str]) -> None:
    query = update.callback_query
    if query is not None:
        if len(parts) == 1:
            await safe_edit(query, parts[0], reply_markup=_learning_back_keyboard())
            return

        await safe_edit(query, parts[0])
        for index, part in enumerate(parts[1:], start=1):
            markup = _learning_back_keyboard() if index == len(parts) - 1 else None
            await query.message.reply_text(part, reply_markup=markup)
        return

    if update.message is not None:
        for index, part in enumerate(parts):
            markup = _learning_back_keyboard() if index == len(parts) - 1 else None
            await update.message.reply_text(part, reply_markup=markup)


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _format_last_feedback(value: str | None) -> str:
    if not value:
        return "-"
    return value[:16].replace("T", " ")


def format_manager_config_report_telegram(report: dict[str, Any]) -> str:
    """Format Manager Config Report for plain-text Telegram messages."""
    summary = report.get("summary", {})
    managers = report.get("managers", [])
    unknown = report.get("historical_unknown", {})

    active_managers = int(summary.get("active_managers", 0))
    configs_with_data = int(summary.get("configs_with_data", 0))
    feedback_count = int(summary.get("feedback_count", 0))

    header = (
        "👥 Manager Config Report\n"
        f"Активных менеджеров: {active_managers}\n"
        f"Конфигов с данными: {configs_with_data}\n"
        f"Карточек с feedback: {feedback_count}"
    )

    blocks = [header]
    if active_managers == 0 or not managers:
        blocks.append("Активных менеджеров нет.")
    elif configs_with_data == 0:
        blocks.append("Данных с config_name пока нет.")
    else:
        for manager in managers:
            configs = manager.get("configs", [])
            display_name = manager.get("display_name") or f"manager_{manager['manager_id']}"
            if not configs:
                blocks.append(f"Manager: {display_name}\nДанных по конфигам пока нет.")
                continue

            total_sent = sum(int(item.get("sent_count", 0)) for item in configs)
            total_feedback = sum(int(item.get("feedback_count", 0)) for item in configs)
            if total_feedback == 0:
                blocks.append(
                    f"Manager: {display_name}\n"
                    f"Отправлено: {total_sent}\n"
                    "Feedback: 0\n"
                    "Данных для оценки пока нет."
                )
                continue

            sorted_configs = sorted(
                configs,
                key=lambda item: (
                    -int(item.get("feedback_count", 0)),
                    -int(item.get("sent_count", 0)),
                    str(item.get("config_name", "")),
                ),
            )
            manager_blocks = [f"Manager: {display_name}"]
            for item in sorted_configs:
                reasons = item.get("top_reasons", [])[:3]
                reason_text = ", ".join(
                    f"{reason['reason_code']} {reason['count']}" for reason in reasons
                ) or "-"
                score = int(item.get("interest_score", 0))
                manager_blocks.append(
                    f"{item['config_name']}\n"
                    f"Sent: {item['sent_count']} | Feedback: {item['feedback_count']} "
                    f"({_percent(float(item.get('feedback_rate', 0)))})\n"
                    f"👀 {item['review_count']} ({_percent(float(item.get('review_rate', 0)))}) | "
                    f"🤔 {item['think_count']} ({_percent(float(item.get('think_rate', 0)))}) | "
                    f"⏭ {item['skip_count']} ({_percent(float(item.get('skip_rate', 0)))})\n"
                    f"Score: {score:+d}\n"
                    f"Причины: {reason_text}\n"
                    f"Последняя реакция: {_format_last_feedback(item.get('last_feedback_at'))}"
                )
            blocks.append("\n\n".join(manager_blocks))

    blocks.append(
        "Исторические данные (не участвуют в score)\n"
        f"sent_ads unknown: {int(unknown.get('sent_ads', 0))}\n"
        f"feedback unknown: {int(unknown.get('feedback', 0))}\n"
        f"reaction_details unknown: {int(unknown.get('reaction_details', 0))}"
    )
    return "\n\n".join(blocks)


def split_telegram_messages(
    text: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH
) -> list[str]:
    """Split plain text without exceeding Telegram's message limit."""
    if max_length < 64:
        raise ValueError("max_length must be at least 64")
    if len(text) <= max_length:
        return [text]

    content_limit = max_length - 32
    chunks: list[str] = []
    current = ""

    for paragraph in text.split("\n\n"):
        candidates = _split_oversized_paragraph(paragraph, content_limit)
        for candidate in candidates:
            combined = candidate if not current else f"{current}\n\n{candidate}"
            if len(combined) <= content_limit:
                current = combined
            else:
                if current:
                    chunks.append(current)
                current = candidate
    if current:
        chunks.append(current)

    total = len(chunks)
    return [f"Manager Config Report ({index}/{total})\n\n{chunk}" for index, chunk in enumerate(chunks, 1)]


def _split_oversized_paragraph(paragraph: str, limit: int) -> list[str]:
    if len(paragraph) <= limit:
        return [paragraph]

    chunks: list[str] = []
    current = ""
    for line in paragraph.splitlines() or [paragraph]:
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        combined = line if not current else f"{current}\n{line}"
        if len(combined) <= limit:
            current = combined
        else:
            chunks.append(current)
            current = line
    if current:
        chunks.append(current)
    return chunks


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
