---
name: region-parser-v2
description: Parse Russian regions from car listing raw_text using city-to-region mapping and oblast keyword fallback for Haraba mobile sampler
source: auto-skill
extracted_at: '2026-06-09T06:44:57.544Z'
---

## Problem

The original region parser in `mobile_first_page_sampler.py` only matched major city names (Ярославль, Москва, Тверь...). It failed on:
- Moscow suburbs (Котельники, Чехов, Подольск, Электросталь, Щербинка)
- Oblast names without city (Тверская область, Тульская область)
- Small settlements (Кесова Гора → Тверская область)
- New towns (Новомосковск → Тульская область)

9 out of 30 cards returned `region: unknown`, blocking Telegram send.

## Solution: Two-tier matching in `region_parser.py`

### Tier 1: City-to-region exact mapping

```python
CITY_TO_REGION = {
    "москва": "Москва",
    "щербинка": "Москва",
    "котельники": "Московская область",
    "чехов": "Московская область",
    "подольск": "Московская область",
    "электросталь": "Московская область",
    "новомосковск": "Тульская область",
    "кесова гора": "Тверская область",
    ...
}
```

### Tier 2: Oblast keyword fallback

```python
OBLAST_KEYWORDS = {
    "тверская": "Тверская область",
    "ярославская": "Ярославская область",
    "тульская": "Тульская область",
    "владимирская": "Владимирская область",
    ...
}
```

### Matching algorithm

```python
def parse_region(text):
    t = text.lower()
    # 1. Exact city match first
    for city, region in CITY_TO_REGION.items():
        if city in t:
            return {"value": city, "normalized": region, "allowed": region in ALLOWED_REGIONS}
    # 2. Oblast keyword fallback
    for kw, oblast in OBLAST_KEYWORDS.items():
        if kw in t:
            return {"value": kw, "normalized": oblast, "allowed": True}
    return {"value": "unknown", "allowed": False}
```

### Key design decisions

1. **Cities mapped to oblasts, not city names** — "Котельники" → "Московская область" (not "Котельники"), because downstream `check_region_allowed()` matches oblast names.
2. **`"обл"` abbreviations** — include both full names ("тверская область") and abbreviated forms ("тверская обл").
3. **`allowed` boolean** — returned alongside region value so downstream can decide: `allowed=True` → send, `allowed=False` → reject, `unknown` → warning but still send (Telegram v1 market labeling).
4. **Unknown does NOT block** — for Telegram v1, unknown region is a warning, not a hard block. The goal is market labeling, not perfect filtering.

## Integration points

- `mobile_first_page_sampler.py` — replaces inline region_patterns list
- `telegram_audit.py` — fallback when card.region == "unknown", uses raw_text + mobile_detail_raw_text
- All raw_text fields must be carried through the pipeline (not stripped at audit stage)
