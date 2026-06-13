---
name: diagnosis-first-no-assumptions
description: Systematic debugging methodology: prove before fixing, read-only first, verify all three sources (local/committed/VPS), only commit/push after full audit
source: auto-skill
extracted_at: '2026-06-12T19:00:00.000Z'
---

# Diagnosis First — No Assumptions

## Core Principle

Before fixing ANY problem:

1. **Read-only diagnosis** — only observe, never change
2. **Prove the root cause** — not guess it
3. **Verify all three sources** — local, committed, VPS
4. **Audit before commit** — no partial deployments

## The Three Sources Rule

Always compare:

| Source | Command |
|--------|---------|
| Local working copy | `cat file.py` |
| Local committed | `git show HEAD:file.py` |
| VPS working copy | `ssh cat remote_file.py` |
| VPS committed | `ssh git show HEAD:file.py` |

**Never assume** they're the same. In this session:
- Local working file = clean (no typo in callback_data) ✅
- VPS committed = clean (no typo in callback_data) ✅
- BUT VPS running process had OLD code (before git pull) ❌
- Root cause was NOT typo — it was `ImportError: cannot import name 'needs_comment'`
- The function `needs_comment()` existed locally but was missing on VPS `ris_reason_store.py`

Only by checking journalctl error lines did we find the REAL root cause.

## Diagnosis Block Pattern

For each suspected problem, create a **diagnosis block** (D0, C1, C2, etc.):

```
BLOCK D0 — AUDIT STATE
  Goal: Find real cause without changes
  Forbidden: commit, push, deploy, SCP, kill, restart, edit
  Allowed: read files, logs, DB, processes

BLOCK C1 — PROVE/REFUTE HYPOTHESIS
  Goal: Test specific hypothesis
  Only: grep, ps, SELECT, journalctl
  
BLOCK C2 — DIAGNOSE ROOT CAUSE
  Goal: Find exact source of error
  Only: read logs, check services, verify tokens
```

## Forbidden Before Diagnosis

Until root cause is proven, NEVER:
- `pkill` / `kill -9`
- `git reset --hard`
- `git checkout`
- SCP file copies
- Manual edits on VPS
- Bot restarts
- DB changes

## Proven Diagnosis Flow (from this session)

### Problem: Reaction buttons don't work

**Hypothesis 1:** Typo in callback_data
- ✅ Checked: local working, local HEAD, VPS working, VPS HEAD
- ❌ Result: NO typo found — hypothesis REJECTED

**Hypothesis 2:** 409 Conflict blocking callbacks
- ✅ Checked: all python processes, systemd services, tokens, webhooks
- ✅ Found: was 2 processes, now 1 process via systemd, 200 OK
- ❌ Result: Conflict RESOLVED — not the current cause

**Hypothesis 3:** Callback not reaching bot
- ✅ Checked: journalctl, bot logs, service status
- ✅ Found: callbacks DO reach bot (journalctl shows handler invocation)
- ❌ Result: not a callback delivery issue

**Hypothesis 4:** Handler crashes on import
- ✅ Checked: journalctl error lines
- ✅ Found: `ImportError: cannot import name 'needs_comment'`
- ✅ Confirmed: function exists locally, missing on VPS
- ✅ ROOT CAUSE FOUND

## Audit Checklist Before Fix

Before any commit/push/deploy:

1. **Prove the exact error** — show the traceback, not assumptions
2. **Compare all sources** — local vs committed vs VPS
3. **List ALL differences** — not just the suspected one
4. **Check ALL imports** — will fixing one cause another ImportError?
5. **Show git diff** — what exactly will be committed?
6. **Show git status** — are there unexpected changed files?

## Table Format for Comparison

Always present findings as a table:

```
Function            Local    Committed    VPS Working    VPS HEAD
needs_comment       ✅       ❌           ❌             ❌
save_reaction       ✅       ✅           ✅             ✅
get_last_feedback   ✅       ✅           ✅             ✅
```

## What NOT to Write in Reports

- ❌ "скорее всего" / "возможно" / "наверное"
- ❌ "I think the issue is..."
- ❌ "This should fix it"
- ❌ "Probably caused by..."

## What TO Write

- ✅ "Proven: X equals Y"
- ✅ "Confirmed: function exists locally, missing on VPS"
- ✅ "Rejected: hypothesis Z because grep found 0 matches"
- ✅ "Root cause: ImportError in reason_handler line 358"

## Deploy Only After

1. Diagnosis blocks complete
2. Root cause proven with evidence
3. Fix tested locally
4. Git diff shown and reviewed
5. Commit message clear
6. Push successful
7. VPS verified with `git reset --hard origin/main`
8. Service restarted
9. Real-world test passed (button press → DB record)

## Why This Matters

Without systematic diagnosis:
- You fix symptoms, not causes
- You create new problems while fixing old ones
- Local ≠ GitHub ≠ VPS diverges
- You lose trust in what's actually running

With systematic diagnosis:
- Every conclusion is backed by evidence
- You know exactly what changed and why
- All three sources stay in sync
- You can rollback with confidence
