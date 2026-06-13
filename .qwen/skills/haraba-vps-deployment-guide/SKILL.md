---
name: haraba-vps-deployment-guide
description: Step-by-step guide to deploy Haraba Mini pipeline and admin bot on a Linux VPS. Includes server info, git pull, .env setup, python-dotenv requirement, systemd services, and known pitfalls.
source: auto-skill
extracted_at: '2026-06-09T16:31:16.149Z'
updated_at: '2026-06-11T17:18:00Z'
---

# Haraba Mini VPS Deployment

## Server Info
- **Host:** `109.238.95.141`
- **User:** `haraba`
- **Project path:** `/home/haraba/harabaBot_code`
- **Python venv:** `/home/haraba/harabaBot_code/.venv` (Python 3.12.3)
- **Existing services:** `haraba-feedback-bot.service` (main bot, running)

## 1. Deploy Code (Git Pull)
```bash
cd /home/haraba/harabaBot_code
git pull origin main
```

## 2. Verify .env
Must contain:
```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
# Admin bot
ADMIN_BOT_TOKEN=...
OWNER_ID=8992376203
ADMIN_IDS=8992376203
DB_PATH=results/feedback.db
```

## 3. Verify Dependencies
```bash
cd /home/haraba/harabaBot_code
.venv/bin/pip install python-dotenv  # REQUIRED for admin_bot
```

## 4. Verify Database
```bash
ls -lh /home/haraba/harabaBot_code/results/feedback.db
```

## 5. Systemd Services

### Main Bot (already running)
```bash
sudo systemctl status haraba-feedback-bot
```

### Admin Bot (new)
Create `/etc/systemd/system/haraba-admin-bot.service`:
```ini
[Unit]
Description=Haraba Telegram Feedback Bot
After=network.target

[Service]
User=haraba
WorkingDirectory=/home/haraba/harabaBot_code
ExecStart=/home/haraba/harabaBot_code/.venv/bin/python telegram_feedback_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Admin Bot service** (`haraba-admin-bot.service`):
```ini
[Unit]
Description=Haraba Mini Admin Telegram Bot
After=network.target haraba-feedback-bot.service

[Service]
User=haraba
Group=haraba
WorkingDirectory=/home/haraba/harabaBot_code
ExecStart=/home/haraba/harabaBot_code/.venv/bin/python -m admin_bot.admin_bot
Restart=always
RestartSec=5
StandardOutput=append:/home/haraba/harabaBot_code/admin_bot.log
StandardError=append:/home/haraba/harabaBot_code/admin_bot.log
Environment=PYTHONPATH=/home/haraba/harabaBot_code

[Install]
WantedBy=multi-user.target
```

**Activate both:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable haraba-feedback-bot haraba-admin-bot
sudo systemctl start haraba-feedback-bot haraba-admin-bot
sudo systemctl status haraba-feedback-bot haraba-admin-bot --no-pager
```

## 6. Cron Job (Pipeline)
Create a wrapper script `run_pipeline.sh` (ensure it uses absolute paths):
```bash
#!/bin/bash
cd /home/haraba/harabaBot_code
source .venv/bin/activate
python run_daily_pipeline.py --send >> logs/pipeline.log 2>&1
```

**Setup Cron (every 15 minutes):**
```bash
chmod +x run_pipeline.sh
crontab -e
# Add: */15 * * * * /home/haraba/harabaBot_code/run_pipeline.sh
```

## 7. Verification
1. Check bot logs: `journalctl -u haraba-feedback-bot -f`
2. Check admin bot logs: `cat /home/haraba/harabaBot_code/admin_bot.log`
3. Check pipeline logs: `tail -f logs/pipeline.log`
4. Test Telegram interaction (`/help`, reactions, admin bot `/start`).

## 8. Known Pitfalls & Fixes

### python-dotenv not in venv
**Issue:** `ModuleNotFoundError: No module named 'dotenv'` when running `admin_bot.admin_bot`.
**Fix:** Install explicitly in the venv: `cd /home/haraba/harabaBot_code && .venv/bin/pip install python-dotenv`. Even if `pip install` was run earlier, the package may not be visible to the specific venv python binary.

### nohup/background process management
**Issue:** `nohup`, `bash -c`, `setsid` all fail to keep admin_bot running in background. Process starts but disappears immediately with empty log.
**Root cause:** `subprocess.Popen` from a remote python3 script kills child when parent exits. `nohup` with `&` inside `exec_command` doesn't properly detach.
**Working approach:** Create a bash script wrapper (`start_admin.sh`) and use `nohup bash start_admin.sh > log 2>&1 &`. For systemd, use the service file directly (which handles daemonization properly).

### sudo requires password on VPS
**Issue:** `sudo systemctl` commands hang waiting for password input via SSH.
**Fix:** Use `echo 'PASSWORD' | sudo -S <command>` for automated deployment, or run commands interactively.

### .env missing admin bot variables
**Issue:** Existing `.env` on VPS only had `TELEGRAM_BOT_TOKEN` — missing `ADMIN_BOT_TOKEN`, `OWNER_ID`, etc.
**Fix:** Append to `.env`:
```bash
echo 'ADMIN_BOT_TOKEN=...' >> .env
echo 'OWNER_ID=8992376203' >> .env
echo 'ADMIN_IDS=8992376203' >> .env
echo 'DB_PATH=results/feedback.db' >> .env
```

### `run_daily_pipeline.py` Import Error
**Issue:** `run_daily_pipeline.py` tries to import `run_pipeline` from `mobile_first_page_sampler.py`, but only `main()` exists.
**Fix:** The `run_daily_pipeline.py` script now uses `subprocess.run` to call `mobile_first_page_sampler.py` directly. Ensure `mobile_first_page_sampler.py` is executable and dependencies are installed.

### Missing Dependencies in `_trash`
**Issue:** `mobile_first_page_sampler.py` imports from `apply_all_searches_17.py` (and potentially others). If these were moved to `_trash/` during cleanup, the sampler will crash with `ModuleNotFoundError`.
**Fix:** Before running, verify imports in `mobile_first_page_sampler.py` and ensure required helper scripts (like `apply_all_searches_17.py`) are present in the root or Python path.

### Session File Location
**Issue:** Confusion over which file contains the Playwright state.
**Fact:** The code uses `data/state.json` (defined in `base.py`). Do not look for `storage_state.json` or `auth.json`.
