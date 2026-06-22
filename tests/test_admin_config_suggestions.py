import asyncio
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock


sys.path.insert(0, str(Path(__file__).parent.parent))

import admin_bot.admin_bot as admin_bot_app
import admin_bot.handlers.learning as learning


def sample_suggestions():
    return {
        "summary": {
            "configs_count": 1,
            "ready_configs": 1,
            "analytics_participants": 2,
        },
        "suggestions": [
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
                        "comment": "Цена выглядит дороговато",
                        "created_at": "2026-01-01T10:00:00",
                    }
                ],
                "owner_signal_present": True,
                "owner_feedback_count": 4,
                "recommendation_text": "Проверить ценовой диапазон.",
            }
        ],
    }


def empty_suggestions():
    return {
        "summary": {
            "configs_count": 0,
            "ready_configs": 0,
            "analytics_participants": 0,
        },
        "suggestions": [],
    }


def make_command_update(user_id=1):
    message = SimpleNamespace(reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        callback_query=None,
        message=message,
    )


def make_callback_update(user_id=1, data="learning_config_suggestions"):
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


def recommendations_button():
    keyboard = learning._learning_keyboard()
    return next(
        button
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data == "learning_config_suggestions"
    )


def test_recommendations_button_exists():
    assert recommendations_button().text == "💡 Рекомендации"


def test_recommendations_button_callback_data_is_correct():
    assert recommendations_button().callback_data == "learning_config_suggestions"


def test_callback_route_calls_common_handler(monkeypatch):
    update = make_callback_update()
    common_handler = AsyncMock()
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(learning, "handle_config_suggestions", common_handler)

    asyncio.run(learning.learning_callback_handler(update, None))

    update.callback_query.answer.assert_awaited_once()
    common_handler.assert_awaited_once_with(update, None)


def test_command_handler_calls_common_handler(monkeypatch):
    update = make_command_update()
    common_handler = AsyncMock()
    monkeypatch.setattr(learning, "handle_config_suggestions", common_handler)

    asyncio.run(learning.config_suggestions_command_handler(update, None))

    common_handler.assert_awaited_once_with(update, None)


def test_admin_bot_registers_config_suggestions_command(monkeypatch):
    class FakeApplication:
        def __init__(self):
            self.handlers = []
            self.run_polling = Mock()

        def add_handler(self, handler):
            self.handlers.append(handler)

    class FakeBuilder:
        def __init__(self, application):
            self.application = application

        def token(self, _token):
            return self

        def build(self):
            return self.application

    application = FakeApplication()
    monkeypatch.setattr(admin_bot_app, "validate", lambda: True)
    monkeypatch.setattr(admin_bot_app, "ensure_tables", lambda: None)
    monkeypatch.setattr(admin_bot_app, "ensure_owner_exists", lambda: None)
    monkeypatch.setattr(
        admin_bot_app,
        "ApplicationBuilder",
        lambda: FakeBuilder(application),
    )

    admin_bot_app.main()

    command_handlers = [
        handler
        for handler in application.handlers
        if hasattr(handler, "commands")
    ]
    suggestions_handler = next(
        handler
        for handler in command_handlers
        if "config_suggestions" in handler.commands
    )
    assert suggestions_handler.callback is learning.config_suggestions_command_handler


def test_owner_or_admin_can_run_suggestions_and_formatter_is_used(monkeypatch):
    update = make_command_update(10)
    suggestions = sample_suggestions()
    get_suggestions = Mock(return_value=suggestions)
    formatter = Mock(return_value="FORMATTED SUGGESTIONS")
    monkeypatch.setattr(learning, "is_admin", lambda user_id: user_id == 10)
    monkeypatch.setattr(learning, "get_config_suggestions", get_suggestions)
    monkeypatch.setattr(learning, "format_config_suggestions", formatter)

    asyncio.run(learning.config_suggestions_command_handler(update, None))

    get_suggestions.assert_called_once_with(learning.DB_PATH)
    formatter.assert_called_once_with(suggestions)
    assert update.message.reply_text.await_args.args[0] == "FORMATTED SUGGESTIONS"


def test_manager_is_denied_without_querying_suggestions(monkeypatch):
    update = make_command_update(20)
    get_suggestions = Mock()
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: False)
    monkeypatch.setattr(learning, "get_config_suggestions", get_suggestions)

    asyncio.run(learning.config_suggestions_command_handler(update, None))

    update.message.reply_text.assert_awaited_once_with("⛔ Нет доступа.")
    get_suggestions.assert_not_called()


def test_split_title_is_config_suggestions(monkeypatch):
    update = make_command_update()
    split = Mock(return_value=["PART"])
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(learning, "get_config_suggestions", lambda _db_path: sample_suggestions())
    monkeypatch.setattr(learning, "format_config_suggestions", lambda _suggestions: "TEXT")
    monkeypatch.setattr(learning, "split_telegram_messages", split)

    asyncio.run(learning.config_suggestions_command_handler(update, None))

    split.assert_called_once_with("TEXT", title="Config Suggestions")


def test_sqlite_error_returns_safe_message(monkeypatch):
    update = make_command_update()
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)

    def fail(_db_path):
        raise sqlite3.OperationalError("database unavailable")

    monkeypatch.setattr(learning, "get_config_suggestions", fail)

    asyncio.run(learning.config_suggestions_command_handler(update, None))

    assert update.message.reply_text.await_args.args[0] == (
        "⚠️ Config Suggestions временно недоступны."
    )


def test_os_error_returns_safe_message(monkeypatch):
    update = make_command_update()
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)

    def fail(_db_path):
        raise OSError("filesystem unavailable")

    monkeypatch.setattr(learning, "get_config_suggestions", fail)

    asyncio.run(learning.config_suggestions_command_handler(update, None))

    assert update.message.reply_text.await_args.args[0] == (
        "⚠️ Config Suggestions временно недоступны."
    )


def test_unexpected_error_returns_safe_message(monkeypatch):
    update = make_command_update()
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(learning, "get_config_suggestions", lambda _db_path: sample_suggestions())

    def fail(_suggestions):
        raise RuntimeError("formatter failed")

    monkeypatch.setattr(learning, "format_config_suggestions", fail)

    asyncio.run(learning.config_suggestions_command_handler(update, None))

    assert update.message.reply_text.await_args.args[0] == (
        "⚠️ Config Suggestions временно недоступны."
    )


def test_no_data_formatter_output_is_sent(monkeypatch):
    update = make_command_update()
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(learning, "get_config_suggestions", lambda _db_path: empty_suggestions())
    monkeypatch.setattr(
        learning,
        "format_config_suggestions",
        lambda _suggestions: "CONFIG SUGGESTIONS\n\nДанных для рекомендаций пока нет.",
    )

    asyncio.run(learning.config_suggestions_command_handler(update, None))

    text = update.message.reply_text.await_args.args[0]
    assert "CONFIG SUGGESTIONS" in text
    assert "Данных для рекомендаций пока нет." in text


def test_callback_sends_all_multipart_suggestions(monkeypatch):
    update = make_callback_update()
    parts = ["PART 1", "PART 2", "PART 3"]
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(learning, "get_config_suggestions", lambda _db_path: sample_suggestions())
    monkeypatch.setattr(learning, "format_config_suggestions", lambda _suggestions: "TEXT")
    monkeypatch.setattr(learning, "split_telegram_messages", lambda *_args, **_kwargs: parts)

    asyncio.run(learning.learning_callback_handler(update, None))

    update.callback_query.edit_message_text.assert_awaited_once_with(
        "PART 1",
        reply_markup=None,
    )
    assert update.callback_query.message.reply_text.await_count == 2
    assert update.callback_query.message.reply_text.await_args_list[0].args[0] == "PART 2"
    assert update.callback_query.message.reply_text.await_args_list[1].args[0] == "PART 3"


def test_splitter_uses_config_suggestions_title_for_multipart():
    text = "\n\n".join(f"Suggestion {index}\n" + "x" * 180 for index in range(20))

    parts = learning.split_telegram_messages(
        text,
        max_length=500,
        title="Config Suggestions",
    )

    assert len(parts) > 1
    assert all(len(part) <= 500 for part in parts)
    assert all(
        part.startswith(f"Config Suggestions ({index}/{len(parts)})")
        for index, part in enumerate(parts, 1)
    )


def test_existing_dashboard_behavior_is_not_broken(monkeypatch):
    update = make_command_update()
    split = Mock(return_value=["DASHBOARD"])
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(learning, "get_manager_dashboard", lambda _db_path: {"dashboard": True})
    monkeypatch.setattr(learning, "format_manager_dashboard", lambda _dashboard: "DASHBOARD TEXT")
    monkeypatch.setattr(learning, "split_telegram_messages", split)

    asyncio.run(learning.manager_dashboard_command_handler(update, None))

    split.assert_called_once_with("DASHBOARD TEXT", title="Manager Dashboard")


def test_existing_manager_config_report_behavior_is_not_broken(monkeypatch):
    update = make_command_update()
    split = Mock(return_value=["CONFIG REPORT"])
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(learning, "get_manager_config_report", lambda _db_path: {"report": True})
    monkeypatch.setattr(
        learning,
        "format_manager_config_report_telegram",
        lambda _report: "CONFIG TEXT",
    )
    monkeypatch.setattr(learning, "split_telegram_messages", split)

    asyncio.run(learning.manager_config_report_command_handler(update, None))

    split.assert_called_once_with("CONFIG TEXT")
    assert update.message.reply_text.await_args.args[0] == "CONFIG REPORT"
