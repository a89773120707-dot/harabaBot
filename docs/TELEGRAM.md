# Telegram / Admin Bot Audit

> Дата: 2026-06-13
> Режим: только чтение, без изменений

---

## 1. Краткий вывод

| Параметр | Значение |
|----------|----------|
| Telegram сервисов | **3** (pipeline sender, feedback bot, admin bot) |
| Файл отправки карточек | `telegram_sender.py` |
| Файл приёма реакций | `telegram_feedback_bot.py` |
| Файл админки | `admin_bot/admin_bot.py` |
| Защита доступа | ✅ is_admin() + can_modify_user() |
| Retry/обработка ошибок | ✅ HTTPXRequest timeouts + fallback |
| Самая опасная операция | Изменение stable_car_key логики или PK sent_ads |

---

## 2. Telegram модули

### 2.1. telegram_sender.py

| Параметр | Значение |
|----------|----------|
| **Путь** | `C:\Users\Admin\haraba-mini\telegram_sender.py` |
| **Назначение** | Отправка карточек в Telegram |
| **Запуск** | Subprocess из `run_daily_pipeline.py` (`--send` или `--dry-run`) |
| **Production** | ✅ VPS (вызывается cron pipeline) |
| **Библиотека** | `python-telegram-bot==22.7` |
| **БД таблицы** | `sent_ads` (write), `telegram_users` (read via get_enabled_recipients) |
| **Команды** | CLI only (`--send`, `--dry-run`, `--limit N`) — нет Telegram handlers |

### 2.2. telegram_feedback_bot.py

| Параметр | Значение |
|----------|----------|
| **Путь** | `C:\Users\Admin\haraba-mini\telegram_feedback_bot.py` (712 строк) |
| **Назначение** | Обработка реакций менеджеров |
| **Запуск** | `python telegram_feedback_bot.py` → `run_polling()` |
| **Production** | ✅ VPS systemd (`haraba-feedback-bot.service`) |
| **Библиотека** | `python-telegram-bot==22.7` |
| **БД таблицы** | `feedback` (write), `telegram_users` (read/write), `reaction_details` (write) |
| **Telegram команды** | `/start`, `/help`, `/register_owner`, `/register_manager`, `/recipients`, `/disable_me` |
| **Callback handlers** | `reason_handler` (pattern `^reason:`), `button_handler` (все остальные) |
| **Message handler** | `text_handler` (текст без команд — комментарии) |

### 2.3. admin_bot/admin_bot.py

| Параметр | Значение |
|----------|----------|
| **Путь** | `C:\Users\Admin\haraba-mini\admin_bot\admin_bot.py` (64 строки) |
| **Назначение** | Админ-панель: менеджеры, статистика, реакции, RIS |
| **Запуск** | `python -m admin_bot.admin_bot` → `run_polling()` |
| **Production** | ✅ VPS systemd (`haraba-admin-bot.service`) |
| **Библиотека** | `python-telegram-bot==22.7` |
| **БД таблицы** | `telegram_users` (read/write), `sent_ads` (read), `feedback` (read), `pipeline_runs` (read) |
| **Telegram команды** | `/start`, `/menu` |
| **Callback handlers** | `menu_callback_handler` (`menu_*`, `back_to_menu`), `user_callback_handler` (`user_*`), `learning_callback_handler` (`learning_*`, `config_*`) |

### 2.4. Вспомогательные Telegram модули

| Файл | Назначение |
|------|------------|
| `telegram_card_formatter.py` (745 строк) | Форматирование карточки V2 для Telegram |
| `admin_bot/handlers/start.py` | `/start` handler + unknown command handler |
| `admin_bot/handlers/menu.py` | Главное меню + действия с пользователями |
| `admin_bot/handlers/learning.py` | RIS раздел (learning report, reasons, config report) |
| `admin_bot/keyboards.py` | Inline клавиатуры (main menu, users, user detail, back) |
| `admin_bot/formatting.py` | Форматирование сообщений для админки |
| `admin_bot/permissions.py` | Проверка доступа (is_owner, is_admin, can_modify_user) |
| `admin_bot/config.py` | Загрузка env vars (ADMIN_BOT_TOKEN, OWNER_ID, ADMIN_IDS, DB_PATH) |
| `admin_bot/services/db_service.py` | SQLite connection, миграции, owner bootstrap |
| `admin_bot/services/users_service.py` | CRUD telegram_users |
| `admin_bot/services/stats_service.py` | Статистика отправок и реакций |
| `admin_bot/services/reactions_service.py` | Счётчики реакций |
| `admin_bot/services/cards_service.py` | Карточки за сегодня + детали |
| `admin_bot/services/searches_service.py` | Список моделей из sent_ads |
| `admin_bot/services/logs_service.py` | Pipeline логи из pipeline_runs |
| `ris_reason_keyboard.py` | Inline клавиатуры причин реакций |
| `ris_reason_store.py` | Сохранение reaction_details |
| `ris_analytics.py` | Аналитика: learning_report, learning_reasons, config_report |
| `card_data_loader.py` | Загрузка карточек для feedback bot |

---

## 3. Основная отправка карточек

### 3.1. Где форматируется карточка?

**Файл:** `telegram_card_formatter.py`
**Функция:** `format_car_card_v2(card, config, is_hold, hold_reasons)`

Формат включает: модель/год, цену, рынок, регион/пробег, двигатель/коробку/привод, владельцев, юр. статус, "Почему в выборке", скоринг breakdown, ссылку.

### 3.2. Где создаются inline-кнопки?

**Файл:** `telegram_sender.py`
**Функция:** `build_inline_keyboard(card_id, photo_count, has_description)`

```python
row1 = ["👀 Посмотреть" → "review:{card_id}", "🤔 Подумать" → "think:{card_id}"]
row2 = ["⏭ Скип" → "skip:{card_id}"]
if has_description: row2.append("📖 Описание" → "desc:{card_id}")
if photo_count > 1: row2.append("📷 Ещё фото" → "photos:{card_id}")
```

### 3.3. Где берётся список получателей?

**Файл:** `telegram_sender.py:run_send()`
**Функция:** `get_enabled_recipients()` (из `feedback_store.py`)

```python
recipients = get_enabled_recipients()
# → SELECT telegram_id as chat_id, username, first_name, role
#   FROM telegram_users WHERE status = 'active' ORDER BY role
```

### 3.4. Где проверяется dedup?

**Файл:** `feedback_store.py`
**Функция:** `check_dedup_with_chat_id(card, chat_id)`

```python
SELECT stable_car_key, price, send_count FROM sent_ads
WHERE stable_car_key = ? AND chat_id = ?
# Returns: "new", "same_price", "price_drop", "price_increased"
```

### 3.5. Где вызывается send_message?

**Файл:** `telegram_sender.py`
**Функция:** `send_car_card_async()`

```python
await bot.send_photo(chat_id=chat_id, photo=photo_bytes, caption=caption, reply_markup=keyboard)
# или
await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
```

### 3.6. Где логируется успешная отправка?

**Файл:** `telegram_sender.py:send_car_card_async()`
```python
log.info(f"  [OK] {card_id}: {card.get('title', '')} ({card.get('year', '')})")
```

**Итоговый лог:** `run_send()` — `SEND SUMMARY: Sent: N, Skipped: N, Failed: N`

### 3.7. Где логируются ошибки?

**Файл:** `telegram_sender.py:send_car_card_async()`
```python
log.error(f"  [SEND ERROR] card={card_id} chat={chat_id} error={type(e).__name__}: {e}")
log.error(f"  [FALLBACK ERROR] card={card_id} chat={chat_id} error={type(e2).__name__}: {e2}")
```

### 3.8. Что происходит при ошибке Telegram?

**Цепочка fallback'ов:**
1. **Primary:** `send_photo()` с caption (max 1024 chars)
2. **Если фото не скачалось:** `send_message()` (max 4000 chars)
3. **Если текст > 4000:** обрезка до 3990 + "..."
4. **Если фото caption > 1024:** обрезка + отдельное сообщение с полным текстом
5. **Если всё failed:** `failed += 1`, карточка НЕ записывается в sent_ads

### 3.9. Есть ли обработка 403/429?

**403 (Forbidden):** ❌ **Нет явной обработки.** Ошибка логируется, карточка пропускается.

**429 (Too Many Requests):** ❌ **Нет явной обработки.** Но `HTTPXRequest` настроен с таймаутами (connect=30s, read=90s), что может помочь при rate limiting.

**Риск:** При 429 от Telegram — карточка будет пропущена, dedup может не сработать (зависит от того, дошёл ли запрос до БД).

### 3.10. Есть ли retry?

**Нет автоматического retry.** Если отправка failed — карточка пропускается. При следующем запуске pipeline (через 10 минут) карточка будет обработана снова (если не была записана в sent_ads).

---

## 4. Feedback bot

### 4.1. Как запускается?

```bash
python telegram_feedback_bot.py
```

На VPS: systemd service `haraba-feedback-bot.service`
```ini
ExecStart=/home/haraba/harabaBot_code/.venv/bin/python telegram_feedback_bot.py
```

### 4.2. Какие callback handlers есть?

| Handler | Pattern | Файл:строка | Назначение |
|---------|---------|-------------|------------|
| `reason_handler` | `^reason:` | line 340-430 | Выбор причины реакции |
| `button_handler` | все остальные | line 432-590 | Нажатие реакции (review/think/skip/desc/photos) |

### 4.3. Как устроен pending_feedback?

```python
pending_feedback = {}  # chat_id -> dict

pending_feedback[chat_id] = {
    "card_id": "171156820",
    "action": "review",           # review/think/skip
    "card_message_id": 12345,     # ID сообщения с карточкой
    "card_data": {                # Данные карточки из card_data_loader
        "card_id", "title", "url", "model_id", "price", "mileage",
        "year", "score", "decision", "engine", "transmission", "drive",
        "region", "owners", "legal_restrictions", "autoteka_status",
        "price_status", "price_score", "mileage_score", "engine_score",
        "transmission_score", "equipment_score", "photo_url", "photo_count",
        "full_location"
        # ← НЕТ config_name
        # ← НЕТ stable_car_key
    },
}
```

**Lifecycle:**
1. Создается в `button_handler()` при нажатии реакции
2. Используется в `reason_handler()` для показа клавиатуры причин
3. Используется в `_save_feedback_for_chat()` для сохранения feedback
4. Удаляется после сохранения (`pending_feedback.pop(chat_id)`)

### 4.4. Как выбирается reason?

1. Пользователь нажимает реакцию → `button_handler()` → показывает `reason_keyboard(action)`
2. Пользователь нажимает причину → `reason_handler()` → парсит `callback_data = "reason:good_price"`
3. `reason_code = "good_price"` → сохраняется в `pending_reason[chat_id]`
4. Если `needs_comment(reason_code)` → просит комментарий
5. Иначе → сразу сохраняет feedback + reaction_detail

### 4.5. Как сохраняется feedback?

**Файл:** `feedback_store.py:save_feedback()`

```python
INSERT INTO feedback (
    card_id, url, model_id, title, price, mileage,
    engine, transmission, drive, region, owners,
    legal_restrictions, autoteka_status,
    score, telegram_status, action, comment,
    price_status, price_score, mileage_score, engine_score,
    transmission_score, equipment_score,
    photo_url, photo_count, full_location,
    telegram_chat_id, telegram_user_id, telegram_username, reviewer_role,
    created_at
) VALUES (32 параметра)
```

### 4.6. Как сохраняется reaction_details?

**Файл:** `ris_reason_store.py:save_reaction_detail()`

```python
last_id = get_last_feedback_id()  # SELECT MAX(id) FROM feedback
INSERT INTO reaction_details (feedback_id, reason_code, created_at) VALUES (?, ?, ?)
```

### 4.7. Как определяется telegram_chat_id?

**Источник:** `update.message.chat_id` или `query.message.chat_id` (Telegram API)

Это ID чата, где пользователь взаимодействует с ботом.

### 4.8. Как определяется telegram_user_id?

**Источник:** `update.effective_user.id` или `user.id` (Telegram API)

Это уникальный ID пользователя в Telegram.

### 4.9. Как определяется reviewer_role?

**Файл:** `telegram_feedback_bot.py:_save_feedback_for_chat()` (line 302-315)

```python
recipients = get_all_recipients()
my_role = "viewer"
for r in recipients:
    if r["chat_id"] == str(chat_id):
        my_role = r["role"]
        break
```

**Возможные значения:** 'owner', 'manager', 'viewer' (fallback)

### 4.10. Где не хватает config_name?

| Место | Проблема |
|-------|----------|
| `card_data_loader.py` | Не загружает config_name из audited JSON |
| `pending_feedback["card_data"]` | Не содержит config_name |
| `_save_feedback_for_chat()` feedback_card dict | Не включает config_name |
| `save_feedback()` INSERT | Нет параметра config_name |
| `feedback` таблица | Нет колонны config_name |

---

## 5. Admin bot

### 5.1. Где точка входа?

**Файл:** `admin_bot/admin_bot.py:main()`

### 5.2. Как запускается?

```bash
python -m admin_bot.admin_bot
```

На VPS: systemd service `haraba-admin-bot.service`

### 5.3. Какие команды есть?

| Команда | Handler | Описание |
|---------|---------|----------|
| `/start` | `start_handler` | Главное меню |
| `/menu` | `start_handler` | Алиас /start |

Все остальные функции — через inline callback кнопки.

### 5.4. Какие действия может делать админ?

| Действие | Callback | Что делает |
|----------|----------|------------|
| 📊 Статистика | `menu_stats` | Статистика отправок и реакций за сегодня |
| 👍 Реакции | `menu_reactions` | Реакции за сегодня |
| 👥 Менеджеры | `menu_users` | Список всех пользователей с действиями |
| 🚗 Карточки | `menu_cards` | Карточки за сегодня |
| 🔍 Поиски | `menu_searches` | Список моделей из sent_ads |
| 🗄 База | `menu_db` | Размер БД, таблицы, строки |
| 🧾 Логи | `menu_logs` | Последний запуск pipeline |
| 🧠 Обучение | `menu_learning` | RIS: learning report, reasons, config report |
| ✅ Approve | `user_approve:ID` | pending → active |
| ⏸ Pause | `user_pause:ID` | active → paused |
| ▶️ Resume | `user_resume:ID` | paused → active |
| ❌ Disable | `user_disable:ID` | any → disabled |

### 5.5. Какие таблицы читает?

| Таблица | Где читается |
|---------|-------------|
| `telegram_users` | `users_service.py` — get_all_users, get_user |
| `sent_ads` | `cards_service.py` — get_cards_today, get_card_detail; `searches_service.py` — get_searches_list |
| `feedback` | `reactions_service.py` — get_reactions_today; `cards_service.py` — reaction_count |
| `pipeline_runs` | `logs_service.py` — get_last_run, get_last_errors, get_pipeline_summary |
| `reaction_reasons` | `learning.py` через `ris_analytics.py` |
| `reaction_details` | `learning.py` через `ris_analytics.py` |

### 5.6. Какие таблицы пишет?

| Таблица | Где пишется |
|---------|-------------|
| `telegram_users` | `db_service.py` — ensure_tables(), ensure_owner_exists(); `users_service.py` — set_user_status() |
| `pipeline_runs` | `db_service.py` — ensure_tables() (создание, не данные) |

### 5.7. Может ли включать/отключать менеджеров?

✅ **Да.** Через `user_callback_handler`:
- `user_approve:ID` → `set_user_status(target_id, "active")`
- `user_pause:ID` → `set_user_status(target_id, "paused")`
- `user_resume:ID` → `set_user_status(target_id, "active")`
- `user_disable:ID` → `set_user_status(target_id, "disabled")`

### 5.8. Может ли смотреть реакции?

✅ **Да.** `menu_reactions` → `get_reactions_today()` → `format_reactions_today()`

### 5.9. Может ли смотреть sent_ads?

✅ **Да.** `menu_cards` → `get_cards_today()` (читает sent_ads)

### 5.10. Может ли менять конфиги?

❌ **Нет.** Admin bot НЕ читает/пишет YAML конфиги. Только читает/пишет БД.

### 5.11. Что уже готово?

| Функция | Статус |
|---------|--------|
| /start, /menu | ✅ |
| Главное меню (8 кнопок) | ✅ |
| Список пользователей | ✅ |
| Approve/Pause/Resume/Disable | ✅ |
| Статистика | ✅ |
| Реакции | ✅ |
| Карточки | ✅ |
| Поиски | ✅ |
| База данных | ✅ |
| Логи | ✅ |
| RIS (обучение) | ✅ |
| Проверка прав (is_admin) | ✅ |
| Защита owner | ✅ |

### 5.12. Что не готово?

| Функция | Статус |
|---------|--------|
| Экспорт CSV | ❌ Не реализовано |
| Backup БД через Telegram | ❌ Не реализовано |
| Управление поисками (pause/resume) | ❌ Только просмотр |
| Config suggestions | ❌ Зависит от config_name в feedback |
| Config approval workflow | ❌ Не реализовано |

---

## 6. Роли и доступы

### 6.1. Какие роли существуют?

| Роль | Где определяется | Описание |
|------|-----------------|----------|
| `owner` | `telegram_users.role` | Полный доступ, нельзя отключить |
| `admin` | `.env ADMIN_IDS` | Доступ к админке, не может менять owner |
| `manager` | `telegram_users.role` | Получает карточки, ставит реакции |
| `viewer` | fallback в feedback bot | Только просмотр (не в БД) |

### 6.2. Где они хранятся?

| Роль | Хранилище |
|------|-----------|
| owner/admin | `.env` (OWNER_ID, ADMIN_IDS) + `telegram_users.role` |
| manager | `telegram_users.role` |
| reviewer_role | `feedback.reviewer_role` (snapshot at reaction time) |

### 6.3. Кто имеет доступ к admin bot?

**Проверка:** `admin_bot/permissions.py:is_admin()`

```python
def is_admin(user_id):
    return is_owner(user_id) or user_id in ADMIN_IDS
```

- **Owner:** `OWNER_ID` из `.env` (default: 8992376203)
- **Admins:** `ADMIN_IDS` из `.env` (comma-separated, owner всегда добавляется)

### 6.4. Кто может нажимать реакции?

**Любой пользователь**, получивший карточку в Telegram. Нет проверки прав — бот обрабатывает callback от любого chat_id.

### 6.5. Есть ли проверка прав?

| Место | Проверка | Файл |
|-------|----------|------|
| Admin bot handlers | `is_admin(user_id)` | `admin_bot/handlers/menu.py` |
| User modification | `can_modify_user(actor_id, target_id)` | `admin_bot/permissions.py` |
| Feedback bot | ❌ **Нет** | Любой может нажимать реакции |
| Telegram sender | ❌ **Нет** | Отправляет всем active recipients |

### 6.6. Есть ли риск, что посторонний пользователь получит доступ?

**Admin bot:** ✅ **Защищён.** Все handlers проверяют `is_admin()`.

**Feedback bot:** ⚠ **Нет защиты.** Любой, кто получил карточку, может нажать реакцию. Но это intentional — менеджеры должны реагировать.

**Риск:** Если chat_id попадёт к постороннему, он сможет:
- Нажимать реакции (искажает аналитику)
- Получить список получателей через `/recipients`
- Отключить себя через `/disable_me`

**Mitigation:** Telegram Bot API требует знать bot token для взаимодействия. Без token — нет доступа.

### 6.7. Что требует проверки на VPS?

| Проверка | Почему |
|----------|--------|
| `OWNER_ID` в .env | Совпадает ли с фактическим owner? |
| `ADMIN_IDS` в .env | Кто в списке? Не устарел ли? |
| telegram_users на VPS | Какие статусы? Кто active? |
| is_admin() работает | Проверить с не-admin user → "⛔ Нет доступа" |

---

## 7. Callback data

### 7.1. Какие callback_data форматы используются?

| Формат | Где | Пример |
|--------|-----|--------|
| `review:{card_id}` | Feedback bot кнопки | `review:171156820` |
| `think:{card_id}` | Feedback bot кнопки | `think:171156820` |
| `skip:{card_id}` | Feedback bot кнопки | `skip:171156820` |
| `desc:{card_id}` | Feedback bot кнопки | `desc:171156820` |
| `photos:{card_id}` | Feedback bot кнопки | `photos:171156820` |
| `reason:{reason_code}` | RIS причины | `reason:good_price` |
| `reasons_main:{action}` | RIS toggle | `reasons_main:review` |
| `reasons_extra:{action}` | RIS toggle | `reasons_extra:think` |
| `reason:comment` | RIS комментарий | `reason:comment` |
| `reason:none` | RIS отмена | `reason:none` |
| `reason_done` | RIS готово | `reason_done` |
| `help_cmd` | Feedback bot help | `help_cmd` |
| `menu_{section}` | Admin bot меню | `menu_stats`, `menu_users` |
| `back_to_menu` | Admin bot назад | `back_to_menu` |
| `user_detail:{telegram_id}` | Admin bot пользователь | `user_detail:1649929050` |
| `user_{action}:{telegram_id}` | Admin bot действие | `user_approve:1649929050` |
| `learning_{section}` | Admin bot RIS | `learning_report`, `config_report` |

### 7.2. Есть ли риск превышения лимита Telegram callback_data?

**Лимит Telegram:** 64 байта на callback_data.

| Формат | Длина | Риск |
|--------|-------|------|
| `review:171156820` | 17 chars | ✅ Нет |
| `reason:good_price` | 18 chars | ✅ Нет |
| `user_detail:1649929050` | 23 chars | ✅ Нет |
| `user_approve:1649929050` | 25 chars | ✅ Нет |

**Риск:** Если card_id станет длиннее (например UUID вместо digits), callback_data может превысить 64 байта. Сейчас card_id = digits (~9-10 chars) — безопасно.

### 7.3. Где хранится card_id?

| Место | Формат |
|-------|--------|
| callback_data | `"review:171156820"` |
| pending_feedback | `pending_feedback[chat_id]["card_id"]` |
| feedback table | `feedback.card_id` |
| sent_ads table | `sent_ads.card_id` |

### 7.4. Где хранится reason?

| Место | Формат |
|-------|--------|
| callback_data | `"reason:good_price"` |
| pending_reason | `pending_reason[chat_id] = "good_price"` |
| reaction_reasons table | `reaction_reasons.reason_code` |
| reaction_details table | `reaction_details.reason_code` |

### 7.5. Есть ли stable_car_key в callback?

❌ **Нет.** Callback содержит только card_id.

### 7.6. Есть ли config_name в callback?

❌ **Нет.** Callback не содержит config_name.

### 7.7. Какие изменения callback_data опасны?

| Изменение | Риск |
|-----------|------|
| Добавить config_name в callback_data | ⚠ Может превысить 64 byte limit |
| Изменить формат `review:{card_id}` | 🔴 Сломает button_handler парсинг |
| Изменить формат `reason:{code}` | 🔴 Сломает reason_handler парсинг |
| Добавить stable_car_key в callback | ⚠ Может превысить 64 byte limit |
| Изменить card_id формат | ⚠ Если станет длиннее — callback_data limit |

---

## 8. Ошибки Telegram и retry

### 8.1. Настройки HTTPXRequest

**Файл:** `telegram_sender.py:send_car_card_sync()`

```python
request = HTTPXRequest(
    connect_timeout=30.0,
    read_timeout=90.0,
    write_timeout=90.0,
    pool_timeout=30.0,
)
```

### 8.2. Обработка ошибок

| Ошибка | Обработка |
|--------|-----------|
| Photo download failed | Fallback к send_message |
| send_photo failed | Fallback к send_message |
| send_message failed (text > 4000) | Обрезка до 3990 + "..." |
| All fallbacks failed | `failed += 1`, no sent_ads record |
| Telegram Conflict (409) | ❌ Нет явной обработки |
| Telegram Forbidden (403) | ❌ Нет явной обработки |
| Telegram Too Many Requests (429) | ❌ Нет явной обработки |
| Network timeout | ✅ HTTPXRequest timeout (90s) |

### 8.3. Retry

**Нет автоматического retry.** Пропущенные карточки будут обработаны при следующем запуске pipeline (через 10 минут).

---

## 9. Что уже работает

| Элемент | Статус | Доказательство |
|---------|--------|----------------|
| Отправка карточек в Telegram | ✅ | `telegram_sender.py:run_send()` |
| Inline кнопки review/think/skip | ✅ | `build_inline_keyboard()` |
| Реакции с причинами | ✅ | 27 причин в БД, inline клавиатуры |
| Feedback сохранение | ✅ | `save_feedback()` → feedback table |
| Reaction details | ✅ | `save_reaction_detail()` → reaction_details |
| Manager identity | ✅ | telegram_chat_id, telegram_user_id, reviewer_role |
| Admin bot меню | ✅ | 8 кнопок, все разделы работают |
| User management | ✅ | Approve/Pause/Resume/Disable |
| Access control | ✅ | is_admin(), can_modify_user() |
| Multi-recipient | ✅ | get_enabled_recipients() → active only |
| Per-manager dedup | ✅ | check_dedup_with_chat_id() |
| RIS analytics | ✅ | get_learning_report, get_learning_reasons, config_report |

---

## 10. Что не работает

| Элемент | Проблема |
|---------|----------|
| config_name в feedback | Нет колонны, нет кода |
| config_name в card_data | Не загружается из audited JSON |
| 403/429 обработка | Нет явной обработки ошибок Telegram API |
| Автоматический retry | Нет — только следующий pipeline run |
| pipeline_runs в БД | 0 строк — pipeline пишет в YAML, не в БД |

---

## 11. Риски

| # | Риск | Уровень | Описание |
|---|------|---------|----------|
| 1 | **Изменение callback_data формата** | HIGH | Сломает все handlers — нужно менять парсинг во всех местах |
| 2 | **callback_data > 64 bytes** | MEDIUM | Если добавить config_name или stable_car_key — превысит лимит |
| 3 | **Нет обработки 403/429** | MEDIUM | При rate limit или ban — карточки теряются без retry |
| 4 | **Нет retry при failed send** | MEDIUM | Карточка пропускается, dedup не срабатывает |
| 5 | **pending_feedback in-memory** | LOW | При restart bot — pending state теряется (но это ожидаемо) |
| 6 | **3 polling bot instance** | MEDIUM | Feedback bot + Admin bot + pipeline sender (subprocess) — все используют один token? Нет, разные токены. Но если token shared → Conflict 409. |
| 7 | **Нет проверки прав в feedback bot** | LOW | Любой получивший карточку может реагировать (intentional) |
| 8 | **OWNER_ID hardcoded** | LOW | `8992376203` в нескольких файлах — если сменится owner, нужно менять везде |

---

## 12. Требует проверки

| № | Что | Почему |
|---|-----|--------|
| 1 | **VPS: OWNER_ID и ADMIN_IDS в .env** | Совпадают ли с фактическими? |
| 2 | **VPS: telegram_users статусы** | Кто active? Кто pending/paused? |
| 3 | **VPS: is_admin() работает** | Проверить с не-admin user |
| 4 | **VPS: Conflict 409 в логах** | Есть ли дубликаты bot instance? |
| 5 | **VPS: HTTPXRequest timeouts** | Достаточно ли 90s read timeout? |
| 6 | **callback_data length** | Текущий max length? Не приближается к 64? |

---

## КРАТКИЙ ОТЧЁТ

| # | Вопрос | Ответ |
|---|--------|-------|
| 1 | Сколько Telegram сервисов/модулей? | **3** (pipeline sender, feedback bot, admin bot) + 15+ вспомогательных |
| 2 | Какой файл отправляет карточки? | `telegram_sender.py` (вызывается pipeline как subprocess) |
| 3 | Какой файл принимает реакции? | `telegram_feedback_bot.py` (systemd service) |
| 4 | Какой файл отвечает за админку? | `admin_bot/admin_bot.py` (systemd service) |
| 5 | Есть ли защита доступа? | ✅ Да — `is_admin()` + `can_modify_user()` в admin bot |
| 6 | Есть ли retry/обработка ошибок? | ✅ HTTPXRequest timeouts + fallback, ❌ нет automatic retry |
| 7 | Какие изменения опасны? | Изменение callback_data формата, stable_car_key логики, PK sent_ads, сигнатуры save_feedback() |
| 8 | 5 самых важных Telegram файлов? | 1. `telegram_sender.py`, 2. `telegram_feedback_bot.py`, 3. `telegram_card_formatter.py`, 4. `feedback_store.py`, 5. `admin_bot/admin_bot.py` |
