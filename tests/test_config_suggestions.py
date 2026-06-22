import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))

from ris_config_suggestions import format_config_suggestions, get_config_suggestions


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
        CREATE TABLE feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT,
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
    *,
    role="manager",
    status="active",
    analytics_participant=1,
):
    conn.execute(
        "INSERT INTO telegram_users VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, f"user_{user_id}", f"User {user_id}", role, status, analytics_participant),
    )


def add_feedback(
    conn,
    user_id,
    card_id,
    config_name,
    action,
    created_at,
    *,
    reasons=None,
    comment=None,
):
    cursor = conn.execute(
        """
        INSERT INTO feedback (
            card_id, telegram_user_id, config_name, action, comment, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (card_id, str(user_id), config_name, action, comment, created_at),
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


def seed_config(
    conn,
    config_name,
    *,
    count,
    action="review",
    reason=None,
    user_id=1,
):
    add_user(conn, user_id)
    for index in range(count):
        add_feedback(
            conn,
            user_id,
            f"{config_name}-{index}",
            config_name,
            action,
            f"2026-01-01T10:{index:02d}:00",
            reasons=[reason] if reason else None,
        )


def suggestion_for(report, config_name):
    return next(item for item in report["suggestions"] if item["config_name"] == config_name)


def test_empty_database_returns_empty_suggestions():
    report = get_config_suggestions(connection=make_db())

    assert report == {
        "summary": {
            "configs_count": 0,
            "suggestions_count": 0,
            "analytics_participants": 0,
            "ready_configs": 0,
        },
        "suggestions": [],
    }


def test_only_active_analytics_participants_are_used():
    conn = make_db()
    add_user(conn, 1)
    add_user(conn, 2, analytics_participant=0)
    add_user(conn, 3, status="paused")
    add_user(conn, 4, role="admin", analytics_participant=0)
    for user_id in (1, 2, 3, 4):
        add_feedback(
            conn,
            user_id,
            f"card-{user_id}",
            "Tiguan",
            "review",
            "2026-01-01T10:00:00",
        )

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["feedback_count"] == 1
    assert item["participants_count"] == 1


def test_owner_is_included_when_analytics_participant_is_enabled():
    conn = make_db()
    add_user(conn, 1)
    add_user(conn, 2, role="owner")
    add_feedback(conn, 1, "m-1", "Tiguan", "review", "2026-01-01T10:00:00")
    add_feedback(conn, 2, "o-1", "Tiguan", "think", "2026-01-01T10:01:00")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["feedback_count"] == 2
    assert item["participants_count"] == 2
    assert item["owner_feedback_count"] == 1
    assert item["owner_signal_present"] is True
    assert "Owner contributed 1 feedback" in item["evidence"]


def test_owner_is_excluded_when_analytics_participant_is_disabled():
    conn = make_db()
    add_user(conn, 1)
    add_user(conn, 2, role="owner", analytics_participant=0)
    add_feedback(conn, 1, "m-1", "Tiguan", "review", "2026-01-01T10:00:00")
    add_feedback(conn, 2, "o-1", "Tiguan", "review", "2026-01-01T10:01:00")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["feedback_count"] == 1
    assert item["owner_signal_present"] is False


def test_latest_feedback_wins_per_participant_card_config():
    conn = make_db()
    add_user(conn, 1)
    add_feedback(
        conn,
        1,
        "card-1",
        "Tiguan",
        "skip",
        "2026-01-01T10:00:00",
        reasons=["high_price"],
        comment="old",
    )
    add_feedback(
        conn,
        1,
        "card-1",
        "Tiguan",
        "review",
        "2026-01-01T11:00:00",
        reasons=["good_price"],
        comment="latest",
    )

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["feedback_count"] == 1
    assert item["review_count"] == 1
    assert item["skip_count"] == 0
    assert item["interest_score"] == 2
    assert item["dominant_reasons"][0]["reason_code"] == "good_price"
    assert item["comments_evidence"][0]["comment"] == "latest"


def test_unknown_config_is_excluded():
    conn = make_db()
    add_user(conn, 1)
    add_feedback(conn, 1, "known", "Tiguan", "review", "2026-01-01T10:00:00")
    add_feedback(
        conn,
        1,
        "unknown",
        "unknown",
        "review",
        "2026-01-01T10:01:00",
        reasons=["good_price"],
        comment="ignore",
    )

    report = get_config_suggestions(connection=conn)

    assert [item["config_name"] for item in report["suggestions"]] == ["Tiguan"]


def test_reason_code_comment_is_excluded_but_feedback_comment_is_evidence():
    conn = make_db()
    add_user(conn, 1)
    for index in range(5):
        add_feedback(
            conn,
            1,
            f"card-{index}",
            "Tiguan",
            "review",
            f"2026-01-01T10:0{index}:00",
            reasons=["comment", "good_price"],
            comment=f"comment {index}",
        )

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert [reason["reason_code"] for reason in item["dominant_reasons"]] == ["good_price"]
    assert len(item["comments_evidence"]) == 3


def test_comments_exclude_empty_dash_and_limit_to_three_latest():
    conn = make_db()
    add_user(conn, 1)
    comments = ["", "-", "first", "second", "third", "fourth"]
    for index, comment in enumerate(comments):
        add_feedback(
            conn,
            1,
            f"card-{index}",
            "Tiguan",
            "review",
            f"2026-01-01T10:0{index}:00",
            comment=comment,
        )

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert [comment["comment"] for comment in item["comments_evidence"]] == [
        "fourth",
        "third",
        "second",
    ]


def test_not_ready_threshold():
    conn = make_db()
    seed_config(conn, "Tiguan", count=4, reason="high_price")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["readiness"] == "NOT_READY"
    assert item["confidence"] == "LOW"
    assert item["recommendation_type"] == "insufficient_data"


def test_low_confidence_threshold():
    conn = make_db()
    seed_config(conn, "Tiguan", count=5, reason="good_price")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["readiness"] == "LOW"
    assert item["confidence"] == "LOW"


def test_medium_confidence_threshold():
    conn = make_db()
    seed_config(conn, "Tiguan", count=10, reason="good_price")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["readiness"] == "MEDIUM"
    assert item["confidence"] == "MEDIUM"


def test_high_confidence_threshold():
    conn = make_db()
    seed_config(conn, "Tiguan", count=20, reason="good_price")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["readiness"] == "HIGH"
    assert item["confidence"] == "HIGH"


def test_high_price_recommends_price_range_not_max_price_increase():
    conn = make_db()
    seed_config(conn, "Tiguan", count=5, action="think", reason="high_price")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["recommendation_type"] == "review_price_range"
    assert "ценовой диапазон" in item["recommendation_text"]
    assert "Не увеличивать max_price автоматически" in item["recommendation_text"]


def test_too_expensive_recommends_price_range():
    conn = make_db()
    seed_config(conn, "Tiguan", count=5, action="skip", reason="too_expensive")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["recommendation_type"] == "review_price_range"


def test_high_mileage_recommends_mileage_review():
    conn = make_db()
    seed_config(conn, "Tiguan", count=5, action="think", reason="high_mileage")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["recommendation_type"] == "review_mileage"
    assert "пробега" in item["recommendation_text"]


def test_bad_condition_recommends_condition_review():
    conn = make_db()
    seed_config(conn, "Tiguan", count=5, action="skip", reason="bad_condition")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["recommendation_type"] == "review_condition"
    assert "состояния" in item["recommendation_text"]


def test_many_owners_recommends_condition_review():
    conn = make_db()
    seed_config(conn, "Tiguan", count=5, action="skip", reason="many_owners")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["recommendation_type"] == "review_condition"


def test_liquid_model_recommends_priority_increase():
    conn = make_db()
    seed_config(conn, "Tiguan", count=5, action="review", reason="liquid_model")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["recommendation_type"] == "increase_priority"


def test_good_price_recommends_priority_increase():
    conn = make_db()
    seed_config(conn, "Tiguan", count=5, action="review", reason="good_price")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["recommendation_type"] == "increase_priority"


def test_negative_score_without_reason_recommends_decrease_priority():
    conn = make_db()
    seed_config(conn, "Tiguan", count=5, action="skip")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["interest_score"] == -10
    assert item["recommendation_type"] == "decrease_priority"


def test_positive_score_without_reason_recommends_keep_as_is():
    conn = make_db()
    seed_config(conn, "Tiguan", count=5, action="think")

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["interest_score"] == 5
    assert item["recommendation_type"] == "keep_as_is"


def test_mixed_signals_recommend_more_data_when_no_reason_dominates():
    conn = make_db()
    add_user(conn, 1)
    fixtures = [
        ("review", "good_price"),
        ("review", "good_price"),
        ("think", "high_price"),
        ("think", "high_price"),
        ("think", None),
    ]
    for index, (action, reason) in enumerate(fixtures):
        add_feedback(
            conn,
            1,
            f"card-{index}",
            "Tiguan",
            action,
            f"2026-01-01T10:0{index}:00",
            reasons=[reason] if reason else None,
        )

    item = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")

    assert item["interest_score"] > 0
    assert item["recommendation_type"] == "mixed_signals"


def test_reason_pressure_is_calculated():
    conn = make_db()
    add_user(conn, 1)
    for index in range(5):
        reason = "high_price" if index < 3 else "bad_condition"
        add_feedback(
            conn,
            1,
            f"card-{index}",
            "Tiguan",
            "think",
            f"2026-01-01T10:0{index}:00",
            reasons=[reason],
        )

    top_reason = suggestion_for(get_config_suggestions(connection=conn), "Tiguan")[
        "dominant_reasons"
    ][0]

    assert top_reason == {
        "reason_code": "high_price",
        "reason_text": "Высокая цена",
        "count": 3,
        "pressure": 0.6,
    }


def test_suggestions_are_sorted_by_feedback_score_and_name():
    conn = make_db()
    add_user(conn, 1)
    for config_name, count, action in [
        ("Low", 5, "think"),
        ("High", 7, "skip"),
        ("Middle", 7, "review"),
    ]:
        for index in range(count):
            add_feedback(
                conn,
                1,
                f"{config_name}-{index}",
                config_name,
                action,
                f"2026-01-01T10:{index:02d}:00",
            )

    names = [item["config_name"] for item in get_config_suggestions(connection=conn)["suggestions"]]

    assert names == ["Middle", "High", "Low"]


def test_summary_counts_ready_configs():
    conn = make_db()
    add_user(conn, 1)
    seed_data = [("Ready", 5), ("NotReady", 4)]
    for config_name, count in seed_data:
        for index in range(count):
            add_feedback(
                conn,
                1,
                f"{config_name}-{index}",
                config_name,
                "think",
                f"2026-01-01T10:{index:02d}:00",
            )

    summary = get_config_suggestions(connection=conn)["summary"]

    assert summary["configs_count"] == 2
    assert summary["suggestions_count"] == 2
    assert summary["analytics_participants"] == 1
    assert summary["ready_configs"] == 1


def sample_formatter_suggestions():
    return {
        "summary": {
            "configs_count": 5,
            "ready_configs": 3,
            "analytics_participants": 3,
        },
        "suggestions": [
            {
                "config_name": "High Config",
                "feedback_count": 20,
                "participants_count": 3,
                "review_count": 12,
                "think_count": 6,
                "skip_count": 2,
                "interest_score": 26,
                "readiness": "HIGH",
                "confidence": "HIGH",
                "dominant_reasons": [
                    {
                        "reason_code": "liquid_model",
                        "reason_text": "Ликвидная модель",
                        "count": 11,
                        "pressure": 11 / 20,
                    }
                ],
                "comments_evidence": [],
                "owner_signal_present": False,
                "owner_feedback_count": 0,
                "recommendation_text": "Модель интересная, оставить как есть.",
            },
            {
                "config_name": "Medium Config",
                "feedback_count": 12,
                "participants_count": 2,
                "review_count": 4,
                "think_count": 5,
                "skip_count": 3,
                "interest_score": 7,
                "readiness": "MEDIUM",
                "confidence": "MEDIUM",
                "dominant_reasons": [
                    {
                        "reason_code": "good_price",
                        "reason_text": "Хорошая цена",
                        "count": 6,
                        "pressure": 0.5,
                    }
                ],
                "comments_evidence": [],
                "owner_signal_present": False,
                "owner_feedback_count": 0,
                "recommendation_text": "Модель даёт интересные варианты.",
            },
            {
                "config_name": "Hyundai Santa Fe",
                "feedback_count": 9,
                "participants_count": 3,
                "review_count": 1,
                "think_count": 6,
                "skip_count": 2,
                "interest_score": 4,
                "readiness": "LOW",
                "confidence": "LOW",
                "dominant_reasons": [
                    {
                        "reason_code": "high_price",
                        "reason_text": "Высокая цена",
                        "count": 5,
                        "pressure": 5 / 9,
                    }
                ],
                "comments_evidence": [
                    {
                        "participant_id": "1",
                        "comment": "Надо посмотреть детально",
                        "created_at": "2026-01-03T10:00:00",
                    },
                    {
                        "participant_id": "1",
                        "comment": "Цена не соответствует состоянию",
                        "created_at": "2026-01-02T10:00:00",
                    },
                    {
                        "participant_id": "1",
                        "comment": "Третий комментарий не должен попасть",
                        "created_at": "2026-01-01T10:00:00",
                    }
                ],
                "owner_signal_present": True,
                "owner_feedback_count": 4,
                "recommendation_text": "Проверить ценовой диапазон.",
            },
            {
                "config_name": "Volkswagen Touareg",
                "feedback_count": 2,
                "participants_count": 1,
                "review_count": 0,
                "think_count": 1,
                "skip_count": 1,
                "interest_score": -1,
                "readiness": "NOT_READY",
                "confidence": "LOW",
                "dominant_reasons": [],
                "comments_evidence": [],
                "owner_signal_present": False,
                "owner_feedback_count": 0,
                "recommendation_text": "Недостаточно данных.",
            },
            {
                "config_name": "Mitsubishi Pajero IV",
                "feedback_count": 1,
                "participants_count": 1,
                "review_count": 0,
                "think_count": 1,
                "skip_count": 0,
                "interest_score": 1,
                "readiness": "NOT_READY",
                "confidence": "LOW",
                "dominant_reasons": [],
                "comments_evidence": [],
                "owner_signal_present": False,
                "owner_feedback_count": 0,
                "recommendation_text": "Недостаточно данных.",
            },
        ],
    }


def test_formatter_contains_global_summary_and_groups():
    text = format_config_suggestions(sample_formatter_suggestions())

    assert "💡 Config Suggestions" in text
    assert "📊 Всего конфигов: 5" in text
    assert "🟡 Готовы к анализу: 3" in text
    assert "⚪ Недостаточно данных: 2" in text
    assert "🟠 LOW:" in text
    assert "Hyundai Santa Fe" in text


def test_formatter_groups_in_readiness_order():
    text = format_config_suggestions(sample_formatter_suggestions())

    high_section = text.index("\n🟢 HIGH\n")
    medium_section = text.index("\n🟡 MEDIUM\n")
    low_section = text.index("\n🟠 LOW\n")
    not_ready_section = text.index("\n⚪ Недостаточно данных\n")

    assert high_section < medium_section
    assert medium_section < low_section
    assert low_section < not_ready_section


def test_formatter_puts_recommendation_before_reasons_and_data():
    text = format_config_suggestions(sample_formatter_suggestions())
    item_start = text.index("🟠 LOW Hyundai Santa Fe")
    recommendation = text.index("💡 Что сделать:", item_start)
    reasons = text.index("Почему:", item_start)
    data = text.index("Данные:", item_start)

    assert recommendation < reasons < data
    assert "Actions:" not in text
    assert "review=" not in text
    assert "think=" not in text
    assert "skip=" not in text
    assert "Participants:" not in text


def test_formatter_uses_owner_human_format():
    text = format_config_suggestions(sample_formatter_suggestions())

    assert "👤 Owner участвовал: 4 реакции" in text
    assert "Owner contributed 4 feedback" not in text


def test_formatter_compacts_not_ready_configs():
    text = format_config_suggestions(sample_formatter_suggestions())
    not_ready_start = text.index("⚪ Недостаточно данных")

    assert "Volkswagen Touareg — 2 реакции, нужно ещё 3" in text
    assert "Mitsubishi Pajero IV — 1 реакция, нужно ещё 4" in text
    assert "⚪ NOT_READY Volkswagen Touareg" not in text
    assert text.index("Volkswagen Touareg", not_ready_start) > not_ready_start


def test_formatter_limits_comments_to_two_and_omits_empty_comment_sections():
    text = format_config_suggestions(sample_formatter_suggestions())

    assert "💬 Комментарии" in text
    assert "• Надо посмотреть детально" in text
    assert "• Цена не соответствует состоянию" in text
    assert "Третий комментарий не должен попасть" not in text
    assert "Комментарии: —" not in text


def test_formatter_uses_high_medium_low_icons():
    text = format_config_suggestions(sample_formatter_suggestions())

    assert "🟢 HIGH High Config" in text
    assert "🟡 MEDIUM Medium Config" in text
    assert "🟠 LOW Hyundai Santa Fe" in text


def test_formatter_hides_internal_reason_codes():
    text = format_config_suggestions(sample_formatter_suggestions())

    assert "Высокая цена — 5 из 9" in text
    assert "high_price" not in text
    assert "liquid_model" not in text


def test_formatter_handles_empty_report():
    text = format_config_suggestions(
        {
            "summary": {
                "configs_count": 0,
                "ready_configs": 0,
                "analytics_participants": 0,
            },
            "suggestions": [],
        }
    )

    assert "Данных для рекомендаций пока нет." in text
