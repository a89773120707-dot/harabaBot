"""Сервис статистики — карточки, отправки, конверсия."""

from datetime import datetime, timedelta

from admin_bot.services.db_service import get_connection


def get_stats_today() -> dict:
    """Получить статистику за сегодня."""
    today_start = datetime.now().strftime("%Y-%m-%d") + " 00:00:00"

    conn = get_connection()
    try:
        # Количество отправленных сегодня (first_sent_at в существующей схеме)
        sent_today = conn.execute(
            "SELECT COUNT(*) as cnt FROM sent_ads WHERE first_sent_at >= ?",
            (today_start,)
        ).fetchone()["cnt"]

        # Количество реакций сегодня
        feedback_today = conn.execute(
            "SELECT COUNT(*) as cnt FROM feedback WHERE created_at >= ?",
            (today_start,)
        ).fetchone()["cnt"]

        # Реакции по типам сегодня (action в существующей схеме)
        reaction_rows = conn.execute(
            """SELECT action, COUNT(*) as cnt
               FROM feedback
               WHERE created_at >= ?
               GROUP BY action""",
            (today_start,)
        ).fetchall()

        by_reaction = {r["action"]: r["cnt"] for r in reaction_rows}

        likes = by_reaction.get("like", by_reaction.get("👍", by_reaction.get("buy", 0)))
        dislikes = by_reaction.get("dislike", by_reaction.get("👎", by_reaction.get("skip", 0)))
        fires = by_reaction.get("fire", by_reaction.get("🔥", by_reaction.get("watch", 0)))

        # Конверсия: лайки / отправлено
        conversion = round((likes / sent_today * 100), 1) if sent_today > 0 else 0

        return {
            "sent_today": sent_today,
            "feedback_today": feedback_today,
            "likes": likes,
            "dislikes": dislikes,
            "fires": fires,
            "conversion": conversion,
        }
    finally:
        conn.close()


def get_stats_week() -> dict:
    """Получить статистику за неделю."""
    week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        sent = conn.execute(
            "SELECT COUNT(*) as cnt FROM sent_ads WHERE created_at >= ?",
            (week_start,)
        ).fetchone()["cnt"]

        feedback = conn.execute(
            "SELECT COUNT(*) as cnt FROM feedback WHERE created_at >= ?",
            (week_start,)
        ).fetchone()["cnt"]

        return {"sent": sent, "feedback": feedback}
    finally:
        conn.close()


def get_top_models(limit: int = 5) -> list[dict]:
    """Топ моделей по реакциям."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT f.card_id, COUNT(*) as reaction_count
            FROM feedback f
            GROUP BY f.card_id
            ORDER BY reaction_count DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
