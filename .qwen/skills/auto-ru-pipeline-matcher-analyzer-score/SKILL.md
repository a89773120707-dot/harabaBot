---
name: auto-ru-pipeline-matcher-analyzer-score
description: Auto.ru pipeline architecture: matcher filters → price analyzer (text status fallback) → score aggregator
source: auto-skill
extracted_at: '2026-06-11T14:40:00.000Z'
---

# Auto.ru Pipeline: Matcher → Analyzer → Score

## Architecture

```
parse_detail_page()
    ↓
matcher (brand/model/year/price/drive/region)
    ↓
price_analyzer (text status fallback)
    ↓
score_aggregator (existing scorers + price bonus)
    ↓
result: {score, level, verdict, reasons}
```

**Critical rule:** Matcher MUST run first. Price analyzer and scorer only run on matched cards. This filters 80-90% of noise before expensive analysis.

## Matcher (`app/matcher/auto_ru_matcher.py`)

```python
from app.matcher.auto_ru_matcher import load_auto_ru_config, match_card_to_single_config

config = load_auto_ru_config("config/auto_ru_searches.yaml")
matched, reasons = match_card_to_single_config(card, search_config)
```

Checks:
- `brand` (case-insensitive substring match)
- `model` (case-insensitive substring match)
- `year_from` / `year_to` range
- `price_from` / `price_to` range
- `regions` list (normalized: МО → Московская область)
- `required.drive` (full/fwd/rwd)

Returns: `(matched: bool, reasons: list[str])`

### Auto.ru Search Config YAML

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
        regions:
          - Москва
          - Московская область
        required:
          drive: fwd
```

## Price Analyzer (`app/analyzer/price_analyzer.py`)

**MVP v2 — Three-tier fallback:**

```python
from app.analyzer.price_analyzer import analyze_price

result = analyze_price(card)
# card must have: price, auto_ru_estimate, auto_ru_price_status
```

### Tier 1: Numeric estimate from Auto.ru (ideal)
If `auto_ru_estimate` (number) is available → calculate exact discount %.
- `>10% below` → verdict=below_market, bonus=+25
- `5-10% below` → verdict=below_market, bonus=+15
- `±5%` → verdict=fair_price, bonus=+5
- `>10% above` → verdict=above_market, bonus=-10

### Tier 2: Text status from Auto.ru (fallback)
If numeric estimate is NOT available but text status IS → use status mapping:
- `"below_estimate"` → verdict=below_market, bonus=+15
- `"fair"` → verdict=fair_price, bonus=+5
- `"above_estimate"` → verdict=above_market, bonus=-10

### Tier 3: Unknown (no data)
If neither is available → verdict=unknown, bonus=0

**IMPORTANT:** Auto.ru numeric estimate (`auto_ru_estimate`) is NOT available in the DOM. It is rendered dynamically via JS or loaded via API. The text status IS available in plain text via `_extract_field(text, "Оценка")` patterns.

### Score Aggregator (`app/analyzer/score.py`)

Combines existing scorers with price analyzer bonus:

```python
from app.analyzer.score import aggregate_score

result = aggregate_score(card, config, price_analysis)
```

Pipeline:
1. `match_card_to_model(card, config)` → model_id
2. `score_price()` + `score_mileage()` + `score_engine()` + `score_transmission()` + `score_equipment()`
3. Add `price_analysis["score_bonus"]`
4. Base score = 50, clamp to 0-100

Output:
```python
{
    "score": 60,
    "level": "good",  # hot(≥80) / good(≥60) / watch(≥40) / weak(<40)
    "reasons": ["above_market", "engine: recommended (best)"],
    "breakdown": {"base": 50, "price": -15, "mileage": 0, "engine": 15, "transmission": 10, "equipment": 0, "price_bonus": 5}
}
```

## Test Pattern (`test_full_report_5_v2.py`)

Use ONE browser for all 5 cars to avoid CAPTCHA and speed up:

```python
p = sync_playwright().start()
browser = p.chromium.launch(headless=True)

for car in TEST_CARS:
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    # ... process
    ctx.close()

browser.close()
p.stop()
```

## CAPTCHA Warning

Auto.ru shows "Вы не робот?" (captcha) for rapid sequential detail page requests.

**Mitigation:**
- Use ONE browser with sequential contexts (not parallel)
- Add `wait_for_timeout(1500-3000)` between page opens
- Limit batch size to 5-10 per run
- If CAPTCHA appears, wait 30+ seconds before retry

## Verified Results (2026-06-11)

Test: 5 detail pages → matcher → analyzer → score

| Car | Matched | Verdict | Score | Notes |
|-----|---------|---------|-------|-------|
| Honda Freed | ✅ | below_market (text) | N/A | No model in main config |
| Kia Rio | ✅ | fair_price (text) | 65/good | Engine +15, Trans +10 |
| Geely Atlas | ✅ | fair_price (text) | N/A | No model in main config |
| Suzuki Swift | ❌ | - | - | CAPTCHA (Вы не робот?) |
| Ford Kuga | ✅ | above_market (text) | 20/weak | Price -30 (above config max) |

**Key finding:** "выше хорошей цены на 290к ₽" comes from `price_scorer_v2.py` (our YAML config ranges), NOT from Auto.ru evaluation. This is correct behavior — our config defines what WE consider fair, independent of Auto.ru's market estimate.

## File Locations

| File | Purpose |
|------|---------|
| `app/matcher/auto_ru_matcher.py` | Matcher with normalize_drive/normalize_region |
| `app/analyzer/price_analyzer.py` | Price analyzer with 3-tier fallback |
| `app/analyzer/score.py` | Score aggregator using existing scorers |
| `config/auto_ru_searches.yaml` | Auto.ru search configurations |
| `config/awd_liquid_full_config.yaml` | Main scoring config (must include model rules) |
| `test_full_report_5_v2.py` | Full pipeline test (single browser, 5 cars) |
| `test_auto_ru_estimate.py` | Estimate availability diagnostic |
