import asyncio
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock


sys.path.insert(0, str(Path(__file__).parent.parent))

import admin_bot.handlers.learning as learning


def sample_report():
    return {
        "summary": {
            "active_managers": 1,
            "configs_with_data": 2,
            "feedback_count": 3,
        },
        "managers": [
            {
                "manager_id": "101",
                "display_name": "@alice",
                "summary": {
                    "best_configs": [
                        "Hyundai Santa Fe (score +3, feedback 2, rate 66.7%)",
                    ],
                    "problem_configs": [
                        "Volvo Xc90 (score -2, feedback 1, rate 100.0%)",
                    ],
                },
                "configs": [
                    {
                        "config_name": "Hyundai Santa Fe",
                        "sent_count": 3,
                        "feedback_count": 2,
                        "review_count": 1,
                        "think_count": 1,
                        "skip_count": 0,
                        "feedback_rate": 2 / 3,
                        "review_rate": 0.5,
                        "think_rate": 0.5,
                        "skip_rate": 0,
                        "interest_score": 3,
                        "status": "GREEN",
                        "confidence": "MEDIUM",
                        "top_reasons": [
                            {"reason_code": "Высокая цена", "count": 2},
                            {"reason_code": "Хорошая цена", "count": 1},
                        ],
                        "manager_comments": [
                            "Надо посмотреть детально",
                            "Клиенту подходит такой мотор",
                        ],
                        "last_feedback_at": "2026-06-14T11:22:33.000000",
                    },
                    {
                        "config_name": "Volvo Xc90",
                        "sent_count": 1,
                        "feedback_count": 1,
                        "review_count": 0,
                        "think_count": 0,
                        "skip_count": 1,
                        "feedback_rate": 1.0,
                        "review_rate": 0,
                        "think_rate": 0,
                        "skip_rate": 1.0,
                        "interest_score": -2,
                        "status": "RED",
                        "confidence": "LOW",
                        "top_reasons": [{"reason_code": "Плохое состояние", "count": 1}],
                        "manager_comments": [],
                        "last_feedback_at": "2026-06-14T09:00:00.000000",
                    },
                ],
            }
        ],
        "historical_unknown": {
            "sent_ads": 10,
            "feedback": 2,
            "reaction_details": 1,
        },
    }


def make_command_update(user_id=1):
    message = SimpleNamespace(reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        callback_query=None,
        message=message,
    )


def make_callback_update(user_id=1, data="learning_manager_config_report"):
    query = SimpleNamespace(
        from_user=SimpleNamespace(id=user_id),
        data=data,
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    return SimpleNamespace(
        effective_user=query.from_user,
        callback_query=query,
        message=None,
    )


def test_formatter_contains_summary_status_confidence_comments_and_unknown():
    text = learning.format_manager_config_report_telegram(sample_report())

    assert "Manager: @alice" in text
    assert "Лучшие конфиги" in text
    assert "1. Hyundai Santa Fe (score +3, feedback 2, rate 66.7%)" in text
    assert "Проблемные конфиги" in text
    assert "1. Volvo Xc90 (score -2, feedback 1, rate 100.0%)" in text
    assert "Hyundai Santa Fe" in text
    assert "Статус: GREEN" in text
    assert "Уверенность: MEDIUM" in text
    assert "Sent: 3 | Feedback: 2 (66.7%)" in text
    assert "Score: +3" in text
    assert "Высокая цена 2" in text
    assert "2026-06-14 11:22" in text
    assert "Что сказал менеджер:\n• Надо посмотреть детально\n• Клиенту подходит такой мотор" in text
    assert "Что сказал менеджер: —" in text
    assert "sent_ads unknown: 10" in text


def test_formatter_handles_no_data():
    report = {
        "summary": {"active_managers": 1, "configs_with_data": 0, "feedback_count": 0},
        "managers": [{"manager_id": "1", "display_name": "@alice", "configs": []}],
        "historical_unknown": {"sent_ads": 4, "feedback": 3, "reaction_details": 2},
    }

    text = learning.format_manager_config_report_telegram(report)

    assert "Данных с config_name пока нет." in text
    assert "feedback unknown: 3" in text


def test_formatter_uses_no_data_summary_when_lists_are_empty():
    report = sample_report()
    report["managers"][0]["summary"] = {
        "best_configs": "данных пока нет",
        "problem_configs": "данных пока нет",
    }

    text = learning.format_manager_config_report_telegram(report)

    assert "Лучшие конфиги: данных пока нет" in text
    assert "Проблемные конфиги: данных пока нет" in text


def test_split_messages_preserves_text_and_limit():
    text = "\n\n".join(f"Block {index}\n" + "x" * 180 for index in range(20))

    parts = learning.split_telegram_messages(text, max_length=500)

    assert len(parts) > 1
    assert all(len(part) <= 500 for part in parts)
    assert all(f"({index}/{len(parts)})" in part for index, part in enumerate(parts, 1))
    assert "Block 0" in parts[0]
    assert "Block 19" in parts[-1]


def test_split_handles_single_oversized_line():
    parts = learning.split_telegram_messages("z" * 1200, max_length=300)

    assert len(parts) > 1
    assert all(len(part) <= 300 for part in parts)


def test_owner_or_admin_can_run_command(monkeypatch):
    update = make_command_update(10)
    monkeypatch.setattr(learning, "is_admin", lambda user_id: user_id == 10)
    monkeypatch.setattr(learning, "get_manager_config_report", lambda db_path: sample_report())

    asyncio.run(learning.manager_config_report_command_handler(update, None))

    update.message.reply_text.assert_awaited()
    text = update.message.reply_text.await_args.args[0]
    assert "Manager Config Report" in text
    assert "Лучшие конфиги" in text
    assert "Статус: GREEN" in text


def test_manager_is_denied_without_querying_report(monkeypatch):
    update = make_command_update(20)
    report_call = AsyncMock()
    monkeypatch.setattr(learning, "is_admin", lambda user_id: False)
    monkeypatch.setattr(learning, "get_manager_config_report", report_call)

    asyncio.run(learning.manager_config_report_command_handler(update, None))

    update.message.reply_text.assert_awaited_once_with("⛔ Нет доступа.")
    report_call.assert_not_called()


def test_callback_button_calls_report(monkeypatch):
    update = make_callback_update()
    monkeypatch.setattr(learning, "is_admin", lambda user_id: True)
    monkeypatch.setattr(learning, "get_manager_config_report", lambda db_path: sample_report())

    asyncio.run(learning.learning_callback_handler(update, None))

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.edit_message_text.assert_awaited()


def test_database_error_returns_safe_message(monkeypatch):
    update = make_command_update()
    monkeypatch.setattr(learning, "is_admin", lambda user_id: True)

    def fail(_db_path):
        raise sqlite3.OperationalError("database unavailable")

    monkeypatch.setattr(learning, "get_manager_config_report", fail)

    asyncio.run(learning.manager_config_report_command_handler(update, None))

    text = update.message.reply_text.await_args.args[0]
    assert text == "⚠️ Manager Config Report временно недоступен."
