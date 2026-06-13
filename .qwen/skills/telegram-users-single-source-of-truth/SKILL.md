---
name: telegram-users-single-source-of-truth
description: telegram_users table is the ONLY source of truth for all bots — recipients, registration, status management
source: auto-skill
extracted_at: '2026-06-12T14:00:00.000Z'
---

# telegram_users — Single Source of Truth

## Rule

`telegram_users` is the ONLY source of truth for recipient management. Both the main feedback bot and admin bot MUST read/write to this table. `telegram_recipients` is legacy — never delete it, but never use it for active logic.

## Why

Two tables (`telegram_recipients` and `telegram_users`) were storing user data independently, causing:
- Admin bot showed 3 users, main bot showed 5
- Different bots had different views of who should receive cards
- No way to manage pending/approve/paused/disabled lifecycle

## Table Schema

```sql
CREATE TABLE telegram_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    role TEXT DEFAULT 'manager',     -- owner, admin, manager
    status TEXT DEFAULT 'pending',   -- pending, active, paused, disabled
    created_at TEXT,
    updated_at TEXT
);
```

## Status Lifecycle

```
New user /start
    → INSERT status='pending'
    → Notify owner about new user
    → Admin shows with ⏳ icon

Owner approves (admin bot)
    → UPDATE status='active'
    → User receives cards

Manager on vacation
    → UPDATE status='paused'
    → No cards, but data preserved

Manager returns
    → UPDATE status='active'
    → Cards resume

Problem user
    → UPDATE status='disabled'
    → No cards, visible in admin panel
```

## Implementation Rules

### feedback_store.py — Read from telegram_users ONLY

```python
def get_enabled_recipients():
    """Only active users get cards."""
    # SELECT FROM telegram_users WHERE status='active'

def get_all_recipients():
    """All users visible in /recipients."""
    # SELECT FROM telegram_users (all statuses)

def register_recipient(chat_id, ...):
    """Upsert into telegram_users. If exists, NEVER change status."""
    # INSERT if new (default status='active' for backward compat)
    # UPDATE username/first_name only if exists

def disable_recipient(chat_id):
    """Set status='disabled' in telegram_users."""
```

### Main bot /start — Auto-registration

```
New user → INSERT telegram_users(status='pending')
    → Reply: "Заявка отправлена, ожидайте подтверждения"
    → Notify owner: "🆕 New user: @username (ID: 123)"

Existing pending → "Заявка уже ожидает подтверждения"
Existing active → "Вы подключены к рассылке"
Existing paused → "Вы временно отключены"
Existing disabled → "Доступ отключён"
```

**Critical:** Never overwrite existing status on re-registration. If paused, stay paused. If disabled, stay disabled.

### telegram_sender — Only active

```python
recipients = get_enabled_recipients()  # WHERE status='active'
# pending/paused/disabled NEVER receive cards
```

### Admin bot — Show ALL statuses

```python
get_all_users()  # Shows pending(⏳), active(✅), paused(⏸), disabled(❌)
```

### Sync Script

When migrating from `telegram_recipients` to `telegram_users`:

```python
# For each row in telegram_recipients:
#   If telegram_id NOT in telegram_users → INSERT with status='active'
#   If telegram_id EXISTS → DO NOT change status (respect paused/disabled)
# NEVER delete telegram_recipients table
```

## VPS Deployment — CRITICAL

**ALWAYS check VPS git status before any fix.** The #1 cause of "changes don't take effect" is stale code on VPS.

```bash
# On VPS — ALWAYS run first:
cd /home/haraba/harabaBot_code
git status          # look for "behind origin/main by N commits"
git log --oneline -3
git fetch origin
git log --oneline origin/main -3
```

If VPS is behind → `git pull` before doing anything else.

### After git pull on VPS:

```bash
python scripts/sync_recipients_to_users.py
```

This adds any missing users from legacy `telegram_recipients` table.

### Troubleshooting: "Fix doesn't work on VPS"

If a code change works locally but not on VPS:
1. Check `git status` on VPS — is it behind origin/main?
2. Check `git diff <file>` — are there uncommitted local changes?
3. Verify the running process uses the new code (restart after `git pull`)
4. Check if old code overwrites your fix on startup (e.g., `ensure_owner_exists()`)

**Common trap:** Running manual SQL fixes on VPS while old code is still running — the old code will overwrite your changes on next restart.

## Anti-patterns

- ❌ Two bots reading from different tables
- ❌ register_recipient() overwriting status on existing user
- ❌ Making new users 'active' immediately (spam risk)
- ❌ /start changing paused → pending (disrupts admin management)
- ❌ Deleting telegram_recipients (keep as historical reference)
- ❌ `/recipients` using `get_all_recipients()` — must use `get_enabled_recipients()`
- ❌ Assuming `Sent: X` means "user received" — it means Telegram API returned HTTP 200; dedup may prevent the same user from getting duplicate cards

## /recipients Command — Must Use get_enabled_recipients()

The `/recipients` command in the main feedback bot MUST call `get_enabled_recipients()` (which filters `WHERE status='active'`), NOT `get_all_recipients()` (which returns everyone).

**Bug found 2026-06-12:** `show_recipients()` called `get_all_recipients()`, showing paused user `ismailovvv97` as a recipient even though they shouldn't receive cards.

**Fix:**
```python
async def show_recipients(update, context):
    from feedback_store import get_enabled_recipients
    recipients = get_enabled_recipients()  # Only active
```

## Unknown User Registration

When a new user writes `/start` to the main bot, they are auto-registered as `status='pending'`. But if they were added to VPS via `sync_recipients_to_users.py` (which sets `status='active'` for legacy users), they bypass the pending approval flow.

**Always check for unknown chat_ids in `sent_ads`** — they may indicate unauthorized registrations:
```sql
SELECT DISTINCT s.chat_id, u.username, u.status
FROM sent_ads s
LEFT JOIN telegram_users u ON s.chat_id = u.telegram_id
WHERE u.telegram_id IS NULL OR u.role NOT IN ('owner', 'manager')
ORDER BY s.chat_id;
```

## Cron Pipeline with Flock

Pipeline runs via cron should use `flock` to prevent parallel execution:

```cron
*/10 * * * * flock -n /tmp/haraba_pipeline.lock /home/haraba/harabaBot_code/run_pipeline_cron.sh >> /home/haraba/harabaBot_code/logs/pipeline_cron.log 2>&1
```

**Why:** Without flock, if a pipeline takes >10 minutes, a new one starts → parallel runs → duplicate sends, race conditions on sent_ads.

**`flock -n`:** Non-blocking — if lock is held, skip this run silently.

## Sent: X Metric

`Sent: X` in pipeline logs means `send_car_card_sync()` returned `True` → real Telegram API `send_message` or `send_photo` succeeded (HTTP 200 OK). It does NOT mean:
- The user actually saw the message (bot could be blocked)
- The user was supposed to receive it (check status first)
- It's not a duplicate (check sent_ads first)

The counter is incremented ONLY on success:
```python
success = send_car_card_sync(bot_token, r_chat_id, card, config)
if success:
    mark_sent_with_chat_id(card, r_chat_id, status=status)
    sent += 1  # ← Only on real HTTP 200
else:
    failed += 1
```
