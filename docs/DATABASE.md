# Database Audit — Haraba Mini

> Дата: 2026-06-13
> Режим: только чтение, без изменений

---

## 1. Найденные базы данных

| # | Путь | Размер | Изменён | Таблиц | Строк (всего) | Используется кодом |
|---|------|--------|---------|--------|---------------|-------------------|
| 1 | `results/feedback.db` | 108 KB | 2026-06-12 18:22 | 9 | 47 | **YES** — основная БД |
| 2 | `results/sent_ads.db` | 20 KB | 2026-06-08 17:33 | 3 | 0 | **NO** — пустая, legacy |
| 3 | `results/dedup_store.db` | 0 KB | 2026-06-09 09:19 | 0 | 0 | **NO** — пустая, нет таблиц |
| 4 | `results/feedback_backup_20260612_143122.db` | 108 KB | 2026-06-11 23:01 | 9 | 47 | **NO** — бэкап |
| 5 | `results/feedback_before_users_sync.db` | 108 KB | 2026-06-11 23:01 | 9 | 47 | **NO** — бэкап |

**Chrome profile БД (не проект):**
- `results/auto_ru_chrome_profile/first_party_sets.db` — Chrome internal
- `results/auto_ru_chrome_profile/Default/heavy_ad_intervention_opt_out.db` — Chrome internal

---

## 2. Основная база feedback.db

**Путь:** `results/feedback.db`
**Размер:** 108 KB
**Последнее изменение:** 2026-06-12 18:22:26

**Кто подключается:**
- `feedback_store.py` (line 23): `DB_PATH = RESULTS_DIR / "feedback.db"` — все pipeline модули
- `telegram_sender.py` — через `feedback_store`
- `telegram_feedback_bot.py` — через `feedback_store`
- `admin_bot/services/db_service.py` — через `admin_bot.config.DB_PATH` (env `DB_PATH`, default `results/feedback.db`)
- `ris_analytics.py`: `DB_PATH = "results/feedback.db"`
- `ris_reason_store.py`: `DB_PATH = "results/feedback.db"`
- `feedback_export.py`, `feedback_report.py` — через `feedback_store`

**Все 9 таблиц:**
1. `sent_ads` — отправленные карточки
2. `feedback` — реакции менеджеров
3. `telegram_users` — менеджеры (single source of truth)
4. `telegram_recipients` — legacy получатели
5. `pipeline_runs` — логи запусков pipeline
6. `reaction_reasons` — справочник причин реакций (RIS)
7. `reaction_details` — детали реакций (RIS)
8. `learning_rules` — правила обучения (RIS)
9. `sqlite_sequence` — internal

---

## 3. Таблицы и назначение

### sent_ads — 10 строк

**Назначение:** Dedup tracking — какие карточки отправлены каким менеджерам.

**Первичный ключ:** `PRIMARY KEY (stable_car_key, chat_id)` — composite, per-manager.

**Уникальный индекс:** `UNIQUE INDEX idx_sent_ads_source_external_id ON sent_ads(source, external_id)` — для Auto.ru dedup.

**Индексы:** Нет дополнительных (кроме PK и unique index).

---

### feedback — 1 строка

**Назначение:** Реакции менеджеров (review/think/skip + причины).

**Первичный ключ:** `id INTEGER PRIMARY KEY AUTOINCREMENT`.

**Foreign keys:** Нет (но `reaction_details.feedback_id` ссылается на `feedback.id`).

**Внимание:** Всего 1 строка! Ожидается 37+ (из daily report). Данные могли быть удалены при очистке dedup или это другая БД (VPS).

---

### telegram_users — 5 строк

**Назначение:** Менеджеры и администраторы (single source of truth).

**Первичный ключ:** `id INTEGER PRIMARY KEY AUTOINCREMENT`, `telegram_id INTEGER UNIQUE NOT NULL`.

**Индексы:** `idx_telegram_users_status`, `idx_telegram_users_role`.

---

### telegram_recipients — 3 строки

**Назначение:** Legacy таблица получателей. НЕ используется как source of truth.

**Первичный ключ:** `chat_id TEXT PRIMARY KEY`.

---

### reaction_reasons — 27 строк

**Назначение:** Справочник причин реакций (RIS).

**Первичный ключ:** `id INTEGER PRIMARY KEY AUTOINCREMENT`, `reason_code TEXT NOT NULL UNIQUE`.

---

### reaction_details — 0 строк

**Назначение:** Привязка реакций к причинам.

**Foreign key:** `feedback_id → feedback(id)`.

**Индексы:** `idx_reaction_details_feedback`, `idx_reaction_details_reason`.

**Внимание:** 0 строк! Из daily report ожидается 31+. Данные на VPS, не локально.

---

### learning_rules — 0 строк

**Назначение:** Правила обучения (pending/active/rejected).

**Индексы:** `idx_learning_rules_status`, `idx_learning_rules_target`.

---

### pipeline_runs — 0 строк

**Назначение:** Логи запусков pipeline.

**Внимание:** 0 строк — pipeline логи НЕ сохраняются в БД (только в YAML файлы).

---

## 4. Таблица sent_ads

### Поля (38 колонок)

| Поле | Тип | Описание |
|------|-----|----------|
| `stable_car_key` | TEXT | Dedup ключ: `id:{haraba_id}` |
| `chat_id` | TEXT | ID менеджера в Telegram |
| `card_id` | TEXT | ID карточки (haraba_id) |
| `url` | TEXT | Desktop URL |
| `mobile_url` | TEXT | Mobile URL |
| `haraba_id` | TEXT | Haraba ID |
| `title` | TEXT | Название авто |
| `model_id` | TEXT | ID модели из конфига |
| `year` | INTEGER | Год |
| `price` | INTEGER | Цена |
| `mileage` | INTEGER | Пробег |
| `region` | TEXT | Регион |
| `first_sent_at` | TEXT | Дата первой отправки |
| `last_seen_at` | TEXT | Дата последнего обнаружения |
| `last_sent_at` | TEXT | Дата последней повторной отправки |
| `send_count` | INTEGER | Количество отправок |
| `source` | TEXT | Источник (`haraba` или `auto_ru`) |
| `external_id` | TEXT | Auto.ru external ID |
| `brand` | TEXT | Бренд (Auto.ru) |
| `model` | TEXT | Модель (Auto.ru) |
| `engine` | TEXT | Двигатель |
| `transmission` | TEXT | Коробка |
| `drive` | TEXT | Привод |
| `owners` | INTEGER | Владельцы |
| `auto_ru_price_low` | INTEGER | Auto.ru мин. оценка |
| `auto_ru_price_high` | INTEGER | Auto.ru макс. оценка |
| `auto_ru_estimate_mid` | INTEGER | Auto.ru средняя оценка |
| `auto_ru_status` | TEXT | Auto.ru статус |
| `auto_ru_status_text` | TEXT | Auto.ru текст статуса |
| `auto_ru_delta_percent` | REAL | Auto.ru дельта % |
| `auto_ru_valuation_url` | TEXT | Auto.ru URL оценки |
| `final_verdict` | TEXT | Финальный вердикт |
| `final_recommendation` | TEXT | Финальная рекомендация |
| `final_score` | INTEGER | Финальный скор |
| `final_reasons_json` | TEXT | Причины (JSON) |
| `raw_json` | TEXT | Raw карточка (JSON) |
| `sent_at` | TEXT | Дата отправки (Auto.ru) |
| `config_name` | TEXT | **Имя конфига** |

### Ответы на вопросы

| Вопрос | Ответ | Доказательство |
|--------|-------|----------------|
| Есть ли `card_id`? | ✅ YES | Схема: `card_id TEXT` |
| Есть ли `chat_id`? | ✅ YES | Схема: `chat_id TEXT` |
| Есть ли `config_name`? | ✅ YES (колонка есть) | Схема: `config_name TEXT` |
| Есть ли `sent_at`? | ✅ YES | Схема: `sent_at TEXT` |
| Есть ли `first_sent_at`? | ✅ YES | Схема: `first_sent_at TEXT` |
| Есть ли `send_count`? | ✅ YES | Схема: `send_count INTEGER` |
| UNIQUE constraint? | ✅ YES | `PRIMARY KEY (stable_car_key, chat_id)` + `UNIQUE INDEX (source, external_id)` |
| По каким полям работает dedup? | `(stable_car_key, chat_id)` | Composite PK |
| Dedup глобальный или персональный? | **Персональный** (per chat_id) | PK включает `chat_id` |
| Может ли одна карточка уйти двум менеджерам? | ✅ **ДА** | Подтверждено: 5 карточек × 2 manager = 10 rows |
| Может ли карточка повторно уйти одному менеджеру? | ❌ **НЕТ** | Composite PK `(stable_car_key, chat_id)` предотвращает |
| Есть ли старые записи без config_name? | ✅ **ВСЕ 10 записей** без config_name | `SELECT config_name, COUNT(*) GROUP BY config_name` → `'None': 10` |
| Сколько записей всего? | 10 | `SELECT COUNT(*) FROM sent_ads` |
| Сколько уникальных card_id? | 5 | `COUNT(DISTINCT card_id)` |
| Сколько уникальных chat_id? | 2 (8992376203, 1649929050) | `COUNT(DISTINCT chat_id)` |
| Сколько уникальных config_name? | **0** (все NULL) | `COUNT(DISTINCT config_name) WHERE NOT NULL` = 0 |

### config_name — критическое наблюдение

**Колонка `config_name` существует в схеме, но ВСЕ 10 записей имеют `config_name = NULL`.**

**Доказательство:**
```sql
SELECT config_name, COUNT(*) FROM sent_ads GROUP BY config_name;
-- Результат: 'None': 10
```

**Вывод:** Колонка добавлена (миграция), но код, который заполняет `config_name`, либо:
1. Не закоммичен (из daily report: "НЕ закоммичен, НЕ задеплоен")
2. Не работает на VPS
3. Работает только для новых записей (после деплоя исправленной версии)

---

## 5. Dedup Logic

### Механизм

**Ключ dedup:** `stable_car_key = "id:{haraba_id}"` (fallback к URL hash)

**Функции (feedback_store.py):**
- `check_dedup_with_chat_id(card, chat_id)` → `new` / `same_price` / `price_drop` / `price_increased`
- `mark_sent_with_chat_id(card, chat_id, status)` → INSERT в sent_ads

**Primary Key:** `(stable_car_key, chat_id)` — гарантирует, что одна карточка НЕ будет отправлена одному менеджеру дважды.

### Подтверждение из данных

| Факт | Значение |
|------|----------|
| Дубликаты (stable_car_key + chat_id) | **0** — PK работает |
| Карточек, отправленных 2 менеджерам | **5** из 5 — все карточки ушли обоим активным менеджерам |
| chat_id=8992376203 (owner) | 5 записей |
| chat_id=1649929050 (protocol_skrin) | 5 записей |

**Вывод:** Dedup работает корректно — per-manager, дубликатов нет, мульти-рассылка работает.

---

## 6. Reaction / Feedback Storage

### Таблица feedback

**Поля (32 колонны):**

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER PK | Autoincrement ID |
| `card_id` | TEXT | ID карточки |
| `url` | TEXT | URL |
| `model_id` | TEXT | ID модели |
| `title` | TEXT | Название |
| `price` | INTEGER | Цена |
| `mileage` | INTEGER | Пробег |
| `engine` | TEXT | Двигатель |
| `transmission` | TEXT | Коробка |
| `drive` | TEXT | Привод |
| `region` | TEXT | Регион |
| `owners` | TEXT | Владельцы |
| `score` | INTEGER | Скор |
| `telegram_status` | TEXT | Статус (excellent/good/watch/weak) |
| `action` | TEXT | Реакция (review/think/skip) |
| `comment` | TEXT | Комментарий |
| `created_at` | TEXT | Дата |
| `legal_restrictions` | TEXT | Юр. статус |
| `autoteka_status` | TEXT | Автотека |
| `price_status` | TEXT | Статус цены |
| `price_score` | INTEGER | Скор цены |
| `mileage_score` | INTEGER | Скор пробега |
| `engine_score` | INTEGER | Скор двигателя |
| `transmission_score` | INTEGER | Скор коробки |
| `equipment_score` | INTEGER | Скор комплектации |
| `photo_url` | TEXT | URL фото |
| `photo_count` | INTEGER | Кол-во фото |
| `full_location` | TEXT | Полная локация |
| `telegram_chat_id` | TEXT | **Chat ID менеджера** |
| `telegram_user_id` | TEXT | **User ID менеджера** |
| `telegram_username` | TEXT | Username менеджера |
| `reviewer_role` | TEXT | Роль (owner/manager) |

### Ответы на вопросы

| Вопрос | Ответ | Доказательство |
|--------|-------|----------------|
| Где хранятся реакции? | `feedback` таблица | Схема подтверждена |
| Есть ли `card_id`? | ✅ YES | `card_id TEXT` |
| Есть ли `chat_id`? | ✅ YES (`telegram_chat_id`) | `telegram_chat_id TEXT` |
| Есть ли `manager_id`? | ✅ YES (`telegram_user_id`) | `telegram_user_id TEXT` |
| Есть ли `config_name`? | ❌ **НЕТ** | Колонки `config_name` НЕТ в feedback таблице |
| Есть ли `reason`? | ❌ Нет в feedback, но есть в `reaction_details` | `reaction_details.feedback_id → feedback.id`, `reason_code TEXT` |
| Есть ли `created_at`? | ✅ YES | `created_at TEXT` |
| Можно ли связать реакцию с sent_ads? | ✅ Да, через `card_id` | Обе таблицы имеют `card_id` |
| Можно ли понять какой менеджер нажал? | ✅ Да | `telegram_chat_id`, `telegram_user_id`, `telegram_username`, `reviewer_role` |
| Можно ли хранить несколько реакций от разных менеджеров? | ✅ Да | Каждая реакция — отдельная строка с уникальным `id`, разные `telegram_chat_id` |

### reaction_details (RIS)

**Поля:** `id`, `feedback_id` (FK → feedback.id), `reason_code`, `created_at`

**Связь:** `reaction_details` → `feedback` (1:1 через `feedback_id`)

**Справочник:** `reaction_reasons` — 27 причин (9 review + 9 think + 9 skip)

### config_name в reactions

**Факт:** Колонка `config_name` **ОТСУТСТВУЕТ** в таблице `feedback`.

**Последствия:** Реакции НЕ привязаны к конкретному конфигу. Для Fix 7 (config_name к реакции) потребуется:
1. `ALTER TABLE feedback ADD COLUMN config_name TEXT`
2. Обновить `save_feedback()` в `feedback_store.py`
3. Обновить pipeline для передачи config_name

---

## 7. Managers / Recipients Storage

### telegram_users (ACTIVE — single source of truth)

**Поля:** `id`, `telegram_id` (UNIQUE), `username`, `first_name`, `role`, `status`, `created_at`, `updated_at`

**Текущие данные:**

| telegram_id | username | first_name | role | status |
|-------------|----------|------------|------|--------|
| 8992376203 | — | Haraba | owner | **active** |
| 1649929050 | protocol_skrin | 🫥 | manager | **active** |
| 896670515 | ismailovvv97 | — | manager | **paused** |
| 5649770485 | — | — | manager | **pending** |
| 1445251473 | — | — | manager | **pending** |

**Активные менеджеры (получают рассылку):** 2
- Haraba (owner, 8992376203)
- protocol_skrin (1649929050)

**Функция:** `get_enabled_recipients()` → `SELECT ... WHERE status = 'active'`

### telegram_recipients (LEGACY)

**Поля:** `chat_id` (PK), `user_id`, `username`, `first_name`, `role`, `enabled`, `created_at`

**Данные:**

| chat_id | username | enabled |
|---------|----------|---------|
| 1649929050 | protocol_skrin | 1 |
| 8992376203 | — | 1 |
| 896670515 | ismailovvv97 | 1 |

**Внимание:** `ismailovvv97` имеет `enabled=1` в legacy таблице, но `status='paused'` в telegram_users. Это рассинхрон.

### Связь manager → config

**Факт:** НЕТ связи manager → config_name в БД.
- Нет таблицы `manager_configs`
- Нет колонки `config_name` в `telegram_users`
- Нет mapping manager ↔ search config

---

## 8. Legacy Databases

### sent_ads.db

- **Размер:** 20 KB
- **Изменён:** 2026-06-08 (5 дней назад)
- **Таблицы:** `sent_ads`, `feedback`, `sqlite_sequence`
- **Данные:** 0 строк во всех таблицах
- **Используется:** **НЕТ** — ни один файл кода не ссылается на `sent_ads.db`
- **Вердикт:** LEGACY, безопасен к удалению

### dedup_store.db

- **Размер:** 0 KB (пустой файл)
- **Изменён:** 2026-06-09
- **Таблицы:** **Нет**
- **Используется:** **НЕТ**
- **Вердикт:** BROKEN/EMPTY, безопасен к удалению

### feedback_backup_*.db / feedback_before_*.db

- **Размер:** 108 KB каждый (копия feedback.db)
- **Используется:** **НЕТ** — бэкапы
- **Вердикт:** BACKUP, оставить

---

## 9. Риски

| # | Риск | Уровень | Описание | Доказательство |
|---|------|---------|----------|----------------|
| 1 | **config_name ВСЕГДА NULL в sent_ads** | HIGH | Колонка есть, но ни одна из 10 записей не заполнена. Блок 2 не закоммичен/не задеплоен. | `SELECT config_name, COUNT(*) GROUP BY config_name` → `'None': 10` |
| 2 | **config_name НЕТ в feedback** | HIGH | Реакции НЕ привязаны к конфигу. Fix 7 требует ALTER TABLE. | `PRAGMA table_info(feedback)` — нет config_name |
| 3 | **reaction_details = 0 строк** | MEDIUM | Локально 0, но из daily report ожидается 31+. Данные на VPS, не синхронизированы локально. | `SELECT COUNT(*) FROM reaction_details` → 0 |
| 4 | **feedback = 1 строка** | MEDIUM | Локально 1, ожидается 37+. Данные на VPS. | `SELECT COUNT(*) FROM feedback` → 1 |
| 5 | **pipeline_runs = 0 строк** | LOW | Pipeline НЕ пишет логи в БД. Только YAML файлы. | `SELECT COUNT(*) FROM pipeline_runs` → 0 |
| 6 | **sent_ads.db — пустой дубликат** | LOW | 0 строк, не используется кодом. | Файл 20 KB, 0 rows |
| 7 | **dedup_store.db — пустой файл** | LOW | 0 bytes, нет таблиц. | Файл 0 bytes |
| 8 | **telegram_recipients рассинхрон с telegram_users** | MEDIUM | ismailovvv97: enabled=1 в legacy, paused=active в users. | `telegram_recipients` row vs `telegram_users` row |
| 9 | **Нет FK между sent_ads и feedback** | LOW | Связь только по `card_id` (текст, не FK). | Схема не содержит FK |
| 10 | **Нет связи manager → config** | MEDIUM | Невозможно определить какой менеджер какой конфиг получает. | Нет такой таблицы/колонки |

---

## 10. Требует проверки

| № | Что | Почему |
|---|-----|--------|
| 1 | **Данные на VPS** | Локальная БД имеет 1 feedback, 0 reaction_details, 10 sent_ads. VPS может иметь другие данные (37+ feedback, 31+ reaction_details). |
| 2 | **config_name на VPS** | Закоммичен ли код, заполняющий config_name? Работает ли на VPS? |
| 3 | **cron пишет в pipeline_runs?** | Таблица существует, но 0 строк. Pipeline сохраняет в YAML, а не в БД. |
| 4 | **learning_rules = 0** | Правила ещё не генерировались или миграция не создала таблицу? (Таблица есть, данных нет). |

---

## 11. Вывод

### Краткие ответы

| Вопрос | Ответ |
|--------|-------|
| **Какая база основная?** | `results/feedback.db` — единственная используемая |
| **Сколько таблиц?** | 9 (8 пользовательских + sqlite_sequence) |
| **Dedup глобальный или manager-aware?** | **Manager-aware** — composite PK `(stable_car_key, chat_id)` |
| **config_name реально используется?** | Колонка **есть в sent_ads**, но **ВСЕ значения NULL**. В `feedback` колонки **нет вообще**. |
| **Реакции привязаны к менеджеру?** | ✅ Да — `telegram_chat_id`, `telegram_user_id`, `telegram_username`, `reviewer_role` |
| **Реакции привязаны к конфигу?** | ❌ Нет — `config_name` отсутствует в `feedback` |
| **Какие таблицы критичны?** | `sent_ads` (dedup), `telegram_users` (менеджеры), `feedback` (реакции) |
| **Что опасно менять?** | PK `(stable_car_key, chat_id)`, колонку `stable_car_key`, таблицу `telegram_users` |
| **Что нужно перед manager-aware dedup?** | Уже работает! Dedup уже per-manager. |
| **Что нужно перед config-aware reactions?** | 1. `ALTER TABLE feedback ADD COLUMN config_name TEXT` 2. Обновить `save_feedback()` 3. Pipeline передаёт config_name |

### Можно ли безопасно строить персональный dedup по менеджерам?

**ДА, уже работает.** Composite PK `(stable_car_key, chat_id)` обеспечивает per-manager dedup.

### Что нужно для привязки реакций к конфигу (Fix 7)?

1. Миграция: `ALTER TABLE feedback ADD COLUMN config_name TEXT`
2. Код: `save_feedback()` принимает `config_name` параметр
3. Pipeline: `run_daily_pipeline.py` → `telegram_sender.py` передают `config_name` в save_feedback
4. Audit: `config_name` пишется при каждой реакции

**Без этого невозможно:**
- Определить какой конфиг даёт хорошие/плохие реакции
- Построить Config Intelligence
- Сделать config_suggestions
