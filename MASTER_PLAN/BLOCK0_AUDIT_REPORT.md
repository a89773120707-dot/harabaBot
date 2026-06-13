# BLOCK 0 — AUDIT REPORT

Дата: 2026-06-13

---

## БЛОК A. Telegram Users

### A1. telegram_users — единственный источник правды?

**Доказано:**
- `get_enabled_recipients()` читает ТОЛЬКО из `telegram_users` WHERE status = 'active'
- `get_all_recipients()` читает ТОЛЬКО из `telegram_users`
- `telegram_sender.py` использует `get_enabled_recipients()` (строка 482)
- `telegram_recipients` — legacy таблица, существует в БД, но НЕ используется для чтения/записи в основном потоке

**Статус: ✅ PASS**

### A2. get_enabled_recipients() возвращает только active

**Доказано:**
```sql
SELECT telegram_id, username, first_name, role FROM telegram_users WHERE status = 'active'
```
Результат (локальная БД):
- 8992376203 — Haraba — owner — active
- 1649929050 — protocol_skrin — manager — active

**Статус: ✅ PASS**

### A3. telegram_users данные

```
(8992376203, None, 'Haraba', 'owner', 'active')
(1649929050, 'protocol_skrin', '🫥', 'manager', 'active')
(896670515, 'ismailovvv97', None, 'manager', 'paused')
(5649770485, '', '', 'manager', 'pending')
(1445251473, '', '', 'manager', 'pending')
```

**Статус: ✅ PASS** — paused/pending не попадают в get_enabled_recipients()

### A4. telegram_recipients НЕ используется для рассылки

**Доказано:**
- Единственные SELECT/INSERT/UPDATE для telegram_recipients — в `init_db()` (создание таблицы) и в скриптах верификации (`scripts/verify_users_sync.py`, `scripts/sync_recipients_to_users.py`)
- В `telegram_sender.py` — нет упоминаний telegram_recipients
- В `run_daily_pipeline.py` — нет упоминаний telegram_recipients
- В `register_recipient()` — INSERT только в telegram_users

**Статус: ✅ PASS**

---

## БЛОК B. Telegram Feedback

### B1. feedback сохраняется

**Доказано:**
- `save_feedback()` в `feedback_store.py` (строка 400) — INSERT в feedback
- `telegram_feedback_bot.py` (строка 352, 658) — вызывает save_feedback
- Таблица feedback имеет 30+ колонок включая telegram_chat_id, reviewer_role

**Статус: ✅ PASS**

### B2. reaction_details сохраняется

**Доказано:**
- `save_reaction_detail()` вызывается в `telegram_feedback_bot.py` (строка 433, 665)
- Таблица reaction_details: `(id, feedback_id, reason_code, created_at)`
- **НО:** локальная БД имеет 0 записей в reaction_details

**ТРЕБУЕТ ПРОВЕРКИ на VPS:** Daily report от 2026-06-12 говорит что на VPS reaction_details заполнен (31 запись). Локальная БД — копия с VPS но могла быть сделана до фикса.

**Статус: ⏳ PASS (код) / ТРЕБУЕТ ПРОВЕРКИ (данные на VPS)**

### B3. needs_comment работает

**Доказано:**
- `telegram_feedback_bot.py` (строка 417) — импортирует `needs_comment` из `ris_reason_store`
- Импорт не падает (commit `dda439e` добавил `needs_comment()` в `ris_reason_store.py`)

**Статус: ✅ PASS (локально)** / ТРЕБУЕТ ПРОВЕРКИ (на VPS — нужен deploy этого коммита)

### B4. Нет 409 Conflict

**Не доказано** — это runtime-проблема, которую нельзя проверить чтением кода.

**Статус: ⏳ ТРЕБУЕТ ПРОВЕРКИ на VPS (systemctl status)**

---

## БЛОК C. Pipeline

### C1. cron каждые 10 минут

**Не доказано локально** — это VPS-специфичная настройка.

Из памяти: cron `*/10 * * * *` с `flock -n /tmp/haraba_pipeline.lock` — настроен на VPS.

**Статус: ⏳ ТРЕБУЕТ ПРОВЕРКИ на VPS**

### C2. Pipeline логика

**Доказано:**
- `run_daily_pipeline.py` содержит полный цикл: verify_searches → collect → enrich → audit → dedup → send → report
- `telegram_sender.py` загружает получателей из БД, проходит по кандидатам, отправляет

**Статус: ✅ PASS (код)**

---

## БЛОК D. Dedup

### D1. sent_ads заполняется

**Доказано:**
- Локальная БД: 10 записей в sent_ads
- `mark_sent_with_chat_id()` в `feedback_store.py` (строка 676) — INSERT/UPDATE
- Composite key: `(stable_car_key, chat_id)`

**Статус: ✅ PASS**

### D2. Дубликаты режутся

**Доказано:**
- `check_dedup_with_chat_id()` в `feedback_store.py` — проверяет stable_car_key + chat_id
- `telegram_sender.py` (строка ~515) — проверяет dedup_status перед отправкой

**Статус: ✅ PASS (код)**

---

## БЛОК E. Config Name Audit

### E1. config_name в sent_ads

**FAIL ❌**

**Доказано:**
- Колонка `config_name` существует в `sent_ads` ✅
- Но ВСЕ 10 записей имеют `config_name = NULL` ❌
- `mark_sent_with_chat_id()` извлекает config_name из `card.get("config_name", "unknown")` (строка 688)
- Код ВЕРНЫЙ — но данные NULL

**Причина:** Код добавлен в `run_daily_pipeline.py` (строка 220) и `telegram_sender.py` (строка 142-150), но НЕ закоммичен и НЕ задеплоен на VPS.

### E2. config_name в feedback

**FAIL ❌**

**Доказано:**
- Колонка `config_name` НЕ существует в таблице `feedback`
- `save_feedback()` НЕ сохраняет config_name

### E3. config_name в reaction_details

**FAIL ❌**

**Доказано:**
- Колонка `config_name` НЕ существует в таблице `reaction_details`
- `save_reaction_detail()` принимает только `(feedback_id, reason_code)`

---

## ИТОГОВЫЙ ОТЧЁТ BLOCK 0

| Блок | Статус | Детали |
|------|--------|--------|
| A. Telegram Users | ✅ PASS | telegram_users — единственный источник; paused/pending исключены |
| B. Telegram Feedback | ⚠️ PASS (код) / NEEDS VPS CHECK | Код верный, данные на VPS нужно проверить |
| C. Pipeline | ⚠️ PASS (код) / NEEDS VPS CHECK | Код верный, cron/flock на VPS нужно проверить |
| D. Dedup | ✅ PASS | sent_ads заполняется, composite key работает |
| E. Config Name Audit | ❌ FAIL | config_name=NULL в sent_ads; колонки нет в feedback и reaction_details |

### ОБЩИЙ РЕЗУЛЬТАТ: ❌ FAIL

**Причина:** Блок E не пройден. Config_name не попадает ни в одну таблицу реакций.

### ЧТО НЕ ТРОГАЛИ:
- Код НЕ изменён
- БД НЕ изменена
- Git НЕ тронут
- VPS НЕ тронут

### СЛЕДУЮЩИЙ ШАГ:
Перейти к BLOCK 1 — FIX 7 CONFIG_NAME (как указано в Master Plan).
