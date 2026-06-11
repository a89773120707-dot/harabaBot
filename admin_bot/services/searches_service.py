"""Сервис поисков — список конфигураций/моделей."""

from datetime import datetime

from admin_bot.services.db_service import get_connection


def get_searches_list() -> list[dict]:
    """Получить список поисков из sent_ads (уникальные model_id)."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT model_id,
                   title,
                   COUNT(*) as cards_count,
                   MIN(first_sent_at) as first_seen,
                   MAX(first_sent_at) as last_seen
            FROM sent_ads
            WHERE model_id IS NOT NULL
            GROUP BY model_id
            ORDER BY cards_count DESC
        """).fetchall()

        searches = []
        for r in rows:
            searches.append({
                "model_id": r["model_id"],
                "title": r["title"],
                "cards_count": r["cards_count"],
                "first_seen": r["first_seen"],
                "last_seen": r["last_seen"],
                "status": "active",  # Пока все active
            })
        return searches
    finally:
        conn.close()


def get_search_detail(model_id: str) -> dict | None:
    """Получить детали по поиску."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT model_id, title,
                      COUNT(*) as cards_count,
                      MIN(first_sent_at) as first_seen,
                      MAX(first_sent_at) as last_seen
               FROM sent_ads
               WHERE model_id = ?
               GROUP BY model_id""",
            (model_id,)
        ).fetchone()

        if not row:
            return None
        return dict(row)
    finally:
        conn.close()
