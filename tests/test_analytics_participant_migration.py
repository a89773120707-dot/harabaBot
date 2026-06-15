import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))

from admin_bot.services.db_service import _ensure_telegram_users


def make_old_schema_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE telegram_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            role TEXT DEFAULT 'manager',
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT
        );
        INSERT INTO telegram_users (telegram_id, username, role, status)
        VALUES
            (1, 'active_manager', 'manager', 'active'),
            (2, 'active_owner', 'owner', 'active'),
            (3, 'active_admin', 'admin', 'active'),
            (4, 'paused_manager', 'manager', 'paused'),
            (5, 'pending_manager', 'manager', 'pending'),
            (6, 'disabled_manager', 'manager', 'disabled');
        """
    )
    return conn


def column_names(conn: sqlite3.Connection) -> set[str]:
    return {row["name"] for row in conn.execute("PRAGMA table_info(telegram_users)")}


def test_analytics_participant_column_is_created_and_backfilled():
    conn = make_old_schema_db()

    _ensure_telegram_users(conn)

    rows = conn.execute(
        """
        SELECT telegram_id, role, status, analytics_participant
        FROM telegram_users
        ORDER BY telegram_id
        """
    ).fetchall()

    assert "analytics_participant" in column_names(conn)
    assert [(row["telegram_id"], row["analytics_participant"]) for row in rows] == [
        (1, 1),
        (2, 1),
        (3, 0),
        (4, 0),
        (5, 0),
        (6, 0),
    ]
    assert rows[1]["role"] == "owner"


def test_analytics_participant_migration_is_idempotent():
    conn = make_old_schema_db()

    _ensure_telegram_users(conn)
    conn.execute(
        "UPDATE telegram_users SET analytics_participant = 0 WHERE role = 'owner'"
    )
    _ensure_telegram_users(conn)

    owner = conn.execute(
        "SELECT role, analytics_participant FROM telegram_users WHERE telegram_id = 2"
    ).fetchone()
    indexes = {
        row["name"] for row in conn.execute("PRAGMA index_list(telegram_users)").fetchall()
    }

    assert owner["role"] == "owner"
    assert owner["analytics_participant"] == 0
    assert "idx_telegram_users_analytics_participant" in indexes
