---
name: haraba-filter-visibility-once
description: Call ensure_filters_visible() ONCE at script start to check/uncheck saved search checkboxes and make the filter panel available — NOT before each search in a loop
source: auto-skill
extracted_at: '2026-06-07T16:46:00.000Z'
---

# Filter Visibility — Call ONCE at Script Start

## Core Rule

**Call `ensure_filters_visible_once(page)` ONCE at the beginning of the script, immediately after loading the page.** Do NOT call it before each search in a loop.

**Why:** After saving a search, Haraba auto-checks the checkbox in the "Мои поиски" dropdown, which hides the filter panel (`#srch_fltr_*`). Instead of reopening filters before each search (which is slow and error-prone), do it once upfront.

**User explicitly said:** "так можно же сразу когда открываешь сайт сразу посмотреть стоят ли галочки в чек боксах и если стоят а тебе нужен фильтр просто там же убрать и нажать на мои поиски что бы применить"

## The Function

```python
def ensure_filters_visible_once(page):
    """
    ОДИН РАЗ при старте: проверить галочки → снять если есть → открыть фильтр.
    """
    _clear_overlay_js(page)  # Remove .cdk-overlay-container innerHTML
    
    _js_click(page, "button.mat-warn[aria-haspopup='menu']")  # Click "Мои поиски" via JS
    page.wait_for_timeout(3000)
    
    options = page.locator("mat-list-option")
    has_selected = any(
        options.nth(i).get_attribute("aria-selected") == "true"
        for i in range(options.count())
    )
    
    if has_selected:
        # Checkboxes ARE selected — uncheck EACH one individually
        for i in range(options.count()):
            opt = options.nth(i)
            if opt.get_attribute("aria-selected") == "true":
                opt.click()
                page.wait_for_timeout(300)
        
        # After unchecking — click "Мои поиски" again to apply
        _js_click(page, "button.mat-warn[aria-haspopup='menu']")
        page.wait_for_timeout(4000)
        
        # Clear overlay + Escape to reveal filter panel
        _clear_overlay_js(page)
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
    else:
        # No checkboxes selected — just close dropdown, filter is already visible
        page.keyboard.press("Escape")
        page.wait_for_timeout(1000)
        _clear_overlay_js(page)
        _js_click(page, "button.mat-warn[aria-haspopup='menu']")
        page.wait_for_timeout(3000)
    
    # Verify filter panel appeared
    brand_sel = page.locator("#srch_fltr_mark")
    brand_sel.wait_for(state="visible", timeout=5000)  # Will raise if fails
    return True
```

## Usage in run_saved_searches_8.py

```python
def run_all():
    # ... parse args, load data ...
    
    page, context, browser = get_authenticated_page()
    
    try:
        page.goto("https://haraba.ru/search")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(5000)
        
        # ═══ ОДИН РАЗ: открыть фильтр ═══
        if not ensure_filters_visible_once(page):
            log.error("Не удалось открыть фильтр — останавливаюсь")
            browser.close()
            return
        
        # Now ALL 8 searches can run without reopening filters
        for s in searches:
            expanded = expand_search(s)
            
            if should_skip_search(expanded.id, registry, force=args.force):
                continue
            
            success, results, error = run_single_search(page, expanded, registry)
            # ... update registry ...
            
    finally:
        browser.close()
```

## Critical Details

1. **Uncheck EACH checkbox individually** — iterating through `mat-list-option` and clicking each one with `aria-selected="true"`. The user corrected: "я не вижу что бы ты снимал галочки".

2. **After unchecking — click "Мои поиски" via JS** to apply changes. This closes the dropdown and reveals the filter panel.

3. **Clear overlay after apply** — Angular recreates overlay, so call `_clear_overlay_js()` + `Escape` after clicking "Мои поиски".

4. **Verify `#srch_fltr_mark` is visible** — this confirms the filter panel appeared.

5. **Do NOT call this before each search** — once at the top, then all searches reuse the same open filter panel.

## What NOT to Do

- ❌ Don't call `ensure_filters_visible` before every search in a loop — do it ONCE at start
- ❌ Don't use Playwright click on "Мои поиски" — ALWAYS use JS click
- ❌ Don't try to uncheck "Выбрать все" only — you MUST uncheck each selected item individually
- ❌ Don't skip the overlay cleanup after clicking "Мои поиски" — Angular will recreate it
- ❌ Don't assume the filter panel is visible — always verify `#srch_fltr_mark` is visible after setup
