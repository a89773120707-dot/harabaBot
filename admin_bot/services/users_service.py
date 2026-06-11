"""Управление пользователями — менеджеры, статусы, роли."""

from datetime import datetime, timedelta

from admin_bot.services.db_service import get_connection
from admin_bot.config import OWNER_ID


def get_all_users() -> list[dict]:
    """Получить всех пользователей с подсчётом реакций за 7 дней."""
    conn = get_connection()
    try:
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

        # Подсчёт реакций за 7 дней
        rows = conn.execute("""
            SELECT
                u.id,
                u.telegram_id,
                u.username,
                u.first_name,
                u.role,
                u.status,
                u.created_at,
                u.updated_at,
                COALESCE(COUNT(f.id), 0) as reactions_7d
            FROM telegram_users u
            LEFT JOIN feedback f ON f.telegram_user_id = u.telegram_id AND f.created_at >= ?
            GROUP BY u.telegram_id
            ORDER BY u.role = 'owner' DESC, u.role = 'admin' DESC, u.created_at ASC
        """, (seven_days_ago,)).fetchall()

        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user(telegram_id: int) -> dict | None:
    """Получить одного пользователя."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM telegram_users WHERE telegram_id = ?",
            (telegram_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_user(telegram_id: int, username: str | None = None, first_name: str | None = None) -> None:
    """Создать или обновить пользователя (при первом /start)."""
    conn = get_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = conn.execute(
            "SELECT id FROM telegram_users WHERE telegram_id = ?",
            (telegram_id,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE telegram_users
                   SET username = COALESCE(?, username),
                       first_name = COALESCE(?, first_name),
                       updated_at = ?
                   WHERE telegram_id = ?""",
                (username, first_name, now, telegram_id)
            )
        else:
            # Owner автоматически создаётся как active, остальные — pending
            role = "owner" if telegram_id == OWNER_ID else "manager"
            status = "active" if telegram_id == OWNER_ID else "pending"
            conn.execute(
                """INSERT INTO telegram_users (telegram_id, username, first_name, role, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (telegram_id, username, first_name, role, status, now, now)
            )
        conn.commit()
    finally:
        conn.close()


def set_user_status(telegram_id: int, new_status: str) -> bool:
    """Изменить статус пользователя.

    Returns:
        True если успешно, False если пользователь не найден.
    """
    if new_status not in ("pending", "active", "paused", "disabled"):
        raise ValueError(f"Неизвестный статус: {new_status}")

    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE telegram_users SET status = ?, updated_at = ? WHERE telegram_id = ?",
            (new_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), telegram_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_active_users() -> list[int]:
    """Получить список telegram_id активных пользователей (для рассылки)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT telegram_id FROM telegram_users WHERE status = 'active'"
        ).fetchall()
        return [r["telegram_id"] for r in rows]
    finally:
        conn.close()
