---
name: full-config-assembly
description: Merge ready_8 + price_ranges_9 + expert_rules_9 into awd_liquid_full_config.yaml with QA checks
source: auto-skill
extracted_at: '2026-06-08T13:28:00.000Z'
---

## Full Config Assembly

### Sources

| Source | File | Content |
|--------|------|---------|
| ready_8 | `config/awd_liquid_ready_8.yaml` | 8 dealer-note models with search_filters, scoring_rules, market_rules |
| price_ranges_9 | `results/price_ranges_9.yaml` | Auto.ru evaluation price ranges for 9 new models |
| expert_rules_9 | `results/expert_rules_9_ready.yaml` | Expert rules (engines, transmissions, mileage, trims, risk_check, reject) for 9 new models |

### Output

`results/awd_liquid_full_config.yaml` — 17 models in unified format

### Normalization Process

**ready_8 models** have different structure than expert_rules_9. Normalization maps:

| ready_8 field | unified field |
|---------------|---------------|
| `search_filters.brand` | `brand` |
| `search_filters.model` | `model` |
| `search_filters.year_from/to` | `years` (string "2016-2019") |
| `search_filters.mileage_max` | `mileage` (derived ranges) |
| `scoring_rules.strong_plus` | `engines.best`, `strong_bonus`, `trims.best` |
| `scoring_rules.medium_plus` | `engines.acceptable`, `trims.good` |
| `scoring_rules.penalty` | `engines.avoid`, `penalty` |
| `market_rules` | `price` + `notes` |
| `reject` | `reject` (with canonical term mapping) |

### Reject Term Canonicalization

ready_8 uses different reject terms than the 5 canonical ones. Mapping:

| ready_8 term | canonical term |
|--------------|----------------|
| taxi, commercial_use, commercial_abuse | red_autoteka |
| heavy_accident, serious_accident, airbag_deployed, structural_damage | major_accident |
| active_engine_errors, engine_overheat_history | bad_engine |
| gearbox_errors, active_gearbox_errors | bad_gearbox |
| twisted_mileage_suspected, mileage_twisted_suspected | twisted_mileage |

**Every model MUST have all 5 canonical reject terms:** red_autoteka, major_accident, bad_engine, bad_gearbox, twisted_mileage. Missing terms are auto-added during assembly.

### New Models (9)

Built from expert_rules_9 + price_ranges_9:
- `price` from price_ranges_9 target ranges
- `engines`, `transmissions`, `mileage`, `trims`, `strong_bonus`, `risk_check`, `reject` from expert_rules_9
- `status` = "ok" or "low_evaluation_sample"
- `notes` includes price_confidence, cards_checked, evaluated_cards, source

### Search Groups

```yaml
search_groups:
  ready_8: [8 model ids]
  partial_9_now_ready: [9 model ids]
  top_10: [top 10 by priority]
  second_10: [remaining 7]
```

### Config Report

```yaml
config_report:
  total_models: 17
  ready_models: 14
  low_sample_models: 3
  price_source:
    dealer_notes: 8
    auto_ru_evaluation: 9
  low_confidence_price:
    - hyundai_grand_santa_fe
    - nissan_pathfinder
    - volvo_xc90
```

### QA Checks (207 total)

All models must pass:
- ✅ 17 models, no duplicate ids
- ✅ search_groups reference existing ids only
- ✅ Each model has: price, engines, transmissions, mileage, trims, strong_bonus, risk_check (≥5), reject
- ✅ Each model reject contains: red_autoteka, major_accident, bad_engine, bad_gearbox, twisted_mileage

### Running

```bash
python build_full_config.py
```

Outputs:
- `results/awd_liquid_full_config.yaml`
- `results/awd_liquid_full_config_qa_report.yaml`
