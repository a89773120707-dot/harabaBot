"""
feedback_report.py — Блок 17.10: аналитика по feedback.db

Читает feedback.db и печатает:
- buy/watch/skip counts
- top models by reactions
- top regions
- avg price by action
- score distribution by action

Запуск:
  python feedback_report.py
  python feedback_report.py --days 30
  python feedback_report.py --export results/feedback_report.json
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from feedback_store import get_feedback_all, get_feedback_stats, get_sent_stats
from base import log, RESULTS_DIR


def format_number(n, suffix=""):
    """Форматировать число с разделителями."""
    try:
        return f"{int(n):,}".replace(",", " ") + suffix
    except (ValueError, TypeError):
        return str(n) + suffix


def print_section(title):
    """Печатать заголовок секции."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def report_action_counts(days=7):
    """Количество реакций по типу."""
    stats = get_feedback_stats(days=days)
    total = sum(stats.values())

    print_section(f"Реакции за {days} дней")
    print(f"  Всего реакций: {total}")
    print()

    action_labels = {
        "buy": "🟢 Купить",
        "watch": "🟡 Посмотреть",
        "skip": "🔴 Скипнуть",
    }

    for action in ["buy", "watch", "skip"]:
        count = stats.get(action, 0)
        pct = round(count / total * 100, 1) if total > 0 else 0
        label = action_labels.get(action, action)
        bar = "█" * (int(pct) // 2)
        print(f"  {label}: {count:>4} ({pct:>5}%) {bar}")


def report_top_models(days=7):
    """Топ моделей по реакциям."""
    feedbacks = get_feedback_all(days=days)
    if not feedbacks:
        print(f"\n  Нет данных за {days} дней")
        return

    model_counter = Counter()
    model_actions = defaultdict(lambda: Counter())

    for fb in feedbacks:
        title = fb.get("title", "Unknown")
        # Извлечь модель из title (первое слово)
        model = title.split()[0] if title else "Unknown"
        action = fb.get("action", "unknown")
        model_counter[model] += 1
        model_actions[model][action] += 1

    print_section(f"Топ моделей по реакциям ({days} дней)")

    for model, count in model_counter.most_common(15):
        actions = model_actions[model]
        buy = actions.get("buy", 0)
        watch = actions.get("watch", 0)
        skip = actions.get("skip", 0)
        print(f"  {model:>20}: {count:>3} всего  (🟢{buy}  🟡{watch}  🔴{skip})")


def report_top_regions(days=7):
    """Топ регионов по реакциям."""
    feedbacks = get_feedback_all(days=days)
    if not feedbacks:
        print(f"\n  Нет данных за {days} дней")
        return

    region_counter = Counter()
    region_actions = defaultdict(lambda: Counter())

    for fb in feedbacks:
        region = fb.get("region", "unknown")
        if region == "unknown" or not region:
            continue
        action = fb.get("action", "unknown")
        region_counter[region] += 1
        region_actions[region][action] += 1

    print_section(f"Топ регионов ({days} дней)")

    for region, count in region_counter.most_common(15):
        actions = region_actions[region]
        buy = actions.get("buy", 0)
        watch = actions.get("watch", 0)
        skip = actions.get("skip", 0)
        print(f"  {region:>25}: {count:>3} всего  (🟢{buy}  🟡{watch}  🔴{skip})")


def report_avg_price_by_action(days=7):
    """Средняя цена по типу реакции."""
    feedbacks = get_feedback_all(days=days)
    if not feedbacks:
        print(f"\n  Нет данных за {days} дней")
        return

    prices_by_action = defaultdict(list)

    for fb in feedbacks:
        action = fb.get("action", "unknown")
        price = fb.get("price", 0)
        if price and price > 0:
            prices_by_action[action].append(price)

    print_section(f"Средняя цена по реакции ({days} дней)")

    action_labels = {
        "buy": "🟢 Купить",
        "watch": "🟡 Посмотреть",
        "skip": "🔴 Скипнуть",
    }

    for action in ["buy", "watch", "skip"]:
        prices = prices_by_action.get(action, [])
        if prices:
            avg = sum(prices) / len(prices)
            median = sorted(prices)[len(prices) // 2]
            label = action_labels.get(action, action)
            print(f"  {label}:")
            print(f"    Средняя: {format_number(avg, ' ₽')}")
            print(f"    Медиана: {format_number(median, ' ₽')}")
            print(f"    Мин:     {format_number(min(prices), ' ₽')}")
            print(f"    Макс:    {format_number(max(prices), ' ₽')}")
            print(f"    Кол-во:  {len(prices)}")
        else:
            label = action_labels.get(action, action)
            print(f"  {label}: нет данных")


def report_score_distribution(days=7):
    """Распределение скоринга по реакции."""
    feedbacks = get_feedback_all(days=days)
    if not feedbacks:
        print(f"\n  Нет данных за {days} дней")
        return

    scores_by_action = defaultdict(list)

    for fb in feedbacks:
        action = fb.get("action", "unknown")
        score = fb.get("score", 0)
        if score and score > 0:
            scores_by_action[action].append(score)

    print_section(f"Распределение скоринга по реакции ({days} дней)")

    action_labels = {
        "buy": "🟢 Купить",
        "watch": "🟡 Посмотреть",
        "skip": "🔴 Скипнуть",
    }

    for action in ["buy", "watch", "skip"]:
        scores = scores_by_action.get(action, [])
        if scores:
            avg = sum(scores) / len(scores)
            label = action_labels.get(action, action)
            print(f"  {label}:")
            print(f"    Средний score: {avg:.1f}")
            print(f"    Мин:           {min(scores)}")
            print(f"    Макс:          {max(scores)}")

            # Гистограмма по диапазонам
            buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
            for s in scores:
                if s <= 20:
                    buckets["0-20"] += 1
                elif s <= 40:
                    buckets["21-40"] += 1
                elif s <= 60:
                    buckets["41-60"] += 1
                elif s <= 80:
                    buckets["61-80"] += 1
                else:
                    buckets["81-100"] += 1

            for bucket, count in buckets.items():
                if count > 0:
                    bar = "█" * count
                    print(f"      {bucket}: {count:>3} {bar}")
        else:
            label = action_labels.get(action, action)
            print(f"  {label}: нет данных")


def report_sent_summary():
    """Общая статистика отправленных."""
    stats = get_sent_stats()
    print_section("Отправленные карточки (всё время)")
    print(f"  Всего отправлено: {stats['total']}")

    if stats["by_model"]:
        print(f"\n  По моделям:")
        for model_id, count in sorted(stats["by_model"].items(), key=lambda x: -x[1])[:10]:
            print(f"    {model_id:>20}: {count}")


def export_report(days=7, output_path=None):
    """Экспорт полного отчёта в JSON."""
    feedbacks = get_feedback_all(days=days)

    report = {
        "generated_at": "now",
        "days": days,
        "total_feedbacks": len(feedbacks),
    }

    # Action counts
    action_counts = Counter()
    prices_by_action = defaultdict(list)
    scores_by_action = defaultdict(list)
    model_counter = Counter()
    region_counter = Counter()

    for fb in feedbacks:
        action = fb.get("action", "unknown")
        action_counts[action] += 1

        price = fb.get("price", 0)
        if price > 0:
            prices_by_action[action].append(price)

        score = fb.get("score", 0)
        if score > 0:
            scores_by_action[action].append(score)

        title = fb.get("title", "")
        model = title.split()[0] if title else "unknown"
        model_counter[model] += 1

        region = fb.get("region", "unknown")
        if region and region != "unknown":
            region_counter[region] += 1

    report["action_counts"] = dict(action_counts)

    # Avg prices
    avg_prices = {}
    for action, prices in prices_by_action.items():
        if prices:
            avg_prices[action] = {
                "avg": round(sum(prices) / len(prices), 0),
                "median": sorted(prices)[len(prices) // 2],
                "min": min(prices),
                "max": max(prices),
                "count": len(prices),
            }
    report["avg_price_by_action"] = avg_prices

    # Score distribution
    score_stats = {}
    for action, scores in scores_by_action.items():
        if scores:
            score_stats[action] = {
                "avg": round(sum(scores) / len(scores), 1),
                "min": min(scores),
                "max": max(scores),
                "count": len(scores),
            }
    report["score_distribution"] = score_stats

    # Top models
    report["top_models"] = dict(model_counter.most_common(15))
    report["top_regions"] = dict(region_counter.most_common(15))

    # Sent stats
    report["sent_stats"] = get_sent_stats()

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  💾 Отчёт сохранён: {output_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Feedback Analytics")
    parser.add_argument("--days", type=int, default=7, help="Период в днях (default 7)")
    parser.add_argument("--export", type=str, default=None, help="Путь для экспорта JSON")
    args = parser.parse_args()

    print("=" * 60)
    print("  FEEDBACK ANALYTICS")
    print("=" * 60)
    print(f"  Период: {args.days} дней")

    # Отправленные
    report_sent_summary()

    # Реакции
    report_action_counts(days=args.days)

    # Топ моделей
    report_top_models(days=args.days)

    # Топ регионов
    report_top_regions(days=args.days)

    # Средняя цена
    report_avg_price_by_action(days=args.days)

    # Распределение скоринга
    report_score_distribution(days=args.days)

    # Экспорт
    if args.export:
        export_report(days=args.days, output_path=args.export)

    print(f"\n{'='*60}")
    print("  Готово!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
