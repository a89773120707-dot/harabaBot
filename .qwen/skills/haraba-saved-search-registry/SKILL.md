---
name: haraba-saved-search-registry
description: Registry pattern for tracking Haraba saved searches — YAML-based state, dedup protection, force-update workflow, and verification via /search/my-searches
source: auto-skill
extracted_at: '2026-06-07T19:11:09.087Z'
---

# Haraba Saved Search Registry Pattern

## Registry File: `config/saved_searches_8.yaml`

```yaml
saved_searches:
  ford_kuga:
    id: ford_kuga
    save_name: "Ford Kuga 2013-2018"
    status: saved          # saved | failed
    brand: Ford
    model: Kuga
    year_from: 2013
    year_to: 2018
    price_from_real: 800000
    price_to_real: 1600000
    results_count: 30
    verify_status: verified  # verified | verify_failed | null
    verify_error: null
    verified_at: "2026-06-07 22:10:28"
    last_error: null
    updated_at: "2026-06-07 22:02:58"
```

## Core Functions

### Skip Logic
```python
def should_skip_search(search_id, registry, force=False):
    if force:
        return False          # Force = never skip
    item = registry.get('saved_searches', {}).get(search_id)
    if item is None:
        return False          # No record = don't skip
    return item.get('status') == 'saved'  # Only skip if already saved
```

### Verify via /search/my-searches
```python
def check_search_exists(page, save_name):
    """Check if a saved search exists on Haraba."""
    page.goto("https://haraba.ru/search/my-searches")
    page.wait_for_timeout(5000)
    spans = page.locator("span.text-truncate")
    for i in range(spans.count()):
        if save_name in spans.nth(i).inner_text().strip():
            page.goto("https://haraba.ru/search")
            page.wait_for_timeout(3000)
            return True
    page.goto("https://haraba.ru/search")
    page.wait_for_timeout(3000)
    return False
```

### Apply All Searches (checkboxes + results)
```python
def apply_all_searches(page, save_names):
    """Set checkboxes on all target searches and apply."""
    # Open dropdown
    _js_click(page, "button.mat-warn[aria-haspopup='menu']")
    page.wait_for_timeout(4000)

    # Check/uncheck each
    opts = page.locator("mat-list-option")
    for i in range(opts.count()):
        text = opts.nth(i).inner_text().strip()
        aria = opts.nth(i).get_attribute("aria-selected")
        if any(name in text for name in save_names):
            if aria != "true":
                opts.nth(i).click()
                page.wait_for_timeout(300)

    # Apply
    _js_click(page, "button.mat-warn[aria-haspopup='menu']")
    page.wait_for_timeout(5000)

    # Count results
    results = page.locator("tr.mat-row").count()
    return results
```

## Dedup Workflow

After `--force` run, duplicates may appear in Haraba. Manual cleanup:
1. Go to `/search/my-searches`
2. Find duplicate rows (same search name appears multiple times)
3. Click trash icon (mat-icon svgicon="trash-can-outline") on duplicates
4. Keep only one row per search

Auto-prevention: `check_search_exists()` checks site before creating, `should_skip_search()` checks registry.

## Force Update Flag

```bash
python run_saved_searches_8.py --force           # Re-save all 8
python run_saved_searches_8.py --only ford_kuga --force  # Re-save one
```

Force mode:
- Skips registry check
- Re-creates search on site
- Does NOT check for existing search on site (saves time)
- Updates registry with new timestamp

## Key Rules

1. **Always apply checkboxes after saving** — searches don't activate until "Мои поиски" clicked again
2. **Registry + Site check** — two layers of dedup protection
3. **Never close browser between saves** — one browser session for all 8 searches
4. **Always call `ensure_filters_visible_once()` before first filter** — opens filter panel by deselecting all saved searches
5. **Update registry after each save** — prevents partial re-runs from duplicating
