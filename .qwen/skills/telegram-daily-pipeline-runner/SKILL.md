---
name: telegram-daily-pipeline-runner
description: Unified daily pipeline runner — one command: check searches → collect → enrich → audit → send → report
source: auto-skill
extracted_at: '2026-06-09T15:00:00.000Z'
---

## Daily Pipeline Runner — run_daily_pipeline.py

Unified entry point for the full Telegram pipeline. Replaces running multiple scripts manually.

### Commands

```bash
# Dry-run (no sending)
python run_daily_pipeline.py --dry-run

# Send all ready cards
python run_daily_pipeline.py --send

# Send with limit
python run_daily_pipeline.py --send --limit 3

# Use existing cards (skip collection)
python run_daily_pipeline.py --send --skip-collect
```

### Pipeline Steps

1. **Check 17 searches** — `check_session_status()` must return "VALID"
2. **Collect cards** — runs `mobile_first_page_sampler.py` internally (or uses existing sample if `--skip-collect`)
3. **Enrich cards** — `photo_parser.enrich_cards_with_photos()` adds photos, regions
4. **Hard-stop audit** — engine/transmission/drive unknown → reject, scoring for all accepted cards
5. **Telegram send** — copies audited JSON to expected location, runs `telegram_sender.py` as subprocess
6. **Feedback count** — logs current reaction count

### Audit Logic (built-in)

The pipeline does its own audit (not calling `telegram_audit.py`):

```python
# Flatten specs to top-level
for c in cards:
    specs = c.get("specs", {})
    for key, val in specs.items():
        if isinstance(val, dict) and "value" in val:
            c[key] = val["value"]

# Normalize drive/transmission
if drive in ("Полный", "полный", "4WD", "AWD"): c["drive"] = "awd"
if trans in ("Автомат", "автомат", "AT"): c["transmission"] = "automatic"

# Hard-stops
if engine == "unknown": reject
if trans == "unknown" or trans == "manual": reject
if drive == "unknown" or drive != "awd": reject

# Scoring
price_r = score_price(price, model_rules["price"])
mileage_r = score_mileage(mileage, model_rules["mileage"])
engine_r = score_engine(engine, model_rules["engines"])
trans_r = score_transmission(transmission, model_rules["transmissions"])
equip_r = score_equipment(card, model_rules)
total = sum(scores) + 50  # baseline
```

### Scoring Decision Thresholds

```
total >= 80 → excellent_candidate
total >= 60 → good_candidate
total >= 40 → watch_candidate
total < 40  → weak_candidate
```

### Daily Report

Saves to `results/daily_pipeline_report.yaml`:

```yaml
run_id: "2026-06-09_1430"
started_at: "2026-06-09T14:30:00"
cards_collected: 30
cards_enriched: 30
with_photos: 27
send_ready: 17
do_not_send: 4
sent_new: 17
skipped_duplicate: 0
failed: 0
feedback_count: 13
```

### Fallback Behavior

- If collection fails: uses existing `mobile_first_page_sample.json`
- If raw cards not found: uses sample as fallback
- If photo download fails: falls back to text-only send
- If Telegram unavailable: error logged, pipeline continues to next step
- Session invalid: pipeline aborts immediately

### Error Recovery

Each step wrapped in `run_step(name, func)` with try/except. If a step fails:
- Logs error with `❌` prefix
- Some steps abort pipeline (check_searches, enrich, audit)
- send failures are tolerated (continues to feedback count)

### Files

| File | Purpose |
|------|---------|
| `run_daily_pipeline.py` | Unified pipeline runner |
| `daily_pipeline_report.yaml` | Daily output report |
| `daily_pipeline.log` | Log file |
| `latest_cards_raw.json` | Raw collected cards |
| `latest_cards_enriched.json` | Enriched with photos |
| `latest_cards_audited.json` | Audit results with scoring |
