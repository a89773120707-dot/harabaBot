---
name: telegram-feedback-v2-schema
description: Feedback database schema v2 with 30+ fields for multi-recipient reaction tracking with full card context
source: auto-skill
extracted_at: '2026-06-09T16:50:00.000Z'
---

# Telegram Feedback V2 Schema

## Overview

Extended feedback table to support multi-recipient system with full card context preservation. Each reaction stores complete snapshot of the card state at time of reaction.

## Schema

```sql
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Card identity
    card_id TEXT,
    url TEXT,
    model_id TEXT,
    title TEXT,
    
    -- Car specs
    price INTEGER,
    mileage INTEGER,
    engine TEXT,
    transmission TEXT,
    drive TEXT,
    region TEXT,
    owners TEXT,
    legal_restrictions TEXT,
    autoteka_status TEXT,
    
    -- Scoring
    score INTEGER,
    telegram_status TEXT,
    price_status TEXT,
    price_score INTEGER,
    mileage_score INTEGER,
    engine_score INTEGER,
    transmission_score INTEGER,
    equipment_score INTEGER,
    
    -- Media
    photo_url TEXT,
    photo_count INTEGER,
    full_location TEXT,
    
    -- Reaction
    action TEXT,
    comment TEXT,
    
    -- Reviewer identity (NEW in v2)
    telegram_chat_id TEXT,
    telegram_user_id TEXT,
    telegram_username TEXT,
    reviewer_role TEXT,
    
    -- Timestamp
    created_at TEXT
)
```

## Migration

When adding new columns to existing database:

```python
new_cols = [
    ("telegram_chat_id", "TEXT"),
    ("telegram_user_id", "TEXT"),
    ("telegram_username", "TEXT"),
    ("reviewer_role", "TEXT"),
]

c.execute("PRAGMA table_info(feedback)")
existing = {row[1] for row in c.fetchall()}

for col_name, col_type in new_cols:
    if col_name not in existing:
        c.execute(f"ALTER TABLE feedback ADD COLUMN {col_name} {col_type}")
```

## Saving Feedback

```python
def save_feedback(card, action, comment=""):
    c.execute("""
        INSERT INTO feedback (
            card_id, url, model_id, title, price, mileage,
            engine, transmission, drive, region, owners,
            legal_restrictions, autoteka_status,
            score, telegram_status, action, comment,
            price_status, price_score, mileage_score, engine_score,
            transmission_score, equipment_score,
            photo_url, photo_count, full_location,
            telegram_chat_id, telegram_user_id, telegram_username, reviewer_role,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        card.get("card_id", ""),
        # ... 29 more values ...
        datetime.now().isoformat(),
    ))
    conn.commit()
```

**Critical:** Must have exactly 31 `?` placeholders for 31 columns.

## Bot Integration

In `telegram_feedback_bot.py`, collect reviewer info from update:

```python
user = update.message.from_user

feedback_card = {
    # ... card fields ...
    "telegram_chat_id": str(chat_id),
    "telegram_user_id": str(user.id),
    "telegram_username": user.username or "",
    "reviewer_role": my_role,  # from telegram_recipients table
}

save_feedback(feedback_card, action, comment)
```

## Verification

```bash
# Check for NULL in critical fields
python -c "
import sqlite3
conn = sqlite3.connect('results/feedback.db')
c = conn.cursor()
c.execute('''
    SELECT COUNT(*) FROM feedback
    WHERE reviewer_role IS NULL OR telegram_chat_id IS NULL
''')
incomplete = c.fetchone()[0]
print(f'Incomplete records: {incomplete}')
assert incomplete == 0, 'Some records missing role/chat_id'
conn.close()
"
```

## Analytics Queries

**Reactions by role:**
```sql
SELECT reviewer_role, action, COUNT(*)
FROM feedback
GROUP BY reviewer_role, action
```

**Owner vs Manager agreement:**
```sql
SELECT f1.card_id, f1.action as owner_action, f2.action as manager_action
FROM feedback f1
JOIN feedback f2 ON f1.card_id = f2.card_id
WHERE f1.reviewer_role = 'owner' AND f2.reviewer_role = 'manager'
```

**Top comment keywords:**
```sql
SELECT comment, COUNT(*)
FROM feedback
WHERE comment IS NOT NULL AND comment != ''
GROUP BY LOWER(comment)
ORDER BY COUNT(*) DESC
```

## Key Rules

1. **NEVER** insert without `reviewer_role` and `telegram_chat_id`
2. **ALWAYS** collect full card context (price, mileage, engine, etc.)
3. **Migration** must add columns safely (check if exists first)
4. **Count** placeholders must match columns exactly (31 columns = 31 `?`)
5. **NULL** values are acceptable for optional fields (photo_url, full_location) but NOT for identity fields
