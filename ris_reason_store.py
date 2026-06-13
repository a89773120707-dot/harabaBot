"""RIS — сохранение reaction_details.

Работает поверх существующей feedback_store.py.
Не модифицирует существующую БД — только добавляет записи.
"""

import sqlite3
from datetime import datetime


DB_PATH = "results/feedback.db"

# Причины, требующие комментарий (всё остальное — без комментария)
REASONS_NEED_COMMENT = {
    "review_other",
    "think_other",
    "skip_other",
    "need_more_info",
}


def needs_comment(reason_code: str) -> bool:
    """Нужен ли комментарий для этой причины."""
    return reason_code in REASONS_NEED_COMMENT


def save_reaction_detail(feedback_id: int, reason_code: str | None) -> None:
    """Сохранить reason_code для реакции.

    Args:
        feedback_id: ID записи в feedback (autoincrement).
        reason_code: код причины (good_price, expensive...) или None.
    """
    if reason_code is None:
        return

    conn = sqlite3.connect(DB_PATH)

    # FIX 7A: взять config_name из feedback по feedback_id
    row = conn.execute("SELECT config_name FROM feedback WHERE id = ?", (feedback_id,)).fetchone()
    config_name = row[0] if row and row[0] else "unknown"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO reaction_details (feedback_id, reason_code, config_name, created_at) VALUES (?, ?, ?, ?)",
        (feedback_id, reason_code, config_name, now)
    )
    conn.commit()
    conn.close()


def get_last_feedback_id() -> int:
    """Получить ID последней записи в feedback."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT MAX(id) as max_id FROM feedback").fetchone()
    conn.close()
    return row[0] if row and row[0] else 0


def get_reasons_for_action(action: str) -> list[dict]:
    """Получить список причин для типа реакции."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT reason_code, title FROM reaction_reasons WHERE reaction_type = ?",
        (action,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
