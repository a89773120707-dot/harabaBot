---
name: auto-ru-sqlite-integration
description: Auto.ru card storage in SQLite — migrations, dedup, full card mapping
source: auto-skill
extracted_at: '2026-06-11T21:30:00.000Z'
---

# Auto.ru SQLite Integration

## Key Principles

1. **Auto.ru is a separate source**: `source = "auto_ru"`, `external_id = Auto.ru ad ID`
2. **Dedup by source + external_id**: Unique index `idx_sent_ads_source_external_id`
3. **Do NOT break existing Haraba data**: Only ADD columns, never DROP
4. **Two-run safety**: First run → INSERT, second run → UPDATE (no duplicates)

## Database Schema

### New Columns Added to `sent_ads` (21 columns)

| Column | Type | Purpose |
|--------|------|---------|
| source | TEXT | "auto_ru" (defaults to "haraba") |
| external_id | TEXT | Auto.ru ad ID (e.g., "1132964187-34034386") |
| brand | TEXT | Car brand |
| model | TEXT | Car model |
| engine | TEXT | Engine description |
| transmission | TEXT | Transmission type |
| drive | TEXT | Drive type |
| owners | INTEGER | Number of owners |
| auto_ru_price_low | INTEGER | Lower bound of Auto.ru valuation |
| auto_ru_price_high | INTEGER | Upper bound of Auto.ru valuation |
| auto_ru_estimate_mid | INTEGER | Calculated midpoint (low+high)/2 |
| auto_ru_status | TEXT | below_market/fair_price/above_market |
| auto_ru_status_text | TEXT | Original text (e.g., "Выше оценки на 27%") |
| auto_ru_delta_percent | REAL | Delta percentage |
| auto_ru_valuation_url | TEXT | URL to Auto.ru evaluation page |
| final_verdict | TEXT | excellent_deal/good_deal/fair_price/etc |
| final_recommendation | TEXT | "Брать немедленно" / "Скипнуть" |
| final_score | INTEGER | Priority 1-5 |
| final_reasons_json | TEXT | JSON array of reason strings |
| raw_json | TEXT | Full card + decision as JSON |
| sent_at | TEXT | Telegram send timestamp |

### Unique Index

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_sent_ads_source_external_id
ON sent_ads(source, external_id)
```

## Migration

### File: `app/database/migrations.py`

- `ensure_auto_ru_columns(conn)` — adds missing columns (idempotent)
- `ensure_auto_ru_unique_index(conn)` — creates unique index (safe if exists)

### Important: Existing Haraba columns NOT changed

| Original column | Unchanged |
|-----------------|-----------|
| stable_car_key | ✅ |
| chat_id | ✅ |
| card_id | ✅ |
| url | ✅ |
| title | ✅ |
| year | ✅ |
| price | ✅ |
| mileage | ✅ |
| region | ✅ |
| first_sent_at | ✅ |
| last_seen_at | ✅ |

## Repository Functions

### File: `app/database/auto_ru_repo.py`

| Function | Purpose |
|----------|---------|
| `map_auto_ru_card_to_db(card, decision)` | Flatten card + decision to DB dict |
| `auto_ru_ad_exists(conn, external_id)` | Check if card exists (source + external_id) |
| `get_auto_ru_ad(conn, external_id)` | Get card by external_id |
| `save_auto_ru_card(conn, card, decision)` | INSERT or UPDATE |

### Save Logic

```
1. If no external_id → error
2. Check if source + external_id exists
3. If EXISTS → UPDATE last_seen_at, price, valuation, verdict
4. If NEW → INSERT with first_sent_at = now
```

### Return Format

```python
{
    "status": "inserted" | "updated" | "error",
    "external_id": "1132964187-34034386",
    "stable_car_key": "auto_ru:1132964187-34034386",
    "reason": None,
}
```

## Raw JSON

The `raw_json` column stores the full card + decision:

```json
{
  "card": {
    "auto_ru_valuation": {...},
    "external_id": "...",
    "seller_price": 1800000,
    ...
  },
  "decision": {
    "final_verdict": "strong_overpriced",
    "reasons": [...],
    ...
  }
}
```

## Testing

### File: `test_auto_ru_sqlite_save.py`

```bash
# First run
python test_auto_ru_sqlite_save.py --limit 3 --delay 25
# Expected: Inserted: 2, Updated: 0

# Second run (same URLs)
python test_auto_ru_sqlite_save.py --limit 3 --delay 25
# Expected: Inserted: 0, Updated: 2 (no duplicates!)
```

### Verification

```python
import sqlite3
conn = sqlite3.connect("results/feedback.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("""
    SELECT source, external_id, brand, model, price,
           auto_ru_price_low, auto_ru_price_high, auto_ru_estimate_mid,
           auto_ru_status, final_verdict, final_recommendation
    FROM sent_ads WHERE source='auto_ru'
""")
for row in c.fetchall():
    print(dict(row))
```

## Files Created

| File | Purpose |
|------|---------|
| `app/database/__init__.py` | Package init |
| `app/database/migrations.py` | Column migrations + unique index |
| `app/database/auto_ru_repo.py` | Repository functions |
| `test_auto_ru_sqlite_save.py` | Integration test |

## What NOT to Touch

- ❌ Telegram sender
- ❌ Daily pipeline
- ❌ Haraba scraper
- ❌ Existing feedback table structure
