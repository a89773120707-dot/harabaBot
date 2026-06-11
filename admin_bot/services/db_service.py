"""Общая работа с SQLite — миграции, подключение, утилиты."""

import os
import sqlite3
from pathlib import Path
from datetime import datetime

from admin_bot.config import DB_PATH, OWNER_ID


def get_connection() -> sqlite3.Connection:
    """Получить подключение к БД."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_db_size() -> float:
    """Получить размер БД в MB."""
    if DB_PATH.exists():
        return DB_PATH.stat().st_size / (1024 * 1024)
    return 0.0


def ensure_tables() -> None:
    """Создать все необходимые таблицы, если их нет."""
    conn = get_connection()
    try:
        _ensure_telegram_users(conn)
        _ensure_pipeline_runs(conn)
        conn.commit()
    finally:
        conn.close()


def _ensure_telegram_users(conn: sqlite3.Connection) -> None:
    """Миграция telegram_users — CREATE IF NOT EXISTS."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telegram_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            role TEXT DEFAULT 'manager',
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT
        )
    """)
    # Проверить индексы
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_telegram_users_status
        ON telegram_users(status)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_telegram_users_role
        ON telegram_users(role)
    """)


def _ensure_pipeline_runs(conn: sqlite3.Connection) -> None:
    """Миграция pipeline_runs — CREATE IF NOT EXISTS."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            finished_at TEXT,
            status TEXT,
            found_count INTEGER,
            sent_count INTEGER,
            duplicate_count INTEGER,
            error_text TEXT
        )
    """)


def ensure_owner_exists() -> None:
    """Автосоздать owner в telegram_users с role=owner, status=active."""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id, role, status FROM telegram_users WHERE telegram_id = ?",
            (OWNER_ID,)
        ).fetchone()

        if existing is None:
            # Создать owner
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                """INSERT INTO telegram_users (telegram_id, role, status, created_at, updated_at)
                   VALUES (?, 'owner', 'active', ?, ?)""",
                (OWNER_ID, now, now)
            )
            print(f"Owner {OWNER_ID} создан в telegram_users")
        else:
            # Убедиться, что role=owner, status=active
            if existing["role"] != "owner" or existing["status"] != "active":
                conn.execute(
                    "UPDATE telegram_users SET role='owner', status='active', updated_at=? WHERE telegram_id=?",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), OWNER_ID)
                )
                print(f"Owner {OWNER_ID} обновлён: role=owner, status=active")
            else:
                print(f"Owner {OWNER_ID} уже существует (role=owner, status=active)")

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    print("Running migrations...")
    ensure_tables()
    ensure_owner_exists()

    # Проверка
    conn = get_connection()
    try:
        users = conn.execute(
            "SELECT telegram_id, role, status FROM telegram_users WHERE telegram_id = ?",
            (OWNER_ID,)
        ).fetchall()
        print(f"\nПроверка telegram_users для OWNER_ID={OWNER_ID}:")
        for u in users:
            print(f"  telegram_id={u['telegram_id']}, role={u['role']}, status={u['status']}")
    finally:
        conn.close()
