---
name: haraba-server-deployment
description: Procedure for deploying Haraba Mini pipeline and feedback bot to a Linux server (VPS)
source: auto-skill
extracted_at: '2026-06-09T16:50:00.000Z'
---

# Haraba Mini — Server Deployment Procedure

## Prerequisites

- Linux server (Ubuntu 20.04+ recommended)
- Python 3.10+ installed
- SSH access
- Haraba Mini project files ready for transfer

## Step 1: Prepare Files (Local Machine)

Create archive with these files:

**Required:**
```
*.py                    # All Python scripts
config/*.yaml           # Search configurations
data/state.json         # Desktop Haraba session (CRITICAL)
data/state_mobile.json  # Mobile session (if exists)
.env                    # Telegram bot tokens (SECRET)
results/feedback.db     # Feedback database (DO NOT LOSE)
requirements.txt        # Python dependencies
```

**Verification script:**
```bash
python clear_and_check.py
# Should show:
# Feedback count: 0
# Sent ads count: 0
# Recipients: owner + manager (enabled=1)
```

## Step 2: Server Setup (Remote)

```bash
# SSH to server
ssh user@server_ip

# Create project directory
mkdir -p /opt/haraba-mini
mkdir -p /opt/haraba-mini/logs

# Upload files (from local machine)
scp -r haraba_deploy/* user@server_ip:/opt/haraba-mini/

# Or use rsync for incremental
rsync -avz --exclude='__pycache__' ./ user@server_ip:/opt/haraba-mini/
```

## Step 3: Install Dependencies

```bash
cd /opt/haraba-mini

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt

# Install Playwright browsers (headless)
playwright install chromium
playwright install-deps  # System dependencies for Linux
```

## Step 4: Verify Session

Create `check_server_session.py`:

```python
from playwright.sync_api import sync_playwright
from pathlib import Path

STATE = Path("data/state.json")

def check():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(storage_state=str(STATE))
    page = context.new_page()
    
    try:
        page.goto("https://haraba.ru/search", wait_until="domcontentloaded", timeout=15000)
        body = page.inner_text("body", timeout=5000)
        
        if "войти" in body.lower() or "логин" in body.lower():
            print("FAIL: Session expired, need re-auth")
            return False
        else:
            print("OK: Session valid")
            return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        browser.close()
        pw.stop()

if __name__ == "__main__":
    check()
```

Run:
```bash
python check_server_session.py
```

Expected output: `OK: Session valid`

## Step 5: Setup Bot as Systemd Service

Create `/etc/systemd/system/haraba-bot.service`:

```ini
[Unit]
Description=Haraba Telegram Feedback Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/haraba-mini
ExecStart=/opt/haraba-mini/venv/bin/python telegram_feedback_bot.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/haraba-mini/logs/bot.log
StandardError=append:/opt/haraba-mini/logs/bot-error.log

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

Verify bot works:
```bash
# Send /help to bot from Telegram
# Should receive command list
```

## Step 6: Setup Pipeline Cron Job

Create `/opt/haraba-mini/run_pipeline.sh`:

```bash
#!/bin/bash
cd /opt/haraba-mini
source venv/bin/activate
python run_daily_pipeline.py --send --skip-collect >> logs/pipeline.log 2>&1
```

Make executable:
```bash
chmod +x /opt/haraba-mini/run_pipeline.sh
```

Add to crontab (every 4 hours):
```bash
crontab -e
```

Add line:
```cron
0 */4 * * * /opt/haraba-mini/run_pipeline.sh
```

## Step 7: Final QA

Run these tests in order:

### Test 1: Dry-run
```bash
python run_daily_pipeline.py --dry-run --skip-collect
```
Expected: Report created, no sends.

### Test 2: Single send
```bash
python run_daily_pipeline.py --send --limit 1 --skip-collect
```
Expected:
- Card sent to Owner
- Card sent to Manager
- Log shows `Sent: 2`

### Test 3: Dedup
```bash
python run_daily_pipeline.py --send --limit 1 --skip-collect
```
Expected:
- Log shows `skipped_duplicate` for both recipients
- `Sent: 0`

### Test 4: Service survival
```bash
sudo reboot
# After reboot
sudo systemctl status haraba-bot
```
Expected: `Active: active (running)`

## Troubleshooting

**Bot not responding:**
```bash
sudo systemctl status haraba-bot
sudo journalctl -u haraba-bot -n 50
```

**Session expired:**
1. Re-auth on local machine with `login_wait.py`
2. Upload new `data/state.json` to server
3. Restart bot: `sudo systemctl restart haraba-bot`

**Playwright fails on Linux:**
```bash
playwright install-deps
# Or manually:
sudo apt install libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 libxshmfence1
```

**Database locked:**
```bash
# Check no other process holds lock
lsof results/feedback.db
```

## Monitoring

Check logs:
```bash
tail -f /opt/haraba-mini/logs/bot.log
tail -f /opt/haraba-mini/logs/pipeline.log
```

Check feedback count:
```bash
python -c "import sqlite3; c=sqlite3.connect('results/feedback.db').cursor(); c.execute('SELECT COUNT(*) FROM feedback'); print(f'Reactions: {c.fetchone()[0]}')"
```
