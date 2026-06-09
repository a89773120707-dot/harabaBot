---
name: project-cleanup-for-deployment
description: Procedure to audit, clean, and prepare a project repository for deployment or GitHub push without losing data.
source: auto-skill
extracted_at: '2026-06-09T16:31:16.149Z'
---

# Project Cleanup for Deployment

When preparing a project for deployment (VPS) or pushing to GitHub, perform a **Pre-Deploy Audit** to remove clutter while keeping safety copies.

## 1. Inventory and Categorization
Scan the project root and classify files:
- **DELETE (Trash):** `debug_*.py`, `check_*.py`, `test_*.py`, `tmp_*.py`, `old_*.py`, `backup_*.py`, `diag_*.py`. (Files created during one-off debugging or setup).
- **ARCHIVE:** `login_wait.py` or specific tools useful for recovery but not runtime.
- **KEEP:** Core runtime scripts (`pipeline.py`, `bot.py`), configs (`*.yaml`), and deployment files (`requirements.txt`, `Dockerfile`, `service` files).

## 2. Move, Don't Delete
Never permanently delete files during cleanup. Use specific directories:
- Create `_trash/` for garbage files.
- Create `_archive/` for useful context/tools not needed for the main app.
- **Action:** Move files to these folders instead of removing them.

## 3. Update .gitignore
Ensure sensitive and heavy files are ignored:
```gitignore
# Secrets
.env
data/state.json

# Database & Logs
*.db
*.log
logs/

# Virtual Env & Cache
venv/
__pycache__/

# Cleanup folders
_trash/
_archive/
```

## 4. Verification Suite
After moving files, verify the project still works:
1. **Syntax Check:** `python -m compileall .`
2. **Import Check:** `python -c "import main_module; print('OK')"`
3. **Dry-Run:** `python pipeline.py --dry-run` (Ensure no missing imports from moved files).

## 5. Git Commit
Once verified:
```bash
git add .
git commit -m "Pre-deploy cleanup: moved diagnostics to trash/archive"
```
