"""Compact read-only dashboard built from manager config analytics."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ris_manager_config_report import DB_PATH, get_manager_config_report


VALID_CONFIG_SQL = "config_name IS NOT NULL AND config_name != '' AND config_name != 'unknown'"


def _open_read_only(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path).resolve()
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _config_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "config_name": config["config_name"],
        "interest_score": int(config["interest_score"]),
        "feedback_count": int(config["feedback_count"]),
        "feedback_rate": float(config["feedback_rate"]),
    }


def _best_configs(configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        config
        for config in configs
        if int(config["feedback_count"]) > 0 and int(config["interest_score"]) > 0
    ]
    return [
        _config_summary(config)
        for config in sorted(
            candidates,
            key=lambda config: (
                -int(config["interest_score"]),
                -float(config["feedback_rate"]),
                -int(config["feedback_count"]),
                str(config["config_name"]),
            ),
        )[:3]
    ]


def _problem_configs(configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        config
        for config in configs
        if int(config["feedback_count"]) > 0 and int(config["interest_score"]) < 0
    ]
    return [
        _config_summary(config)
        for config in sorted(
            candidates,
            key=lambda config: (
                int(config["interest_score"]),
                -int(config["feedback_count"]),
                float(config["feedback_rate"]),
                str(config["config_name"]),
            ),
        )[:3]
    ]


def _top_reasons(configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for config in configs:
        for reason in config.get("top_reasons", []):
            raw_code = str(reason.get("raw_reason_code") or "").strip()
            if not raw_code or raw_code == "comment":
                continue
            title = str(reason.get("reason_code") or "Неизвестная причина")
            counts[title] = counts.get(title, 0) + int(reason.get("count", 0))

    return [
        {"reason": title, "count": count}
        for title, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:3]
    ]


def _recent_comments(configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    for config in configs:
        config_name = str(config.get("config_name") or "").strip()
        created_at = config.get("last_feedback_at")
        for raw_comment in config.get("manager_comments", []):
            comment = str(raw_comment or "").strip()
            if not comment or comment == "-":
                continue
            comments.append(
                {
                    "config_name": config_name,
                    "comment": comment,
                    "created_at": created_at,
                }
            )

    comments.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return comments[:2]


def _load_comment_summary(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    feedback_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(feedback)").fetchall()
    }
    if "comment" not in feedback_columns:
        return {}

    rows = conn.execute(
        f"""
        WITH analytics_participants AS (
            -- manager_id is kept for report compatibility; it is the analytics participant id.
            SELECT CAST(telegram_id AS TEXT) AS manager_id
            FROM telegram_users
            WHERE status = 'active'
              AND analytics_participant = 1
        ),
        latest_feedback_ids AS (
            SELECT
                CAST(f.telegram_chat_id AS TEXT) AS manager_id,
                f.card_id,
                f.config_name,
                MAX(f.id) AS feedback_id
            FROM feedback f
            JOIN analytics_participants m
              ON m.manager_id = CAST(f.telegram_chat_id AS TEXT)
            WHERE f.{VALID_CONFIG_SQL}
            GROUP BY CAST(f.telegram_chat_id AS TEXT), f.card_id, f.config_name
        ),
        valid_comments AS (
            SELECT
                l.manager_id,
                f.id AS feedback_id,
                f.config_name,
                TRIM(f.comment) AS comment,
                f.created_at,
                ROW_NUMBER() OVER (
                    PARTITION BY l.manager_id
                    ORDER BY f.created_at DESC, f.id DESC
                ) AS recency_rank
            FROM latest_feedback_ids l
            JOIN feedback f ON f.id = l.feedback_id
            WHERE f.comment IS NOT NULL
              AND TRIM(f.comment) != ''
              AND TRIM(f.comment) != '-'
        )
        SELECT
            manager_id,
            COUNT(*) AS comments_count,
            MAX(CASE WHEN recency_rank = 1 THEN comment END) AS last_comment,
            MAX(CASE WHEN recency_rank = 1 THEN config_name END) AS last_comment_config,
            MAX(CASE WHEN recency_rank = 1 THEN created_at END) AS last_comment_at
        FROM valid_comments
        GROUP BY manager_id
        """
    ).fetchall()

    return {
        str(row["manager_id"]): {
            "comments_count": int(row["comments_count"]),
            "last_comment": row["last_comment"],
            "last_comment_config": row["last_comment_config"],
            "last_comment_date": row["last_comment_at"],
        }
        for row in rows
    }


def get_manager_dashboard(
    db_path: str | Path = DB_PATH,
    *,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Return a compact manager dashboard without modifying the database."""
    conn = connection or _open_read_only(db_path)
    owns_connection = connection is None
    conn.row_factory = sqlite3.Row

    try:
        report = get_manager_config_report(db_path, connection=conn)
        comments_by_manager = _load_comment_summary(conn)
        managers = []

        for manager in report["managers"]:
            configs = manager.get("configs", [])
            sent_count = sum(int(config["sent_count"]) for config in configs)
            feedback_count = sum(int(config["feedback_count"]) for config in configs)
            comment_summary = comments_by_manager.get(
                str(manager["manager_id"]),
                {
                    "comments_count": 0,
                    "last_comment": None,
                    "last_comment_config": None,
                    "last_comment_date": None,
                },
            )
            managers.append(
                {
                    "manager_id": str(manager["manager_id"]),
                    "display_name": manager["display_name"],
                    "sent_count": sent_count,
                    "feedback_count": feedback_count,
                    "feedback_rate": _rate(feedback_count, sent_count),
                    "best_configs": _best_configs(configs),
                    "problem_configs": _problem_configs(configs),
                    "top_reasons": _top_reasons(configs),
                    "recent_comments": _recent_comments(configs),
                    **comment_summary,
                }
            )

        managers.sort(key=lambda manager: str(manager["display_name"]).casefold())
        total_sent = sum(manager["sent_count"] for manager in managers)
        total_feedback = sum(manager["feedback_count"] for manager in managers)

        return {
            "summary": {
                "active_managers": len(managers),
                "sent_count": total_sent,
                "feedback_count": total_feedback,
                "feedback_rate": _rate(total_feedback, total_sent),
            },
            "managers": managers,
        }
    finally:
        if owns_connection:
            conn.close()


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y")
    except ValueError:
        return value[:10]


def _format_configs(title: str, configs: list[dict[str, Any]]) -> list[str]:
    if not configs:
        return [f"{title}: данных пока нет"]
    return [title, *[f"{index}. {item['config_name']}" for index, item in enumerate(configs, 1)]]


def _format_reasons(reasons: list[dict[str, Any]]) -> list[str]:
    if not reasons:
        return ["🧠 Причины: данных пока нет"]
    return ["🧠 Причины", *[f"{item['reason']} — {item['count']}" for item in reasons]]


def _aggregate_global_configs(
    managers: list[dict[str, Any]],
    field: str,
    *,
    positive: bool,
) -> list[dict[str, Any]]:
    scores: dict[str, int] = {}
    for manager in managers:
        for config in manager.get(field, []):
            config_name = str(config.get("config_name") or "").strip()
            if not config_name:
                continue
            scores[config_name] = scores.get(config_name, 0) + int(
                config.get("interest_score", 0)
            )

    candidates = [
        {"config_name": config_name, "interest_score": score}
        for config_name, score in scores.items()
        if (score > 0 if positive else score < 0)
    ]
    candidates.sort(
        key=lambda item: (
            -int(item["interest_score"]) if positive else int(item["interest_score"]),
            str(item["config_name"]),
        )
    )
    return candidates[:3]


def _format_recent_comments(manager: dict[str, Any]) -> list[str]:
    comments = manager.get("recent_comments", [])
    if not comments and manager.get("last_comment"):
        comments = [
            {
                "config_name": manager.get("last_comment_config"),
                "comment": manager.get("last_comment"),
                "created_at": manager.get("last_comment_date"),
            }
        ]
    if not comments:
        return ["💬 Что сказал менеджер: —"]

    lines = ["💬 Что сказал менеджер", ""]
    for index, item in enumerate(comments[:2], 1):
        lines.extend(
            [
                (
                    f"{index}. {item.get('config_name') or '—'} — "
                    f"{_format_date(item.get('created_at'))}"
                ),
                f'"{item.get("comment") or "—"}"',
            ]
        )
        if index < len(comments[:2]):
            lines.append("")
    return lines


def format_manager_dashboard(dashboard: dict[str, Any]) -> str:
    """Format a compact plain-text dashboard for Telegram or CLI output."""
    summary = dashboard.get("summary", {})
    managers = dashboard.get("managers", [])
    lines = [
        "📊 Manager Dashboard",
        "",
        f"📨 Отправок: {int(summary.get('sent_count', 0))}",
        f"💬 Реакций: {int(summary.get('feedback_count', 0))}",
        f"🎯 Конверсия: {_percent(float(summary.get('feedback_rate', 0)))}",
        f"👥 Менеджеров: {int(summary.get('active_managers', 0))}",
    ]

    if not managers:
        lines.extend(["", "Активных менеджеров нет."])
        return "\n".join(lines)

    best_global = _aggregate_global_configs(
        managers, "best_configs", positive=True
    )
    problem_global = _aggregate_global_configs(
        managers, "problem_configs", positive=False
    )
    lines.extend(
        [
            "",
            *_format_configs("🏆 Самые интересные конфиги", best_global),
            "",
            *_format_configs("⚠️ Самые проблемные конфиги", problem_global),
        ]
    )

    active_managers = [
        manager for manager in managers if int(manager.get("feedback_count", 0)) > 0
    ]
    inactive_managers = [
        manager for manager in managers if int(manager.get("feedback_count", 0)) == 0
    ]

    for manager in active_managers:
        lines.extend(
            [
                "",
                f"👤 {manager['display_name']}",
                "",
                (
                    f"📊 {manager['sent_count']} отправлено | "
                    f"{manager['feedback_count']} feedback | "
                    f"{_percent(float(manager['feedback_rate']))}"
                ),
                "",
                *_format_configs("🔥 Лучшие", manager.get("best_configs", [])),
                "",
                *_format_configs("⚠️ Проблемные", manager.get("problem_configs", [])),
                "",
                *_format_reasons(manager.get("top_reasons", [])),
                "",
                *_format_recent_comments(manager),
            ]
        )

    if inactive_managers:
        lines.extend(
            [
                "",
                "⚪ Без активности",
                "",
                *[str(manager["display_name"]) for manager in inactive_managers],
            ]
        )

    return "\n".join(lines)
