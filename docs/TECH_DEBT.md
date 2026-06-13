# Tech Debt / Risks — Haraba Mini

> Дата: 2026-06-13
> Источник: docs/AUDIT_SNAPSHOT.md, PROJECT_INVENTORY.md, DATABASE.md, MANAGERS.md, REACTIONS.md, ARCHITECTURE.md, TELEGRAM.md, CONFIGS.md, DEPLOYMENT.md
> Режим: только документация

---

## 1. Краткий вывод

Haraba Mini — **работающий production проект** с 3 сервисами (pipeline, feedback bot, admin bot), VPS deployment, cron `*/10`, и SQLite БД.

**Критичные проблемы:** 14 modified файлов не закоммичены, VPS отстаёт, config_name не доходит до feedback, нет manager_config.

**Стабильные части:** dedup manager-aware, реакции работают, admin bot работает, cron с flock, сессия Haraba жива.

**Главный блок:** Без config_name в feedback невозможно Config Intelligence — флагманская идея проекта.

---

## 2. Критичные риски (P0 — блокируют развитие)

### TD-01: 14 modified файлов не закоммичены

| Параметр | Значение |
|----------|----------|
| **Проблема** | feedback_store.py, run_daily_pipeline.py, telegram_sender.py и др. — modified, не в git |
| **Где** | `git status` — 14 modified files |
| **Доказательство** | `git status` → modified: feedback_store.py, run_daily_pipeline.py, telegram_sender.py, admin_bot/handlers/menu.py, config/awd_liquid_full_config.yaml, results/telegram_sender_report.yaml, DAILY_REPORT_2026-06-12.md, 7 SKILL.md файлов |
| **Последствия** | VPS не получит фиксы. При потере рабочей машины — изменения утеряны. Невозможно rollback к known-good state. |
| **Приоритет** | 🔴 P0 |
| **Решение** | `git add feedback_store.py run_daily_pipeline.py telegram_sender.py` → commit → push → VPS deploy (`git pull`) |
| **Проверка** | `git status` → working tree clean; `git log -1` → commit message |

### TD-02: config_name не доходит до feedback

| Параметр | Значение |
|----------|----------|
| **Проблема** | config_name появляется в step_audit(), но теряется в 3 точках: card_data_loader → _save_feedback_for_chat → save_feedback → feedback table |
| **Где** | card_data_loader.py:35-58, telegram_feedback_bot.py:302-330, feedback_store.py:save_feedback(), feedback table schema |
| **Доказательство** | card_data_loader.py — dict cards не включает config_name; _save_feedback_for_chat() — feedback_card dict не содержит config_name; PRAGMA table_info(feedback) — 32 колонны, config_name отсутствует |
| **Последствия** | Невозможно Config Intelligence. Невозможно привязать реакцию к конфигу. Невозможно config_report по реальным данным. |
| **Приоритет** | 🔴 P0 |
| **Решение** | Fix 7: (1) ALTER TABLE feedback ADD COLUMN config_name TEXT, (2) card_data_loader.py — добавить config_name, (3) _save_feedback_for_chat() — включить config_name, (4) save_feedback() — добавить параметр |
| **Проверка** | `SELECT config_name FROM feedback ORDER BY id DESC LIMIT 5` → config_name не NULL |

### TD-03: VPS отстаёт от GitHub

| Параметр | Значение |
|----------|----------|
| **Проблема** | VPS: commit `36ab6dc`, GitHub: commit `dda439e` (1 коммит разница) |
| **Где** | VPS `/home/haraba/harabaBot_code` |
| **Доказательство** | git log — последний коммит `dda439e` (needs_comment helper). VPS deploy был на `36ab6dc`. |
| **Последствия** | needs_comment helper на VPS может отсутствовать → reaction reasons не сохраняются. |
| **Приоритет** | 🔴 P0 |
| **Решение** | `ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && git pull && systemctl restart haraba-bot && systemctl restart haraba-admin-bot"` |
| **Проверка** | `ssh ... "git log --oneline -1"` → `dda439e` |

### TD-04: 100+ untracked файлов загрязняют проект

| Параметр | Значение |
|----------|----------|
| **Проблема** | block_*.py (30+), vps_*.py (15+), test_*.py (18+), debug_*.py (12+) |
| **Где** | Корень проекта, `results/debug/`, `results/auto_ru_chrome_profile/` |
| **Доказательство** | `git status` → 100+ untracked files |
| **Последствия** | Усложняет git status, deploy, понимание структуры. При accidental `git add .` — мусор в репозитории. |
| **Приоритет** | 🔴 P0 |
| **Решение** | Классифицировать → удалить временные (block_*, vps_*) → переместить полезные в tests/ или scripts/ → обновить .gitignore |
| **Проверка** | `git status --untracked-files=all | wc -l` → < 20 |

---

## 3. Важные риски (P1 — влияют на стабильность)

### TD-05: feedback table не имеет config_name

| Параметр | Значение |
|----------|----------|
| **Проблема** | Колонна config_name отсутствует в feedback таблице |
| **Где** | `results/feedback.db`, таблица `feedback` |
| **Доказательство** | `PRAGMA table_info(feedback)` — 32 колонны, config_name нет |
| **Последствия** | ALTER TABLE required — миграция перед любым кодом |
| **Приоритет** | 🟠 P1 |
| **Решение** | `ALTER TABLE feedback ADD COLUMN config_name TEXT DEFAULT NULL;` |
| **Проверка** | `PRAGMA table_info(feedback)` → config_name TEXT |

### TD-06: get_enabled_recipients() bug требует проверки на VPS

| Параметр | Значение |
|----------|----------|
| **Проблема** | Из daily report: "НЕ исправлено" — может возвращать всех пользователей |
| **Где** | VPS `/home/haraba/harabaBot_code/feedback_store.py` |
| **Доказательство** | daily_report_2026-06-12: "get_enabled_recipients() bug — НЕ исправлено (отложено)" |
| **Последствия** | Paused/pending менеджеры получают карточки |
| **Приоритет** | 🟠 P1 |
| **Решение** | Проверить на VPS: `grep -A 5 "def get_enabled_recipients" feedback_store.py` → должен быть `WHERE status = 'active'` |
| **Проверка** | `ssh ... "python -c 'from feedback_store import get_enabled_recipients; print(get_enabled_recipients())'"` |

### TD-07: Нет automatic retry для Telegram

| Параметр | Значение |
|----------|----------|
| **Проблема** | При failed send карточка пропускается, нет retry |
| **Где** | telegram_sender.py:send_car_card_async() |
| **Доказательство** | Код: если all fallbacks failed → `failed += 1`, no sent_ads record, no retry |
| **Последствия** | Карточки теряются при transient network errors |
| **Приоритет** | 🟠 P1 |
| **Решение** | Добавить retry loop (max 3 attempts, exponential backoff) |
| **Проверка** | Симулировать network error → карточка retry'ится |

### TD-08: Нет обработки 403/429 от Telegram

| Параметр | Значение |
|----------|----------|
| **Проблема** | Нет явной обработки Forbidden и Too Many Requests |
| **Где** | telegram_sender.py:send_car_card_async() |
| **Доказательство** | except Exception — логирует error, нет специфичной обработки TelegramError |
| **Последствия** | При rate limit или ban — карточки пропускаются без предупреждения |
| **Приоритет** | 🟠 P1 |
| **Решение** | except telegram.error.Forbidden → mark as failed permanently; except telegram.error.RetryAfter → wait and retry |
| **Проверка** | Симулировать 429 → bot waits и retry'ит |

### TD-09: sent_ads config_name = NULL во всех 10 записях

| Параметр | Значение |
|----------|----------|
| **Проблема** | Колонка есть, но все записи имеют config_name = NULL |
| **Где** | `results/feedback.db`, таблица `sent_ads` |
| **Доказательство** | `SELECT config_name, COUNT(*) FROM sent_ads GROUP BY config_name` → `'None': 10` |
| **Последствия** | Невозможно аналитику по config_name из sent_ads |
| **Приоритет** | 🟠 P1 |
| **Решение** | Задеплоить исправленный код → новые записи будут иметь config_name. Старые записи останутся NULL (ожидаемо). |
| **Проверка** | Отправить тестовую карточку → `SELECT config_name FROM sent_ads ORDER BY first_sent_at DESC LIMIT 1` |

### TD-10: telegram_recipients legacy inconsistent

| Параметр | Значение |
|----------|----------|
| **Проблема** | ismailovvv97: enabled=1 в legacy, status=paused в telegram_users |
| **Где** | `results/feedback.db`, таблицы `telegram_recipients` и `telegram_users` |
| **Доказательство** | `SELECT * FROM telegram_recipients WHERE chat_id='896670515'` → enabled=1; `SELECT * FROM telegram_users WHERE telegram_id=896670515` → status='paused' |
| **Последствия** | Путаница при отладке. Legacy таблица не используется, но данные misleading. |
| **Приоритет** | 🟡 P2 |
| **Решение** | Удалить telegram_recipients таблицу или добавить комментарий что deprecated |
| **Проверка** | Код не использует telegram_recipients для рассылки |

### TD-11: dedup_store.db broken (empty, no tables)

| Параметр | Значение |
|----------|----------|
| **Проблема** | Файл 0 bytes, нет таблиц |
| **Где** | `results/dedup_store.db` |
| **Доказательство** | `os.path.getsize('results/dedup_store.db')` → 0 bytes |
| **Последствия** | Занимает место, confusing при audit |
| **Приоритет** | 🟡 P2 |
| **Решение** | Удалить файл (safe — не используется кодом) |
| **Проверка** | grep dedup_store *.py → no imports |

### TD-12: sent_ads.db legacy пустая

| Параметр | Значение |
|----------|----------|
| **Проблема** | 20 KB, 0 строк, не используется кодом |
| **Где** | `results/sent_ads.db` |
| **Доказательство** | `SELECT COUNT(*) FROM sent_ads` → 0 rows; grep sent_ads.db *.py → no imports |
| **Последствия** | Занимает место, confusing |
| **Приоритет** | 🟡 P2 |
| **Решение** | Удалить файл |
| **Проверка** | grep sent_ads.db *.py → no results |

### TD-13: OWNER_ID hardcoded в 3+ файлах

| Параметр | Значение |
|----------|----------|
| **Проблема** | `8992376203` hardcoded в feedback_store.py, telegram_feedback_bot.py, admin_bot/config.py |
| **Где** | feedback_store.py:417, telegram_feedback_bot.py:154/184/203, admin_bot/config.py:10 |
| **Доказательство** | grep "8992376203" *.py → 6+ matches |
| **Последствия** | При смене owner — менять везде. Риск ошибки. |
| **Приоритет** | 🟡 P2 |
| **Решение** | Centralize: один источник (admin_bot.config.OWNER_ID), остальные импортируют |
| **Проверка** | grep "8992376203" *.py → только в admin_bot/config.py |

### TD-14: manager_config отсутствует

| Параметр | Значение |
|----------|----------|
| **Проблема** | Нет персональных конфигов менеджеров. Все получают одинаковые карточки. |
| **Где** | Вся архитектура |
| **Доказательство** | grep manager_config *.py → 0 results. Нет таблицы, нет колонки, нет кода. |
| **Последствия** | Невозможно персонализировать рассылку. Config Intelligence ограничен. |
| **Приоритет** | 🟡 P2 |
| **Решение** | После Fix 7: ALTER TABLE telegram_users ADD COLUMN config_name TEXT → изменить get_enabled_recipients() → изменить pipeline send logic |
| **Проверка** | Отправить карточки → каждый менеджер получает только свои конфиги |

---

## 4. Желательные улучшения (P3 — не блокируют, но улучшат)

### TD-15: Нет .env.example

| Параметр | Значение |
|----------|----------|
| **Проблема** | Невозможно развернуть проект без существующего .env |
| **Доказательство** | `ls .env.example` → NOT FOUND |
| **Решение** | Создать `.env.example` с placeholder values |

### TD-16: Нет автоматического backup БД

| Параметр | Значение |
|----------|----------|
| **Проблема** | Бэкапы только ручные |
| **Доказательство** | scripts/backup_db.py существует, но не scheduled |
| **Решение** | Добавить cron: `0 2 * * * cd /home/haraba/harabaBot_code && .venv/bin/python scripts/backup_db.py` |

### TD-17: Документы deployment/cron устарели

| Параметр | Значение |
|----------|----------|
| **Проблема** | haraba_bot.service: `/opt/haraba-mini` vs `/home/haraba/harabaBot_code`. CRON_SETUP.md: `*/15` vs `*/10` |
| **Доказательство** | read haraba_bot.service → User=root, WorkingDirectory=/opt/haraba-mini; read CRON_SETUP.md → */15 |
| **Решение** | Обновить файлы с фактическими путями |

### TD-18: Нет health check endpoint

| Параметр | Значение |
|----------|----------|
| **Проблема** | Нет способа проверить работоспособность без просмотра логов |
| **Решение** | Добавить /health команду в feedback bot: "✅ Bot alive, feedback_count=N, active_recipients=M" |

### TD-19: pipeline_runs = 0 строк

| Параметр | Значение |
|----------|----------|
| **Проблема** | Pipeline пишет логи в YAML, не в БД |
| **Доказательство** | `SELECT COUNT(*) FROM pipeline_runs` → 0 |
| **Решение** | Добавить INSERT в pipeline_runs при каждом запуске |

### TD-20: Нет config validation at startup

| Параметр | Значение |
|----------|----------|
| **Проблема** | Невалидный YAML → crash pipeline без предупреждения |
| **Доказательство** | validate_config_basic() существует, но не вызывается при старте pipeline |
| **Решение** | Вызывать validate_config_basic() в step_audit() перед обработкой |

### TD-21: Дубликат ford_kuga в full_config

| Параметр | Значение |
|----------|----------|
| **Проблема** | Два ford_kuga entry в awd_liquid_full_config.yaml |
| **Доказательство** | grep "id: ford_kuga" config/awd_liquid_full_config.yaml → 2 matches |
| **Решение** | Удалить дубликат или объединить |

### TD-22: Auto.ru module frozen but still in repo

| Параметр | Значение |
|----------|----------|
| **Проблема** | `app/` — 27 файлов, 100% CAPTCHA, не работает |
| **Доказательство** | Memory: auto_ru_frozen.md — "100% CAPTCHA даже с persistent Chrome profile" |
| **Решение** | Пока оставить — может пригодиться при разморозке. Добавить README в app/ с статусом. |

---

## 5. Что нельзя ломать

### CRITICAL — НЕ ТРОГАТЬ БЕЗ BACKUP

| # | Что | Почему | Где |
|---|-----|--------|-----|
| 1 | **stable_car_key логика** | Dedup зависит от неё. Изменение → все карточки станут "new" | `feedback_store.py:_build_stable_key()` |
| 2 | **PK sent_ads (stable_car_key, chat_id)** | Composite PK обеспечивает per-manager dedup | `feedback_store.py:init_db()` migration |
| 3 | **telegram_users таблица** | Single source of truth для менеджеров | `results/feedback.db` |
| 4 | **data/state.json** | Сессия Haraba — без неё pipeline не запустится | `data/state.json` |
| 5 | **.env файл** | Токены, OWNER_ID, ADMIN_IDS — без них боты не запустятся | `.env` |
| 6 | **callback_data формат** | `review:{card_id}`, `reason:{code}` — парсинг во всех handlers | `telegram_sender.py`, `telegram_feedback_bot.py` |
| 7 | **get_enabled_recipients() сигнатура** | Вызывается из 3+ мест — изменение сломает pipeline и bot | `feedback_store.py:593` |
| 8 | **save_feedback() сигнатура** | 32 параметра — добавление нового требует изменения INSERT | `feedback_store.py:save_feedback()` |
| 9 | **flock в cron** | Без flock — параллельные запуски → corruption | VPS crontab |
| 10 | **feedback → reaction_details FK** | reaction_details.feedback_id → feedback.id — удаление feedback сломает FK | Schema |

---

## 6. Что обязательно backup перед изменениями

| # | Что | Команда |
|---|-----|---------|
| 1 | **БД feedback.db** | `cp results/feedback.db results/feedback_before_<change>.db` |
| 2 | **VPS БД** | `ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && cp results/feedback.db results/feedback_before_<change>.db"` |
| 3 | **Сессия** | `cp data/state.json data/state_backup.json` |
| 4 | **Git hash** | `git rev-parse HEAD > .git/COMMIT_BEFORE_<change>` |
| 5 | **VPS git hash** | `ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && git rev-parse HEAD"` |
| 6 | **.env** | `cp .env .env.backup` |

---

## 7. Рекомендуемый порядок исправлений

### Фаза 1: Стабилизация (сегодня)

| # | Задача | Время | Риск |
|---|--------|-------|------|
| 1 | Закоммитить 14 modified файлов | 5 мин | LOW |
| 2 | Push на GitHub | 2 мин | LOW |
| 3 | VPS deploy (git pull + restart) | 5 мин | LOW |
| 4 | Проверить get_enabled_recipients() на VPS | 2 мин | NONE |
| 5 | Проверить reaction reasons на VPS | 2 мин | NONE |

### Фаза 2: Fix 7 — config_name в feedback (после стабилизации)

| # | Задача | Время | Риск |
|---|--------|-------|------|
| 1 | Backup БД (локально + VPS) | 5 мин | NONE |
| 2 | ALTER TABLE feedback ADD COLUMN config_name TEXT | 1 мин | LOW |
| 3 | Обновить card_data_loader.py | 10 мин | LOW |
| 4 | Обновить _save_feedback_for_chat() | 10 мин | LOW |
| 5 | Обновить save_feedback() | 10 мин | MEDIUM |
| 6 | Тест: отправить карточку → нажать реакцию → проверить config_name | 10 мин | NONE |
| 7 | Commit + push + VPS deploy | 10 мин | LOW |

### Фаза 3: Очистка (после Fix 7)

| # | Задача | Время | Риск |
|---|--------|-------|------|
| 1 | Классифицировать untracked файлы | 15 мин | NONE |
| 2 | Удалить block_*.py, vps_*.py | 5 мин | NONE |
| 3 | Переместить полезные в tests/ или scripts/ | 15 мин | LOW |
| 4 | Удалить dedup_store.db, sent_ads.db | 2 мин | NONE |
| 5 | Обновить haraba_bot.service и CRON_SETUP.md | 10 мин | LOW |
| 6 | Создать .env.example | 5 мин | NONE |

### Фаза 4: Улучшения (после очистки)

| # | Задача | Время | Риск |
|---|--------|-------|------|
| 1 | Добавить automatic retry | 30 мин | MEDIUM |
| 2 | Добавить 403/429 обработку | 20 мин | MEDIUM |
| 3 | Добавить health check команду | 15 мин | LOW |
| 4 | Centralize OWNER_ID | 20 мин | LOW |
| 5 | Добавить pipeline_runs INSERT | 10 мин | LOW |
| 6 | Добавить automatic backup cron | 10 мин | LOW |

### Фаза 5: Manager Config (после 100+ реакций)

| # | Задача | Время | Риск |
|---|--------|-------|------|
| 1 | ALTER TABLE telegram_users ADD COLUMN config_name | 1 мин | LOW |
| 2 | Изменить get_enabled_recipients() | 15 мин | MEDIUM |
| 3 | Изменить pipeline send logic | 30 мин | MEDIUM |
| 4 | Admin bot: assign config к менеджеру | 30 мин | MEDIUM |
| 5 | Тест: разные конфиги → разные карточки | 20 мин | NONE |

---

## КРАТКИЙ ОТЧЁТ

### ТОП-10 задач по приоритету

| # | Задача | Приоритет | Блокирует |
|---|--------|-----------|-----------|
| 1 | Закоммитить 14 modified файлов | 🔴 P0 | Всё |
| 2 | Push + VPS deploy | 🔴 P0 | Fix 7, config_name |
| 3 | Проверить get_enabled_recipients() на VPS | 🔴 P0 | Рассылка менеджерам |
| 4 | ALTER TABLE feedback ADD COLUMN config_name | 🟠 P1 | Config Intelligence |
| 5 | Fix 7: config_name в feedback pipeline | 🟠 P1 | Config Intelligence |
| 6 | Очистить 100+ untracked файлов | 🟠 P1 | Git hygiene |
| 7 | Добавить automatic retry | 🟠 P1 | Потеря карточек |
| 8 | Добавить 403/429 обработку | 🟠 P1 | Rate limit handling |
| 9 | Обновить deployment docs | 🟡 P2 | Misleading documentation |
| 10 | Создать .env.example | 🟡 P2 | Deployment friction |

### ТОП-5 вещей, которые нельзя трогать без backup

| # | Что | Последствия если сломать |
|---|-----|-------------------------|
| 1 | **stable_car_key логика** | Все карточки станут "new" → дубли в Telegram |
| 2 | **PK sent_ads (stable_car_key, chat_id)** | Dedup сломается → дубли или потеря карточек |
| 3 | **telegram_users таблица** | Потеря менеджеров → рассылка остановится |
| 4 | **data/state.json** | Pipeline не запустится → нет карточек |
| 5 | **.env файл** | Боты не запустятся → нет рассылки, нет админки |

### Самый безопасный следующий шаг

**Закоммитить 14 modified файлов → push → VPS deploy.**

Это:
- ✅ Не меняет БД
- ✅ Не меняет архитектуру
- ✅ Не ломает существующий функционал
- ✅ Синхронизирует VPS с GitHub
- ✅ Разблокирует Fix 7
- ✅ Занимает 10 минут

Команды:
```bash
git add feedback_store.py run_daily_pipeline.py telegram_sender.py admin_bot/handlers/menu.py config/awd_liquid_full_config.yaml
git commit -m "Fix: config_name pipeline, get_enabled_recipients, menu handler"
git push origin main
ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && git pull && systemctl restart haraba-bot && systemctl restart haraba-admin-bot"
```
