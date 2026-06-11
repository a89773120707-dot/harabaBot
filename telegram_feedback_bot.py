"""
telegram_feedback_bot.py — Блок 16.7: обработка нажатий кнопок и комментариев.

Логика:
1. Пользователь нажал 🟢/🟡/🔴 → бот сохраняет pending state
2. Бот отвечает: "✍️ Напиши комментарий к решению:"
3. Следующее текстовое сообщение → comment в feedback.db
4. pending state очищается

Запуск:
  python telegram_feedback_bot.py
"""

import json
import os
import sys
import logging
from pathlib import Path
from datetime import datetime

from base import RESULTS_DIR, log
from feedback_store import save_feedback, register_recipient, get_all_recipients, disable_recipient
from card_data_loader import load_card_data

# RIS — Reaction Intelligence System
from ris_reason_keyboard import reason_keyboard, reason_selected_keyboard
from ris_reason_store import save_reaction_detail, get_last_feedback_id

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False
    # Не exit — нужен для теста config
    log.warning("python-telegram-bot не установлен. pip install python-telegram-bot")

# ──────────────────────────────────────────────────────────────
# Настройки
# ──────────────────────────────────────────────────────────────

def load_telegram_config():
    env_path = Path(__file__).parent / ".env"
    bot_token = None
    chat_id = None

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key == "TELEGRAM_BOT_TOKEN":
                    bot_token = val
                elif key == "TELEGRAM_CHAT_ID":
                    chat_id = val

    bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token:
        log.error("TELEGRAM_BOT_TOKEN не найден в .env")
        sys.exit(1)
    if not chat_id:
        log.error("TELEGRAM_CHAT_ID не найден в .env")
        sys.exit(1)

    return bot_token, chat_id


# ──────────────────────────────────────────────────────────────
# Pending state (in-memory)
# ──────────────────────────────────────────────────────────────

pending_feedback = {}  # chat_id -> {"card_id": ..., "action": ..., "card_data": ...}

# RIS — pending для выбора причины реакции
# chat_id -> {"feedback_id": int, "action": str}
pending_reason = {}

# Загрузить данные карточек
card_data = load_card_data()


# ──────────────────────────────────────────────────────────────
# Handlers (только если telegram установлен)
# ──────────────────────────────────────────────────────────────

if HAS_TELEGRAM:
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start."""
        keyboard = [
            [InlineKeyboardButton("📋 Команды", callback_data="help_cmd")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🚗 Haraba Bot v1\n\n"
            "Я отправляю карточки авто из Haraba.\n"
            "Нажимай кнопки под каждой карточкой:\n"
            "🟢 Купить — интересная\n"
            "🟡 Посмотреть — может быть\n"
            "🔴 Скипнуть — не интересно\n\n"
            "После нажатия я попрошу комментарий.",
            reply_markup=reply_markup
        )

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help и callback кнопки."""
        help_text = (
            "📋 **Доступные команды:**\n\n"
            "/start — Главное меню\n"
            "/help — Показать список команд\n"
            "/register_owner — Зарегистрироваться как владелец (получать карточки)\n"
            "/register_manager — Зарегистрироваться как менеджер (получать карточки)\n"
            "/recipients — Показать список всех получателей\n"
            "/disable_me — Отключить себя от рассылки\n\n"
            "🔘 **Кнопки под карточкой:**\n"
            "🟢 Купить — Записать реакцию 'Купить' и попросить комментарий\n"
            "🟡 Посмотреть — Записать реакцию 'Посмотреть' и попросить комментарий\n"
            "🔴 Скипнуть — Записать реакцию 'Скипнуть' и попросить комментарий\n"
            "📖 Описание — Показать полное описание продавца\n"
            "📷 Ещё фото — Показать дополнительные фото автомобиля\n"
        )

        # Если callback — редактируем сообщение, иначе отправляем новое
        if update.callback_query:
            await update.callback_query.edit_message_text(help_text, parse_mode=None)
        else:
            await update.message.reply_text(help_text)

    async def register_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Зарегистрировать как владельца."""
        chat_id = update.message.chat_id
        user = update.message.from_user
        register_recipient(
            chat_id=str(chat_id),
            user_id=str(user.id),
            username=user.username or "",
            first_name=user.first_name or "",
            role="owner"
        )
        await update.message.reply_text("✅ Владелец подключён!")

    async def register_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Зарегистрировать как менеджера."""
        chat_id = update.message.chat_id
        user = update.message.from_user
        register_recipient(
            chat_id=str(chat_id),
            user_id=str(user.id),
            username=user.username or "",
            first_name=user.first_name or "",
            role="manager"
        )
        await update.message.reply_text("✅ Менеджер подключён!")

    async def show_recipients(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список получателей."""
        recipients = get_all_recipients()
        if not recipients:
            await update.message.reply_text("Получателей пока нет.")
            return
        lines = ["📋 Получатели:"]
        for r in recipients:
            status = "✅" if r["enabled"] else "❌"
            lines.append(f"{status} {r['role']}: {r.get('username','?')} (chat: {r['chat_id']})")
        await update.message.reply_text("\n".join(lines))

    async def disable_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отключить себя."""
        chat_id = update.message.chat_id
        disable_recipient(str(chat_id))
        await update.message.reply_text("❌ Вы отключены от рассылки.")


    async def reason_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора причины реакции (RIS)."""
        query = update.callback_query
        await query.answer()

        chat_id = query.message.chat_id
        callback_data = query.data  # e.g. "reason:good_price"

        if callback_data == "reason:none":
            # Менеджер выбрал "без причины"
            pending_reason.pop(chat_id, None)
            # Сразу просим комментарий
            if chat_id in pending_feedback:
                pf = pending_feedback[chat_id]
                action_label = {"buy": "🟢 Купить", "watch": "🟡 Посмотреть", "skip": "🔴 Скипнуть"}.get(pf["action"], pf["action"])
                await query.edit_message_text(
                    f"✍️ {action_label}\n\nНапиши комментарий (или «-» если без комментария):",
                    reply_to_message_id=query.message.message_id,
                )
            return

        if callback_data == "reason_done":
            await query.edit_message_text("✅ Причина записана.")
            return

        # reason:CODE — сохранить причину, потом попросить комментарий
        reason_code = callback_data.split(":", 1)[1]
        pending_reason[chat_id] = reason_code
        log.info(f"RIS: pending reason={reason_code} for chat={chat_id}")

        if chat_id in pending_feedback:
            pf = pending_feedback[chat_id]
            action_label = {"buy": "🟢 Купить", "watch": "🟡 Посмотреть", "skip": "🔴 Скипнуть"}.get(pf["action"], pf["action"])
            await query.edit_message_text(
                f"✅ Причина записана.\n\n✍️ {action_label}\nНапиши комментарий (или «-» если без комментария):",
                reply_to_message_id=query.message.message_id,
            )

    async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатия inline кнопки."""
        query = update.callback_query
        await query.answer()

        callback_data = query.data  # e.g. "buy:173295809"

        # Пропускаем reason: — они обработаны в reason_handler
        if callback_data.startswith("reason:"):
            return
        if callback_data == "help_cmd":
            await help_command(update, context)
            return

        parts = callback_data.split(":", 1)
        if len(parts) != 2:
            await query.edit_message_reply_markup(reply_markup=None)
            return

        action = parts[0]  # buy/watch/skip/desc
        card_id = parts[1]

        # Блок 17.4: кнопка "Описание" — отправить полное описание продавца
        if action == "desc":
            card = card_data.get(card_id, {})
            raw_text = card.get("mobile_detail_raw_text", "")

            # Распарсить описание
            seller_desc = ""
            if raw_text:
                start_marker = "Комментарий продавца"
                end_marker = "Читать дальше"
                start_idx = raw_text.find(start_marker)
                if start_idx != -1:
                    start_idx += len(start_marker)
                    end_idx = raw_text.find(end_marker, start_idx)
                    if end_idx == -1:
                        seller_desc = raw_text[start_idx:].strip()
                    else:
                        seller_desc = raw_text[start_idx:end_idx].strip()
                    seller_desc = " ".join(seller_desc.split())

            title = card.get("title", "Unknown")
            if seller_desc:
                # Telegram лимит 4096 символов
                if len(seller_desc) > 4000:
                    seller_desc = seller_desc[:3990] + "..."
                await query.message.reply_text(
                    f"📖 {title}\n\n{seller_desc}",
                    reply_to_message_id=query.message.message_id,
                )
            else:
                await query.message.reply_text(
                    f"📖 {title}\n\nОписание продавца не найдено.",
                    reply_to_message_id=query.message.message_id,
                )
            return

        # Блок 19.5-19.6: кнопка "Ещё фото" — отправить gallery фото
        if action == "photos":
            card = card_data.get(card_id, {})
            photos = card.get("photos", {})
            gallery = photos.get("gallery", [])

            title = card.get("title", "Unknown")

            # Убираем главное фото (оно уже показано)
            extra_photos = gallery[1:6] if len(gallery) > 1 else []

            if extra_photos:
                await query.message.reply_text(
                    f"📷 {title} — ещё {len(extra_photos)} фото:",
                    reply_to_message_id=query.message.message_id,
                )
                # Отправляем каждое фото отдельно
                for photo_url in extra_photos:
                    try:
                        await query.message.reply_photo(
                            photo=photo_url,
                            reply_to_message_id=query.message.message_id,
                        )
                    except Exception as e:
                        log.error(f"  Error sending photo: {e}")
            else:
                await query.message.reply_text(
                    f"📷 {title}\n\nДополнительных фото не найдено.",
                    reply_to_message_id=query.message.message_id,
                )
            return

        action_labels = {
            "buy": "🟢 Купить",
            "watch": "🟡 Посмотреть",
            "skip": "🔴 Скипнуть",
        }
        action_label = action_labels.get(action, action)

        card = card_data.get(card_id, {})
        title = card.get("title", "Unknown")
        year = card.get("year", "")

        # Сохранить pending state — ВКЛЮЧАЯ message_id карточки
        pending_feedback[query.message.chat_id] = {
            "card_id": card_id,
            "action": action,
            "card_message_id": query.message.message_id,
            "card_data": {
                "card_id": card_id,
                "title": card.get("title", ""),
                "url": card.get("url", ""),
                "model_id": card.get("model_id", ""),
                "price": card.get("price", 0),
                "mileage": card.get("mileage", 0),
                "year": card.get("year", 0),
                "score": card.get("score", 0),
                "decision": card.get("decision", ""),
                "engine": card.get("engine", "unknown"),
                "transmission": card.get("transmission", "unknown"),
                "drive": card.get("drive", "unknown"),
                "region": card.get("region", "unknown"),
                "owners": card.get("owners", "unknown"),
                "legal_restrictions": card.get("legal_restrictions", "unknown"),
                "autoteka_status": card.get("autoteka_status", "unknown"),
                "price_status": card.get("price_status", ""),
                "price_score": card.get("price_score", 0),
                "mileage_score": card.get("mileage_score", 0),
                "engine_score": card.get("engine_score", 0),
                "transmission_score": card.get("transmission_score", 0),
                "equipment_score": card.get("equipment_score", 0),
                "photo_url": card.get("photo_url", ""),
                "photo_count": card.get("photo_count", 0),
                "full_location": card.get("full_location", ""),
            },
        }

        # Убрать кнопки
        await query.edit_message_reply_markup(reply_markup=None)

        # RIS — показать кнопки выбора причины
        await query.message.reply_text(
            f"📋 {action_label}\n\nВыбери причину:",
            reply_markup=reason_keyboard(action),
            reply_to_message_id=query.message.message_id,
        )


    async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстового сообщения (комментарий)."""
        chat_id = update.message.chat_id
        comment = update.message.text.strip()

        if chat_id not in pending_feedback:
            return

        pending = pending_feedback.pop(chat_id)
        card_id = pending["card_id"]
        action = pending["action"]
        card_message_id = pending.get("card_message_id")
        card = pending["card_data"]

        # Получатель info
        user = update.message.from_user
        recipients = get_all_recipients()
        my_role = "viewer"
        for r in recipients:
            if r["chat_id"] == str(chat_id):
                my_role = r["role"]
                break

        action_map = {
            "buy": "buy",
            "watch": "watch",
            "skip": "skip",
        }

        feedback_card = {
            "card_id": card.get("card_id", card_id),
            "url": card.get("url", ""),
            "model_id": card.get("model_id", ""),
            "title": card.get("title", ""),
            "price": card.get("price", 0),
            "mileage": card.get("mileage", 0),
            "engine": card.get("engine", "unknown"),
            "transmission": card.get("transmission", "unknown"),
            "drive": card.get("drive", "unknown"),
            "region": card.get("region", "unknown"),
            "owners": card.get("owners", "unknown"),
            "legal_restrictions": card.get("legal_restrictions", "unknown"),
            "autoteka_status": card.get("autoteka_status", "unknown"),
            "score": card.get("score", 0),
            "telegram_status": card.get("decision", ""),
            "price_status": card.get("price_status", ""),
            "price_score": card.get("price_score", 0),
            "mileage_score": card.get("mileage_score", 0),
            "engine_score": card.get("engine_score", 0),
            "transmission_score": card.get("transmission_score", 0),
            "equipment_score": card.get("equipment_score", 0),
            "photo_url": card.get("photo_url", ""),
            "photo_count": card.get("photo_count", 0),
            "full_location": card.get("full_location", ""),
            "telegram_chat_id": str(chat_id),
            "telegram_user_id": str(user.id),
            "telegram_username": user.username or "",
            "reviewer_role": my_role,
        }

        save_feedback(feedback_card, action_map.get(action, action), comment)

        # RIS — сохранить reason_code
        reason_code = pending_reason.pop(chat_id, None)
        if reason_code:
            last_id = get_last_feedback_id()
            if last_id > 0:
                save_reaction_detail(last_id, reason_code)
                log.info(f"RIS: reason_code={reason_code} saved for feedback_id={last_id}")

        title = card.get("title", "Unknown")
        await update.message.reply_text(
            f"✅ Записано!\n\n"
            f"🚗 {title}\n"
            f"📝 Действие: {action_map.get(action, action)}\n"
            f"💬 Комментарий: {comment if comment != '-' else '(без комментария)'}",
            reply_to_message_id=card_message_id,
        )


    def main():
        bot_token, chat_id = load_telegram_config()

        log.info("Запускаю Feedback Bot...")
        log.info(f"Chat ID: {chat_id}")

        # Авто-регистрация owner из .env
        register_recipient(
            chat_id=str(chat_id),
            user_id="",
            username="",
            first_name="",
            role="owner"
        )
        log.info(f"Owner зарегистрирован: chat_id={chat_id}")

        app = Application.builder().token(bot_token).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("register_owner", register_owner))
        app.add_handler(CommandHandler("register_manager", register_manager))
        app.add_handler(CommandHandler("recipients", show_recipients))
        app.add_handler(CommandHandler("disable_me", disable_me))
        app.add_handler(CallbackQueryHandler(reason_handler, pattern="^reason:"))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

        log.info("Bot запущен. Ожидание сообщений...")
        app.run_polling()


if __name__ == "__main__":
    main()
