"""Analytics — learning_report, learning_reasons, config_report.

Читает из:
- feedback (reaction, model_id, card_id, comment)
- reaction_details (reason_code, feedback_id)
- sent_ads (model_id, stable_car_key, config info)

Все SQL — read-only, никаких изменений в БД.
"""

import sqlite3
from datetime import datetime


DB_PATH = "results/feedback.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ──────────────────────────────────────────────────────────────
# learning_report — общий отчёт
# ──────────────────────────────────────────────────────────────

def get_learning_report() -> dict:
    """Общий отчёт: реакции по типам, топ модели, топ причины."""
    conn = get_conn()
    result = {}

    # Всего реакций
    total = conn.execute("SELECT COUNT(*) as cnt FROM feedback").fetchone()["cnt"]
    result["total"] = total

    # По типам
    by_type = conn.execute(
        "SELECT action, COUNT(*) as cnt FROM feedback GROUP BY action ORDER BY cnt DESC"
    ).fetchall()
    result["by_type"] = {r["action"]: r["cnt"] for r in by_type}

    # Топ модели
    top_models = conn.execute(
        """SELECT model_id, action, COUNT(*) as cnt
           FROM feedback
           WHERE model_id IS NOT NULL AND model_id != ''
           GROUP BY model_id, action
           ORDER BY cnt DESC
           LIMIT 10"""
    ).fetchall()
    result["top_models"] = [dict(r) for r in top_models]

    # Топ причины
    top_reasons = conn.execute(
        """SELECT rr.reaction_type, rr.reason_code, rr.title, COUNT(*) as cnt
           FROM reaction_details rd
           JOIN reaction_reasons rr ON rd.reason_code = rr.reason_code
           GROUP BY rr.reason_code
           ORDER BY cnt DESC
           LIMIT 10"""
    ).fetchall()
    result["top_reasons"] = [dict(r) for r in top_reasons]

    # Без причины
    no_reason = conn.execute(
        """SELECT COUNT(*) as cnt FROM feedback f
           LEFT JOIN reaction_details rd ON rd.feedback_id = f.id
           WHERE rd.id IS NULL"""
    ).fetchone()["cnt"]
    result["without_reason"] = no_reason

    conn.close()
    return result


# ──────────────────────────────────────────────────────────────
# learning_reasons — причины по группам
# ──────────────────────────────────────────────────────────────

def get_learning_reasons() -> dict:
    """Топ причин для каждой группы реакций."""
    conn = get_conn()
    result = {}

    for reaction_type in ["review", "think", "skip"]:
        rows = conn.execute(
            """SELECT rr.reason_code, rr.title, COUNT(*) as cnt
               FROM reaction_details rd
               JOIN reaction_reasons rr ON rd.reason_code = rr.reason_code
               WHERE rr.reaction_type = ?
               GROUP BY rr.reason_code
               ORDER BY cnt DESC""",
            (reaction_type,)
        ).fetchall()
        result[reaction_type] = [dict(r) for r in rows]

    conn.close()
    return result


# ──────────────────────────────────────────────────────────────
# config_report — отчёт по конфигам/моделям
# ──────────────────────────────────────────────────────────────

def get_config_report() -> dict:
    """Отчёт по моделям: карточки, реакции, причины."""
    conn = get_conn()
    result = {}

    # Список моделей с реакциями
    models = conn.execute(
        """SELECT f.model_id,
                  COUNT(*) as reaction_count,
                  SUM(CASE WHEN f.action = 'review' THEN 1 ELSE 0 END) as review_count,
                  SUM(CASE WHEN f.action = 'think' THEN 1 ELSE 0 END) as think_count,
                  SUM(CASE WHEN f.action = 'skip' THEN 1 ELSE 0 END) as skip_count
           FROM feedback f
           WHERE f.model_id IS NOT NULL AND f.model_id != ''
           GROUP BY f.model_id
           ORDER BY reaction_count DESC"""
    ).fetchall()

    for m in models:
        model_id = m["model_id"]

        # Причины по этой модели
        reasons = conn.execute(
            """SELECT rr.reaction_type, rr.reason_code, rr.title, COUNT(*) as cnt
               FROM reaction_details rd
               JOIN reaction_reasons rr ON rd.reason_code = rr.reason_code
               JOIN feedback f ON rd.feedback_id = f.id
               WHERE f.model_id = ?
               GROUP BY rr.reason_code
               ORDER BY cnt DESC""",
            (model_id,)
        ).fetchall()

        result[model_id] = {
            "reaction_count": m["reaction_count"],
            "review": m["review_count"],
            "think": m["think_count"],
            "skip": m["skip_count"],
            "reasons": [dict(r) for r in reasons],
        }

    conn.close()
    return result
