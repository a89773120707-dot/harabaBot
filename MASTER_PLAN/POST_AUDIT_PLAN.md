# HARABA MINI — ПЛАН РЕАЛИЗАЦИИ ПОСЛЕ АУДИТА

> Дата: 2026-06-13
> Источник: результаты 9-этапного аудита
> Статус: УТВЕРЖДЁН

---

## ЦЕЛЬ

Сначала привести проект в единое состояние:

**Локальный код = GitHub = VPS**

Только после этого делать Fix 7.

---

## ФАЗА 0 — FREEZE

До завершения стабилизации **запрещено:**

- ❌ manager_config
- ❌ Auto.ru интеграция
- ❌ новые Telegram функции
- ❌ новые кнопки
- ❌ новые таблицы БД
- ❌ рефакторинг

**Разрешено:**

- ✅ документация
- ✅ коммиты аудита
- ✅ синхронизация VPS
- ✅ Fix 7

---

## ФАЗА 1 — СОХРАНЕНИЕ АУДИТА

**Цель:** Зафиксировать всю документацию в Git.

### Коммит №1

```
docs/
MASTER_PLAN/
ADMIN_BOT_PLAN.md, FLAGSHIP_PLAN.md, AUTO_RU_INTEGRATION_PLAN.md, BLOCK2_CONFIG_NAME_PLAN.md
DAILY_REPORT_2026-06-11.md, DAILY_REPORT_2026-06-12.md, REPORT_2026-06-11.md, NEXT_PLAN.md
.qwen/skills/ (все 26 папок)
```

### Проверки

```bash
git diff --cached
# Убедиться что НЕТ:
#   .env
#   *.db
#   state.json
#   auto_ru_state.json
#   chrome_profile/
#   results/debug/
```

### Commit message

```
docs: add full project audit and knowledge base
```

### Результат

- ✅ Аудит сохранён навсегда
- ✅ Все 12 документов в Git
- ✅ Skills зафиксированы

---

## ФАЗА 2 — СТАБИЛИЗАЦИЯ РАБОЧЕГО КОДА

**Цель:** Разобрать 14 modified файлов.

### Для каждого файла:

1. Посмотреть diff
2. Подтвердить назначение
3. Подтвердить что изменение завершено

### Особое внимание (4 файла):

| Файл | Что изменено | Статус |
|------|-------------|--------|
| `run_daily_pipeline.py` | +8 строк: config_name в step_audit() | ✅ Завершено |
| `telegram_sender.py` | +11 строк: config_name в load_audited_candidates() | ✅ Завершено |
| `feedback_store.py` | +22 строки: миграция config_name + mark_sent | ✅ Завершено |
| `admin_bot/handlers/menu.py` | +6 строк: menu_learning callback | ✅ Завершено |

### Остальные modified файлы:

| Файл | Тип | Решение |
|------|-----|---------|
| `config/awd_liquid_full_config.yaml` | Config | ❌ НЕ коммитить — ford_kuga дубликат |
| `DAILY_REPORT_2026-06-12.md` | Docs | ✅ Коммит в Фазе 1 |
| `results/telegram_sender_report.yaml` | Docs | ✅ Коммит в Фазе 1 |
| 7 × SKILL.md | Docs | ✅ Коммит в Фазе 1 |

### Проверки

```bash
python -m compileall run_daily_pipeline.py telegram_sender.py feedback_store.py admin_bot/handlers/menu.py
```

### Commit message

```
fix: stabilize config_name pipeline and admin menu
```

### Файлы коммита

```
run_daily_pipeline.py
telegram_sender.py
feedback_store.py
admin_bot/handlers/menu.py
```

---

## ФАЗА 3 — СИНХРОНИЗАЦИЯ VPS

**Цель:** Убрать ситуацию: локально ≠ GitHub ≠ VPS

### Текущее состояние

| Место | Commit | Отставание |
|-------|--------|-----------|
| Локально | dda439e + 14 modified | 0 |
| GitHub | dda439e | +14 modified |
| VPS | 36ab6dc | -2 commits |

### Шаги

```bash
# 1. Push в GitHub
git push origin main

# 2. На VPS — записать текущий hash ДО
ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && git rev-parse HEAD > /tmp/hash_before.txt"

# 3. Backup БД
ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && cp results/feedback.db results/feedback_before_sync_$(date +%Y%m%d_%H%M%S).db"

# 4. Git pull
ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && git pull"

# 5. Проверить hash
ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && git rev-parse HEAD"

# 6. Restart сервисов
ssh haraba@109.238.95.141 "systemctl restart haraba-bot && systemctl restart haraba-admin-bot"
```

### Проверки

```bash
# Хеш должен совпадать
git rev-parse HEAD  # локально
ssh ... "git rev-parse HEAD"  # VPS
```

---

## ФАЗА 4 — ПРОВЕРКА MVP ПОСЛЕ DEPLOY

### Проверить сервисы

```bash
# Pipeline cron работает
ssh haraba@109.238.95.141 "crontab -l"
ssh haraba@109.238.95.141 "tail -20 logs/pipeline_cron.log"

# Feedback bot работает
ssh haraba@109.238.95.141 "systemctl status haraba-bot --no-pager"
ssh haraba@109.238.95.141 "journalctl -u haraba-bot -n 50 --no-pager"

# Admin bot работает
ssh haraba@109.238.95.141 "systemctl status haraba-admin-bot --no-pager"
ssh haraba@109.238.95.141 "journalctl -u haraba-admin-bot -n 50 --no-pager"
```

### Проверить get_enabled_recipients()

```bash
ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && .venv/bin/python -c \"
from feedback_store import get_enabled_recipients
r = get_enabled_recipients()
print('Active recipients:', len(r))
for u in r:
    print(f'  {u}')
\""
```

**Ожидание:** 2 active recipient (owner + protocol_skrin). НЕ должно быть paused/pending.

### Проверить pipeline

```bash
# Запустить dry-run
ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && .venv/bin/python run_daily_pipeline.py --dry-run"
```

### Проверить config_name в sent_ads (после следующего запуска pipeline)

```bash
ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && .venv/bin/python -c \"
import sqlite3
c = sqlite3.connect('results/feedback.db').cursor()
c.execute('SELECT config_name, COUNT(*) FROM sent_ads GROUP BY config_name')
for r in c.fetchall():
    print(f'  config_name={r[0]}: {r[1]} rows')
\""
```

**Ожидание:** Новые записи должны иметь config_name != NULL.

---

## ФАЗА 5 — FIX 7

**Цель:** Довести config_name до feedback.

### BLOCK 5A — PRE-CHECK

```bash
# Backup
cp results/feedback.db results/feedback_before_fix7.db

# Проверить схемы
python -c "
import sqlite3
c = sqlite3.connect('results/feedback.db').cursor()

print('=== sent_ads ===')
c.execute('PRAGMA table_info(sent_ads)')
for r in c.fetchall():
    print(f'  {r[1]} ({r[2]})')

print('=== feedback ===')
c.execute('PRAGMA table_info(feedback)')
for r in c.fetchall():
    print(f'  {r[1]} ({r[2]})')

print('=== reaction_details ===')
c.execute('PRAGMA table_info(reaction_details)')
for r in c.fetchall():
    print(f'  {r[1]} ({r[2]})')
"
```

**Подтвердить:**
- ✅ sent_ads.config_name существует
- ❌ feedback.config_name отсутствует
- ❌ reaction_details.config_name отсутствует

### BLOCK 5B — МИГРАЦИИ

**Добавить:**
1. `feedback.config_name TEXT`
2. `reaction_details.config_name TEXT`

**Idempotent режим:** если колонка уже существует — не падать.

```python
def ensure_fix7_columns(conn):
    c = conn.cursor()
    # feedback
    c.execute("PRAGMA table_info(feedback)")
    cols = {r[1] for r in c.fetchall()}
    if "config_name" not in cols:
        c.execute("ALTER TABLE feedback ADD COLUMN config_name TEXT DEFAULT NULL")
        print("Added feedback.config_name")

    # reaction_details
    c.execute("PRAGMA table_info(reaction_details)")
    cols = {r[1] for r in c.fetchall()}
    if "config_name" not in cols:
        c.execute("ALTER TABLE reaction_details ADD COLUMN config_name TEXT DEFAULT NULL")
        print("Added reaction_details.config_name")

    conn.commit()
```

**Проверки:**
```bash
PRAGMA table_info(feedback)
PRAGMA table_info(reaction_details)
```

### BLOCK 5C — КОД

**Изменить:**

| Файл | Изменение |
|------|-----------|
| `telegram_feedback_bot.py` | `_save_feedback_for_chat()` → добавить `config_name` в feedback_card dict |
| `feedback_store.py` | `save_feedback()` → добавить config_name в INSERT |
| `card_data_loader.py` | `load_card_data()` → добавить `config_name` из audited JSON |

**Логика:**
- feedback получает config_name из card_data
- reaction_details получает config_name через feedback_id (JOIN)

**НЕ передавать вручную** — reaction_details получает через JOIN с feedback.

### BLOCK 5D — ТЕСТЫ

Минимум 6 тестов:

| # | Тест | Что проверяет |
|---|------|--------------|
| 1 | migration_idempotent | Миграция не падает при повторном запуске |
| 2 | feedback_has_config_name | Колонна добавлена |
| 3 | save_feedback_with_config_name | config_name записывается |
| 4 | card_data_loader_includes_config_name | config_name загружается из audited JSON |
| 5 | reaction_details_joins_config_name | JOIN возвращает config_name |
| 6 | full_pipeline_config_name | Отправка → реакция → config_name в БД |

```bash
pytest tests/test_fix7.py -v
```

### BLOCK 5E — DEPLOY

```bash
git add feedback_store.py telegram_feedback_bot.py card_data_loader.py
git commit -m "fix: add config_name to feedback and reaction_details (Fix 7)"
git push origin main

# VPS backup
ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && cp results/feedback.db results/feedback_before_fix7.db"

# VPS deploy
ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && git pull && systemctl restart haraba-bot && systemctl restart haraba-admin-bot"
```

### BLOCK 5F — LIVE TEST

```bash
# 1. Карточка пришла
ssh ... "tail -20 logs/pipeline_cron.log"

# 2. sent_ads.config_name != NULL
ssh ... "python -c \"import sqlite3; c=sqlite3.connect('results/feedback.db').cursor(); c.execute('SELECT config_name FROM sent_ads WHERE config_name IS NOT NULL LIMIT 5'); [print(r[0]) for r in c.fetchall()]\""

# 3. Нажать реакцию в Telegram

# 4. feedback.config_name != NULL
ssh ... "python -c \"import sqlite3; c=sqlite3.connect('results/feedback.db').cursor(); c.execute('SELECT config_name FROM feedback WHERE config_name IS NOT NULL ORDER BY id DESC LIMIT 5'); [print(r[0]) for r in c.fetchall()]\""

# 5. reaction_details.config_name != NULL (через JOIN)
ssh ... "python -c \"import sqlite3; c=sqlite3.connect('results/feedback.db').cursor(); c.execute('SELECT rd.reason_code, f.config_name FROM reaction_details rd JOIN feedback f ON f.id=rd.feedback_id ORDER BY rd.id DESC LIMIT 5'); [print(r) for r in c.fetchall()]\""
```

---

## ФАЗА 6 — СБОР ДАННЫХ

**После успешного Fix 7.**

Ничего нового не делать.

**Накопить:**
- 100+ реакций (минимум)
- 200–300 реакций (желательно)

**Цель:** Получить статистику по config_name.

---

## ФАЗА 7 — CONFIG INTELLIGENCE

**После накопления статистики.**

Строим:

```
config_name → реакции → конверсия → рейтинг поисков
```

**Получаем понимание:**
- какие поиски работают
- какие поиски мусор
- что отключать
- что усиливать

---

## ФАЗА 8 — MANAGER CONFIGS

**Только после появления аналитики.**

Добавить:
- `telegram_users.config_name` или
- `manager_configs` таблица

**Архитектура:**

```
Общий пул карточек
  ↓
Персональная фильтрация
  ↓
Manager-aware dedup
  ↓
Feedback
  ↓
Analytics
```

---

## ЧТО НЕ ТРОГАТЬ

| Элемент | Почему |
|---------|--------|
| stable_car_key логика | Dedup сломается |
| PK (stable_car_key, chat_id) | Dedup сломается |
| telegram_users таблица | Потеря менеджеров |
| state.json | Pipeline не запустится |
| .env | Боты не запустятся |
| cron schedule | Риск параллельных запусков |
| dedup logic | Дубли в Telegram |

---

## ТЕКУЩИЙ БЛИЖАЙШИЙ ШАГ

Сейчас начинать **НЕ Fix 7**.

Сейчас делать: **ФАЗА 1 → ФАЗА 2 → ФАЗА 3**

То есть:
1. Коммит аудита
2. Коммит рабочих фиксов
3. Синхронизация VPS
4. Проверка сервисов

И только потом переход к миграциям Fix 7.

---

## ПРИОРИТЕТЫ

| Приоритет | Задача | Блокирует |
|-----------|--------|-----------|
| P0-1 | Зафиксировать документацию | Знание проекта |
| P0-2 | Синхронизировать Git ↔ VPS | Все фиксы |
| P0-3 | Проверить get_enabled_recipients на VPS | Рассылка менеджерам |
| P1 | Fix 7 (config_name → feedback) | Config Intelligence |
| P2 | Manager Configs | Персонализация |
| P3 | Auto.ru | Новый источник |
