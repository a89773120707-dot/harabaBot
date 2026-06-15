import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))

from ris_manager_config_report import format_manager_config_report, get_manager_config_report


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
            status TEXT,
            analytics_participant INTEGER NOT NULL DEFAULT 0
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
            comment TEXT,
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


def add_user(
    conn,
    user_id,
    username="",
    first_name="",
    role="manager",
    status="active",
    analytics_participant=1,
):
    conn.execute(
        "INSERT INTO telegram_users VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, username, first_name, role, status, analytics_participant),
    )


def add_sent(conn, manager_id, card_id, config_name, send_count=1):
    conn.execute(
        "INSERT INTO sent_ads VALUES (?, ?, ?, ?, ?)",
        (f"key:{manager_id}:{card_id}", str(manager_id), card_id, config_name, send_count),
    )


def add_feedback(
    conn,
    manager_id,
    card_id,
    config_name,
    action,
    created_at,
    reasons=None,
    comment=None,
):
    cursor = conn.execute(
        """
        INSERT INTO feedback (
            card_id, telegram_chat_id, telegram_user_id, config_name, action, comment, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (card_id, str(manager_id), str(manager_id), config_name, action, comment, created_at),
    )
    for reason in reasons or []:
        conn.execute(
            """
            INSERT INTO reaction_details (feedback_id, reason_code, config_name, created_at)
            VALUES (?, ?, ?, ?)
            """,
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
    add_feedback(
        conn,
        1,
        "card-1",
        "Tiguan",
        "skip",
        "2026-01-01T10:00:00",
        reasons=["high_price"],
        comment="Старый комментарий",
    )
    add_feedback(
        conn,
        1,
        "card-1",
        "Tiguan",
        "review",
        "2026-01-01T11:00:00",
        reasons=["good_price"],
        comment="Берем в работу",
    )

    item = config_for(get_manager_config_report(connection=conn), 1, "Tiguan")

    assert item["feedback_count"] == 1
    assert item["review_count"] == 1
    assert item["skip_count"] == 0
    assert item["interest_score"] == 2
    assert item["top_reasons"] == [
        {"reason_code": "Хорошая цена", "raw_reason_code": "good_price", "count": 1}
    ]
    assert item["manager_comments"] == ["Берем в работу"]


def test_sent_count_uses_sum_and_negative_score_makes_status_red():
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
    assert item["status"] == "RED"
    assert item["confidence"] == "LOW"


def test_sent_without_feedback_has_zero_rates_and_no_summary_data():
    conn = make_db()
    add_user(conn, 1)
    add_sent(conn, 1, "card-1", "Tiguan")

    report = get_manager_config_report(connection=conn)
    item = config_for(report, 1, "Tiguan")
    summary = report["managers"][0]["summary"]

    assert item["feedback_count"] == 0
    assert item["feedback_rate"] == 0
    assert item["review_rate"] == 0
    assert item["last_feedback_at"] is None
    assert item["status"] == "YELLOW"
    assert item["confidence"] == "LOW"
    assert summary["best_configs"] == "данных пока нет"
    assert summary["problem_configs"] == "данных пока нет"


def test_only_active_analytics_participants_are_included():
    conn = make_db()
    add_user(conn, 1, "active")
    add_user(conn, 2, "paused", status="paused", analytics_participant=1)
    add_user(conn, 3, "owner", role="owner", analytics_participant=0)
    add_user(conn, 4, "manager_off", analytics_participant=0)
    add_user(conn, 5, "admin", role="admin", analytics_participant=0)
    for user_id in (1, 2, 3, 4, 5):
        add_sent(conn, user_id, f"card-{user_id}", "Tiguan")

    report = get_manager_config_report(connection=conn)

    assert [m["manager_id"] for m in report["managers"]] == ["1"]
    assert report["summary"]["active_managers"] == 1


def test_owner_with_analytics_participant_is_included_without_role_change():
    conn = make_db()
    add_user(conn, 1, "owner", "Owner", role="owner", analytics_participant=1)
    add_sent(conn, 1, "card-1", "Tiguan")
    add_feedback(conn, 1, "card-1", "Tiguan", "review", "2026-01-01T10:00:00")

    report = get_manager_config_report(connection=conn)

    assert [m["manager_id"] for m in report["managers"]] == ["1"]
    assert config_for(report, 1, "Tiguan")["review_count"] == 1
    assert conn.execute(
        "SELECT role FROM telegram_users WHERE telegram_id = 1"
    ).fetchone()["role"] == "owner"


def test_active_manager_without_analytics_participant_is_excluded():
    conn = make_db()
    add_user(conn, 1, "alice", analytics_participant=0)
    add_sent(conn, 1, "card-1", "Tiguan")

    report = get_manager_config_report(connection=conn)

    assert report["managers"] == []
    assert report["summary"]["active_managers"] == 0


def test_unknown_is_historical_and_unknown_comments_do_not_mix_into_main_report():
    conn = make_db()
    add_user(conn, 1, "alice")
    add_sent(conn, 1, "known", "Tiguan")
    add_sent(conn, 1, "old", "unknown")
    add_feedback(
        conn,
        1,
        "known",
        "Tiguan",
        "think",
        "2026-01-01T10:00:00",
        reasons=[""],
        comment="-",
    )
    add_feedback(
        conn,
        1,
        "old",
        "unknown",
        "skip",
        "2025-01-01T10:00:00",
        reasons=["high_price"],
        comment="Комментарий для unknown",
    )

    report = get_manager_config_report(connection=conn)
    item = config_for(report, 1, "Tiguan")

    assert item["top_reasons"] == []
    assert item["manager_comments"] == []
    assert report["historical_unknown"] == {
        "sent_ads": 1,
        "feedback": 1,
        "reaction_details": 1,
    }
    assert [c["config_name"] for c in report["managers"][0]["configs"]] == ["Tiguan"]


def test_display_name_fallback_and_cli_format_is_russian():
    conn = make_db()
    add_user(conn, 1, "alice", "Alice")
    add_user(conn, 2, "", "Bob")
    add_user(conn, 3)
    add_sent(conn, 1, "one", "Tiguan")
    add_sent(conn, 2, "two", "Tiguan")
    add_sent(conn, 3, "three", "Tiguan")
    add_feedback(
        conn,
        1,
        "one",
        "Tiguan",
        "review",
        "2026-01-01T10:00:00",
        reasons=["high_price", "comment"],
        comment="Отличный вариант",
    )

    report = get_manager_config_report(connection=conn)
    names = [manager["display_name"] for manager in report["managers"]]
    text = format_manager_config_report(report)

    assert names == ["@alice", "Bob", "manager_3"]
    assert "ОТЧЕТ ПО КОНФИГАМ МЕНЕДЖЕРОВ" in text
    assert "Исторические данные (не участвуют в рейтинге и score)" in text
    assert "Что сказал менеджер" in text
    assert "Высокая цена" in text
    assert "Комментарий менеджера" in text
    assert "high_price" not in text
    assert "comment" not in text


def test_multiple_managers_keep_independent_reactions_and_comments():
    conn = make_db()
    add_user(conn, 1, "alice")
    add_user(conn, 2, "bob")
    for manager_id in (1, 2):
        add_sent(conn, manager_id, "same-card", "Tiguan")
    add_feedback(
        conn,
        1,
        "same-card",
        "Tiguan",
        "review",
        "2026-01-01T10:00:00",
        comment="Смотрим",
    )
    add_feedback(
        conn,
        2,
        "same-card",
        "Tiguan",
        "skip",
        "2026-01-01T10:00:00",
        comment="Не подходит",
    )

    report = get_manager_config_report(connection=conn)

    assert config_for(report, 1, "Tiguan")["review_count"] == 1
    assert config_for(report, 1, "Tiguan")["manager_comments"] == ["Смотрим"]
    assert config_for(report, 2, "Tiguan")["skip_count"] == 1
    assert config_for(report, 2, "Tiguan")["manager_comments"] == ["Не подходит"]


def test_status_and_confidence_thresholds():
    conn = make_db()
    add_user(conn, 1, "alice")

    for index in range(5):
        add_sent(conn, 1, f"green-{index}", "GreenCfg", send_count=1)
        add_feedback(
            conn,
            1,
            f"green-{index}",
            "GreenCfg",
            "review",
            f"2026-01-01T10:0{index}:00",
        )

    for index in range(4):
        add_sent(conn, 1, f"yellow-{index}", "YellowCfg", send_count=1)
        add_feedback(
            conn,
            1,
            f"yellow-{index}",
            "YellowCfg",
            "think",
            f"2026-01-02T10:0{index}:00",
        )

    for index in range(20):
        add_sent(conn, 1, f"red-{index}", "RedCfg", send_count=1)
        add_feedback(
            conn,
            1,
            f"red-{index}",
            "RedCfg",
            "skip",
            f"2026-01-03T10:{index:02d}:00",
        )

    report = get_manager_config_report(connection=conn)

    green = config_for(report, 1, "GreenCfg")
    yellow = config_for(report, 1, "YellowCfg")
    red = config_for(report, 1, "RedCfg")

    assert green["status"] == "GREEN"
    assert green["confidence"] == "MEDIUM"
    assert yellow["status"] == "YELLOW"
    assert yellow["confidence"] == "LOW"
    assert red["status"] == "RED"
    assert red["confidence"] == "HIGH"


def test_comments_keep_latest_three_real_values_only():
    conn = make_db()
    add_user(conn, 1, "alice")

    comments = [
        ("card-1", "2026-01-01T10:00:00", ""),
        ("card-2", "2026-01-01T10:01:00", "-"),
        ("card-3", "2026-01-01T10:02:00", "Первый"),
        ("card-4", "2026-01-01T10:03:00", "Второй"),
        ("card-5", "2026-01-01T10:04:00", "Третий"),
        ("card-6", "2026-01-01T10:05:00", "Четвертый"),
    ]
    for card_id, created_at, comment in comments:
        add_sent(conn, 1, card_id, "Tiguan")
        add_feedback(conn, 1, card_id, "Tiguan", "review", created_at, comment=comment)

    add_sent(conn, 1, "unknown-card", "unknown")
    add_feedback(
        conn,
        1,
        "unknown-card",
        "unknown",
        "review",
        "2026-01-01T11:00:00",
        comment="Не должен попасть",
    )

    item = config_for(get_manager_config_report(connection=conn), 1, "Tiguan")

    assert item["manager_comments"] == ["Четвертый", "Третий", "Второй"]


def test_sorting_puts_feedback_first_then_feedback_count_score_and_rate():
    conn = make_db()
    add_user(conn, 1, "alice")

    add_sent(conn, 1, "a-1", "NoFeedback", send_count=2)

    for index in range(2):
        add_sent(conn, 1, f"b-{index}", "NeutralCfg", send_count=2)
    add_feedback(conn, 1, "b-0", "NeutralCfg", "review", "2026-01-01T10:00:00")
    add_feedback(conn, 1, "b-1", "NeutralCfg", "skip", "2026-01-01T10:01:00")

    for index in range(2):
        add_sent(conn, 1, f"c-{index}", "PositiveCfg", send_count=2)
    add_feedback(conn, 1, "c-0", "PositiveCfg", "review", "2026-01-01T10:02:00")
    add_feedback(conn, 1, "c-1", "PositiveCfg", "review", "2026-01-01T10:03:00")

    for index in range(5):
        add_sent(conn, 1, f"d-{index}", "HeavyCfg", send_count=1)
        add_feedback(conn, 1, f"d-{index}", "HeavyCfg", "think", f"2026-01-01T10:{10 + index}:00")

    report = get_manager_config_report(connection=conn)
    manager = next(m for m in report["managers"] if m["manager_id"] == "1")

    assert [item["config_name"] for item in manager["configs"]] == [
        "HeavyCfg",
        "PositiveCfg",
        "NeutralCfg",
        "NoFeedback",
    ]


def test_manager_summary_lists_best_and_problem_configs():
    conn = make_db()
    add_user(conn, 1, "alice")

    fixtures = [
        ("BestCfg", [("review", "2026-01-01T10:00:00"), ("review", "2026-01-01T10:01:00")]),
        ("OkayCfg", [("review", "2026-01-01T10:02:00"), ("think", "2026-01-01T10:03:00")]),
        ("NeutralCfg", [("think", "2026-01-01T10:04:00")]),
        ("BadCfg", [("skip", "2026-01-01T10:05:00")]),
        ("WorstCfg", [("skip", "2026-01-01T10:06:00"), ("skip", "2026-01-01T10:07:00")]),
    ]
    for config_name, actions in fixtures:
        for index, (action, created_at) in enumerate(actions):
            card_id = f"{config_name}-{index}"
            add_sent(conn, 1, card_id, config_name)
            add_feedback(conn, 1, card_id, config_name, action, created_at)

    report = get_manager_config_report(connection=conn)
    summary = report["managers"][0]["summary"]

    assert summary["best_configs"] == [
        "BestCfg (score +4, feedback 2, rate 100.0%)",
        "OkayCfg (score +3, feedback 2, rate 100.0%)",
        "NeutralCfg (score +1, feedback 1, rate 100.0%)",
    ]
    assert summary["problem_configs"] == [
        "WorstCfg (score -4, feedback 2, rate 100.0%)",
        "BadCfg (score -2, feedback 1, rate 100.0%)",
    ]


def test_manager_summary_excludes_zero_and_negative_from_best():
    conn = make_db()
    add_user(conn, 1, "alice")

    fixtures = [
        ("PositiveCfg", [("review", "2026-01-01T10:00:00")]),
        ("ZeroCfg", [("review", "2026-01-01T10:01:00"), ("skip", "2026-01-01T10:02:00")]),
        ("NegativeCfg", [("skip", "2026-01-01T10:03:00")]),
    ]
    for config_name, actions in fixtures:
        for index, (action, created_at) in enumerate(actions):
            card_id = f"{config_name}-{index}"
            add_sent(conn, 1, card_id, config_name)
            add_feedback(conn, 1, card_id, config_name, action, created_at)

    report = get_manager_config_report(connection=conn)
    summary = report["managers"][0]["summary"]

    assert summary["best_configs"] == ["PositiveCfg (score +2, feedback 1, rate 100.0%)"]
    assert summary["problem_configs"] == ["NegativeCfg (score -2, feedback 1, rate 100.0%)"]
