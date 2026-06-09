---
name: telegram-pipeline-dry-run
description: Pattern for running Telegram pipeline dry-run on fresh mobile cards — loader integration, normalize_card region fix, and preview validation
source: auto-skill
extracted_at: '2026-06-08T21:04:00.000Z'
---

## Problem

After collecting fresh car cards via mobile_first_page_sampler.py, need to run the Telegram scoring pipeline and verify card appearance before sending to Telegram.

## Commands

```bash
# Dry-run on fresh mobile cards
python run_telegram_pipeline.py --cards results/mobile_first_page_sample.json --dry-run

# With limit
python run_telegram_pipeline.py --cards results/mobile_first_page_sample.json --dry-run --limit 10

# With custom output
python run_telegram_pipeline.py --cards results/mobile_first_page_sample.json --dry-run --out results/mobile_scoring_dry_run.yaml
```

## load_mobile_sample integration

`run_telegram_pipeline.py` was extended with `--cards` argument. When provided, it calls `load_mobile_sample()` instead of loading the old `real_cards_matched_17.json`.

The function transforms mobile sample cards (with specs from mobile detail pages) into the pipeline format:

| Mobile field | Pipeline field | Transformation |
|---|---|---|
| specs.transmission.value | transmission | "Автомат" → "automatic", "Робот" → "dsg", "Вариатор" → "cvt" |
| specs.drive.value | drive | "Полный" → "awd" |
| specs.region.value | region | direct |
| specs.engine.value | engine | direct (combined: Модификация + Тип + Объём) |
| specs.owners.value | owners | direct |
| raw_text + mobile_detail_raw_text | features | keyword scan for leather, panorama, 7_seats, etc. |

## Critical fix: normalize_card must pass region

`cards_loader.py` `normalize_card()` originally did NOT pass the `region` field. This caused 0/16 cards with region in the dry-run.

**Fix:** Add `"region": raw.get("region", "unknown")` to the return dict in `normalize_card()`.

```python
return {
    ...
    "region": raw.get("region", "unknown"),  # ← MUST be present for region filter
    ...
}
```

Without this fix, `extract_region_from_card()` returns "unknown" for all cards.

## Dry-run validation checklist

After running dry-run, verify:

1. **Model/year/price visible at top** — ✅ `Mercedes-Benz GLK (2012)`, `💰 Цена: 1,700,000 ₽`
2. **Engine/transmission/drive visible** — ✅ `Двигатель: 2.0 TDI...`, `Коробка: dsg`, `Привод: AWD ✅`
3. **Price ranges visible** — ✅ `Excellent: до 1726600 ₽`, `Good: 1726600-1780000 ₽`
4. **Score explanation visible** — ✅ `💰 Цена: +35 —`, `🛣 Пробег: -10 —`
5. **No manual transmission cards** — ✅ 0 skipped_manual
6. **Links present** — ✅ `🔗 https://haraba.ru/common/click?id=...`
7. **Region coverage** — should be >0% (check `cards_with_region` in summary)

## Output files

| File | Purpose |
|------|---------|
| `results/mobile_telegram_preview.md` | Readable preview of all candidate cards |
| `results/mobile_telegram_dry_run_report.yaml` | Structured stats: sent_candidates, skipped_*, cards_with_* |

## Decision matrix

| Metric | Good | Concern |
|--------|------|---------|
| sent_candidates / total | 40-60% | <20% (scoring too harsh) or >80% (scoring too soft) |
| good_candidate | 5-15% | 0% (excellent conditions too strict) |
| skipped_manual | expected | >10% (need to filter manual at search level) |
| skipped_region | expected | >30% (region filter too narrow) |
| cards_with_engine | >90% | <70% (mobile parsing broken) |
| cards_with_region | >70% | <50% (region extraction needs fix) |

## Next step after dry-run

If preview looks good:
1. Add Telegram sender with inline buttons (🟢 Купить / 🟡 Посмотреть / 🔴 Скипнуть)
2. Add feedback handler for button clicks
3. Run `--send --limit 3` for real test
4. Monitor for 5-7 days, collect feedback, recalibrate scoring
