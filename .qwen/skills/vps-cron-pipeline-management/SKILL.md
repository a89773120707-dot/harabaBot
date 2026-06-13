---
name: vps-cron-pipeline-management
description: Diagnosing and updating VPS cron for pipeline runs — always check timing, add flock, verify before changing
source: auto-skill
extracted_at: '2026-06-12T15:00:00.000Z'
---

# VPS Cron Pipeline Management

## Rule: Always diagnose before changing cron interval

When changing pipeline cron frequency, **always check current state first**: current interval, average runtime, lock file protection, and running processes.

## Pre-Change Diagnosis

Before modifying cron, gather these facts:

```bash
# 1. Current cron
crontab -l

# 2. Average runtime from logs
tail -100 logs/pipeline_cron.log | grep -E 'START:|END:'

# 3. Check for lock file protection
cat run_pipeline_cron.sh
grep -n 'lock\|flock\|PID\|single' run_daily_pipeline.py

# 4. Check for stale processes
ps aux | grep run_daily_pipeline | grep -v grep
```

## Key Findings from Experience

1. **Current cron was `0 */1 * * *` (every hour)** — not `*/15` as expected
2. **No flock/lock file** — parallel runs were possible if pipeline took > interval
3. **Pipeline runtime: ~5 minutes** — safe for 10-minute interval but not for 1-minute
4. **Log file grows large** (3263+ lines) — use `tail` not `cat`

## Safe Cron Update Pattern

When changing cron interval, always add `flock` to prevent parallel runs:

```bash
# Before (no protection):
*/15 * * * * /home/haraba/harabaBot_code/run_pipeline_cron.sh >> logs/pipeline_cron.log 2>&1

# After (with flock protection):
*/10 * * * * flock -n /tmp/haraba_pipeline.lock /home/haraba/harabaBot_code/run_pipeline_cron.sh >> /home/haraba/harabaBot_code/logs/pipeline_cron.log 2>&1
```

### What flock does:
- `-n` (non-blocking): if lock is held → skip this run, don't wait
- `/tmp/haraba_pipeline.lock`: lock file path
- If previous run is still going → new run is silently skipped
- Lock auto-released when process exits

### Installing new crontab via SSH:

```bash
# Write to temp file and install
cat << "CRON_EOF" | crontab -
# Haraba Mini pipeline
*/10 * * * * flock -n /tmp/haraba_pipeline.lock /home/haraba/harabaBot_code/run_pipeline_cron.sh >> /home/haraba/harabaBot_code/logs/pipeline_cron.log 2>&1
CRON_EOF

# Verify
crontab -l
```

## Post-Change Verification

1. **Confirm crontab:**
   ```bash
   crontab -l
   ```

2. **Wait for next scheduled run** — check log for new START marker

3. **Verify no parallel processes:**
   ```bash
   ps aux | grep run_daily_pipeline | grep -v grep
   # Should be 0 or 1 process, never 2+
   ```

4. **Check lock file released:**
   ```bash
   fuser /tmp/haraba_pipeline.lock 2>/dev/null
   # Should return nothing after pipeline completes
   ```

## Cron Timing Reference

| Interval | Cron expression | Risk level |
|----------|----------------|------------|
| Every minute | `* * * * *` | ❌ Too frequent — pipeline takes ~5 min |
| Every 5 min | `*/5 * * * *` | ⚠️ Borderline — flock will skip most runs |
| Every 10 min | `*/10 * * * *` | ✅ Safe with flock |
| Every 15 min | `*/15 * * * *` | ✅ Safe |
| Every hour | `0 * * * *` | ✅ Safe |

## Anti-patterns

- ❌ Changing cron without adding flock — parallel runs will corrupt DB
- ❌ Setting interval shorter than average pipeline runtime
- ❌ Assuming cron is already set correctly — always check with `crontab -l`
- ❌ Not backing up old crontab before changing (`crontab -l > /tmp/crontab_backup.txt`)
- ❌ Forgetting to verify after change — check that next run actually happens