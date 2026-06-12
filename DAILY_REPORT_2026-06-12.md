# Daily Report: 2026-06-12

## Тема: telegram_users — единый источник правды + фикс /recipients + cron */10

---

## ✅ ЧТО СДЕЛАНО

### 1. telegram_users — единый источник правды

**Проблема:** Два источника правды — `telegram_recipients` (старая таблица) и `telegram_users` (новая). Админ-бот и основной бот показывали разных пользователей.

**Решение:**
- `feedback_store.py` — переписаны 4 функции:
  - `get_enabled_recipients()` → `SELECT FROM telegram_users WHERE status='active'`
  - `get_all_recipients()` → `SELECT FROM telegram_users` (все статусы)
  - `register_recipient()` → upsert в `telegram_users`, статус НЕ меняется
  - `disable_recipient()` → `UPDATE telegram_users SET status='disabled'`
- `telegram_recipients` — оставлена как legacy, не удалять

**Коммит:** `a238e27` — Fix: telegram_users as single source of truth

### 2. Авто-регистрация через /start основного бота

- `/start` → новый пользователь → `telegram_users` status=`pending`
- Уведомление owner о новом пользователе
- `/register_manager` → `status='pending'`
- `/register_owner` → только для owner_id (8992376203)
- Повторный /start НЕ меняет статус (paused/disabled остаются)

### 3. Фикс команды /recipients

**Проблема:** `/recipients` вызывал `get_all_recipients()` — показывал ВСЕХ, включая paused/pending.

**Решение:** Заменено на `get_enabled_recipients()` — только active.

**Коммит:** `36ab6dc` — Fix /recipients command to show only active users

### 4. Cron изменён на каждые 10 минут

- **Было:** `0 */1 * * *` (каждый час)
- **Стало:** `*/10 * * * *` (каждые 10 минут)
- **Добавлен:** `flock -n /tmp/haraba_pipeline.lock` — защита от параллельных запусков

### 5. VPS обновлён

- `git reset --hard origin/main` → HEAD = `36ab6dc`
- Боты перезапущены
- Бэкап БД: `results/feedback_before_git_pull.db`

### 6. Созданные скрипты

| Файл | Назначение |
|------|-----------|
| `scripts/backup_db.py` | Бэкап БД с timestamp |
| `scripts/sync_recipients_to_users.py` | Синхронизация recipients → users (добавляет недостающих, не меняет существующие статусы) |
| `scripts/verify_users_sync.py` | Проверка consistency между таблицами |

---

## 📊 Статусы пользователей

| ID | Username | Роль | Статус | Рассылка? |
|---|---|---|---|---|
| 8992376203 | — | owner | active | ✅ |
| 1649929050 | @protocol_skrin | manager | active | ✅ |
| 896670515 | @ismailovvv97 | manager | paused | ❌ |
| 1445251473 | — | manager | pending | ❌ |
| 5649770485 | — | manager | pending | ❌ |
| 6946123280 | @Cryptonit_shisha | manager | active | ✅ |

---

## 🔍 Диагностика: Sent: 12 но карточки не пришли

**Вопрос:** "Sent: X" — это реальный Telegram send_message или только запись в БД?

**Ответ:** Реальный send_message (HTTP 200 OK).
- `send_car_card_sync()` → если ошибка → `failed += 1`, `sent` НЕ увеличивается
- `mark_sent_with_chat_id()` вызывается ТОЛЬКО после успешной отправки

**Почему owner не получил в 14:50:**
- Получил в 14:04 от старого hourly cron (4 карточки)
- В 14:50 dedup сработал — те же карточки уже отправлены

**Новый пользователь:**
- `6946123280` (@Cryptonit_shisha, G.I.O) зарегистрировался через /start → получил 27 карточек

**Дубликаты в БД:** Нет. 290 записей, все уникальные пары (stable_car_key + chat_id).

---

## 🚫 ЗАМОРОЖЕНО (не делать)

- Config Intelligence (Fix 7: config_name) — до 100 реакций
- learning_score
- reaction_learning_scorer.py
- Автоматическое изменение score
- Автоматическое изменение конфигов
- Auto.ru MVP — CAPTCHA проблема

---

## 📍 Где остановились

- Сервер работает, pipeline каждые 10 минут с flock
- Статусы пользователей управляются через админку
- VPS БД имеет 6 пользователей
- Админка работает — статусы меняются через неё

---

## 📌 Следующие шаги

1. **Накопить 50-100 реакций** — отправлять карточки, собирать feedback
2. **После 100 реакций → Fix 7: config_name** — привязать реакцию к config_name
3. **Config Intelligence** — config_suggestions, /config_report, /approve_config_change

---

## 📦 Коммиты сегодня

```
36ab6dc Fix /recipients command to show only active users via get_enabled_recipients()
a238e27 Fix: telegram_users as single source of truth — sync recipients, auto-register /start with pending, owner notification
```
