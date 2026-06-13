---
name: auto-ru-integration-architecture
description: Auto.ru source module integration into Haraba Mini — architecture, implementation stages, CAPTCHA handling, and persistent browser profile approach
source: auto-skill
extracted_at: '2026-06-11T18:00:00.000Z'
---

# Auto.ru Integration Architecture

## Overview

Auto.ru is integrated as a **separate source module** within the Haraba Mini project. It operates independently from the Haraba scraper and pipeline, with its own runner, parser, matcher, and analyzer modules.

**Key principle:** Do not touch `run_daily_pipeline.py`, `session_manager.py`, or any Haraba-specific code until Auto.ru works stably as a standalone module.

## Module Structure

```
app/
  sources/
    auto_ru/
      __init__.py
      browser.py              # Playwright browser/context creation (non-persistent)
      persistent_browser.py   # Persistent Chrome profile handling
      scraper.py              # Search page scraping + card extraction
      selectors.py            # CSS selectors for Auto.ru
      parser.py               # Detail page parsing (engine, transmission, drive, etc.)
      urls.py                 # URL builder (placeholder)
      normalizer.py           # Price/mileage parsing, brand/model extraction, overlay cleanup
      valuation_parser.py     # Auto.ru price estimate extraction
  matcher/
    auto_ru_matcher.py        # Match cards against YAML config
  analyzer/
    price_analyzer.py         # Market position analysis (below/fair/above)
    internal_price_analysis.py # Internal YAML-based price scoring
    score.py                  # Score aggregator (combines all scorers)
  runners/
    run_auto_ru.py            # Main runner with --debug --limit --no-send flags
```

## Data Flow

```
Search URL (from config)
    ↓
scraper.py → collect cards from search results (JS evaluate)
    ↓
parser.py → parse detail page (engine, transmission, drive, owners, description)
    ↓
matcher.py → filter against YAML config (brand/model/year/price/drive/region)
    ↓
valuation_parser.py → extract Auto.ru estimate (below/fair/above market)
    ↓
internal_price_analysis.py → internal YAML-based price scoring
    ↓
score.py → aggregate score (base + price + mileage + engine + transmission + equipment + bonus)
    ↓
[future] SQLite → dedup + storage
[future] Telegram → send matched cards
```

## Key Implementation Details

### 1. Card Extraction from Search

Auto.ru uses client-side rendering. `page.content()` returns raw HTML without cards. Use `page.evaluate()` with JavaScript to extract card data from the DOM after JS render:

```python
JS_EXTRACT_CARDS = """
(limit) => {
    const wrappers = document.querySelectorAll('div.ListingCars__universalSnippetWrapper');
    // extract text, links, prices from each wrapper
    return results;
}
"""
cards = page.evaluate(JS_EXTRACT_CARDS, limit)
```

**Selector:** `div.ListingCars__universalSnippetWrapper` — confirmed stable.

### 2. Detail Page Parsing

Parse `page.inner_text("body")` using label-based extraction:

```python
def _extract_field(text: str, label: str) -> str | None:
    idx = text.lower().find(label.lower())
    if idx < 0:
        return None
    rest = text[idx + len(label):].lstrip('\n\r\t ')
    return rest.split('\n')[0].strip()
```

Key fields extracted:
- Engine (full description: "2.0 л, 170 л.с., бензин")
- Transmission (Коробка/КПП)
- Drive (Привод)
- Owners (Владельцы)
- Seller type (Частное лицо / Дилер)
- Description (Комментарий продавца)
- Region (city from text)
- PTS status (ПТС)
- Configuration (Комплектация)
- VIN, Gos number

### 3. Price Parsing Bug Fix

**Critical bug:** External ID (e.g., `1132951420-8a165e88`) was being merged with price in the same line, producing `11329514201390000` instead of `1390000`.

**Fix:** Skip lines containing ID pattern before price extraction:

```python
for line in body_text.split('\n'):
    # Skip lines with external ID (digits-letters pattern)
    if re.search(r'\d{6,}-[a-f0-9]+', line, re.IGNORECASE):
        continue
    pm = re.search(r'(\d[\d\s\xa0]*\d)\s*[₽р]', line)
    # ... parse price
```

### 4. Valuation Parser (Auto.ru Estimates)

Auto.ru shows price status text ("Ниже оценки", "Справедливая цена", "Выше оценки") but the numeric estimate is rendered dynamically and not available in DOM text.

**Current approach:** Parse text status only, fallback to unknown if not found.

```python
STATUS_MAP = {
    "ниже оценки": "below_market",
    "выше оценки": "above_market",
    "справедливая": "fair_price",
}
```

**Separation:** Auto.ru valuation and internal YAML-based analysis are kept as separate blocks in the card dict. Never mix them.

### 5. Persistent Browser Profile (CAPTCHA Mitigation)

Auto.ru detects Playwright as a bot and shows CAPTCHA even with authenticated cookies.

**Solution:** Use `launch_persistent_context()` with a saved Chrome profile:

```python
context = p.chromium.launch_persistent_context(
    user_data_dir=str(PROFILE_DIR),
    headless=True,
    viewport={"width": 1280, "height": 900},
    args=["--disable-blink-features=AutomationControlled"],
)
```

**Setup:** Run `python test_auto_ru_persistent_profile.py --setup` once to create the profile and log in manually.

**Testing:** Use one browser + one context + one page with forward/back navigation between cards. Add 20-30 second delays between requests.

**Expected result:** CAPTCHA count should drop from 5/5 to ≤1/5 with persistent profile.

### 6. Single Browser Navigation Pattern

To minimize CAPTCHA, reuse one browser instance:

```python
p, context, page = create_persistent_browser(headless=True)

for url in urls:
    is_captcha, reason = navigate_to_car(page, url)
    # parse, save results
    # wait delay seconds
    # page stays open, navigate to next URL

context.close()
p.stop()
```

**Do NOT** create new browser/context/page for each card — this triggers CAPTCHA.

## Configuration

Auto.ru searches are defined in `config/auto_ru_searches.yaml`:

```yaml
sources:
  auto_ru:
    enabled: true
    searches:
      - name: kia_rio_moscow
        url: "https://auto.ru/moskva/cars/kia/rio/used/"
        brand: Kia
        model: Rio
        year_from: 2017
        year_to: 2022
        price_from: 1000000
        price_to: 2000000
        regions: ["Москва", "Московская область"]
        required:
          drive: fwd
```

## Testing

### Unit Tests
```bash
pytest tests/test_auto_ru_valuation_parser.py
pytest tests/test_internal_price_analysis.py
pytest tests/test_auto_ru_normalizer.py
```

### Integration Tests
```bash
# Persistent profile setup (first time only)
python test_auto_ru_persistent_profile.py --setup

# Run valuation test with auth
python test_auto_ru_valuation_10.py --use-auth --delay 20 --limit 10

# Quick test on 5 cars
python test_auto_ru_persistent_profile.py --delay 25 --limit 5
```

### Readiness Criteria
- auto_ru_status found in ≥ 8/10 cards
- auto_ru_estimate or low/high found in ≥ 6/10 cards
- No price merge bugs (0 occurrences)
- CAPTCHA ≤ 1 out of 10 cards

## Known Issues

### CAPTCHA
Auto.ru has aggressive bot detection. Even with:
- Authenticated cookies
- Persistent browser profile
- 20-30 second delays
- Single browser context

CAPTCHA may still appear. If persistent profile doesn't reduce CAPTCHA below 20%, consider the module temporarily unsuitable for MVP.

### Auto.ru Estimate Not Numeric
The numeric estimate value from Auto.ru is rendered via JS and not available in `page.inner_text()`. Currently only the text status ("below/fair/above") is extracted.

### Non-Russian Brands in Search
Some search URLs return cards for brands not in the main Haraba config. These pass the Auto.ru matcher but fail the internal score aggregator (no model rules). Add models to `config/awd_liquid_full_config.yaml` as needed.

## What NOT to Do

- Do not integrate into `run_daily_pipeline.py` until stable
- Do not connect Telegram until CAPTCHA is resolved
- Do not connect SQLite until valuation parsing is reliable
- Do not use CAPTCHA bypass services (against terms, adds complexity)
- Do not mix Auto.ru valuation with internal YAML scoring

## Future Work

1. **Numeric estimate extraction** — find Auto.ru estimate in JSON state or API response
2. **Detail page photo parsing** — extract photos from Auto.ru detail pages
3. **VIN parsing** — extract and validate VIN numbers
4. **Batch processing** — optimize for 50-100 cards per run
5. **Pipeline integration** — merge with Haraba pipeline after stability proven
