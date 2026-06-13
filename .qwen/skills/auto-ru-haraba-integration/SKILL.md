---
name: auto-ru-haraba-integration
description: Architecture and decisions for integrating Auto.ru scraper into Haraba Mini as a separate source module
source: auto-skill
extracted_at: '2026-06-12T12:00:00.000Z'
---

## Auto.ru Integration into Haraba Mini

### Core Architecture Decision

**Auto.ru is a separate source module, NOT part of the existing Haraba pipeline.**

- Directory: `app/sources/auto_ru/`
- Runner: `app/runners/run_auto_ru.py`
- The Haraba pipeline (`run_daily_pipeline.py`, `session_manager.py`, `mobile_first_page_sampler.py`) is **NOT touched** until Auto.ru works independently.

### Module Structure (UPDATED 2026-06-12)

```
app/
  sources/auto_ru/
    __init__.py              # package
    browser.py               # Playwright browser/context (separate from Haraba)
    selectors.py             # CSS selectors (CARD_SELECTOR, LINK_SELECTOR)
    normalizer.py            # parse_price, parse_mileage, parse_brand_model, overlay cleanup
    parser.py                # parse_search_card(), parse_detail_page()
    scraper.py               # scrape_search_page(), scrape_detail_page()
    urls.py                  # URL builder (stub)
    valuation_parser.py      # 3-tier: scripts/JSON → DOM → text → fallback
    valuation_page_parser.py # separate /evaluation/cars/?offer_id=... page
    full_card_parser.py      # combines detail + card status + valuation page
    persistent_browser.py    # persistent Chrome profile for CAPTCHA avoidance
  matcher/
    auto_ru_matcher.py       # brand/model/year/price/drive/region matching
  runners/
    run_auto_ru.py           # ⚠️ CLI runner (only Stage 2 implemented)
  database/
    auto_ru_repo.py          # SQLite INSERT/UPDATE with dedup by external_id
  telegram/
    auto_ru_formatter.py     # Telegram card formatter with valuation block
  config/
    auto_ru_searches.yaml    # 5 searches configured
  tests/
    test_auto_ru_normalizer.py       # ~25 unit tests
    test_auto_ru_valuation_parser.py # ~12 unit tests
```

### Key Rules

**DO NOT use Haraba session_manager for Auto.ru:**
- `session_manager.get_authenticated_page()` is Haraba-specific.
- Create a separate browser module in `browser.py` that launches a clean Playwright browser without any session state.
- Authorization on Auto.ru is NOT needed for MVP.

**DO NOT modify run_daily_pipeline.py until MVP is complete:**
- Auto.ru must first work as a standalone runner.
- Only after stable operation should it be integrated into the daily pipeline.
- Use `python -m app.runners.run_auto_ru --debug --limit 10 --no-send` for testing.

**stable_car_key for dedup:**
- Format: `source:external_id`
- Example: `auto_ru:1132811999-0a4690cd`
- Extracted via regex from URL: `/([\d]+-[a-f0-9]+)/?$`
- Do NOT do cross-source dedup by brand+model+year+price+mileage yet.

### Test URL Pattern

For initial development, use a hardcoded test URL:
```python
TEST_SEARCH_URL = "https://auto.ru/moskva/cars/ford/kuga/used/"
```

Later, URLs will be loaded from a YAML config (`config/auto_ru_searches.yaml`):
```yaml
sources:
  auto_ru:
    enabled: true
    searches:
      - name: ford_kuga_moscow
        url: "https://auto.ru/moskva/cars/ford/kuga/used/"
        brand: Ford
        model: Kuga
        year_from: 2013
        year_to: 2019
        price_from: 1000000
        price_to: 2000000
        regions:
          - Москва
          - Московская область
```

### Browser Module (browser.py)

```python
def create_auto_ru_context(headless=None) -> tuple[Page, BrowserContext, Browser]:
    """
    Create a clean Playwright browser for Auto.ru.
    No session_state, no authorization.
    """
    is_headless = headless if headless is not None else HEADLESS_DEFAULT
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=is_headless)
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
    )
    page = context.new_page()
    return page, context, browser


def open_auto_ru_page(page: Page, url: str, timeout: int = 30000) -> Page:
    page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    page.wait_for_timeout(3000)  # JS render
    return page


def save_debug_artifacts(page: Page, prefix: str, debug_dir: Path) -> dict:
    debug_dir.mkdir(parents=True, exist_ok=True)
    html_path = debug_dir / f"{prefix}.html"
    png_path = debug_dir / f"{prefix}.png"
    html_path.write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(png_path))
    return {"html": str(html_path), "screenshot": str(png_path)}
```

### Scraper Module (scraper.py)

```python
def scrape_search_page(url: str, debug=False, debug_dir=None) -> dict:
    """
    Open Auto.ru search page, save debug artifacts.
    Returns: {url, page_title, card_count, html_path, screenshot_path, status}
    """
    page, context, browser = create_auto_ru_context(headless=not debug)
    open_auto_ru_page(page, url)
    page_title = page.title()

    artifacts = {}
    if debug:
        artifacts = save_debug_artifacts(page, "auto_ru_search", debug_dir or DEFAULT_DEBUG_DIR)

    card_count = page.locator(CARD_SELECTOR).count()

    return {
        "url": url, "page_title": page_title, "card_count": card_count,
        "html_path": artifacts.get("html", ""), "screenshot_path": artifacts.get("screenshot", ""),
        "status": "ok",
    }
```

### Runner Commands

```bash
python -m app.runners.run_auto_ru                           # default run
python -m app.runners.run_auto_ru --debug --limit 10 --no-send  # debug mode
python -m app.runners.run_auto_ru --url https://auto.ru/...    # custom URL
```

### Verified Results (2026-06-11)

**Test URL 1** — Ford Kuga:
```
https://auto.ru/moskva/cars/ford/kuga/used/
```
- Returns **37 cards** using selector `div.ListingCars__universalSnippetWrapper`

**Test URL 2** — Foreign cars with filters (working test URL):
```
https://auto.ru/moskva/cars/vendor-foreign/used/transmission-automatic/
    ?year_from=2010&price_from=1000000&price_to=2000000&km_age_to=150000
    &pts_status=1&search_tag=real_photo&exp_flags=SEARCHER_VS_923_DISTANCE_SORTING
    &with_discount=false&seller_group=PRIVATE&owners_count_group=LESS_THAN_THREE
    &top_days=2
```
- Returns **37 cards**, 36/37 with price, 36/37 with region, 25/37 with recognized brand
- Data extraction works via `page.evaluate()` (NOT `page.content()` — SPA renders client-side)
- Debug artifacts: `results/debug/auto_ru_search.html`, `auto_ru_search.png`, `auto_ru_cards_parsed.json`
- No Haraba files modified (session_manager.py, run_daily_pipeline.py, mobile_first_page_sampler.py all unchanged)

### Staged Implementation Order

1. **Stage 1** (DONE 2026-06-11): Structure + Playwright open + debug artifacts ✅
2. **Stage 2** (DONE 2026-06-11): Parse cards from search results ✅
   - **33/33 pytest tests** passing
   - **37/37 cards parsed** from test URL
   - Coverage: price 100%, year 100%, mileage 97%, brand 100%, region 97%, ext_id 100%, url 100%
   - Key fixes: mileage split by `\n`, Chinese brands (20+), overlay filtering, `\xa0` handling
3. **Stage 3** (DONE 2026-06-11): Detail page parser ✅
   - `parse_detail_page()` in `app/sources/auto_ru/parser.py`
   - **4/4 cars** successfully parsed from 5 test URLs
   - Coverage: engine 100%, transmission 100%, drive 100%, owners 100%, seller_type 100%, price_status 75%, pts_status 100%, description 100%
   - Also extracts: engine_volume, engine_power, engine_fuel, configuration, gos_number, VIN
   - `scrape_detail_page()` wrapper in scraper.py
   - Debug artifacts: `results/debug/auto_ru_detail_*.html/png`
4. **Stage 4** (DONE 2026-06-11): Config + matcher ✅
   - `app/matcher/auto_ru_matcher.py` — brand/model/year/price/drive/region matching
   - `config/auto_ru_searches.yaml` — 5 searches (Kia Rio, Ford Kuga, Geely Atlas, Honda Freed, Suzuki Swift)
   - **4/19 cards matched** (21%), 15 rejected by brand mismatch
   - Rejection categorization: brand, model, year, price, drive, region
   - `match_card_to_single_config(card, search_config)` → `(matched: bool, reasons: list)`
   - `match_card_to_config(card, full_config)` → `{matched, reasons, matched_search}`
5. **Stage 5** (DONE 2026-06-11): Price analyzer + score aggregator ✅
   - `app/analyzer/price_analyzer.py` — below/fair/above market verdict with score bonus (+25/+15/5/-10)
   - `app/analyzer/score.py` — aggregates price bonus + mileage scorer + powertrain scorer + equipment scorer
   - Full pipeline verified: parse → match → analyze → score
   - Test output: `Parsed: 5, Matched: 4, Kia Rio Score: 60, Ford Kuga Score: 50`
   - Uses existing scorers: `price_scorer_v2.py`, `mileage_scorer.py`, `powertrain_scorer.py`, `equipment_scorer.py`
6. **Stage 6** (DONE 2026-06-11): Valuation page parser ✅
   - `valuation_page_parser.py` — opens `/evaluation/cars/?offer_id=...` for numeric range
   - `full_card_parser.py` — combines detail + card status + valuation page into single result
   - **4/5 cars** got full valuation with price_low/price_high/estimate_mid
   - Status parsing: "Ниже оценки на 9%" → below_market + delta_percent
   - **1/5 CAPTCHA** on valuation page
   - Raw range text captured: `2 033 000–2 336 000 ₽`
7. **Stage 7** (DONE 2026-06-11): Database dedup integration ✅
   - `auto_ru_repo.py` — `save_auto_ru_card()` with INSERT/UPDATE by external_id
   - `map_auto_ru_card_to_db()` — maps all fields including valuation to flat dict
   - `auto_ru_ad_exists()` — dedup check by source='auto_ru' + external_id
   - Stores: brand, model, year, price, mileage, engine, transmission, drive, owners
   - Stores: auto_ru_price_low/high/estimate_mid, status, delta_percent, valuation_url
   - Stores: final_verdict, recommendation, score, reasons, raw_json
8. **Stage 8** (DONE 2026-06-11): Telegram formatter ✅
   - `auto_ru_formatter.py` — `format_auto_ru_card()` with full card layout
   - Sections: title, price, Auto.ru evaluation (range + avg), status, specs, verdict, link
   - `format_short_card()` — compact preview format
   - Handles missing data gracefully (shows "—" for None)
9. **Stage 9** (PENDING): Full runner integration ❌
   - `run_auto_ru.py` currently only does Stage 2 (search page scraping)
   - Missing: matcher, detail page, valuation, scoring, dedup, save, telegram
   - **Main blocker** for MVP readiness
10. **Stage 10** (PENDING): Daily pipeline integration ❌
    - `run_daily_pipeline.py` NOT modified (per core rule)
    - Only after Stage 9 is stable

### What to Reuse from Haraba Mini

| Module | Purpose |
|--------|---------|
| `base.py` | constants, logger |
| `config_loader.py` | YAML config loading |
| `feedback_store.py` | dedup via stable_car_key |
| `price_scorer_v2.py` | price scoring |
| `mileage_scorer.py` | mileage scoring |
| `powertrain_scorer.py` | engine/transmission scoring |
| `equipment_scorer.py` | equipment scoring |
| `model_matcher.py` | card-to-model matching |
| `telegram_sender.py` | Telegram sending |
| `telegram_card_formatter.py` | card formatting |
| `region_parser.py` | region parsing |
| `legal_parser.py` | legal restrictions parsing |

### What NOT to Reuse

| Module | Why |
|--------|-----|
| `session_manager.py` | Haraba-specific authentication |
| `mobile_first_page_sampler.py` | Haraba-specific card collection |
| `run_daily_pipeline.py` | Not modified until Auto.ru MVP is stable |

### MVP Exclusions

- ❌ Auto.ru authorization (MVP doesn't need it, but production does for CAPTCHA avoidance)
- ❌ Captcha bypass
- ❌ Mass pagination (only 1st page)
- ❌ Complex ML/self-learning
- ❌ Cross-source dedup by brand+model+year
- ❌ Automatic URL generation from config (manual YAML first)
- ❌ Changes to run_daily_pipeline.py

---

## Auto.ru Valuation Parsing (2026-06-11)

### Critical Finding: Auto.ru Estimate is NOT in DOM

The numeric price estimate from Auto.ru (`auto_ru_estimate`) is **NOT available in the HTML DOM**. It is rendered via JavaScript API calls and not present in `page.content()` or `page.inner_text()`.

However, the **price status text** IS available in the page body text:
- "Ниже оценки" → `below_market`
- "Справедливая цена" / "Справедливая" → `fair_price`
- "Выше оценки" → `above_market`

### Valuation Parser Module

Location: `app/sources/auto_ru/valuation_parser.py`

Functions:
- `parse_auto_ru_valuation(page)` — main entry point, tries scripts → DOM → text → fallback
- `parse_auto_ru_valuation_from_text(text)` — parses status from full page text
- `parse_auto_ru_valuation_from_scripts(html)` — searches JSON state in script tags
- `parse_auto_ru_valuation_from_html(html)` — searches DOM markers

Return format:
```python
{
    "auto_ru_estimate": None,           # NOT available in DOM
    "auto_ru_price_low": None,          # If range found
    "auto_ru_price_high": None,         # If range found
    "auto_ru_price_status": "fair_price",  # below_market / fair_price / above_market / unknown
    "auto_ru_price_status_text": "Справедливая цена",  # Original text
    "auto_ru_price_source": "text_status",  # numeric_estimate / range_estimate / text_status / not_found
    "auto_ru_raw_text": "..."           # Context around valuation block
}
```

### Internal Price Analysis (SEPARATE from Auto.ru)

Location: `app/analyzer/internal_price_analysis.py`

**IMPORTANT: Auto.ru valuation and internal config price analysis are TWO DIFFERENT THINGS and must NOT be mixed.**

Internal price analysis uses `price_scorer_v2.py` and `awd_liquid_full_config.yaml` ranges:
```python
{
    "internal_price_verdict": "fair",           # excellent / good / fair / expensive_but_ok / above_good_price
    "internal_price_score": 0,                   # Score bonus/penalty from price_scorer_v2
    "internal_price_reason": "...",              # Human-readable explanation
    "good_price_from": 950000,
    "good_price_to": 1100000,
    "acceptable_price_from": 1100000,
    "acceptable_price_to": 1500000,
    "source": "price_scorer_v2_yaml"
}
```

### Price Parsing Bug (FIXED 2026-06-11)

**Problem:** External ID was being merged with price: `11329514201390000` instead of `1390000`.

**Root cause:** The line-by-line price search found lines containing both the external ID and the price in adjacent text.

**Fix:** In `app/sources/auto_ru/parser.py`, skip lines that contain external ID pattern:
```python
for line in body_text.split('\n'):
    if re.search(r'\d{6,}-[a-f0-9]+', line, re.IGNORECASE):
        continue  # Skip lines with external IDs
    pm = re.search(r'(\d[\d\s\xa0]*\d)\s*[₽р]', line)
    # ... parse price
```

### CAPTCHA Issue (UPDATED 2026-06-12)

**Problem:** Auto.ru detects Playwright and shows "Вы не робот?" CAPTCHA.

**Current CAPTCHA rates:**
- **Guest mode (headless):** 100% CAPTCHA on detail pages
- **With auth cookies (login_auto_ru.py):** 100% CAPTCHA (56 cookies saved, insufficient)
- **Persistent Chrome profile:** Still testing — `persistent_browser.py` + `test_auto_ru_persistent_profile.py`
- **Full card pipeline test:** 1/5 CAPTCHA on valuation page, 2/5 CAPTCHA on detail pages (~40%)

**Auth state saved:** `data/auto_ru_state.json` — contains 56 cookies + localStorage for auto.ru, yandex.ru, passport.yandex.ru

**Files:**
- `login_auto_ru.py` — semi-automatic login, saves state
- `login_auto_ru_profile.py` — persistent profile login
- `persistent_browser.py` — `launch_persistent_context()` with saved profile
- `test_auto_ru_persistent_profile.py` — test with `--setup` and `--test` modes

**Decision rule:** If persistent profile also gets >1 CAPTCHA per 5 pages → **pause Auto.ru module for MVP**

**NO CAPTCHA bypass services** — too complex and risky for MVP.

### Test Scripts

| Script | Purpose |
|--------|---------|
| `test_auto_ru_valuation_10.py` | Full 10-car valuation test with auth support |
| `test_auto_ru_auth_vs_guest.py` | CAPTCHA comparison between auth/guest |
| `test_full_report_5_v2.py` | Detailed report with single browser context |
| `login_auto_ru.py` | Save Auto.ru session for CAPTCHA avoidance |
| `tests/test_auto_ru_valuation_parser.py` | 13 unit tests for valuation parser |
| `tests/test_internal_price_analysis.py` | 6 unit tests for internal price analysis |

### Readiness Criteria (UPDATED 2026-06-12)

| Component | Status | % Ready |
|-----------|--------|---------|
| Browser / Playwright | ✅ Works | 100% |
| Search page scraping | ✅ 37/37 cards | 100% |
| Normalizer | ✅ + Chinese brands | 100% |
| CSS selectors | ✅ Confirmed | 100% |
| Detail page parser | ✅ engine/transmission/drive/owners | 95% |
| Valuation parser (text) | ✅ 3-tier fallback | 90% |
| Valuation page | ✅ Works but CAPTCHA | 70% |
| Full card parser | ✅ Combines all | 90% |
| Matcher | ✅ brand/model/year/price/region/drive | 100% |
| YAML config | ✅ 5 searches | 60% (expand to 17?) |
| SQLite repo | ✅ INSERT/UPDATE/dedup | 100% |
| Telegram formatter | ✅ Full format | 100% |
| Persistent browser | ✅ CAPTCHA detection | 80% |
| **Runner** | ⚠️ Only Stage 2 | **30%** |
| **Scoring integration** | ❌ Not in runner | 0% |
| **Telegram sender** | ❌ Not integrated | 0% |
| **Daily pipeline** | ❌ Not touched | 0% |
| **Feedback/V2 buttons** | ❌ Not implemented | 0% |
| **CAPTCHA avoidance** | ❌ ~40% rate | 0% |

**Main blockers:**
1. **CAPTCHA** — blocks ~40% of detail/valuation pages
2. **Runner incomplete** — only collects search cards, no full pipeline
3. **Scoring not wired** — existing scorers not called in runner
4. **Telegram not integrated** — formatter ready but sender not connected

**Next priority:**
1. Complete `run_auto_ru.py` — full cycle: search → detail → valuation → matcher → score → dedup → save
2. Wire scoring system into runner
3. Integrate Telegram sender + feedback buttons
4. Resolve CAPTCHA (persistent profile test or pause module)
5. Expand config to more models (optional)
6. Daily pipeline — only after runner is stable
