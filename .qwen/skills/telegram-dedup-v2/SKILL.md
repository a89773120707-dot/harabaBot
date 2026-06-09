---
name: telegram-dedup-v2
description: Persistent dedup with stable_car_key and price tracking — same_price skips, price_drop sends with 🔻 prefix, price_increased skips
source: auto-skill
extracted_at: '2026-06-09T10:18:00.000Z'
---

## Problem

Old dedup (v1) used `url TEXT PRIMARY KEY` in `sent_ads`. Issues:
- Clearing dedup before each run caused re-sends
- Could not detect price changes
- URL-based dedup broke if URL format changed
- No tracking of send history

## Solution: Dedup v2

### stable_car_key

Built from card data with 3-tier priority:

```python
def _build_stable_key(card) -> str:
    # 1. card_id (best)
    if card.get("card_id"):
        return "id:" + card["card_id"]

    # 2. haraba_id from URL (fallback)
    haraba_id = _extract_haraba_id(card.get("url", ""))
    if haraba_id:
        return "haraba:" + haraba_id

    # 3. Content hash (last resort)
    return "fallback:{title}_{year}_{price}_{mileage}_{region}"
```

### sent_ads v2 schema

```sql
CREATE TABLE sent_ads (
    stable_car_key TEXT PRIMARY KEY,
    card_id TEXT,
    url TEXT,
    mobile_url TEXT,
    haraba_id TEXT,
    title TEXT,
    model_id TEXT,
    year INTEGER,
    price INTEGER,
    mileage INTEGER,
    region TEXT,
    first_sent_at TEXT,
    last_seen_at TEXT,
    last_sent_at TEXT,
    send_count INTEGER
);
```

### Dedup states

```python
def check_dedup(card) -> str:
    """Returns: new | same_price | price_drop | price_increased"""
```

| State | Condition | Action |
|-------|-----------|--------|
| `new` | No record in sent_ads | Send, mark_sent(status="new") |
| `same_price` | Record exists, price unchanged | Skip |
| `price_drop` | Record exists, price decreased | Send with "🔻 Цена снизилась" prefix, mark_sent(status="price_drop") |
| `price_increased` | Record exists, price increased | Skip, update_last_seen() |

### Integration in telegram_sender.py

```python
from feedback_store import check_dedup, mark_sent, update_last_seen

# In run_send():
for card in candidates:
    dedup_status = check_dedup(card)

    if dedup_status == "same_price":
        skipped += 1
        continue
    elif dedup_status == "price_increased":
        update_last_seen(card)
        skipped += 1
        continue

    price_drop = dedup_status == "price_drop"
    success = send_car_card_sync(..., price_drop=price_drop)

    if success:
        status = "price_drop" if price_drop else "new"
        mark_sent(card, status=status)
        sent += 1
```

### Price drop prefix

When sending a price-drop update:

```python
async def send_car_card_async(bot, chat_id, card, config, price_drop=False):
    text = prepare_card_text(card, config)
    if price_drop:
        text = "🔻 Цена снизилась!\n\n" + text
    ...
```

### Database persistence

- **NEVER** delete sent_ads automatically
- **NEVER** clear sent_ads at script start
- Reset only via explicit command: `python dedup_store.py --reset` or `feedback_store.reset_sent_ads()`
- Migrations v1→v2 are automatic: old `url`-based records are converted to `stable_car_key` on first access

### Verification

```python
from feedback_store import check_dedup, get_sent_stats

# Check individual card
status = check_dedup(card)  # "new" | "same_price" | "price_drop" | "price_increased"

# Check overall stats
stats = get_sent_stats()
# {'total': 18, 'by_model': {'nissan_xtrail': 3, 'volkswagen_tiguan': 2, ...}}
```

### Migration from v1

Automatic on import of `feedback_store.py`:

1. Detect old schema (no `stable_car_key` column)
2. Rename old table to `sent_ads_v1_old`
3. Create new v2 table
4. Copy data: `stable_car_key = COALESCE(card_id, url)`
5. Drop old table
