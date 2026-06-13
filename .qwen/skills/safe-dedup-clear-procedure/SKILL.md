---
name: safe-dedup-clear-procedure
description: Safely clear sent_ads dedup with backup, verification, and limited test send before full pipeline resumes
source: auto-skill
extracted_at: '2026-06-12T19:30:00.000Z'
---

# Safe Dedup Clear Procedure

## When to Use

When dedup has accumulated stale records and you need to test that the pipeline sends correctly again, but you must:
- Not lose reaction data (feedback, reaction_details)
- Not spam all managers with a full resend
- Have a rollback option if something goes wrong

## The Rule

**NEVER** delete sent_ads without:
1. Backup first
2. Verify other tables untouched
3. Test with `--limit 3` before full run
4. Check results before deciding to keep or restore

## Procedure

### Step 1: Backup

```bash
cp results/feedback.db results/feedback_before_clear_dedup_$(date +%Y%m%d_%H%M).db
```

### Step 2: Count Before

```sql
SELECT COUNT(*) FROM sent_ads;
-- Example: 350
```

### Step 3: Clear sent_ads ONLY

```python
import sqlite3
conn = sqlite3.connect('results/feedback.db')
conn.execute('DELETE FROM sent_ads')
conn.commit()
conn.close()
```

### Step 4: Verify Other Tables Untouched

```sql
SELECT COUNT(*) FROM feedback;           -- must be same as before
SELECT COUNT(*) FROM reaction_details;   -- must be same as before
SELECT COUNT(*) FROM telegram_users;     -- must be same as before
```

### Step 5: Confirm sent_ads Empty

```sql
SELECT COUNT(*) FROM sent_ads;
-- Expected: 0
```

### Step 6: Test Send with Limit

```bash
python telegram_sender.py --send --limit 3
```

This sends only 3 cards (not all candidates) to verify:
- Sending works (no HTTP errors)
- All active recipients receive
- Dedup records are created correctly

### Step 7: Check Results

```sql
SELECT chat_id, COUNT(*), MAX(first_sent_at)
FROM sent_ads
GROUP BY chat_id;
```

Expected: 3 cards × N recipients = 3×N rows distributed across all active chat_ids.

### Step 8: Check Sender Report

```bash
cat results/telegram_sender_report.yaml
```

Check:
- `sent: N` (should be 3 × number of recipients)
- `failed: 0`
- `skipped_duplicate: 0` (fresh clear, no dups yet)

### Step 9: Decide

**If everything OK:**
- Leave dedup cleared
- Next cron run will send fresh cards normally

**If error or avalanche:**
```bash
cp results/feedback_before_clear_dedup_YYYYMMDD_HHMM.db results/feedback.db
```

## What NOT to Clear

| Table | Clear? | Why |
|-------|--------|-----|
| `sent_ads` | ✅ YES | This is the dedup table — safe to clear with backup |
| `feedback` | ❌ NO | Contains all manager reactions — irreplaceable data |
| `reaction_details` | ❌ NO | Contains reason codes for reactions — needed for analytics |
| `telegram_users` | ❌ NO | User management — would lose all recipient data |
| `telegram_recipients` | ❌ NO | Legacy table — harmless to keep |

## On VPS via Paramiko

When doing this remotely:

```python
import paramiko, shutil
from datetime import datetime

ssh = paramiko.SSHClient()
ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=15)

REMOTE = '/home/haraba/harabaBot_code'
VENV = REMOTE + '/.venv/bin/python'
TS = datetime.now().strftime('%Y%m%d_%H%M')
BACKUP = f'{REMOTE}/results/feedback_before_clear_dedup_{TS}.db'

# Step 1: Backup
run(f'cp {REMOTE}/results/feedback.db {BACKUP}')

# Step 2-5: Clear via Python script (upload, run)
# Write clear script locally, upload via SFTP, execute

# Step 6: Test send
run(f'cd {REMOTE} && {VENV} telegram_sender.py --send --limit 3', timeout=120)

# Step 7: Check
run(f'cd {REMOTE} && sqlite3 results/feedback.db "SELECT chat_id, COUNT(*), MAX(first_sent_at) FROM sent_ads GROUP BY chat_id;"')
```

## Common Pitfall

**`limit` applies to candidates, not recipients.**
- `--limit 3` means "take first 3 candidate cards"
- Each card is sent to ALL active recipients
- So 3 cards × 6 recipients = 18 messages, not 3

If you want to limit to 1 recipient, you must modify the recipients list, not use `--limit`.
