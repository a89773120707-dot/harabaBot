---
name: telegram-card-v2-with-photo
description: Telegram Card V2 final format with photo at top, 📷 Ещё фото button, send_photo via bytes download
source: auto-skill
extracted_at: '2026-06-09T15:00:00.000Z'
---

## Telegram Card V3 — Final approved format with Verdict

**Approved 2026-06-09** by user after iterative testing. Card V3 merges Verdict + Why in selection to avoid duplication.

### Card structure (V3)

```
[PHOTO — send_photo via bytes]

🟡 Hyundai Santa Fe (2014)

💰 2 000 000 ₽

📊 Рынок:
🟢 Отличная: 1 800 000–2 150 000 ₽
🟡 Хорошая: 2 150 000–2 400 000 ₽
🟠 Дорого (если топ): 2 400 000–2 600 000 ₽

📍 Ростов-на-Дону
🛣 68 000 км

⚙️ 2.4 бензин (175 л.с.)
🔄 Автомат
🚙 полный ✅

👤 2 владельца
⚖️ без ограничений ✅

🎯 Вердикт: 🟢 Хороший вариант

Почему в выборке:

✅ Полный привод
✅ Автомат
✅ Без ограничений
✅ 2 владельца
✅ Регион подходит

🧮 Оценка: 75/100
💰 Цена: +5 — fair
🛣 Пробег: +20 — отличный
⚙️ Двигатель: 0 — допустимый
🔄 Коробка: +10 — рекомендованная (best)
🚙 Привод: +15 — полный

🔗 https://m.haraba.ru/search/car/173324131

[🟢 Купить]  [🟡 Посмотреть]
[🔴 Скипнуть]  [📖 Описание]  [📷 Ещё фото]
```

### V3 changes from V2

1. **Verdict merged with Why in selection** — one block instead of two:
   ```
   🎯 Вердикт: {emoji} {label}
   
   Почему в выборке:
   
   ✅ Плюсы...
   ⚠ Минусы... (if price_score < 0 or mileage_score < 0)
   ```

2. **Price explanation shows delta** — in price_scorer_v2.py:
   ```python
   # Expensive range
   delta = card_price - good_hi
   return {"score": -15, "explanation": f"выше хорошей цены на {delta:,} ₽ — {detail}"}
   
   # Above all ranges
   delta = card_price - exp_hi
   return {"score": -30, "explanation": f"выше верхней границы на {delta:,} ₽"}
   ```

3. **Score breakdown always has reason** — no empty lines:
   ```
   💰 Цена: +5 — fair          (not "0 — нейтрально")
   🛣 Пробег: +20 — отличный    (not "+20 (excellent)")
   ```

4. **Engine format**: `{volume} {fuel} ({power} л.с.)` — e.g. `2.0 бензин (144 л.с.)`
   - No CVT/AT in engine line (that belongs to transmission)
   - No raw string like `2.0 CVT (144 л.с.) 4WD (Бензин), 2 л`

5. **Owners format**: `1 владелец`, `2 владельца`, `3 владельца`, `4+ владельцев`

### Photo sending

**Download photo as bytes** (avito.st URLs fail with send_photo URL parameter):

```python
import requests
from io import BytesIO

photo_url = card.get("photo_url", "") or card.get("photos", {}).get("main_photo_url", "")

if photo_url:
    try:
        resp = requests.get(photo_url, timeout=10, stream=True)
        resp.raise_for_status()
        photo_bytes = BytesIO(resp.content)
    except Exception as e:
        log.warning(f"Photo download failed: {e}")
        photo_bytes = None

if photo_bytes:
    caption = text if len(text) <= 1024 else text[:1020] + "..."
    await bot.send_photo(chat_id=chat_id, photo=photo_bytes, caption=caption, reply_markup=keyboard)
    if len(text) > 1024:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
else:
    # Fallback: text only
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
```

### Photo parsing from mobile detail

**Wait until "load"** (not "domcontentloaded"):

```python
page.goto(mobile_url, wait_until="load", timeout=30000)
page.wait_for_timeout(5000)  # JS render
```

**Hero image selector:**
```python
hero = page.locator("[class*='hero'], [class*='MainPhoto'], [class*='mainPhoto'], [class*='swiper-slide-active'] img").first
```

**All img elements with filter:**
```python
imgs = page.locator("img")
for i in range(imgs.count()):
    src = imgs.nth(i).get_attribute("src")
    # Filter out: /static/, logo, icon, avatar, sprite, favicon, arrow, chevron
    if any(skip in src.lower() for skip in [...]): continue
```

**Sources found:**
- `avatars.mds.yandex.net` (autoru)
- `*.img.avito.st` (avito)
- `s*.auto.drom.ru` (drom)

### 📷 Ещё фото button

**Only shown if gallery.length > 1:**

```python
def build_inline_keyboard(card_id, photo_count=0, has_description=True):
    row1 = [🟢 Купить, 🟡 Посмотреть]
    row2 = [🔴 Скипнуть]
    if has_description: row2.append(📖 Описание)
    if photo_count > 1: row2.append(📷 Ещё фото)
```

**Handler in feedback_bot:**
```python
if action == "photos":
    gallery = card.get("photos", {}).get("gallery", [])
    extra_photos = gallery[1:6]  # skip main, max 5
    for photo_url in extra_photos:
        await query.message.reply_photo(photo=photo_url)
```

**Does NOT trigger pending_feedback state** — only 🟢🟡🔴 request comment.

### Hard-stop rules (cards NOT sent)

- engine=unknown → do_not_send
- transmission=unknown → do_not_send  
- drive=unknown → do_not_send
- manual transmission → do_not_send
- not AWD → do_not_send
- confirmed legal restriction → do_not_send
- wrong region confirmed → do_not_send

### Button behavior

| Button | Action | Triggers comment? |
|--------|--------|-------------------|
| 🟢 Купить | buy | ✅ Yes |
| 🟡 Посмотреть | watch | ✅ Yes |
| 🔴 Скипнуть | skip | ✅ Yes |
| 📖 Описание | desc | ❌ No — shows description |
| 📷 Ещё фото | photos | ❌ No — shows gallery |

### Files

- `telegram_card_formatter.py` — V2 format
- `telegram_sender.py` — send_photo with bytes fallback
- `telegram_feedback_bot.py` — 5-button handler
- `mobile_first_page_sampler.py` — wait_until="load" + photo parsing
- `photo_parser.py` — offline photo extraction from raw_text
- `CARD_V2_APPROVED.md` — approved format reference
