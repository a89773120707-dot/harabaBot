# AUDIT REPORT — Haraba Mini

> Дата начала: 2026-06-13
> Дата завершения: 2026-06-13
> Режим: технический аудитор и документатор (только чтение, без изменений кода/БД/VPS)
> Всего этапов: 9

---

## ОБЗОР

Проведён полный read-only аудит проекта Haraba Mini — от снимка состояния до deployment.

**Результат:** 11 документов (~3 450 строк), описывающих каждую часть проекта с доказательствами.

---

## ЭТАП 0 — СНИМОК СОСТОЯНИЯ

**Файл:** `docs/AUDIT_SNAPSHOT.md`

### Что сделано
- `pwd`, `git status`, `git branch -a`, `git log --oneline -50`
- Полный список файлов и папок
- Python 3.13.6, playwright==1.60.0, python-telegram-bot==22.7
- Найдено 7 SQLite БД (5 проекта + 2 Chrome)
- Схемы всех 8 таблиц feedback.db

### Ключевые факты
- Ветка `main`, up to date с `origin/main`
- **14 modified файлов** не закоммичены
- **100+ untracked файлов** (block_*, vps_*, test_*)
- 3 активные БД: feedback.db (108 KB), sent_ads.db (20 KB, пустая), dedup_store.db (0 KB, broken)
- VPS: `haraba@109.238.95.141`, path `/home/haraba/harabaBot_code`

---

## ЭТАП 1 — ИНВЕНТАРИЗАЦИЯ ПРОЕКТА

**Файл:** `docs/PROJECT_INVENTORY.md`

### Что сделано
- Проанализированы все 319 .py файлов
- Разобраны все директории: app/, admin_bot/, config/, results/, scripts/, tests/
- Составлен dependency graph между модулями
- Классифицированы 100+ untracked файлов (5 категорий)

### Ключевые факты
- **4 точки входа:** run_daily_pipeline.py, telegram_feedback_bot.py, admin_bot.py, run_auto_ru.py (frozen)
- **3 Telegram модуля:** telegram_sender.py, telegram_feedback_bot.py, telegram_card_formatter.py
- **app/ = 27 файлов** Auto.ru (заморожен, 100% CAPTCHA)
- **admin_bot/ = 18 файлов** (полная админка)
- **TOP-5 критичных файлов:** run_daily_pipeline.py, telegram_sender.py, telegram_feedback_bot.py, feedback_store.py, session_manager.py

### ТОП-10 рисков
1. 14 modified файлов не закоммичены
2. VPS код может отставать
3. 100+ untracked файлов
4. Auto.ru заморожен
5. Дубликат sent_ads.db
6. dedup_store.db пустая
7. detail_card_enricher_v3.py зависит от соседней директории
8. get_enabled_recipients() bug на VPS
9. Блок 2 config_name не закоммичен
10. 5 планов untracked

---

## ЭТАП 2 — АУДИТ БАЗЫ ДАННЫХ

**Файл:** `docs/DATABASE.md`

### Что сделано
- Полная схема всех 9 таблиц feedback.db
- Подсчёт строк во всех таблицах
- Deep анализ sent_ads (38 колонок, 10 строк)
- Deep анализ feedback (32 колонны, 1 строка)
- Анализ telegram_users (5 пользователей)
- Проверка dedup: 0 дубликатов, 5 карточек × 2 менеджера

### Ключевые факты
- **sent_ads:** PK `(stable_car_key, chat_id)` — per-manager dedup работает
- **config_name в sent_ads:** колонка есть, все 10 записей = NULL
- **config_name в feedback:** колонны НЕТ
- **reaction_details:** 0 строк (данные на VPS, не локально)
- **feedback:** 1 строка (данные на VPS)
- **telegram_recipients:** legacy, рассинхрон с telegram_users
- **sent_ads.db:** пустая, не используется
- **dedup_store.db:** 0 bytes, нет таблиц

### Вывод
Dedup уже manager-aware. Для Config Intelligence нужно: ALTER TABLE feedback ADD COLUMN config_name TEXT.

---

## ЭТАП 3 — МЕНЕДЖЕРЫ, ПОЛУЧАТЕЛИ И CONFIG_NAME

**Файл:** `docs/MANAGERS.md`

### Что сделано
- Полный анализ get_enabled_recipients()
- Flow config_name от pipeline до БД
- Анализ всех мест, где теряется config_name
- Проверка связи manager → config

### Ключевые факты
- **Активные менеджеры:** 2 (owner Haraba + protocol_skrin)
- **get_enabled_recipients():** возвращает {chat_id, username, first_name, role} — NO config_name
- **config_name теряется в 3 точках:**
  1. card_data_loader.py — не загружает из audited JSON
  2. _save_feedback_for_chat() — не включает в feedback_card dict
  3. feedback table — нет колонны
- **Персональные конфиги:** НЕ СУЩЕСТВУЮТ
- **Block 2:** код написан, но НЕ закоммичен

---

## ЭТАП 4 — REACTIONS / FEEDBACK / CONFIG_NAME

**Файл:** `docs/REACTIONS.md`

### Что сделано
- Полный callback flow: от кнопки до БД
- Анализ всех 17 callback_data форматов
- Анализ feedback table (32 колонны)
- Анализ 27 reaction reasons
- Анализ pending_feedback lifecycle

### Ключевые факты
- **Callback data:** `review:{card_id}`, `think:{card_id}`, `skip:{card_id}`, `reason:{code}`
- **Все < 64 bytes** — безопасно для Telegram API
- **feedback_card dict:** 30+ полей, НЕТ config_name, НЕТ stable_car_key
- **reaction_details:** FK → feedback.id, reason_code из 27 вариантов
- **Manager identity:** telegram_chat_id, telegram_user_id, reviewer_role — ВСЕ заполняются
- **config_name gap:** 3 точки потери + нет колонны в БД

---

## ЭТАП 5 — АРХИТЕКТУРА PIPELINE

**Файл:** `docs/ARCHITECTURE.md`

### Что сделано
- Полная ASCII-схема архитектуры
- Детальный разбор каждого шага pipeline
- Анализ card_id и stable_car_key flow
- config_name flow table (10 шагов)
- Database write points
- Где теряются данные

### Ключевые факты
- **card_id** появляется в mobile_first_page_sampler.py (regex из URL)
- **stable_car_key** формируется в _build_stable_key(): `id:{card_id}`
- **config_name** появляется в step_audit(), записывается в sent_ads, но НЕ доходит до feedback
- **3 сервиса пишут в 1 БД** — SQLite serializes writes
- **pipeline_runs = 0** — pipeline пишет в YAML, не в БД

---

## ЭТАП 6 — TELEGRAM БОТЫ И АДМИН-БОТ

**Файл:** `docs/TELEGRAM.md`

### Что сделано
- Полный анализ 3 Telegram сервисов
- Все callback_data форматы (17 штук)
- Ошибки и retry логика
- Роли и доступы
- Admin bot: команды, handlers, permissions

### Ключевые факты
- **3 сервиса:** pipeline sender (subprocess), feedback bot (systemd), admin bot (systemd)
- **Нет обработки 403/429** от Telegram API
- **Нет automatic retry** — failed send = пропуск
- **Admin bot защищён** — is_admin() + can_modify_user()
- **Feedback bot НЕ защищён** — любой получивший карточку может реагировать (intentional)
- **OWNER_ID hardcoded** в 3+ файлах

---

## ЭТАП 7 — CONFIGS / ENV / SEARCH CONFIGS

**Файл:** `docs/CONFIGS.md`

### Что сделано
- Все YAML конфиги (4 active, 3 legacy, 10+ reports)
- Все JSON файлы (4 state, 4 runtime, 8+ test, 15+ debug)
- .env файл (9 переменных)
- 17 моделей — полный список
- Config loading flow
- manager_config статус

### Ключевые факты
- **awd_liquid_full_config.yaml:** 1678 строк, 17 моделей, global_rules
- **ford_kuga дубликат** в full_config
- **Секреты в коде:** OWNER_ID hardcoded в 3+ файлах
- **manager_config:** НЕ СУЩЕСТВУЕТ
- **Можно добавить модели без изменения кода** — достаточно YAML

---

## ЭТАП 8 — DEPLOYMENT / VPS / CRON / SYSTEMD

**Файл:** `docs/DEPLOYMENT.md`

### Что сделано
- Анализ всех deploy файлов
- Local / GitHub / VPS diff
- Cron и systemd анализ
- Backup и rollback процедуры
- Устаревшие документы

### Ключевые факты
- **VPS отстаёт:** commit `36ab6dc` vs GitHub `dda439e` (1 коммит)
- **haraba_bot.service устарел:** пути `/opt/haraba-mini` vs `/home/haraba/harabaBot_code`
- **CRON_SETUP.md устарел:** `*/15` vs `*/10`
- **Нет автоматического backup**
- **Нет .env.example**
- **Backup есть:** feedback_backup_20260612_143122.db, feedback_before_users_sync.db

---

## ЭТАП 9 — TECH DEBT / РИСКИ

**Файл:** `docs/TECH_DEBT.md`

### Что найдено

| Приоритет | Количество | Примеры |
|-----------|-----------|---------|
| 🔴 P0 | 4 | Modified файлы, config_name gap, VPS lag, untracked files |
| 🟠 P1 | 10 | feedback колонна, get_enabled_recipients bug, retry, 403/429 |
| 🟡 P2 | 8 | Legacy таблицы, OWNER_ID hardcoded, manager_config |
| P3 | 6 | .env.example, auto backup, health check, pipeline_runs |

**Итого: 22 проблемы**

### ТОП-5 нельзя ломать
1. stable_car_key логика
2. PK sent_ads (stable_car_key, chat_id)
3. telegram_users таблица
4. data/state.json
5. .env файл

### Рекомендуемый порядок
1. Фаза 1: Стабилизация (commit → push → VPS deploy) — 10 минут
2. Фаза 2: Fix 7 config_name в feedback — 45 минут
3. Фаза 3: Очистка untracked файлов — 30 минут
4. Фаза 4: Улучшения (retry, 403/429) — 90 минут
5. Фаза 5: Manager config (после 100+ реакций)

---

## ФИНАЛЬНЫЙ ДОКУМЕНТ

**Файл:** `docs/PROJECT_STATE.md`

Главный файл памяти проекта — обновлять при каждом значительном изменении.

Содержит: архитектуру, сервисы, pipeline, БД, конфиги, реакции, dedup, config_name статус, git статус, VPS, замороженные элементы, открытые задачи, документацию, правила, ключевые файлы.

---

## ИТОГОВАЯ СТАТИСТИКА

| Метрика | Значение |
|---------|----------|
| Этапов аудита | 9 |
| Документов создано | 11 |
| Строк документации | ~3 450 |
| Python файлов проанализировано | 319 |
| SQLite баз найдено | 7 |
| Таблиц проанализировано | 25+ |
| Проблем найдено | 22 |
| P0 критичных | 4 |
| P1 важных | 10 |
| P2 желательных | 8 |

---

## ГЛАВНЫЙ ВЫВОД

Haraba Mini — **работающий production проект** с стабильным pipeline, работающим dedup, и функциональной системой реакций.

**Главный блок:** config_name не доходит до feedback → невозможна Config Intelligence (флагманская идея проекта).

**Самый безопасный следующий шаг:** закоммитить 14 modified файлов → push → VPS deploy → проверить get_enabled_recipients() → Fix 7.

---

## ВСЕ ДОКУМЕНТЫ

| Файл | Этап | Назначение |
|------|------|-----------|
| `docs/AUDIT_SNAPSHOT.md` | 0 | Снимок состояния |
| `docs/PROJECT_INVENTORY.md` | 1 | Инвентаризация файлов |
| `docs/DATABASE.md` | 2 | Аудит БД |
| `docs/MANAGERS.md` | 3 | Менеджеры и config_name |
| `docs/REACTIONS.md` | 4 | Реакции и feedback |
| `docs/ARCHITECTURE.md` | 5 | ASCII-схема архитектуры |
| `docs/TELEGRAM.md` | 6 | Telegram боты |
| `docs/CONFIGS.md` | 7 | Конфиги и ENV |
| `docs/DEPLOYMENT.md` | 8 | Deployment/VPS |
| `docs/TECH_DEBT.md` | 9 | Технический долг |
| `docs/PROJECT_STATE.md` | Финал | Главный файл памяти |
