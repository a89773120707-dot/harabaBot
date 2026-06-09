---
name: haraba-mobile-card-sampler
description: Pattern for collecting fresh car cards from Haraba's current 17-search results via mobile detail pages — parsing engine/transmission/drive/region/owners with high coverage
source: auto-skill
extracted_at: '2026-06-08T20:47:00.000Z'
---

## Problem

Need to collect fresh car cards from the currently active 17 Haraba searches (not the stale cars_db.json). Each card needs engine/transmission/drive/region/owners for Telegram scoring.

## Architecture

```
apply_all_searches_17_report.yaml (verify 17 active)
    ↓
mobile_first_page_sampler.py
    ↓
tr.mat-row parsing (cdk-column-* cells)
    ↓
mobile detail: m.haraba.ru/search/car/{id}?source=Telegram&fromMonolith=true
    ↓
page.inner_text("body") + click "Показать все"
    ↓
parse_mobile_specs() → engine/transmission/drive/region/owners/autoteka
    ↓
coverage report + decision → Telegram ready?
```

## Key selectors (from haraba_bot)

**Table cards:** `tr.mat-row` with `.cdk-column-car`, `.cdk-column-year`, `.cdk-column-price`, `.cdk-column-mileage`, `.cdk-column-seller`, `.cdk-column-source`

**URL extraction:** Find `<a>` tags in row, extract `href`, regex `id=(\d+)` or `/(\d{6,})`

**Mobile detail URL:** `https://m.haraba.ru/search/car/{id}?source=Telegram&fromMonolith=true`

**"Показать все" click:** `page.get_by_text("Показать все").first` → `evaluate("el => el.click()")`

**Close drawer overlay:** `page.locator(".MuiDrawer-root .MuiModal-backdrop").first` → Escape if present

## Spec parsing patterns (parse_mobile_specs)

Mobile detail page raw_text format:
```
01 июня 2026 (снижение цены)ЯрославльЧастник
Hyundai Santa Fe, 2015, 2.2 AT
2 100 000 ₽
...
Модификация
2.2 CRDi 4WD AT (200 л.с.)
Тип двигателя
Дизель
Объём двигателя
2.2 л
КПП
Автомат
Привод
Полный
Владельцы
3
Состояние
Небитый
...
```

| Field | Pattern | Example |
|-------|---------|---------|
| engine | `Модификация\n(.*)` + `Тип двигателя\n(.*)` + `Объём двигателя\n(.*)` | "2.2 CRDi 4WD AT (200 л.с.) (Дизель), 2.2 л" |
| transmission | `КПП\n(.*)` | "Автомат" |
| drive | `Привод\n(.*)` | "Полный" |
| region | City name list scan | "Ярославль" |
| owners | `Владельцы\n(\d+)` | "3" |
| autoteka | "Предпроверка от Автотеки" present | "available" |
| body_state | `Состояние\n(.*)` | "Небитый" |

**Region extraction:** Scan for city names in raw_text — `["Ярославль", "Москва", "Тверь", "Владимир", "Калуга", "Рязань", "Тула"]`. City appears concatenated in the first line (e.g., `"...ЯрославльЧастник"`).

## Coverage results (30 cards from 17 searches)

| Field | Coverage |
|-------|----------|
| engine | 100% |
| transmission | 100% |
| drive | 100% |
| region | 70% |
| owners | 100% |
| autoteka_status | 73.3% |

**Telegram ready:** True (all thresholds met: engine ≥70%, transmission ≥70%, region ≥70%, drive ≥90%)

## Activation workflow (when results not visible after browser restart)

1. Open Haraba → check for `tr.mat-row`
2. If no results → open dropdown "Мои поиски" via JS click (`button.mat-warn[aria-haspopup='menu']`)
3. Scan `mat-list-option` → match against EXPECTED_ALL 17 names → click to check all
4. **Close dropdown**: Escape + clear overlay via JS (`.cdk-overlay-container` innerHTML = '')
5. **Reload page**: `page.reload(wait_until="domcontentloaded")` — Haraba restores checkbox state
6. **Scroll down**: `page.evaluate("window.scrollTo(0, 1000)")` — table is below the fold
7. Parse `tr.mat-row` cards (30 per page)

**Critical:** The table is hidden below the viewport. Without `scrollTo`, `tr.mat-row` returns 0 elements even though cards exist.

## Output files

| File | Purpose |
|------|---------|
| `results/mobile_first_page_sample.json` | 30 cards with specs, raw_text, mobile_detail_raw_text |
| `results/mobile_details_cache_17.json` | Raw card data (cache) |
| `results/mobile_fields_coverage_report.yaml` | Coverage stats + decision |
| `results/telegram_data_source_decision.yaml` | telegram_ready: true/false + blockers |

## Field source tracking

Every parsed field has `{value, source}`:
- `source: "mobile_detail"` — found in mobile detail page
- `source: "not_found"` — not found (value = "unknown")

## Commands

```bash
# Full collection (30 cards)
python mobile_first_page_sampler.py --limit 30

# Debug mode (3 cards, verbose)
python mobile_first_page_sampler.py --debug

# Dry run (check 17 active without browser)
python mobile_first_page_sampler.py --dry-run
```
