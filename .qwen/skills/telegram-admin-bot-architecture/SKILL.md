---
name: telegram-admin-bot-architecture
description: Architecture pattern for a separate admin Telegram bot that manages users, stats, and system state without touching the operational pipeline
source: auto-skill
extracted_at: '2026-06-11T14:04:54.308Z'
---

# Telegram Admin Bot Architecture

## Core principle

**Never mix** the operational bot (sends cards to managers) with the admin bot (manages system). They share only the SQLite database.

```
telegram_feedback_bot.py   — operational: sends cards, collects reactions
admin_bot/                 — management: users, stats, DB, logs
feedback_store.py          — shared: SQLite operations
run_daily_pipeline.py      — pipeline: collects, audits, sends
```

## Role hierarchy

```
owner (OWNER_ID in .env)
 ├─ full access to everything
 ├─ cannot be paused/disabled/deleted (hard-coded protection)
 └─ auto-created in telegram_users on first bot start

admin (ADMIN_IDS in .env, comma-separated)
 ├─ view stats, reactions, DB
 ├─ pause/resume/disable managers
 └─ CANNOT modify owner

manager
 └─ receives cards (controlled by status)
```

## Status workflow

```
pending → active    (approve — starts receiving cards)
active  → paused    (vacation/temporary off)
paused  → active    (resume — back to receiving)
any     → disabled  (permanent off)
```

## Key files

```
admin_bot/
├── admin_bot.py           — entry point, registers handlers
├── config.py              — loads .env, OWNER_ID, ADMIN_IDS
├── permissions.py         — is_owner(), is_admin(), can_modify_user()
├── keyboards.py           — inline keyboard layouts
├── formatting.py          — message formatting
├── handlers/
│   ├── start.py           — /start, /menu
│   └── menu.py            — callback handlers for all menu actions
└── services/
    ├── db_service.py       — migrations, connections, db_size
    ├── users_service.py    — CRUD, status changes, get_active_users()
    ├── reactions_service.py — reaction stats by day/week
    ├── stats_service.py    — pipeline stats, conversion rates
    ├── cards_service.py    — cards_today, card_detail
    ├── searches_service.py — list of model searches
    └── logs_service.py     — last_run, last_errors, pipeline_summary
```

## Database migration pattern

Always use `CREATE TABLE IF NOT EXISTS` — safe to run multiple times:

```python
def ensure_tables():
    conn = get_connection()
    conn.execute("""CREATE TABLE IF NOT EXISTS telegram_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        role TEXT DEFAULT 'manager',
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        updated_at TEXT
    )""")
```

## Owner auto-creation and protection

On bot start, automatically seed owner:

```python
def ensure_owner_exists():
    existing = conn.execute(
        "SELECT role, status FROM telegram_users WHERE telegram_id = ?",
        (OWNER_ID,)
    ).fetchone()
    if not existing:
        # Create owner as active
        conn.execute("INSERT INTO telegram_users ... VALUES (?, 'owner', 'active', ...)", (OWNER_ID, ...))
    else:
        # Ensure role=owner, status=active even if corrupted
        conn.execute("UPDATE telegram_users SET role='owner', status='active' WHERE telegram_id=?", (OWNER_ID,))
```

Protection in permissions:

```python
def can_modify_user(actor_id: int, target_id: int) -> tuple[bool, str]:
    if not is_admin(actor_id):
        return False, "⛔ Нет доступа."
    if is_owner(target_id):
        return False, "⛔ Owner нельзя отключить, удалить или поставить на паузу."
    return True, ""
```

## .env structure

```env
# Operational bot
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Admin bot
ADMIN_BOT_TOKEN=...
OWNER_ID=8992376203
ADMIN_IDS=8992376203

# Paths
DB_PATH=results/feedback.db
LOG_PATH=logs/
BACKUP_PATH=backups/
EXPORT_PATH=exports/
```

## VPS deployment (systemd)

```ini
[Unit]
Description=Haraba Mini Admin Telegram Bot
After=network.target

[Service]
User=haraba
WorkingDirectory=/home/haraba/harabaBot
EnvironmentFile=/home/haraba/harabaBot/.env
ExecStart=/home/haraba/harabaBot/.venv/bin/python -m admin_bot.admin_bot
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Adding new menu sections

When adding a new section (e.g. 🧠 Обучение), follow this pattern:

### 1. Create handler in `admin_bot/handlers/`

```python
# admin_bot/handlers/learning.py
from admin_bot.handlers.menu import safe_edit
from admin_bot.keyboards import back_keyboard

async def learning_callback_handler(update, context):
    query = update.callback_query
    await query.answer()
    # ... handle callback data
```

### 2. Register in `admin_bot.py` with specific pattern

```python
from admin_bot.handlers.learning import learning_callback_handler

# Order matters: specific patterns before general ones
application.add_handler(CallbackQueryHandler(learning_callback_handler, pattern="^(learning_|config_)"))
application.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^(menu_|back_to_menu)"))
```

### 3. Add button to main menu

```python
# admin_bot/keyboards.py
[InlineKeyboardButton("🧠 Обучение", callback_data="menu_learning")]
```

### 4. Handle menu_* routing in menu.py

The `menu_callback_handler` catches `menu_*` patterns. For `menu_learning`, delegate to the learning handler:

```python
if data == "menu_learning":
    from admin_bot.handlers.learning import learning_callback_handler
    await learning_callback_handler(update, context)
    return
```

**Critical:** Without this delegation, clicking the button does nothing because `menu_callback_handler` catches `menu_learning` (matches `menu_*`) but has no case for it.

## Analytics pattern (learning_report, config_report)

Create a separate `ris_analytics.py` (or similar) with read-only SQL functions. The analytics services should never modify the database.

```python
# ris_analytics.py
def get_learning_report():
    conn = get_conn()
    # SELECT only, no INSERT/UPDATE/DELETE
    result = conn.execute("SELECT action, COUNT(*) ...").fetchall()
    conn.close()
    return result
```

Use these in the handler for formatting:

```python
from ris_analytics import get_learning_report, get_config_report

def _format_learning_report(report):
    lines = [f"📊 Learning Report\n\nВсего реакций: {report['total']}"]
    return "\n".join(lines)
```

## Single source of truth: telegram_users

**Rule:** `telegram_users` is the ONLY source of truth for who receives cards. `telegram_recipients` is legacy — do not delete, do not read from.

### Rewriting feedback_store.py functions

**get_enabled_recipients()** — reads ONLY from telegram_users:
```python
def get_enabled_recipients():
    """Get active recipients from telegram_users only."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT telegram_id as chat_id, username, first_name, role
        FROM telegram_users
        WHERE status = 'active'
        ORDER BY role
    """)
    return [dict(row) for row in c.fetchall()]
```

**get_all_recipients()** — reads ONLY from telegram_users:
```python
def get_all_recipients():
    """Get ALL recipients from telegram_users only."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT telegram_id as chat_id, username, first_name, role, status,
               CASE WHEN status != 'disabled' THEN 1 ELSE 0 END as enabled
        FROM telegram_users
        ORDER BY role, telegram_id
    """)
    return [dict(row) for row in c.fetchall()]
```

**register_recipient()** — upsert into telegram_users, never overwrite status:
```python
def register_recipient(chat_id, user_id="", username="", first_name="", role="manager"):
    """Upsert into telegram_users. If exists, only update username/first_name (never status)."""
    conn = get_conn()
    c = conn.cursor()
    telegram_id = int(chat_id)
    existing = c.execute("SELECT id FROM telegram_users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    if not existing:
        c.execute("""
            INSERT INTO telegram_users (telegram_id, username, first_name, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', ?, ?)
        """, (telegram_id, username, first_name, role, now, now))
    else:
        c.execute("""
            UPDATE telegram_users
            SET username = COALESCE(NULLIF(?,''), username),
                first_name = COALESCE(NULLIF(?,''), first_name),
                updated_at = ?
            WHERE telegram_id = ?
        """, (username, first_name, now, telegram_id))
```

### Sync script pattern

Create `scripts/sync_recipients_to_users.py`:
1. Read ALL from telegram_recipients
2. For each: if NOT in telegram_users → INSERT with status='active'
3. If EXISTS → DO NOTHING (respect paused/disabled/pending)
4. Owner → never touch
5. NEVER delete telegram_recipients

### Auto-registration via /start (operational bot)

When a new user writes `/start`:
```python
async def start(update, context):
    user = update.effective_user
    telegram_id = user.id

    # Check if exists
    existing = conn.execute("SELECT status FROM telegram_users WHERE telegram_id = ?", (telegram_id,)).fetchone()

    if not existing:
        # NEW → insert as pending
        conn.execute("""
            INSERT INTO telegram_users (telegram_id, username, first_name, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
        """, (telegram_id, username, first_name, "manager", now, now))

        # Notify owner
        await context.bot.send_message(chat_id=OWNER_ID, text=f"🆕 New user: @{user.username} (ID: {telegram_id})")
        await update.message.reply_text("✅ Заявка отправлена. Ожидайте подтверждения.")
    else:
        # Existing — show status message, NEVER overwrite
        status_messages = {
            "pending": "⏳ Заявка ожидает подтверждения.",
            "active": "✅ Вы подключены.",
            "paused": "⏸ Вы временно отключены.",
            "disabled": "⛔ Доступ отключён.",
        }
        await update.message.reply_text(status_messages.get(existing["status"], "✅ Вы подключены."))
```

### Verification checklist

```bash
python scripts/verify_users_sync.py

# Should show:
# ✅ active users == enabled recipients
# ✅ all users == all recipients
# ✅ pending users NOT in enabled recipients
# ✅ paused users NOT in enabled recipients
```

### Key rules

1. **Backup first:** `cp results/feedback.db results/feedback_before_sync.db`
2. **Never delete telegram_recipients** — keep as legacy
3. **Never overwrite status** — if user is paused/disabled/pending, /start must NOT change it
4. **Owner protection** — owner (8992376203) always stays active
5. **pending ≠ active** — only `status='active'` receives cards

## User display name fallback in buttons

When rendering inline keyboard buttons, don't assume username exists:

```python
def users_list_keyboard(users):
    for u in users:
        display_name = u.get("username") or u.get("first_name") or str(u["telegram_id"])
        if u.get("username"):
            display_name = f"@{display_name}"
        label = f"{status_icon} {display_name} ({u['status']})"
```

Without this fallback, owner (who has no @username) shows as `✅ None (active)`.

## Deployment order

1. Create admin bot → get token → add to .env
2. Run migrations locally → verify telegram_users table
3. Sync existing recipients: `telegram_recipients` → `telegram_users`
4. Test /start, /users, /approve, /pause on local machine
5. Test real send: `python telegram_sender.py --send --limit 1` — verify active gets, paused doesn't
6. Deploy to VPS as separate systemd service
7. Only THEN modify operational bot to read from `telegram_users WHERE status='active'`

## Common mistakes to avoid

- ❌ Don't modify the operational bot before admin bot is tested
- ❌ Don't skip the `is_owner()` check in can_modify_user()
- ❌ Don't use `reset_sent_ads()` in normal pipeline — only for manual testing
- ❌ Don't store admin_bot in same process as telegram_feedback_bot — separate services

## Telegram callback safe_edit pattern

`query.edit_message_text()` throws `BadRequest: Message is not modified` when the content and markup are exactly the same as the current message (e.g. pressing "Back" to the same menu). Always wrap in a try/except:

```python
from telegram.error import BadRequest

async def safe_edit(query, text, reply_markup=None):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except BadRequest as e:
        if "not modified" in str(e):
            pass  # Nothing changed — this is normal
        else:
            raise
```

Use `safe_edit()` for ALL `edit_message_text` calls in callback handlers.

## Adapting to existing database schemas

The operational bot may have created tables with different column names than what you expect. **Always inspect existing schemas before writing SQL.**

### Existing table reality (haraba-mini feedback.db)

| Expected column | Actual column | Table |
|---|---|---|
| `reaction` | `action` | `feedback` |
| `telegram_id` | `telegram_user_id` | `feedback` |
| `created_at` | `first_sent_at` | `sent_ads` |

### How to discover before coding

```bash
python -c "
import sqlite3; conn = sqlite3.connect('results/feedback.db')
rows = conn.execute(\"SELECT sql FROM sqlite_master WHERE type='table'\").fetchall()
for r in rows: print(r[0], '\n')
"
```

### Rule

When joining `telegram_users` with `feedback`:
```sql
-- WRONG
JOIN feedback f ON u.telegram_id = f.telegram_id

-- CORRECT (existing schema)
JOIN feedback f ON f.telegram_user_id = u.telegram_id
```

When querying sent_ads by date:
```sql
-- WRONG
WHERE created_at >= ?

-- CORRECT (existing schema)
WHERE first_sent_at >= ?
```

When grouping reactions:
```sql
-- WRONG
SELECT reaction, COUNT(*) FROM feedback GROUP BY reaction

-- CORRECT (existing schema)
SELECT action, COUNT(*) FROM feedback GROUP BY action
```
