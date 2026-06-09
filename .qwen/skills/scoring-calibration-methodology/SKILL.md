---
name: scoring-calibration-methodology
description: Iterative calibration process for car card scoring system to avoid binary excellent/reject distribution
source: auto-skill
extracted_at: '2026-06-08T13:45:00.000Z'
---

## Scoring Calibration Methodology

### Problem

Initial scoring produced binary distribution: ~34% excellent, ~33% reject, with watch/weak nearly empty. This means the scorer couldn't distinguish between good-but-not-great cards.

### Root Causes

1. **reject_if_weak too aggressive** — `max_median * 1.07` rejected most cards above market price
2. **Reject penalty too harsh** — `-50` with auto-reject killed any nuanced scoring
3. **No conditions for excellent** — Any card with score >= 85 became excellent, regardless of actual quality

### Calibration Steps

#### Step 1: Soften reject_if_weak

Change from `max_median * 1.07` to:
- `max_median * 1.20` for status=ok models
- `max_median * 1.25` for low_evaluation_sample models

#### Step 2: Reduce penalty magnitudes

| Range | v1 | v2 |
|-------|-----|-----|
| excellent | +40 | +35 |
| good | +25 | +20 |
| fair | +5 | +5 |
| expensive | -10 | -15 |
| reject_if_weak | -50 (auto-reject) | -30 (penalty only) |
| suspicious_low | -25 | -15 |

#### Step 3: Add conditions for excellent

```python
excellent_candidate only if ALL:
  - score >= 80
  - price in [excellent, good]
  - mileage in [excellent, good]
  - strong_bonus_count >= 2
  - no warnings
```

#### Step 4: Adjust thresholds

```python
good_candidate: score >= 80    # was 70
watch:          score >= 55    # unchanged
weak:           score >= 40    # unchanged
reject:         score < 40     # unchanged
```

### Testing Process

1. Generate 500+ synthetic cards across all 17 models with realistic price/mileage ranges
2. Run scoring with `config_scoring_tester.py --cards-file results/test_cards_500.json --all`
3. Check distribution against targets:
   - excellent: 5-12%
   - good: 15-25%
   - watch: 25-40%
   - weak: 15-30%
   - reject: 15-30%
4. Iterate until 3+ categories are in target range

### Key Insight

**Never calibrate on <100 cards.** With 15 cards, the Q5 reject rate looked like a bug; with 678 cards, it was confirmed as a systematic issue across multiple models.

### File Structure

| File | Purpose |
|------|---------|
| `price_scorer_v2.py` | Updated price scoring with softer penalties |
| `price_ranges_9_v2.yaml` | Updated price range multipliers |
| `calibrate_price_ranges_v2.py` | Regenerates price ranges from market analysis |
| `calibration_v2_report.yaml` | Before/after comparison report |
| `generate_test_cards.py` | Generates 500+ synthetic test cards |
