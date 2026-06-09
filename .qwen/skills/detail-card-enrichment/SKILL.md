---
name: detail-card-enrichment
description: Enrich raw car cards with engine, transmission, drive, region before scoring/Telegram — hybrid approach with cache/title/search-filter fallback
source: auto-skill
extracted_at: '2026-06-08T17:58:35.000Z'
---

## Problem

cars_db.json contains basic card data (title, price, year, mileage, url) but **lacks**: engine, transmission, drive, region. These are required for Telegram cards and accurate scoring.

## Enrichment hierarchy (3 tiers)

### Tier 1: source_enrichment_cache (best)

`haraba_bot/data/source_enrichment_cache.json` contains engine/transmission/drive for auto.ru cards.

**Linking:** `resolved_urls.json` maps haraba_id → source_url → source_enrichment_cache.
**Limitation:** Only ~14 entries, mostly auto.ru. Most resolved_urls point to Avito — **0 overlap** between resolved_urls and source_enrichment_cache URLs.

### Tier 2: Title parsing (fallback)

Parse title from cars_db for engine/transmission.
**Reality:** cars_db.title is usually just "KIA Sportage" — no engine info. Title parsing rarely succeeds.

### Tier 3: Search filter defaults (MVP v1)

For all cards from AWD-saved searches:
- `drive = "awd"`, `drive_source = "search_filter"` — confirmed
- `engine = "unknown"` — TODO: detail scraper
- `transmission = "unknown"` — TODO: detail scraper
- `region = "unknown"` — cars_db.seller_location is empty

## Browser enrichment (NOT for MVP v1)

Opening `m.haraba.ru/search/car/{id}` via authenticated session works but:
- Takes 30-35 seconds per card
- 160 cards = ~80-90 minutes
- Pages may be removed/404
- Session may expire mid-batch

**Only use browser enrichment when:** < 20 cards, confirmed session, can tolerate 30s/card.

### Browser parsing (when needed)

```python
from session_manager import get_authenticated_page

page, context, browser = get_authenticated_page()
page.goto(f"https://m.haraba.ru/search/car/{car_id}", wait_until="domcontentloaded", timeout=20000)
page.wait_for_timeout(3000)

show_all = page.get_by_text("Показать все").first
if show_all.count() > 0:
    show_all.click()
    page.wait_for_timeout(3000)

body = page.inner_text("body", timeout=5000)
```

Fields found after "Показать все": Модификация, Тип двигателя, Объём двигателя, КПП, Привод, Тип кузова, Цвет, Руль, Состояние, Владельцы, Пробег, Поколение.

## MVP v1 enrichment (what we use NOW)

```python
# detail_card_enricher_v3.py — < 1 second for 160 cards
enriched = {
    "drive": "awd",
    "drive_source": "search_filter",
    "engine": "unknown",
    "engine_source": "not_available_mvp",
    "transmission": "unknown",
    "transmission_source": "not_available_mvp",
    "region": "unknown",
    "region_source": "unknown",
}
```

## Important rules

1. **Enrichment BEFORE scoring**
2. **Manual transmission filter** — skip manual cars
3. **Drive confidence HIGH** from search_filter
4. **resolved_urls → source_enrichment_cache has 0 overlap** (resolved = Avito, enrichment = auto.ru)
5. **Browser enrichment is last resort** — only for <20 cards

## Files

| File | Purpose |
|------|---------|
| `detail_card_enricher_v3.py` | MVP v1: drive from search filter (160 cards in <1s) |
| `enriched_cards_mvp.json` | Current enriched dataset |
| `enrichment_mvp_report.yaml` | QA report |
