---
name: haraba-my-searches-page
description: Reliable patterns for interacting with Haraba's /search/my-searches page — check existence, delete duplicates via trash icon
source: auto-skill
extracted_at: '2026-06-07T17:16:37.250Z'
---

# Haraba /search/my-searches Page Pattern

## Core Discovery

The `/search/my-searches` page is a **separate page** (not a dropdown). It shows all saved searches in an accordion/accordion-list with `span.text-truncate` elements for names and `mat-icon[svgicon='trash-can-outline']` for delete buttons.

**Why this matters:** Checking search existence via the dropdown ("Мои поиски") is unreliable because overlay backdrops block mat-list-option rendering. The `/search/my-searches` page is a static page — no overlay issues, reliable selectors.

## Check if Search Exists (Reliable)

**Use `/search/my-searches` page with `span.text-truncate` selector:**

```python
def check_search_exists(page: Page, save_name: str) -> bool:
    """Check if a saved search exists by going to /search/my-searches."""
    try:
        page.goto("https://haraba.ru/search/my-searches")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(5000)

        spans = page.locator("span.text-truncate")
        for i in range(spans.count()):
            span = spans.nth(i)
            text = span.inner_text().strip()
            if save_name in text:
                return True
        return False
    except Exception as e:
        return False
```

**This is the ONLY reliable way to check.** The dropdown approach fails because:
- Overlay backdrops block `mat-list-option` rendering
- After closing dropdown once, overlay may not reopen properly
- `innerText` on overlay container is inconsistent

## Delete Duplicate Searches

**Use the trash-can-outline icon button on each row:**

```python
def remove_duplicates(page: Page):
    """Remove duplicate saved searches via /search/my-searches trash button."""
    page.goto("https://haraba.ru/search/my-searches")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(5000)

    # Find all rows
    rows = page.locator("tr.mat-row")
    
    # Count occurrences of each search name
    seen = {}
    duplicates = []
    for i in range(rows.count()):
        row = rows.nth(i)
        text = row.inner_text().strip()
        name = text.split('\n')[0].strip()
        if name in seen:
            duplicates.append(i)  # This is a duplicate
        else:
            seen[name] = i
    
    # Delete duplicates from END to start (indices shift)
    for idx in reversed(duplicates):
        row = page.locator("tr.mat-row").nth(idx)
        delete_btn = row.locator("mat-icon[svgicon='trash-can-outline']")
        if delete_btn.count() > 0:
            delete_btn.first.click()
            page.wait_for_timeout(2000)
        else:
            # Fallback: button with tooltip
            delete_btn = row.locator("button[mattooltip='Удалить']")
            if delete_btn.count() > 0:
                delete_btn.first.click()
                page.wait_for_timeout(2000)
```

## Key Selectors on /search/my-searches

| Element | Selector | Purpose |
|---------|----------|---------|
| Search name | `span.text-truncate` | Contains the saved search name |
| Delete button | `mat-icon[svgicon='trash-can-outline']` | Trash icon for deletion |
| Delete button (fallback) | `button[mattooltip='Удалить']` | Button with "Удалить" tooltip |
| Row | `tr.mat-row` | Each saved search is a table row |

## Delete Button HTML

The delete button has this structure:

```html
<button type="button" mat-icon-button="" color="warn" mattooltip="Удалить" ...>
  <mat-icon svgicon="trash-can-outline">
    <svg>...</svg>
  </mat-icon>
</button>
```

**Best selector:** `mat-icon[svgicon='trash-can-outline']` — most specific, least likely to match other elements.

## Important Notes

1. **Each navigation to `/search/my-searches` is independent** — no need to manage overlays or dropdowns
2. **Always wait 5s after page load** — Angular needs time to render the accordion list
3. **Delete from end to start** — row indices shift after each deletion
4. **`span.text-truncate` contains the full search name** — use `.includes()` not exact match
5. **The page may show empty initially** — use `networkidle` or 5s+ wait

## What NOT to Do

- ❌ Don't try to check search existence via "Мои поиски" dropdown — use `/search/my-searches` page instead
- ❌ Don't delete from start to end — indices will be wrong after first deletion
- ❌ Don't use `get_by_role` for the trash button — use CSS selector on `svgicon` attribute
- ❌ Don't assume `tr.mat-row` count stays the same after deletion — re-query after each delete
- ❌ Don't skip the 5-second wait after navigating to `/search/my-searches` — Angular accordion renders slowly
