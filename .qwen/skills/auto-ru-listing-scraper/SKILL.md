---
name: auto-ru-listing-scraper
description: How to scrape car listings and market evaluations from Auto.ru using Playwright
source: auto-skill
extracted_at: '2026-06-08T06:34:40.193Z'
---

# Auto.ru Listing Scraper Patterns

## URL Pattern

Auto.ru search URLs follow this template:

```
https://auto.ru/moskovskaya_oblast/cars/{brand_slug}/{model_slug}/used/drive-4x4_wheel/
    ?year_from={year_from}&year_to={year_to}
    &km_age_to={mileage_max}
    &pts_status=1
    &with_discount=false
    &resolution_filter=is_pts_ok&resolution_filter=is_owners_ok
    &resolution_filter=is_legal_ok&resolution_filter=is_accidents_ok
    &seller_group=PRIVATE
    &sort=cr_date-desc
```

Key parameters:
- Region is part of the path (`moskovskaya_oblast/`)
- `drive-4x4_wheel/` filters for AWD
- `resolution_filter` — filters for clean legal/accident/PTS/owner history
- `seller_group=PRIVATE` — only private sellers
- `pts_status=1` — valid PTS (vehicle registration)
- `km_age_to` — max mileage
- `sort=cr_date-desc` — newest first

### URLs with catalog_filter (generations)

When filtering by specific generations (e.g., Audi Q5 8R + 8R Рестайлинг), the URL uses `catalog_filter` with **duplicate parameters**:

```
https://auto.ru/moskovskaya_oblast/cars/used/
    ?year_from=2012&km_age_to=200000
    &catalog_filter=mark%3DAUDI%2Cmodel%3DQ5%2Cgeneration%3D8351293
    &catalog_filter=mark%3DAUDI%2Cmodel%3DQ5%2Cgeneration%3D3784280
    &resolution_filter=...&seller_group=PRIVATE&gear_type=ALL_WHEEL_DRIVE
```

**Important:** Playwright's `page.goto()` cannot handle duplicate query parameters (it drops duplicates). Use this workaround:

```python
# First load any page, then navigate via JavaScript
page.goto("https://auto.ru", wait_until="domcontentloaded")
page.evaluate(f"window.location.href = `{full_url_with_duplicates}`")
page.wait_for_url("**auto.ru/**", timeout=30000)
```

## CSS Selectors

**Card container** (verified on 2026-06-08):
```
div.ListingCars__universalSnippetWrapper
```

This selector returns all visible listing cards on the search results page.

**Card URL link**:
```
a[href*='/cars/used/sale/']
```

## Parsing Card Data

Each card's `inner_text()` contains structured lines:
```
Ещё 6 фото
История авто бесплатно
Audi Q5 II (FY)
Комплектация
45 TFSI quattro S tronic
•
Коричневый
2.0 л, 249 л.с., бензин
Внедорожник 5 дв.
Полный привод
Робот
2017
92 000 км
3 198 000 ₽
Справедливая цена
```

Parsing strategy:
1. Split text by `\n`, strip each line
2. **Title**: find first line containing a brand name (Audi, BMW, Kia, etc.)
3. **Year**: match `^(20\d{2})$` as a standalone line
4. **Price**: search `([\d\s]+)\s*[₽р]` in any line
5. **Mileage**: search `([\d\s]+)\s*км` in any line
6. **Evaluation status** (from search page text):
   - `"Справедливая"` → `fair`
   - `"Ниже оценки"` → `below`
   - `"Выше оценки"` → `above`

## Market Evaluation Parsing (on card page)

**Works for ALL cards** — every listing has the "Подробнее про оценку стоимости" link.

### Step 1: Read badge text
Selector: `[class*='OfferPriceBadgeNew']`
Extract: `el.childNodes[0].textContent`

Pattern: `(Выше|Ниже)\s+оценки\s+на\s+(\d+)%`
Returns delta as ±percent and status: `above` / `below` / `fair`.

### Step 2: Open popup for min-max (ALL cards)
Click link: `"Подробнее про оценку стоимости"` (always present, not just for "Справедливая цена")

```python
with page.expect_popup(timeout=10000) as popup_info:
    page.get_by_role("link", name="Подробнее про оценку стоимости").first.click()

popup = popup_info.value
popup.wait_for_load_state("domcontentloaded", timeout=10000)

title_elem = popup.locator(".EvaluationFormResult__title-fEw84").first
title_text = title_elem.inner_text(timeout=3000)
# Pattern: "1 822 000–2 062 000 ₽"
m = re.search(r"([\d\s]+)\s*[–—\-]\s*([\d\s]+)\s*₽", title_text)
eval_min = clean_digits(m.group(1))
eval_max = clean_digits(m.group(2))

popup.close()
```

**Verified on 2026-06-08:** 30/30 cards returned min-max via popup, including "Выше/Ниже" cards.

## Timing

- After page load: `wait_for_timeout(5000)` for JS rendering
- Between card openings: `wait_for_timeout(1500-3000)` to avoid rate limiting
- Page load timeout: 15-30 seconds

## Fallback

If search page returns 0 cards:
- Save HTML for debugging: `page.content()`
- Take screenshot: `page.screenshot(path=...)`
- Check for captcha/bot detection

## What doesn't work

- `data-marker='offer-item'` — old selector, returns 0
- `.ListingItem` — old selector, returns 0
- `article[data-marker='offer-item']` — returns 0
- These were valid in older Auto.ru versions but no longer match
