---
name: telegram-dedup-composite-key-fix
description: Fix for multi-recipient dedup using composite primary key (stable_car_key + chat_id) in sent_ads table
source: auto-skill
extracted_at: '2026-06-09T16:50:00.000Z'
---

# Telegram Dedup: Composite Key Fix for Multi-Recipient

## Problem

When sending to multiple recipients (owner + manager), the `sent_ads` table used `stable_car_key` as PRIMARY KEY. This caused conflicts:
1. Car sent to Owner → record created with key `id:173324131`
2. Car sent to Manager → INSERT fails (duplicate key) → Manager never gets dedup record
3. Next run → Manager receives same car again (no dedup record exists for them)

## Solution

Change PRIMARY KEY from single column to composite: `(stable_car_key, chat_id)`.

This allows tracking sent status independently per recipient.

## Implementation

### Migration (feedback_store.py)

```python
# In init_db(), detect old schema and migrate
c.execute("PRAGMA table_info(sent_ads)")
cols_info = c.fetchall()
pk_cols = [row[1] for row in cols_info if row[5] > 0]

if pk_cols == ['stable_car_key']:
    # Rename old table
    c.execute("ALTER TABLE sent_ads RENAME TO sent_ads_v3_old")
    
    # Create new table with composite PK
    c.execute("""
        CREATE TABLE sent_ads (
            stable_car_key TEXT,
            chat_id TEXT,
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
            send_count INTEGER,
            PRIMARY KEY (stable_car_key, chat_id)
        )
    """)
    
    # Copy data with default chat_id
    c.execute("""
        INSERT INTO sent_ads (...)
        SELECT ..., COALESCE(chat_id, 'legacy')
        FROM sent_ads_v3_old
    """)
    
    c.execute("DROP TABLE IF EXISTS sent_ads_v3_old")
    conn.commit()
```

### Check dedup per recipient

```python
def check_dedup_with_chat_id(card, chat_id):
    stable_key = _build_stable_key(card)
    c.execute("""
        SELECT price FROM sent_ads
        WHERE stable_car_key = ? AND chat_id = ?
    """, (stable_key, str(chat_id)))
    
    row = c.fetchone()
    if not row:
        return "new"
    
    old_price = row[0]
    card_price = card.get("price", 0)
    
    if old_price == card_price:
        return "same_price"
    elif card_price < old_price:
        return "price_drop"
    else:
        return "price_increased"
```

### Mark sent per recipient

```python
def mark_sent_with_chat_id(card, chat_id, status="new"):
    stable_key = _build_stable_key(card)
    # ... prepare data ...
    
    if status == "new":
        c.execute("""
            INSERT OR IGNORE INTO sent_ads (
                stable_car_key, chat_id, ..., send_count
            ) VALUES (?, ?, ..., 1)
        """, (stable_key, str(chat_id), ...))
    elif status == "price_drop":
        c.execute("""
            UPDATE sent_ads
            SET price = ?, last_sent_at = ?, send_count = send_count + 1
            WHERE stable_car_key = ? AND chat_id = ?
        """, (new_price, now, stable_key, str(chat_id)))
    
    conn.commit()
```

## Sender Loop

```python
for card in candidates:
    for recipient in recipients:
        r_chat_id = recipient["chat_id"]
        dedup_status = check_dedup_with_chat_id(card, r_chat_id)
        
        if dedup_status == "same_price":
            log(f"SKIP {recipient['role']}:same_price")
            continue
        
        # Send to this recipient
        success = send_car_card_sync(bot_token, r_chat_id, card, config)
        if success:
            mark_sent_with_chat_id(card, r_chat_id, status="new")
```

## Verification

```bash
# After sending 1 card to 2 recipients
python -c "
import sqlite3
conn = sqlite3.connect('results/feedback.db')
c = conn.cursor()
c.execute('SELECT stable_car_key, chat_id, send_count FROM sent_ads')
for r in c.fetchall():
    print(f'{r[0]} -> chat={r[1]}, count={r[2]}')
conn.close()
"
```

Expected output: 2 rows with same `stable_car_key` but different `chat_id`.

## Key Rules

1. **NEVER** call `reset_sent_ads()` in production pipeline
2. **ALWAYS** include `chat_id` in dedup checks
3. **PRIMARY KEY** must be `(stable_car_key, chat_id)` for multi-recipient support
4. **Migration** must preserve existing data when changing schema
