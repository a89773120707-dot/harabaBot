---
name: telegram-bot-conflict-resolution
description: Only one python-telegram-bot polling instance can run at a time. 409 Conflict error means another instance is still running.
source: auto-skill
extracted_at: '2026-06-08T22:10:00.000Z'
---

## Problem

When running `python telegram_feedback_bot.py`, you get:

```
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
```

This happens when:
1. A previous bot instance is still running in the background
2. Multiple processes call `app.run_polling()` simultaneously
3. `start /b` doesn't properly isolate the process

## Fix

### Kill old instances before starting

```bash
# Kill all python processes running telegram_feedback_bot
taskkill /F /IM python.exe /FI "PID eq <pid>"

# Or kill by window title
taskkill /F /FI "WINDOWTITLE eq *telegram_feedback*"

# Wait 2 seconds for Telegram API to release
timeout /t 2 /nobreak >nul

# Start fresh
python telegram_feedback_bot.py
```

### Alternative: Use webhook instead of polling

For production, use webhooks instead of polling to avoid conflicts:

```python
app.run_webhook(
    listen="0.0.0.0",
    port=8443,
    url_path=TOKEN,
    webhook_url=f"https://your-domain/{TOKEN}",
)
```

### Background mode without conflict

Use `start /b` but ensure only one instance:

```bash
# Check if already running
tasklist | findstr "python.exe"

# If running, kill it
taskkill /F /IM python.exe

# Start fresh in background
start /b python telegram_feedback_bot.py
```

## Important

- Only ONE `run_polling()` instance per bot token can exist at any time
- The Telegram API will terminate the older instance when a new one connects
- Background processes may not terminate cleanly — always kill by PID