import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))

from ris_manager_config_report import (
    format_manager_config_report,
    get_manager_config_report,
)


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE telegram_users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            role TEXT,
            status TEXT
        );
        CREATE TABLE sent_ads (
            stable_car_key TEXT,
            chat_id TEXT,
            card_id TEXT,
            config_name TEXT,
            send_count INTEGER,
            PRIMARY KEY (stable_car_key, chat_id)
        );
        CREATE TABLE feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT,
            telegram_chat_id TEXT,
            telegram_user_id TEXT,
            config_name TEXT,
            action TEXT,
            created_at TEXT
        );
        CREATE TABLE reaction_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id INTEGER,
            reason_code TEXT,
            config_name TEXT,
            created_at TEXT
        );
        """
    )
    return conn


def add_user(conn, user_id, username="", first_name="", role="manager", status="active"):
    conn.execute(
        "INSERT INTO telegram_users VALUES (?, ?, ?, ?, ?)",
        (user_id, username, first_name, role, status),
    )


def add_sent(conn, manager_id, card_id, config_name, send_count=1):
    conn.execute(
        "INSERT INTO sent_ads VALUES (?, ?, ?, ?, ?)",
        (f"key:{manager_id}:{card_id}", str(manager_id), card_id, config_name, send_count),
    )


def add_feedback(conn, manager_id, card_id, config_name, action, created_at, reason=None):
    cursor = conn.execute(
        """
        INSERT INTO feedback (
            card_id, telegram_chat_id, telegram_user_id, config_name, action, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (card_id, str(manager_id), str(manager_id), config_name, action, created_at),
    )
    if reason is not None:
        conn.execute(
            "INSERT INTO reaction_details (feedback_id, reason_code, config_name, created_at) VALUES (?, ?, ?, ?)",
            (cursor.lastrowid, reason, config_name, created_at),
        )
    return cursor.lastrowid


def config_for(report, manager_id, config_name):
    manager = next(m for m in report["managers"] if m["manager_id"] == str(manager_id))
    return next(c for c in manager["configs"] if c["config_name"] == config_name)


def test_latest_feedback_wins_and_card_is_counted_once():
    conn = make_db()
    add_user(conn, 1, "alice")
    add_sent(conn, 1, "card-1", "Tiguan")
    add_feedback(conn, 1, "card-1", "Tiguan", "skip", "2026-01-01T10:00:00", "high_price")
    add_feedback(conn, 1, "card-1", "Tiguan", "review", "2026-01-01T11:00:00", "good_price")

    item = config_for(get_manager_config_report(connection=conn), 1, "Tiguan")

    assert item["feedback_count"] == 1
    assert item["review_count"] == 1
    assert item["skip_count"] == 0
    assert item["interest_score"] == 2
    assert item["top_reasons"] == [{"reason_code": "good_price", "count": 1}]


def test_sent_count_uses_sum_and_rates_use_unique_cards():
    conn = make_db()
    add_user(conn, 1, first_name="Alice")
    add_sent(conn, 1, "card-1", "Tiguan", send_count=3)
    add_sent(conn, 1, "card-2", "Tiguan", send_count=1)
    add_feedback(conn, 1, "card-1", "Tiguan", "think", "2026-01-01T10:00:00")
    add_feedback(conn, 1, "card-2", "Tiguan", "skip", "2026-01-01T11:00:00")

    item = config_for(get_manager_config_report(connection=conn), 1, "Tiguan")

    assert item["sent_count"] == 4
    assert item["feedback_count"] == 2
    assert item["feedback_rate"] == 0.5
    assert item["think_rate"] == 0.5
    assert item["skip_rate"] == 0.5
    assert item["interest_score"] == -1


def test_sent_without_feedback_has_zero_rates():
    conn = make_db()
    add_user(conn, 1)
    add_sent(conn, 1, "card-1", "Tiguan")

    item = config_for(get_manager_config_report(connection=conn), 1, "Tiguan")

    assert item["feedback_count"] == 0
    assert item["feedback_rate"] == 0
    assert item["review_rate"] == 0
    assert item["last_feedback_at"] is None


def test_only_active_managers_are_included_and_owner_is_excluded():
    conn = make_db()
    add_user(conn, 1, "active")
    add_user(conn, 2, "paused", status="paused")
    add_user(conn, 3, "owner", role="owner")
    for user_id in (1, 2, 3):
        add_sent(conn, user_id, f"card-{user_id}", "Tiguan")

    report = get_manager_config_report(connection=conn)

    assert [m["manager_id"] for m in report["managers"]] == ["1"]
    assert report["summary"]["active_managers"] == 1


def test_unknown_is_historical_and_empty_reasons_are_excluded():
    conn = make_db()
    add_user(conn, 1, "alice")
    add_sent(conn, 1, "known", "Tiguan")
    add_sent(conn, 1, "old", "unknown")
    add_feedback(conn, 1, "known", "Tiguan", "think", "2026-01-01T10:00:00", "")
    add_feedback(conn, 1, "old", "unknown", "skip", "2025-01-01T10:00:00", "high_price")

    report = get_manager_config_report(connection=conn)
    item = config_for(report, 1, "Tiguan")

    assert item["top_reasons"] == []
    assert report["historical_unknown"] == {
        "sent_ads": 1,
        "feedback": 1,
        "reaction_details": 1,
    }
    assert [c["config_name"] for c in report["managers"][0]["configs"]] == ["Tiguan"]


def test_display_name_fallback_and_cli_format():
    conn = make_db()
    add_user(conn, 1, "alice", "Alice")
    add_user(conn, 2, "", "Bob")
    add_user(conn, 3)
    add_sent(conn, 1, "one", "Tiguan")
    add_sent(conn, 2, "two", "Tiguan")
    add_sent(conn, 3, "three", "Tiguan")

    report = get_manager_config_report(connection=conn)
    names = [manager["display_name"] for manager in report["managers"]]
    text = format_manager_config_report(report)

    assert names == ["@alice", "Bob", "manager_3"]
    assert "MANAGER CONFIG REPORT V1" in text
    assert "Historical data (excluded from ratings)" in text


def test_multiple_managers_keep_independent_reactions():
    conn = make_db()
    add_user(conn, 1, "alice")
    add_user(conn, 2, "bob")
    for manager_id in (1, 2):
        add_sent(conn, manager_id, "same-card", "Tiguan")
    add_feedback(conn, 1, "same-card", "Tiguan", "review", "2026-01-01T10:00:00")
    add_feedback(conn, 2, "same-card", "Tiguan", "skip", "2026-01-01T10:00:00")

    report = get_manager_config_report(connection=conn)

    assert config_for(report, 1, "Tiguan")["review_count"] == 1
    assert config_for(report, 2, "Tiguan")["skip_count"] == 1
