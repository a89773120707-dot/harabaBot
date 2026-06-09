---
name: telegram-multi-recipient-system
description: Multi-recipient Telegram pipeline — owner + managers get same cards with independent dedup and feedback per chat_id
source: auto-skill
extracted_at: '2026-06-09T15:42:00.000Z'
---

## Problem

Single chat_id pipeline means only one person receives cards. To involve a manager who also evaluates cars, you need:

1. Same card sent to both owner AND manager
2. Independent dedup — owner already received ≠ manager already received
3. Independent feedback — owner's "buy" ≠ manager's "buy"
4. Role tracking — know WHO reacted (owner vs manager)

## Solution

### 1. telegram_recipients table

```sql
CREATE TABLE telegram_recipients (
    chat_id TEXT PRIMARY KEY,
    user_id TEXT,
    username TEXT,
    first_name TEXT,
    role TEXT,          -- 'owner' or 'manager'
    enabled INTEGER DEFAULT 1,
    created_at TEXT
);
```

### 2. Registration commands

```python
# In telegram_feedback_bot.py:
async def register_owner(update, context):
    register_recipient(
        chat_id=str(update.message.chat_id),
        user_id=str(update.message.from_user.id),
        username=update.message.from_user.username or "",
        first_name=update.message.from_user.first_name or "",
        role="owner"
    )

async def register_manager(update, context):
    # Same logic, role="manager"
```

Owner is auto-registered on bot start from `.env` chat_id:

```python
def main():
    register_recipient(chat_id=str(chat_id), role="owner")
```

### 3. Sender reads recipients from DB

```python
def run_send(limit=None):
    recipients = get_enabled_recipients()  # from feedback_store.py
    if not recipients:
        recipients = [{"chat_id": chat_id_from_env, "role": "owner"}]

    for card in candidates:
        for recipient in recipients:
            r_chat_id = recipient["chat_id"]
            dedup_status = check_dedup_with_chat_id(card, r_chat_id)

            if dedup_status == "same_price":
                continue  # This recipient already got this card

            send_car_card_sync(bot_token, r_chat_id, card, config)
            mark_sent_with_chat_id(card, r_chat_id)
```

### 4. Dedup with chat_id

```python
def check_dedup_with_chat_id(card, chat_id):
    """Check dedup per recipient."""
    stable_key = _build_stable_key(card)
    c.execute("""
        SELECT price FROM sent_ads
        WHERE stable_car_key = ? AND chat_id = ?
    """, (stable_key, str(chat_id)))
    # Returns: "new" | "same_price" | "price_drop" | "price_increased"
```

Key: `stable_car_key + chat_id` is the unique key.
- Owner gets card → owner's dedup entry created
- Manager gets same card → manager's dedup entry created (different chat_id)
- Same card sent again → owner skips (same_price), manager skips (same_price)

### 5. sent_ads schema extension

```sql
ALTER TABLE sent_ads ADD COLUMN chat_id TEXT;
```

Each row: `(stable_car_key, chat_id)` → unique per recipient.

### 6. Feedback with reviewer_role

```python
# In feedback_store.py save_feedback():
INSERT INTO feedback (..., telegram_chat_id, telegram_user_id, telegram_username, reviewer_role, ...)
VALUES (..., card["telegram_chat_id"], card["telegram_user_id"], card["telegram_username"], card["reviewer_role"], ...)
```

```python
# In telegram_feedback_bot.py text_handler:
recipients = get_all_recipients()
my_role = "viewer"
for r in recipients:
    if r["chat_id"] == str(chat_id):
        my_role = r["role"]
        break

feedback_card["reviewer_role"] = my_role
feedback_card["telegram_chat_id"] = str(chat_id)
feedback_card["telegram_user_id"] = str(user.id)
feedback_card["telegram_username"] = user.username or ""
```

### 7. Management commands

| Command | Description |
|---------|-------------|
| `/register_owner` | Register as owner (receives all cards) |
| `/register_manager` | Register as manager (receives all cards) |
| `/recipients` | List all registered recipients |
| `/disable_me` | Disable yourself from receiving cards |
| `/help` | Show all commands with descriptions |
| `/start` | Welcome message + "📋 Commands" button |

### 8. Verification

```python
from feedback_store import get_all_recipients, get_enabled_recipients, register_recipient

# Check recipients
recipients = get_all_recipients()
# [{'chat_id': '8992376203', 'role': 'owner', 'enabled': 1},
#  {'chat_id': '1649929050', 'role': 'manager', 'enabled': 1, 'username': 'protocol_skrin'}]

# Check sent_ads per recipient
import sqlite3
c.execute('SELECT stable_car_key, chat_id, send_count FROM sent_ads')
# ('id:173324131', '8992376203', 1)  -- owner received
# ('id:173324131', '1649929050', 1)  -- manager received (separate dedup)
```

## Key principles

1. **One card → multiple recipients** — each gets independent copy
2. **Dedup is per recipient** — owner's history ≠ manager's history
3. **Feedback is per recipient** — role, chat_id, username stored with each reaction
4. **Manager self-registers** — writes `/register_manager` to bot
5. **Owner auto-registers** — from .env chat_id on bot start
6. **Disable is self-service** — `/disable_me` sets enabled=0

## Files

- `feedback_store.py` — telegram_recipients table, check_dedup_with_chat_id(), mark_sent_with_chat_id()
- `telegram_sender.py` — loops over recipients, per-recipient dedup
- `telegram_feedback_bot.py` — /register_owner, /register_manager, /recipients, /disable_me, reviewer_role tracking
