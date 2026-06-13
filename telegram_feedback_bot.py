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
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

from base import RESULTS_DIR, log
from feedback_store import save_feedback, register_recipient, upsert_telegram_user, get_all_recipients, disable_recipient
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

async def upsert_and_notify(user, role="manager", status="pending"):
    """Upsert user into telegram_users and notify owner if new pending."""
    import sqlite3
    from pathlib import Path
    from feedback_store import get_conn
    from base import log

    telegram_id = user.id
    username = user.username or ""
    first_name = user.first_name or ""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    c = conn.cursor()

    existing = c.execute(
        "SELECT status FROM telegram_users WHERE telegram_id = ?",
        (telegram_id,)
    ).fetchone()

    if not existing:
        # NEW user → insert as pending
        c.execute("""
            INSERT INTO telegram_users (telegram_id, username, first_name, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (telegram_id, username, first_name, role, status, now, now))
        conn.commit()
        conn.close()
        return "new"
    else:
        conn.close()
        return existing["status"]


# Загрузить данные карточек
card_data = load_card_data()


# ──────────────────────────────────────────────────────────────
# Handlers (только если telegram установлен)
# ──────────────────────────────────────────────────────────────

if HAS_TELEGRAM:
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start — авто-регистрация менеджеров."""
        user = update.effective_user
        telegram_id = user.id

        result = await upsert_and_notify(user, role="manager")

        if result == "new":
            await update.message.reply_text(
                f"✅ Заявка на подключение отправлена.\n\n"
                f"👤 {user.first_name or 'Пользователь'}"
                f"{' @' + user.username if user.username else ''}\n"
                f"🆔 ID: {telegram_id}\n\n"
                f"Ожидайте подтверждения администратора."
            )
            # Уведомить owner
            OWNER_ID = 8992376203
            try:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=(
                        f"🆕 Новый пользователь ожидает подтверждения:\n\n"
                        f"👤 {user.first_name or 'Пользователь'}"
                        f"{' @' + user.username if user.username else ''}\n"
                        f"🆔 ID: {telegram_id}\n\n"
                        f"Откройте админ-бот → 👥 Менеджеры → Approve"
                    )
                )
            except Exception as e:
                log.warning(f"Не удалось уведомить owner: {e}")
            return

        status_messages = {
            "pending": "⏳ Ваша заявка уже ожидает подтверждения.",
            "active": "✅ Вы уже подключены к рассылке.",
            "paused": "⏸ Вы временно отключены от рассылки. Обратитесь к администратору.",
            "disabled": "⛔ Доступ отключён. Обратитесь к администратору.",
        }

        msg = status_messages.get(result, "✅ Вы подключены.")
        await update.message.reply_text(msg)

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
        """Зарегистрировать как владельца (только для owner_id из .env)."""
        user = update.effective_user
        telegram_id = user.id

        # Только owner_id может зарегистрироваться как owner
        OWNER_ID = 8992376203
        if telegram_id != OWNER_ID:
            await update.message.reply_text("⛔ Эта команда только для владельца.")
            return

        # Upsert as owner, always active
        from feedback_store import get_conn
        conn = get_conn()
        c = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = c.execute(
            "SELECT id FROM telegram_users WHERE telegram_id = ?",
            (telegram_id,)
        ).fetchone()

        if not existing:
            c.execute("""
                INSERT INTO telegram_users (telegram_id, username, first_name, role, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'active', ?, ?)
            """, (telegram_id, user.username or "", user.first_name or "", "owner", now, now))
        else:
            c.execute("""
                UPDATE telegram_users SET role='owner', status='active',
                    username = COALESCE(NULLIF(?,''), username),
                    first_name = COALESCE(NULLIF(?,''), first_name),
                    updated_at = ?
                WHERE telegram_id = ?
            """, (user.username or "", user.first_name or "", now, telegram_id))

        conn.commit()
        conn.close()
        await update.message.reply_text("✅ Владелец подключён!")

    async def register_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Зарегистрировать как менеджера → status=pending."""
        user = update.effective_user
        result = await upsert_and_notify(user, role="manager", status="pending")

        if result == "new":
            await update.message.reply_text(
                f"✅ Заявка на подключение отправлена.\n"
                f"Ожидайте подтверждения администратора."
            )
        else:
            status_messages = {
                "pending": "⏳ Ваша заявка уже ожидает подтверждения.",
                "active": "✅ Вы уже подключены к рассылке.",
                "paused": "⏸ Вы временно отключены.",
                "disabled": "⛔ Доступ отключён.",
            }
            await update.message.reply_text(status_messages.get(result, "✅ Вы подключены."))

    async def show_recipients(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список активных получателей."""
        from feedback_store import get_enabled_recipients
        recipients = get_enabled_recipients()
        if not recipients:
            await update.message.reply_text("Получателей пока нет.")
            return
        lines = ["📋 Активные получатели:"]
        for r in recipients:
            lines.append(f"✅ {r['role']}: {r.get('username','?')} (chat: {r['chat_id']})")
        await update.message.reply_text("\n".join(lines))

    async def disable_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отключить себя."""
        chat_id = update.message.chat_id
        disable_recipient(str(chat_id))
        await update.message.reply_text("❌ Вы отключены от рассылки.")


    # ──────────────────────────────────────────────────────────────
    # RIS helpers
    # ──────────────────────────────────────────────────────────────

    def _get_reason_title(reason_code: str) -> str:
        """Получить читаемое название причины."""
        titles = {
            "good_price": "Хорошая цена",
            "good_condition": "Хорошее состояние",
            "low_mileage": "Небольшой пробег",
            "few_owners": "Мало владельцев",
            "good_history": "Хорошая история",
            "good_equipment": "Хорошая комплектация",
            "liquid_model": "Ликвидная модель",
            "good_region": "Хороший регион",
            "review_other": "Другое",
            "high_price": "Высокая цена",
            "high_mileage": "Большой пробег",
            "many_owners": "Много владельцев",
            "bad_color": "Не нравится цвет",
            "poor_equipment": "Слабая комплектация",
            "history_questions": "Есть вопросы по истории",
            "bad_modification": "Неудачная модификация",
            "bad_region": "Неудобный регион",
            "need_more_info": "Нужно изучить подробнее",
            "think_other": "Другое",
            "not_my_model": "Не моя модель",
            "not_my_segment": "Не мой сегмент",
            "too_expensive": "Слишком дорого",
            "too_mileage": "Слишком большой пробег",
            "bad_condition": "Плохое состояние",
            "legal_risk": "Юридические риски",
            "illiquid": "Неликвид",
            "skip_other": "Другое",
        }
        return titles.get(reason_code, reason_code)


    def _save_feedback_for_chat(chat_id: int, pf: dict, user) -> None:
        """Сохранить feedback из pending_feedback."""
        from feedback_store import save_feedback
        action_map = {"review": "review", "think": "think", "skip": "skip"}
        card = pf["card_data"]

        recipients = get_all_recipients()
        my_role = "viewer"
        for r in recipients:
            if r["chat_id"] == str(chat_id):
                my_role = r["role"]
                break

        feedback_card = {
            "card_id": card.get("card_id", pf["card_id"]),
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
            "config_name": card.get("config_name", ""),
        }
        save_feedback(feedback_card, action_map.get(pf["action"], pf["action"]), "-")
        log.info(f"RIS: feedback saved for card_id={pf['card_id']}, action={pf['action']}")


    async def reason_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора причины реакции (RIS)."""
        from ris_reason_store import needs_comment, save_reaction_detail, get_last_feedback_id
        from ris_reason_keyboard import reason_keyboard, REACTION_PROMPTS

        query = update.callback_query
        await query.answer()

        try:
            chat_id = query.message.chat_id
            callback_data = query.data

            log.info(f"RIS: callback={callback_data}, chat={chat_id}")

            # Toggle: показать основные причины
            if callback_data.startswith("reasons_main:"):
                action = callback_data.split(":", 1)[1]
                prompt = REACTION_PROMPTS.get(action, "Выбери причину:")
                await query.edit_message_text(prompt, reply_markup=reason_keyboard(action, show_extra=False))
                return

            # Toggle: показать дополнительные причины
            if callback_data.startswith("reasons_extra:"):
                action = callback_data.split(":", 1)[1]
                await query.edit_message_text("➕ Дополнительные причины:", reply_markup=reason_keyboard(action, show_extra=True))
                return

            # 💬 Написать комментарий — сразу просим комментарий
            if callback_data == "reason:comment":
                if chat_id in pending_feedback:
                    pf = pending_feedback[chat_id]
                    action_label = {"review": "👀 Посмотреть", "think": "🤔 Подумать", "skip": "⏭ Скип"}.get(pf["action"], pf["action"])
                    # Сохраняем pending_reason как "comment" чтобы пометить что это пользовательский комментарий
                    pending_reason[chat_id] = "comment"
                    await query.edit_message_text("✍️ Напиши комментарий:")
                    await query.message.reply_text(
                        f"✍️ {action_label}\nНапиши комментарий (или «-» если передумал):",
                        reply_to_message_id=query.message.message_id,
                    )
                return

            if callback_data == "reason:none":
                if chat_id in pending_feedback:
                    pending_feedback.pop(chat_id)
                pending_reason.pop(chat_id, None)
                await query.edit_message_text("✅ Реакция сохранена.")
                return

            if callback_data == "reason_done":
                await query.edit_message_text("✅ Причина записана.")
                return

            reason_code = callback_data.split(":", 1)[1]

            if chat_id not in pending_feedback:
                await query.edit_message_text("❌ Ошибка: реакция не найдена.")
                return

            pf = pending_feedback[chat_id]
            action_label = {"review": "👀 Посмотреть", "think": "🤔 Подумать", "skip": "⏭ Скип"}.get(pf["action"], pf["action"])

            if needs_comment(reason_code):
                pending_reason[chat_id] = reason_code
                log.info(f"RIS: pending reason={reason_code} (need comment)")
                await query.edit_message_text("✍️ Напиши комментарий:")
                await query.message.reply_text(
                    f"✍️ {action_label}\nНапиши комментарий (или «-» если без комментария):",
                    reply_to_message_id=query.message.message_id,
                )
                return

            # Стандартная причина — сразу сохраняем
            pending_reason[chat_id] = reason_code
            _save_feedback_for_chat(chat_id, pf, update.effective_user)

            last_id = get_last_feedback_id()
            if last_id > 0:
                save_reaction_detail(last_id, reason_code)
                log.info(f"RIS: reason_code={reason_code} saved for feedback_id={last_id}")

            pending_feedback.pop(chat_id, None)
            pending_reason.pop(chat_id, None)

            reason_title = _get_reason_title(reason_code)
            await query.edit_message_text(
                f"✅ Реакция сохранена\n\n"
                f"Тип: {action_label}\n"
                f"Причина: {reason_title}"
            )

        except Exception as e:
            log.error(f"RIS reason_handler ERROR: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Ошибка: {e}")

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
            "review": "👀 Посмотреть",
            "think": "🤔 Подумать",
            "skip": "⏭ Скип",
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

        # RIS — показать кнопки выбора причины с улучшенным промптом
        from ris_reason_keyboard import REACTION_PROMPTS
        prompt = REACTION_PROMPTS.get(action, f"📋 {action_label}\n\nВыбери причину:")
        await query.message.reply_text(
            prompt,
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
            "review": "review",
            "think": "think",
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
            "config_name": card.get("config_name", ""),
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

        # Авто-регистрация owner из .env (upsert, не перезаписывает status)
        upsert_telegram_user(
            telegram_id=int(chat_id),
            username="",
            first_name="",
            role="owner",
            status="active",
        )
        log.info(f"Owner обеспечен: chat_id={chat_id}")

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
