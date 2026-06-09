---
name: config-scoring-system
description: Multi-module scoring system for evaluating car cards against awd_liquid_full_config.yaml
source: auto-skill
extracted_at: '2026-06-08T13:28:00.000Z'
---

## Config Scoring System

### Overview

Evaluates individual car cards against `awd_liquid_full_config.yaml` using a multi-module pipeline:

```
card → normalize → match_model → reject_check → price_score + mileage_score + engine_score + trans_score + equipment_score → decision
```

### Modules

| Module | File | Purpose |
|--------|------|---------|
| config_loader | `config_loader.py` | Load and validate YAML config |
| cards_loader | `cards_loader.py` | Load and normalize cards (price/mileage/year/drive/transmission) |
| model_matcher | `model_matcher.py` | Map card → model_id using brand/model + aliases |
| reject_engine | `reject_engine.py` | Reject check (runs BEFORE scoring) |
| price_scorer | `price_scorer.py` | Score against price ranges (excellent/good/fair/expensive/reject) |
| mileage_scorer | `mileage_scorer.py` | Score against mileage ranges (excellent/good/penalty/reject) |
| powertrain_scorer | `powertrain_scorer.py` | Engine + transmission scoring (best/acceptable/avoid) |
| equipment_scorer | `equipment_scorer.py` | Trim + options scoring (strong_bonus list) |

### Scoring Pipeline

1. **Base score = 50**
2. **Reject check FIRST** — if rejected, score = 0, decision = "reject"
3. **Add/subtract** from each scorer
4. **Clamp** to 0–100
5. **Decision thresholds (v4)**:
   - `excellent_candidate`: score ≥ 80 **AND** price in excellent/good **AND** mileage in excellent/good **AND** ≥2 strong_bonus **AND** no warnings
   - `good_candidate`: score ≥ 80
   - `watch`: score ≥ 55
   - `weak`: score ≥ 40
   - `reject`: score < 40 or hard_reject

**Important:** The multi-condition excellent prevents binary scoring. Without it, ~34% of cards become excellent and ~33% become reject. With v4 conditions: excellent ~0.7%, good ~37%, watch ~29%, weak ~15%, reject ~18% (on 678 synthetic cards). The excellent rate is artificially low on synthetic data because random prices rarely fall in excellent/good range.

### Reject Conditions

- `red_autoteka` — autoteka_color = "red"
- `major_accident` — explicit accident keywords (airbag, geometry, frame damage, structural damage, битый, после дтп)
- `bad_engine` / `bad_gearbox` — found in title/description
- `twisted_mileage` — twisted/скручен keywords
- `no_awd_when_required` — model requires AWD but card has FWD
- `taxi_or_commercial` — taxi/такси/commercial keywords

**Important:** Reject keywords for accident should NOT include generic words like "damage" — use only explicit markers: `airbag`, `подушк`, `geometry`, `геометр`, `frame damage`, `structural damage`, `битый`, `после дтп`, `после аварии`.

### Price Scoring (v2)

Uses model's `price` block with ranges (from `price_ranges_9_v2.yaml`):
- `suspicious_low: "<X"` → **-15** (was -25 in v1)
- `excellent: "<Y"` → **+35** (was +40)
- `good: "Y-Z"` → **+20** (was +25)
- `fair: "Z-W"` → **+5**
- `expensive_but_ok_if_top: "W-V"` → **-15** (was -10)
- `reject_if_weak: "V+"` → **-30** (was -50, NO longer auto-reject)

**Returns:**
```python
{
    "score": int,            # -30..+35
    "category": str,         # "excellent" / "good" / "fair" / "expensive_but_ok_if_top" / ...
    "explanation": str,      # human-readable: "Цена 1,510,000 — дорого, близко к верхней границе..."
    "price_status": str,     # "отличная цена" / "хорошая цена" / "fair" / "дорого, но допустимо" / "выше допустимого"
}
```

**Expensive range detail:** position within range determines text:
- ratio > 0.7 → «дорого, близко к верхней границе допустимого»
- ratio > 0.4 → «дорого, но допустимо»
- ratio <= 0.4 → «дорого, но в пределах допустимого»

Full text: «OK только если топ-комплектация и хорошее состояние» (never truncated).

### Transmission Scoring — normalization

`score_transmission()` normalizes raw UI values before matching against `transmissions.best`:
- «Автомат» / «AT» / «акпп» / «автоматическая» → matches «automatic»
- «Робот» / «DSG» / «S tronic» → matches «dsg»
- «Вариатор» / «CVT» → matches «cvt»
- «Механика» / «мкпп» → matches «manual»

This ensures that raw values like «Автомат» (from mobile detail page) correctly match `best: [automatic]` in config and get +10.

**Returns explanation with display name:** «Коробка 'автомат' — рекомендованная (best)»

### Equipment Scoring

Key bonus points:
| Option | Points |
|--------|--------|
| 7_seats | 15 |
| top_trim (match) | 15 |
| good_trim (match) | 8 |
| panorama | 8 |
| s_line / r_line / amg_package | 10 |
| leather | 6 |
| ventilation | 6 |
| 360_camera | 8 |
| webasto | 8 |
| adaptive_cruise | 8 |
| green_autoteka | 10 |
| executive | 10 |
| rear_camera | 5 |
| keyless | 5 |

### Card Normalization

`cards_loader.normalize_card()` converts raw card to:
- `price` → int
- `mileage` → int
- `year` → int
- `drive` → "awd" / "fwd" / "rwd" / "unknown"
- `transmission` → "automatic" / "dsg" / "cvt" / "manual" / "unknown"
- `autoteka_color` → "red" / "green" / "yellow" / "unknown"
- `features` → list of detected options (leather, panorama, 7_seats, etc.)
- `missing_fields` → list of missing critical fields

### Feature Detection

Features are detected by keyword matching in `title + description`:
```python
feature_keywords = {
    "7_seats": ["7 мест", "7-seat", "seven_seat", "трёхрядн"],
    "leather": ["кож", "leather"],
    "panorama": ["панорам", "panorama"],
    ...
}
```

### Model Matching

`model_matcher.py` uses:
1. Direct (brand, model) match from config
2. Title search via aliases dictionary
3. Partial brand+model in title

Aliases example:
```python
ALIASES = {
    "kia_sorento_prime": ["sorento prime", "соренто прайм"],
    "volkswagen_touareg_nf": ["touareg", "туарег"],
    "mazda_cx5": ["cx-5", "cx5", "сх-5"],
    ...
}
```

### Running

```bash
python config_scoring_tester.py --limit 1              # 1 card
python config_scoring_tester.py --limit 5              # 5 cards (default)
python config_scoring_tester.py --limit 15             # 15 cards
python config_scoring_tester.py --cards-file results/test_cards_500.json --all   # all cards from file
```

Output: `results/config_scoring_test_{N}.yaml` with summary + model_distribution.

### Calibration Process

Calibration was done iteratively on 678 synthetic cards (v1→v2→v3→v4):

| Version | excellent | good | watch | weak | reject |
|---------|-----------|------|-------|------|--------|
| v1 | 33.9% | 15.3% | 9.4% | 8.4% | 32.9% |
| v4 (synthetic) | 0.7% | 36.7% | 29.2% | 14.9% | 18.4% |
| v4 (real 160 cards) | 0% | 5.6% | 37.5% | 34.4% | 22.5% |
| target | 5-12% | 15-25% | 25-40% | 15-30% | 15-30% |

### Real Data Results (160 cards from cars_db.json)

On real Haraba data, distribution shifts toward watch/weak (expected — the market has many mediocre listings):
- **watch: 37.5%** ✅ (target 25-40%)
- **reject: 22.5%** ✅ (target 15-30%)
- **weak: 34.4%** ⚠️ slightly above target
- **good: 5.6%** ⚠️ below target — excellent/good are genuinely rare finds
- **excellent: 0%** ❌ — no real cards met ALL conditions (price excellent/good + mileage excellent/good + ≥2 bonuses)

Top real good cards: Nissan Qashqai (score=100), VW Tiguan (score=90), Mazda CX-5 (score=90) — all with excellent prices and low mileage.

See `real-data-scoring-validation` skill for the real data testing workflow.
