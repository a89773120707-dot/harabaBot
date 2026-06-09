---
name: haraba-filter-values-reference
description: Correct Haraba.ru filter value mappings — regions, transmission, legal restrictions, drive types, verified 2026-06-07
source: auto-skill
extracted_at: '2026-06-07T19:11:09.087Z'
---

# Haraba Filter Values Reference

## Regions (7 options in mat-select)

Real Haraba names — NOT the full Russian names from configs:

| Config Value | Haraba Value | Notes |
|-------------|-------------|-------|
| Москва + Московская область | Москва и МО | **Combined** — one option |
| Ярославская область | Ярославская обл. | **Abbreviated** |
| Тверская область | Тверская обл. | Abbreviated |
| Владимирская область | Владимирская обл. | Abbreviated |
| Калужская область | Калужская обл. | Abbreviated |
| Рязанская область | Рязанская обл. | Abbreviated |
| Тульская область | Тульская обл. | Abbreviated |

**Wrong** (will NOT match): `Москва`, `Московская область`, `Ярославская область`
**Correct**: `Москва и МО`, `Ярославская обл.`, `Тверская обл.`, etc.

## Transmission (4 options)

| Config Value | Haraba Value | Notes |
|-------------|-------------|-------|
| automatic | Автомат | |
| dsg | Робот | DSG is classified as Robot |
| manual | Механика | |
| cvt | Вариатор | |
| robot | Робот | |

Can be multi-select: `['automatic', 'dsg', 'cvt']` → select 3 options.

## Drive Type

| Config Value | Haraba Value | Notes |
|-------------|-------------|-------|
| awd | Полный | |
| 4matic | Полный | Maps to same as awd |
| fwd | Передний | |
| rwd | Задний | |

## Legal Restrictions

| Config Value | Haraba Value | Notes |
|-------------|-------------|-------|
| none | Без ограничения | **SINGULAR** — NOT "ограничений" |

Only 2 options in dropdown: "Без ограничения" and "Только с ограничением"

## Seller Type

| Config Value | Haraba Value |
|-------------|-------------|
| private | Частник |
| dealer | Дилер |

## Owners Range

| Config Value | Haraba Value |
|-------------|-------------|
| 1-3 | 1-3 |
| 1-2 | 1-2 |
| 1 | 1 |

## Condition

| Config Value | Haraba Value |
|-------------|-------------|
| not_damaged | Кроме битых |

## Mileage (input field)

`#srch_fltr_mileage_to` — input field for maximum mileage (e.g., `200000`, `170000`)

## Recommended Config Pattern

```yaml
search_filters:
  drivetrain: awd
  transmission: ['automatic', 'dsg', 'cvt']  # or ['cvt'] for CVT-only models
  regions:
    - Москва и МО
    - Ярославская обл.
    - Тверская обл.
    - Владимирская обл.
    - Калужская обл.
    - Рязанская обл.
    - Тульская обл.
  legal_restrictions: none
  seller_type: private
  owners_range: '1-3'
  condition: not_damaged
  mileage_max: 200000
```

## Selector Summary

| Haraba Element | CSS Selector | Type |
|---------------|-------------|------|
| Regions | `#srch_fltr_region` | mat-select (multi) |
| Drivetrain | `#srch_fltr_drive_type` | mat-select |
| Transmission | `#srch_fltr_transmission` | mat-select (multi) |
| Legal Restrictions | `#srch_fltr_restrictions` | mat-select |
| Seller Type | `#srch_fltr_salers_type` | mat-select |
| Owners Range | `#srch_fltr_owners` | mat-select |
| Condition | `#srch_fltr_confition` | mat-select |
| Mileage Max | `#srch_fltr_mileage_to` | input (text) |
