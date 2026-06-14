"""Read-only manager + config analytics for the Block 2C CLI report."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any


DB_PATH = Path("results/feedback.db")
VALID_CONFIG_SQL = "config_name IS NOT NULL AND config_name != '' AND config_name != 'unknown'"


def _open_read_only(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path).resolve()
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _display_name(username: str | None, first_name: str | None, manager_id: str) -> str:
    if username and username.strip():
        return f"@{username.strip()}"
    if first_name and first_name.strip():
        return first_name.strip()
    return f"manager_{manager_id}"


def get_manager_config_report(
    db_path: str | Path = DB_PATH,
    *,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Return the Block 2C report without modifying the database."""
    conn = connection or _open_read_only(db_path)
    owns_connection = connection is None
    conn.row_factory = sqlite3.Row

    try:
        active_managers = conn.execute(
            """
            SELECT telegram_id, username, first_name
            FROM telegram_users
            WHERE role = 'manager' AND status = 'active'
            ORDER BY telegram_id
            """
        ).fetchall()

        rows = conn.execute(
            f"""
            WITH active_managers AS (
                SELECT
                    CAST(telegram_id AS TEXT) AS manager_id,
                    username,
                    first_name
                FROM telegram_users
                WHERE role = 'manager' AND status = 'active'
            ),
            sent AS (
                SELECT
                    CAST(s.chat_id AS TEXT) AS manager_id,
                    s.config_name,
                    SUM(COALESCE(s.send_count, 1)) AS sent_count
                FROM sent_ads s
                JOIN active_managers m
                  ON m.manager_id = CAST(s.chat_id AS TEXT)
                WHERE s.{VALID_CONFIG_SQL}
                GROUP BY CAST(s.chat_id AS TEXT), s.config_name
            ),
            latest_feedback_ids AS (
                SELECT
                    CAST(f.telegram_chat_id AS TEXT) AS manager_id,
                    f.card_id,
                    f.config_name,
                    MAX(f.id) AS feedback_id
                FROM feedback f
                JOIN active_managers m
                  ON m.manager_id = CAST(f.telegram_chat_id AS TEXT)
                WHERE f.{VALID_CONFIG_SQL}
                GROUP BY CAST(f.telegram_chat_id AS TEXT), f.card_id, f.config_name
            ),
            latest_feedback AS (
                SELECT
                    l.manager_id,
                    l.card_id,
                    l.config_name,
                    f.id AS feedback_id,
                    f.action,
                    f.created_at
                FROM latest_feedback_ids l
                JOIN feedback f ON f.id = l.feedback_id
            ),
            feedback_stats AS (
                SELECT
                    manager_id,
                    config_name,
                    COUNT(DISTINCT card_id) AS feedback_count,
                    SUM(CASE WHEN action = 'review' THEN 1 ELSE 0 END) AS review_count,
                    SUM(CASE WHEN action = 'think' THEN 1 ELSE 0 END) AS think_count,
                    SUM(CASE WHEN action = 'skip' THEN 1 ELSE 0 END) AS skip_count,
                    MAX(created_at) AS last_feedback_at
                FROM latest_feedback
                GROUP BY manager_id, config_name
            ),
            report_keys AS (
                SELECT manager_id, config_name FROM sent
                UNION
                SELECT manager_id, config_name FROM feedback_stats
            )
            SELECT
                k.manager_id,
                m.username,
                m.first_name,
                k.config_name,
                COALESCE(s.sent_count, 0) AS sent_count,
                COALESCE(f.feedback_count, 0) AS feedback_count,
                COALESCE(f.review_count, 0) AS review_count,
                COALESCE(f.think_count, 0) AS think_count,
                COALESCE(f.skip_count, 0) AS skip_count,
                f.last_feedback_at
            FROM report_keys k
            JOIN active_managers m ON m.manager_id = k.manager_id
            LEFT JOIN sent s
              ON s.manager_id = k.manager_id AND s.config_name = k.config_name
            LEFT JOIN feedback_stats f
              ON f.manager_id = k.manager_id AND f.config_name = k.config_name
            ORDER BY k.manager_id, k.config_name
            """
        ).fetchall()

        reasons = conn.execute(
            f"""
            WITH active_managers AS (
                SELECT CAST(telegram_id AS TEXT) AS manager_id
                FROM telegram_users
                WHERE role = 'manager' AND status = 'active'
            ),
            latest_feedback_ids AS (
                SELECT
                    CAST(f.telegram_chat_id AS TEXT) AS manager_id,
                    f.card_id,
                    f.config_name,
                    MAX(f.id) AS feedback_id
                FROM feedback f
                JOIN active_managers m
                  ON m.manager_id = CAST(f.telegram_chat_id AS TEXT)
                WHERE f.{VALID_CONFIG_SQL}
                GROUP BY CAST(f.telegram_chat_id AS TEXT), f.card_id, f.config_name
            )
            SELECT
                l.manager_id,
                l.config_name,
                rd.reason_code,
                COUNT(*) AS reason_count
            FROM latest_feedback_ids l
            JOIN reaction_details rd ON rd.feedback_id = l.feedback_id
            WHERE rd.reason_code IS NOT NULL AND rd.reason_code != ''
            GROUP BY l.manager_id, l.config_name, rd.reason_code
            ORDER BY l.manager_id, l.config_name, reason_count DESC, rd.reason_code
            """
        ).fetchall()

        reasons_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in reasons:
            key = (row["manager_id"], row["config_name"])
            reasons_by_key.setdefault(key, []).append(
                {"reason_code": row["reason_code"], "count": row["reason_count"]}
            )

        managers: dict[str, dict[str, Any]] = {}
        for manager in active_managers:
            manager_id = str(manager["telegram_id"])
            managers[manager_id] = {
                "manager_id": manager_id,
                "display_name": _display_name(
                    manager["username"], manager["first_name"], manager_id
                ),
                "configs": [],
            }

        for row in rows:
            sent_count = int(row["sent_count"])
            feedback_count = int(row["feedback_count"])
            review_count = int(row["review_count"])
            think_count = int(row["think_count"])
            skip_count = int(row["skip_count"])
            manager_id = row["manager_id"]
            config_name = row["config_name"]
            managers[manager_id]["configs"].append(
                {
                    "config_name": config_name,
                    "sent_count": sent_count,
                    "feedback_count": feedback_count,
                    "review_count": review_count,
                    "think_count": think_count,
                    "skip_count": skip_count,
                    "feedback_rate": _rate(feedback_count, sent_count),
                    "review_rate": _rate(review_count, feedback_count),
                    "think_rate": _rate(think_count, feedback_count),
                    "skip_rate": _rate(skip_count, feedback_count),
                    "interest_score": review_count * 2 + think_count - skip_count * 2,
                    "top_reasons": reasons_by_key.get((manager_id, config_name), []),
                    "last_feedback_at": row["last_feedback_at"],
                }
            )

        historical = {}
        for table in ("sent_ads", "feedback", "reaction_details"):
            historical[table] = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM {table}
                WHERE config_name IS NULL OR config_name = '' OR config_name = 'unknown'
                """
            ).fetchone()[0]

        config_names = {row["config_name"] for row in rows}
        feedback_total = sum(
            config["feedback_count"]
            for manager in managers.values()
            for config in manager["configs"]
        )

        return {
            "summary": {
                "active_managers": len(active_managers),
                "configs_with_data": len(config_names),
                "feedback_count": feedback_total,
            },
            "managers": list(managers.values()),
            "historical_unknown": historical,
        }
    finally:
        if owns_connection:
            conn.close()


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def format_manager_config_report(report: dict[str, Any]) -> str:
    """Format a report returned by get_manager_config_report()."""
    summary = report["summary"]
    lines = [
        "MANAGER CONFIG REPORT V1",
        "=" * 60,
        f"Active managers: {summary['active_managers']}",
        f"Configs with data: {summary['configs_with_data']}",
        f"Unique cards with feedback: {summary['feedback_count']}",
    ]

    for manager in report["managers"]:
        lines.extend(["", manager["display_name"], "-" * 60])
        if not manager["configs"]:
            lines.append("No config data.")
            continue
        for config in manager["configs"]:
            lines.extend(
                [
                    config["config_name"],
                    f"  Sent: {config['sent_count']}",
                    f"  Feedback: {config['feedback_count']} ({_percent(config['feedback_rate'])})",
                    (
                        "  Actions: "
                        f"review={config['review_count']} ({_percent(config['review_rate'])}), "
                        f"think={config['think_count']} ({_percent(config['think_rate'])}), "
                        f"skip={config['skip_count']} ({_percent(config['skip_rate'])})"
                    ),
                    f"  Manager Interest Score: {config['interest_score']}",
                    f"  Last feedback: {config['last_feedback_at'] or '-'}",
                ]
            )
            if config["top_reasons"]:
                reason_text = ", ".join(
                    f"{item['reason_code']} ({item['count']})"
                    for item in config["top_reasons"]
                )
                lines.append(f"  Top reasons: {reason_text}")
            else:
                lines.append("  Top reasons: -")

    unknown = report["historical_unknown"]
    lines.extend(
        [
            "",
            "Historical data (excluded from ratings)",
            "-" * 60,
            f"sent_ads unknown: {unknown['sent_ads']}",
            f"feedback unknown: {unknown['feedback']}",
            f"reaction_details unknown: {unknown['reaction_details']}",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Print Manager Config Report v1")
    parser.add_argument("--db", default=str(DB_PATH), help="Path to feedback.db")
    args = parser.parse_args()
    print(format_manager_config_report(get_manager_config_report(args.db)))


if __name__ == "__main__":
    main()
