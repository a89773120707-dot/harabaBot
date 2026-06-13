---
name: project-status-audit
description: Systematic audit of project implementation status vs plans — directory scan, code review, git log, database state, plan comparison
source: auto-skill
extracted_at: '2026-06-12T11:24:43.241Z'
---

# Project Status Audit

When the user asks "что сделали", "где остановились", "что по плану" — perform a structured audit across 4 layers.

## Step 1 — Directory Structure Scan

List all directories and files in the component:

```
list_directory(path=<component_root>)
list_directory(path=<component_root>/handlers)
list_directory(path=<component_root>/services)
```

This reveals what files **exist** vs what was planned.

## Step 2 — Read Implementation Files

Read the key files to understand what's actually implemented:

- **Entry point** (e.g., `admin_bot.py`) — what handlers are registered, what callbacks exist
- **Handlers** — what commands/callbacks are handled
- **Services** — what business logic exists
- **Config/Keyboards** — what UI elements are defined

Focus on **registration patterns** (e.g., `application.add_handler(...)`) to know what's actually wired up, not just what files exist.

## Step 3 — Git History

Check recent commits to understand what was done and when:

```
git log --oneline -20
git log --oneline --since="YYYY-MM-DD" --until="YYYY-MM-DD"
```

This shows the **timeline** of work and what was committed together.

## Step 4 — Database/Data State

Query the actual data to understand runtime state:

```python
import sqlite3
conn = sqlite3.connect('results/feedback.db')
conn.row_factory = sqlite3.Row
# Check tables, row counts, sample data
```

Key checks:
- **Table existence** — which tables were created (migrations ran?)
- **Row counts** — is data accumulating or empty?
- **Sample data** — what format is data in? (especially after schema migrations)
- **Discrepancies** — old data format vs new schema expectations

## Step 5 — Plan Comparison

Read the plan document(s) and compare against reality:

```
read_file(path=<PLAN>.md)
```

For each planned block/feature, mark:
- ✅ Implemented (file exists + handler registered + tested)
- ⚠️ Partially implemented (file exists but not wired up, or missing edge cases)
- ❌ Not started (no files, no references in code)

## Output Format

Produce a structured report:

```
## ✅ Что сделано
- List implemented features with file references
- Git commits that delivered them

## 🏗 Архитектура
- Current directory tree with ✅ markers

## 📋 Состояние БД
- Table counts, data format observations, discrepancies

## 🚫 Что НЕ сделано (по <PLAN>.md)
- Planned blocks with ❌ status and what's missing

## ❌ Проблемы
- Data discrepancies, empty tables, schema mismatches
- Things that look done but don't work in practice

## 📌 Где остановились
- One-line summary of current state

## 🎯 Что далее по плану
- Next steps from the plan document, prioritized
```

## Key Principles

1. **Trust code over plans** — a file existing doesn't mean it's wired up. Check registrations.
2. **Trust DB over code** — code may expect a column that doesn't exist yet. Query the actual schema.
3. **Cross-reference** — compare git commits, plan documents, and actual file content to find gaps.
4. **Note discrepancies** — if a plan says "done" but the table is empty, flag it. If old data format conflicts with new schema, flag it.
5. **Count things** — row counts, file counts, commit counts. Numbers reveal state faster than descriptions.

## Code Dependency Mapping

When auditing, build a dependency map by searching imports across the codebase:

```bash
# For each module, find who imports it
grep -rn "from module_name import\|import module_name" --include="*.py"
```

Categorize each file by usage:
- **ACTIVE** — imported by production pipeline/bot code
- **CLI-only** — only run directly (`python script.py`), never imported
- **TEST** — only imported by test files
- **UNUSED** — no imports found anywhere

Also identify the **universal dependencies** — modules imported by 50+ other files (e.g., `base.py` in Haraba Mini).

## Untracked File Classification

When a project has 100+ untracked files, classify them into categories:

1. **Временные скрипты** — one-time deploy/debug scripts (e.g., `block_*.py`, `vps_*.py`)
2. **Тестовые файлы** — test scripts that should live in `tests/`
3. **Отладочные файлы** — diagnostic scripts for specific problems
4. **Потенциально полезные** — scripts that could be integrated into the main codebase
5. **Неиспользуемый мусор** — resolved, completed, or abandoned scripts

Do NOT delete — only classify. Flag categories 1 and 5 for potential cleanup.

## Read-Only Mode Enforcement

When auditing, explicitly enforce:
- ❌ No code changes
- ❌ No refactoring
- ❌ No bug fixes
- ❌ No DB changes (no ALTER TABLE, INSERT, UPDATE, DELETE)
- ❌ No git operations (commit, push, merge, rebase)
- ✅ Only reading files, running SELECT queries, grep/search
- ✅ Only creating documentation files in `docs/`
