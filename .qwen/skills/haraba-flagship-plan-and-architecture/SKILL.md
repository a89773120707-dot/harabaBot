---
name: haraba-flagship-plan-and-architecture
description: Haraba Mini flagship plan, current architecture, frozen areas, and 13-block implementation roadmap
source: auto-skill
extracted_at: '2026-06-12T18:30:00.000Z'
---

## Flagship Principle

Haraba Mini is NOT just a card-sending bot. It is a **search config intelligence system**:

```
рынок → реакции менеджеров → диагностика конфигов → предложения → owner подтверждает → система точнее
```

**Key rule:** бот НЕ меняет конфиги сам — бот предлагает — решение принимает owner

## Current Architecture

### Production environment
- **VPS:** `haraba@109.238.95.141` at `/home/haraba/harabaBot_code`
- **VPS DB is the ONLY source of truth** — local DB is irrelevant for production decisions
- **Cron:** `*/10 * * * *` with `flock -n /tmp/haraba_pipeline.lock`
- **Systemd service:** `haraba-bot` (telegram_feedback_bot.py)

### What already works ✅
| Component | Files | Status |
|-----------|-------|--------|
| 17 search configs | `results/awd_liquid_full_config.yaml` | ✅ |
| Pipeline every 10 min | `run_daily_pipeline.py` + cron | ✅ |
| Haraba scraper (mobile) | `mobile_first_page_sampler.py` | ✅ |
| Scoring system | `price_scorer_v2.py`, `mileage_scorer.py`, `powertrain_scorer.py`, `equipment_scorer.py` | ✅ |
| Telegram sender (multi-recipient) | `telegram_sender.py` | ✅ |
| Inline buttons 👀🤔⏭📖📷 | `telegram_feedback_bot.py` | ✅ |
| Reaction reason codes (27+) | `ris_reason_keyboard.py`, `ris_reason_store.py` | ✅ |
| Feedback DB with dedup | `feedback_store.py` (composite PK: stable_car_key + chat_id) | ✅ |
| Telegram Users (single source) | `feedback_store.py` telegram_users table | ✅ |
| Status workflow | pending → active / paused / disabled | ✅ |
| Admin bot | separate process | ✅ (7 menu buttons) |
| Config + Matcher (Auto.ru) | `app/matcher/auto_ru_matcher.py`, `config/auto_ru_searches.yaml` | ✅ (but frozen) |

### Key files
| File | Purpose |
|------|---------|
| `run_daily_pipeline.py` | Daily pipeline: scrape → score → audit → telegram |
| `telegram_sender.py` | Send cards with inline buttons, multi-recipient dedup |
| `telegram_feedback_bot.py` | Bot that handles reactions, reasons, comments |
| `feedback_store.py` | SQLite: sent_ads, feedback, telegram_users tables |
| `ris_reason_keyboard.py` | Reason inline keyboards for review/think/skip |
| `ris_reason_store.py` | Save/retrieve reaction_details |
| `card_data_loader.py` | Load card data from sample files |
| `cards_loader.py` | Normalize cards for scoring |
| `config_loader.py` | Load YAML config, get_model_by_id |
| `model_matcher.py` | Match card to model_id from config |

### Database schema (current)

**sent_ads** — dedup tracking:
- stable_car_key, chat_id (composite PK)
- card_id, url, mobile_url, haraba_id, title, model_id
- year, price, mileage, region
- first_sent_at, last_seen_at, last_sent_at, send_count
- ✅ config_name — added 2026-06-12 (Block 2)
- ❌ MISSING: source, config_version

**feedback** — reactions:
- id (PK), card_id, url, model_id, title, price, mileage
- engine, transmission, drive, region, owners, legal_restrictions, autoteka_status
- score, telegram_status, action, comment
- price_status, price_score, mileage_score, engine_score, transmission_score, equipment_score
- photo_url, photo_count, full_location
- telegram_chat_id, telegram_user_id, telegram_username, reviewer_role
- created_at
- ❌ config_name NOT added — analytics via JOIN with sent_ads

**reaction_details** — reason codes:
- id (PK), feedback_id (FK), reason_code, created_at

**telegram_users** — user management:
- id (PK), telegram_id (UNIQUE), username, first_name
- role (owner/manager), status (pending/active/paused/disabled)
- created_at, updated_at

## Frozen areas 🚫

Do NOT work on these unless explicitly requested:
- **Auto.ru MVP** — CAPTCHA blocks 100% of Playwright requests
- **Avito** — not in scope
- **Voice/photo requests** (Blocks 11-12) — later
- **AI scoring** — not in flagship plan
- **Automatic config changes** — violates key principle
- **learning_score / reaction_learning_scorer** — frozen until 100+ reactions

## 13-Block Implementation Roadmap

### Phase 1: Now (immediate)
| Block | Title | Status | What's needed |
|-------|-------|--------|---------------|
| **0** | Стабилизация | 🔄 | Verify cron, dedup, reactions on VPS |
| **1** | Сбор реакций | 🔄 | Accumulate 50-100-200 reactions |
| **2** | Привязка реакции к config_name | ✅ | DONE — config_name in sent_ads via step_audit injection |
| **3** | Backfill config_name | ❌ | Script to backfill old sent_ads from model_id/title |
| **4** | Config Report | ❌ | /config_report command — per-config analytics |
| **5** | Learning Dashboard | ❌ | /learning_dashboard — daily overview |

### Phase 2: After 50+ reactions
| Block | Title | Status |
|-------|-------|--------|
| **6** | Диагностика конфигов | ❌ | Detect wide/narrow configs, overpriced, high mileage |
| **7** | Near-miss анализ | ❌ | Cards that almost passed filters (price_above_max, etc.) |
| **8** | Config Suggestions | ❌ | Generate proposals (raise/lower price, mileage, etc.) |
| **9** | Owner Approval | ❌ | approve/reject suggestions in admin |
| **10** | Версионирование конфигов | ❌ | config_v1, v2, v3 — track changes |

### Phase 3: Later
| Block | Title | Status |
|-------|-------|--------|
| **11** | Менеджерские запросы | ❌ | /new_search from main bot |
| **12** | Голос/Фото запросы | ❌ | Voice message → search_request |
| **13** | Экспорт/Backup | ❌ | /db_backup, /export_reactions_csv |

## Block 2 — config_name ✅ IMPLEMENTED 2026-06-12

### Architecture decision
**config_name is stored ONLY in sent_ads, NOT in feedback.**
Reactions are linked to config via JOIN:
```sql
SELECT f.*, s.config_name
FROM feedback f
JOIN sent_ads s ON s.card_id = f.card_id AND s.chat_id = f.telegram_user_id
```

This avoids duplication and desync risk.

### Implementation details
**Injection point:** `run_daily_pipeline.py` → `step_audit()`:
```python
model_id = match_card_to_model(c, config)
model_rules = get_model_by_id(config, model_id)
if model_rules:
    c["config_name"] = f"{model_rules['brand']} {model_rules['model']}"
else:
    c["config_name"] = "unknown"
```

**Propagation chain:**
1. `step_audit()` sets `card["config_name"]` → saved in audit JSON
2. `telegram_sender.py` reads config_name from audit JSON (fallback: derive from model_rules if missing)
3. `mark_sent_with_chat_id(card, chat_id)` reads `card["config_name"]` → INSERT into sent_ads
4. Analytics queries JOIN feedback → sent_ads to get config_name

**Migration:** `feedback_store.py` init_db() adds `config_name TEXT` column via ALTER TABLE

**Files changed:**
- `run_daily_pipeline.py` — config_name injection in step_audit
- `feedback_store.py` — migration + config_name in mark_sent_with_chat_id INSERT
- `telegram_sender.py` — preserve config_name from audit (fallback from model_rules)
- `tests/test_block2_config_name.py` — 5 tests: migration, config_name derivation, mark_sent, JOIN, unknown

### config_name format
- `{brand} {model}` — e.g. "Volkswagen Tiguan", "Kia Sportage", "Mazda Cx5"
- Derived from YAML config model_id → get_model_by_id → brand + model
- "unknown" if model_id not found in config (with warning log)

## Block 4 — /config_report format
```
📋 Config Report

Конфиг: Volkswagen Tiguan
Карточек отправлено: 40
Реакций всего: 18

👀 Посмотреть: 7
🤔 Подумать: 8
⏭ Скип: 3

Топ причин:
💸 Высокая цена — 5
📈 Большой пробег — 3
⚙ Слабая комплектация — 2

Средняя цена 👀: 1 180 000
Средняя цена 🤔: 1 090 000
Средний пробег 👀: 135 000
Средний пробег 🤔: 165 000
```

## Block 5 — /learning_dashboard format
```
🧠 Learning Dashboard

Реакций всего: 87
👀 Посмотреть: 25
🤔 Подумать: 40
⏭ Скип: 22

С причинами: 82
Без причин: 5

Конфигов с реакциями: 12

Топ причин:
1. Высокая цена — 15
2. Большой пробег — 11
3. Хорошая комплектация — 8

Топ конфиги:
1. Tiguan — 18 реакций
2. CX-5 — 14 реакций
3. Sorento — 9 реакций

Активных менеджеров: 5
Реакций за 24 часа: 17
```

## Block 6 — Config Diagnostics examples

**Example 1 — high_price:**
```
Volkswagen Tiguan: много 🤔 high_price
→ Вывод: Менеджеры считают варианты дорогими. Возможно max_price нужно снижать.
```

**Example 2 — too_mileage:**
```
Kia Sorento: много ⏭ too_mileage
→ Вывод: Конфиг пропускает машины с пробегом, который менеджеры не принимают. Возможно нужно снизить max_mileage.
```

**Example 3 — good_equipment:**
```
Mazda CX-5: много 👀 good_equipment
→ Вывод: Комплектация является сильным фактором интереса. Можно учитывать комплектацию сильнее.
```

## Block 7 — Near-miss analysis

Near-miss = card that almost passed one filter:
- price above max_price by 10-20%
- mileage above max_mileage by 10-15%
- year below min_year by 1 year
- region not in allowed list

New table `near_miss_cards`:
- id, card_id, config_name, title, year, price, mileage, region
- failed_rule, failed_value, expected_value, score, created_at

## Safety Rules

1. VPS DB is the ONLY source of truth — never compare/sync with local DB
2. NEVER auto-apply config changes — owner must approve
3. NEVER clear sent_ads automatically — only on explicit command
4. Users: if admin shows correct statuses, don't suggest changes
5. CREATE TABLE IF NOT EXISTS — never break existing DB
6. Check column existence before ALTER TABLE
