---
name: telegram-card-v2
description: Telegram card V2 final structure — compact layout, unified verdict block, price delta, engine normalized, owners scoring
source: auto-skill
extracted_at: '2026-06-09T11:55:00.000Z'
---

## Telegram Card V2 — Final structure

**Key design decisions:**
1. Seller description is NOT in the card body — only via 📖 Описание button
2. Verdict and "Почему в выборке" are ONE block — no duplication
3. Price delta always shown relative to market upper bound
4. Market ranges always show 🟢🟡🟠 (with fallback if good is missing)

### Card V2 structure

```
✅ Nissan X-Trail (2015)

💰 1 640 000 ₽

📊 Рынок:
🟢 Отличная: 850 000–1 000 000 ₽
🟡 Хорошая: 1 000 000–1 150 000 ₽
🟠 Дорого (если топ): 1 150 000–1 250 000 ₽

📍 Кесова Гора, Тверская область
🛣 140 000 км

⚙️ 2.0 бензин (144 л.с.)
🔄 вариатор
🚙 полный ✅

👤 3 владельца
⚖️ без ограничений ✅

🎯 Почему в выборке:

✅ Полный привод
✅ Вариатор
✅ Без ограничений
✅ 3 владельца
✅ Регион подходит

⚠ цена выше рынка

🧮 Оценка: 80/100
💰 Цена: 0 — выше рынка
🛣 Пробег: +20 — пробег 140,000 км — отличный
⚙️ Двигатель: 0 — допустимый
🔄 Коробка: +10 — рекомендованная (best)
🚙 Привод: +15 — полный
👤 Владельцы: -5 — 3 владельца

🔗 https://m.haraba.ru/search/car/171340559
```

Buttons (2 rows):
```
[🟢 Купить]  [🟡 Посмотреть]
[🔴 Скипнуть] [📖 Описание]
```

### Key principles

1. **Price+market at top** — user's first question is "сколько и дорого ли?"
2. **Price delta** — "Выше верхней границы на 390 000 ₽" not just "Выше допустимого"
3. **Market always shows all ranges** — 🟢🟡🟠 always visible (fallback good=excellent*1.15 if missing)
4. **Engine normalized** — "2.0 бензин (144 л.с.)" not "2.0 CVT, 144 л, 144 л.с., бензин"
5. **Owners formatted** — "3 владельца" not "3 вл."
6. **City+oblast** — "Кесова Гора, Тверская область" not duplicate
7. **Score breakdown always has reason** — no empty "Цена: 0" without explanation
8. **Unified verdict block** — 🎯 Почему в выборке with ✅ pros and ⚠ cons
9. **Автотека removed** — almost all cars have it
10. **Owners in scoring** — "👤 Владельцы: -5 — 3 владельца"
11. **Engine reason clean** — "допустимый" not full engine spec string

### Price block logic

```python
def build_price_block_v2(card, config):
    if current_price:
        lines.append(f"💰 {format_money(current_price)}")
        if excellent_max and good_max and expensive_max:
            if current_price <= excellent_max:
                lines.append(f"🟢 Отличная цена")
            elif current_price <= good_max:
                lines.append(f"🟡 Хорошая цена")
            elif current_price <= expensive_max:
                delta = current_price - good_max
                lines.append(f"🟠 Выше хорошей цены на {format_money(delta)}")
            elif reject_min and current_price >= reject_min:
                delta = current_price - reject_min
                lines.append(f"🔴 Выше верхней границы на {format_money(delta)}")
            else:
                delta = current_price - expensive_max
                lines.append(f"🔴 Выше верхней границы на {format_money(delta)}")
```

### Market fallback (if good is missing)

```python
if good:
    lines.append(f"🟡 Хорошая: {_format_range_label(good)} ₽")
elif excellent_max:
    # Fallback: good = excellent + 15%
    good_lo = excellent_max
    good_hi = int(excellent_max * 1.15)
    lines.append(f"🟡 Хорошая: {good_lo:,}–{good_hi:,} ₽".replace(",", " "))
```

### Engine normalization

```python
def _shorten_engine(engine):
    # "2.0 4WD CVT (144 л.с.) 4WD (Бензин), 2 л" → "2.0 бензин (144 л.с.)"
    # 1. Volume: prefer "2.0" at start, then "2.0 л", then ", 2 л"
    # 2. Fuel from parentheses: (Бензин|Дизель|Газ|Электро)
    # 3. Power from "144 л.с."
    # Format: "{Volume} {fuel} ({Power} л.с.)"
    # Exclude 3-digit numbers (like 144 л.с.) from volume
```

### Owners formatting + scoring

```python
def _format_owners(owners):
    n = int(owners)
    if n == 1: return "1 владелец"
    elif n in (2, 3): return f"{n} владельца"
    else: return f"{n} владельцев"

# In score breakdown:
if n == 1: "👤 Владельцы: +10 — 1 владелец"
elif n <= 2: "👤 Владельцы: +5 — 2 владельца"
elif n == 3: "👤 Владельцы: -5 — 3 владельца"
else: "👤 Владельцы: -10 — 4 владельца"
```

### Verdict block (unified with "why passed")

```python
def _build_verdict(card):
    # Override decision if price_score < 0 → always "watch"
    if price_score < 0:
        decision = "watch"

    lines = ["🎯 Почему в выборке:", ""]

    # Pros: ✅ items
    if drive == "awd": pros.append("✅ Полный привод")
    if trans in ("automatic", "cvt", "dsg"): pros.append(f"✅ {display_transmission(trans).capitalize()}")
    if legal == "Без ограничений": pros.append("✅ Без ограничений")
    if owners <= 3: pros.append(f"✅ {_format_owners(owners)}")
    if region != "unknown": pros.append("✅ Регион подходит")

    # Cons: ⚠ items
    if price_score < 0: cons.append(f"⚠ {price_status or 'цена выше рынка'}")
    if mileage_score < 0: cons.append("⚠ пробег выше нормы")
    if owners >= 4: cons.append(f"⚠ {_format_owners(owners)}")
```

### Score fallback reasons

```python
if score_field == "engine_score":
    cat_map = {"best": "лучший мотор модели", "acceptable": "допустимый", "avoid": "проблемный мотор"}
    return cat_map.get(card.get("engine_category", ""), "нейтрально")
if score_field == "transmission_score":
    cat_map = {"best": "рекомендованная", "avoid": "не рекомендуется"}
    return cat_map.get(card.get("transmission_category", ""), "нейтрально")
```

### Files

- `telegram_card_formatter.py` — full V2 structure
- `telegram_sender.py` — 4-button layout, desc handler
- `telegram_feedback_bot.py` — desc:{card_id} handler
- `card_data_loader.py` — mobile_detail_raw_text, raw_text fields
- `region_parser.py` — city+oblast extraction
- `legal_parser.py` — legal restriction detection
- `feedback_store.py` — v2 dedup with stable_car_key, price tracking
