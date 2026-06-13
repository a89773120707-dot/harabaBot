# AUDIT SNAPSHOT — Haraba Mini

## 1. Дата аудита

2026-06-13

---

## 2. Текущая директория

`C:\Users\Admin\haraba-mini`

---

## 3. Git статус

**Branch:** `main` (up to date with `origin/main`)

**Modified (unstaged, 14 files):**
- `.qwen/skills/auto-ru-evaluation-aggregator/SKILL.md`
- `.qwen/skills/auto-ru-listing-scraper/SKILL.md`
- `.qwen/skills/haraba-server-deployment/SKILL.md`
- `.qwen/skills/haraba-vps-deployment-guide/SKILL.md`
- `.qwen/skills/plan-discuss-approve-implement/SKILL.md`
- `.qwen/skills/telegram-bot-conflict-resolution/SKILL.md`
- `.qwen/skills/telegram-feedback-v2-schema/SKILL.md`
- `DAILY_REPORT_2026-06-12.md`
- `admin_bot/handlers/menu.py`
- `config/awd_liquid_full_config.yaml`
- `feedback_store.py`
- `results/telegram_sender_report.yaml`
- `run_daily_pipeline.py`
- `telegram_sender.py`

**Untracked (100+ files):** включая `app/`, `tests/`, 20+ `block_*.py`, 15+ `vps_*.py`, 10+ `test_auto_ru_*.py`, `config/auto_ru_searches.yaml`, `results/auto_ru_chrome_profile/` (Chrome profile), `results/debug/` (множество HTML/PNG/JSON), и 20+ новых `.qwen/skills/` папок.

---

## 4. Активная ветка

`main` — единственная ветка, remote `origin/main` совпадает.

---

## 5. Последние коммиты (15 total, не 50)

```
dda439e Add needs_comment helper for reaction reasons
7840171 Add daily report 2026-06-12 — telegram_users single source of truth, /recipients fix, cron */10
36ab6dc Fix /recipients command to show only active users via get_enabled_recipients()
a238e27 Fix: telegram_users as single source of truth — sync recipients, auto-register /start with pending, owner notification
2ff2dec Feedback V2 UX v3 — clean reasons, no duplicates, comment button
5423105 Add RIS analytics — learning_report, learning_reasons, config_report
8e60016 Feedback V2 — replace like/dislike/fire with review/think/skip
b9bdd56 Add RIS Block 1 — Reaction Intelligence System
ba88ea3 Add admin bot and recipient management
c25c016 Connect telegram_sender to telegram_users status
c7f29f3 Add Haraba Mini admin bot MVP
a8d9a7a Increase Telegram timeouts for VPS sender + fix counters
7225f62 Add VPS headless mode support for Playwright
7349262 Fix pipeline collector (subprocess run + timeout), add timing, restore apply_all_searches_17
5c27cb5 Haraba Mini MVP ready for VPS deployment (cleanup + pipeline + feedback v2)
```

---

## 6. Основные папки (top-level)

| Папка | Назначение |
|-------|------------|
| `admin_bot/` | Админ-бот (handlers/, services/) |
| `app/` | Auto.ru source module (sources/auto_ru/, runners/) |
| `config/` | YAML конфиги (awd_liquid_full_config.yaml, auto_ru_searches.yaml, saved_searches) |
| `data/` | state.json, сессии, данные |
| `docs/` | Документация (создана при аудите) |
| `logs/` | Логи pipeline |
| `results/` | Результаты: БД, JSON, HTML, PNG, отчёты |
| `scripts/` | Утилиты (backup_db.py, sync_recipients_to_users.py) |
| `tests/` | Тесты pytest |
| `.qwen/` | Skills и memories |
| `_archive/` | Архив старых файлов |
| `_trash/` | Удалённый мусор |

---

## 7. Ключевые файлы проекта

### Pipeline / Telegram
| Файл | Назначение |
|------|------------|
| `run_daily_pipeline.py` | Главный runner pipeline (collect → enrich → audit → send) |
| `telegram_sender.py` | Отправка карточек в Telegram |
| `telegram_feedback_bot.py` | Feedback bot (реакции review/think/skip + причины) |
| `telegram_card_formatter.py` | Форматирование карточки V2 |
| `telegram_audit.py` | Аудит кандидатов перед отправкой |
| `feedback_store.py` | SQLite: sent_ads, feedback, telegram_users, RIS таблицы |
| `session_manager.py` | Управление Haraba-сессией (state.json) |

### Admin Bot
| Файл | Назначение |
|------|------------|
| `admin_bot/admin_bot.py` | Точка входа админ-бота |
| `admin_bot/handlers/menu.py` | Главное меню (7 кнопок) |
| `admin_bot/handlers/stats.py` | Статистика |
| `admin_bot/handlers/users.py` | Управление менеджерами |

### Scoring / Config
| Файл | Назначение |
|------|------------|
| `config/awd_liquid_full_config.yaml` | Полный конфиг 17 моделей |
| `config_loader.py` | Загрузка YAML конфигов |
| `price_scorer_v2.py` | Скоринг цены |
| `mileage_scorer.py` | Скоринг пробега |
| `powertrain_scorer.py` | Скоринг двигателя/коробки |
| `equipment_scorer.py` | Скоринг комплектации |
| `model_matcher.py` | Matcher карточки к конфигу |
| `final_price_decision.py` | Финальное ценовое решение |

### Auto.ru (app/)
| Файл | Назначение |
|------|------------|
| `app/sources/auto_ru/browser.py` | Playwright браузер для Auto.ru |
| `app/sources/auto_ru/scraper.py` | Сбор карточек с Auto.ru |
| `app/sources/auto_ru/selectors.py` | CSS селекторы Auto.ru |
| `app/sources/auto_ru/parser.py` | Парсинг карточек |
| `app/sources/auto_ru/normalizer.py` | Нормализация price, mileage, ext_id |
| `app/runners/run_auto_ru.py` | Runner для Auto.ru |

### RIS (Reaction Intelligence)
| Файл | Назначение |
|------|------------|
| `ris_reason_store.py` | Хранение reason codes |
| `ris_reason_keyboard.py` | Inline-клавиатуры причин |
| `ris_analytics.py` | Аналитика реакций |
| `ris_migration.py` | Миграция RIS таблиц |

### Haraba Scraper
| Файл | Назначение |
|------|------------|
| `mobile_first_page_sampler.py` | Сбор карточек с mobile Haraba |
| `detail_card_enricher_v3.py` | Обогащение карточек (engine, transmission, drive) |
| `photo_parser.py` | Парсинг фото из mobile detail |
| `region_parser.py` | Парсинг региона |
| `legal_parser.py` | Парсинг ограничений |

### Plans (не закоммичены в git)
| Файл | Статус |
|------|--------|
| `ADMIN_BOT_PLAN.md` | Untracked |
| `AUTO_RU_INTEGRATION_PLAN.md` | Untracked |
| `FLAGSHIP_PLAN.md` | Untracked |
| `RIS_PLAN.md` | Untracked |
| `BLOCK1_PLAN.md` | Tracked |
| `BLOCK2_PLAN.md` | Tracked |
| `MVP_PLAN.md` | Tracked |
| `PRE_DEPLOY_PLAN.md` | Tracked |
| `CRON_SETUP.md` | Tracked |
| `CARD_V2_APPROVED.md` | Tracked |
| `PROGRESS.md` | Tracked |

---

## 8. Базы данных

### results/feedback.db (основная)

**Таблицы:**
| Таблица | Назначение |
|---------|------------|
| `feedback` | Реакции менеджеров (30+ полей включая V2 и RIS) |
| `sent_ads` | Отправленные объявления (composite PK: stable_car_key + chat_id) |
| `telegram_users` | Пользователи (role, status: pending/active/paused/disabled) |
| `telegram_recipients` | Legacy recipients (enabled=0/1) — НЕ используется как source of truth |
| `pipeline_runs` | Логи запусков pipeline |
| `reaction_reasons` | RIS: справочник причин реакций |
| `reaction_details` | RIS: детали реакций (feedback_id → reason_code) |
| `learning_rules` | RIS: правила обучения (pending/active/rejected) |

### results/sent_ads.db (дубликат/backup)

**Таблицы:** `sent_ads`, `feedback`, `sqlite_sequence`

### results/dedup_store.db

**Пустая** — нет таблиц.

### results/feedback_backup_20260612_143122.db

Бэкап feedback.db от 2026-06-12.

### results/feedback_before_users_sync.db

Бэкап до синхронизации telegram_users.

### results/auto_ru_chrome_profile/

Chrome persistent profile для Auto.ru (не БД проекта).

---

## 9. VPS признаки (из памяти, ТРЕБУЕТ ПРОВЕРКИ на VPS)

**ТРЕБУЕТ ПРОВЕРКИ:**

- **VPS:** `haraba@109.238.95.141`, path `/home/haraba/harabaBot_code`
- **Systemd:** `haraba-bot` (feedback bot), `haraba-admin-bot` (admin bot)
- **Cron:** `*/10 * * * *` с `flock -n /tmp/haraba_pipeline.lock`
- **Log:** `logs/pipeline_cron.log`
- **Deploy:** `git reset --hard origin/main` на VPS

**На локальной машине (Windows) systemd/cron НЕ применимы.**

---

## 10. Python окружение

- **Python:** 3.13.6
- **playwright:** 1.60.0
- **python-telegram-bot:** 22.7
- **pyTelegramBotAPI:** 4.28.0
- **PyYAML:** 6.0.3

---

## 11. Что требует проверки

| № | Что | Почему |
|---|-----|--------|
| 1 | 14 modified файлов не закоммичены | Включая `feedback_store.py`, `run_daily_pipeline.py`, `telegram_sender.py` — приоритетные фиксы из daily report |
| 2 | 100+ untracked файлов | `block_*.py`, `vps_*.py`, `test_*.py` — временные скрипты, подлежат очистке |
| 3 | `results/sent_ads.db` vs `feedback.db` | sent_ads таблица есть в обоих БД — какой источник authoritative? |
| 4 | `results/dedup_store.db` пустая | Предназначена для dedup, но таблиц нет — миграция не выполнена? |
| 5 | `config/auto_ru_searches.yaml` untracked | Конфиг Auto.ru создан, но не в git |
| 6 | `results/auto_ru_chrome_profile/` | Chrome profile ~сотни файлов — tracked ли в .gitignore? |
| 7 | VPS состояние | Код на VPS может отличаться от локального (git status на VPS ТРЕБУЕТ ПРОВЕРКИ) |
| 8 | `get_enabled_recipients()` bug | Из daily report: на VPS старая версия без `WHERE status = 'active'` — исправлено ли? |
| 9 | Блок 2 (config_name) | Из daily report: НЕ закоммичен, НЕ задеплоен — колонка config_name есть в sent_ads схеме (подтверждено), но данные? |
| 10 | 5 планов untracked | FLAGSHIP_PLAN.md, ADMIN_BOT_PLAN.md, AUTO_RU_INTEGRATION_PLAN.md, RIS_PLAN.md — не в git |
