---
name: telegram-pipeline-v1
description: End-to-end pipeline: raw cards → enrichment → scoring → region/legal fallback → Telegram card formatting → dedup → send
source: auto-skill
extracted_at: '2026-06-09T07:07:04.375Z'
---

## Telegram v1 architecture

**Goal:** Send all cards that pass basic config checks, collect user reactions (🟢/🟡/🔴 + comment), build rules from real decisions.

**Scoring does NOT filter — it explains.** User decides via buttons.

```
17 active saved searches
    ↓
mobile_first_page_sampler.py → 30 fresh cards with specs
    ↓
telegram_audit.py → audit (region/legal/drive/transmission/score)
    ↓
telegram_candidates_audited.json → send_ready + hold + do_not_send
    ↓
telegram_sender.py → send to Telegram with inline buttons
    ↓
telegram_feedback_bot.py → handle button clicks + collect comments
    ↓
feedback_store.py (SQLite) → save action + comment
    ↓
feedback_export.py → export for rule calibration
```

## Key modules

| Module | Purpose |
|--------|---------|
| `mobile_first_page_sampler.py` | Collect fresh cards from active 17 searches via mobile detail pages (wait_until="load" for photos) |
| `telegram_audit.py` | Pre-send audit: hard-stop on engine/transmission/drive unknown |
| `telegram_sender.py` | Send cards to Telegram with inline buttons (send_photo via bytes fallback) |
| `telegram_card_formatter.py` | Format card V2: photo + price+market at top + verdict + score |
| `telegram_feedback_bot.py` | Handle 5 button types: 🟢🟡🔴📖📷 |
| `feedback_store.py` | SQLite: sent_ads (dedup v2) + feedback (action + comment) |
| `feedback_export.py` | Export feedback stats by model/action for rule calibration |
| `photo_parser.py` | Offline photo extraction from raw_text |
| `pipeline_searches_check.py` | Verify 17 searches active before each run |

## Region parsing

**`region_parser.py`** — replaces inline region_patterns in `mobile_first_page_sampler.py`:

- Tier 1: exact city-to-region mapping (30+ cities including suburbs like Котельники, Чехов, Электросталь, Щербинка, Новомосковск)
- Tier 2: oblast keyword fallback (Тверская область, Ярославская обл., etc.)
- Returns `{value, normalized, allowed, confidence, source}`
- **Unknown does NOT block** — for Telegram v1, unknown region is a warning but cards still send

**Integration:**
- `mobile_first_page_sampler.py` — uses `region_parser.parse_region()` for all cards
- `telegram_audit.py` — fallback when `card.region == "unknown"`, parses from `raw_text` + `mobile_detail_raw_text`
- Both `raw_text` and `mobile_detail_raw_text` must be carried through the audit pipeline

**Result:** 30/30 cards recognized (was 21/30, 9 unknown)

## Send logic

**Send to Telegram if:**
- action in [send_ready, hold_manual_review]
- NOT manual transmission
- NOT not_awd
- NOT wrong_region_confirmed
- NOT legal_restriction_confirmed
- NOT duplicate

**Hold cards get warning:**
```
⚠️ НУЖНА РУЧНАЯ ПРОВЕРКА
• Регион: не распознан — проверить вручную
```

**Do NOT send only hard-stop:**
- manual transmission
- not AWD
- wrong region confirmed
- legal restriction confirmed
- duplicate

## Telegram card format v2

**Key improvements over v1:**
- Price status field (`price_status`) — explicit: «отличная цена» / «хорошая цена» / «fair» / «дорого, но допустимо» / «выше допустимого»
- Checklist reasons are always filled (no empty parentheses)
- Transmission normalized: «Автомат» / «AT» → matching «automatic», «S tronic» → matching «dsg»
- Engine display shortened: «2.0 TSI 4Motion AT, 170 л.с., бензин» instead of raw string
- Risk texts are complete (no truncation): «OK только если топ-комплектация и хорошее состояние»
- Price penalty not duplicated in «Что проверить»
- **Price block: current price on top, config ranges below, status at bottom — all in one visual block** (no need to scan up/down)

```
⚠️ НУЖНА РУЧНАЯ ПРОВЕРКА          ← only for hold cards
• Регион: не распознан — проверить вручную

✅ Mercedes-Benz GLK (2012)         ← model / year
Score: 100/100 — GOOD

📍 Москва | 🛣 151,113 km           ← region / mileage
⚙️ 2.1 TDI, 170 л.с., дизель | 🔄 автомат | 🚙 полный ✅  ← shortened engine
👤 2 вл. | Автотека: есть | Юр.: без ограничений ✅

💰 Цена: 1,700,000 ₽ → хорошая цена  ← current price with status
📊 Цена по конфигу:
🟢 Отличная: 1,450,000–1,600,000 ₽  ← config ranges below
🟡 Хорошая: 1,600,000–1,750,000 ₽
🟠 Дорого (OK если топ): 1,750,000–1,900,000 ₽
🔴 Reject: 1,900,000+ ₽

🧮 Оценка (100/100):                ← no empty () — each item has reason
💰 Цена: +20 — хорошая, в диапазоне 1,600,000–1,750,000
🛣 Пробег: +20 — пробег 151,113 км — отличный
⚙️ Двигатель: 0 — 2.1 TDI — допустимый
🔄 Коробка: +10 — рекомендованная (best)
🚙 Привод: +15 — полный

✅ Сильные стороны:
• Цена в good диапазоне
• Пробег отличный (151,113 км)
• Полный привод
• Мало владельцев (2)
• Автотека доступна

⚠️ Что проверить:
• Регион не определён — проверить вручную

🔗 https://m.haraba.ru/search/car/173295809
```

**Card dict fields added in v2:**
```python
card["price_category"] = price_r.get("category", "")   # "excellent" / "good" / "fair" / ...
card["price_status"] = price_r.get("price_status", "")  # "хорошая цена" / "дорого, но допустимо" / ...
```

These are set in `telegram_audit.py` and `run_telegram_pipeline.py` after calling `score_price()`.

**Buttons (inline):**
```
[🟢 Купить] [🟡 Посмотреть]
[🔴 Скипнуть]
```

## Persistent dedup v2

**See skill: `telegram-dedup-v2`**

Key points:
- `stable_car_key` built from card_id → haraba_id from URL → fallback hash
- States: `new` → send, `same_price` → skip, `price_drop` → send with "🔻", `price_increased` → skip
- `feedback_store.py` has `check_dedup()`, `mark_sent()`, `update_last_seen()`, `reset_sent_ads()`
- sent_ads v2 schema tracks: price, send_count, first_sent_at, last_seen_at, last_sent_at
- Migration v1→v2 is automatic on first import
- **NEVER** clear sent_ads automatically — only via explicit command

## Feedback data integrity (critical)

```python
# load_card_data() enriches audited candidates with sample specs:
cards[cid] = {
    ...
    "engine": specs.get("engine", {}).get("value", "unknown"),
    "transmission": specs.get("transmission", {}).get("value", "unknown"),
    "drive": specs.get("drive", {}).get("value", "unknown"),
    "region": specs.get("region", {}).get("value", "unknown"),
    "owners": specs.get("owners", {}).get("value", "unknown"),
}

# telegram_feedback_bot.py saves ALL fields:
feedback_card = {
    "card_id": card.get("card_id"),
    "engine": card.get("engine", "unknown"),
    "transmission": card.get("transmission", "unknown"),
    "drive": card.get("drive", "unknown"),
    "region": card.get("region", "unknown"),
    "owners": card.get("owners", "unknown"),
    ...
}
save_feedback(feedback_card, action, comment)
```

**Without this enrichment**, feedback.db would have `engine=unknown`, `transmission=unknown`, etc. for every reaction — making it impossible to calibrate rules from user decisions.

**Also critical:** `feedback_store.py` INSERT must include `owners` column:
```sql
INSERT INTO feedback (..., engine, transmission, drive, region, owners, score, ...)
```
Missing `owners` from CREATE TABLE or INSERT causes silent data loss.

**Verify with:** `python test_feedback_integrity.py` — checks all 49 integrity points:
- load_card_data has all fields (engine/transmission/drive/region/owners known)
- save_feedback writes all fields to SQLite
- telegram_sender.py enriches candidates from sample
- telegram_sender.py and telegram_feedback_bot.py use same token/chat_id

**feedback.db schema (v2):**
```sql
sent_ads:
  stable_car_key TEXT PRIMARY KEY  -- "id:{card_id}" or "haraba:{id}" or "fallback:{...}"
  card_id TEXT, url TEXT, mobile_url TEXT, haraba_id TEXT
  title TEXT, model_id TEXT
  year INTEGER, price INTEGER, mileage INTEGER, region TEXT
  first_sent_at TEXT, last_seen_at TEXT, last_sent_at TEXT
  send_count INTEGER

feedback:
  id INTEGER PRIMARY KEY AUTOINCREMENT
  card_id, url, model_id, title, price, mileage
  engine, transmission, drive, region, owners
  score, telegram_status, action, comment, created_at
```

## Decision thresholds (v4) — for explanation, not filtering

```
excellent_candidate: score >= 80 AND price in [excellent,good] AND mileage in [excellent,good] AND >=2 strong_bonus AND no warnings
good_candidate: score >= 80
watch: score >= 55
weak: score >= 40
reject: score < 40 OR hard_reject
```

## Commands

```bash
# Dry-run — preview without sending
python telegram_sender.py --dry-run --input results/telegram_candidates_audited.json

# Send all
python telegram_sender.py --send

# Send N cards
python telegram_sender.py --send --limit 3

# Run feedback bot
python telegram_feedback_bot.py

# Export feedback
python feedback_export.py --days 7

# Feedback analytics report
python feedback_report.py --days 7
```

## Configuration

`.env` file:
```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Key rules

1. **Scoring explains, doesn't filter** — score is a checklist, not a gate
2. **Send send_ready only** — hold cards go to manual review, do_not_send cards are rejected
3. **Hard-stop audit: unknown critical fields** — engine=unknown, transmission=unknown, or drive=unknown → `do_not_send` (not just hold). See skill: `audit-hard-stops`
4. **Dedup v2 is mandatory** — uses `check_dedup(card)` from `feedback_store.py`. States: new/same_price/price_drop/price_increased. Never clear sent_ads automatically.
5. **Photos: send_photo with text fallback** — if photo_url available use send_photo, fallback to send_message on error. Never let photo error block pipeline.
6. **Always request comment** — after button click, ask for comment before saving
7. **Never send before audit** — always run telegram_audit.py first
8. **Mobile URLs only** — `m.haraba.ru/search/car/{id}` not desktop URLs
9. **feedback.db NEVER deleted** — accumulates across all runs

### Reply-to-message pattern (critical for UX)

When multiple cards arrive in Telegram simultaneously, the user loses context about which card they're reacting to. **Both the comment request and the confirmation MUST be replies to the card message:**

```python
# button_handler — reply to the card message
await query.message.reply_text(
    f"✍️ {action_label}\n\n"
    f"Напиши комментарий (или «-» если без комментария):",
    reply_to_message_id=query.message.message_id,  # ← REPLY to card
)

# text_handler — confirmation also replies to card
await update.message.reply_text(
    f"✅ Записано!\n\n"
    f"🚗 {title}\n"
    f"📝 Действие: {action}\n"
    f"💬 Комментарий: {comment}",
    reply_to_message_id=card_message_id,  # ← REPLY to card
)
```

**Visual result in Telegram:**
```
📱 [Card: Mercedes-Benz GLK (2012)]
     ↳ ✍️ 🟢 Купить
         Напиши комментарий...
         ↳ ✅ Записано!
             🚗 Mercedes-Benz GLK
             📝 Действие: buy
             💬 Комментарий: Хорошая цена
```

Without `reply_to_message_id`, when 3+ cards arrive at once, the user presses a button on one card but the comment request appears as a standalone message — context is lost.

### Mobile URLs (critical for links)

All card links must use **mobile URLs**: `https://m.haraba.ru/search/car/{card_id}`. Desktop URLs (`haraba.ru/common/click?id=...`) do not open properly on mobile.

In `telegram_card_formatter.py`:
```python
# Prefer mobile_url if available
mobile_url = card.get("mobile_url", "")
if mobile_url:
    parts.append(f"🔗 {mobile_url}")
elif url:
    # Fallback: convert desktop → mobile
    ad_id = url.split("id=")[1].split("&")[0]
    parts.append(f"🔗 https://m.haraba.ru/search/car/{ad_id}")
```

`telegram_sender.py` must pass `mobile_url` to the card formatter:
```python
scored_card = {
    ...
    "mobile_url": card.get("mobile_url", ""),
    ...
}
```

### Database persistence

**feedback.db is NEVER deleted by scripts.** It accumulates reactions across all runs. The only time it should be deleted is manually during initial testing.

- `telegram_sender.py` → only INSERTs into sent_ads, NEVER deletes
- `telegram_feedback_bot.py` → only INSERTs into feedback, NEVER deletes
- Running `del results\feedback.db` between sessions loses ALL accumulated reactions

**Verify persistence:** `python check_feedback.py` shows all accumulated records.
