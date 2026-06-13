# PROJECT STATE — Haraba Mini

> Дата: 2026-06-13
> Источник: 8 этапов аудита (AUDIT_SNAPSHOT → DEPLOYMENT)
> Это главный файл памяти проекта — обновлять при каждом значительном изменении

---

## 1. Что такое Haraba Mini

Haraba Mini — система автоматического сбора и отправки карточек автомобилей из Haraba.ru менеджерам через Telegram с системой реакций для улучшения поисковых конфигов.

**Флагманская идея:** рынок + реакции + конфиги = предложения по улучшению поисков.

**Принцип:** бот НЕ меняет конфиги сам — бот предлагает — решение принимает owner.

---

## 2. Архитектура (фактическая)

```
3 сервиса → 1 БД (feedback.db, 9 таблиц)

┌─────────────────────┐  ┌──────────────────────┐  ┌────────────────────┐
│ run_daily_pipeline  │  │ telegram_feedback_bot│  │ admin_bot          │
│ (cron */10)         │  │ (systemd)            │  │ (systemd)          │
│                     │  │                      │  │                    │
│ collect → enrich →  │  │ review/think/skip →  │  │ /start, /menu →    │
│ audit → send        │  │ reason → feedback    │  │ stats, users, RIS  │
└─────────┬───────────┘  └──────────┬───────────┘  └──────────┬─────────┘
          │                         │                         │
          └─────────────────────────┼─────────────────────────┘
                                    │
                          ┌─────────▼─────────┐
                          │  results/feedback  │
                          │  .db (9 tables)    │
                          │  - sent_ads        │
                          │  - feedback        │
                          │  - telegram_users  │
                          │  - reaction_details│
                          │  - reaction_reasons│
                          │  - learning_rules  │
                          │  - pipeline_runs   │
                          │  - telegram_recipt │
                          └───────────────────┘
```

---

## 3. Сервисы

| Сервис | Файл | Запуск | Production |
|--------|------|--------|------------|
| **Pipeline** | `run_daily_pipeline.py` | cron `*/10` с flock | ✅ VPS |
| **Feedback Bot** | `telegram_feedback_bot.py` | systemd `haraba-bot` | ✅ VPS |
| **Admin Bot** | `admin_bot/admin_bot.py` | systemd `haraba-admin-bot` | ✅ VPS |

---

## 4. Pipeline (фактическая цепочка)

```
step_check_searches() → session_manager.check_session_status()
  ↓ VALID/EXPIRED/MISSING
step_collect_cards() → subprocess: mobile_first_page_sampler.py --limit 30
  ↓ output: latest_cards_raw.json
step_enrich_cards() → photo_parser.enrich_cards_with_photos()
  ↓ output: latest_cards_enriched.json
step_audit() → region/legal/scoring → config_name = f"{brand} {model}"
  ↓ output: latest_cards_audited.json
step_send() → subprocess: telegram_sender.py --send
  ↓ output: telegram_sender_report.yaml
step_feedback_count() → get_feedback_all()
  ↓
save_daily_report() → daily_pipeline_report.yaml
```

---

## 5. База данных

**Файл:** `results/feedback.db` (108 KB)

### Таблицы (9 штук)

| Таблица | Строк | Назначение |
|---------|-------|-----------|
| `sent_ads` | 10 | Отправленные карточки (PK: stable_car_key + chat_id) |
| `feedback` | 1 | Реакции менеджеров (32 колонны) |
| `telegram_users` | 5 | Менеджеры (single source of truth) |
| `telegram_recipients` | 3 | LEGACY — не используется |
| `pipeline_runs` | 0 | Логи pipeline (pipeline пишет в YAML, не в БД) |
| `reaction_reasons` | 27 | Справочник причин реакций (RIS) |
| `reaction_details` | 0 | Привязка реакций к причинам |
| `learning_rules` | 0 | Правила обучения (pending/active/rejected) |
| `sqlite_sequence` | 3 | Internal |

### Менеджеры (telegram_users)

| telegram_id | username | role | status |
|-------------|----------|------|--------|
| 8992376203 | — | owner | active |
| 1649929050 | protocol_skrin | manager | active |
| 896670515 | ismailovvv97 | manager | paused |
| 5649770485 | — | manager | pending |
| 1445251473 | — | manager | pending |

**Активные получатели:** 2 (owner + protocol_skrin)

---

## 6. Конфиги

### Активные YAML

| Файл | Моделей | Назначение |
|------|---------|-----------|
| `config/awd_liquid_full_config.yaml` | 17 | Полный конфиг scoring (pipeline) |
| `config/awd_liquid_ready_8.yaml` | 8 | Исходные модели + search_filters |
| `config/awd_liquid_9.yaml` | 9 | Дополнительные модели + search_filters |
| `config/auto_ru_searches.yaml` | — | Auto.ru MVP (ЗАМОРОЖЕН) |

### 17 моделей

Kia Rio, Ford Kuga, Kia Sorento Prime, VW Touareg, VW Tiguan, Nissan X-Trail, Nissan Qashqai J11, Mercedes GLK 220 CDI, VW Multivan T5, Audi Q5, Hyundai Santa Fe, Kia Sorento, Kia Sportage, Mazda CX-5, Mitsubishi Pajero IV, Hyundai Grand Santa Fe, Nissan Pathfinder / Volvo XC90

---

## 7. Реакции

### Модель (Feedback V2)

| Реакция | Эмодзи | Причины |
|---------|--------|---------|
| review | 👀 Посмотреть | 9 причин (good_price, low_mileage, liquid_model, ...) |
| think | 🤔 Подумать | 10 причин (high_price, high_mileage, need_more_info, ...) |
| skip | ⏭ Скип | 8 причин (too_expensive, bad_condition, legal_risk, ...) |

### Flow реакции

```
review:{card_id} → button_handler() → pending_feedback[chat_id]
  ↓ reason_keyboard(action)
reason:good_price → reason_handler() → pending_reason[chat_id]
  ↓ text_handler() → comment
_save_feedback_for_chat() → save_feedback() → feedback table
  ↓ get_last_feedback_id() → N
save_reaction_detail(N, reason_code) → reaction_details table
```

---

## 8. Dedup

**Механизм:** `stable_car_key = "id:{haraba_id}"` (fallback к URL hash или title+year+price+mileage+region)

**PK:** `(stable_car_key, chat_id)` — per-manager

**Статусы:** `new`, `same_price`, `price_drop`, `price_increased`

**Результат:** 0 дубликатов подтверждено. 5 карточек × 2 менеджера = 10 записей.

---

## 9. config_name статус

| Место | Статус | Доказательство |
|-------|--------|----------------|
| sent_ads колонка | ✅ Есть | PRAGMA table_info(sent_ads) |
| sent_ads данные | ❌ Все NULL (10 записей) | SELECT config_name GROUP BY → 'None': 10 |
| pipeline step_audit() | ✅ Код есть (modified) | run_daily_pipeline.py:205-211 |
| telegram_sender.py | ✅ Код есть (modified) | telegram_sender.py:119-128 |
| mark_sent_with_chat_id() | ✅ Код есть (modified) | feedback_store.py:547 |
| card_data_loader.py | ❌ НЕ загружает | card_data_loader.py:35-58 |
| _save_feedback_for_chat() | ❌ НЕ включает | telegram_feedback_bot.py:302-330 |
| save_feedback() | ❌ Нет параметра | feedback_store.py |
| feedback колонка | ❌ НЕТ | PRAGMA table_info(feedback) — 32 колонны |

---

## 10. Git статус

| Параметр | Значение |
|----------|----------|
| Branch | `main` |
| Remote | `origin` → `https://github.com/a89773120707-dot/harabaBot.git` |
| Last commit | `dda439e` — Add needs_comment helper for reaction reasons |
| Modified | 14 файлов (не закоммичены) |
| Untracked | 100+ файлов |
| VPS commit | `36ab6dc` (отстаёт на 1 коммит) |

---

## 11. VPS

| Параметр | Значение |
|----------|----------|
| Сервер | `haraba@109.238.95.141` |
| Путь | `/home/haraba/harabaBot_code` |
| Python | 3.13.6 |
| Cron | `*/10 * * * *` с `flock -n /tmp/haraba_pipeline.lock` |
| Services | `haraba-bot`, `haraba-admin-bot` |
| Deploy | `git pull` + `systemctl restart` |

---

## 12. Что заморожено

| Элемент | Причина |
|---------|---------|
| Auto.ru MVP | 100% CAPTCHA даже с persistent Chrome profile |
| learning_score | До 100+ реакций |
| reaction_learning_scorer.py | До 100+ реакций |
| Автоматическое изменение score | Запрещено без owner approval |
| Автоматическое изменение конфигов | Запрещено без owner approval |
| Config Intelligence | До Fix 7 и 100+ реакций |

---

## 13. Что нельзя ломать

| Элемент | Последствия |
|---------|------------|
| stable_car_key логика | Все карточки станут "new" → дубли |
| PK sent_ads (stable_car_key, chat_id) | Dedup сломается |
| telegram_users таблица | Потеря менеджеров |
| data/state.json | Pipeline не запустится |
| .env файл | Боты не запустятся |
| callback_data формат | Сломает все handlers |
| get_enabled_recipients() сигнатура | Сломает pipeline и bot |
| save_feedback() сигнатура | Сломает INSERT |

---

## 14. Открытые задачи

| # | Задача | Приоритет | Блокирует |
|---|--------|-----------|-----------|
| 1 | Закоммитить 14 modified файлов | 🔴 P0 | Всё |
| 2 | Push + VPS deploy | 🔴 P0 | Fix 7 |
| 3 | Проверить get_enabled_recipients() на VPS | 🔴 P0 | Рассылка |
| 4 | Fix 7: config_name в feedback | 🟠 P1 | Config Intelligence |
| 5 | Очистить 100+ untracked файлов | 🟠 P1 | Git hygiene |
| 6 | Добавить automatic retry | 🟠 P1 | Потеря карточек |
| 7 | Добавить 403/429 обработку | 🟠 P1 | Rate limit |
| 8 | manager_config | 🟡 P2 | Персонализация |
| 9 | Обновить deployment docs | 🟡 P2 | Misleading docs |
| 10 | Создать .env.example | 🟡 P2 | Deployment friction |

---

## 15. Документация

| Файл | Этап | Содержимое |
|------|------|-----------|
| `docs/AUDIT_SNAPSHOT.md` | 0 | Снимок состояния проекта |
| `docs/PROJECT_INVENTORY.md` | 1 | Инвентаризация файлов |
| `docs/DATABASE.md` | 2 | Аудит SQLite баз |
| `docs/MANAGERS.md` | 3 | Менеджеры, recipients, config_name |
| `docs/REACTIONS.md` | 4 | Реакции, feedback, callback flow |
| `docs/ARCHITECTURE.md` | 5 | ASCII-схема архитектуры |
| `docs/TELEGRAM.md` | 6 | Telegram боты и callback data |
| `docs/CONFIGS.md` | 7 | Конфиги, ENV, secrets |
| `docs/DEPLOYMENT.md` | 8 | Deployment, VPS, cron, systemd |
| `docs/TECH_DEBT.md` | 9 | Технический долг и риски |
| `docs/PROJECT_STATE.md` | Финал | Главный файл памяти |

---

## 16. Правила проекта

| Правило | Описание |
|---------|----------|
| Workflow | План → обсуждение → утверждение → реализация |
| Deploy/push | Только с явного утверждения пользователя |
| Файлы | НЕ добавлять контент без запроса |
| Язык вывода | Русский (если не запрошен другой) |
| БД | НЕ менять без backup |
| Auto.ru | НЕ трогать без явного запроса |
| Users | НЕ трогать если статусы корректны |
| AUTO_MAIN_* | НЕ трогать — другой проект |
| .md файлы | ВСЕ включены в git (документация) |
| Скоринг | НЕ менять до 50+ реакций |
| Конфиги | НЕ менять до 50+ реакций |

---

## 17. Ключевые файлы

| Файл | Назначение | Критичность |
|------|-----------|-------------|
| `run_daily_pipeline.py` | Orchestrator pipeline | HIGH |
| `telegram_sender.py` | Отправка в Telegram | HIGH |
| `telegram_feedback_bot.py` | Реакции менеджеров | HIGH |
| `feedback_store.py` | SQLite: sent_ads, feedback, users | HIGH |
| `session_manager.py` | Playwright сессия Haraba | HIGH |
| `mobile_first_page_sampler.py` | Сбор карточек | HIGH |
| `base.py` | Константы, пути, логгер | HIGH |
| `telegram_card_formatter.py` | Формат карточки V2 | HIGH |
| `telegram_audit.py` | Аудит кандидатов | HIGH |
| `config/awd_liquid_full_config.yaml` | 17 моделей scoring | HIGH |
| `config_loader.py` | Загрузка YAML | HIGH |
| `model_matcher.py` | Matcher card → model | HIGH |
| `admin_bot/admin_bot.py` | Админ-панель | MEDIUM |
| `ris_reason_store.py` | RIS: reaction_details | MEDIUM |
| `ris_reason_keyboard.py` | RIS: inline клавиатуры | MEDIUM |

---

## 18. Контакт / доступы

| Ресурс | Значение |
|--------|----------|
| GitHub | `https://github.com/a89773120707-dot/harabaBot` |
| VPS | `haraba@109.238.95.141` |
| OWNER_ID | `8992376203` |
| Python | 3.13.6 |
| venv | `.venv/` |

---

> ⚠️ **Этот файл — главный источник истины о состоянии проекта.**
> Обновлять при: новом коммите, deploy, изменении БД, добавлении/удалении менеджеров, изменении конфигов.
