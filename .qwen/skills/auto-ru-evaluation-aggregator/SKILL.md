---
name: auto-ru-evaluation-aggregator
description: Scrape Auto.ru search results and market evaluation (min-max price range) per car card using Playwright
source: auto-skill
extracted_at: '2026-06-08T10:13:02.584Z'
updated_at: '2026-06-11T18:00:00.000Z'
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

### SPA Architecture — CRITICAL

Auto.ru is a **fully client-side SPA**. The raw HTML from `page.content()` contains **NO card data** — everything is rendered by JavaScript after page load.

- **Must use `page.evaluate()`** to extract data from the already-rendered DOM
- **Never use `page.content()`** for parsing Auto.ru cards
- `wait_until="networkidle"` **never completes** on Auto.ru (constant tracker reloads)
- Use `wait_until="domcontentloaded"` + `page.wait_for_timeout(5000-8000)` for JS render
- Close "Модели-близнецы" popup with `page.keyboard.press("Escape")` before parsing

### Card Selector

```python
card_selector = "div.ListingCars__universalSnippetWrapper"
```

**Parsing strategy: `page.evaluate()` with JS script** (confirmed: 37 cards on test search page, 2026-06-11):

```python
# Use page.evaluate() to extract from DOM innerText, NOT card.inner_text() from Python
js_script = """
() => {
    const cards = document.querySelectorAll('div.ListingCars__universalSnippetWrapper');
    return Array.from(cards).map(card => ({
        text: card.innerText,
        url: card.querySelector('a[href*="/cars/used/sale/"]')?.href || ''
    }));
}
"""
cards_data = await page.evaluate(js_script)

for card in cards_data:
    text = card['text']
    lines = [l.strip() for l in text.split('\n') if l.strip()]
```

**Parsing via regex on innerText:**

```python
# Price: (\d[\d\s]*\d)\s*[₽р] → parseInt after removing spaces
price_match = re.search(r'(\d[\d\s]*\d)\s*[₽р]', line)
price = int(price_match.group(1).replace(' ', '').replace('\xa0', ''))

# Year: \b(20\d{2})\b
year_match = re.match(r'^(20\d{2})$', line.strip())
year = int(year_match.group(1))

# Mileage: (\d[\d\s]*\d)\s*км — ⚠️ captures extra digits (year+mileage mixed), needs fix
mileage_match = re.search(r'(\d[\d\s]*\d)\s*км', line)
# Fix: if mileage == year, it's wrong — skip or parse differently
mileage = int(mileage_match.group(1).replace(' ', '').replace('\xa0', ''))

# Region: (Москва|МО|Московская обл\.|Подмосковье)
region_match = re.search(r'(Москва|МО|Московская обл\.|Подмосковье)', text)
region = region_match.group(1) if region_match else 'unknown'

# Link / ext_id: from URL pattern /(\d+-[\w-]+)/
ext_id_match = re.search(r'/(\d+-[\w-]+)/', url)
ext_id = ext_id_match.group(1) if ext_id_match else ''
```

### Brand/Model Detection

**Extract from `innerText`, NOT from URL** (URL model names are URL-encoded and unreliable):

```python
# Known brands list
BRANDS = ['Toyota', 'BMW', 'Mercedes', 'Volkswagen', 'Kia', 'Hyundai', 'Mazda', 'Ford',
          'Nissan', 'Honda', 'Audi', 'Skoda', 'Chevrolet', 'Lexus', 'Volvo', 'Mitsubishi',
          'Land Rover', 'Porsche', 'Peugeot', 'Citroen', 'Renault', 'Opel', 'Subaru']

def parse_brand_model(text):
    for brand in BRANDS:
        if brand in text:
            # Model = text after brand, before year
            after_brand = text[text.index(brand) + len(brand):].strip()
            # Model ends at year (20XX)
            model_match = re.match(r'([^\d]+)', after_brand)
            model = model_match.group(1).strip() if model_match else ''
            return brand, model
    return '', ''
```

**Known gaps:** Chinese brands (Chery, Geely, Dongfeng, Haval, FAW, MG) NOT in list — add explicitly.

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
5. **Chinese brands** — Chery, Geely, Dongfeng, Haval, FAW, MG not recognized by brand detection
6. **Mileage regex** — may capture year+mileage mixed digits; verify `mileage != year`
7. **SPA rendering** — `page.content()` is useless; always use `page.evaluate()` for DOM extraction
8. **CAPTCHA** — Auto.ru may show "Модели-близнецы" popup; close with `Escape` before parsing
