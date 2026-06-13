---
name: haraba-server-deployment
description: Procedure for deploying Haraba Mini pipeline and feedback bot to a Linux server (VPS) — includes git-based deploy, headless Playwright fix, systemd, cron, and multi-recipient feedback
source: auto-skill
extracted_at: '2026-06-09T16:50:00.000Z'
---

# Haraba Mini — Server Deployment Procedure

## Critical: Headless Mode for VPS

**Problem:** On headless Linux servers (no GUI), Playwright fails with:
```
Missing X server or $DISPLAY
Looks like you launched a headed browser without having a XServer running.
```

**Fix:** `session_manager.py` now defaults to `headless=True` on VPS:
```python
HEADLESS_DEFAULT = os.getenv("HEADLESS", "true").lower() == "true"

def get_authenticated_page(headless: bool = None):
    is_headless = headless if headless is not None else HEADLESS_DEFAULT
    browser = p.chromium.launch(headless=is_headless)
```

**Result:**
- **VPS:** runs headless automatically (no `$DISPLAY` needed)
- **Local:** can override with `HEADLESS=false python script.py`
- **`refresh_session_manual()`:** still forces `headless=False` (needs GUI for login)

---

## Prerequisites

- Linux server (Ubuntu 24.04+ recommended)
- Python 3.10+ installed
- SSH access
- GitHub repo with project code

## Step 1: Clone from GitHub (Remote)

```bash
ssh user@server_ip

# Clone the repo
cd ~
git clone https://github.com/a89773120707-dot/harabaBot.git
cd harabaBot

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium
sudo playwright install-deps
```

## Step 2: Transfer Secret Files (Local → Remote)

**These files are NOT in GitHub** — must be transferred manually via `scp`:

```bash
# From your local machine (PowerShell/CMD):
scp .env user@server_ip:~/harabaBot/
scp results/feedback.db user@server_ip:~/harabaBot/results/
scp data/state.json user@server_ip:~/harabaBot/data/
```

**Secret files audit (confirmed):**

| FILE | PATH | SIZE | NOTES |
|------|------|------|-------|
| `.env` | `.env` | ~94 bytes | Telegram bot tokens |
| `feedback.db` | `results/feedback.db` | ~45 KB | User reactions database |
| `state.json` | `data/state.json` | ~707 KB | Playwright desktop session (CRITICAL) |

**Do NOT transfer:** `data/state_backup.json` (old backup, 4 KB)

## Step 3: Verify on Server

```bash
cd ~/harabaBot
source .venv/bin/activate

# Check secret files exist
ls -lah .env results/feedback.db data/state.json

# Check deploy readiness
python deploy_check.py

# Check Haraba session
python check_server_session.py
# Expected: "Session status: VALID"
```

## Step 4: Test Pipeline

```bash
# Dry-run (no sends)
python run_daily_pipeline.py --dry-run --skip-collect

# Single card test (sends to all recipients)
python run_daily_pipeline.py --send --limit 1
```

**Expected for single send:**
- Card sent to Owner (Telegram)
- Card sent to Manager (Telegram)
- Both see photo, buttons (🟢🟡🔴📖📷)
- `results/feedback.db` gets new entries with `reviewer_role`

## Step 5: Setup Bot as Systemd Service

Create `/etc/systemd/system/haraba-bot.service`:

```ini
[Unit]
Description=Haraba Mini Telegram Feedback Bot
After=network.target

[Service]
Type=simple
User=haraba
WorkingDirectory=/home/haraba/harabaBot
ExecStart=/home/haraba/harabaBot/.venv/bin/python telegram_feedback_bot.py
Restart=always
RestartSec=10
StandardOutput=append:/home/haraba/harabaBot/logs/bot.log
StandardError=append:/home/haraba/harabaBot/logs/bot_error.log

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable haraba-bot
sudo systemctl start haraba-bot
sudo systemctl status haraba-bot
```

## Step 6: Setup Pipeline Cron Job

Create `/home/haraba/harabaBot/run_pipeline.sh`:

```bash
#!/bin/bash
cd /home/haraba/harabaBot
source .venv/bin/activate
python run_daily_pipeline.py --send >> logs/pipeline.log 2>&1
```

Make executable:
```bash
chmod +x run_pipeline.sh
```

Add to crontab (every 15 minutes):
```bash
crontab -e
```

Add line:
```cron
*/15 * * * * cd /home/haraba/harabaBot && .venv/bin/python run_daily_pipeline.py --send >> logs/pipeline.log 2>&1
```

**To change interval:**
- Every hour: `0 * * * *`
- Every 4 hours: `0 */4 * * *`

## Step 7: Update Code on Server

When local changes are pushed to GitHub:

```bash
cd ~/harabaBot
source .venv/bin/activate
git pull origin main

# If dependencies changed:
pip install -r requirements.txt

# If Playwright changed:
playwright install chromium

# Restart bot if code changed
sudo systemctl restart haraba-bot
```

**⚠️ Common pitfall:** Multiple project folders on server (e.g., `harabaBot` and `harabaBot_code`). Always verify you're in the correct directory:
```bash
pwd
grep "subprocess" run_daily_pipeline.py  # Should find subprocess, NOT run_pipeline import
```

## Troubleshooting

**"Missing X server" error:**
- Ensure `session_manager.py` has `HEADLESS_DEFAULT = os.getenv("HEADLESS", "true")`
- Verify no `headless=False` hardcoded in `get_authenticated_page()`

**Session expired on server:**
1. Re-auth locally: `python refresh_session.py` (opens GUI browser)
2. Upload new session: `scp data/state.json user@server:~/harabaBot/data/`
3. Restart: `sudo systemctl restart haraba-bot`

**Pipeline stuck on Collect cards:**
- `mobile_first_page_sampler.py` calls `get_authenticated_page()` — should use headless=True on VPS
- Check `grep "headless" session_manager.py` shows HEADLESS_DEFAULT usage
- The collector now runs via `subprocess` in `run_daily_pipeline.py` (not direct import)

**Bot not responding:**
```bash
sudo systemctl status haraba-bot
sudo journalctl -u haraba-bot -n 50
tail -f logs/bot_error.log
```

**Database locked:**
```bash
lsof results/feedback.db
```

## Monitoring

Check logs:
```bash
tail -f logs/bot.log
tail -f logs/pipeline.log
```

Check feedback count:
```bash
python -c "import sqlite3; c=sqlite3.connect('results/feedback.db').cursor(); c.execute('SELECT COUNT(*) FROM feedback'); print(f'Reactions: {c.fetchone()[0]}')"
```

Check pipeline health:
```bash
cat logs/pipeline.log | grep -E "STEP|FAILED|SUMMARY" | tail -20
```
