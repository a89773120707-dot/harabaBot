---
name: telegram-pipeline-stabilization
description: End-to-end pipeline stabilization workflow — 17 searches → fresh cards → audit → V2 preview → send → feedback
source: auto-skill
extracted_at: '2026-06-09T14:30:00.000Z'
---

## Pipeline Stabilization — Iteration Workflow

**Main principle:** Do NOT change scoring or config until 50–100 reactions collected.

### Iteration 1 — Stabilize full pipeline

#### Block 1: Check 17 searches
```bash
python pipeline_searches_check.py
```
- Verify 17 saved searches active
- 17 checkboxes checked
- results > 0
- Report: `results/pipeline_searches_check.yaml`

#### Block 2: Collect fresh cards
```bash
python mobile_first_page_sampler.py --limit 30
```
- Save: `results/latest_cards.json`
- Verify: price 100%, mileage 90%+, engine 90%+, transmission 90%+, drive 90%+

**Critical:** `wait_until="load"` (not "domcontentloaded") for mobile detail pages, + 5s for JS render.

#### Block 3: Hard-stop audit
```bash
python telegram_audit.py
```
Hard-stop rules:
- engine unknown → do_not_send
- transmission unknown → do_not_send
- drive unknown → do_not_send
- not AWD → do_not_send
- manual → do_not_send
- confirmed legal restriction → do_not_send
- wrong region → do_not_send
- duplicate same_price → do_not_send

**Unknown region/legal does NOT block** — warning only for Telegram v1.

#### Block 4: Telegram V2 preview
```bash
python telegram_sender.py --dry-run --v2 --with-photos
```
- Save: `results/latest_telegram_preview.md`
- Verify: photo or fallback text, no missing specs, buttons present

#### Block 5: Test send
```bash
# First 1 card
python telegram_sender.py --send --v2 --with-photos --limit 1

# Then 3 cards
python telegram_sender.py --send --v2 --with-photos --limit 3
```
Verify: photo visible, buttons work, 📖 description works, 📷 more photos works, reaction saves to feedback.db

#### Iteration 1 report
Create `results/iteration_1_pipeline_report.yaml`:
```yaml
block: iteration_1
searches_active: 17
cards_collected: N
send_ready: N
do_not_send: N
dry_run_ok: true
test_send_ok: true
feedback_working: true
pass: true/false
```

### Iteration 2 — Feedback V2

#### Block 6: Extend feedback.db
Add fields to feedback table:
- photo_url, photo_count
- seller_description, full_location
- price_status, price_delta_to_good
- first_seen_at, last_seen_at, send_count

#### Block 7: Full reaction save
On 🟢🟡🔴 click, save complete card data:
```python
feedback_card = {
    "card_id", "model_id", "title", "year",
    "price", "mileage", "engine", "transmission", "drive",
    "region", "owners", "legal_status",
    "score", "price_status", "photo_url",
    "reaction", "comment", "created_at"
}
```

#### Block 8: Card history in sent_ads
Extend sent_ads:
```
stable_car_key, card_id, title, price, last_price,
first_seen_at, last_seen_at, last_sent_at, send_count,
price_history_json
```

### Commands reference

```bash
# Check searches
python pipeline_searches_check.py

# Collect cards
python mobile_first_page_sampler.py --limit 30

# Audit
python telegram_audit.py

# Dry-run
python telegram_sender.py --dry-run --v2 --with-photos

# Send
python telegram_sender.py --send --v2 --with-photos --limit 1

# Feedback bot
python telegram_feedback_bot.py

# Analytics
python feedback_report.py --days 7
```

### Files

| File | Purpose |
|------|---------|
| `pipeline_searches_check.py` | Verify 17 searches active |
| `mobile_first_page_sampler.py` | Collect fresh cards with photos |
| `telegram_audit.py` | Hard-stop audit |
| `telegram_sender.py` | Send with photo (bytes fallback) |
| `telegram_feedback_bot.py` | Handle buttons + comments |
| `feedback_store.py` | SQLite dedup + feedback |
| `feedback_report.py` | Analytics dashboard |
