"""Сервис реакций — подсчёт и статистика."""

from datetime import datetime, timedelta

from admin_bot.services.db_service import get_connection


def get_reactions_today() -> dict:
    """Получить сводку реакций за сегодня."""
    today_start = datetime.now().strftime("%Y-%m-%d") + " 00:00:00"

    conn = get_connection()
    try:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM feedback WHERE created_at >= ?",
            (today_start,)
        ).fetchone()["cnt"]

        # Группировка по типу реакции (action в существующей схеме)
        rows = conn.execute(
            """SELECT action, COUNT(*) as cnt
               FROM feedback
               WHERE created_at >= ?
               GROUP BY action""",
            (today_start,)
        ).fetchall()

        by_reaction = {}
        for r in rows:
            by_reaction[r["action"]] = r["cnt"]

        # По пользователям (telegram_user_id в существующей схеме)
        user_rows = conn.execute(
            """SELECT f.telegram_user_id, u.username, COUNT(f.id) as cnt
               FROM feedback f
               LEFT JOIN telegram_users u ON f.telegram_user_id = u.telegram_id
               WHERE f.created_at >= ?
               GROUP BY f.telegram_user_id
               ORDER BY cnt DESC""",
            (today_start,)
        ).fetchall()

        by_user = []
        for r in user_rows:
            tid = r["telegram_user_id"]
            by_user.append({
                "telegram_id": tid,
                "username": r["username"] or str(tid),
                "count": r["cnt"],
            })

        return {
            "total": total,
            "by_reaction": by_reaction,
            "by_user": by_user,
        }
    finally:
        conn.close()


def get_reactions_week() -> dict:
    """Получить сводку реакций за неделю."""
    week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM feedback WHERE created_at >= ?",
            (week_start,)
        ).fetchone()["cnt"]

        rows = conn.execute(
            """SELECT action, COUNT(*) as cnt
               FROM feedback
               WHERE created_at >= ?
               GROUP BY action""",
            (week_start,)
        ).fetchall()

        return {
            "total": total,
            "by_reaction": {r["action"]: r["cnt"] for r in rows},
        }
    finally:
        conn.close()
