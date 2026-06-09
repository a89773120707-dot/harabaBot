---
name: haraba-9-search-extension
description: Pattern for adding 9 new search models to haraba-mini — config assembly, dual-margin expander, stable save helper
source: auto-skill
extracted_at: '2026-06-08T19:40:00.000Z'
updated_at: '2026-06-08T22:15:00.000Z'
---

## Problem

After completing 8 ready models (Phase 1), 9 partial models need to be connected as saved searches on Haraba. These come from auto.ru evaluation data (not dealer notes), so they have different confidence levels.

## Known issue: mat-select state pollution

When running searches in a loop, the brand mat-select (`#srch_fltr_mark`) may show **models from the previous brand** (209 options) instead of the brand list.

**Fix:** Use case-insensitive search across ALL options in `_select_mat_option()`. Do NOT block by option count > 100. See `haraba-mat-select-state-pollution` skill.

## Source files

| File | Purpose |
|------|---------|
| `config/saved_searches_9.yaml` | Basic model params (brand, model, years) |
| `results/price_ranges_9_v2.yaml` | Auto.ru evaluation price ranges |
| `results/expert_rules_9_ready.yaml` | Engines, transmissions, mileage, trims, reject rules |

## Output: `config/awd_liquid_9.yaml`

Assembled from all three sources. Key differences from ready_8:
- `price_from` = `good_buy_price` (not excellent lower bound) — avoids suspiciously cheap listings
- `price_to` = `expensive_but_ok_if_top` upper bound
- 3 models marked as `low_evaluation_sample`: hyundai_grand_santa_fe, nissan_pathfinder, volvo_xc90

### The 9 models

audi_q5, hyundai_santa_fe, kia_sorento, kia_sportage, mazda_cx5, mitsubishi_pajero_iv, hyundai_grand_santa_fe, nissan_pathfinder, volvo_xc90

## Dual-margin expander

`search_expander_9.py` uses different price margins:

| Type | Models | Margin |
|------|--------|--------|
| Normal | audi_q5, hyundai_santa_fe, kia_sorento, kia_sportage, mazda_cx5, mitsubishi_pajero_iv | ±50,000 |
| Low sample | hyundai_grand_santa_fe, nissan_pathfinder, volvo_xc90 | ±100,000 |

Why: Low sample models have fewer Auto.ru evaluation cards, so price ranges are less precise. Wider margin compensates for uncertainty.

## Stable save helper (TargetClosedError fix)

The old `saved_search_helper_8.py` consistently crashes with `TargetClosedError` on save button click.

**Solution:** `saved_search_helper_9.py` uses the pattern from `diag_save_dialog.py`:
1. Click "Сохранить в мои поиски" via `get_by_text()` (not `get_by_role()`)
2. Wait 3s for MatDialog
3. Remove overlay backdrops via JS
4. Fill `input[formcontrolname='name']`
5. Find confirm button by scanning all buttons for "сохранить"/"ok"/"подтвердить" text
6. Click confirm, wait 3s

**Never use `get_by_role("button", name="Сохранить")`** — it causes TargetClosedError. Use `get_by_text()` or scan buttons manually.

## Module architecture

```
config/awd_liquid_9.yaml
    ↓
config_loader_9.py → SearchConfig9 (with price_confidence, need_manual_review)
    ↓
search_expander_9.py → ExpandedSearchConfig9 (with expanded_price_from/to, price_margin)
    ↓
apply_filters_9.py → apply_filters_9(), click_search_9(), count_results()
    ↓
saved_search_helper_9.py → save_search_9(), check_search_exists_9()
    ↓
registry_9.py → load_registry_9(), upsert_registry_9_success/failed/verified()
    ↓
run_saved_searches_9.py → main runner (--dry-run, --only, --force, --skip-existing)
```

## Registry

Separate from 8-model registry: `results/saved_searches_9_registry.yaml`
Statuses: pending → saved → verified
Never mix with 8-model registry until all 9 are verified.

## Brand selector pollution fix

When running multiple searches in a loop, after a Hyundai search the brand selector (`#srch_fltr_mark`) shows **models instead of brands** (209 Hyundai model options instead of ~50 brands). The "Очистить" button doesn't fully reset Angular mat-select state.

**Fix in `_select_mat_option()`:** Remove the `count > 100` blocking logic. Instead, scan ALL options (even 209) using case-insensitive matching. Kia is found as "KIA" among the 209 options and clicks correctly.

```python
# Search ALL options, not just first N
for i in range(opt_count):
    opt_text = options.nth(i).inner_text().strip()
    if opt_text == text or opt_text.lower() == text.lower():
        options.nth(i).click()
        return True
```

Don't try page.reload(), window.location.href, or dropdown reopen — none of them reset the Angular mat-select cache. Just search all options.

## Commands

```bash
# Dry run
python run_saved_searches_9.py --dry-run

# Test one model
python run_saved_searches_9.py --only audi_q5

# All 9
python run_saved_searches_9.py

# Force recreate
python run_saved_searches_9.py --force
```
