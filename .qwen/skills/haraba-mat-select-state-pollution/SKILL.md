---
name: haraba-mat-select-state-pollution
description: Haraba brand mat-select may show models (209 options) from previous search instead of brands. Fix: search all options with case-insensitive match, don't filter by count > 100.
source: auto-skill
extracted_at: '2026-06-08T20:00:00.000Z'
---

## Problem

After selecting a brand (e.g., Hyundai) in Haraba's `#srch_fltr_mark` dropdown, the mat-select state is polluted. The next time the brand selector is opened, it shows **209 Hyundai model options** instead of the brand list (~50 brands).

This broke Kia Sorento and Kia Sportage searches because "Kia" was not found among the 209 Hyundai model options.

## Root Cause

Angular mat-select does not fully reset its cached options when "Очистить" (Clear) is clicked. The dropdown retains the previous brand's model list.

## Fix

**Do NOT block by option count > 100.** Instead, search ALL options with case-insensitive match:

```python
def _select_mat_option(page: Page, selector: str, text: str) -> bool:
    sel = page.locator(selector)
    sel.wait_for(state="visible", timeout=5000)
    sel.click()
    page.wait_for_timeout(1000)
    page.wait_for_selector("mat-option", state="visible", timeout=5000)

    options = page.locator("mat-option")
    opt_count = options.count()

    # Case-insensitive search across ALL options
    for i in range(opt_count):
        try:
            opt_text = options.nth(i).inner_text().strip()
            if opt_text == text or opt_text.lower() == text.lower():
                options.nth(i).click()
                _close_dropdown(page)
                return True
        except:
            pass

    _close_dropdown(page)
    return False
```

**Key insight:** "Kia" exists in the 209-option list — the previous code was blocking before searching. Case-insensitive match finds it.

## What NOT to do

- ❌ Don't check `opt_count > 100` and skip searching — the target brand may still be in the list
- ❌ Don't try to reload page between each search — slow and unnecessary
- ❌ Don't rely on "Очистить" to reset mat-select — it doesn't fully reset Angular state