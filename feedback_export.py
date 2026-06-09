"""
feedback_export.py — Блок 16.11: экспорт обратной связи из feedback.db.

Команда:
  python feedback_export.py --days 7

Выход:
  results/feedback_last_7_days.yaml
"""

import argparse
import yaml
import sys
import logging
from collections import Counter
from pathlib import Path

from base import RESULTS_DIR, log
from feedback_store import get_feedback_stats, get_feedback_all

def main():
    parser = argparse.ArgumentParser(description="Export feedback from feedback.db")
    parser.add_argument("--days", type=int, default=7, help="Дней для экспорта (default 7)")
    args = parser.parse_args()

    stats = get_feedback_stats(args.days)
    all_feedback = get_feedback_all(args.days)

    if not all_feedback:
        log.info(f"Нет feedback за последние {args.days} дней")
        return

    # Группировка по модели
    by_model = {}
    for f in all_feedback:
        mid = f.get("model_id", "unknown")
        if mid not in by_model:
            by_model[mid] = {"buy": 0, "watch": 0, "skip": 0}
        action = f.get("action", "")
        if action in by_model[mid]:
            by_model[mid][action] += 1

    # Комментарии
    comments = []
    for f in all_feedback:
        comments.append({
            "card_id": f.get("card_id", ""),
            "title": f.get("title", ""),
            "price": f.get("price", 0),
            "action": f.get("action", ""),
            "comment": f.get("comment", ""),
            "created_at": f.get("created_at", ""),
        })

    export = {
        "period": f"last {args.days} days",
        "total_feedback": len(all_feedback),
        "actions": stats,
        "by_model": by_model,
        "comments": comments,
    }

    export_path = RESULTS_DIR / f"feedback_last_{args.days}_days.yaml"
    with open(export_path, "w", encoding="utf-8") as f:
        yaml.dump(export, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    log.info(f"Экспорт feedback за {args.days} дней:")
    log.info(f"  Total: {len(all_feedback)}")
    log.info(f"  Actions: {stats}")
    log.info(f"  Models: {list(by_model.keys())}")
    log.info(f"  💾 {export_path}")


if __name__ == "__main__":
    main()
