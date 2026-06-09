---
name: haraba-ui-interaction-patterns
description: Critical UI interaction patterns for Haraba.ru automation via Playwright — overlay handling, filter workflow, timing requirements, search saving, search verification, and Block 9 additional filters (regions, drivetrain, seller, owners, condition)
source: auto-skill
extracted_at: '2026-06-07T09:59:15.210Z'
updated_at: '2026-06-07T18:44:00.000Z'
---

# Haraba UI Interaction Patterns

## Problem

Haraba.ru is an Angular Material app with overlay backdrops (`cdk-overlay-backdrop`) that block clicks on elements even when those elements are visible in the DOM. The page shows either saved searches OR the filter panel — never both at the same time.

**CRITICAL:** When overlay backdrops persist across interactions (Angular recreates them), Playwright's `.click()` will always timeout. You MUST use JavaScript-based approaches to bypass the overlay.

## Core Pattern: Clear Overlay Container via JS — PRIMARY Approach

**The most reliable method** is to remove the entire overlay container HTML, then use JS clicks:

```python
def _clear_overlay_via_js(page):
    """Remove overlay container HTML via JS."""
    page.evaluate("""() => {
        const container = document.querySelector('.cdk-overlay-container');
        if (container) container.innerHTML = '';
    }""")
    page.wait_for_timeout(500)

def _js_click_button(page):
    """Click "Мои поиски" via JS — bypasses any overlay."""
    page.evaluate("""(sel) => {
        const el = document.querySelector(sel);
        if (el) el.click();
    }""", "button.mat-warn[aria-haspopup='menu']")
```

## Confirmed Selectors (verified 2026-06-07)

**mat-select dropdowns:**
- `#srch_fltr_mark` — brand
- `#srch_fltr_model` — model
- `#srch_fltr_drive_type` — drive (Полный/Передний/Задний)
- `#srch_fltr_transmission` — transmission
- `#srch_fltr_confition` — condition (Кроме битых)
- `#srch_fltr_salers_type` — seller type (Частник/Дилер)
- `#srch_fltr_owners` — owners (1-3)
- `#srch_fltr_restrictions` — restrictions (Без ограничений)
- `#srch_fltr_wheel_side` — steering
- `#srch_fltr_period` — period

**inputs:**
- `#srch_fltr_year_from`, `#srch_fltr_year_to`
- `#srch_fltr_price_from`, `#srch_fltr_price_to`
- `#srch_fltr_mileage_from`, `#srch_fltr_mileage_to`

**buttons:**
- `#srch_fltr_apply_btn` — "Применить"
- `#srch_fltr_clear_btn` — "Очистить фильтр"
- button:has-text("Сохранить в мои поиски") — save search

## Block 9: Additional Filter Value Mappings

```python
HARABA_VALUES = {
    'drivetrain': {'awd': 'Полный', 'fwd': 'Передний', 'rwd': 'Задний', '4matic': 'Полный'},
    'seller_type': {'private': 'Частник', 'dealer': 'Дилер'},
    'legal_restrictions': {'none': 'Без ограничений'},
    'owners': {'1-3': '1-3', '1-2': '1-2', '1': '1'},
    'condition': {'not_damaged': 'Кроме битых'},
}

REGIONS = ['Москва', 'Московская область', 'Ярославская область', 'Тверская область',
           'Владимирская область', 'Калужская область', 'Рязанская область', 'Тульская область']
```

## Key Timing Values

| Action | Wait Time | Reason |
|--------|-----------|--------|
| Page load | 4000ms | Angular boot + API calls |
| Brand → Model | 4000ms | Models load after brand selection |
| "Сохранить" click → dialog | 3000ms | MatDialog animation |
| After save cleanup | 3000ms total | Dialog close + overlay cleanup |
| "Мои поиски" dropdown open | 3000ms | Animation + data load |
| JS click → "Мои поиски" apply | 5000ms | Saved search loading |
| "Применить" click → results | 3000ms | API query + render |

## What NOT to Do

- ❌ Don't click filter elements without clearing overlays first — timeout guaranteed
- ❌ Don't select model immediately after brand — models won't be loaded yet (need 4s)
- ❌ Don't use `is_visible()` check on `mat-select` — use `wait_for(state="visible")` with timeout
- ❌ Don't assume filter panel is always visible — depends on saved search selection state
- ❌ Don't use `input()` to wait in YOLO mode — use `time.sleep()` instead
- ❌ Don't skip the 5-second wait after applying a saved search — results take time to load
- ❌ Don't use Playwright click on "Мои поиски" — ALWAYS use JS click to bypass overlay
