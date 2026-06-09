---
name: feedback-db-migration
description: Migrating feedback_store.py for multi-recipient dedup and schema fixes
source: auto-skill
extracted_at: '2026-06-09T16:20:00.000Z'
---

## Context

When adding multi-recipient support (owner + manager) to the Telegram pipeline,
the `sent_ads` table needed a composite primary key to track dedup per recipient.

## Problem 1: Single PK collision

**Issue:** `sent_ads` had `stable_car_key TEXT PRIMARY KEY`. When the same car
was sent to both owner and manager, the second `INSERT OR IGNORE` silently failed
because the key already existed. Only one recipient's record was stored.

**Fix:** Migrate to composite PK `(stable_car_key, chat_id)`:

```python
# Detect old schema
c.execute("PRAGMA table_info(sent_ads)")
cols_info = c.fetchall()
pk_cols = [row[1] for row in cols_info if row[5] > 0]

if pk_cols == ['stable_car_key']:
    c.execute("ALTER TABLE sent_ads RENAME TO sent_ads_v3_old")
    c.execute("""
        CREATE TABLE sent_ads (
            stable_car_key TEXT, chat_id TEXT, ...,
            PRIMARY KEY (stable_car_key, chat_id)
        )
    """)
    c.execute("""
        INSERT INTO sent_ads (...)
        SELECT ..., COALESCE(chat_id, 'legacy'), ...
        FROM sent_ads_v3_old
    """)
```

## Problem 2: 30 values for 31 columns

**Issue:** Added new columns (`telegram_chat_id`, `reviewer_role`, etc.) to the
`feedback` table via ALTER TABLE migration, but forgot to add the 31st `?`
placeholder in the INSERT VALUES clause. This caused silent save failures
for all reactions.

**Fix:** Count placeholders carefully. The INSERT must match the column count exactly:

```python
c.execute("""
    INSERT INTO feedback (col1, col2, ..., col31)
    VALUES (?, ?, ..., ?)  -- must be 31 question marks
""", (val1, val2, ..., val31))
```

## Problem 3: log vs _log name error

**Issue:** `feedback_store.py` used `log.info()` but `log` was not imported
(or was imported differently). This caused a `NameError` at module load time.

**Fix:** Use `print()` for internal logging in `feedback_store.py`, or ensure
consistent import of the logger.

## Verification

After any schema migration:

```bash
# Test import doesn't crash
python -c "from feedback_store import reset_sent_ads; reset_sent_ads()"

# Verify composite PK works
python -c "
import sqlite3
conn = sqlite3.connect('results/feedback.db')
c = conn.cursor()
c.execute('PRAGMA table_info(sent_ads)')
cols = [r[1] for r in c.fetchall()]
assert 'chat_id' in cols, 'chat_id column missing'
conn.close()
"
```

## Key Rule

When modifying `feedback_store.py`:
1. Always test import after schema changes (module-level `init_db()` runs on import).
2. Count INSERT columns and placeholders — they must match exactly.
3. Use `print()` or a defined logger, never assume `log` is available.
