---
name: haraba-search-builder-architecture
description: HarabaMini Search Builder complete architecture — 9 blocks, module files, data flow, and CLI commands
source: auto-skill
extracted_at: '2026-06-07T19:45:00.000Z'
---

# Haraba Search Builder Architecture (v1.1)

## Module Files

| File | Purpose |
|------|---------|
| `base.py` | Shared constants (STATE_PATH, logging, dirs) |
| `session_manager.py` | `get_authenticated_page()` — opens browser with state.json |
| `config_loader_8.py` | `load_searches()` → `list[SearchConfig]` from YAML |
| `search_expander_8.py` | `expand_search()` → price margin ±50,000, returns `ExpandedSearchConfig` |
| `apply_filters_8.py` | `apply_filters_from_expanded_config()` — sets all filters on page |
| `saved_search_helper_8.py` | `save_current_search()`, `verify_saved_search()`, `check_search_exists()` |
| `filters_block9.py` | `_apply_additional_filters()` — regions, drivetrain, transmission, etc. |
| `registry_8.py` | `load_registry()`, `save_registry()`, `should_skip_search()`, `upsert_registry_success/failed()` |
| `run_saved_searches_8.py` | Main runner — creates/updates all 8 searches |
| `verify_saved_searches_8.py` | Verifies all saved searches are active and have results |

## CLI Commands

```bash
# Create/update all 8 searches
python run_saved_searches_8.py              # skip already saved
python run_saved_searches_8.py --force      # re-create all 8
python run_saved_searches_8.py --only ford_kuga   # one search

# Verify all saved searches
python verify_saved_searches_8.py           # check checkboxes + results

# Quick session check
python check_session.py                     # VALID / EXPIRED / MISSING
```

## Data Flow

```
config/awd_liquid_ready_8.yaml
    ↓ (load_searches → 8 SearchConfig)
config_loader_8.py
    ↓ (expand_search → price margin ±50K)
search_expander_8.py
    ↓ (ExpandedSearchConfig with all fields)
run_saved_searches_8.py
    ├── ensure_filters_visible_once()     # open filter panel
    ├── apply_filters_from_expanded_config()  # brand, model, year, price, mileage
    ├── _apply_additional_filters()        # regions, drivetrain, legal, seller, owners, condition, transmission
    ├── click_search()                     # press "Применить"
    ├── save_current_search()              # "Сохранить в мои поиски"
    ├── verify_saved_search()              # confirm via /search/my-searches
    └── upsert_registry_success()          # update config/saved_searches_8.yaml
    ↓
config/saved_searches_8.yaml               # registry with status/results_count/verify_status
```

## Registry Structure (config/saved_searches_8.yaml)

```yaml
saved_searches:
  ford_kuga:
    id: ford_kuga
    save_name: "Ford Kuga 2013-2018"
    status: saved                    # saved | failed
    results_count: 30
    verify_status: verified          # verified | verify_failed
    verify_error: null
    verified_at: "2026-06-07 22:10:28"
    updated_at: "2026-06-07 22:02:58"
    last_error: null
```

## Critical Rules

1. **Call `ensure_filters_visible_once()` ONCE at start** — deselects all saved searches to show filter panel
2. **JS click for "Мои поиски"** — overlay blocks Playwright clicks, use `page.evaluate()`
3. **Close browser in `finally`** — one browser session for all operations
4. **Update registry after each save** — prevents partial re-runs from duplicating
5. **Never touch AUTO_MAIN_* searches** — separate project, exclude from all operations
6. **Apply checkboxes after saving** — searches don't activate until "Мои поиски" clicked again
