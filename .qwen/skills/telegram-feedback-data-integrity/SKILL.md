---
name: telegram-feedback-data-integrity
description: Ensure feedback.db stores ALL card fields (engine, transmission, drive, region, owners) plus V2 fields (price_status, score breakdown, photo_url, reviewer_role, telegram_chat_id) — never save "unknown" for fields that exist in the source data.
source: auto-skill
extracted_at: '2026-06-09T15:42:00.000Z'
---

## Problem

When saving Telegram button reactions (buy/watch/skip) to feedback.db, critical fields like `engine`, `transmission`, `drive`, `region`, `owners` were saved as `"unknown"` even though the full data was available in `mobile_first_page_sample.json`.

This makes the feedback database useless for training scoring rules — you'd have 100 reactions but no engine/transmission data.

## Fix

### 1. Enrich card data in telegram_sender.py

Load full specs from `mobile_first_page_sample.json` and merge into audited candidates:

```python
def load_audited_candidates(path: str) -> list:
    # Load audited candidates
    with open(path) as f:
        audited = json.load(f)

    # Load sample for enrichment
    with open(SAMPLE_PATH) as f:
        sample = json.load(f)
    sample_lookup = {c["card_id"]: c for c in sample["cards"]}

    for c in audited["cards"]:
        cid = c["card_id"]
        if cid in sample_lookup:
            s = sample_lookup[cid]
            specs = s["specs"]
            # Enrich ALL fields
            c["engine"] = specs["engine"]["value"]
            c["transmission"] = specs["transmission"]["value"]
            c["drive"] = specs["drive"]["value"]
            c["region"] = specs["region"]["value"]
            c["owners"] = specs["owners"]["value"]
            # Also enrich basic fields that may be missing
            c["mileage"] = c.get("mileage") or s["mileage"]
            c["price"] = c.get("price") or s["price"]
            c["url"] = c.get("url") or s["url"]
            c["mobile_url"] = s["mobile_url"]
```

### 2. Card data loader for feedback bot

Extract `load_card_data()` into a separate module (`card_data_loader.py`) so both `telegram_feedback_bot.py` and tests can use it without depending on `telegram` package:

```python
# card_data_loader.py
def load_card_data():
    """Load full card data from audited + sample."""
    # Load audited
    # Load sample lookup
    # Merge specs into each card
    # Return {card_id: full_card_data}
```

### 3. feedback_store.py schema

Table must include `owners` column:

```sql
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT, url TEXT, model_id TEXT, title TEXT,
    price INTEGER, mileage INTEGER,
    engine TEXT, transmission TEXT, drive TEXT, region TEXT, owners TEXT,
    score INTEGER, telegram_status TEXT,
    action TEXT, comment TEXT, created_at TEXT
)
```

INSERT must include all 16 fields:

```python
c.execute("""
    INSERT INTO feedback (
        card_id, url, model_id, title, price, mileage,
        engine, transmission, drive, region, owners,
        score, telegram_status, action, comment, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (...16 values...))
```

### 4. Pending state in feedback bot

Pass FULL card data through pending state, not just card_id:

```python
pending_feedback[chat_id] = {
    "card_id": card_id,
    "action": action,
    "card_data": {
        "card_id": cid,
        "engine": card["engine"],
        "transmission": card["transmission"],
        "drive": card["drive"],
        "region": card["region"],
        "owners": card["owners"],
        # ... all other fields
    }
}
```

Then save ALL fields when comment arrives:

```python
feedback_card = {
    "engine": card["engine"],
    "transmission": card["transmission"],
    # ... all fields from pending card_data
}
save_feedback(feedback_card, action, comment)
```

## Verification

Run `test_feedback_integrity.py` which checks:
1. `load_card_data()` returns 16 cards with engine/transmission/drive known
2. `save_feedback()` stores engine='2.0 TDI...', transmission='automatic', drive='awd', region='Москва', owners='2' in DB
3. `telegram_sender.py` enrichment passes all fields
4. Both `telegram_sender.py` and `telegram_feedback_bot.py` use same token/chat_id

## Key principle

> Every reaction (buy/watch/skip) must preserve the full context of the car.
> Without engine/transmission/drive/region, you cannot train scoring rules from feedback.