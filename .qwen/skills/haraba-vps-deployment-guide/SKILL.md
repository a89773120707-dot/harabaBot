---
name: haraba-vps-deployment-guide
description: Step-by-step guide to deploy Haraba Mini pipeline and bot on a Linux VPS using Git, systemd, and cron.
source: auto-skill
extracted_at: '2026-06-09T16:31:16.149Z'
---

# Haraba Mini VPS Deployment

This guide covers deploying the Haraba Mini project from a local Git repository to a Linux VPS.

## 1. Server Preparation
```bash
ssh user@server_ip
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git -y
```

## 2. Clone & Install
```bash
git clone <your_repo_url> ~/haraba-mini
cd ~/haraba-mini
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
```

## 3. Secrets & Data
Manually upload or create these files (they are not in Git):
- `.env` (Telegram tokens)
- `data/state.json` (Browser session)
- `results/feedback.db` (Database backup, if migrating)

## 4. Systemd Service (Bot)
Create `/etc/systemd/system/haraba-bot.service`:
```ini
[Unit]
Description=Haraba Telegram Bot
After=network.target

[Service]
User=root
WorkingDirectory=/root/haraba-mini
ExecStart=/root/haraba-mini/venv/bin/python telegram_feedback_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
**Activate:**
```bash
systemctl daemon-reload
systemctl enable haraba-bot
systemctl start haraba-bot
```

## 5. Cron Job (Pipeline)
Create a wrapper script `run_pipeline.sh` (ensure it uses absolute paths):
```bash
#!/bin/bash
cd /root/haraba-mini
source venv/bin/activate
python run_daily_pipeline.py --send --limit 3 >> logs/pipeline.log 2>&1
```

**Setup Cron (every 15 minutes):**
```bash
chmod +x run_pipeline.sh
crontab -e
# Add: */15 * * * * /root/haraba-mini/run_pipeline.sh
```

## 6. Verification
1. Check bot logs: `journalctl -u haraba-bot -f`
2. Check pipeline logs: `tail -f logs/pipeline.log`
3. Test Telegram interaction (`/help`, reactions).

## 7. Known Pitfalls & Fixes

### `run_daily_pipeline.py` Import Error
**Issue:** `run_daily_pipeline.py` tries to import `run_pipeline` from `mobile_first_page_sampler.py`, but only `main()` exists.
**Fix:** The `run_daily_pipeline.py` script now uses `subprocess.run` to call `mobile_first_page_sampler.py` directly. Ensure `mobile_first_page_sampler.py` is executable and dependencies are installed.

### Missing Dependencies in `_trash`
**Issue:** `mobile_first_page_sampler.py` imports from `apply_all_searches_17.py` (and potentially others). If these were moved to `_trash/` during cleanup, the sampler will crash with `ModuleNotFoundError`.
**Fix:** Before running, verify imports in `mobile_first_page_sampler.py` and ensure required helper scripts (like `apply_all_searches_17.py`) are present in the root or Python path.

### Session File Location
**Issue:** Confusion over which file contains the Playwright state.
**Fact:** The code uses `data/state.json` (defined in `base.py`). Do not look for `storage_state.json` or `auth.json`.
