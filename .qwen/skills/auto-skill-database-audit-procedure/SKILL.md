---
name: database-audit-procedure
description: Systematic read-only audit of SQLite databases — schema discovery, data analysis, cross-reference verification without modifying any data
source: auto-skill
extracted_at: '2026-06-13T16:21:35.119Z'
---

# Database Audit Procedure (Read-Only)

## When to use

When you need to understand the actual state of project SQLite databases before making changes — especially for dedup, migrations, data integrity checks, or schema evolution.

## Core rules

- **READ ONLY** — no ALTER TABLE, no INSERT, no UPDATE, no DELETE, no migrations
- **No schema changes** — only PRAGMA, SELECT, schema inspection
- **Document everything** — every claim must be backed by actual query results
- **No assumptions** — if a column is expected but missing, write "NOT FOUND"

## Step-by-step procedure

### 1. Discover all databases

```bash
find . -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3"
```

For each database, record: path, size, modification date.

### 2. List tables and row counts

For each database:
```python
import sqlite3, os
conn = sqlite3.connect(db_path)
c = conn.cursor()
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
for t in tables:
    cnt = c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
    print(f"  {t}: {cnt} rows")
```

### 3. Full schema extraction

```python
for row in c.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"):
    print(row[0])
```

Capture: CREATE TABLE, CREATE INDEX, UNIQUE constraints, FOREIGN KEYs.

### 4. Deep analysis per table

For each important table:
```python
# Column list
cols = [r[1] for r in c.execute("PRAGMA table_info(table_name)").fetchall()]

# Check for specific critical columns
critical = ['card_id', 'chat_id', 'config_name', 'sent_at', 'first_sent_at']
for col in critical:
    print(f"  {col}: {'EXISTS' if col in cols else 'MISSING'}")

# Distribution analysis
c.execute("SELECT col, COUNT(*) FROM table GROUP BY col ORDER BY COUNT(*) DESC")
```

### 5. Dedup-specific analysis (for sent_ads tables)

```python
# Can same car go to multiple managers?
c.execute("""
    SELECT stable_car_key, COUNT(DISTINCT chat_id) as mgr_count,
           GROUP_CONCAT(DISTINCT chat_id) as chat_ids
    FROM sent_ads GROUP BY stable_car_key HAVING mgr_count > 1 LIMIT 10
""")

# Check for duplicate PK violations (should be 0)
c.execute("""
    SELECT COUNT(*) FROM (
        SELECT stable_car_key, chat_id, COUNT(*) as cnt
        FROM sent_ads GROUP BY stable_car_key, chat_id HAVING cnt > 1
    )
""")

# NULL analysis for critical columns
c.execute("SELECT COUNT(*) FROM sent_ads WHERE config_name IS NULL OR config_name = ''")
```

### 6. Cross-reference analysis

- Can reactions be linked to sent_ads? (check shared `card_id`)
- Can reactions be linked to specific managers? (check `telegram_chat_id`, `telegram_user_id`)
- Are there FK constraints or just loose references?

### 7. Code-to-DB verification

For each database, grep the codebase to find which files actually connect to it:
```bash
grep -rn "DB_PATH\|feedback\.db\|sent_ads\.db\|dedup_store" --include="*.py"
```

Distinguish between:
- **Active** — used by production code (pipeline, bots)
- **Legacy** — referenced only by old/debug scripts
- **Unused** — no code references at all

### 8. Document findings

Create `docs/DATABASE.md` with:
1. All discovered databases (path, size, date, tables, row counts)
2. Full schema of primary database
3. Per-table deep analysis (columns, indexes, constraints, data distribution)
4. Answers to specific business questions (dedup logic, config_name status, etc.)
5. Legacy/unused database identification
6. Risks identified (NULL columns, missing columns, sync issues)
7. Items requiring verification (especially VPS vs local data drift)

## Key patterns from Haraba Mini audit

### Dedup verification
- PK `(stable_car_key, chat_id)` = per-manager dedup ✅
- 0 duplicate PK pairs = working correctly ✅
- 5 cars × 2 managers = 10 rows = multi-recipient works ✅

### config_name gap discovery
- Column EXISTS in `sent_ads` schema → ✅
- But ALL 10 rows have `config_name = NULL` → ❌
- Column DOES NOT EXIST in `feedback` table → ❌
- Root cause: code modified but not committed/deployed

### Database lifecycle
- `feedback.db` (108 KB, active) → PRODUCTION
- `sent_ads.db` (20 KB, 0 rows, last modified 5 days ago) → LEGACY
- `dedup_store.db` (0 bytes, no tables) → BROKEN/ABANDONED
- `feedback_backup_*.db` → BACKUPS (keep)

## Common pitfalls

1. **Assuming a column exists because memory says so** — always verify with PRAGMA table_info
2. **Confusing local DB with VPS DB** — row counts may differ drastically (1 row locally vs 37 on VPS)
3. **Not checking NULL distribution** — a column can exist but have 100% NULL values
4. **Missing FK gaps** — SQLite often has no actual FK constraints, just convention
5. **Not checking which databases code actually uses** — grep for DB_PATH references
