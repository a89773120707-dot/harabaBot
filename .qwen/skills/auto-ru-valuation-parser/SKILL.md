---
name: auto-ru-valuation-parser
description: Auto.ru valuation parser — persistent profile, separate valuation page, unified card structure
source: auto-skill
extracted_at: '2026-06-11T20:00:00.000Z'
---

# Auto.ru Valuation Parser

## Key Findings

### CAPTCHA Problem
- **Regular Playwright context**: 100% CAPTCHA rate (5/5 blocked) even with authorized cookies
- **Persistent Chrome profile**: Reduced CAPTCHA to 40% (2/5 blocked)
- **Solution**: Use `launch_persistent_context()` with `user_data_dir=results/auto_ru_chrome_profile/`

### Valuation Page Architecture
Auto.ru does NOT show numeric price range on the detail page. The range is on a separate page:

```
Detail page: https://auto.ru/cars/used/sale/ford/kuga/1132964187-34034386/
  → Shows only status text: "Выше оценки на 27%"
  
Valuation page: https://auto.ru/evaluation/cars/?offer_id=1132964187-34034386&utm_source=card_offer
  → Shows numeric range: "1 269 000–1 420 000 ₽"
```

### Parsing Flow
1. Open detail page → parse seller_price, brand, model, year, external_id
2. Extract status text from detail page: "Выше оценки на X%" → parse status + delta_percent
3. Build valuation URL: `https://auto.ru/evaluation/cars/?offer_id=<external_id>&utm_source=card_offer`
4. Wait 3-5 seconds (avoid bot detection)
5. Open valuation page → parse price range "X–Y ₽"
6. Calculate estimate_mid = (low + high) / 2

### Unified Card Structure

```json
{
  "seller_price": 1800000,
  "brand": "Ford",
  "model": "Kuga",
  "year": 2017,
  "mileage": 136850,
  "external_id": "1132964187-34034386",
  "stable_car_key": "auto_ru:1132964187-34034386",
  "auto_ru_valuation": {
    "valuation_url": "https://auto.ru/evaluation/cars/?offer_id=...",
    "price_low": 1269000,
    "price_high": 1420000,
    "estimate_mid": 1344500,
    "status": "above_market",
    "status_text": "Выше оценки на 27%",
    "delta_percent": 27,
    "source": "valuation_page",
    "raw_range_text": "1 269 000–1 420 000 ₽",
    "error": null
  }
}
```

### Important: estimate_mid vs Auto.ru Estimate
- `price_low` and `price_high` come directly from Auto.ru
- `estimate_mid` is **calculated** as (low + high) / 2 — it is NOT the Auto.ru estimate
- In Telegram: show "Auto.ru оценка: 1 269 000–1 420 000 ₽, Средняя: ~1 344 500 ₽"

### Error Handling

| Source | When | Error field |
|--------|------|-------------|
| `valuation_page` | Range found on valuation page | null |
| `card_status_only` | Status found but no range on valuation page | "range_not_found_on_valuation_page" |
| `captcha` | CAPTCHA detected on detail or valuation page | "captcha" |
| `error` | Page load failed | "valuation_page_error: ..." |
| `no_external_id` | external_id empty | "no_external_id" |

### Files
- `app/sources/auto_ru/persistent_browser.py` — persistent Chrome browser helper
- `app/sources/auto_ru/valuation_page_parser.py` — parse price range from valuation page
- `app/sources/auto_ru/full_card_parser.py` — unified card parser (detail + valuation)
- `login_auto_ru.py` — save session cookies (insufficient alone)
- `test_auto_ru_full_card_with_valuation.py` — integration test

### Performance
- Delay between cars: 25 seconds (reduces CAPTCHA)
- Delay between detail → valuation: 3 seconds
- Success rate with persistent profile: ~60% (3/5 cars with full valuation)

### How to Setup Persistent Profile
```bash
python test_auto_ru_persistent_profile.py --setup
# Opens visible browser — login to Auto.ru, close browser
# Profile saved to results/auto_ru_chrome_profile/
```

### How to Run Tests
```bash
# Full card parser test
python test_auto_ru_full_card_with_valuation.py --limit 5 --delay 25

# Check report
cat results/debug/auto_ru_full_card_valuation_report.json
```

### CAPTCHA Handling
- If CAPTCHA on detail page: save screenshot, skip to next car
- If CAPTCHA on valuation page: save status from card, set source="captcha"
- Never retry same URL immediately (increases CAPTCHA risk)
