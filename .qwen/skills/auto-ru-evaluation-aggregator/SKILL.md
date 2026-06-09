---
name: auto-ru-evaluation-aggregator
description: Scrape Auto.ru search results and market evaluation (min-max price range) per car card using Playwright
source: auto-skill
extracted_at: '2026-06-08T10:13:02.584Z'
---

## Auto.ru Evaluation Aggregator

### URL Pattern

Build search URL with `catalog_filter` and `window.location.href` navigation:

```python
from urllib.parse import quote
model_upper = model.upper().replace("-", "_")  # CX-5 -> CX_5
catalog_filter = quote(f"mark={brand_upper},model={model_upper}", safe="")

url = (
    f"https://auto.ru/moskovskaya_oblast/cars/all/"
    f"?year_from={y1}&year_to={y2}"
    f"&km_age_to=200000&pts_status=1&with_discount=false"
    f"&catalog_filter={catalog_filter}"
    f"&resolution_filter=is_pts_ok&resolution_filter=is_owners_ok"
    f"&resolution_filter=is_legal_ok&resolution_filter=is_accidents_ok"
    f"&seller_group=PRIVATE"
    f"&gear_type=ALL_WHEEL_DRIVE"
    f"&sort=cr_date-desc"
)
```

**Critical:** Navigate via `window.location.href` (not `page.goto()`) because duplicate `catalog_filter` params are dropped by Playwright:

```python
page.goto("https://auto.ru", wait_until="domcontentloaded")
page.evaluate(f"window.location.href = `{url}`")
page.wait_for_url("**auto.ru/**", timeout=30000)
page.wait_for_timeout(8000)
```

### Card Selector

```python
card_selector = "div.ListingCars__universalSnippetWrapper"
```

Parse via `inner_text()` + regex (not individual element selectors):

```python
text = card.inner_text(timeout=3000)
lines = [l.strip() for l in text.split("\n") if l.strip()]

# Price
price = int(re.search(r"([\d\s]+)\s*[₽р]", line).group(1).replace(" ", "").replace("\xa0", ""))

# Year
year = int(re.match(r"^(20\d{2})$", line.strip()).group(1))

# Mileage
mileage = int(re.search(r"([\d\s]+)\s*км", line).group(1).replace(" ", "").replace("\xa0", ""))

# Link
link = card.locator("a[href*='/cars/used/sale/']").first
href = link.get_attribute("href")
```

### Market Evaluation (popup)

**For ALL cards** (not just "Справедливая цена"), click "Подробнее про оценку стоимости" to get the min-max range:

```python
from auto_ru_evaluation_parser import parse_auto_ru_evaluation

# 1. Read badge text for delta%
badge = page.locator("[class*='OfferPriceBadgeNew']").first
badge_text = badge.evaluate("el => el.childNodes[0].textContent").strip()
# => "Выше оценки на 8%" or "Ниже оценки на 5%" or "Справедливая цена"

# 2. Open popup for min-max range
link = page.get_by_role("link", name="Подробнее про оценку стоимости").first
with page.expect_popup(timeout=10000) as popup_info:
    link.click()

popup = popup_info.value
popup.wait_for_load_state("domcontentloaded", timeout=10000)

title_elem = popup.locator(".EvaluationFormResult__title-fEw84").first
title_text = title_elem.inner_text(timeout=3000)
# => "1 800 000 – 2 100 000 ₽"
```

### Aggregation Formulas

```python
import statistics

eval_min_median = statistics.median([c["evaluation_min"] for c in cards if c.get("evaluation_min")])
eval_max_median = statistics.median([c["evaluation_max"] for c in cards if c.get("evaluation_max")])

good_buy_price = round(eval_min_median * 0.97)
suspicious_low = round(eval_min_median * 0.85)
overpriced_price = round(eval_max_median * 1.05)
```

### Price Ranges

```yaml
target:
  suspicious_low: "<{round(eval_min_median * 0.75)}"
  excellent: "<{good_buy_price}"
  good: "{good_buy_price}-{eval_min_median}"
  fair: "{eval_min_median}-{eval_max_median}"
  expensive_but_ok_if_top: "{eval_max_median}-{round(eval_max_median * 1.12)}"
  reject_if_weak: "{round(eval_max_median * multiplier)}+"
```

**Multiplier depends on confidence:**
- `status: ok` → multiplier = **1.20** (v1 was 1.07, too aggressive)
- `status: low_evaluation_sample` → multiplier = **1.25**

After scoring 678 cards, the v1 multiplier (1.07) rejected 63% of Audi Q5 and 67% of Santa Fe cards. v2 multipliers (1.20/1.25) brought reject rates to 18-30% range.

### Confidence Levels

- `confidence: medium` — 10+ cards with evaluation (status: ok)
- `confidence: low` — <10 cards (status: low_evaluation_sample, need_manual_review: true)

### Known Issues

1. **No AWD listings** — Hyundai Grand Santa Fe sometimes has 0 cards on Auto.ru
2. **Popup fails** — ~5-10% of cards may not open popup (use badge delta% as fallback)
3. **Rate limiting** — Add 1.5s delay between card opens
4. **CX-5 model name** — Auto.ru uses `CX_5` (underscore), not `CX-5`
