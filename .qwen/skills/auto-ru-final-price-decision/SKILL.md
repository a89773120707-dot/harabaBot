---
name: auto-ru-final-price-decision
description: Final price decision engine — combines Auto.ru valuation range + internal YAML config for purchase verdict
source: auto-skill
extracted_at: '2026-06-11T21:00:00.000Z'
---

# Final Price Decision Engine

## Purpose

Combines two sources of price evaluation to give a clear verdict for the buyer:

1. **Auto.ru valuation range** (low/high from `auto.ru/evaluation/cars/?offer_id=...`)
2. **Internal YAML config** (price ranges from `awd_liquid_full_config.yaml`)

## Key Insight

**Do NOT mix Auto.ru evaluation and internal config assessment.** They are separate:

| Source | What it tells you |
|--------|-------------------|
| Auto.ru range | Market reality (based on recent sales) |
| Internal config | Our preferences for this specific model |

## Architecture

```
parse_full_auto_ru_card()
    ↓
make_final_price_decision(card, full_config)
    ↓
{
    final_verdict: "excellent_deal" | "good_deal" | "fair_price" | "slightly_overpriced" | "strong_overpriced",
    final_label: human-readable,
    final_emoji: 🔥/✅/⚠️/❌/❓,
    recommendation: "Брать немедленно" | "Рассмотреть" | "Скипнуть" | "Проверить вручную",
    priority: 5|4|3|2|1|0,
    delta_to_auto_ru_high: int | None,
    delta_percent_to_auto_ru_high: float | None,
    delta_to_internal_good: int | None,
    delta_percent_to_internal_good: float | None,
    reasons: list[str],
}
```

## Decision Logic

### When both sources available (Auto.ru high + internal good_price_to):

| Condition | Verdict | Priority |
|-----------|---------|----------|
| seller_price <= auto_ru_low AND seller_price <= excellent_price_to | excellent_deal | 5 |
| seller_price <= auto_ru_high AND seller_price <= good_price_to | good_deal | 4 |
| seller_price <= auto_ru_high OR seller_price <= good_price_to | fair_price | 3 |
| seller_price > auto_ru_high AND > good_price_to, over < 25% | slightly_overpriced | 2 |
| seller_price > auto_ru_high AND > good_price_to, over >= 25% | strong_overpriced | 1 |

### When only one source available:

| Condition | Verdict |
|-----------|---------|
| seller_price <= auto_ru_low | excellent_deal |
| seller_price <= auto_ru_high AND delta < 10% | good_deal |
| seller_price > auto_ru_high, over > 25% | strong_overpriced |
| seller_price > auto_ru_high, over 10-25% | slightly_overpriced |
| seller_price > good_price_to, over > 25% | strong_overpriced |

## Files

- `app/analyzer/final_price_decision.py` — main module
- `test_final_price_decision.py` — test on real data from SQLite report

## Usage

```python
from app.analyzer.final_price_decision import make_final_price_decision
from config_loader import load_config

full_cfg = load_config("config/awd_liquid_full_config.yaml")
decision = make_final_price_decision(card, full_cfg)
```

## Example Output

### Ford Kuga (overpriced):
```
final_verdict: "strong_overpriced"
final_label: "Сильно выше рынка"
final_emoji: "❌"
recommendation: "Скипнуть"
priority: 1
delta_to_auto_ru_high: 380000
delta_percent_to_auto_ru_high: 26.8
reasons: [
    "цена выше верхней границы Auto.ru на 380,000 ₽ (26.8%)",
    "Auto.ru: выше оценки на 27%"
]
```

### Honda Freed (underpriced):
```
final_verdict: "excellent_deal"
final_label: "Отличная сделка"
final_emoji: "🔥"
recommendation: "Брать немедленно"
priority: 5
delta_to_auto_ru_high: -328000
delta_percent_to_auto_ru_high: -20.1
reasons: [
    "цена ниже верхней границы Auto.ru на 328,000 ₽",
    "Auto.ru: ниже оценки на 9%"
]
```
