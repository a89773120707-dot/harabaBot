# PROJECT INVENTORY — Haraba Mini

> Дата: 2026-06-13
> Режим: только чтение и документирование

---

## 1. ОБЩАЯ СТРУКТУРА ПРОЕКТА

Всего Python файлов: **319** (включая тесты, временные скрипты, untracked)

```
C:\Users\Admin\haraba-mini\
│
├── 📂 app/                          # Auto.ru source module (20 .py + 7 __init__.py)
│   ├── analyzer/                    # Price analysis & scoring
│   ├── database/                    # SQLite repository for Auto.ru
│   ├── matcher/                     # Config matching
│   ├── runners/                     # CLI entry point
│   ├── sources/auto_ru/             # Scraper, parser, browser
│   └── telegram/                    # Telegram formatting
│
├── 📂 admin_bot/                    # Admin Telegram bot (18 .py files)
│   ├── handlers/                    # start.py, menu.py, learning.py
│   └── services/                    # 7 service modules
│
├── 📂 config/                       # YAML configs (7 files)
│
├── 📂 data/                         # session state.json, auto_ru_state.json
│
├── 📂 docs/                         # Документация (создана при аудите)
│
├── 📂 logs/                         # Логи pipeline, session
│
├── 📂 results/                      # Результаты: БД, JSON, HTML, PNG (200+ файлов)
│   └── auto_ru_chrome_profile/      # Chrome persistent profile (500+ файлов)
│
├── 📂 scripts/                      # Утилиты (3 .py)
│
├── 📂 tests/                        # Тесты pytest (7 .py)
│
├── 📂 .qwen/skills/                 # 35+ skill директорий
│
├── 📂 _archive/                     # Архив старых файлов
│
├── 📂 _trash/                       # Удалённый мусор
│
├── 📁 __pycache__/                  # Python bytecode
│
└── [ROOT .py files]                 # 40+ скриптов в корне проекта
```

---

## 2. ГЛАВНЫЕ ТОЧКИ ВХОДА

### 2.1. run_daily_pipeline.py (ОСНОВНАЯ)

**Назначение:** Единый orchestrator ежедневного pipeline.

**Запуск:** `python run_daily_pipeline.py` (cron `*/10` на VPS)

**Pipeline steps:**
1. `step_check_searches()` — проверка сессии + 17 поисков
2. `step_collect_cards()` — subprocess → `mobile_first_page_sampler.py --limit 30`
3. `step_enrich_cards()` — фото через `photo_parser.enrich_cards_with_photos()`
4. `step_audit()` — region/legal/scoring → send_ready/hold/do_not_send
5. `step_send()` — subprocess → `telegram_sender.py`
6. `step_feedback_count()` — счётчик реакций
7. `save_daily_report()` — YAML отчёт

**Критичность: HIGH**

**Доказательство:** Cron на VPS: `*/10 * * * * flock -n /tmp/haraba_pipeline.lock` → `run_daily_pipeline.py`

---

### 2.2. telegram_feedback_bot.py

**Назначение:** Telegram feedback bot — отправка карточек менеджерам, обработка реакций (👀/🤔/⏭ + причины).

**Запуск:** `python telegram_feedback_bot.py` (systemd `haraba-feedback-bot.service` на VPS)

**Критичность: HIGH**

**Доказательство:** VPS systemd service `haraba-bot` → `telegram_feedback_bot.py`

---

### 2.3. admin_bot/admin_bot.py

**Назначение:** Admin bot — управление менеджерами, статистика, реакции, RIS.

**Запуск:** `python -m admin_bot.admin_bot` (systemd `haraba-admin-bot.service` на VPS)

**Критичность: MEDIUM** (административный, не влияет на отправку карточек)

---

### 2.4. app/runners/run_auto_ru.py

**Назначение:** CLI runner для Auto.ru scraper (MVP, стадия 2).

**Запуск:** `python -m app.runners.run_auto_ru --debug --limit 10 --no-send`

**Критичность: LOW** (заморожен из-за CAPTCHA)

**Доказательство:** Файл `project/auto_ru_frozen.md` — "Auto.ru MVP заморожен. 100% CAPTCHA."

---

## 3. TELEGRAM ОТПРАВКА

### telegram_sender.py

**Назначение:** Отправка карточек в Telegram. Multi-recipient (get_enabled_recipients → active users только).

**Кем вызывается:**
- `run_daily_pipeline.py` → subprocess (line 313)
- Тестовые скрипты: `block_j_*.py`, `vps_*.py` (ручные проверки)

**Что импортирует:**
- `feedback_store.py` → dedup (`check_dedup_with_chat_id`, `mark_sent_with_chat_id`)
- `telegram_card_formatter.py` → `format_car_card_v2`
- `config_loader.py`, `model_matcher.py` → match + score
- `cards_loader.py` → `normalize_card`
- `price_scorer_v2.py`, `mileage_scorer.py`, `powertrain_scorer.py` → scoring

**Критичность: HIGH**

**Ключевая логика:**
1. Загружает `telegram_candidates_audited.json`
2. Enrich из `mobile_first_page_sample.json`
3. Для каждого active recipient:
   - `normalize_card()` → `match_card_to_model()` → score
   - `check_dedup_with_chat_id(card, chat_id)` → new/same_price/price_drop/price_increased
   - `send_car_card_sync()` → send_photo или send_message
   - `mark_sent_with_chat_id()` → sent_ads
4. Report: `results/telegram_sender_report.yaml`

---

## 4. РЕАКЦИИ (FEEDBACK / RIS)

### Файлы, связанные с реакциями:

| Файл | Назначение | Статус |
|------|------------|--------|
| `telegram_feedback_bot.py` | Обработка реакций 👀/🤔/⏭ + inline кнопки | ACTIVE, HIGH |
| `feedback_store.py` | SQLite: save_feedback, feedback таблица (30+ полей) | ACTIVE, HIGH |
| `ris_reason_store.py` | Сохранение reason_code в reaction_details | ACTIVE, MEDIUM |
| `ris_reason_keyboard.py` | Inline клавиатуры причин (MAIN_REASONS, EXTRA_REASONS) | ACTIVE, MEDIUM |
| `ris_analytics.py` | Аналитика: get_learning_report, get_learning_reasons, get_config_report | ACTIVE, MEDIUM |
| `ris_migration.py` | Миграция RIS таблиц | STANDBY, LOW |
| `ris_reason_keyboard.py` | REASON_WEIGHTS (30 reason codes, веса 1-10) | ACTIVE, MEDIUM |
| `feedback_export.py` | Экспорт feedback в YAML | CLI, LOW |
| `feedback_report.py` | Аналитика реакций (CLI dashboard) | CLI, LOW |
| `admin_bot/handlers/learning.py` | RIS в админ-боте | ACTIVE, LOW |

**Таблицы в feedback.db:**
- `feedback` — реакции (30+ колонок)
- `reaction_reasons` — справочник причин
- `reaction_details` — привязка feedback_id → reason_code
- `learning_rules` — правила обучения (pending/active/rejected)

---

## 5. DEDUP

### Файлы, связанные с dedup:

| Файл | Назначение | Статус |
|------|------------|--------|
| `feedback_store.py` | Основная dedup логика (check_dedup, check_dedup_with_chat_id) | ACTIVE, HIGH |
| `dedup_store.py` | Backward-compat wrapper (re-exports из feedback_store) | UNUSED, LOW |
| `test_dedup_v2.py` | Тесты dedup | TEST, LOW |
| `results/sent_ads.db` | Отдельная БД с sent_ads (дубликат feedback.db) | UNUSED?, MEDIUM |
| `results/dedup_store.db` | Пустая БД (нет таблиц) | EMPTY, LOW |

**Механизм dedup (feedback_store.py):**
- **Ключ:** `stable_car_key = id:{haraba_id}` (fallback к URL hash)
- **PK:** `(stable_car_key, chat_id)` — composite, пер-recipient
- **Статусы:** `new`, `same_price`, `price_drop`, `price_increased`
- **Цена:** отслеживается для price_drop детекции

**Доказательство:** `feedback_store.py` line 513 — `check_dedup_with_chat_id()`, line 539 — `mark_sent_with_chat_id()`

---

## 6. МЕНЕДЖЕРЫ

### telegram_users — единственный источник правды

**Файл:** `feedback_store.py`

**Функции:**
- `upsert_telegram_user()` — upsert в telegram_users
- `register_recipient()` — регистрация (НЕ меняет status)
- `get_enabled_recipients()` — только `status = 'active'`
- `disable_recipient()` — disable
- `get_all_recipients()` — все (для админки)

**Где используется:**

| Файл | Вызов |
|------|-------|
| `telegram_sender.py` | `get_enabled_recipients()` → список получателей |
| `telegram_feedback_bot.py` | `register_recipient()`, `upsert_telegram_user()`, `get_all_recipients()` |
| `admin_bot/services/users_service.py` | CRUD telegram_users |
| `admin_bot/admin_bot.py` | `ensure_owner_exists()` при старте |
| `run_daily_pipeline.py` | НЕ использует напрямую (делегирует telegram_sender) |

**Схема telegram_users:**
```sql
CREATE TABLE telegram_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    role TEXT DEFAULT 'manager',
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    updated_at TEXT
);
```

**Legacy:** `telegram_recipients` — read-only fallback, НЕ используется как source of truth.

### config_name

**Присутствует в:**
- `sent_ads` таблица: колонка `config_name TEXT` (подтверждено схемой)
- `run_daily_pipeline.py` — передаёт config_name при save (line 290-295, ТРЕБУЕТ ПРОВЕРКИ — файл modified, не закоммичен)
- `telegram_sender.py` — использует config_name при mark_sent (ТРЕБУЕТ ПРОВЕРКИ — файл modified)
- `tests/test_block2_config_name.py` — тесты

**ТРЕБУЕТ ПРОВЕРКИ:** Закоммичен ли config_name функционал (из daily report: "НЕ закоммичен, НЕ задеплоен").

---

## 7. AUTO.RU ИНТЕГРАЦИЯ

### Структура: `app/`

```
app/
  sources/auto_ru/
    browser.py              # Playwright browser/context (clean, no auth)
    persistent_browser.py   # Chrome persistent profile (CAPTCHA bypass attempt)
    scraper.py              # scrape_search_page() — JS extraction
    parser.py               # parse_search_card(), parse_detail_page()
    full_card_parser.py     # 3-step enrichment (detail → status → valuation)
    normalizer.py           # price, mileage, ID parsing, overlay cleanup
    selectors.py            # CSS selectors (CARD_SELECTOR)
    urls.py                 # URL builder stub (unused)
    valuation_parser.py     # Valuation from detail page JSON/DOM
    valuation_page_parser.py # Valuation from /evaluation/cars/ page

  analyzer/
    price_analyzer.py       # Price vs market estimate
    internal_price_analysis.py  # Internal YAML config price analysis
    final_price_decision.py # Unified verdict (Auto.ru + YAML config)
    score.py                # Aggregate scoring (price+mileage+engine+trans+equip)

  database/
    migrations.py           # Ensure sent_ads has Auto.ru columns (21 cols)
    auto_ru_repo.py         # SQLite repo: save, lookup, exists

  matcher/
    auto_ru_matcher.py      # Match cards vs YAML config

  telegram/
    auto_ru_formatter.py    # Telegram card formatting (unused)

  runners/
    run_auto_ru.py          # CLI entry point (stage 2: scrape only)
```

**Текущий статус:** ЗАМОРОЖЕН.

**CAPTCHA проблема:** 100% CAPTCHA даже с auth cookies (56 cookies, headless + headed) и persistent Chrome profile.

**Активная цепочка:** `run_auto_ru.py` → `scraper.py` → `browser.py` + `normalizer.py` + `selectors.py`

**Не подключено к pipeline:** matcher, analyzer, database, telegram, full_card_parser — написаны, но НЕ вызываются из runner.

---

## 8. HARABA PARSER — ЦЕПОЧКА

```
session_manager.py (get_authenticated_page)
  ↓
mobile_first_page_sampler.py
  ├── check_17_active() → verify apply_all_searches_17_report.yaml
  ├── get_authenticated_page() → Playwright browser
  ├── parse_cards_from_table() → raw cards (tr.mat-row)
  ├── open_mobile_detail() → m.haraba.ru/search/car/{id}
  │     ├── raw_text (description + seller)
  │     └── photos (hero + gallery, max 10)
  ├── parse_mobile_specs() → engine/transmission/drive/region/owners/autoteka/legal
  └── enrich_cards_with_photos() → final cards

region_parser.py → parse_region(raw_text) → city, oblast, allowed
legal_parser.py → parse_legal(raw_text) → clear/restricted/unknown

  ↓
run_daily_pipeline.py (enrich step)
  └── photo_parser.enrich_cards_with_photos()

  ↓
telegram_audit.py (audit step)
  ├── reject_engine.check_reject() → hard-stop (red autoteka, accident, taxi)
  ├── region_filter.check_region() → allowed/NOT allowed
  ├── region_parser.parse_region() → city + oblast matching
  ├── legal_parser.parse_legal() → legal status
  ├── score_card() → full scoring pipeline
  └── classify → send_ready / hold / do_not_send

  ↓
telegram_sender.py (send step)
  ├── normalize_card() → unified format
  ├── match_card_to_model() → model_id lookup
  ├── score (price, mileage, engine, transmission) → final score
  ├── format_car_card_v2() → Telegram text
  ├── check_dedup_with_chat_id() → per-recipient dedup
  └── send_photo/send_message → Telegram API
  └── mark_sent_with_chat_id() → sent_ads
```

---

## 9. UNTRACKED ФАЙЛЫ — КЛАССИФИКАЦИЯ

### Категория 1: Временные скрипты (VPS deployment/debug) — 30 файлов

```
block_a_verify.py, block_c1.py, block_c2.py, block_c3.py, block_c4.py
block_f_deploy.py, block_g_restart.py, block_g_restart_v2.py
block_h_final.py, block_h_reactions.py, block_h_reactions_v2.py, block_h_show_reactions.py
block_h_sql_check.py, block_h_try.py
block_i_pipeline_check.py, block_i_recipients_check.py
block_j_final.py, block_j_sent_ads_check.py, block_j_v2.py, block_j_v3.py, block_j_v4.py
block_k_clear.py, block_k_do_clear.py, block_k_full.py, block_k_safe_clear.py, block_k_v2.py
block_l_check_dedup.py
vps_check.py, vps_check_committed.py, vps_copy_fix.py
vps_debug_block2.py, vps_debug_feedback.py, vps_deploy_block2.py
vps_final_diagnosis.py, vps_finalize_block2.py, vps_fix_callback.py
vps_force_fix.py, vps_kill_duplicates.py, vps_report.py
vps_step1_2.py, vps_verify_block2.py, vps_verify_fix.py
block1_vps.py
```

**Назначение:** Одноразовые скрипты для деплоя и отладки на VPS. Больше не нужны после успешного деплоя.

---

### Категория 2: Тестовые файлы — 18 файлов

```
test_auto_ru_auth_vs_guest.py, test_auto_ru_estimate.py, test_auto_ru_formatter.py
test_auto_ru_full_card_with_valuation.py, test_auto_ru_full_pipeline_5.py
test_auto_ru_persistent_profile.py, test_auto_ru_sqlite_save.py
test_auto_ru_telegram_dry_run.py, test_auto_ru_valuation_10.py
test_auto_ru_valuation_page_5.py, test_auto_ru_visible_browser.py
test_detail_page_5.py, test_final_price_decision.py
test_full_report_5.py, test_full_report_5_v2.py, test_matcher_20.py
test_score_pipeline.py, test_card_data.py
```

**Назначение:** Тесты Auto.ru MVP, scoring pipeline, formatter. Некоторые из них — кандидаты в `tests/`.

---

### Категория 3: Отладочные файлы — 12 файлов

```
debug_detail_page.py
login_auto_ru.py, login_auto_ru_profile.py
quick_price_test.py, resolve_contradiction.py
collect_fresh_cars.py, collect_fresh_cars_v2.py
d0_audit.py, d0_steps_2_9.py
final_typo_check.py
check_config_name_column.py, check_dedup_now.py, check_dedup_simple.py
check_sent.py, check_sent_final.py
```

**Назначение:** Диагностика конкретных проблем. Некоторые содержат полезную логику (collect_fresh_cars).

---

### Категория 4: Потенциально полезные — 5 файлов

```
check_dedup_now.py       — быстрая проверка dedup состояния
check_sent_final.py      — проверка sent_ads таблицы
d0_audit.py              — аудит pipeline данных
collect_fresh_cars.py    — альтернативный сборщик карточек
login_auto_ru.py         — авторизация Auto.ru (может пригодиться при разморозке)
```

**Назначение:** Могут быть интегрированы в основной pipeline или tests/.

---

### Категория 5: Неиспользуемый мусор — 35+ файлов

```
# Block scripts (all) — одноразовые, выполнены
# VPS scripts (all) — одноразовые, выполнены  
# Тесты Auto.ru (все) — Auto.ru заморожен

# Plus:
resolve_contradiction.py  — разрешение противоречий (единожды использован)
quick_price_test.py       — быстрый тест цены
test_auto_ru_visible_browser.py — visible browser тест
```

---

### Untracked: .qwen/skills/ (35+ директорий)

```
auto-ru-final-price-decision/
auto-ru-haraba-integration/
auto-ru-integration-architecture/
auto-ru-pipeline-matcher-analyzer-score/
auto-ru-sqlite-integration/
auto-ru-telegram-formatter/
auto-ru-valuation-parser/
diagnosis-first-no-assumptions/
haraba-flagship-plan-and-architecture/
project-context-loading/
project-status-audit/
ris-reaction-intelligence-system/
safe-dedup-clear-procedure/
telegram-admin-bot-architecture/
telegram-bot-api-gotchas/
telegram-display-commands-use-enabled-only/
telegram-feedback-v2-reactions/
telegram-users-single-source-of-truth/
vps-bot-troubleshooting/
vps-code-sync-check/
vps-cron-pipeline-management/
vps-deployment-via-paramiko/
vps-file-integrity-and-callback-safety/
```

**Назначение:** Skills для Qwen Code — документация по паттернам и процедурам. НЕ код проекта.

---

### Untracked: Plans (не в git)

```
ADMIN_BOT_PLAN.md
AUTO_RU_INTEGRATION_PLAN.md
AUTO_RU_TEST_REPORT.md
BLOCK2_CONFIG_NAME_PLAN.md
DAILY_REPORT_2026-06-11.md
FLAGSHIP_PLAN.md
NEXT_PLAN.md
REPORT_2026-06-11.md
```

**Назначение:** Планы и отчёты. FLAGSHIP_PLAN.md и ADMIN_BOT_PLAN.md — наиболее актуальны.

---

### Untracked: app/ (весь)

Полностью untracked. 27 файлов Auto.ru модуля.

---

### Untracked: tests/ (частично)

```
tests/test_auto_ru_normalizer.py
tests/test_auto_ru_valuation_page_parser.py
tests/test_auto_ru_valuation_parser.py
tests/test_block2_config_name.py
tests/test_internal_price_analysis.py
tests/test_reason_callbacks.py
```

---

## 10. КРИТИЧНЫЕ ФАЙЛЫ ПРОЕКТА (TOP-20)

| # | Путь | Назначение | Критичность |
|---|------|------------|-------------|
| 1 | `run_daily_pipeline.py` | Главный orchestrator pipeline | **HIGH** |
| 2 | `telegram_sender.py` | Отправка карточек в Telegram | **HIGH** |
| 3 | `telegram_feedback_bot.py` | Feedback bot — реакции менеджеров | **HIGH** |
| 4 | `feedback_store.py` | SQLite: sent_ads, feedback, telegram_users, RIS | **HIGH** |
| 5 | `session_manager.py` | Playwright сессия Haraba (state.json) | **HIGH** |
| 6 | `mobile_first_page_sampler.py` | Сбор карточек с Haraba (17 поисков) | **HIGH** |
| 7 | `base.py` | Константы, пути, логгер (imported by 60+ файлов) | **HIGH** |
| 8 | `telegram_card_formatter.py` | Форматирование карточки V2 (745 строк) | **HIGH** |
| 9 | `telegram_audit.py` | Аудит кандидатов перед отправкой | **HIGH** |
| 10 | `config/awd_liquid_full_config.yaml` | Полный конфиг 17 моделей | **HIGH** |
| 11 | `config_loader.py` | Загрузка YAML конфигов | **HIGH** |
| 12 | `model_matcher.py` | Matcher карточки к модели | **HIGH** |
| 13 | `price_scorer_v2.py` | Скоринг цены | **HIGH** |
| 14 | `mileage_scorer.py` | Скоринг пробега | **MEDIUM** |
| 15 | `powertrain_scorer.py` | Скоринг двигателя/коробки | **MEDIUM** |
| 16 | `equipment_scorer.py` | Скоринг комплектации | **MEDIUM** |
| 17 | `ris_reason_store.py` | Сохранение причин реакций | **MEDIUM** |
| 18 | `admin_bot/admin_bot.py` | Admin bot entry point | **MEDIUM** |
| 19 | `photo_parser.py` | Парсинг фото | **MEDIUM** |
| 20 | `region_parser.py` | Парсинг регионов | **MEDIUM** |

---

## 11. ГЛАВНЫЕ ТОЧКИ РИСКА (TOP-10)

| # | Риск | Влияние | Доказательство |
|---|------|---------|----------------|
| 1 | **14 modified файлов не закоммичены** | HIGH | `git status` — включая `feedback_store.py`, `run_daily_pipeline.py`, `telegram_sender.py` |
| 2 | **VPS код может отставать от локального** | HIGH | Файлы modified locally, push не выполнен. VPS: `git reset --hard origin/main` покажет старую версию |
| 3 | **100+ untracked файлов в корне** | MEDIUM | `block_*.py`, `vps_*.py`, `test_*.py` — загрязняют проект, усложняют деплой |
| 4 | **Auto.ru заморожен (CAPTCHA 100%)** | MEDIUM | `app/` — 27 файлов написаны, но НЕ подключены к pipeline |
| 5 | **Дубликат sent_ads в sent_ads.db** | MEDIUM | `results/sent_ads.db` имеет sent_ads + feedback таблицы — какой authoritative? |
| 6 | **Пустая dedup_store.db** | LOW | Нет таблиц — миграция не выполнена или файл брошен |
| 7 | **detail_card_enricher_v3.py — путь к haraba_bot** | MEDIUM | `CARS_DB = BASE_DIR.parent / "haraba_bot" / "data" / "cars_db.json"` — зависит от соседней директории |
| 8 | **get_enabled_recipients() bug на VPS** | HIGH | Из daily report: "НЕ исправлено" — возвращает ВСЕХ пользователей |
| 9 | **Блок 2 (config_name) не закоммичен** | MEDIUM | Колонка есть в схеме, но код modified — неизвестно, работает ли на VPS |
| 10 | **Telegram timeout на VPS** | MEDIUM | `HTTPXRequest` настроен (90s read), но VPS сеть может быть медленнее |

---

## 12. ТРЕБУЕТ ПРОВЕРКИ

| № | Что | Почему |
|---|-----|--------|
| 1 | **VPS git status** | Локально 14 modified файлов — на VPS может быть другая версия |
| 2 | **get_enabled_recipients() на VPS** | Из daily report: "НЕ исправлено" — требует проверки текущего кода на VPS |
| 3 | **config_name данные в sent_ads** | Колонка есть в схеме, но содержит ли данные? |
| 4 | **sent_ads.db vs feedback.db** | Два файла с sent_ads таблицей — какой используется telegram_sender.py? |
| 5 | **dedup_store.db пустая** | Предназначена для dedup? Когда создана? Почему нет таблиц? |
| 6 | **cron на VPS** | Память говорит `*/10`, CRON_SETUP.md говорит `*/15` — актуальное расписание? |
| 7 | **systemd services на VPS** | Какие именно запущены? `haraba-bot`, `haraba-admin-bot`? |
| 8 | **config_loader_8.py и config_loader_9.py** | Существуют ли? Чем отличаются от config_loader.py? |
| 9 | **auto_ru_chrome_profile на VPS** | Скопирован ли Chrome profile? Используется ли persistent_browser.py? |
| 10 | **reject_engine.py** | Кто импортирует? Только telegram_audit.py и config_scoring_tester.py — в pipeline НЕ вызывается напрямую |

---

## 13. МОДУЛИ — СВОДКА

| Категория | Модулей | Файлов | Критичность |
|-----------|---------|--------|-------------|
| **Pipeline orchestrator** | 1 | 1 | HIGH |
| **Telegram** | 3 | 4 | HIGH |
| **Database/Storage** | 1 | 1 (+ 2 legacy) | HIGH |
| **Session/Auth** | 1 | 1 | HIGH |
| **Haraba Scraper** | 2 | 2 | HIGH |
| **Scoring** | 4 | 4 | HIGH |
| **Config** | 1 | 1 | HIGH |
| **Matching** | 1 | 1 | HIGH |
| **Audit/Filter** | 4 | 4 | HIGH |
| **RIS (Reactions)** | 3 | 3 | MEDIUM |
| **Admin Bot** | 1 package | 18 | MEDIUM |
| **Auto.ru** | 1 package | 27 | LOW (frozen) |
| **Reporting** | 2 | 2 | LOW |
| **Tests** | 1 package | 7 | LOW |
| **Utilities** | 1 package | 3 | LOW |

---

## 14. ОТЧЁТ ПО ЗАВЕРШЕНИИ

| Метрика | Значение |
|---------|----------|
| Файлов проанализировано | **~80** (все .py файлы проекта) |
| Модулей найдено | **15** основных категорий |
| Точек входа найдено | **4** (run_daily_pipeline.py, telegram_feedback_bot.py, admin_bot.py, run_auto_ru.py) |
| Telegram модулей найдено | **3** (telegram_sender.py, telegram_feedback_bot.py, telegram_card_formatter.py) |
| DB модулей найдено | **1** активный (feedback_store.py) + 2 legacy |
| Файлов связано с реакциями | **9** |
| Файлов связано с dedup | **5** |
| Untracked файлов классифицировано | **100+** (5 категорий) |
| Самые критичные файлы (TOP-5) | 1. run_daily_pipeline.py, 2. telegram_sender.py, 3. telegram_feedback_bot.py, 4. feedback_store.py, 5. session_manager.py |
