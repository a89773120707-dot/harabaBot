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
Только на Авто.ру
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

### Step 1: Clean overlay text (REQUIRED)
Remove non-data overlay lines before parsing:
```python
OVERLAY_PATTERNS = [
    r'Ещё\s*\d+\s*фото',       # "Ещё 6 фото"
    r'Только на Авто\.ру',     # "Только на Авто.ру"
    r'История\s*авто\s*бесплатно',  # "История авто бесплатно"
    r'Модели-близнецы',        # popup
    r'Добавить в поиск',       # popup кнопка
]

def clean_overlay_text(text: str) -> str:
    cleaned = text
    for pattern in OVERLAY_PATTERNS:
        cleaned = re.sub(pattern, '', cleaned)
    lines = [l.strip() for l in cleaned.split('\n') if l.strip()]
    return '\n'.join(lines)
```

### Step 2: Parse brand/model
Use regex with ALL brands including Chinese:
```python
BRANDS = [
    # European: BMW, Mercedes-Benz, Audi, Volkswagen, Opel, Porsche, MINI, Volvo, Peugeot, Citroen, Renault, DS, Alfa Romeo, Fiat, Jaguar, Land Rover, Range Rover, Skoda
    # Japanese: Toyota, Honda, Nissan, Mazda, Subaru, Suzuki, Mitsubishi, Lexus, Infiniti
    # Korean: Hyundai, Kia, Genesis
    # American: Ford, Chevrolet, Cadillac, Jeep
    # Chinese: Chery, Haval, FAW, Dongfeng, Geely, Changan, Exeed, Omoda, Tank, Great Wall, GAC, Jetour, WEY, Livan, KAIYI, JAC, SWM, HAWT, Hongqi, BAIC, BYD, Zotye, Soueast, MG
]
# Sort by length descending (so "Land Rover" matches before "Land")
BRANDS_SORTED = sorted(BRANDS, key=len, reverse=True)
brand_pattern = '|'.join(re.escape(b) for b in BRANDS_SORTED)
model_re = re.compile(
    rf'({brand_pattern})\s+((?:[A-Z][a-zA-Z0-9]*|\d+)[a-zA-Z0-9]*(?:[-–][a-zA-Z0-9]+)?(?:\s+[IVX]+)?(?:\s+(?:Рестайлинг|I|II|III|IV))?)',
    re.IGNORECASE
)
```

### Step 3: Parse price
Price uses non-breaking spaces (`\xa0`), not regular spaces:
```python
price_m = re.search(r'(\d[\d\s\xa0]*\d)\s*[₽р]', text)
price = int(price_m.group(1).replace(' ', '').replace('\xa0', '').strip())
```

### Step 4: Parse mileage (CRITICAL — split by lines first)
**DO NOT** use `re.findall(r'(\d[\d\s]*\d)\s*км', full_text)` on the raw text — year and mileage will merge into one number (e.g., `202065000`).

**Correct approach — split by `\n` first:**
```python
def parse_mileage_from_text(full_text: str, year: int = None) -> int | None:
    lines = full_text.split('\n')
    candidates = []
    for line in lines:
        mileage_matches = re.findall(r'(\d[\d\s\xa0]*\d)\s*км', line)
        for m in mileage_matches:
            num_str = m.replace(' ', '').replace('\xa0', '').strip()
            if not num_str.isdigit():
                continue
            num = int(num_str)
            if year and num == year:
                continue
            if num > 1_000_000:
                continue
            candidates.append(num)
    return max(candidates) if candidates else None
```

### Step 5: Extract external ID
```python
ext_id_m = re.search(r'/(\d+-[a-f0-9]+)/?$', url)
ext_id = ext_id_m.group(1) if ext_id_m else ""
stable_car_key = f"auto_ru:{ext_id}"
```

### Step 6: Parse region
```python
region_m = re.search(r'(Москва|МО|Московская обл\.)', text)
region = region_m.group(1) if region_m else ''
```

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

## Critical: Data Extraction Method

**Auto.ru is a fully client-side SPA.** `page.content()` returns the raw HTML shell without card data.

### DOES NOT WORK:
```python
page.goto(url, wait_until="networkidle")  # TIMEOUT — networkidle never fires (analytics calls)
html = page.content()  # No card data embedded in HTML
```

### WORKS — Use `page.evaluate()` to extract from rendered DOM:
```python
page.goto(url, wait_until="domcontentloaded", timeout=30000)
page.wait_for_timeout(5000)  # Extra wait for JS render
page.keyboard.press("Escape")  # Close "Модели-близнецы" popup

js_extract = """(limit) => {
    const wrappers = document.querySelectorAll('div.ListingCars__universalSnippetWrapper');
    const results = [];
    wrappers.forEach((wrapper, i) => {
        if (limit && i >= limit) return;
        const text = wrapper.innerText;
        // ... extract price, year, mileage, brand, model, region, extId from text
        results.push({brand, model, year, price, mileage, region, extId, href});
    });
    return results;
}"""
cards_data = page.evaluate(js_extract, limit)
```

### Why `evaluate()` works but `content()` doesn't:
- `page.content()` = server-side HTML (shell only, no card data)
- `page.evaluate()` = reads the live DOM after JS rendering
- `card.inner_text()` via Playwright locator also works (accesses rendered DOM)

## Popup Handling
- Press `Escape` to close "Модели-близнецы" popup that overlays some cards
- Alternative: click the `X` button on the popup

## Known Parsing Issues (RESOLVED)

1. **Mileage regex captures year digits** — FIXED: Split text by `\n` before parsing mileage, check num != year, filter >1M. See Step 4.
2. **Chinese brands not in regex** — FIXED: Full brand list includes Chery, Haval, FAW, Dongfeng, Geely, Changan, Exeed, Omoda, Tank, Great Wall, GAC, Jetour, WEY, Livan, KAIYI, JAC, SWM, HAWT, Hongqi, BAIC, BYD, Zotye, Soueast, MG. See Step 2.
3. **Overlay text ("Ещё 6 фото") pollutes title** — FIXED: `clean_overlay_text()` removes overlay lines before parsing. See Step 1.
4. **Non-breaking spaces (`\xa0`) in prices** — FIXED: Use `[\d\s\xa0]` in regex and `.replace('\xa0', '')`. See Step 3.

## Current Parse Coverage (verified 2026-06-11)

Test: 37 cards from filtered Auto.ru search.

| Field | Coverage | Notes |
|-------|----------|-------|
| price | 100% | With `\xa0` handling |
| year | 100% | Standalone line |
| mileage | 97% | Line-by-line parsing |
| brand | 100% | Including Chinese brands |
| region | 97% | Москва/МО detection |
| ext_id | 100% | From URL regex |
| url | 100% | From href attribute |

## Remaining Unresolved Issues

1. **No AWD listings** — Hyundai Grand Santa Fe sometimes has 0 cards on Auto.ru
2. **Popup fails** — ~5-10% of cards may not open popup (use badge delta% as fallback)
3. **Rate limiting** — Add 1.5s delay between card opens
4. **CX-5 model name** — Auto.ru uses `CX_5` (underscore), not `CX-5`
5. **URL resolution** — Haraba click-tracking URLs (`haraba.ru/common/click?id=XXX`) don't work directly on Auto.ru. Must resolve via popup from Haraba session first.

## Detail Page Parser (Stage 3 — DONE 2026-06-11)

Direct Auto.ru detail URLs work and return rich data:
```
https://auto.ru/cars/used/sale/{brand}/{model}/{ext_id}/
```

### Key Fields Extracted

| Field | Method | Coverage |
|-------|--------|----------|
| engine | `_extract_field(text, "Двигатель")` → "2.0 л, 170 л.с., бензин" | 100% |
| engine_volume | regex `(\d+\.?\d*)\s*[лЛ]` from engine | 100% |
| engine_power | regex `(\d+)\s*л\.?с\.?` from engine | 100% |
| engine_fuel | regex `(бензин\|дизель\|газ\|электро\|гибрид)` | 100% |
| transmission | `_extract_field(text, "Коробка")` | 100% |
| drive | `_extract_field(text, "Привод")` | 100% |
| owners | `_extract_field(text, "Владельцы")` → regex `(\d+)` | 100% |
| seller_type | "Частное лицо"→private, "Дилер"→dealer | 100% |
| pts_status | `_extract_field(text, "ПТС")` | 100% |
| description | After "Комментарий продавца" / "Описание" | 100% |
| price_status | "Ниже оценки"→below, "Выше оценки"→above, "Справедливая"→fair | 75% |
| configuration | `_extract_field(text, "Комплектация")` | 100% |
| region | City name search in text | 75% |

### _extract_field() Helper

Field format on Auto.ru detail page:
```
Лейбл
Значение
```

```python
def _extract_field(text: str, label: str) -> str | None:
    idx = text.lower().find(label.lower())
    if idx < 0:
        return None
    rest = text[idx + len(label):]
    rest = rest.lstrip('\n\r\t ')
    lines = rest.split('\n')
    if lines:
        val = lines[0].strip()
        if val and len(val) < 200:
            return val
    return None
```

### Critical: Price Parsing (line-by-line to avoid ext_id merge)

ext_id (e.g., `1132948842`) and price (e.g., `1500000`) are on adjacent lines. Must parse line-by-line:

```python
# WRONG — merges ext_id + price:
price_m = re.search(r'(\d[\d\s\xa0]*\d)\s*[₽р]', body_text)

# CORRECT — line by line:
for line in body_text.split('\n'):
    pm = re.search(r'(\d[\d\s\xa0]*\d)\s*[₽р]', line)
    if pm:
        val = int(re.sub(r'[\s\xa0]+', '', pm.group(1)))
        if 100_000 < val < 50_000_000:
            price = val
            break
```

### Verified Test Results (2026-06-11)

Tested on 5 URLs (4 succeeded, 1 returned 404):

```
Honda Freed (1130171222)   — ✅ engine, transmission, drive, owners, seller, price_status, pts, desc
Kia Rio (1132951420)       — ✅ engine, transmission, drive, owners, seller, price_status, pts, desc, region
Geely Atlas (1132968845)   — ✅ engine, transmission, drive, owners, seller, price_status, pts, desc, region
Suzuki Swift (1132968418)  — ✅ engine, transmission, drive, owners, seller, pts, desc, region
Mazda CX-5 (1132972923)    — ❌ 404 — ad removed
```

Coverage on successful cards: engine 4/4, transmission 4/4, drive 4/4, owners 4/4, seller 4/4, price_status 3/4, pts 4/4, description 4/4.

## CRITICAL: CAPTCHA Issue (2026-06-11)

Auto.ru shows **"Вы не робот?"** (captcha) when opening multiple detail pages sequentially. This blocks parsing.

**Symptoms:**
- `page.title()` returns "Вы не робот?"
- `page.inner_text("body")` returns captcha text only
- All fields come back as empty/unknown

**Mitigation:**
1. Use ONE browser instance with sequential contexts (not parallel)
2. Add `wait_for_timeout(2000-3000)` between each detail page open
3. Limit batch size to 5-10 per run
4. If captcha appears, wait 30+ seconds and retry
5. Consider using different IP/user agent if batch processing is needed

**Test pattern that works:**
```python
p = sync_playwright().start()
browser = p.chromium.launch(headless=True)
for car in cars:
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(2000)  # Between pages
    # ... process
    ctx.close()
browser.close()
p.stop()
```

## CRITICAL: Auto.ru Numeric Estimate NOT Available in DOM

The numeric `auto_ru_estimate` (market price number) is **NOT available** in the rendered DOM. It is either:
- Rendered dynamically via JS after additional API calls
- Stored in internal state not exposed to the DOM
- Only available via Auto.ru's internal API

**What IS available in plain text:**
- Text status: "Ниже оценки", "Справедливая цена", "Выше оценки"

**Workaround — use text status as fallback:**
```python
# In detail page parser:
if "Ниже оценки" in body_text:
    price_status = "below_estimate"
elif "Выше оценки" in body_text:
    price_status = "above_estimate"
elif "Справедливая" in body_text:
    price_status = "fair"

# In price analyzer, map status to bonus:
status_map = {
    "below_estimate": ("below_market", +15),
    "fair": ("fair_price", +5),
    "above_estimate": ("above_market", -10),
}
```

See `auto-ru-pipeline-matcher-analyzer-score` skill for the full pipeline with text status fallback.

## Internal Price Scorer vs Auto.ru Estimate

**IMPORTANT distinction:** The phrase "выше хорошей цены на 290к ₽" in scoring output comes from `price_scorer_v2.py` (our YAML config ranges), NOT from Auto.ru's market evaluation.

- **Our config scorer** compares price against ranges defined in `awd_liquid_full_config.yaml`
- **Auto.ru estimate** would compare against Auto.ru's market data (numeric value not available in DOM)

Both signals are useful:
- Config scorer = "Is this price good according to OUR criteria?"
- Auto.ru estimate = "Is this price good according to MARKET data?"

When both are available, use both. When Auto.ru numeric is unavailable, use text status as fallback.
