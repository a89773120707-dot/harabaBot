"""prepare_manual_review.py — Блок 13.6-13.7: TOP-списки + ручная проверка"""
import yaml
import json
from pathlib import Path
from base import RESULTS_DIR

# Загружаем результаты скоринга
with open(RESULTS_DIR / "config_scoring_test_500.yaml", "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

results = data.get("results", [])

# Сортируем по score
sorted_results = sorted(results, key=lambda r: r.get("score", 0), reverse=True)

# Разделяем по decision
by_decision = {}
for r in sorted_results:
    d = r.get("decision", "unknown")
    if d not in by_decision:
        by_decision[d] = []
    by_decision[d].append(r)

# TOP-20 excellent + good
top_excellent = by_decision.get("excellent_candidate", [])[:20]
top_good = by_decision.get("good_candidate", [])[:20]
top_watch = by_decision.get("watch", [])[:20]
top_reject = by_decision.get("reject", [])[:20]

print(f"excellent: {len(top_excellent)}")
print(f"good: {len(top_good)}")
print(f"watch: {len(top_watch)}")
print(f"reject: {len(top_reject)}")

# Формируем manual review — берём:
# - все excellent + good (есть или нет)
# - топ-10 watch (по score)
# - топ-5 reject (по score)
# - несколько weak для проверки

manual_review = []

for i, r in enumerate(top_excellent + top_good + top_watch[:10] + top_reject[:5] + by_decision.get("weak", [])[:5]):
    card = {
        "id": f"card_{i+1:03d}",
        "title": r.get("title", ""),
        "model_id": r.get("model_id", ""),
        "price": r.get("url", "").startswith("test://") and "N/A" or r.get("price"),
        "year": r.get("year"),
        "mileage": r.get("mileage"),
        "score": r.get("score", 0),
        "decision": r.get("decision", ""),
        "url": r.get("url", ""),
        "explanation": r.get("explanation", ""),
        "bonus_reasons": r.get("bonus_reasons", []),
        "penalty_reasons": r.get("penalty_reasons", []),
        "reject_reasons": r.get("reject_reasons", []),
        "human_verdict": None,
        "comment": None,
    }
    manual_review.append(card)

# Сохраняем
out_path = RESULTS_DIR / "manual_review_top_20.yaml"
with open(out_path, "w", encoding="utf-8") as f:
    yaml.dump({
        "manual_review": manual_review,
        "instructions": """
human_verdict варианты:
  - correct: скоринг верный
  - too_high: score завышен
  - too_low: score занижен
  - should_reject: должен быть reject
  - should_watch: должен быть watch
  - interesting_for_call: стоит позвонить
"""
    }, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120)

print(f"\n💾 {out_path}: {len(manual_review)} карточек")

# Telegram preview для top good/excellent
telegram_lines = []
for r in top_excellent + top_good[:5]:
    title = r.get("title", "Unknown")
    model = r.get("model_id", "")
    score = r.get("score", 0)
    decision = r.get("decision", "")
    url = r.get("url", "")

    emoji = "🔥" if decision == "excellent_candidate" else "✅"
    decision_label = "EXCELLENT" if decision == "excellent_candidate" else "GOOD"

    bonuses = r.get("bonus_reasons", [])
    penalties = r.get("penalty_reasons", [])

    lines = [
        f"{emoji} {title}",
        f"",
        f"Оценка: {score}/100 — {decision_label}",
        f"Модель: {model}",
    ]

    if bonuses:
        lines.append("")
        lines.append("Плюсы:")
        for b in bonuses[:5]:
            lines.append(f"✅ {b}")

    if penalties:
        lines.append("")
        lines.append("Минусы:")
        for p in penalties[:3]:
            lines.append(f"⚠️ {p}")

    if url and not url.startswith("test://"):
        lines.append("")
        lines.append(f"Ссылка: {url}")

    lines.append("")
    lines.append("─" * 40)

    telegram_lines.append("\n".join(lines))

telegram_text = "\n".join(telegram_lines)
tg_path = RESULTS_DIR / "telegram_preview_real.txt"
with open(tg_path, "w", encoding="utf-8") as f:
    f.write(telegram_text)

print(f"💾 {tg_path}")
print(f"\n{'='*50}")
print("PREVIEW первых 3 сообщений:")
print("=" * 50)
for msg in telegram_lines[:3]:
    print(msg)
    print()
