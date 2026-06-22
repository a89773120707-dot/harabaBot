"""Read-only config suggestion engine based on feedback analytics."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any


DB_PATH = Path("results/feedback.db")
VALID_CONFIG_SQL = "config_name IS NOT NULL AND config_name != '' AND config_name != 'unknown'"

REASON_TITLES = {
    "good_price": "Хорошая цена",
    "low_mileage": "Небольшой пробег",
    "liquid_model": "Ликвидная модель",
    "good_equipment": "Хорошая комплектация",
    "comment": "Комментарий",
    "good_condition": "Хорошее состояние",
    "good_history": "Хорошая история",
    "few_owners": "Немного владельцев",
    "good_region": "Хороший регион",
    "review_other": "Другое",
    "high_price": "Высокая цена",
    "high_mileage": "Большой пробег",
    "many_owners": "Много владельцев",
    "poor_equipment": "Слабая комплектация",
    "history_questions": "Вопросы по истории",
    "bad_color": "Неудачный цвет",
    "bad_modification": "Неудачная модификация",
    "bad_region": "Неудачный регион",
    "need_more_info": "Нужно изучить подробнее",
    "think_other": "Другое",
    "too_expensive": "Слишком дорого",
    "too_mileage": "Слишком большой пробег",
    "bad_condition": "Плохое состояние",
    "legal_risk": "Юридические риски",
    "not_my_model": "Не моя модель",
    "not_my_segment": "Не мой сегмент",
    "illiquid": "Неликвидная модель",
    "skip_other": "Другое",
}

PRICE_REASONS = {"high_price", "too_expensive"}
MILEAGE_REASONS = {"high_mileage", "too_mileage"}
CONDITION_REASONS = {
    "bad_condition",
    "many_owners",
    "history_questions",
    "legal_risk",
}
POSITIVE_PRIORITY_REASONS = {"good_price", "liquid_model"}


def _open_read_only(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path).resolve()
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _normalize_comment(comment: str | None) -> str | None:
    if comment is None:
        return None
    normalized = comment.strip()
    if not normalized or normalized == "-":
        return None
    return normalized


def _reason_title(reason_code: str) -> str:
    return REASON_TITLES.get(reason_code, "Неизвестная причина")


def _readiness(feedback_count: int) -> tuple[str, str]:
    if feedback_count < 5:
        return "NOT_READY", "LOW"
    if feedback_count < 10:
        return "LOW", "LOW"
    if feedback_count < 20:
        return "MEDIUM", "MEDIUM"
    return "HIGH", "HIGH"


def _reason_pressure(count: int, feedback_count: int) -> float:
    return count / feedback_count if feedback_count else 0.0


def _top_reason(dominant_reasons: list[dict[str, Any]]) -> dict[str, Any] | None:
    return dominant_reasons[0] if dominant_reasons else None


def _has_mixed_signals(
    interest_score: int,
    dominant_reasons: list[dict[str, Any]],
) -> bool:
    reason_codes = {str(reason["reason_code"]) for reason in dominant_reasons}
    has_positive_reason = bool(reason_codes & POSITIVE_PRIORITY_REASONS)
    has_negative_reason = bool(reason_codes & (PRICE_REASONS | MILEAGE_REASONS | CONDITION_REASONS))
    top = _top_reason(dominant_reasons)
    top_pressure = float(top["pressure"]) if top else 0.0
    return (
        interest_score > 0
        and has_positive_reason
        and has_negative_reason
        and top_pressure < 0.5
    )


def _recommendation_for(
    *,
    readiness: str,
    interest_score: int,
    dominant_reasons: list[dict[str, Any]],
) -> tuple[str, str]:
    if readiness == "NOT_READY":
        return (
            "insufficient_data",
            "Недостаточно данных. Нужно больше реакций перед изменением конфига.",
        )

    top = _top_reason(dominant_reasons)
    top_code = str(top["reason_code"]) if top else ""

    if _has_mixed_signals(interest_score, dominant_reasons):
        return (
            "mixed_signals",
            "Модель интересная, но сигналы смешанные. Требуется накопление данных.",
        )
    if top_code in PRICE_REASONS:
        return (
            "review_price_range",
            "Проверить ценовой диапазон и price/value фильтр. Не увеличивать max_price автоматически.",
        )
    if top_code in MILEAGE_REASONS:
        return (
            "review_mileage",
            "Проверить ограничение пробега для этого конфига.",
        )
    if top_code in CONDITION_REASONS:
        return (
            "review_condition",
            "Проверить фильтр состояния, истории и качества карточек.",
        )
    if top_code in POSITIVE_PRIORITY_REASONS and interest_score > 0:
        return (
            "increase_priority",
            "Модель даёт интересные варианты, можно рассмотреть повышение приоритета.",
        )
    if interest_score < 0:
        return (
            "decrease_priority",
            "Модель часто отклоняют, стоит понизить приоритет или проверить критерии поиска.",
        )
    if interest_score > 0:
        return (
            "keep_as_is",
            "Модель интересная, оставить как есть и продолжать сбор реакций.",
        )
    return (
        "mixed_signals",
        "Сигналы неясные, требуется накопление данных.",
    )


def _build_evidence(
    *,
    feedback_count: int,
    participants_count: int,
    interest_score: int,
    dominant_reasons: list[dict[str, Any]],
    comments_evidence: list[dict[str, Any]],
    owner_feedback_count: int,
) -> list[str]:
    evidence = [
        f"Feedback: {feedback_count}",
        f"Participants: {participants_count}",
        f"Interest score: {interest_score:+d}",
    ]
    top = _top_reason(dominant_reasons)
    if top:
        evidence.append(
            "Dominant reason: "
            f"{top['reason_text']} {top['count']}/{feedback_count} "
            f"({_percent(float(top['pressure']))})"
        )
    if owner_feedback_count:
        evidence.append(f"Owner contributed {owner_feedback_count} feedback")
    if comments_evidence:
        evidence.append(f"Comments evidence: {len(comments_evidence)}")
    return evidence


def get_config_suggestions(
    db_path: str | Path = DB_PATH,
    *,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Return conservative config suggestions without modifying the database."""
    conn = connection or _open_read_only(db_path)
    owns_connection = connection is None
    conn.row_factory = sqlite3.Row

    try:
        participants = conn.execute(
            """
            SELECT
                CAST(telegram_id AS TEXT) AS participant_id,
                role
            FROM telegram_users
            WHERE status = 'active'
              AND analytics_participant = 1
            """
        ).fetchall()
        participant_ids = [str(row["participant_id"]) for row in participants]
        owner_ids = {
            str(row["participant_id"])
            for row in participants
            if str(row["role"]) == "owner"
        }

        if not participant_ids:
            return {
                "summary": {
                    "configs_count": 0,
                    "suggestions_count": 0,
                    "analytics_participants": 0,
                    "ready_configs": 0,
                },
                "suggestions": [],
            }

        placeholders = ",".join("?" for _ in participant_ids)
        rows = conn.execute(
            f"""
            WITH latest_feedback_ids AS (
                SELECT
                    CAST(f.telegram_user_id AS TEXT) AS participant_id,
                    f.card_id,
                    f.config_name,
                    MAX(f.id) AS feedback_id
                FROM feedback f
                WHERE f.{VALID_CONFIG_SQL}
                  AND CAST(f.telegram_user_id AS TEXT) IN ({placeholders})
                GROUP BY CAST(f.telegram_user_id AS TEXT), f.card_id, f.config_name
            ),
            latest_feedback AS (
                SELECT
                    l.participant_id,
                    l.card_id,
                    l.config_name,
                    f.id AS feedback_id,
                    f.action,
                    f.comment,
                    f.created_at
                FROM latest_feedback_ids l
                JOIN feedback f ON f.id = l.feedback_id
            )
            SELECT
                config_name,
                COUNT(*) AS feedback_count,
                COUNT(DISTINCT participant_id) AS participants_count,
                SUM(CASE WHEN action = 'review' THEN 1 ELSE 0 END) AS review_count,
                SUM(CASE WHEN action = 'think' THEN 1 ELSE 0 END) AS think_count,
                SUM(CASE WHEN action = 'skip' THEN 1 ELSE 0 END) AS skip_count,
                SUM(
                    CASE
                        WHEN action = 'review' THEN 2
                        WHEN action = 'think' THEN 1
                        WHEN action = 'skip' THEN -2
                        ELSE 0
                    END
                ) AS interest_score,
                SUM(CASE WHEN participant_id IN ({",".join("?" for _ in owner_ids) or "NULL"}) THEN 1 ELSE 0 END)
                    AS owner_feedback_count
            FROM latest_feedback
            GROUP BY config_name
            ORDER BY feedback_count DESC, interest_score DESC, config_name
            """,
            [*participant_ids, *owner_ids],
        ).fetchall()

        reason_rows = conn.execute(
            f"""
            WITH latest_feedback_ids AS (
                SELECT
                    CAST(f.telegram_user_id AS TEXT) AS participant_id,
                    f.card_id,
                    f.config_name,
                    MAX(f.id) AS feedback_id
                FROM feedback f
                WHERE f.{VALID_CONFIG_SQL}
                  AND CAST(f.telegram_user_id AS TEXT) IN ({placeholders})
                GROUP BY CAST(f.telegram_user_id AS TEXT), f.card_id, f.config_name
            )
            SELECT
                l.config_name,
                rd.reason_code,
                COUNT(*) AS reason_count
            FROM latest_feedback_ids l
            JOIN reaction_details rd ON rd.feedback_id = l.feedback_id
            WHERE rd.reason_code IS NOT NULL
              AND TRIM(rd.reason_code) != ''
              AND rd.reason_code != 'comment'
            GROUP BY l.config_name, rd.reason_code
            ORDER BY l.config_name, reason_count DESC, rd.reason_code
            """,
            participant_ids,
        ).fetchall()

        comments = conn.execute(
            f"""
            WITH latest_feedback_ids AS (
                SELECT
                    CAST(f.telegram_user_id AS TEXT) AS participant_id,
                    f.card_id,
                    f.config_name,
                    MAX(f.id) AS feedback_id
                FROM feedback f
                WHERE f.{VALID_CONFIG_SQL}
                  AND CAST(f.telegram_user_id AS TEXT) IN ({placeholders})
                GROUP BY CAST(f.telegram_user_id AS TEXT), f.card_id, f.config_name
            )
            SELECT
                l.config_name,
                l.participant_id,
                f.comment,
                f.created_at
            FROM latest_feedback_ids l
            JOIN feedback f ON f.id = l.feedback_id
            WHERE f.comment IS NOT NULL
            ORDER BY l.config_name, f.created_at DESC, f.id DESC
            """,
            participant_ids,
        ).fetchall()

        reasons_by_config: dict[str, list[dict[str, Any]]] = {}
        feedback_by_config = {str(row["config_name"]): int(row["feedback_count"]) for row in rows}
        for row in reason_rows:
            config_name = str(row["config_name"])
            reason_code = str(row["reason_code"])
            count = int(row["reason_count"])
            feedback_count = feedback_by_config.get(config_name, 0)
            reasons_by_config.setdefault(config_name, []).append(
                {
                    "reason_code": reason_code,
                    "reason_text": _reason_title(reason_code),
                    "count": count,
                    "pressure": _reason_pressure(count, feedback_count),
                }
            )

        comments_by_config: dict[str, list[dict[str, Any]]] = {}
        for row in comments:
            comment = _normalize_comment(row["comment"])
            if comment is None:
                continue
            config_name = str(row["config_name"])
            bucket = comments_by_config.setdefault(config_name, [])
            if len(bucket) < 3:
                bucket.append(
                    {
                        "participant_id": str(row["participant_id"]),
                        "comment": comment,
                        "created_at": row["created_at"],
                    }
                )

        suggestions: list[dict[str, Any]] = []
        for row in rows:
            config_name = str(row["config_name"])
            feedback_count = int(row["feedback_count"])
            participants_count = int(row["participants_count"])
            review_count = int(row["review_count"] or 0)
            think_count = int(row["think_count"] or 0)
            skip_count = int(row["skip_count"] or 0)
            interest_score = int(row["interest_score"] or 0)
            owner_feedback_count = int(row["owner_feedback_count"] or 0)
            readiness, confidence = _readiness(feedback_count)
            dominant_reasons = reasons_by_config.get(config_name, [])[:3]
            comments_evidence = comments_by_config.get(config_name, [])
            recommendation_type, recommendation_text = _recommendation_for(
                readiness=readiness,
                interest_score=interest_score,
                dominant_reasons=dominant_reasons,
            )

            suggestions.append(
                {
                    "config_name": config_name,
                    "feedback_count": feedback_count,
                    "participants_count": participants_count,
                    "review_count": review_count,
                    "think_count": think_count,
                    "skip_count": skip_count,
                    "interest_score": interest_score,
                    "dominant_reasons": dominant_reasons,
                    "comments_evidence": comments_evidence,
                    "owner_feedback_count": owner_feedback_count,
                    "owner_signal_present": owner_feedback_count > 0,
                    "recommendation_type": recommendation_type,
                    "recommendation_text": recommendation_text,
                    "confidence": confidence,
                    "readiness": readiness,
                    "evidence": _build_evidence(
                        feedback_count=feedback_count,
                        participants_count=participants_count,
                        interest_score=interest_score,
                        dominant_reasons=dominant_reasons,
                        comments_evidence=comments_evidence,
                        owner_feedback_count=owner_feedback_count,
                    ),
                }
            )

        return {
            "summary": {
                "configs_count": len(suggestions),
                "suggestions_count": len(suggestions),
                "analytics_participants": len(participant_ids),
                "ready_configs": sum(
                    1 for item in suggestions if item["readiness"] != "NOT_READY"
                ),
            },
            "suggestions": suggestions,
        }
    finally:
        if owns_connection:
            conn.close()


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


READINESS_LABELS = {
    "HIGH": "🟢 HIGH",
    "MEDIUM": "🟡 MEDIUM",
    "LOW": "🟠 LOW",
    "NOT_READY": "⚪ NOT_READY",
}

READINESS_ORDER = ("HIGH", "MEDIUM", "LOW", "NOT_READY")


def _readiness_label(readiness: str) -> str:
    return READINESS_LABELS.get(readiness, readiness)


def _reaction_word(count: int) -> str:
    remainder = abs(count) % 100
    if 11 <= remainder <= 14:
        return "реакций"
    last_digit = remainder % 10
    if last_digit == 1:
        return "реакция"
    if 2 <= last_digit <= 4:
        return "реакции"
    return "реакций"


def _participant_word(count: int) -> str:
    remainder = abs(count) % 100
    if 11 <= remainder <= 14:
        return "участников"
    last_digit = remainder % 10
    if last_digit == 1:
        return "участник"
    if 2 <= last_digit <= 4:
        return "участника"
    return "участников"


def _group_suggestions(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {readiness: [] for readiness in READINESS_ORDER}
    for item in items:
        readiness = str(item.get("readiness") or "NOT_READY")
        grouped.setdefault(readiness, []).append(item)
    return grouped


def _format_ready_item(item: dict[str, Any]) -> list[str]:
    feedback_count = int(item["feedback_count"])
    participants_count = int(item["participants_count"])
    interest_score = int(item["interest_score"])
    lines = [
        f"{_readiness_label(str(item['readiness']))} {item['config_name']}",
        "",
        "💡 Что сделать:",
        str(item["recommendation_text"]),
        "",
    ]

    if item.get("dominant_reasons"):
        lines.append("Почему:")
        for reason in item["dominant_reasons"][:3]:
            lines.append(
                f"• {reason['reason_text']} — {reason['count']} из {feedback_count}"
            )
        lines.append("")

    comments = item.get("comments_evidence", [])[:2]
    if comments:
        lines.append("💬 Комментарии")
        lines.append("")
        for comment in comments:
            lines.append(f"• {comment['comment']}")
        lines.append("")

    lines.append(
        "Данные: "
        f"{feedback_count} {_reaction_word(feedback_count)} | "
        f"{participants_count} {_participant_word(participants_count)} | "
        f"score {interest_score:+d}"
    )

    if item.get("owner_signal_present"):
        owner_feedback_count = int(item.get("owner_feedback_count", 0))
        lines.append(
            f"👤 Owner участвовал: {owner_feedback_count} "
            f"{_reaction_word(owner_feedback_count)}"
        )

    return lines


def _format_not_ready_items(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return []

    lines = ["⚪ Недостаточно данных", ""]
    for item in items:
        feedback_count = int(item["feedback_count"])
        needed = max(0, 5 - feedback_count)
        lines.append(
            f"{item['config_name']} — "
            f"{feedback_count} {_reaction_word(feedback_count)}, "
            f"нужно ещё {needed}"
        )
    return lines


def format_config_suggestions(suggestions: dict[str, Any]) -> str:
    """Format suggestions for CLI or Telegram-compatible plain text."""
    summary = suggestions.get("summary", {})
    items = suggestions.get("suggestions", [])
    grouped = _group_suggestions(items)
    not_ready_count = len(grouped.get("NOT_READY", []))
    lines = [
        "💡 Config Suggestions",
        "",
        f"📊 Всего конфигов: {int(summary.get('configs_count', 0))}",
        f"🟡 Готовы к анализу: {int(summary.get('ready_configs', 0))}",
        f"⚪ Недостаточно данных: {not_ready_count}",
    ]

    if not items:
        lines.extend(["", "Данных для рекомендаций пока нет."])
        return "\n".join(lines)

    low_items = grouped.get("LOW", [])
    if low_items:
        lines.extend(["", "🟠 LOW:", *[str(item["config_name"]) for item in low_items]])

    for readiness in ("HIGH", "MEDIUM", "LOW"):
        group = grouped.get(readiness, [])
        if not group:
            continue
        lines.extend(["", _readiness_label(readiness), ""])
        for index, item in enumerate(group):
            if index:
                lines.append("")
            lines.extend(_format_ready_item(item))

    not_ready_lines = _format_not_ready_items(grouped.get("NOT_READY", []))
    if not_ready_lines:
        lines.extend(["", *not_ready_lines])

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Show config suggestions.")
    parser.add_argument("--db-path", default=str(DB_PATH))
    args = parser.parse_args()
    print(format_config_suggestions(get_config_suggestions(args.db_path)))


if __name__ == "__main__":
    main()
