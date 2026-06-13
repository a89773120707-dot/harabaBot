---
name: haraba-mini-audit-procedure
description: Systematic read-only audit procedure for Haraba Mini project — 6-stage documentation workflow covering snapshot, inventory, database, managers, reactions, architecture, and Telegram
source: auto-skill
extracted_at: '2026-06-13T16:44:38.560Z'
---

# Haraba Mini Audit Procedure

## Purpose

Systematically audit the Haraba Mini project in read-only mode to understand its actual state, identify risks, and document the architecture — without modifying any code, database, configuration, or git state.

## Mode Rules

- ❌ Never modify code, database, migrations, configs, .env, systemd, or cron
- ❌ Never git commit/push/merge/rebase
- ❌ Never deploy to VPS or restart services
- ✅ Only read files, run read-only queries, create documentation in `docs/`
- Every claim must be proven with: file path, line number, command output, DB schema, or git commit
- No proofs → write "ТРЕБУЕТ ПРОВЕРКИ"
- Object not found → write "НЕ НАЙДЕНО"
- Never invent architecture — describe only what actually exists

## 6-Stage Audit Workflow

### Stage 0: Snapshot (`docs/AUDIT_SNAPSHOT.md`)

**Goal:** Capture current project state.

**Commands (read-only):**
```bash
pwd
git status
git branch -a
git log --oneline -50
find . -maxdepth 4 -type f | sort
find . -maxdepth 3 -type d | sort
python --version
pip freeze | grep -i "playwright\|telegram\|yaml"
find . -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3"
```

**Document:**
- Date, current directory, git status, active branch
- Last 50 commits
- Directory structure
- Found databases
- systemd/cron indicators (if accessible)
- Items requiring verification

### Stage 1: Inventory (`docs/PROJECT_INVENTORY.md`)

**Goal:** Understand actual project structure.

**For each important file, determine:**
- Path, purpose, who calls it, what it calls
- Used currently: YES/NO
- Proof of usage (grep for imports)
- Criticality: HIGH / MEDIUM / LOW

**Special attention to:**
- Entry points: `main()`, `if __name__ == "__main__"`
- Telegram modules (sender, feedback, formatter)
- Database modules (feedback_store, repositories)
- Scrapers (session_manager, mobile_first_page_sampler)
- Scoring modules (price_scorer, mileage_scorer, etc.)
- Config files (YAML)

**Classify untracked files into 5 categories:**
1. Temporary scripts (block_*.py, vps_*.py)
2. Test files (test_*.py)
3. Debug files (debug_*.py, check_*.py)
4. Potentially useful
5. Unused garbage

**Output:** TOP-20 critical files, TOP-10 risks, items requiring verification.

### Stage 2: Database Audit (`docs/DATABASE.md`)

**Goal:** Understand actual SQLite database state.

**For each .db file:**
- Path, size, modification date
- Tables, row counts per table
- Used by code: YES/NO (grep for path references)

**For primary database (feedback.db):**
- Full schema: all tables, columns, PKs, indexes, UNIQUE constraints, FKs
- Row counts per table
- Which tables actually have data vs empty

**Deep analysis of key tables:**

**sent_ads:**
- All fields present/missing
- UNIQUE constraints, PKs
- Dedup logic (global or per-manager)
- Sample rows with all fields
- Distribution: unique card_ids, chat_ids, config_names
- Config_name status (exists in schema? populated?)

**feedback:**
- All fields present/missing
- Action distribution
- Telegram fields (chat_id, user_id, username, role)
- config_name presence
- Sample rows

**telegram_users:**
- All users, roles, statuses
- Active vs paused vs pending vs disabled

**telegram_recipients (legacy):**
- Compare with telegram_users for sync issues

**Output:** Legacy databases identified, risks, items requiring VPS verification.

### Stage 3: Managers/Recipients Audit (`docs/MANAGERS.md`)

**Goal:** Understand manager storage, get_enabled_recipients(), config_name status.

**Find all code references to:**
- manager, managers, recipient, recipients, chat_id
- telegram_users, get_enabled_recipients
- config_name, reviewer_role, enabled

**Answer:**
1. Where are managers stored?
2. How are recipients created/enabled/disabled?
3. What does get_enabled_recipients() return? (fields, filters)
4. Is there a known bug? Fixed locally? Deployed to VPS?
5. Where is config_name in schema vs data?
6. Why are sent_ads config_name values NULL?
7. Is there manager → config mapping?
8. What's needed for per-manager configs?

**Document current flow:** collect → enrich → audit → send → feedback, noting where data is lost.

### Stage 4: Reactions/Feedback Audit (`docs/REACTIONS.md`)

**Goal:** Understand full reaction lifecycle from button click to DB save.

**Build callback flow:**
1. Card sent to Telegram → inline buttons created
2. User clicks → callback_query sent
3. Callback parsed (action:card_id)
4. card_data looked up
5. pending_feedback stored
6. Reason keyboard shown
7. Reason selected
8. feedback_card dict built
9. save_feedback() → INSERT
10. save_reaction_detail() → INSERT

**For each step document:**
- File, function, input/output
- Fields present, fields lost

**Identify where config_name is lost (typically 3+ points).**

**Answer:**
- Can we identify which manager reacted? (YES: telegram_chat_id, telegram_user_id)
- Can we identify which config? (NO: config_name not in feedback)
- What minimal changes needed for Config Intelligence?

### Stage 5: Architecture (`docs/ARCHITECTURE.md`)

**Goal:** Build complete ASCII architecture diagram with actual file/function names.

**Document:**
- All entry points (3 services: pipeline, feedback bot, admin bot)
- Full pipeline chain with field-level detail
- card_id and stable_car_key lifecycle
- config_name flow table (step → file → present? → status)
- Telegram send flow
- Feedback flow
- Database write points (who writes to which table)
- Data loss points

**Risk assessment:**
- What changes are dangerous?
- What needs verification before changes?

### Stage 6: Telegram/Admin Bot Audit (`docs/TELEGRAM.md`)

**Goal:** Document all Telegram-related modules, commands, callbacks, roles.

**For each module:**
- Path, purpose, launch mode (service vs import)
- Commands/handlers
- DB tables used

**Document:**
- All callback_data formats
- 64-byte limit risk assessment
- Error handling and retry logic
- Role/access model (owner/admin/manager/viewer)
- Admin bot capabilities (what works, what doesn't)

## Output Documents

All created in `docs/` directory:

| File | Stage | Content |
|------|-------|---------|
| `AUDIT_SNAPSHOT.md` | 0 | Current project state, git, files, DBs |
| `PROJECT_INVENTORY.md` | 1 | Full module inventory, criticality, risks |
| `DATABASE.md` | 2 | Full DB schema analysis, data state |
| `MANAGERS.md` | 3 | Manager storage, recipients, config_name |
| `REACTIONS.md` | 4 | Reaction lifecycle, callback flow, gaps |
| `ARCHITECTURE.md` | 5 | ASCII architecture, data flow, risks |
| `TELEGRAM.md` | 6 | Telegram modules, callbacks, roles, admin bot |

## Verification Checklist

After completing all stages, maintain a consolidated "ТРЕБУЕТ ПРОВЕРКИ" list across all documents. Typical items:

- VPS code vs local code (git status mismatch)
- VPS database state (different row counts)
- Deployed bug fixes (local fixed, VPS unknown)
- systemd service status
- cron configuration
- .env values on VPS

## Key Patterns to Look For

1. **Modified but uncommitted files** — critical code changes not in git
2. **Schema vs data mismatch** — column exists but all NULL
3. **Data loss points** — fields that exist in one step but disappear in the next
4. **Legacy databases** — .db files that are empty or unused
5. **Untracked code** — entire directories (like `app/`) not in git
6. **Hardcoded values** — OWNER_ID, URLs, paths scattered across files
7. **Missing FK constraints** — text-based joins instead of proper relationships
