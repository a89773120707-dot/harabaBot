"""block3_price_ranges.py — Блок 3: ценовые коридоры для 9 моделей"""
import yaml, glob

def clean(v):
    """Убирает .0 из целых чисел."""
    if v is None:
        return "N/A"
    if isinstance(v, float) and v == int(v):
        return int(v)
    return v


files = glob.glob("results/market_analysis_*.yaml")
output = {"price_ranges_9": {}}

for f in sorted(files):
    with open(f, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    for model_id, m in data.get("models", {}).items():
        status = m.get("status", "unknown")
        cards = m.get("cards_checked", 0)
        evaluated = m.get("evaluated_cards", 0)
        eval_min = clean(m.get("evaluation_min_median"))
        eval_max = clean(m.get("evaluation_max_median"))
        good_buy = clean(m.get("good_buy_price"))
        suspicious = clean(m.get("suspicious_low_price"))

        if eval_min is None or eval_max is None or good_buy is None:
            continue

        # Формулы
        expensive_top = round(eval_max * 1.07)

        # Confidence
        if status == "low_evaluation_sample":
            confidence = "low"
            need_review = True
        else:
            confidence = "medium"
            need_review = False

        entry = {
            "status": status,
            "confidence": confidence,
            "source": "auto_ru_evaluation_aggregator",
            "cards_checked": cards,
            "evaluated_cards": evaluated,
            "evaluation_min_median": eval_min,
            "evaluation_max_median": eval_max,
            "good_buy_price": good_buy,
            "target": {
                "suspicious_low": f"<{suspicious}" if suspicious else "N/A",
                "excellent": f"<{good_buy}",
                "good": f"{good_buy}-{eval_min}",
                "fair": f"{eval_min}-{eval_max}",
                "expensive_but_ok_if_top": f"{eval_max}-{expensive_top}",
                "reject_if_weak": f"{expensive_top}+",
            },
        }

        if need_review:
            entry["need_manual_review"] = True

        output["price_ranges_9"][model_id] = entry

out_path = "results/price_ranges_9.yaml"
with open(out_path, "w", encoding="utf-8") as f:
    yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

print(f"💾 Сохранено: {out_path}")
print(f"Моделей: {len(output['price_ranges_9'])}")

for mid, entry in output["price_ranges_9"].items():
    t = entry["target"]
    print(f"\n{mid}: status={entry['status']}, confidence={entry['confidence']}")
    for k, v in t.items():
        print(f"  {k}: {v}")
