---
name: saved-search-lifecycle
description: Pattern for managing saved search creation — duplicate prevention, registry-based state, force-update logic, and single-responsibility functions
source: auto-skill
extracted_at: '2026-06-07T16:15:00.000Z'
---

# Saved Search Lifecycle Pattern

## Core Principle: Prevent Duplicates Before Creating, Don't Clean Up After

**Never create duplicate saved searches.** Always check if a search with the same name exists BEFORE saving.

```python
from saved_search_helper_8 import check_search_exists, save_current_search

# Check BEFORE saving — prevents duplicates entirely
if check_search_exists(page, expanded.save_name):
    log.info(f"[INFO] Поиск '{expanded.save_name}' уже существует — не сохраняю дубликат")
else:
    save_current_search(page, expanded.save_name)
```

**Why:** Post-creation duplicate cleanup is unreliable (Haraba's UI makes automated deletion fragile). Prevention is simpler and always works.

## Registry-Based State Management

Use a local YAML registry to track which searches are saved, failed, or need retry:

```python
from registry_8 import (
    load_registry,
    save_registry,
    should_skip_search,
    upsert_registry_success,
    upsert_registry_failed,
)

registry = load_registry()

# Skip if already saved (unless --force)
if should_skip_search(model_id, registry, force=args.force):
    log.info("[STATUS] already saved → skip")
    continue

# After success:
upsert_registry_success(registry, expanded, results_count=30)
save_registry(registry)

# After failure:
upsert_registry_failed(registry, expanded, "error message")
save_registry(registry)
```

## Force-Update CLI Flags

| Flag | Behaviour |
|------|-----------|
| `--force` | Re-create ALL 8 searches (ignore registry saved status) |
| `--only ford_kuga` | Run only one search |
| `--only ford_kuga --force` | Re-create one specific search |
| `--dry-run` | Show plan without launching browser |

```python
def should_skip_search(search_id, registry, force=False) -> bool:
    if force: return False              # --force → never skip
    item = get_registry_item(search_id, registry)
    if item is None: return False       # no record → don't skip
    return item.get("status") == "saved" # saved → skip, failed → retry
```

## Single-Responsibility Functions

**Rule:** Each function does exactly ONE thing. Don't combine multiple actions.

| Function | Does | Does NOT |
|----------|------|----------|
| `check_search_exists()` | Check if search exists | Does NOT delete, does NOT create |
| `save_current_search()` | Save one search | Does NOT verify, does NOT clean up |
| `verify_saved_search()` | Verify search exists | Does NOT create, does NOT delete |
| `apply_filters()` | Apply filter values | Does NOT save, does NOT search |
| `click_search()` | Click "Применить" | Does NOT check results |

**User explicitly said:** "каждая функция только за одно действие не надо переусложнять"

## What NOT to Do

- ❌ Don't create duplicates then try to clean them up — check first
- ❌ Don't combine save + verify + cleanup in one function
- ❌ Don't rely on automated duplicate deletion (Haraba UI makes this unreliable)
- ❌ Don't skip `save_registry()` after each search — must persist state immediately
- ❌ Don't use post-creation dedup scripts — they fail on Angular Material dropdowns
- ❌ Don't set checkboxes on ALL searches in dropdown — ONLY on the 8 from config
- ❌ Don't use `--force` without first manually deleting existing searches from `/search/my-searches` — it will create more duplicates
- ❌ Don't run `verify_saved_search()` after `check_search_exists` returns True — if the search already exists, skip verify (the dropdown may be empty after unchecking)

## Workflow After Manual Cleanup

When the user has manually deleted ALL saved searches from `/search/my-searches`:
1. Run `python run_saved_searches_8.py --force` (first time, all need creating)
2. Subsequent runs: `python run_saved_searches_8.py` (no --force, uses registry skip)
3. Result: exactly 8 searches, no duplicates

Each search follows: filters → apply → save → registry update → next.
The `check_search_exists` guard prevents accidental duplicates on reruns.

## Apply All Searches at End of run_saved_searches_8.py

**After all searches are saved (or skipped), always check and apply checkbox selections.**

```python
# After the main loop, INSIDE the try block (before finally: browser.close()):
save_names = [expand_search(s).save_name for s in searches]

# Open "Мои поиски" dropdown
_clear_overlay_js(page)
_js_click(page, "button.mat-warn[aria-haspopup='menu']")
page.wait_for_timeout(4000)

options = page.locator("mat-list-option")
need_apply = False

# Check which of our 8 searches are selected
for i in range(options.count()):
    opt = options.nth(i)
    text = opt.inner_text().strip()
    aria = opt.get_attribute("aria-selected")
    if any(name in text for name in save_names):
        if aria != "true":
            need_apply = True

if need_apply:
    # Set checkboxes on all our searches
    for i in range(options.count()):
        opt = options.nth(i)
        text = opt.inner_text().strip()
        aria = opt.get_attribute("aria-selected")
        if any(name in text for name in save_names) and aria != "true":
            opt.click()
            page.wait_for_timeout(300)
    # Apply via JS click on "Мои поиски"
    _js_click(page, "button.mat-warn[aria-haspopup='menu']")
    page.wait_for_timeout(5000)
else:
    # All already selected — just close dropdown
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
```

**Why:** After `ensure_filters_visible_once` unchecks all searches to open the filter panel, the searches are no longer applied. This step ensures all 8 are re-selected and applied at the end.

**Critical:** This must be INSIDE the `try` block, BEFORE `finally: browser.close()`, because it needs the browser to be open.
