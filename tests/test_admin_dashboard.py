import asyncio
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock


sys.path.insert(0, str(Path(__file__).parent.parent))

import admin_bot.handlers.learning as learning
import admin_bot.admin_bot as admin_bot_app


def sample_dashboard():
    return {
        "summary": {
            "active_managers": 1,
            "sent_count": 92,
            "feedback_count": 8,
            "feedback_rate": 8 / 92,
        },
        "managers": [
            {
                "manager_id": "101",
                "display_name": "@alice",
                "sent_count": 92,
                "feedback_count": 8,
                "feedback_rate": 8 / 92,
                "best_configs": [{"config_name": "Hyundai Santa Fe"}],
                "problem_configs": [{"config_name": "Volvo Xc90"}],
                "top_reasons": [{"reason": "Высокая цена", "count": 3}],
                "comments_count": 1,
                "last_comment": "Надо посмотреть детально",
                "last_comment_config": "Ford Kuga",
                "last_comment_date": "2026-06-14T07:38:52",
            }
        ],
    }


def empty_dashboard():
    return {
        "summary": {
            "active_managers": 0,
            "sent_count": 0,
            "feedback_count": 0,
            "feedback_rate": 0,
        },
        "managers": [],
    }


def make_command_update(user_id=1):
    message = SimpleNamespace(reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        callback_query=None,
        message=message,
    )


def make_callback_update(user_id=1, data="learning_manager_dashboard"):
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


def dashboard_button():
    keyboard = learning._learning_keyboard()
    return next(
        button
        for row in keyboard.inline_keyboard
        for button in row
        if button.text == "📊 Dashboard"
    )


def test_dashboard_button_exists():
    assert dashboard_button().text == "📊 Dashboard"


def test_dashboard_button_callback_data_is_correct():
    assert dashboard_button().callback_data == "learning_manager_dashboard"


def test_command_handler_calls_common_handler(monkeypatch):
    common_handler = AsyncMock()
    monkeypatch.setattr(learning, "handle_manager_dashboard", common_handler)
    update = make_command_update()

    asyncio.run(learning.manager_dashboard_command_handler(update, None))

    common_handler.assert_awaited_once_with(update, None)


def test_callback_route_calls_common_handler(monkeypatch):
    update = make_callback_update()
    common_handler = AsyncMock()
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(learning, "handle_manager_dashboard", common_handler)

    asyncio.run(learning.learning_callback_handler(update, None))

    update.callback_query.answer.assert_awaited_once()
    common_handler.assert_awaited_once_with(update, None)


def test_admin_can_run_dashboard_and_formatter_is_used(monkeypatch):
    update = make_command_update(10)
    dashboard = sample_dashboard()
    get_dashboard = Mock(return_value=dashboard)
    formatter = Mock(return_value="FORMATTED DASHBOARD")
    monkeypatch.setattr(learning, "is_admin", lambda user_id: user_id == 10)
    monkeypatch.setattr(learning, "get_manager_dashboard", get_dashboard)
    monkeypatch.setattr(learning, "format_manager_dashboard", formatter)

    asyncio.run(learning.manager_dashboard_command_handler(update, None))

    get_dashboard.assert_called_once_with(learning.DB_PATH)
    formatter.assert_called_once_with(dashboard)
    assert update.message.reply_text.await_args.args[0] == "FORMATTED DASHBOARD"


def test_manager_is_denied_without_querying_dashboard(monkeypatch):
    update = make_command_update(20)
    get_dashboard = Mock()
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: False)
    monkeypatch.setattr(learning, "get_manager_dashboard", get_dashboard)

    asyncio.run(learning.manager_dashboard_command_handler(update, None))

    update.message.reply_text.assert_awaited_once_with("⛔ Нет доступа.")
    get_dashboard.assert_not_called()


def test_dashboard_split_uses_dashboard_title(monkeypatch):
    update = make_command_update()
    split = Mock(return_value=["PART"])
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(learning, "get_manager_dashboard", lambda _db_path: sample_dashboard())
    monkeypatch.setattr(learning, "format_manager_dashboard", lambda _dashboard: "TEXT")
    monkeypatch.setattr(learning, "split_telegram_messages", split)

    asyncio.run(learning.manager_dashboard_command_handler(update, None))

    split.assert_called_once_with("TEXT", title="Manager Dashboard")


def test_sqlite_error_returns_safe_dashboard_message(monkeypatch):
    update = make_command_update()
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)

    def fail(_db_path):
        raise sqlite3.OperationalError("database unavailable")

    monkeypatch.setattr(learning, "get_manager_dashboard", fail)

    asyncio.run(learning.manager_dashboard_command_handler(update, None))

    assert update.message.reply_text.await_args.args[0] == (
        "⚠️ Manager Dashboard временно недоступен."
    )


def test_unexpected_formatter_error_returns_safe_message(monkeypatch):
    update = make_command_update()
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(learning, "get_manager_dashboard", lambda _db_path: sample_dashboard())

    def fail(_dashboard):
        raise RuntimeError("formatter failed")

    monkeypatch.setattr(learning, "format_manager_dashboard", fail)

    asyncio.run(learning.manager_dashboard_command_handler(update, None))

    assert update.message.reply_text.await_args.args[0] == (
        "⚠️ Manager Dashboard временно недоступен."
    )


def test_no_data_dashboard_is_sent(monkeypatch):
    update = make_command_update()
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(learning, "get_manager_dashboard", lambda _db_path: empty_dashboard())

    asyncio.run(learning.manager_dashboard_command_handler(update, None))

    text = update.message.reply_text.await_args.args[0]
    assert "Manager Dashboard" in text
    assert "Активных менеджеров нет." in text


def test_dashboard_split_title_and_message_limit():
    text = "\n\n".join(f"Manager {index}\n" + "x" * 180 for index in range(20))

    parts = learning.split_telegram_messages(
        text,
        max_length=500,
        title="Manager Dashboard",
    )

    assert len(parts) > 1
    assert all(len(part) <= 500 for part in parts)
    assert all(
        part.startswith(f"Manager Dashboard ({index}/{len(parts)})")
        for index, part in enumerate(parts, 1)
    )


def test_callback_sends_all_multipart_dashboard_messages(monkeypatch):
    update = make_callback_update()
    parts = ["PART 1", "PART 2", "PART 3"]
    monkeypatch.setattr(learning, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(learning, "get_manager_dashboard", lambda _db_path: sample_dashboard())
    monkeypatch.setattr(learning, "format_manager_dashboard", lambda _dashboard: "TEXT")
    monkeypatch.setattr(learning, "split_telegram_messages", lambda *_args, **_kwargs: parts)

    asyncio.run(learning.learning_callback_handler(update, None))

    update.callback_query.edit_message_text.assert_awaited_once_with(
        "PART 1",
        reply_markup=None,
    )
    assert update.callback_query.message.reply_text.await_count == 2
    assert update.callback_query.message.reply_text.await_args_list[0].args[0] == "PART 2"
    assert update.callback_query.message.reply_text.await_args_list[1].args[0] == "PART 3"


def test_default_split_title_remains_manager_config_report():
    parts = learning.split_telegram_messages("x" * 1200, max_length=300)

    assert len(parts) > 1
    assert all(
        part.startswith(f"Manager Config Report ({index}/{len(parts)})")
        for index, part in enumerate(parts, 1)
    )


def test_existing_manager_config_report_handler_still_uses_default_split(monkeypatch):
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


def test_admin_bot_registers_manager_dashboard_command(monkeypatch):
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
    dashboard_handler = next(
        handler
        for handler in command_handlers
        if "manager_dashboard" in handler.commands
    )
    assert dashboard_handler.callback is learning.manager_dashboard_command_handler
