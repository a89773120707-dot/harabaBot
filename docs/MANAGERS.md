# Managers / Recipients / Config Audit

> Дата: 2026-06-13
> Режим: только чтение, без изменений

---

## 1. Краткий вывод

| Метрика | Значение | Доказательство |
|---------|----------|----------------|
| Активных получателей | **2** (owner + 1 manager) | `SELECT * FROM telegram_users WHERE status='active'` |
| Получателей всего | **5** (2 active, 1 paused, 2 pending) | `SELECT COUNT(*) FROM telegram_users` |
| Legacy recipients | **3** (все enabled=1, включая paused) | `SELECT * FROM telegram_recipients` |
| Manager-aware dedup | **Работает** — PK `(stable_car_key, chat_id)` | Схема sent_ads, 0 дубликатов |
| config_name в sent_ads | **Колонка есть, все 10 записей = NULL** | `SELECT config_name, COUNT(*) GROUP BY config_name` → `'None': 10` |
| config_name в feedback | **Колонки НЕТ** | `PRAGMA table_info(feedback)` — 32 колонны, config_name отсутствует |
| Персональные конфиги | **НЕТ** | Нет таблицы, нет колонки, нет кода |
| Реакции привязаны к менеджеру | **Да** — `telegram_chat_id`, `telegram_user_id`, `reviewer_role` | Схема feedback |
| Реакции привязаны к конфигу | **Нет** | config_name нет в feedback |

---

## 2. Где хранятся менеджеры

### telegram_users — ЕДИНСТВЕННЫЙ источник правды

**Файл:** `feedback_store.py` (line 519-590)

**Схема:**
```sql
CREATE TABLE telegram_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    role TEXT DEFAULT 'manager',  -- 'owner', 'manager'
    status TEXT DEFAULT 'pending', -- 'pending', 'active', 'paused', 'disabled'
    created_at TEXT,
    updated_at TEXT
);
```

**Индексы:** `idx_telegram_users_status`, `idx_telegram_users_role`

**Текущие данные:**

| telegram_id | username | first_name | role | status |
|-------------|----------|------------|------|--------|
| 8992376203 | — | Haraba | owner | active |
| 1649929050 | protocol_skrin | 🫥 | manager | active |
| 896670515 | ismailovvv97 | — | manager | paused |
| 5649770485 | — | — | manager | pending |
| 1445251473 | — | — | manager | pending |

### telegram_recipients — LEGACY

**Файл:** `feedback_store.py` (line 557-590 — функции больше не используют эту таблицу)

**Схема:**
```sql
CREATE TABLE telegram_recipients (
    chat_id TEXT PRIMARY KEY,
    user_id TEXT,
    username TEXT,
    first_name TEXT,
    role TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT
);
```

**Текущие данные:** 3 записи, все `enabled=1`.

**Рассинхрон:** `ismailovvv97` (telegram_id=896670515) имеет `enabled=1` в legacy, но `status='paused'` в `telegram_users`. Legacy таблица НЕ используется для рассылки.

**Доказательство:** `get_enabled_recipients()` (line 593) делает `SELECT ... FROM telegram_users WHERE status='active'` — telegram_recipients не задействована.

---

## 3. Telegram users / recipients — полный анализ

### Где создаются получатели

| Функция | Файл:строка | Когда вызывается |
|---------|-------------|-----------------|
| `upsert_telegram_user()` | `feedback_store.py:519` | Admin bot: approve/pause/resume/disable |
| `register_recipient()` | `feedback_store.py:557` | Telegram feedback bot: при первом `/start` (backward compat) |
| `/start` handler | `telegram_feedback_bot.py:117` | Когда новый пользователь пишет /start |
| `/register_owner` | `telegram_feedback_bot.py:177` | Owner self-registration |
| `/register_manager` | `telegram_feedback_bot.py:216` | Manager self-registration |
| `ensure_owner_exists()` | `admin_bot/services/db_service.py` | При старте admin bot |

### Где включаются/отключаются

| Функция | Файл:строка | Что делает |
|---------|-------------|------------|
| `get_enabled_recipients()` | `feedback_store.py:593` | SELECT WHERE status='active' |
| `disable_recipient()` | `feedback_store.py:613` | UPDATE status='disabled' |
| `set_user_status()` | `admin_bot/services/users_service.py` | Admin bot: approve/pause/resume/disable |
| `/disable_me` | `telegram_feedback_bot.py:267` | User self-disable |

### Где хранится enabled

- **telegram_users:** `status` колонка ('active' = enabled, другие = disabled)
- **telegram_recipients:** `enabled` INTEGER (0/1) — LEGACY, не используется

### Роли

| Роль | Где определяется | Значение |
|------|-----------------|----------|
| `owner` | `telegram_users.role` | Полная админка, не может быть paused/disabled |
| `manager` | `telegram_users.role` | Получает карточки, ставит реакции |

### reviewer_role

**Поле:** `feedback.reviewer_role TEXT`

**Заполняется:** В `_save_feedback_for_chat()` (`telegram_feedback_bot.py:302-315`) — lookup из `get_all_recipients()` по chat_id.

**Возможные значения:** 'owner', 'manager', 'viewer' (fallback)

---

## 4. get_enabled_recipients()

### Файл и функция

**Файл:** `feedback_store.py`, строки 593-609

```python
def get_enabled_recipients():
    init_db()
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT telegram_id as chat_id, username, first_name, role
        FROM telegram_users
        WHERE status = 'active'
        ORDER BY role
    """)
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows
```

### Кто вызывает

| Файл | Строка | Контекст |
|------|--------|----------|
| `telegram_sender.py` | 482 | `run_send()` — получение списка получателей для рассылки |
| `telegram_feedback_bot.py` | 255 | `show_recipients()` — команда /recipients |
| `scripts/verify_users_sync.py` | 55 | Верификация синхронизации |

### Что возвращает

```python
[
    {"chat_id": 8992376203, "username": None, "first_name": "Haraba", "role": "owner"},
    {"chat_id": 1649929050, "username": "protocol_skrin", "first_name": "🫥", "role": "manager"},
]
```

### Ответы на вопросы

| Вопрос | Ответ |
|--------|-------|
| Возвращает ли chat_id? | ✅ Да (`telegram_id as chat_id`) |
| Возвращает ли name? | ✅ Да (`username`, `first_name`) |
| Возвращает ли config_name? | ❌ **НЕТ** — в telegram_users нет config_name |
| Возвращает ли role? | ✅ Да |
| Возвращает ли status? | ❌ Нет (только active, WHERE filter) |

### Bug и исправление

**Bug (из daily report):** `get_enabled_recipients()` возвращала ВСЕХ пользователей, игнорируя `status`.

**Причина:** На VPS была старая версия `feedback_store.py` без `WHERE status = 'active'`.

**Исправление:** Коммит `36ab6dc` — `Fix /recipients command to show only active users`.

**Локально:** ✅ Исправлено — код содержит `WHERE status = 'active'`.

**На VPS:** ⚠ **ТРЕБУЕТ ПРОВЕРКИ** — файл `feedback_store.py` имеет local modifications (git status показывает modified). Если modified версия содержит fix — OK. Если fix только в unstaged changes и не задеплоен — bug остаётся.

**Риск для рассылки:** Если на VPS старая версия — paused/pending пользователи получают карточки.

---

## 5. config_name

### Где config_name добавлен в схему

**Файл:** `feedback_store.py`, строки 196-199 (внутри `init_db()`):

```python
c.execute("PRAGMA table_info(sent_ads)")
sent_ads_cols = {row[1] for row in c.fetchall()}
if "config_name" not in sent_ads_cols:
    log.info("Migrating sent_ads: adding config_name column")
    c.execute("ALTER TABLE sent_ads ADD COLUMN config_name TEXT")
```

**Схема sent_ads подтверждает:** `config_name TEXT` присутствует.

### Где config_name записывается в sent_ads

**Файл:** `feedback_store.py`, строка 547 (в `mark_sent_with_chat_id()`):

```python
config_name = card.get("config_name", "unknown")
```

И строка 553 (INSERT):
```python
c.execute("""
    INSERT OR IGNORE INTO sent_ads (
        stable_car_key, card_id, url, mobile_url, haraba_id,
        title, model_id, year, price, mileage, region, chat_id, config_name,
        first_sent_at, last_seen_at, last_sent_at, send_count
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
""", (
    stable_key, card_id, url, mobile_url, haraba_id,
    card.get("title", ""), card.get("model_id", ""),
    card.get("year", 0), card.get("price", 0),
    card.get("mileage", 0), card.get("region", ""), str(chat_id), config_name,
    now, now, now,
))
```

### Где config_name читается

**Нигде не читается для бизнес-логики.** Только присутствует в схеме и записывается.

**Факт:** Нет SELECT-запросов, которые используют `config_name` для фильтрации, аналитики или dedup.

### Почему текущие 10 записей имеют config_name = NULL

**Причина:** Данные записаны ДО того, как код заполнения config_name был добавлен в pipeline.

**Цепочка:**
1. `run_daily_pipeline.py:step_audit()` — устанавливает `c["config_name"]` (line 205-211) ✅
2. `run_daily_pipeline.py:step_send()` — вызывает `telegram_sender.py` как subprocess
3. `telegram_sender.py:load_audited_candidates()` — тоже устанавливает `c["config_name"]` (line 119-128) ✅
4. `telegram_sender.py:run_send()` — вызывает `mark_sent_with_chat_id(card, ...)` ✅
5. `feedback_store.py:mark_sent_with_chat_id()` — читает `card.get("config_name", "unknown")` ✅

**Но:** 10 записей в БД были записаны при тестовой рассылке (`--limit 3`) 2026-06-12. Если в тот момент код был НЕ закоммичен/не задеплоен на VPS, то config_name был NULL.

**Вывод:** Код заполнения config_name **присутствует** в локальных файлах (modified), но:
- НЕ закоммичен в git (`git status` показывает modified)
- На VPS может быть старая версия

### Block 2 — статус

| Аспект | Статус |
|--------|--------|
| Код написан | ✅ `run_daily_pipeline.py:step_audit()` line 205-211 |
| Код написан | ✅ `telegram_sender.py:load_audited_candidates()` line 119-128 |
| Код написан | ✅ `feedback_store.py:mark_sent_with_chat_id()` line 547 |
| Миграция БД | ✅ `feedback_store.py:init_db()` line 196-199 |
| Закоммичен | ❌ **НЕТ** — 14 modified файлов, включая эти 3 |
| Задеплоен на VPS | ❌ **ТРЕБУЕТ ПРОВЕРКИ** — если VPS = `origin/main`, то НЕ задеплоен |
| Тесты | ✅ `tests/test_block2_config_name.py` |

### Связь manager → config_name

**НЕТ.** Нет таблицы, нет колонки, нет кода.

**Текущая модель:** Один общий пул конфигов (17 моделей) → все active менеджеры получают все карточки из этого пула.

### config_name в feedback

**❌ НЕТ.** Колонка `config_name` **отсутствует** в таблице `feedback`.

**Что нужно для привязки реакций к конфигу:**
1. `ALTER TABLE feedback ADD COLUMN config_name TEXT`
2. Обновить `save_feedback()` в `feedback_store.py` — добавить параметр `config_name`
3. Обновить `_save_feedback_for_chat()` в `telegram_feedback_bot.py` — передать `config_name` из карточки
4. Обновить pipeline — `config_name` должен быть в `card_data` при реакции

---

## 6. Текущий flow рассылки

### Полная цепочка (фактическая)

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Сбор карточек                                        │
│ Файл: run_daily_pipeline.py → step_collect_cards()           │
│ Функция: subprocess → mobile_first_page_sampler.py           │
│ Вход: --limit 30                                             │
│ Выход: results/latest_cards_raw.json                         │
│ Потери: Нет                                                  │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Enrichment (фото)                                    │
│ Файл: run_daily_pipeline.py → step_enrich_cards()            │
│ Функция: photo_parser.enrich_cards_with_photos()             │
│ Вход: latest_cards_raw.json                                  │
│ Выход: results/latest_cards_enriched.json                    │
│ Поля добавляются: photo_url, photo_count, photos             │
│ Потери: Нет                                                  │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Audit (hard-stop + scoring)                          │
│ Файл: run_daily_pipeline.py → step_audit()                   │
│ Функции: check_region_allowed, check_legal_restrictions,     │
│          score_price, score_mileage, score_engine, etc.       │
│ Вход: latest_cards_enriched.json                             │
│ Выход: results/latest_cards_audited.json                     │
│ Поля добавляются: model_id, config_name, score, decision,    │
│          price_score, mileage_score, engine_score, etc.       │
│ ⚠ config_name устанавливается ЗДЕСЬ (line 205-211)          │
│ Потери: do_not_send карточки отсеиваются                     │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: Telegram отправка                                    │
│ Файл: run_daily_pipeline.py → step_send()                    │
│ Функция: subprocess → telegram_sender.py --send              │
│                                                                │
│   4a. Load candidates                                        │
│       Файл: telegram_sender.py → load_audited_candidates()   │
│       Вход: telegram_candidates_audited.json                 │
│       Enrich из mobile_first_page_sample.json                │
│       ⚠ config_name пересчитывается ЗДЕСЬ (line 119-128)    │
│                                                                │
│   4b. Get recipients                                         │
│       Функция: get_enabled_recipients()                      │
│       Возвращает: [{chat_id, username, first_name, role}]    │
│       ⚠ config_name НЕТ в recipients                        │
│                                                                │
│   4c. Для каждого recipient → для каждой карточки:           │
│       - check_dedup_with_chat_id(card, chat_id)              │
│       - send_car_card_sync(bot_token, chat_id, card, config) │
│       - mark_sent_with_chat_id(card, chat_id, status)        │
│         ⚠ config_name читается из card (line 547)           │
│         ⚠ Если card["config_name"] = None → "unknown"       │
│                                                                │
│ Выход: results/telegram_sender_report.yaml                   │
│ Запись в БД: sent_ads (stable_car_key + chat_id PK)          │
│ ⚠ config_name записывается, но может быть NULL              │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: Реакция менеджера                                    │
│ Файл: telegram_feedback_bot.py → button_handler()            │
│ Функция: reason_handler() → _save_feedback_for_chat()        │
│ Вход: inline button callback (review/think/skip:card_id)     │
│                                                                │
│   5a. card_data_loader.load_card_data()                      │
│       Загружает card_data из audited JSON + mobile sample    │
│       ⚠ config_name МОЖЕТ быть в card_data                  │
│         (если audited JSON содержит config_name)             │
│                                                                │
│   5b. _save_feedback_for_chat()                              │
│       Формирует feedback_card dict                           │
│       ⚠ config_name НЕ передаётся в feedback_card!          │
│       Поля: card_id, url, model_id, title, price, ...        │
│       НЕТ config_name                                        │
│                                                                │
│   5c. save_feedback(feedback_card, action, comment)          │
│       INSERT INTO feedback (32 колонны)                      │
│       ⚠ НЕТ колонны config_name в feedback                   │
│                                                                │
│   5d. save_reaction_detail(feedback_id, reason_code)         │
│       INSERT INTO reaction_details                           │
│                                                                │
│ Запись в БД: feedback + reaction_details                     │
│ Потери: config_name ТЕРЯЕТСЯ на шаге 5b                      │
└─────────────────────────────────────────────────────────────┘
```

### Где теряются данные

| Данные | Где теряется | Почему |
|--------|-------------|--------|
| **config_name** | `telegram_feedback_bot.py:_save_feedback_for_chat()` | Не включается в `feedback_card` dict |
| **config_name** | `feedback` таблица | Колонка не существует |
| **manager identity** | Нет потерь | `telegram_chat_id`, `telegram_user_id`, `reviewer_role` сохраняются |
| **config_name в sent_ads** | Может быть NULL | Если pipeline запущен со старой версией кода |

---

## 7. Персональные конфиги менеджеров

### Текущее состояние

| Элемент | Есть? | Где? |
|---------|-------|------|
| Таблица manager_configs | ❌ Нет | — |
| Колонка config_name в telegram_users | ❌ Нет | `PRAGMA table_info(telegram_users)` — 8 колонок, нет config_name |
| manager_id → config mapping | ❌ Нет | — |
| Per-manager search filters | ❌ Нет | — |
| YAML с manager configs | ❌ Нет | `config/` содержит только общие конфиги |

### Как сейчас фильтруются карточки

**Фильтрация ОБЩАЯ, не персональная.**

1. `awd_liquid_full_config.yaml` — 17 моделей, единый для всех
2. `step_audit()` в `run_daily_pipeline.py` — фильтрует через `check_region_allowed()`, `check_legal_restrictions()`, scoring
3. Все active менеджеры получают **одинаковый** набор карточек (после dedup per-manager)

**Нет персонализации.** Каждый менеджер видит те же карточки, что и остальные.

### Что нужно для перехода на manager_config

1. **Схема БД:** Новая таблица `manager_configs`:
   ```sql
   CREATE TABLE manager_configs (
       id INTEGER PRIMARY KEY,
       telegram_id INTEGER NOT NULL,
       config_name TEXT NOT NULL,
       enabled INTEGER DEFAULT 1,
       FOREIGN KEY (telegram_id) REFERENCES telegram_users(telegram_id)
   );
   ```

2. **Изменение pipeline:**
   - `get_enabled_recipients()` → возвращать также `config_names` менеджера
   - Для каждого manager → фильтровать карточки по его конфигам
   - Dedup остаётся per-manager

3. **Изменение feedback:**
   - Добавить `config_name` в `feedback` таблицу
   - Передать `config_name` при `_save_feedback_for_chat()`

---

## 8. Что уже готово

| Элемент | Статус | Доказательство |
|---------|--------|----------------|
| Manager-aware dedup | ✅ Работает | PK `(stable_car_key, chat_id)`, 0 дубликатов |
| telegram_users как source of truth | ✅ Работает | `get_enabled_recipients()` → `WHERE status='active'` |
| Статусы пользователей (pending/active/paused/disabled) | ✅ Работает | 5 пользователей с разными статусами |
| Роли (owner/manager) | ✅ Работает | owner=8992376203, manager=1649929050 |
| config_name колонка в sent_ads | ✅ Есть в схеме | `PRAGMA table_info(sent_ads)` — 38 колонок |
| Код заполнения config_name | ✅ Написан | `run_daily_pipeline.py:205-211`, `telegram_sender.py:119-128` |
| config_name в mark_sent_with_chat_id | ✅ Написан | `feedback_store.py:547` |
| Реакции привязаны к менеджеру | ✅ Работает | `telegram_chat_id`, `telegram_user_id`, `reviewer_role` |
| RIS причины реакций | ✅ Работает | 27 причин в `reaction_reasons`, inline клавиатуры |
| Foreign key reaction_details → feedback | ✅ Есть | `FOREIGN KEY (feedback_id) REFERENCES feedback(id)` |
| Admin bot управление менеджерами | ✅ Работает | approve/pause/resume/disable через inline кнопки |

---

## 9. Что не готово

| Элемент | Что нужно | Приоритет |
|---------|-----------|-----------|
| config_name НЕ закоммичен | Commit + push + VPS deploy | **HIGH** |
| config_name в sent_ads = NULL (10 записей) | Задеплоить исправленный код | **HIGH** |
| config_name НЕТ в feedback | ALTER TABLE + обновить save_feedback + telegram_feedback_bot | **HIGH** (Fix 7) |
| config_name НЕТ в recipients | Новая таблица или колонка в telegram_users | MEDIUM |
| Персональные конфиги менеджеров | manager_configs таблица + pipeline changes | MEDIUM |
| Аналитика по config_name | Config report, config suggestions | LOW (после 100+ реакций) |
| Pipeline логи в БД | pipeline_runs = 0 строк | LOW |

---

## 10. Риски

| # | Риск | Уровень | Описание | Доказательство |
|---|------|---------|----------|----------------|
| 1 | **config_name не закоммичен** | HIGH | 3 файла modified, код не в git. VPS может не иметь fix. | `git status` → modified: feedback_store.py, run_daily_pipeline.py, telegram_sender.py |
| 2 | **config_name = NULL во всех 10 записях sent_ads** | HIGH | Колонка есть, данные пустые. Невозможно аналитику. | `SELECT config_name, COUNT(*) GROUP BY config_name` → `'None': 10` |
| 3 | **config_name НЕТ в feedback** | HIGH | Реакции НЕ привязаны к конфигу. Fix 7 невозможен без ALTER TABLE. | `PRAGMA table_info(feedback)` — 32 колонны, config_name отсутствует |
| 4 | **_save_feedback_for_chat() не передаёт config_name** | HIGH | Даже если бы колонка была — данные не записываются. | `telegram_feedback_bot.py:302-330` — feedback_card dict не содержит config_name |
| 5 | **get_enabled_recipients() не возвращает config_name** | MEDIUM | Невозможно определить какие конфиги получает менеджер. | Функция возвращает только `{chat_id, username, first_name, role}` |
| 6 | **Нет связи manager → config** | MEDIUM | Все менеджеры получают одинаковые карточки. | Нет таблицы, нет колонки, нет кода |
| 7 | **telegram_recipients рассинхрон** | LOW | ismailovvv97: enabled=1 в legacy, paused в users. | Legacy таблица не используется, но данные inconsistent |
| 8 | **Нет FK между sent_ads и feedback** | LOW | Связь только по card_id (текст). Нет CASCADE. | Схема не содержит FK между этими таблицами |

---

## 11. Требует проверки

| № | Что | Почему |
|---|-----|--------|
| 1 | **config_name на VPS** | Файлы modified локально. Закоммичены ли? Задеплоены ли на VPS? |
| 2 | **get_enabled_recipients() на VPS** | Из daily report: "НЕ исправлено" — содержит ли VPS версия `WHERE status='active'`? |
| 3 | **Данные на VPS** | Локально: 1 feedback, 10 sent_ads. VPS может иметь 37+ feedback, 350+ sent_ads. |
| 4 | **config_name в VPS sent_ads** | Есть ли записи с заполненным config_name на VPS? |

---

## 12. Рекомендуемая целевая архитектура

### Текущая архитектура

```
awd_liquid_full_config.yaml (17 моделей)
  ↓
pipeline: collect → enrich → audit → dedup → send
  ↓
all active managers receive SAME cards
  ↓
reactions saved WITHOUT config_name
```

### Целевая архитектура (для Config Intelligence)

```
awd_liquid_full_config.yaml (17 моделей)
  ↓
pipeline: collect → enrich → audit → dedup → send
  ↓
all active managers receive SAME cards (без изменений)
  ↓
reactions saved WITH config_name ← КРИТИЧНО
  ↓
config analytics: какие конфиги дают good/bad reactions
  ↓
config suggestions: owner approves changes
  ↓
config versions: track changes over time
```

### Минимальные изменения для Fix 7

1. **БД:** `ALTER TABLE feedback ADD COLUMN config_name TEXT`
2. **feedback_store.py:** `save_feedback(card, action, comment)` → добавить `config_name` параметр
3. **telegram_feedback_bot.py:** `_save_feedback_for_chat()` → добавить `config_name` в `feedback_card` dict
4. **card_data_loader.py:** загружать `config_name` из audited JSON
5. **pipeline:** audited JSON должен содержать `config_name` (уже делает `step_audit()`)

---

## КРАТКИЙ ОТЧЁТ

| # | Вопрос | Ответ |
|---|--------|-------|
| 1 | Сколько активных получателей сейчас? | **2** (owner Haraba + manager protocol_skrin) |
| 2 | Где хранится список менеджеров? | `telegram_users` таблица в `results/feedback.db` |
| 3 | Работает ли manager-aware dedup? | **Да** — PK `(stable_car_key, chat_id)`, 0 дубликатов |
| 4 | Почему config_name = NULL? | Код написан, но **НЕ закоммичен** и, вероятно, **НЕ задеплоен** на VPS |
| 5 | Есть ли персональные конфиги? | **Нет** — общий пул, все менеджеры получают одинаковые карточки |
| 6 | Что нужно сделать следующим для manager_config? | **Fix 7**: config_name в feedback → собрать 100+ реакций → Config Intelligence |
| 7 | Какие файлы самые критичные? | 1. `feedback_store.py` (БД + dedup), 2. `telegram_sender.py` (отправка), 3. `telegram_feedback_bot.py` (реакции), 4. `run_daily_pipeline.py` (orchestrator), 5. `telegram_card_formatter.py` (формат карточки) |
