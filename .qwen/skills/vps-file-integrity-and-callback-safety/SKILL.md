---
name: vps-file-integrity-and-callback-safety
description: Verify file integrity on VPS before deploying fixes; validate Telegram callback_data for typos; never hardcode credentials
source: auto-skill
extracted_at: '2026-06-12T18:00:00.000Z'
---

# VPS File Integrity & Callback Safety

## Problem 1: Working copy differs from HEAD but `git diff` is empty

**Symptom:** On VPS, `grep` shows typo in callback_data (e.g., `low_mileaage`, `commeent`), but `git diff` returns empty and `git reset --hard origin/main` doesn't fix it.

**Root cause:** File on disk was modified AFTER the commit but NOT staged. Git sees it as "clean" because no tracked changes were made since last commit, but the file content differs from HEAD.

**Diagnosis:**
```bash
# Compare hashes
git hash-object ris_reason_keyboard.py        # working copy
git hash-object HEAD:ris_reason_keyboard.py   # committed version

# If hashes differ but git diff is empty:
md5sum ris_reason_keyboard.py
git show HEAD:ris_reason_keyboard.py | md5sum

# Force restore from commit
git checkout HEAD -- ris_reason_keyboard.py
```

**Fix:**
```bash
# Always use checkout to restore, not just reset
git checkout HEAD -- <file>

# Verify
git hash-object <file>
git hash-object HEAD:<file>
# Must be identical
```

## Problem 2: Telegram callback_data typos break reactions

**Symptom:** Manager clicks reaction button (👀/🤔/⏭) then selects a reason — nothing happens or error in logs.

**Root cause:** Doubled letters in callback_data strings. Example:
```python
# WRONG — these will NEVER match expected reason codes
callback_data="reason:low_mileaage"     # should be: low_mileage
callback_data="reason:liquid_moodel"    # should be: liquid_model
callback_data="reason:commeent"         # should be: comment
callback_data="reason:high_mileagge"    # should be: high_mileage
callback_data="reason:many_owneers"     # should be: many_owners
callback_data="reason:too_expensiive"   # should be: too_expensive
callback_data="reason:tooo_mileage"     # should be: too_mileage
callback_data="reason:bad_condiition"   # should be: bad_condition
callback_data="reason:good_conndition"  # should be: good_condition
callback_data="reason:good_histoory"    # should be: good_history
callback_data="reason:few_ownerss"      # should be: few_owners
callback_data="reason:good_regionn"     # should be: good_region
callback_data="reason:historyy_questions" # should be: history_questions
callback_data="reason:bad_colorr"       # should be: bad_color
callback_data="reason:bad__modification" # should be: bad_modification
callback_data="reason:bad_regioon"      # should be: bad_region
callback_data="reason:neeed_more_info"  # should be: need_more_info
callback_data="reason:not_my_modell"    # should be: not_my_model
callback_data="reason:not_my_segmment"  # should be: not_my_segment

# CORRECT — single letters only
callback_data="reason:low_mileage"
callback_data="reason:liquid_model"
# etc.
```

**Pre-deploy validation script:**
```python
import sys
sys.path.insert(0, '.')
from ris_reason_keyboard import MAIN_REASONS, EXTRA_REASONS

# Known valid reason codes
VALID_CODES = {
    "good_price", "good_condition", "low_mileage", "few_owners",
    "good_history", "good_equipment", "liquid_model", "good_region",
    "review_other", "high_price", "high_mileage", "many_owners",
    "bad_color", "poor_equipment", "history_questions",
    "bad_modification", "bad_region", "need_more_info", "think_other",
    "not_my_model", "not_my_segment", "too_expensive", "too_mileage",
    "bad_condition", "legal_risk", "illiquid", "skip_other",
    "comment",
}

errors = []
for action, rows in {**MAIN_REASONS, **EXTRA_REASONS}.items():
    for row in rows:
        for btn in row:
            cd = btn.callback_data
            if cd.startswith("reason:"):
                code = cd.split(":", 1)[1]
                if code not in VALID_CODES:
                    errors.append(f"  INVALID: {cd} (action={action})")

if errors:
    print("ERRORS found:")
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print("All callback_data codes are valid")
```

## Problem 3: 409 Conflict from duplicate bot processes

**Symptom:** Logs filled with `telegram.error.Conflict: terminated by other getUpdates request`

**Root cause:** Multiple bot processes calling `run_polling()` simultaneously. Common when:
- `setsid ... &` creates both bash wrapper + python child
- Previous process wasn't killed before starting new one
- Cron restarts while old instance still running

**Diagnosis:**
```bash
# Count actual python processes (exclude bash wrappers)
ps aux | grep telegram_feedback_bot | grep -v grep
ps aux | grep telegram_feedback_bot | grep -v grep | grep python | wc -l
```

**Expected:** Exactly 1 python process per bot.

**Fix:** See `vps-bot-troubleshooting` skill for correct bot restart procedure.

## Security: Never hardcode credentials

**NEVER** put passwords, tokens, or secrets in deploy/debug scripts:
- No `PASSWORD = "..."` in any `.py` file
- No hardcoded SSH keys
- No API tokens in scripts

**Use environment variables:**
```python
import os
PASSWORD = os.environ.get("VPS_PASSWORD")
if not PASSWORD:
    print("Set VPS_PASSWORD environment variable")
    sys.exit(1)
```

**Or prompt at runtime:**
```python
import getpass
PASSWORD = getpass.getpass("VPS password: ")
```

**After any debugging session with credentials:**
1. Change the password/rotate the token
2. Delete temporary debug scripts
3. Never commit scripts with secrets

## How to apply

When deploying fixes to VPS:

1. **Validate locally first** — run callback_data validation script
2. **Commit and push** — ensure fix is in git
3. **On VPS: verify file integrity** — compare `git hash-object` before and after `git reset`
4. **Validate on VPS** — grep for known typos in the deployed file
5. **Only then restart** — kill duplicates, start single process
6. **Verify** — check logs for clean startup, no Conflict errors
