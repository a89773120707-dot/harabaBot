---
name: real-data-scoring-validation
description: Workflow to validate scoring system on real car cards before Telegram deployment
source: auto-skill
extracted_at: '2026-06-08T13:55:00.000Z'
---

# Real Data Scoring Validation

## Purpose

Before sending scored cards to Telegram, validate the scoring system on real data from the production pipeline — not synthetic test cards.

## Source of Real Cards

Real cards come from `haraba_bot/data/cars_db.json` — a database of cards already scraped from Haraba/Auto.ru by the main bot.

### cards_db.json Structure

```json
{
  "172875978": {
    "title": "KIA Sportage",
    "brand": "Kia",
    "model": "Sportage",
    "year": 2012,
    "mileage": 174000,
    "url": "https://haraba.ru/common/click?id=172875978&source=1",
    "first_price": 1220000,
    "last_price": 1220000,
    "score": 120,
    "status": "GONE",
    "matched_request": "Kia Sportage"
  }
}
```

### Minimum Required Fields

- `url` — link to the listing
- `title` — car name
- `price` — `last_price` or `first_price`
- `year` — model year
- `mileage` — odometer reading
- `brand` / `model` — for matching

## Preparation Pipeline

### Step 1: Filter to Our 17 Models

```python
from config_loader import load_config, get_models
from model_matcher import match_card_to_model
from cards_loader import normalize_card

config = load_config("results/awd_liquid_full_config.yaml")
matched = []

for ad_id, card in cars_db.items():
    raw = {
        "url": card.get("url"),
        "title": card.get("title"),
        "brand": card.get("brand"),
        "model": card.get("model"),
        "year": card.get("year"),
        "price": card.get("last_price") or card.get("first_price"),
        "mileage": card.get("mileage"),
    }
    norm = normalize_card(raw)
    model_id = match_card_to_model(norm, config)
    if model_id:
        norm["model_id"] = model_id
        matched.append(norm)
```

### Step 2: Run Scoring

```bash
python config_scoring_tester.py \
  --cards-file results/real_cards_matched_17.json \
  --all
```

### Step 3: Check Distribution

Expected distribution on real data (Haraba scrapes the full market):

| Decision | Expected % |
|----------|-----------|
| watch | 30-45% |
| weak | 20-35% |
| reject | 15-30% |
| good | 5-20% |
| excellent | 0-10% |

**Note:** excellent/good will be lower on real data because the market has many mediocre listings. This is expected and correct.

### Step 4: Generate TOP Lists

```python
# Sort by score descending
sorted_results = sorted(results, key=lambda r: r["score"], reverse=True)

# Top lists by decision
top_excellent = [r for r in sorted_results if r["decision"] == "excellent_candidate"]
top_good = [r for r in sorted_results if r["decision"] == "good_candidate"]
top_reject = [r for r in sorted_results if r["decision"] == "reject"]
```

### Step 5: Manual Review File

Create `manual_review_top_20.yaml` with cards for human review:

```yaml
manual_review:
  - id: card_001
    title: "Nissan Qashqai"
    model_id: nissan_qashqai_j11
    price: 1200000
    year: 2015
    mileage: 101000
    score: 100
    decision: good_candidate
    url: https://haraba.ru/...
    explanation: "..."
    bonus_reasons: ["Цена в excellent", "Пробег excellent"]
    penalty_reasons: []
    human_verdict: null  # To be filled manually
    comment: null
```

**human_verdict options:**
- `correct` — scoring is accurate
- `too_high` — score is inflated
- `too_low` — score should be higher
- `should_reject` — should have been rejected
- `should_watch` — should have been watch
- `interesting_for_call` — worth calling about

### Step 6: Telegram Preview

Generate readable messages for top good/excellent cards:

```
✅ Nissan Qashqai

Оценка: 100/100 — GOOD
Модель: nissan_qashqai_j11

Плюсы:
✅ Цена 1,200,000 в диапазоне excellent
✅ Пробег 101,000 < 140,000 (excellent)

Ссылка: https://haraba.ru/...
```

## Validation Criteria

| Criterion | Pass Condition |
|-----------|---------------|
| scored_cards | >= 50 |
| explanation present | 95%+ of cards |
| reject rate | 15-40% (not >50%) |
| good/excellent exist | at least some cards |
| no garbage in good | manual review confirms |
| false_excellent rate | <= 20% |
| false_reject rate | <= 15% |

## Common Issues

1. **All reject**: reject_if_weak too aggressive, or price ranges wrong
2. **All excellent**: scoring too soft, no conditions on excellent
3. **Binary distribution**: see `scoring-calibration-methodology`
4. **No cards match**: model_matcher aliases missing for real title formats
5. **Missing fields**: real cards often lack drive/engine/transmission — these should produce warnings, not reject

## Files

| File | Purpose |
|------|---------|
| `prepare_real_cards.py` | Filters cars_db.json to 17 models |
| `prepare_manual_review.py` | Generates TOP lists + manual review + Telegram preview |
| `results/real_cards_matched_17.json` | Filtered real cards |
| `results/manual_review_top_20.yaml` | Cards for human review |
| `results/telegram_preview_real.txt` | Formatted Telegram messages |
| `results/real_scoring_qa_report.yaml` | Full QA report |
| `results/real_cards_qa.yaml` | Card preparation QA |
