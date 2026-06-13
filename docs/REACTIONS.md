# Reactions / Feedback Audit

> Дата: 2026-06-13
> Режим: только чтение, без изменений

---

## 1. Краткий вывод

| Вопрос | Ответ | Доказательство |
|--------|-------|----------------|
| Реакции сохраняются? | ✅ Да | `feedback` таблица, `save_feedback()` |
| Можно ли понять менеджера? | ✅ Да | `telegram_chat_id`, `telegram_user_id`, `reviewer_role` |
| Можно ли понять config_name? | ❌ **Нет** | Нет колонны в feedback, нет в callback, нет в card_data |
| Где теряется config_name? | **В 3 местах** (см. раздел 7) | Анализ потока данных |
| Reaction reasons работают? | ✅ Да | 27 причин в `reaction_reasons`, inline клавиатуры |
| Связь feedback ↔ sent_ads? | ⚠ Только по `card_id` (текст, не FK) | Схема БД |

---

## 2. Основные файлы

| Файл | Назначение | Критичность |
|------|------------|-------------|
| `telegram_feedback_bot.py` (712 строк) | Обработка реакций: кнопки → reason → comment → БД | **HIGH** |
| `feedback_store.py` (650 строк) | SQLite: save_feedback, init_db, dedup, recipients | **HIGH** |
| `ris_reason_store.py` (58 строк) | Сохранение reaction_details, get_last_feedback_id | **MEDIUM** |
| `ris_reason_keyboard.py` (160 строк) | Inline клавиатуры причин, веса, промпты | **MEDIUM** |
| `card_data_loader.py` (59 строк) | Загрузка card_data из audited JSON + sample | **MEDIUM** |
| `ris_analytics.py` (76 строк) | Аналитика: learning_report, learning_reasons, config_report | **MEDIUM** |
| `telegram_sender.py` (570 строк) | Отправка карточек + build_inline_keyboard | **HIGH** |
| `run_daily_pipeline.py` (420 строк) | Orchestrator: audit → config_name → send | **HIGH** |
| `feedback_export.py` | Экспорт feedback в YAML (CLI) | LOW |
| `feedback_report.py` | Аналитика реакций (CLI dashboard) | LOW |

---

## 3. Callback flow

### Полная цепочка реакции

```
┌──────────────────────────────────────────────────────────────────┐
│ STEP 1: Карточка отправляется в Telegram                          │
│ Файл: telegram_sender.py → send_car_card_sync()                   │
│ Функция: send_car_card_async()                                    │
│ Входные данные: bot_token, chat_id, card, config                  │
│ Выходные данные: Telegram message с inline кнопками               │
│                                                                    │
│ Callback_data кнопок (telegram_sender.py:192-204):                │
│   "review:{card_id}"     — 👀 Посмотреть                          │
│   "think:{card_id}"      — 🤔 Подумать                            │
│   "skip:{card_id}"       — ⏭ Скип                                │
│   "desc:{card_id}"       — 📖 Описание                            │
│   "photos:{card_id}"     — 📷 Ещё фото                            │
│                                                                    │
│ ⚠ callback_data содержит ТОЛЬКО card_id.                          │
│ ⚠ config_name НЕ передаётся в callback_data.                      │
│ ⚠ model_id НЕ передаётся в callback_data.                         │
│ ⚠ stable_car_key НЕ передаётся в callback_data.                   │
└──────────────────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 2: Пользователь нажимает кнопку                              │
│ Telegram отправляет callback_query:                               │
│   callback_data = "review:171156820"                              │
│   chat_id = 8992376203 (ID пользователя)                          │
│   user.id = 8992376203                                            │
│   user.username = ...                                             │
│   message.message_id = ID сообщения с карточкой                   │
└──────────────────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 3: Callback парсится                                         │
│ Файл: telegram_feedback_bot.py → button_handler()                 │
│ Вход: callback_data = "review:171156820"                          │
│ Парсинг: action = "review", card_id = "171156820"                 │
│                                                                    │
│ card_data = card_data.get(card_id)  ← load_card_data()            │
│                                                                    │
│ ⚠ card_data НЕ содержит config_name!                              │
│   (card_data_loader.py не загружает config_name)                  │
│                                                                    │
│ pending_feedback[chat_id] = {                                     │
│     "card_id": "171156820",                                       │
│     "action": "review",                                           │
│     "card_message_id": ...,                                       │
│     "card_data": {                                                │
│         "card_id", "title", "url", "model_id", "price",           │
│         "mileage", "year", "score", "decision",                   │
│         "engine", "transmission", "drive", "region",              │
│         "owners", "legal_restrictions", "autoteka_status",        │
│         "price_status", "price_score", "mileage_score",           │
│         "engine_score", "transmission_score", "equipment_score",  │
│         "photo_url", "photo_count", "full_location"               │
│         ← НЕТ config_name                                         │
│         ← НЕТ stable_car_key                                      │
│     }                                                             │
│ }                                                                 │
└──────────────────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 4: Показываются кнопки причин (RIS)                          │
│ Файл: telegram_feedback_bot.py → button_handler()                 │
│ Функция: reason_keyboard(action)                                  │
│                                                                    │
│ Кнопки:                                                           │
│   review: 💰 Хорошая цена, 📉 Небольшой пробег, ...              │
│   think: 💸 Высокая цена, 📈 Большой пробег, ...                 │
│   skip: ❌ Слишком дорого, ❌ Слишком большой пробег, ...        │
│                                                                    │
│ Callback_data причин: "reason:good_price"                         │
│   (НЕ содержит card_id, НЕ содержит config_name)                  │
└──────────────────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 5: Пользователь выбирает причину                             │
│ Файл: telegram_feedback_bot.py → reason_handler()                 │
│ Вход: callback_data = "reason:good_price"                         │
│ Парсинг: reason_code = "good_price"                               │
│                                                                    │
│ pending_reason[chat_id] = "good_price"                            │
│                                                                    │
│ Если needs_comment(reason_code):                                  │
│   → ждём текстовый комментарий                                    │
│ Иначе:                                                            │
│   → сразу сохраняем feedback                                      │
└──────────────────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 6: Сохранение feedback                                       │
│ Файл: telegram_feedback_bot.py → _save_feedback_for_chat()        │
│ или text_handler() (если комментарий)                             │
│                                                                    │
│ Формируется feedback_card dict:                                   │
│   card_id = card.get("card_id")         ✅                        │
│   url = card.get("url")                 ✅                        │
│   model_id = card.get("model_id")       ✅                        │
│   title, price, mileage, year, score    ✅                        │
│   engine, transmission, drive, region   ✅                        │
│   owners, legal_restrictions            ✅                        │
│   price_status, price_score, etc.       ✅                        │
│   telegram_chat_id = str(chat_id)       ✅                        │
│   telegram_user_id = str(user.id)       ✅                        │
│   telegram_username                     ✅                        │
│   reviewer_role = lookup из recipients  ✅                        │
│                                                                    │
│   config_name                             ❌ НЕТ                  │
│   stable_car_key                          ❌ НЕТ                  │
│   config_name                             ❌ НЕТ                  │
│                                                                    │
│ save_feedback(feedback_card, action, comment)                     │
│ → INSERT INTO feedback (32 колонны)                               │
│ → feedback.id = autoincrement                                     │
│                                                                    │
│ save_reaction_detail(feedback_id, reason_code)                    │
│ → INSERT INTO reaction_details (feedback_id, reason_code)         │
└──────────────────────────────────────────────────────────────────┘
```

### Где теряются поля

| Поле | Есть в sent_ads | Есть в audited JSON | Есть в card_data | Есть в callback_data | Есть в feedback_card | Есть в feedback БД |
|------|-----------------|---------------------|-----------------|---------------------|---------------------|-------------------|
| card_id | ✅ | ✅ | ✅ | ✅ (в callback) | ✅ | ✅ |
| model_id | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| config_name | ✅ (но NULL) | ✅ | ❌ | ❌ | ❌ | ❌ (нет колонны) |
| stable_car_key | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| telegram_chat_id | ✅ (как chat_id) | ❌ | ❌ | ❌ (но известен) | ✅ | ✅ |
| telegram_user_id | ❌ | ❌ | ❌ | ❌ (но известен) | ✅ | ✅ |
| reviewer_role | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |

---

## 4. Feedback table

### Схема (32 колонны)

```sql
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,     -- autoincrement
    card_id TEXT,                              -- ID карточки (haraba_id)
    url TEXT,                                  -- Desktop URL
    model_id TEXT,                             -- ID модели из конфига
    title TEXT,                                -- Название авто
    price INTEGER,                             -- Цена
    mileage INTEGER,                           -- Пробег
    engine TEXT,                               -- Двигатель
    transmission TEXT,                         -- Коробка
    drive TEXT,                                -- Привод
    region TEXT,                               -- Регион
    owners TEXT,                               -- Владельцы
    score INTEGER,                             -- Скор
    telegram_status TEXT,                      -- excellent/good/watch/weak
    action TEXT,                               -- review/think/skip
    comment TEXT,                              -- Комментарий менеджера
    created_at TEXT,                           -- Дата создания

    legal_restrictions TEXT,                   -- Юр. статус
    autoteka_status TEXT,                      -- Автотека
    price_status TEXT,                         -- Статус цены
    price_score INTEGER,                       -- Скор цены
    mileage_score INTEGER,                     -- Скор пробега
    engine_score INTEGER,                      -- Скор двигателя
    transmission_score INTEGER,                -- Скор коробки
    equipment_score INTEGER,                   -- Скор комплектации
    photo_url TEXT,                            -- URL главного фото
    photo_count INTEGER,                       -- Количество фото
    full_location TEXT,                        -- Полная локация

    telegram_chat_id TEXT,                     -- Chat ID менеджера
    telegram_user_id TEXT,                     -- User ID менеджера
    telegram_username TEXT,                    -- Username менеджера
    reviewer_role TEXT                         -- owner/manager/viewer
);
```

### Анализ полей

| Поле | Обязательное | Заполняется | Может быть NULL | Примечание |
|------|-------------|-------------|-----------------|------------|
| `id` | ✅ PK | ✅ auto | ❌ | Autoincrement |
| `card_id` | ❌ | ✅ | ✅ | Всегда заполняется |
| `url` | ❌ | ✅ | ✅ | |
| `model_id` | ❌ | ✅ | ✅ | |
| `title` | ❌ | ✅ | ✅ | |
| `price` | ❌ | ✅ | ✅ (default 0) | |
| `mileage` | ❌ | ✅ | ✅ (default 0) | |
| `engine` | ❌ | ✅ | ✅ (default "unknown") | |
| `transmission` | ❌ | ✅ | ✅ (default "unknown") | |
| `drive` | ❌ | ✅ | ✅ (default "unknown") | |
| `region` | ❌ | ✅ | ✅ (default "unknown") | |
| `owners` | ❌ | ✅ | ✅ (default "unknown") | |
| `score` | ❌ | ✅ | ✅ (default 0) | |
| `telegram_status` | ❌ | ✅ | ✅ | |
| `action` | ❌ | ✅ | ✅ | review/think/skip |
| `comment` | ❌ | ✅ | ✅ | Может быть "-" |
| `created_at` | ❌ | ✅ | ✅ | |
| `legal_restrictions` | ❌ | ✅ | ✅ | |
| `autoteka_status` | ❌ | ✅ | ✅ | |
| `price_status` | ❌ | ✅ | ✅ | |
| `price_score` | ❌ | ✅ | ✅ (default 0) | |
| `mileage_score` | ❌ | ✅ | ✅ (default 0) | |
| `engine_score` | ❌ | ✅ | ✅ (default 0) | |
| `transmission_score` | ❌ | ✅ | ✅ (default 0) | |
| `equipment_score` | ❌ | ✅ | ✅ (default 0) | |
| `photo_url` | ❌ | ✅ | ✅ | |
| `photo_count` | ❌ | ✅ | ✅ (default 0) | |
| `full_location` | ❌ | ✅ | ✅ | |
| `telegram_chat_id` | ❌ | ✅ | ✅ | **Manager identity** |
| `telegram_user_id` | ❌ | ✅ | ✅ | **Manager identity** |
| `telegram_username` | ❌ | ✅ | ✅ | |
| `reviewer_role` | ❌ | ✅ | ✅ | owner/manager/viewer |
| **`config_name`** | ❌ | ❌ | ❌ | **НЕТ КОЛОННЫ** |
| **`stable_car_key`** | ❌ | ❌ | ❌ | **НЕТ КОЛОННЫ** |

### Связь с sent_ads

| Тип связи | Поле | Статус |
|-----------|------|--------|
| feedback → sent_ads | `card_id` = `card_id` | ✅ Текстовое совпадение, не FK |
| feedback → sent_ads | `telegram_chat_id` = `chat_id` | ✅ Можно JOIN |
| feedback → sent_ads | `model_id` = `model_id` | ✅ Можно JOIN |
| feedback → sent_ads | `stable_car_key` | ❌ Нет в feedback |
| feedback → sent_ads | `config_name` | ❌ Нет в feedback |

**Возможный JOIN:**
```sql
SELECT f.*, s.config_name, s.stable_car_key
FROM feedback f
LEFT JOIN sent_ads s ON f.card_id = s.card_id AND f.telegram_chat_id = s.chat_id
```

**Но:** config_name = NULL во всех записях sent_ads, так что JOIN не поможет.

---

## 5. Reaction reasons

### Существующие причины (27 штук)

**reaction_reasons таблица:**

| ID | Тип | Код | Название |
|----|-----|-----|----------|
| 18 | review | good_price | Хорошая цена |
| 19 | review | good_condition | Хорошее состояние |
| 20 | review | low_mileage | Небольшой пробег |
| 21 | review | few_owners | Мало владельцев |
| 22 | review | good_history | Хорошая история |
| 23 | review | good_equipment | Хорошая комплектация |
| 24 | review | liquid_model | Ликвидная модель |
| 25 | review | good_region | Хороший регион |
| 26 | review | review_other | Другое |
| 27 | think | high_price | Высокая цена |
| 28 | think | high_mileage | Большой пробег |
| 29 | think | many_owners | Много владельцев |
| 30 | think | bad_color | Не нравится цвет |
| 31 | think | poor_equipment | Слабая комплектация |
| 32 | think | history_questions | Есть вопросы по истории |
| 33 | think | bad_modification | Неудачная модификация |
| 34 | think | bad_region | Неудобный регион |
| 35 | think | need_more_info | Нужно изучить подробнее |
| 36 | think | think_other | Другое |
| 37 | skip | not_my_model | Не моя модель |
| 38 | skip | not_my_segment | Не мой сегмент |
| 39 | skip | too_expensive | Слишком дорого |
| 40 | skip | too_mileage | Слишком большой пробег |
| 41 | skip | bad_condition | Плохое состояние |
| 42 | skip | legal_risk | Юридические риски |
| 43 | skip | illiquid | Неликвид |
| 44 | skip | skip_other | Другое |

### Где объявлены

| Место | Файл | Что |
|-------|------|-----|
| Клавиатуры (UI) | `ris_reason_keyboard.py` | MAIN_REASONS, EXTRA_REASONS, REASON_WEIGHTS |
| Справочник в БД | `reaction_reasons` таблица | 27 записей, reason_code UNIQUE |
| Нужен комментарий | `ris_reason_store.py` | REASONS_NEED_COMMENT = {review_other, think_other, skip_other, need_more_info} |
| Промпты | `ris_reason_keyboard.py` | REACTION_PROMPTS |

### Как выбираются пользователем

1. Нажимает реакцию (review/think/skip)
2. Появляется inline-клавиатура с 4 основными причинами + "Написать комментарий"
3. Выбирает причину → сохраняется в `reaction_details`
4. Или нажимает "Написать комментарий" → бот просит текст → reason_code = "other"

### Как сохраняются

```
feedback INSERT → feedback.id = N
reaction_details INSERT → feedback_id=N, reason_code="good_price"
```

### Свободный текст

✅ **Да.** Кнопка "💬 Написать комментарий" → `text_handler()` → `save_feedback(card, action, comment)`.

### Разные причины для approve/reject

✅ **Да.** 3 типа реакций → разные наборы причин:
- review: 9 причин (позитивные)
- think: 10 причин (сомнения)
- skip: 8 причин (негативные)

### Можно ли добавить причины без изменения БД

**Да, но с ограничениями:**

| Действие | Нужно менять БД? | Нужно менять код? |
|----------|-----------------|-------------------|
| Добавить причину в UI | ❌ Нет | ✅ Да (`ris_reason_keyboard.py`) |
| Добавить причину в БД | ✅ Да (INSERT в reaction_reasons) | ❌ Нет |
| Полностью новая причина | ✅ Да + ✅ Да | Оба |

### Что было сломано ранее

**Ошибка:** `ImportError: cannot import name 'needs_comment' from 'ris_reason_store'`

**Причина:** Функции `needs_comment()` и `REASONS_NEED_COMMENT` были добавлены локально, но **НЕ закоммичены** в git. На VPS была старая версия файла.

**Исправление:** Коммит `dda439e` — `Add needs_comment helper for reaction reasons`. Push + VPS deploy + restart bot.

**Проверка после изменений:**
1. `python -c "from ris_reason_store import needs_comment; print(needs_comment('good_price'))"` → False
2. Нажать реакцию в Telegram → выбрать причину → проверить `reaction_details` в БД
3. `SELECT COUNT(*) FROM reaction_details WHERE reason_code IS NOT NULL` → > 0

---

## 6. Manager identity

### Можно ли понять какой менеджер нажал реакцию?

| Способ | Работает? | Поле | Доказательство |
|--------|-----------|------|----------------|
| По chat_id | ✅ Да | `feedback.telegram_chat_id` | Заполняется в `_save_feedback_for_chat()` |
| По user_id | ✅ Да | `feedback.telegram_user_id` | Заполняется |
| По username | ✅ Да | `feedback.telegram_username` | Заполняется |
| По роли | ✅ Да | `feedback.reviewer_role` | Заполняется через `get_all_recipients()` lookup |
| JOIN с telegram_users | ✅ Да | `telegram_users.telegram_id = feedback.telegram_user_id` | Можно получить status, role, created_at |

### Можно ли построить аналитику по менеджеру?

✅ **Да.** Примеры запросов:

```sql
-- Реакции по менеджеру
SELECT u.username, f.action, COUNT(*)
FROM feedback f
JOIN telegram_users u ON u.telegram_id = CAST(f.telegram_user_id AS INTEGER)
GROUP BY u.username, f.action;

-- Топ причины по менеджеру
SELECT u.username, rd.reason_code, COUNT(*)
FROM feedback f
JOIN telegram_users u ON u.telegram_id = CAST(f.telegram_user_id AS INTEGER)
JOIN reaction_details rd ON rd.feedback_id = f.id
GROUP BY u.username, rd.reason_code;
```

---

## 7. config_name gap

### Передаётся ли config_name в Telegram message?

**❌ НЕТ.** Текст карточки формируется `prepare_card_text()` → `format_car_card_v2()`. config_name НЕ включается в текст карточки.

### Есть ли config_name в callback_data?

**❌ НЕТ.** Формат callback_data: `"review:{card_id}"` — только action и card_id. Максимум 64 байта (Telegram Bot API limit).

### Есть ли config_name в sent_ads?

**✅ Колонка есть, но все значения = NULL.** (10 записей, все NULL).

### Можно ли восстановить config_name из sent_ads?

**Теоретически да,** через JOIN по `card_id`:
```sql
SELECT s.config_name FROM sent_ads s
WHERE s.card_id = '171156820' AND s.chat_id = '8992376203'
```

**Но:** config_name = NULL, так что результат будет NULL.

### Где именно config_name теряется (3 точки)

| # | Место | Файл:строка | Проблема |
|---|-------|-------------|----------|
| 1 | **card_data_loader.py** | line 35-58 | `load_card_data()` НЕ загружает `config_name` из audited JSON. audited JSON содержит config_name, но dict cards его не включает. |
| 2 | **_save_feedback_for_chat()** | `telegram_feedback_bot.py:302-330` | `feedback_card` dict НЕ содержит `config_name`. Даже если бы card_data имел config_name — он не включается. |
| 3 | **feedback таблица** | Схема БД | Колонка `config_name` **НЕ СУЩЕСТВУЕТ** в feedback. 32 колонны, config_name отсутствует. |

### Какие файлы нужно изменить для Fix 7

| # | Файл | Изменение | Тип |
|---|------|-----------|-----|
| 1 | **feedback.db** | `ALTER TABLE feedback ADD COLUMN config_name TEXT` | Миграция БД |
| 2 | **card_data_loader.py** | Добавить `"config_name": c.get("config_name", "")` в dict | Код |
| 3 | **telegram_feedback_bot.py** | `_save_feedback_for_chat()` → добавить `config_name` в feedback_card dict | Код |
| 4 | **feedback_store.py** | `save_feedback()` → добавить `config_name` в INSERT (32 → 33 параметра) | Код |
| 5 | **telegram_sender.py** | Убедиться что card передаёт config_name (уже делает, но проверит) | Проверка |

### Нужна ли миграция ALTER TABLE?

**✅ Да.** Без колонны `config_name` в feedback таблице — данные невозможно сохранить.

### Есть ли риск сломать старые feedback записи?

**❌ Нет.** `ALTER TABLE ... ADD COLUMN` — безопасная операция. Новые колонны будут NULL для существующих записей. SQLite не требует NOT NULL для ADD COLUMN (если нет DEFAULT).

**Рекомендация:**
```sql
ALTER TABLE feedback ADD COLUMN config_name TEXT DEFAULT NULL;
```

---

## 8. Что уже работает

| Элемент | Статус | Доказательство |
|---------|--------|----------------|
| Inline кнопки review/think/skip | ✅ Работает | `telegram_sender.py:192-204` |
| Reason клавиатуры (4 main + comment) | ✅ Работает | `ris_reason_keyboard.py` |
| Сохранение feedback в БД | ✅ Работает | `feedback_store.py:save_feedback()` |
| Сохранение reaction_details | ✅ Работает | `ris_reason_store.py:save_reaction_detail()` |
| Manager identity в feedback | ✅ Работает | `telegram_chat_id`, `telegram_user_id`, `reviewer_role` |
| Comment от менеджера | ✅ Работает | `text_handler()` → `save_feedback(card, action, comment)` |
| RIS аналитика | ✅ Работает | `ris_analytics.py: get_learning_report, get_learning_reasons, get_config_report` |
| Admin bot RIS section | ✅ Работает | `admin_bot/handlers/learning.py` |
| 27 причин реакций в БД | ✅ Работает | `reaction_reasons` таблица, 27 rows |

---

## 9. Что не работает

| Элемент | Проблема | Приоритет |
|---------|----------|-----------|
| config_name в feedback | Колонка не существует | **HIGH** |
| config_name в card_data | Не загружается из audited JSON | **HIGH** |
| config_name в sent_ads | Все 10 записей = NULL (не закоммичен) | **HIGH** |
| Config Intelligence | Невозможно без config_name в feedback | MEDIUM |
| config_report аналитика | `get_config_report()` работает, но группировка по model_id, не config_name | LOW |

---

## 10. Что нужно для Config Intelligence

### Минимальные изменения (Fix 7)

1. **Миграция БД:**
   ```sql
   ALTER TABLE feedback ADD COLUMN config_name TEXT DEFAULT NULL;
   ```

2. **card_data_loader.py** — добавить config_name:
   ```python
   cards[cid] = {
       ...
       "config_name": c.get("config_name", ""),
   }
   ```

3. **telegram_feedback_bot.py** — `_save_feedback_for_chat()`:
   ```python
   feedback_card = {
       ...
       "config_name": card.get("config_name", ""),
   }
   ```

4. **feedback_store.py** — `save_feedback()`:
   ```python
   # Добавить config_name в INSERT (33 параметра вместо 32)
   c.execute("""
       INSERT INTO feedback (..., config_name, created_at)
       VALUES (..., ?, ?)
   """, (..., card.get("config_name", ""), now))
   ```

5. **telegram_sender.py** — проверка:
   - Убедиться что `card["config_name"]` передаётся в `mark_sent_with_chat_id()` (уже делает)
   - Убедиться что `card["config_name"]` есть в audited JSON (уже делает `step_audit()`)

### Что можно отложить

| Элемент | Когда делать |
|---------|-------------|
| config_name в callback_data | Не нужно — восстанавливается из card_data |
| stable_car_key в feedback | Не нужно — можно JOIN через card_id |
| Персональные конфиги менеджеров | После 100+ реакций с config_name |
| Config suggestions | После 100+ реакций |
| Config versioning | После первых config suggestions |

---

## 11. Риски

| # | Риск | Уровень | Описание |
|---|------|---------|----------|
| 1 | **Миграция ALTER TABLE** | LOW | Безопасна в SQLite. Новые колонны = NULL для старых записей. |
| 2 | **save_feedback() — 32 → 33 параметра** | MEDIUM | Если INSERT не обновлён — ошибка при записи. Нужен тест. |
| 3 | **card_data_loader не загружает config_name** | MEDIUM | Audited JSON содержит config_name, но loader его пропускает. |
| 4 | **VPS без Fix 7** | HIGH | Если код не закоммичен/не задеплоен — VPS продолжает писать без config_name. |
| 5 | **callback_data 64 byte limit** | LOW | config_name не помещается в callback_data, но восстанавливается из card_data. |
| 6 | **Старые feedback записи без config_name** | LOW | config_name будет NULL — аналитика будет их пропускать. Это ожидаемо. |

---

## 12. Чеклист проверки после изменений

### Перед деплоем

- [ ] `ALTER TABLE feedback ADD COLUMN config_name TEXT` выполнена
- [ ] `PRAGMA table_info(feedback)` показывает config_name
- [ ] `card_data_loader.py` включает config_name
- [ ] `_save_feedback_for_chat()` включает config_name
- [ ] `save_feedback()` принимает config_name (33 параметра)
- [ ] Тест: создать feedback → проверить config_name в БД

### После деплоя

- [ ] Отправить тестовую карточку
- [ ] Нажать реакцию → выбрать причину
- [ ] `SELECT config_name FROM feedback ORDER BY id DESC LIMIT 1` → не NULL
- [ ] `SELECT config_name, COUNT(*) FROM feedback GROUP BY config_name` → config_name распределены
- [ ] `get_config_report()` → данные по конфигам

### На VPS

- [ ] `git status` — нет local modifications на критичных файлах
- [ ] `git log -1` — последний коммит включает Fix 7
- [ ] `systemctl restart haraba-feedback-bot.service`
- [ ] `journalctl -u haraba-feedback-bot --no-pager -n 20` — без ошибок

---

## КРАТКИЙ ОТЧЁТ

| # | Вопрос | Ответ |
|---|--------|-------|
| 1 | Реакции сейчас сохраняются? | ✅ **Да** — feedback таблица, save_feedback(), reaction_details |
| 2 | Можно ли понять менеджера? | ✅ **Да** — telegram_chat_id, telegram_user_id, reviewer_role |
| 3 | Можно ли понять config_name? | ❌ **Нет** — колонки нет в feedback, нет в card_data, нет в callback |
| 4 | Где именно теряется config_name? | **3 точки:** (1) card_data_loader.py не загружает, (2) _save_feedback_for_chat() не включает, (3) feedback таблица не имеет колонну |
| 5 | Какие 3-5 файлов нужно для Fix 7? | 1. feedback.db (ALTER TABLE), 2. card_data_loader.py, 3. telegram_feedback_bot.py, 4. feedback_store.py, 5. telegram_sender.py (проверка) |
| 6 | Нужна ли миграция БД? | ✅ **Да** — `ALTER TABLE feedback ADD COLUMN config_name TEXT` |
| 7 | Какие проверки обязательны после фикса? | Тестовая реакция → SELECT config_name FROM feedback → не NULL; VPS restart; journalctl без ошибок |
