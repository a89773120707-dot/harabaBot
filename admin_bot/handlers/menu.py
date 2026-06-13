"""Handler: главное меню и навигация через callback_data."""

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from admin_bot.keyboards import (
    main_menu_keyboard,
    users_list_keyboard,
    user_detail_keyboard,
    back_keyboard,
)
from admin_bot.formatting import (
    format_user_list,
    format_user_detail,
    format_action_result,
    format_reactions_today,
    format_stats_today,
    format_db_status,
    format_cards_today,
    format_card_detail,
    format_searches_list,
    format_last_errors,
    format_pipeline_summary,
    format_pipeline_run,
)
from admin_bot.permissions import is_admin, can_modify_user
from admin_bot.services.users_service import get_all_users, get_user, set_user_status
from admin_bot.services.reactions_service import get_reactions_today
from admin_bot.services.stats_service import get_stats_today
from admin_bot.services.db_service import get_connection, get_db_size
from admin_bot.services.cards_service import get_cards_today, get_card_detail
from admin_bot.services.searches_service import get_searches_list
from admin_bot.services.logs_service import get_last_run, get_last_errors, get_pipeline_summary
from admin_bot.config import DB_PATH


async def safe_edit(query, text, reply_markup=None):
    """Безопасное редактирование — игнор "Message is not modified"."""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except BadRequest as e:
        if "not modified" in str(e):
            pass  # Ничего не изменилось — это нормально
        else:
            raise


async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки главного меню."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        await safe_edit(query, "⛔ Нет доступа.")
        return

    data = query.data

    if data == "back_to_menu":
        await safe_edit(query, "Главное меню:", reply_markup=main_menu_keyboard())
        return

    if data == "menu_stats":
        stats = get_stats_today()
        text = format_stats_today(stats)
        await safe_edit(query, text, reply_markup=back_keyboard())
        return

    if data == "menu_reactions":
        reactions = get_reactions_today()
        text = format_reactions_today(reactions)
        await safe_edit(query, text, reply_markup=back_keyboard())
        return

    if data == "menu_users":
        users = get_all_users()
        # Преобразуем для форматтера
        users_data = [
            {
                "telegram_id": u["telegram_id"],
                "username": u["username"],
                "first_name": u["first_name"],
                "role": u["role"],
                "status": u["status"],
                "reactions_7d": u.get("reactions_7d", 0),
            }
            for u in users
        ]
        text = format_user_list(users_data)
        await safe_edit(query, text, reply_markup=users_list_keyboard(users_data))
        return

    if data == "menu_db":
        text = await _format_db_status()
        await safe_edit(query, text, reply_markup=back_keyboard())
        return

    if data == "menu_cards":
        cards_data = get_cards_today()
        text = format_cards_today(cards_data)
        await safe_edit(query, text, reply_markup=back_keyboard())
        return

    if data == "menu_searches":
        searches = get_searches_list()
        text = format_searches_list(searches)
        await safe_edit(query, text, reply_markup=back_keyboard())
        return

    if data == "menu_logs":
        summary = get_pipeline_summary()
        text = format_pipeline_summary(summary)
        await safe_edit(query, text, reply_markup=back_keyboard())
        return

    if data == "menu_learning":
        # Перенаправить на learning handler
        from admin_bot.handlers.learning import learning_callback_handler
        await learning_callback_handler(update, context)
        return


async def user_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий с пользователями."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        await safe_edit(query, "⛔ Нет доступа.")
        return

    data = query.data

    # user_detail:ID
    if data.startswith("user_detail:"):
        target_id = int(data.split(":")[1])
        user = get_user(target_id)
        if not user:
            await safe_edit(query, "Пользователь не найден.")
            return
        text = format_user_detail(user)
        await safe_edit(query, text, reply_markup=user_detail_keyboard(target_id))
        return

    # user_approve/pause/resume/disable:ID
    action_map = {
        "user_approve": "active",
        "user_pause": "paused",
        "user_resume": "active",
        "user_disable": "disabled",
    }

    for prefix, new_status in action_map.items():
        if data.startswith(f"{prefix}:"):
            target_id = int(data.split(":")[1])

            # Проверка прав
            can, reason = can_modify_user(user_id, target_id)
            if not can:
                await safe_edit(query, reason)
                return

            action = prefix.replace("user_", "")
            success = set_user_status(target_id, new_status)
            if success:
                text = format_action_result(action, target_id, new_status)
            else:
                text = "❌ Пользователь не найден."
            await safe_edit(query, text, reply_markup=back_keyboard())
            return


async def _format_db_status() -> str:
    """Форматировать статус БД."""
    size_mb = get_db_size()
    conn = get_connection()
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        tables_info = []
        for t in tables:
            count = conn.execute(f'SELECT COUNT(*) as cnt FROM "{t["name"]}"').fetchone()["cnt"]
            tables_info.append({"name": t["name"], "count": count})
        from admin_bot.formatting import format_db_status as _fmt
        return _fmt(tables_info, size_mb, str(DB_PATH))
    finally:
        conn.close()
