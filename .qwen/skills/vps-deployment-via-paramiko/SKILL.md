---
name: vps-deployment-via-paramiko
description: Deploy code to VPS via SSH using paramiko when no SSH keys or sshpass are available
source: auto-skill
extracted_at: '2026-06-11T17:42:00.000Z'
---

## When to use

When you need to deploy code to a VPS (e.g. `haraba@109.238.95.141`) and:
- No SSH keys are set up
- `sshpass` is not installed on the local machine
- You have the SSH password
- The project uses a Python virtual environment on the server

## Approach

Use Python `paramiko` library for SSH operations.

### Basic connection

```python
import paramiko
HOST = "109.238.95.141"
USER = "haraba"
PASSWORD = "271288"  # Never commit this — delete script after use

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASSWORD, timeout=15)
```

### Running commands

```python
def run(cmd, label=""):
    if label:
        print(f">>> {label}\n$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(out[:5000])
    if err and exit_status != 0:
        print(f"ERR: {err[:500]}")
```

### Uploading files via SFTP

```python
sftp = client.open_sftp()
sftp.put("local_file.py", "/home/haraba/project/remote_file.py")
sftp.close()
```

### Running background processes (critical!)

**DO NOT** use `nohup ... &` directly with `source .venv/bin/activate` — it may not work.
**DO NOT** use `exec` inside `bash -c` — it blocks.

The working approach for services: use a bash script, then run it via nohup:

```python
# Create script
run('cat > /home/haraba/project/start.sh << "EOF"\n#!/bin/bash\ncd /home/haraba/project\nexec .venv/bin/python -m module.name\nEOF', "Create script")
run("chmod +x /home/haraba/project/start.sh", "chmod")

# Run via nohup + bash
run("cd /home/haraba/project && nohup bash start.sh > app.log 2>&1 &", "Start")
```

**Alternative** — direct nohup works if you use the full venv python path:

```python
run("cd /home/haraba/project && nohup /home/haraba/project/.venv/bin/python -m module.name > app.log 2>&1 &")
```

### Sudo commands

**CRITICAL: `sudo` does NOT work with `exec_command()`** — SSH exec_command doesn't provide a TTY, so `sudo` will always fail with "a terminal is required to read the password".

Use `echo 'PASSWORD' | sudo -S` (works in non-interactive context):

```python
run("echo '271288' | sudo -S systemctl restart haraba-bot", "Restart")
```

**BUT:** On this VPS, `sudo` requires a password AND the user `haraba` is NOT in sudoers without password. `echo PASS | sudo -S` DOES work in non-interactive context:

```python
run("echo '271288' | sudo -S systemctl restart haraba-feedback-bot.service", "Restart")
```

**Verified working:** `echo 'PASSWORD' | sudo -S systemctl restart ...` works via paramiko `exec_command()`.

### VPS Actual Structure (as of 2026-06-12)

```
/home/haraba/harabaBot_code/       # project root
/home/haraba/harabaBot_code/.venv/ # Python venv (NOT venv/)
/home/haraba/harabaBot_code/.venv/bin/python -> python3
```

**Bot IS a systemd service.** Two services exist:

```
haraba-feedback-bot.service  → telegram_feedback_bot.py
haraba-admin-bot.service     → admin_bot.admin_bot
```

**Bot startup:** via systemd `ExecStart=/home/haraba/harabaBot_code/.venv/bin/python /home/haraba/harabaBot_code/telegram_feedback_bot.py`

**Restart requires sudo:** `echo 'PASSWORD' | sudo -S systemctl restart haraba-feedback-bot.service`

**Pipeline cron:**
```
*/10 * * * * flock -n /tmp/haraba_pipeline.lock /home/haraba/harabaBot_code/run_pipeline_cron.sh >> logs/pipeline_cron.log 2>&1
```

### Running migrations on VPS

**CRITICAL: `init_db()` is called at module import time** (`feedback_store.py` has `init_db()` at bottom of file). This means:

1. When a process starts, it imports `feedback_store` → `init_db()` runs → schema is locked
2. If you `git pull` new migration code, **running processes still have the OLD schema in memory**
3. **You must run `init_db()` with the NEW code** to apply migrations

After `git pull`, always run:
```python
.venv/bin/python -c "from feedback_store import init_db; init_db(); print('Migration OK')"
```

This ensures the migration (e.g., `ALTER TABLE ADD COLUMN config_name TEXT`) is executed with the new code.

### Deploy workflow (correct order)

1. `git pull` on VPS
2. Run migration: `.venv/bin/python -c "from feedback_store import init_db; init_db()"`
3. Verify migration: check column exists via `PRAGMA table_info(sent_ads)`
4. **Only then** restart bot (if needed — running processes will still use old schema until restart)
5. Wait for next cron run or trigger pipeline manually

Upload migration script, then run via venv python:

```python
upload("migration.py", f"{PROJECT}/migration.py")
run(f"cd {PROJECT} && .venv/bin/python migration.py", "Run migration")
```

If migration creates new tables, always use `CREATE TABLE IF NOT EXISTS` and check column existence before ALTER.

### Security rules

1. **NEVER** commit scripts containing passwords to git
2. **ALWAYS** delete deploy scripts after use: `del deploy_*.py`
3. **ALWAYS** clean up deploy scripts from VPS too
4. Passwords in `.env` are fine (it's in `.gitignore`) but never hardcode in Python files
5. After deployment, remove all temporary deploy scripts from both local and VPS

### Running Python scripts on VPS — three approaches

**Approach 1: Inline python -c** (simple queries only)
```python
run('cd /home/haraba/project && .venv/bin/python -c "import sqlite3; c=sqlite3.connect(\'results/feedback.db\').cursor(); c.execute(\'SELECT COUNT(*) FROM sent_ads\'); print(c.fetchone()[0])"')
```
Works for simple one-liners. Fails with complex quoting.

**Approach 2: Heredoc** (multi-line scripts)
```python
cmd = """cd /home/haraba/project && .venv/bin/python << 'PYEOF'
import sqlite3
conn = sqlite3.connect('results/feedback.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute('SELECT chat_id, COUNT(*) FROM sent_ads GROUP BY chat_id')
for r in c.fetchall():
    print(f'chat={r[0]} count={r[1]}')
conn.close()
PYEOF"""
run(cmd, timeout=30)
```
Works for most cases. May fail with complex string escaping.

**Approach 3: SFTP upload + execute** (reliable for any script)
```python
# Write script locally
with open('check_sent.py', 'w') as f:
    f.write("""import sqlite3
conn = sqlite3.connect('results/feedback.db')
...
""")

# Upload via SFTP
sftp = ssh.open_sftp()
sftp.put('check_sent.py', '/home/haraba/project/check_sent.py')
sftp.close()

# Execute
run('cd /home/haraba/project && .venv/bin/python check_sent.py')
```
**Most reliable approach** — no quoting issues at all. Use when inline/heredoc fail.

### Common pitfalls

- **`ModuleNotFoundError` on server**: The venv `python` works but package not found → use `.venv/bin/pip install <package>` explicitly
- **Background process dies immediately**: Use `nohup bash script.sh &` not `nohup python &` directly, or use full venv path
- **`sudo` prompts for password**: Use `echo 'PASS' | sudo -S cmd`
- **Encoding issues on server**: Use `.decode("utf-8", errors="replace")`
- **`setsid` not available**: Use `nohup bash script.sh &` approach instead
- **`edit_message_text()` with `reply_to_message_id`**: Telegram's `edit_message_text` does NOT accept `reply_to_message_id`. To reply after editing, use `query.message.reply_text(...)` as a separate call
- **`sqlite3.Row` without row_factory**: When using `conn.execute(...).fetchone()`, the result is a tuple, not a dict. Use `row[0]` not `row["max_id"]` unless you explicitly set `conn.row_factory = sqlite3.Row`
- **Feedback bot `telegram_feedback_bot.py`**: `action` column in `feedback` table (not `reaction`), `telegram_user_id` (not `telegram_id`), `first_sent_at` (not `created_at`) in `sent_ads`
