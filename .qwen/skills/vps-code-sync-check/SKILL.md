---
name: vps-code-sync-check
description: Always check VPS git status before diagnosing issues — stale code on VPS is the #1 cause of "changes not taking effect" bugs
source: auto-skill
extracted_at: '2026-06-12T14:20:00.000Z'
---

# VPS Code Sync Check — Always Verify Git Status First

## Rule

Before any VPS troubleshooting involving **behaviour that doesn't match local code**, always check if the VPS is on the same git commit as local. Stale code on VPS is the most common cause of "fix doesn't work" issues.

## Why

During the telegram_users single-source-of-truth fix:
- Local code was updated (commit `a238e27`)
- Code was pushed to GitHub
- VPS was never `git pull`-ed — still on commit `ba88ea3` (5 commits behind)
- VPS ran **old** `feedback_store.py` that wrote to `telegram_recipients` instead of `telegram_users`
- VPS ran **old** `admin_bot` that used legacy recipient management
- All manual SQL fixes (`UPDATE telegram_users SET status=...`) were being overwritten because the running code used a different table
- The AI spent hours diagnosing "duplicate processes" and "bash wrappers" when the real issue was stale code

## Pre-Diagnostic Check

Before running any diagnostic blocks, always run this FIRST:

```bash
# On VPS:
cd /home/haraba/harabaBot_code
git log --oneline -3
git status
git fetch origin
git log --oneline origin/main -3
```

**Compare:**
- VPS current HEAD vs `origin/main` HEAD
- If `git status` says "behind origin/main by N commits" → `git pull` is the fix

## Checklist

When a user reports "X doesn't work" or "status reverts after restart":

1. **Is VPS on the same commit as local?**
   ```bash
   git status  # look for "behind origin/main by N commits"
   ```

2. **Is the file actually updated?**
   ```bash
   git diff <file>  # shows uncommitted local changes
   git show HEAD:<file> | grep -A 5 '<function_name>'  # shows deployed code
   ```

3. **Are the running processes using the new code?**
   - If you just did `git pull` but didn't restart → processes use OLD code
   - If you restarted but git pull failed → processes use OLD code

4. **Is there a .venv or cached .pyc?**
   ```bash
   python -c "import module_name; print(module_name.__file__)"
   ```

## Common Scenarios

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Code change doesn't take effect | VPS behind origin/main | `git pull` + restart |
| Manual SQL fix reverts | Old code overwrites on startup/restart | `git pull` first |
| "Working locally but not on VPS" | Different git commits | Compare `git log` local vs VPS |
| File doesn't exist on VPS | New file not in old commit | `git pull` pulls new files too |
| Function behaves differently | Old version of function | `git diff` to see what changed |

## How to apply

1. **ALWAYS** start with `git status` and `git log --oneline` on VPS
2. If behind → `git pull` before any other action
3. After `git pull` → restart affected processes
4. After restart → verify with the same diagnostic that identified the issue

### When git pull fails due to local changes

If `git pull` says "Your local changes to the following files would be overwritten by merge":

```bash
# Option 1: Stash local changes (preserves them)
git stash
git pull origin main
git stash pop  # may have conflicts, resolve manually

# Option 2: Discard local changes (use if local changes are unwanted)
git reset --hard origin/main

# After either option, verify:
git log --oneline -1   # should match origin/main HEAD
```

**Why this happens:** VPS often has uncommitted local modifications (debug output, local testing changes) that conflict with incoming commits. `git pull --ff-only` and normal `git pull` both fail when there are overlapping file changes.

**Anti-pattern:** Running `git pull` and assuming it succeeded without checking the output. Always verify HEAD matches origin/main after pull.

## Anti-patterns

- ❌ Running SQL fixes when old code will overwrite them on restart
- ❌ Diagnosing "duplicate processes" when the real issue is stale code
- ❌ Manually editing files on VPS instead of using git
- ❌ Assuming `git pull` succeeded without checking output
- ❌ Restarting processes before `git pull` completes
- ❌ Pushing to GitHub but not pulling on VPS (push ≠ deploy)
