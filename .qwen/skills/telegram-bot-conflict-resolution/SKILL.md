---
name: telegram-bot-conflict-resolution
description: Only one python-telegram-bot polling instance can run at a time. 409 Conflict error means another instance is still running OR shared token OR stale log.
source: auto-skill
extracted_at: '2026-06-12T14:00:00.000Z'
---

## Problem

When running a python-telegram-bot with `run_polling()`, you get:

```
telegram.error.Conflict: terminated by other getUpdates request
```

### Possible causes (in order of likelihood)

1. **Duplicate process** — two instances of the same bot are running
2. **Shared token** — two DIFFERENT bots configured with the same TELEGRAM_BOT_TOKEN
3. **Stale log** — Conflict from a past incident, still visible in appended log file
4. **webhook + polling conflict** — one bot uses webhook, another uses polling on same token

## Diagnose FIRST — do NOT kill/restart immediately

See skill: `vps-bot-troubleshooting`

Run these checks:

```bash
# 1. How many instances?
ps -ef | grep admin_bot | grep -v grep
ps -ef | grep telegram_feedback_bot | grep -v grep
pgrep -af admin_bot
pgrep -af telegram_feedback_bot

# 2. Are tokens unique?
grep BOT_TOKEN .env
# Each bot must have its own unique token

# 3. Is the error current or stale?
tail -5 logs/admin_bot.log
# If using >> (append), old errors persist indefinitely

# 4. Where is polling called?
grep -rn 'run_polling' admin_bot/ telegram_feedback_bot.py
# Should be exactly once per bot, in its own entry point
```

## Decision

| Finding | Action |
|---------|--------|
| Only 1 process per bot, tokens unique | **No action needed** — error is stale in log |
| 2+ processes for same bot | Kill duplicates, keep oldest PID |
| Two bots share same token | Fix .env — assign unique tokens |
| Polling called in wrong place | Move to entry point only |

## Fix: Kill duplicate processes

### On Linux (VPS)

```bash
# Find all PIDs for the bot
pgrep -f "admin_bot.admin_bot"
pgrep -f "telegram_feedback_bot"

# Kill duplicates — keep the OLDEST (lowest PID)
kill -9 <newer_PID>

# Wait 3 seconds for Telegram API to release
sleep 3
```

**Critical:** Use `kill -9` with specific PIDs. Do NOT `pkill -9 python` — it kills ALL Python processes including cron tasks and pipelines.

### On Windows

```bash
# Kill specific PID
taskkill /F /PID <pid>

# Wait 2 seconds
timeout /t 2 /nobreak
```

## How to start bots cleanly

### Linux (VPS) — systemd (recommended, current setup as of 2026-06-12)

```bash
# Check status
systemctl status haraba-feedback-bot
systemctl status haraba-admin-bot

# Restart if needed
sudo systemctl restart haraba-feedback-bot
sudo systemctl restart haraba-admin-bot

# Verify
systemctl is-active haraba-feedback-bot
systemctl is-active haraba-admin-bot
```

### Linux (VPS) — background with nohup (legacy, not recommended)

```bash
# Kill old first
pkill -f "admin_bot.admin_bot"
pkill -f "telegram_feedback_bot"
sleep 3

# Start fresh (ONE of each)
cd /home/haraba/harabaBot_code
nohup .venv/bin/python -m admin_bot.admin_bot > logs/admin_bot.log 2>&1 &
nohup .venv/bin/python telegram_feedback_bot.py > logs/feedback_bot.log 2>&1 &

# Verify only 1 each
ps aux | grep -E "admin_bot|telegram_feedback" | grep -v grep
```

**Warning:** nohup through SSH may create bash wrapper processes. If you see duplicates, kill the bash wrappers too (higher PIDs). **Prefer systemd when available.**

### Windows — background

```bash
start /b python telegram_feedback_bot.py
```

## Important

- Only ONE `run_polling()` instance per bot token can exist at any time
- The Telegram API terminates the older instance when a new one connects
- **Log files with >> (append) preserve old errors** — a Conflict in the log doesn't mean it's happening now
- Background processes may not terminate cleanly — always kill by specific PID
- For production on VPS, consider webhooks instead of polling to avoid conflict entirely