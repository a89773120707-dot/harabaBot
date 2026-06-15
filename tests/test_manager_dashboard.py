import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))

from ris_manager_dashboard import format_manager_dashboard, get_manager_dashboard


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


def add_feedback(
    conn,
    manager_id,
    card_id,
    config_name,
    action,
    created_at,
    *,
    comment=None,
    reasons=None,
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
            "INSERT INTO reaction_details (feedback_id, reason_code, config_name, created_at) "
            "VALUES (?, ?, ?, ?)",
            (cursor.lastrowid, reason, config_name, created_at),
        )
    return cursor.lastrowid


def manager_for(dashboard, manager_id):
    return next(
        manager
        for manager in dashboard["managers"]
        if manager["manager_id"] == str(manager_id)
    )


def test_empty_database():
    dashboard = get_manager_dashboard(connection=make_db())

    assert dashboard == {
        "summary": {
            "active_managers": 0,
            "sent_count": 0,
            "feedback_count": 0,
            "feedback_rate": 0,
        },
        "managers": [],
    }


def test_manager_without_feedback():
    conn = make_db()
    add_user(conn, 1, "alice")
    add_sent(conn, 1, "card-1", "Tiguan", send_count=3)

    manager = manager_for(get_manager_dashboard(connection=conn), 1)

    assert manager["sent_count"] == 3
    assert manager["feedback_count"] == 0
    assert manager["feedback_rate"] == 0
    assert manager["best_configs"] == []
    assert manager["problem_configs"] == []


def test_manager_with_feedback_has_totals_and_rate():
    conn = make_db()
    add_user(conn, 1, "alice")
    add_sent(conn, 1, "card-1", "Tiguan", send_count=2)
    add_sent(conn, 1, "card-2", "Kuga", send_count=2)
    add_feedback(conn, 1, "card-1", "Tiguan", "review", "2026-01-01T10:00:00")

    dashboard = get_manager_dashboard(connection=conn)
    manager = manager_for(dashboard, 1)

    assert manager["sent_count"] == 4
    assert manager["feedback_count"] == 1
    assert manager["feedback_rate"] == 0.25
    assert dashboard["summary"]["feedback_rate"] == 0.25


def test_best_configs_are_positive_and_limited_to_three():
    conn = make_db()
    add_user(conn, 1, "alice")
    for index, config_name in enumerate(("A", "B", "C", "D")):
        card_id = f"card-{index}"
        add_sent(conn, 1, card_id, config_name)
        add_feedback(conn, 1, card_id, config_name, "review", f"2026-01-01T10:0{index}:00")

    best = manager_for(get_manager_dashboard(connection=conn), 1)["best_configs"]

    assert [item["config_name"] for item in best] == ["A", "B", "C"]
    assert all(item["interest_score"] > 0 for item in best)


def test_problem_configs_are_negative_and_limited_to_three():
    conn = make_db()
    add_user(conn, 1, "alice")
    for index, config_name in enumerate(("A", "B", "C", "D")):
        card_id = f"card-{index}"
        add_sent(conn, 1, card_id, config_name)
        add_feedback(conn, 1, card_id, config_name, "skip", f"2026-01-01T10:0{index}:00")

    problems = manager_for(get_manager_dashboard(connection=conn), 1)["problem_configs"]

    assert [item["config_name"] for item in problems] == ["A", "B", "C"]
    assert all(item["interest_score"] < 0 for item in problems)


def test_owner_and_inactive_manager_are_excluded():
    conn = make_db()
    add_user(conn, 1, "active")
    add_user(conn, 2, "owner", role="owner")
    add_user(conn, 3, "paused", status="paused")
    for user_id in (1, 2, 3):
        add_sent(conn, user_id, f"card-{user_id}", "Tiguan")

    dashboard = get_manager_dashboard(connection=conn)

    assert [manager["manager_id"] for manager in dashboard["managers"]] == ["1"]


def test_unknown_config_is_excluded_from_all_dashboard_metrics():
    conn = make_db()
    add_user(conn, 1, "alice")
    add_sent(conn, 1, "known", "Tiguan")
    add_sent(conn, 1, "unknown", "unknown", send_count=5)
    add_feedback(
        conn,
        1,
        "unknown",
        "unknown",
        "review",
        "2026-01-01T11:00:00",
        comment="Не учитывать",
        reasons=["good_price"],
    )

    manager = manager_for(get_manager_dashboard(connection=conn), 1)

    assert manager["sent_count"] == 1
    assert manager["feedback_count"] == 0
    assert manager["top_reasons"] == []
    assert manager["comments_count"] == 0


def test_reason_comment_is_excluded_and_reasons_are_aggregated():
    conn = make_db()
    add_user(conn, 1, "alice")
    for index, config_name in enumerate(("Tiguan", "Kuga")):
        card_id = f"card-{index}"
        add_sent(conn, 1, card_id, config_name)
        add_feedback(
            conn,
            1,
            card_id,
            config_name,
            "review",
            f"2026-01-01T10:0{index}:00",
            reasons=["high_price", "comment"],
        )

    reasons = manager_for(get_manager_dashboard(connection=conn), 1)["top_reasons"]

    assert reasons == [{"reason": "Высокая цена", "count": 2}]


def test_comments_count_uses_only_latest_feedback_per_card_and_config():
    conn = make_db()
    add_user(conn, 1, "alice")
    add_sent(conn, 1, "card-1", "Tiguan")
    add_sent(conn, 1, "card-2", "Tiguan")
    add_feedback(
        conn,
        1,
        "card-1",
        "Tiguan",
        "think",
        "2026-01-01T10:00:00",
        comment="Старый комментарий",
    )
    add_feedback(
        conn,
        1,
        "card-1",
        "Tiguan",
        "skip",
        "2026-01-01T11:00:00",
        comment="-",
    )
    add_feedback(
        conn,
        1,
        "card-2",
        "Tiguan",
        "review",
        "2026-01-01T12:00:00",
        comment="Единственный актуальный комментарий",
    )

    manager = manager_for(get_manager_dashboard(connection=conn), 1)

    assert manager["comments_count"] == 1


def test_last_comment_contains_text_config_and_date():
    conn = make_db()
    add_user(conn, 1, "alice")
    add_sent(conn, 1, "card-1", "Tiguan")
    add_sent(conn, 1, "card-2", "Ford Kuga")
    add_feedback(
        conn,
        1,
        "card-1",
        "Tiguan",
        "review",
        "2026-01-01T10:00:00",
        comment="Первый",
    )
    add_feedback(
        conn,
        1,
        "card-2",
        "Ford Kuga",
        "think",
        "2026-01-02T12:30:00",
        comment="Надо посмотреть детально",
    )

    manager = manager_for(get_manager_dashboard(connection=conn), 1)

    assert manager["last_comment"] == "Надо посмотреть детально"
    assert manager["last_comment_config"] == "Ford Kuga"
    assert manager["last_comment_date"] == "2026-01-02T12:30:00"


def test_recent_comments_are_built_from_config_comments_and_limited_to_two():
    conn = make_db()
    add_user(conn, 1, "alice")
    for index, config_name in enumerate(("Tiguan", "Ford Kuga", "Volvo Xc90"), 1):
        card_id = f"card-{index}"
        add_sent(conn, 1, card_id, config_name)
        add_feedback(
            conn,
            1,
            card_id,
            config_name,
            "review",
            f"2026-01-0{index}T10:00:00",
            comment=f"Комментарий {index}",
        )

    recent = manager_for(get_manager_dashboard(connection=conn), 1)["recent_comments"]

    assert recent == [
        {
            "config_name": "Volvo Xc90",
            "comment": "Комментарий 3",
            "created_at": "2026-01-03T10:00:00",
        },
        {
            "config_name": "Ford Kuga",
            "comment": "Комментарий 2",
            "created_at": "2026-01-02T10:00:00",
        },
    ]


def test_formatter_contains_compact_dashboard_sections():
    dashboard = {
        "summary": {
            "active_managers": 1,
            "sent_count": 92,
            "feedback_count": 8,
            "feedback_rate": 8 / 92,
        },
        "managers": [
            {
                "manager_id": "1",
                "display_name": "@protocol_skrin",
                "sent_count": 92,
                "feedback_count": 8,
                "feedback_rate": 8 / 92,
                "best_configs": [{"config_name": "Hyundai Santa Fe"}],
                "problem_configs": [{"config_name": "Volvo Xc90"}],
                "top_reasons": [{"reason": "Высокая цена", "count": 3}],
                "comments_count": 2,
                "last_comment": "Надо посмотреть детально",
                "last_comment_config": "Ford Kuga",
                "last_comment_date": "2026-06-14T07:38:52",
                "recent_comments": [
                    {
                        "config_name": "Ford Kuga",
                        "comment": "Надо посмотреть детально",
                        "created_at": "2026-06-14T07:38:52",
                    },
                    {
                        "config_name": "Hyundai Santa Fe",
                        "comment": "Хороший вариант",
                        "created_at": "2026-06-13T09:00:00",
                    },
                ],
            }
        ],
    }

    text = format_manager_dashboard(dashboard)

    assert "📊 Manager Dashboard" in text
    assert "📨 Отправок: 92" in text
    assert "💬 Реакций: 8" in text
    assert "🎯 Конверсия: 8.70%" in text
    assert "👥 Менеджеров: 1" in text
    assert "🏆 Самые интересные конфиги" in text
    assert "⚠️ Самые проблемные конфиги" in text
    assert "🔥 Лучшие" in text
    assert "1. Hyundai Santa Fe" in text
    assert "⚠️ Проблемные" in text
    assert "🧠 Причины" in text
    assert "Высокая цена — 3" in text
    assert "💬 Что сказал менеджер" in text
    assert '"Надо посмотреть детально"' in text
    assert '"Хороший вариант"' in text
    assert "14.06.2026" in text


def test_formatter_aggregates_global_config_tops():
    managers = [
        {
            "display_name": "@alice",
            "feedback_count": 1,
            "sent_count": 1,
            "feedback_rate": 1.0,
            "best_configs": [
                {"config_name": "Tiguan", "interest_score": 2},
                {"config_name": "Kuga", "interest_score": 4},
            ],
            "problem_configs": [{"config_name": "XC90", "interest_score": -2}],
            "top_reasons": [],
            "recent_comments": [],
        },
        {
            "display_name": "@bob",
            "feedback_count": 1,
            "sent_count": 1,
            "feedback_rate": 1.0,
            "best_configs": [{"config_name": "Tiguan", "interest_score": 4}],
            "problem_configs": [{"config_name": "XC90", "interest_score": -4}],
            "top_reasons": [],
            "recent_comments": [],
        },
    ]
    dashboard = {
        "summary": {
            "active_managers": 2,
            "sent_count": 2,
            "feedback_count": 2,
            "feedback_rate": 1.0,
        },
        "managers": managers,
    }

    text = format_manager_dashboard(dashboard)

    global_best = text.split("🏆 Самые интересные конфиги", 1)[1].split(
        "⚠️ Самые проблемные конфиги", 1
    )[0]
    assert global_best.index("1. Tiguan") < global_best.index("2. Kuga")
    assert "1. XC90" in text.split("⚠️ Самые проблемные конфиги", 1)[1]


def test_formatter_groups_managers_without_feedback():
    dashboard = {
        "summary": {
            "active_managers": 2,
            "sent_count": 5,
            "feedback_count": 0,
            "feedback_rate": 0,
        },
        "managers": [
            {"display_name": "@idle", "feedback_count": 0},
            {"display_name": "manager_2", "feedback_count": 0},
        ],
    }

    text = format_manager_dashboard(dashboard)

    assert "⚪ Без активности" in text
    assert "@idle" in text
    assert "manager_2" in text
    assert "👤 @idle" not in text
    assert "👤 manager_2" not in text


def test_formatter_shows_dash_when_manager_has_no_comments():
    dashboard = {
        "summary": {
            "active_managers": 1,
            "sent_count": 1,
            "feedback_count": 1,
            "feedback_rate": 1.0,
        },
        "managers": [
            {
                "display_name": "@alice",
                "sent_count": 1,
                "feedback_count": 1,
                "feedback_rate": 1.0,
                "best_configs": [],
                "problem_configs": [],
                "top_reasons": [],
                "recent_comments": [],
            }
        ],
    }

    text = format_manager_dashboard(dashboard)

    assert "💬 Что сказал менеджер: —" in text


def test_multiple_managers_are_independent_and_sorted_by_display_name():
    conn = make_db()
    add_user(conn, 1, "zulu")
    add_user(conn, 2, "alpha")
    for user_id, action in ((1, "skip"), (2, "review")):
        add_sent(conn, user_id, "same-card", "Tiguan")
        add_feedback(
            conn,
            user_id,
            "same-card",
            "Tiguan",
            action,
            "2026-01-01T10:00:00",
            comment=f"manager-{user_id}",
        )

    dashboard = get_manager_dashboard(connection=conn)

    assert [manager["display_name"] for manager in dashboard["managers"]] == [
        "@alpha",
        "@zulu",
    ]
    assert manager_for(dashboard, 1)["problem_configs"][0]["config_name"] == "Tiguan"
    assert manager_for(dashboard, 2)["best_configs"][0]["config_name"] == "Tiguan"
