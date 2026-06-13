# HARABA MINI — Admin Bot Plan

**Дата:** 2026-06-11  
**Цель:** Создать отдельного Telegram-бота администратора для управления системой Haraba Mini

---

## Архитектура

Основной бот (`telegram_feedback_bot.py`) — рассылка карточек менеджерам.  
Админ-бот (`admin_bot/`) — управление системой, НЕ парсит Haraba, только читает/обновляет БД и показывает статистику.

**Запрещено смешивать:**
```
telegram_sender.py        — рассылка карточек менеджерам
admin_bot/                — управление системой
feedback_store.py         — работа с SQLite
run_daily_pipeline.py     — запуск Haraba pipeline
```

---

## Блок 0. Правило архитектуры

Админ-бот не должен парсить Haraba. Он только читает/обновляет БД и показывает статистику.

---

## Блок 1. Структура файлов

Создать папку `admin_bot/`:

```
admin_bot/
│
├── admin_bot.py              # точка входа
├── config.py                 # загрузка токена, admin ids, пути к БД
├── permissions.py            # проверка доступа
├── keyboards.py              # кнопки Telegram
├── formatting.py             # красивые сообщения
│
├── services/
│   ├── db_service.py          # общая работа с SQLite
│   ├── stats_service.py       # статистика
│   ├── reactions_service.py   # реакции
│   ├── users_service.py       # менеджеры
│   ├── cards_service.py       # карточки
│   ├── searches_service.py    # поиски
│   └── logs_service.py        # логи
│
└── handlers/
    ├── start.py
    ├── menu.py
    ├── stats.py
    ├── reactions.py
    ├── users.py
    ├── cards.py
    ├── searches.py
    ├── db.py
    └── logs.py
```

**Проверка:** `tree admin_bot`

---

## Блок 2. Конфиг

Добавить в `.env`:

```env
ADMIN_BOT_TOKEN=telegram_admin_bot_token
OWNER_ID=8992376203
ADMIN_IDS=8992376203
DB_PATH=results/feedback.db
LOG_PATH=logs/
BACKUP_PATH=backups/
EXPORT_PATH=exports/
```

**Логика доступа:**
```python
def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def is_admin(user_id: int) -> bool:
    return is_owner(user_id) or user_id in ADMIN_IDS
```

**Автосоздание owner в БД** — при старте проверить `telegram_users`, создать если нет:
```
telegram_id: 8992376203
role: owner
status: active
```

**Защита owner:** запретить `/pause`, `/disable`, `/delete` для owner.

**Проверка:**
```bash
python -m admin_bot.config
sqlite3 results/feedback.db "SELECT telegram_id, role, status FROM telegram_users WHERE telegram_id = 8992376203;"
```

---

## Блок 3. Безопасность доступа

Все админ-команды проверяют `is_admin(user_id)`.  
Если не админ: `⛔ Нет доступа.`

---

## Блок 4. Главное меню

`/start` или `/menu` → inline-кнопки:
```
Админ-панель Haraba Mini

📊 Статистика
👍 Реакции
👥 Менеджеры
🚗 Карточки
🔍 Поиски
🗄 База
🧾 Логи
⚙️ Настройки
```

---

## Блок 5. Таблица пользователей Telegram

```sql
CREATE TABLE IF NOT EXISTS telegram_users (
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

**Статусы:** `pending`, `active`, `paused`, `disabled`  
**Роли:** `owner`, `admin`, `manager`

---

## Блок 6. Команды управления менеджерами

```
/users          — список всех менеджеров
/approve ID     — pending → active
/pause ID       — active → paused
/resume ID      — paused → active
/disable ID     — any → disabled
```

Каждый юзер показывает: имя, @username, ID, роль, статус, реакции за 7 дней.

---

## Блок 7. Интеграция с основным ботом рассылки

Заменить `MANAGER_CHAT_IDS = [...]` на:

```sql
SELECT telegram_id FROM telegram_users WHERE status = 'active';
```

Pipeline отправляет ТОЛЬКО active менеджерам.

**Проверка:** один active, один paused → запустить pipeline → карточку получает только active.

---

## Блок 8. Реакции

Таблица (если нет):
```sql
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    telegram_id INTEGER NOT NULL,
    reaction TEXT NOT NULL,
    comment TEXT,
    created_at TEXT
);
```

Команды:
```
/reactions_today
/reactions_week
/reactions_by_manager
/reactions_by_model
```

---

## Блок 9. Карточки

Команды:
```
/cards_today     — карточки за сегодня
/card ID         — конкретная карточка
/top_cards       — топ по реакциям
/bad_cards       — худшие по реакциям
/no_reaction     — без реакций
```

---

## Блок 10. Статистика

Команды:
```
/stats_today
/stats_week
/stats_month
/top_models
/top_regions
/top_managers
```

Показывает: найдено, отправлено, дубликаты, лайки, дизлайки, конверсия.

---

## Блок 11. Поиски

Таблица (если нет):
```sql
CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    config_name TEXT,
    source TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT,
    updated_at TEXT
);
```

Команды:
```
/searches
/search ID
/pause_search ID
/resume_search ID
/disable_search ID
```

---

## Блок 12. База данных

Команды:
```
/db_status    — размер, таблицы, строки
/db_backup    — бэкап + отправка файла в Telegram
/db_count     — общие счётчики
```

---

## Блок 13. Логи

Таблица:
```sql
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    finished_at TEXT,
    status TEXT,
    found_count INTEGER,
    sent_count INTEGER,
    duplicate_count INTEGER,
    error_text TEXT
);
```

Команды:
```
/last_run       — последний запуск
/last_errors    — последние ошибки
/pipeline_status — текущий статус
```

---

## Блок 14. Экспорт CSV

```
/export_reactions   → exports/reactions_YYYY-MM-DD.csv
/export_cards       → exports/cards_YYYY-MM-DD.csv
/export_users       → exports/users_YYYY-MM-DD.csv
```

---

## Блок 15. Сервисный запуск на VPS

Создать `haraba-admin-bot.service`:
```ini
[Unit]
Description=Haraba Mini Admin Telegram Bot
After=network.target

[Service]
User=haraba
WorkingDirectory=/home/haraba/harabaBot_code
EnvironmentFile=/home/haraba/harabaBot_code/.env
ExecStart=/home/haraba/harabaBot_code/.venv/bin/python -m admin_bot.admin_bot
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## Блок 16. Проверка полного сценария

1. Новый менеджер → `/start` → pending → `/approve ID` → active → получает карточки
2. Менеджер в отпуске → `/pause ID` → paused → не получает карточки
3. Менеджер вернулся → `/resume ID` → active → снова получает
4. Реакция нажата → сохранена в БД → `/reactions_today` видит
5. `/stats_today` → найдено, отправлено, лайки, дизлайки, конверсия

---

## Блок 17. MVP (первым делаем)

1. `/start`
2. `/menu`
3. `/users`
4. `/approve ID`
5. `/pause ID`
6. `/resume ID`
7. `/disable ID`
8. `/stats_today`
9. `/reactions_today`
10. `/db_status`

Потом добавляем: `/cards_today`, `/card ID`, `/searches`, `/logs`, `/export_csv`, `/db_backup`

---

## Блок 18. Финальная проверка

1. `python -m admin_bot.admin_bot`
2. Telegram: `/start`, `/menu`, `/users`, `/stats_today`, `/reactions_today`, `/db_status`
3. `sudo systemctl start haraba-admin-bot`
4. `sudo systemctl status haraba-admin-bot`
5. `python run_daily_pipeline.py` → active получает, paused/disabled нет

---

## Иерархия ролей

```
owner (8992376203)
 ├─ может всё
 ├─ назначать admin
 ├─ удалять admin
 ├─ подключать/отключать менеджеров
 └─ управлять поисками

admin
 ├─ смотреть статистику
 ├─ смотреть реакции
 ├─ pause/resume менеджерам
 └─ НЕ может менять owner

manager
 └─ получает карточки
```
