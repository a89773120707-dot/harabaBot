---
name: vps-bot-troubleshooting
description: Diagnostic workflow for VPS Telegram bot issues (Conflict errors, duplicate processes, sync problems) — diagnose before acting
source: auto-skill
extracted_at: '2026-06-12T14:00:00.000Z'
---

# VPS Bot Troubleshooting — Diagnose Before Acting

## Rule: NEVER kill/restart/deploy before diagnosis

When a VPS bot issue is reported (Conflict errors, duplicate processes, sync problems), **always run full diagnostics first**. Do NOT kill processes, restart services, or deploy code until you know the root cause.

## Why

During troubleshooting of admin_bot / feedback_bot on VPS, the AI cycled through multiple incorrect theories (nohup → bash wrapper → subprocess.Popen → fork → cron → systemd respawn), killing processes and restarting repeatedly. The actual situation was:

- Only 1 process per bot was running
- Tokens were unique
- Conflict error was from an old appended log line
- The "problem" was already resolved

Treating symptoms instead of diagnosing caused unnecessary downtime and confusion.

## Diagnostic Workflow (7 Blocks)

Execute these in order on the VPS. **No kill, no restart, no deploy.**

### Block 1 — Process Inventory

```bash
ps -ef | grep admin_bot | grep -v grep
ps -ef | grep telegram_feedback_bot | grep -v grep
pgrep -af admin_bot
pgrep -af telegram_feedback_bot
```

Record: PID, PPID, CMD for each process.

### Block 2 — systemd Services

```bash
systemctl --user status haraba-admin-bot 2>/dev/null
systemctl --user status haraba-feedback-bot 2>/dev/null
sudo systemctl status haraba-admin-bot 2>/dev/null
sudo systemctl status haraba-feedback-bot 2>/dev/null
systemctl --user is-enabled haraba-admin-bot 2>/dev/null
systemctl --user is-enabled haraba-feedback-bot 2>/dev/null
```

Record: service exists (yes/no), enabled (yes/no), running (yes/no).

### Block 3 — Parent Process Tree

```bash
pstree -sp <PID>    # for each bot PID
# OR fallback:
ps -fp <PID>
ps -fp <PPID>
```

Determine: was the bot started by systemd, cron, bash, or manual?

### Block 4 — Token Check

```bash
grep BOT_TOKEN .env
```

**Critical:** Verify each bot uses a UNIQUE token. Conflict errors are often caused by two bots sharing the same TELEGRAM_BOT_TOKEN.

Output: mask values, just confirm uniqueness.

### Block 5 — Polling Locations

```bash
grep -rn 'run_polling' admin_bot/ telegram_feedback_bot.py
grep -rn 'start_polling' admin_bot/ telegram_feedback_bot.py
```

Each bot should call polling exactly once, in its own entry point.

### Block 6 — Webhook Check

```bash
grep -rn 'webhook\|set_webhook\|getUpdates' admin_bot/ telegram_feedback_bot.py
```

If webhook is configured somewhere, it will conflict with polling.

### Block 7 — Log Freshness Check

```bash
# Check if error is current or stale
tail -5 logs/admin_bot.log
# If using append (>>), old errors persist
# Check timestamp of the error vs current time
```

**Common trap:** Logs accumulated via `>>` preserve old Conflict errors. A Conflict in the log doesn't mean Conflict is happening now.

## Decision Matrix

After diagnostics, decide:

| Finding | Action |
|---------|--------|
| 1 admin + 1 feedback, tokens unique, no webhook | **No action needed** — error was stale |
| 2+ of same bot | Kill ONLY duplicates (keep oldest PID), find respawn source |
| Shared token between bots | Fix .env — assign unique tokens |
| Webhook + polling conflict | Disable one |
| systemd respawn killing bots | `systemctl --user disable` the service first |
| Bot process not running | Start fresh, then verify only 1 instance |

## How to apply

1. Run all 7 blocks, collect facts into a summary table
2. Present findings to user BEFORE proposing any action
3. Only proceed with fix if the diagnostic evidence supports it
4. After any fix, re-run Block 1 to verify the change

## Anti-patterns (DO NOT DO)

- ❌ `kill -9 $(ps aux | grep python | ...)` — kills ALL python processes including cron, pipeline, diagnostic scripts
- ❌ Restart both bots "just in case" — creates new Conflict from two instances starting simultaneously
- ❌ Append to logs (`>>`) when troubleshooting — old errors confuse diagnosis
- ❌ Assume Conflict = duplicate processes — could be shared token, webhook, or stale log
- ❌ Cycle through theories without verifying — test one hypothesis at a time
- ❌ Use `nohup ... &` through SSH to start bots — creates bash wrapper process that forks a duplicate python process, causing Conflict errors
- ❌ Use `setsid ... &` without checking for existing instances — can create additional duplicates

## Starting Bots on VPS — Correct Approach

When starting bot processes on VPS, avoid creating duplicate instances:

```bash
# WRONG — nohup creates bash wrapper + python child = 2 processes
nohup .venv/bin/python -m admin_bot.admin_bot > logs/admin_bot.log 2>&1 &

# BETTER — direct execution (but still check for existing)
.venv/bin/python -m admin_bot.admin_bot >> logs/admin_bot.log 2>&1 &

# ALWAYS — check before starting
pgrep -af admin_bot.admin_bot && echo "Already running" || (.venv/bin/python -m admin_bot.admin_bot >> logs/admin_bot.log 2>&1 &)
```

**Why nohup creates duplicates:** When executed via SSH `exec_command()`, `nohup cmd &` creates a bash process that forks the python process. Both appear in `ps aux` as separate processes using the same Telegram token → Conflict error.

## VPS Actual Setup (as of 2026-06-12, updated)

**systemd services DO exist and manage both bots:**
- `haraba-feedback-bot.service` → active (running), PID managed by systemd
- `haraba-admin-bot.service` → active (running), PID managed by systemd

**Service files location:** `/etc/systemd/system/haraba-*.service`

**Check service status:**
```bash
systemctl status haraba-feedback-bot
systemctl status haraba-admin-bot
```

**Restart properly via systemd:**
```bash
sudo systemctl restart haraba-feedback-bot
sudo systemctl restart haraba-admin-bot
```

**Note:** The user has sudo password. If sudo requires password, either:
- Ask user to run the restart command manually
- Use `ssh -t` for interactive sudo prompt

**Pipeline cron:**
```
*/10 * * * * flock -n /tmp/haraba_pipeline.lock /home/haraba/harabaBot_code/run_pipeline_cron.sh >> /home/haraba/harabaBot_code/logs/pipeline_cron.log 2>&1
```

The cron runs `run_daily_pipeline.py --send` which does NOT start the bot — it only sends cards via direct HTTP calls (no polling).

## Migration Gotcha

After `git pull` with schema changes (e.g., `ALTER TABLE ADD COLUMN`):
- **Running bot process has OLD `init_db()` in memory** — migration hasn't run
- Must execute `init_db()` with new code: `.venv/bin/python -c "from feedback_store import init_db; init_db()"`
- Then restart bot for it to use the new schema

## File Integrity Gotcha: `git diff` can be empty but working copy differs from HEAD

**Symptom:** `git diff -- file.py` returns empty, but the file on disk has different content than the committed version (e.g., typos in callback_data).

**Why this happens:** File was modified after commit but changes were never staged. Git's `diff` compares working copy against index (staging area), not HEAD. If the working copy matches the index but the index differs from HEAD, `git diff` shows empty while the file is actually wrong.

**Always verify with:**
```bash
# Compare hashes — these MUST match
git hash-object file.py        # working copy hash
git hash-object HEAD:file.py   # committed hash

# If different, force restore:
git checkout HEAD -- file.py

# Verify restored:
git hash-object file.py
git hash-object HEAD:file.py
# Must now be identical
```

**Add this to any VPS deploy workflow:** After `git reset --hard origin/main`, always run `git hash-object` checks on critical files to confirm they match HEAD.

## Security: Never hardcode credentials in deploy scripts

Deploy/debug scripts MUST NOT contain passwords, tokens, or secrets:
- No `PASSWORD = "..."` in `.py` files
- Use environment variables or `getpass` prompt
- After debugging with credentials: change password, delete temp scripts, rotate tokens
- See `vps-file-integrity-and-callback-safety` skill for full security guidelines
