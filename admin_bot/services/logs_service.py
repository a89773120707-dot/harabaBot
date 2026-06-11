"""Сервис логов — последний запуск, ошибки, статус pipeline."""

from datetime import datetime

from admin_bot.services.db_service import get_connection


def get_last_run() -> dict | None:
    """Получить последний запуск pipeline."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT * FROM pipeline_runs
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_last_errors(limit: int = 10) -> list[dict]:
    """Получить последние ошибки из pipeline_runs."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT started_at, status, error_text
               FROM pipeline_runs
               WHERE error_text IS NOT NULL AND error_text != ''
               ORDER BY id DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_pipeline_summary() -> dict:
    """Общая статистика по запускам."""
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) as cnt FROM pipeline_runs").fetchone()["cnt"]

        success = conn.execute(
            "SELECT COUNT(*) as cnt FROM pipeline_runs WHERE status = 'success'"
        ).fetchone()["cnt"]

        error = conn.execute(
            "SELECT COUNT(*) as cnt FROM pipeline_runs WHERE status = 'error'"
        ).fetchone()["cnt"]

        last_run = conn.execute(
            "SELECT finished_at FROM pipeline_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()

        return {
            "total_runs": total,
            "success": success,
            "error": error,
            "last_finished": last_run["finished_at"] if last_run else None,
        }
    finally:
        conn.close()
