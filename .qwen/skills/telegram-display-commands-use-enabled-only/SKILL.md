---
name: telegram-display-commands-use-enabled-only
description: Display commands (/recipients, /users list) must use get_enabled_recipients() to show only active users, not get_all_recipients()
source: auto-skill
extracted_at: '2026-06-12T14:36:00.000Z'
---

# Telegram Display Commands — Use get_enabled_recipients() for Active Users

## Rule

Display commands that show "who receives cards" MUST use `get_enabled_recipients()` (which returns only `status='active'`), NOT `get_all_recipients()` (which returns all statuses).

## Why

The `/recipients` command in `telegram_feedback_bot.py` was calling `get_all_recipients()` which showed ALL users including those with `status='paused'` and `status='pending'`. This created confusion:

- Admin bot correctly showed `ismailovvv97 = paused`
- `/recipients` showed `ismailovvv97` as an active recipient
- User thought the admin panel was broken, when actually `/recipients` was reading wrong data

## Implementation

### /recipients — Show ONLY active users

```python
async def show_recipients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список активных получателей."""
    from feedback_store import get_enabled_recipients
    recipients = get_enabled_recipients()  # WHERE status='active'
    if not recipients:
        await update.message.reply_text("Получателей пока нет.")
        return
    lines = ["📋 Активные получатели:"]
    for r in recipients:
        lines.append(f"✅ {r['role']}: {r.get('username','?')} (chat: {r['chat_id']})")
    await update.message.reply_text("\n".join(lines))
```

### When get_all_recipients() IS appropriate

`get_all_recipients()` is still valid for:
- Looking up a user's role when saving feedback (need to find role even for paused users who reacted earlier)
- Internal lookups where you need ALL users regardless of status

```python
# OK — role lookup for feedback attribution
recipients = get_all_recipients()
for r in recipients:
    if r["chat_id"] == str(chat_id):
        my_role = r["role"]
```

### Function contract

```python
# feedback_store.py
def get_enabled_recipients():
    """Only users with status='active' — for card sending and display."""
    # SELECT FROM telegram_users WHERE status = 'active'

def get_all_recipients():
    """All users regardless of status — for internal lookups."""
    # SELECT FROM telegram_users (no WHERE on status)
```

## Verification

After implementing:

```python
from feedback_store import get_enabled_recipients
enabled = get_enabled_recipients()
# Should match: SELECT telegram_id FROM telegram_users WHERE status='active'
```

## Anti-patterns

- ❌ `/recipients` calling `get_all_recipients()` — shows paused/pending as active
- ❌ Displaying `enabled=1` from legacy `telegram_recipients` table
- ❌ Mixing data sources: admin bot reads `telegram_users`, /recipients reads `telegram_recipients`
- ❌ Showing users with ❌ icon in /recipients — they shouldn't appear at all if not active
