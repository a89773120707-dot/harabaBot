"""Красивые сообщения для админ-бота."""

from datetime import datetime


def format_welcome(username: str | None = None) -> str:
    name = f"@{username}" if username else "Администратор"
    return (
        f"👋 Привет, {name}!\n\n"
        f"Админ-панель Haraba Mini\n\n"
        f"Выберите раздел:"
    )


def format_user_list(users: list[dict]) -> str:
    if not users:
        return "👥 Менеджеры\n\nСписок пуст."

    lines = ["👥 Менеджеры\n"]
    for i, u in enumerate(users, 1):
        status_icon = {"active": "✅", "paused": "⏸", "disabled": "❌", "pending": "⏳"}.get(u["status"], "?")
        username = f"@{u['username']}" if u.get("username") else str(u["telegram_id"])
        first_name = f" {u['first_name']}" if u.get("first_name") else ""
        reactions_7d = u.get("reactions_7d", 0)
        lines.append(
            f"{i}. {status_icon} {username}{first_name}\n"
            f"   ID: {u['telegram_id']}\n"
            f"   Роль: {u['role']}\n"
            f"   Статус: {u['status']}\n"
            f"   Реакций за 7 дней: {reactions_7d}\n"
        )
    return "\n".join(lines)


def format_user_detail(user: dict) -> str:
    status_icon = {"active": "✅", "paused": "⏸", "disabled": "❌", "pending": "⏳"}.get(user["status"], "?")
    username = f"@{user['username']}" if user.get("username") else "—"
    first_name = user.get("first_name") or "—"
    return (
        f"👤 Профиль пользователя\n\n"
        f"{status_icon} {username} {first_name}\n"
        f"ID: {user['telegram_id']}\n"
        f"Роль: {user['role']}\n"
        f"Статус: {user['status']}\n"
        f"Создан: {user.get('created_at', '—')}\n"
        f"Обновлён: {user.get('updated_at', '—')}"
    )


def format_action_result(action: str, user_id: int, new_status: str) -> str:
    actions = {
        "approve": "✅ Утверждён",
        "pause": "⏸ Поставлен на паузу",
        "resume": "▶️ Возобновлён",
        "disable": "❌ Отключён",
    }
    action_text = actions.get(action, action)
    return f"{action_text}\n\nUser ID: {user_id}\nНовый статус: {new_status}"


def format_db_status(tables_info: list[dict], db_size_mb: float, db_path: str) -> str:
    lines = [
        "🗄 База данных\n",
        f"Файл: {db_path}",
        f"Размер: {db_size_mb:.2f} MB\n",
        "Таблицы:",
    ]
    for t in tables_info:
        lines.append(f"  {t['name']}: {t['count']} строк")
    return "\n".join(lines)


def format_reactions_today(data: dict) -> str:
    """Форматировать реакции за сегодня."""
    total = data["total"]
    by_reaction = data.get("by_reaction", {})
    by_user = data.get("by_user", [])

    lines = [f"👍 Реакции за сегодня\n\nВсего: {total}\n"]

    reaction_icons = {"like": "👍", "dislike": "👎", "fire": "🔥", "skip": "💬", "buy": "🟢", "watch": "🟡"}
    for reaction, count in sorted(by_reaction.items()):
        icon = reaction_icons.get(reaction, "•")
        lines.append(f"{icon} {reaction}: {count}")

    if by_user:
        lines.append("\nПо пользователям:")
        for u in by_user:
            username = f"@{u['username']}" if u.get("username") else f"ID {u['telegram_id']}"
            lines.append(f"  {username}: {u['count']}")

    return "\n".join(lines)


def format_stats_today(stats: dict) -> str:
    """Форматировать статистику за сегодня."""
    return (
        f"📊 Статистика за сегодня\n\n"
        f"Отправлено карточек: {stats['sent_today']}\n"
        f"Реакций: {stats['feedback_today']}\n\n"
        f"👍 Лайков: {stats['likes']}\n"
        f"👎 Дизлайков: {stats['dislikes']}\n"
        f"🔥 Интересных: {stats['fires']}\n\n"
        f"Конверсия отправлено → лайк: {stats['conversion']}%"
    )


def format_pipeline_run(run: dict) -> str:
    status_icon = {"success": "✅", "error": "❌", "running": "🔄"}.get(run.get("status", ""), "❓")
    started = run.get("started_at", "—")
    if started and len(started) > 16:
        started = started[:16].replace("T", " ")
    return (
        f"🧾 Последний запуск\n\n"
        f"{status_icon} Статус: {run.get('status', '—')}\n"
        f"Старт: {started}\n"
        f"Найдено: {run.get('found_count', 0)}\n"
        f"Отправлено: {run.get('sent_count', 0)}\n"
        f"Дубликатов: {run.get('duplicate_count', 0)}\n"
        f"Ошибки: {run.get('error_text', 'Нет') or 'Нет'}"
    )


def format_cards_today(data: dict) -> str:
    """Форматировать карточки за сегодня."""
    lines = [
        f"🚗 Карточки сегодня\n\n"
        f"Найдено: {data['total']}\n"
        f"С реакциями: {data['with_reactions']}\n"
        f"Без реакции: {data['without_reactions']}\n",
        "Последние 20:",
    ]
    for i, c in enumerate(data["cards"][:10], 1):
        reaction_icon = "💬" if c["reaction_count"] > 0 else "⬜"
        price_str = f"{c['price']:,}".replace(",", " ") if c["price"] else "?"
        lines.append(
            f"{i}. {reaction_icon} {c['title'] or 'Unknown'} ({c['year'] or '?'})\n"
            f"   {price_str} ₽ | {c['mileage']:,} км | {c['region'] or '?'}\n"
            f"   Реакции: {c['reaction_count']}"
        )
    return "\n".join(lines)


def format_card_detail(card: dict) -> str:
    """Форматировать детальную карточку."""
    price_str = f"{card['price']:,}".replace(",", " ") if card.get("price") else "?"
    mileage_str = f"{card['mileage']:,}".replace(",", " ") if card.get("mileage") else "?"

    lines = [
        f"🚗 {card.get('title', 'Unknown')}\n\n"
        f"Цена: {price_str} ₽\n"
        f"Пробег: {mileage_str} км\n"
        f"Регион: {card.get('region', '?')}\n"
        f"Год: {card.get('year', '?')}\n"
        f"Score: {card.get('send_count', 0)} отправок\n\n"
        f"Реакции:",
    ]

    reactions = card.get("reactions", [])
    if reactions:
        for r in reactions:
            username = f"@{r['username']}" if r.get("username") else f"ID {r.get('first_name', '?')}"
            comment = f" — {r['comment']}" if r.get("comment") else ""
            lines.append(f"  {r.get('action', '?')} {username}{comment}")
    else:
        lines.append("  Нет реакций")

    return "\n".join(lines)


def format_searches_list(searches: list[dict]) -> str:
    """Форматировать список поисков."""
    if not searches:
        return "🔍 Поиски\n\nСписок пуст."

    lines = ["🔍 Поиски\n"]
    for i, s in enumerate(searches, 1):
        status_icon = "✅" if s.get("status") == "active" else "⏸"
        lines.append(
            f"{i}. {status_icon} {s['model_id']}\n"
            f"   {s.get('title', '')}\n"
            f"   Карточек: {s['cards_count']}"
        )
    return "\n".join(lines)


def format_last_errors(errors: list[dict]) -> str:
    """Форматировать последние ошибки."""
    if not errors:
        return "🧾 Последние ошибки\n\nОшибок нет ✅"

    lines = ["🧾 Последние ошибки\n"]
    for i, e in enumerate(errors, 1):
        started = e.get("started_at", "?")[:16] if e.get("started_at") else "?"
        lines.append(f"{i}. {e.get('error_text', '?')}\n   Время: {started}")
    return "\n".join(lines)


def format_pipeline_summary(summary: dict) -> str:
    """Форматировать общую статистику pipeline."""
    return (
        f"🧾 Pipeline статус\n\n"
        f"Всего запусков: {summary['total_runs']}\n"
        f"Успешных: {summary['success']}\n"
        f"С ошибками: {summary['error']}\n"
        f"Последний: {summary['last_finished'] or '—'}"
    )
