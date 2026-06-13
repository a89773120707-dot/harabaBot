---
name: block-zero-audit-procedure
description: Systematic read-only BLOCK 0 audit for Haraba Mini — 5 blocks (Users, Feedback, Pipeline, Dedup, Config Name) with PASS/FAIL verdict per block
source: auto-skill
extracted_at: '2026-06-13T17:00:00.000Z'
---

# BLOCK 0 — Audit Procedure (Haraba Mini)

## When to use

Before starting any new feature implementation (especially BLOCK 1+), run BLOCK 0 audit to verify the current system is fully functional and no data is being lost.

## Core rules

- **READ ONLY** — no code changes, no DB changes, no git operations
- **Every claim must have evidence** — file line, SQL result, grep match, or log
- **No assumptions** — write "NOT FOUND" or "NEEDS VPS CHECK" instead of guessing
- **Stop on FAIL** — if any block fails, do not proceed to implementation without user approval

## Block A — Telegram Users

Check:
1. `telegram_users` is the single source of truth
2. `telegram_recipients` is NOT used for sending (only legacy table creation)
3. `get_enabled_recipients()` returns ONLY `status = 'active'`
4. `paused` users do not receive cards
5. `pending` users do not receive cards
6. `active` users receive cards

Commands:
```python
# Check schema
conn.execute("SELECT sql FROM sqlite_master WHERE name='telegram_users'").fetchone()
conn.execute("SELECT sql FROM sqlite_master WHERE name='telegram_recipients'").fetchone()

# Check data
conn.execute("SELECT telegram_id, username, role, status FROM telegram_users").fetchall()

# Verify get_enabled_recipients logic
conn.execute("SELECT telegram_id FROM telegram_users WHERE status = 'active'").fetchall()
```

Code check:
```bash
grep -rn "get_enabled_recipients\|get_all_recipients\|telegram_recipients" --include="*.py"
```
Verify that `telegram_sender.py` uses `get_enabled_recipients()`, NOT `telegram_recipients`.

Pass criterion: 100% match between active users in DB and actual send recipients.

## Block B — Telegram Feedback

Check:
1. `feedback` table receives INSERTs
2. `reaction_details` table receives INSERTs
3. `reason_code` is saved correctly
4. `needs_comment()` import works (no ImportError)
5. No 409 Conflict in logs

Commands:
```python
# Feedback schema
conn.execute("SELECT sql FROM sqlite_master WHERE name='feedback'").fetchone()

# Reaction details schema
conn.execute("SELECT sql FROM sqlite_master WHERE name='reaction_details'").fetchone()

# Data counts
conn.execute("SELECT COUNT(*) FROM feedback").fetchone()
conn.execute("SELECT COUNT(*) FROM reaction_details").fetchone()

# Sample recent data
conn.execute("SELECT id, card_id, action, telegram_chat_id FROM feedback ORDER BY created_at DESC LIMIT 10").fetchall()
```

Code check:
```bash
grep -n "needs_comment\|save_reaction_detail\|ris_reason_store" telegram_feedback_bot.py
grep -n "from ris_reason_store import" telegram_feedback_bot.py
```

Pass criterion: Any reaction completes the full path: card → reaction → reason → comment → DB.

## Block C — Pipeline

Check:
1. cron runs every 10 minutes (VPS only)
2. flock prevents parallel runs (VPS only)
3. `run_daily_pipeline.py` contains full cycle: verify → collect → enrich → audit → dedup → send → report
4. sender uses correct recipient source

Code check:
```bash
grep -n "step_\|collect\|enrich\|audit\|send" run_daily_pipeline.py
grep -n "get_enabled_recipients" telegram_sender.py
```

Pass criterion: Pipeline runs 24+ hours without manual intervention (VPS check required).

## Block D — Dedup

Check:
1. `sent_ads` table fills up
2. Duplicates are actually filtered
3. New cards pass through
4. Old cards are skipped

Commands:
```python
# sent_ads schema
conn.execute("SELECT sql FROM sqlite_master WHERE name='sent_ads'").fetchone()

# Row count and sample
conn.execute("SELECT COUNT(*) FROM sent_ads").fetchone()
conn.execute("SELECT stable_car_key, chat_id FROM sent_ads ORDER BY last_sent_at DESC LIMIT 10").fetchall()

# Unique chat_ids
conn.execute("SELECT DISTINCT chat_id FROM sent_ads").fetchall()

# Check for duplicate PKs (should be 0)
conn.execute("""
    SELECT COUNT(*) FROM (
        SELECT stable_car_key, chat_id, COUNT(*) as cnt
        FROM sent_ads GROUP BY stable_car_key, chat_id HAVING cnt > 1
    )
""").fetchone()
```

Code check:
```bash
grep -n "check_dedup_with_chat_id\|mark_sent_with_chat_id\|_build_stable_key" feedback_store.py
grep -n "dedup_status\|skipped_duplicate" telegram_sender.py
```

Pass criterion: Dedup works predictably — same car+chat_id = skip, different chat_id = send.

## Block E — Config Name Audit

Check:
1. `config_name` column EXISTS in `sent_ads`
2. `config_name` column EXISTS in `feedback`
3. `config_name` column EXISTS in `reaction_details`
4. `config_name` is NOT NULL in actual data
5. Full path: card → sent_ads → feedback → reaction_details

Commands:
```python
# Check column existence
conn.execute("SELECT COUNT(*) FROM pragma_table_info('sent_ads') WHERE name='config_name'").fetchone()
conn.execute("SELECT COUNT(*) FROM pragma_table_info('feedback') WHERE name='config_name'").fetchone()
conn.execute("SELECT COUNT(*) FROM pragma_table_info('reaction_details') WHERE name='config_name'").fetchone()

# Check NULL distribution
conn.execute("SELECT COUNT(*) FROM sent_ads WHERE config_name IS NULL OR config_name = ''").fetchone()
conn.execute("SELECT COUNT(*) FROM sent_ads WHERE config_name IS NOT NULL AND config_name != ''").fetchone()

# Sample data
conn.execute("SELECT stable_car_key, chat_id, config_name FROM sent_ads LIMIT 5").fetchall()
```

Code check:
```bash
grep -n "config_name" run_daily_pipeline.py telegram_sender.py feedback_store.py telegram_feedback_bot.py
```

Pass criterion: `config_name` present on the entire path from card to reaction_details.

## Output format

Produce a structured report:

```
## BLOCK 0 — AUDIT REPORT

| Block | Status | Details |
|-------|--------|---------|
| A. Telegram Users | ✅ PASS / ❌ FAIL / ⚠️ NEEDS VPS CHECK | ... |
| B. Telegram Feedback | ✅ PASS / ❌ FAIL / ⚠️ NEEDS VPS CHECK | ... |
| C. Pipeline | ✅ PASS / ❌ FAIL / ⚠️ NEEDS VPS CHECK | ... |
| D. Dedup | ✅ PASS / ❌ FAIL / ⚠️ NEEDS VPS CHECK | ... |
| E. Config Name Audit | ✅ PASS / ❌ FAIL / ⚠️ NEEDS VPS CHECK | ... |

### OVERALL: ✅ PASS / ❌ FAIL

**Reason:** [one-line summary of any FAIL blocks]

### WHAT WAS NOT TOUCHED:
- Code not modified
- DB not modified
- Git not touched
- VPS not touched

### NEXT STEP:
[What to do based on audit result]
```

## Key findings from Haraba Mini BLOCK 0 (2026-06-13)

- Block A: ✅ PASS — telegram_users is single source, legacy table unused
- Block B: ✅ PASS (code) / ⚠️ NEEDS VPS CHECK — code correct, VPS data needs verification
- Block C: ✅ PASS (code) / ⚠️ NEEDS VPS CHECK — code correct, cron/flock on VPS needs check
- Block D: ✅ PASS — sent_ads fills up, composite key (stable_car_key + chat_id) works
- Block E: ❌ FAIL — config_name = NULL in all sent_ads rows; column missing from feedback and reaction_details

## Common pitfalls

1. **Local DB vs VPS DB mismatch** — row counts differ (10 rows locally vs 350 on VPS). Always note which DB you're checking.
2. **Column exists but all NULL** — `config_name` existed in sent_ads schema but had 0 non-NULL values.
3. **Code added but not deployed** — `config_name` logic was in `run_daily_pipeline.py` and `telegram_sender.py` locally but not committed/deployed to VPS.
4. **Table exists but empty** — `reaction_details` table existed but had 0 rows locally (31 on VPS).
5. **Import errors at runtime** — `needs_comment()` existed locally but was not committed, causing ImportError on VPS.
