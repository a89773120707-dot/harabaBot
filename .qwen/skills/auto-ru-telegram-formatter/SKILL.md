---
name: auto-ru-telegram-formatter
description: Auto.ru card formatter for Telegram — human-readable output with verdict, valuation, and reasons
source: auto-skill
extracted_at: '2026-06-11T22:00:00.000Z'
---

# Auto.ru Telegram Formatter

## Purpose

Generate human-readable Telegram messages for Auto.ru car cards.

**Does NOT send messages.** Only formats text for review (dry run).

## Architecture

```
SQLite (sent_ads WHERE source='auto_ru')
    ↓
format_auto_ru_card(card) → str
    ↓
Telegram message text
```

## Card Format

### Full Format (for excellent/good deals):

```
🚗 Kia Rio IV Рестайлинг 2021

💰 Цена: 1 390 000 ₽

📊 Auto.ru оценка:
1 344 000 ₽ – 1 493 000 ₽
Средняя: ~1 418 500 ₽

✅ Статус Auto.ru:
Справедливая цена

🛠 Характеристики:
Пробег: 119 000 км
Двигатель: 1.6 л, 123 л.с., бензин
Коробка: Автоматическая
Привод: Передний
Владельцев: 1

🎯 Вердикт:
✅ Хорошая цена

Причины:
• цена ниже верхней границы Auto.ru на 103 000 ₽
• Auto.ru: справедливая цена

Рекомендация:
Рассмотреть

🔗 Ссылка:
https://auto.ru/cars/used/sale/kia/rio/1132951420-8a165e88/
```

### Short Format (for list/preview):

```
✅ Kia Rio IV Рестайлинг 2021 | 1.39 млн ₽ | Справедливая цена
```

## Status Emoji Mapping

| Status | Emoji | Label |
|--------|-------|-------|
| excellent_deal | 🔥 | Отличная сделка |
| good_deal | ✅ | Хорошая цена |
| fair_price | | Справедливая цена |
| slightly_overpriced | ⚠️ | Slightly выше рынка |
| strong_overpriced | ❌ | Сильно выше рынка |
| no_data | ❓ | Недостаточно данных |

## Auto.ru Status Emoji

| Status | Emoji | Label |
|--------|-------|-------|
| above_market | ⬆️ | Выше оценки |
| below_market | ⬇️ | Ниже оценки |
| fair_price | | Справедливая цена |

## Files

| File | Purpose |
|------|---------|
| `app/telegram/auto_ru_formatter.py` | Main formatter module |
| `test_auto_ru_formatter.py` | Test on cards from SQLite |
| `test_auto_ru_telegram_dry_run.py` | Full dry run (generates preview) |

## Functions

### `format_auto_ru_card(card: dict) -> str`

Full card format with all fields.

### `format_short_card(card: dict) -> str`

Short preview format (one line).

### `format_price(val) -> str`

Helper: `1800000` → `"1 800 000 ₽"`

## Card Input Format

The formatter accepts cards from two sources:

### 1. From SQLite (flat columns):
```python
{
    "price": 1390000,
    "auto_ru_price_low": 1344000,
    "auto_ru_price_high": 1493000,
    "auto_ru_estimate_mid": 1418500,
    "auto_ru_status": "fair_price",
    "auto_ru_status_text": "Справедливая цена",
    "final_verdict": "good_deal",
    "final_recommendation": "Рассмотреть",
    "final_reasons": ["причина 1", "причина 2"],
    ...
}
```

### 2. From full card parser (nested):
```python
{
    "seller_price": 1390000,
    "auto_ru_valuation": {
        "price_low": 1344000,
        "price_high": 1493000,
        "estimate_mid": 1418500,
        "status": "fair_price",
        "status_text": "Справедливая цена",
    },
    "final_price_decision": {
        "final_verdict": "good_deal",
        "final_label": "Хорошая цена",
        "final_emoji": "✅",
        "recommendation": "Рассмотреть",
        "reasons": [...],
    },
    ...
}
```

## Dry Run Output

```bash
python test_auto_ru_telegram_dry_run.py
# Output: results/debug/telegram_preview.txt
```

### Preview Structure:
```
AUTO.RU TELEGRAM PREVIEW
Дата: 2026-06-11 21:53:33
======================================================================

🔥 ОТЛИЧНЫЕ И ХОРОШИЕ СДЕЛКИ (1)
======================================================================

--- Карточка 1 ---
🚗 Kia Rio IV Рестайлинг 2021
...

⏭️ ОСТАЛЬНЫЕ (2)
======================================================================

--- Карточка 1 ---
🚗 Honda Freed II Рестайлинг 2021
...
```

## Critical Rules

1. **NEVER send messages** from formatter or dry run — only format text
2. **Separate excellent/good** from others in preview
3. **Always include**: price, valuation range, status, verdict, reasons, link
4. **If valuation range missing**: show "Диапазон не найден" instead of fake numbers
5. **estimate_mid is calculated**: label it "Средняя: ~X ₽" not "Оценка Auto.ru: X ₽"
