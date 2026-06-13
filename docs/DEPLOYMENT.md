# Deployment / VPS Audit

> Дата: 2026-06-13
> Режим: только чтение, без изменений

---

## 1. Краткий вывод

| Параметр | Значение |
|----------|----------|
| Python версия | 3.13.6 |
| Репозиторий | `https://github.com/a89773120707-dot/harabaBot.git` |
| Ветка | `main` |
| VPS сервер | `haraba@109.238.95.141` |
| VPS путь | `/home/haraba/harabaBot_code` |
| Pipeline cron | `*/10` с `flock` |
| Feedback bot | systemd (`haraba-feedback-bot.service`) |
| Admin bot | systemd (`haraba-admin-bot.service`) |
| Локальный статус | ⚠ **14 modified файлов, 100+ untracked** |
| VPS синхронизация | ⚠ **ТРЕБУЕТ ПРОВЕРКИ** — нет прямого доступа |

---

## 2. Локальный запуск

### Как запустить проект локально?

```bash
# 1. Установить зависимости
pip install -r requirements.txt
playwright install chromium

# 2. Настроить .env (скопировать из существующего)
# .env уже существует с токенами

# 3. Проверить сессию
python check_session.py
```

### Как запустить pipeline вручную?

```bash
# Dry-run (без отправки)
python run_daily_pipeline.py --dry-run

# Реальная отправка
python run_daily_pipeline.py --send

# С лимитом
python run_daily_pipeline.py --send --limit 3

# Пропустить сбор (использовать существующие карточки)
python run_daily_pipeline.py --send --skip-collect
```

### Как запустить feedback bot?

```bash
python telegram_feedback_bot.py
```

**Требует:** `.env` с `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID`

### Как запустить admin bot?

```bash
python -m admin_bot.admin_bot
```

**Требует:** `.env` с `ADMIN_BOT_TOKEN`, `OWNER_ID`, `ADMIN_IDS`

### Какие зависимости нужны?

**requirements.txt:**
```
playwright>=1.35.0
python-telegram-bot>=20.0
pyyaml>=6.0
requests>=2.31.0
```

**Фактические версии (локально):**
- playwright==1.60.0
- python-telegram-bot==22.7
- pyTelegramBotAPI==4.28.0
- PyYAML==6.0.3
- Python==3.13.6

### Где лежит .env?

**Путь:** `C:\Users\Admin\haraba-mini\.env`

**Содержит:** TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ADMIN_BOT_TOKEN, OWNER_ID, ADMIN_IDS, DB_PATH, LOG_PATH, BACKUP_PATH, EXPORT_PATH

### Где лежат логи?

| Лог | Путь |
|-----|------|
| Pipeline | `results/daily_pipeline.log` |
| Session | `logs/session.log` |
| Bot (VPS) | `logs/bot.log` |
| Bot error (VPS) | `logs/bot_error.log` |
| Cron (VPS) | `logs/pipeline_cron.log` |

### Где лежит БД?

**Путь:** `results/feedback.db` (108 KB)

---

## 3. Production/VPS состояние

### Данные о VPS (из памяти и документации)

| Параметр | Значение | Источник |
|----------|----------|----------|
| Сервер | `haraba@109.238.95.141` | Memory: github_repo |
| Путь | `/home/haraba/harabaBot_code` | Memory: github_repo |
| Git remote | `https://github.com/a89773120707-dot/harabaBot.git` | git remote -v (локально) |
| Последний deploy commit | `36ab6dc` | Memory: daily_report_2026-06-09 |
| Deploy дата | 2026-06-12 | Memory |
| venv | `/home/haraba/harabaBot_code/.venv/` | ADMIN_BOT_PLAN.md |

### Файлы для VPS deployment

| Файл | Назначение | Статус |
|------|-----------|--------|
| `haraba_bot.service` | Systemd unit для feedback bot | ✅ Есть (но требует обновления — User=root, путь /opt/haraba-mini) |
| `run_pipeline.sh` | Cron wrapper script | ✅ Есть (но требует обновления — путь /opt/haraba-mini) |
| `requirements.txt` | Python зависимости | ✅ Есть |
| `deploy_check.py` | Pre-deploy checklist | ✅ Есть |

### ⚠ Рассинхрон документации и фактов

| Документ | Указанный путь | Фактический путь |
|----------|---------------|-----------------|
| `haraba_bot.service` | `/opt/haraba-mini` | `/home/haraba/harabaBot_code` |
| `run_pipeline.sh` | `/opt/haraba-mini` | `/home/haraba/harabaBot_code` |
| `CRON_SETUP.md` | `*/15` | `*/10` (из memory) |
| `haraba_bot.service` User | `root` | `haraba` (из memory) |

**Вывод:** Файлы `haraba_bot.service` и `run_pipeline.sh` — **старые версии**, не отражают текущую VPS конфигурацию.

---

## 4. Cron pipeline

### Есть ли cron?

**✅ Да** (из memory, daily_report).

### Какая команда запускает pipeline?

**Из memory:**
```cron
*/10 * * * * flock -n /tmp/haraba_pipeline.lock cd /home/haraba/harabaBot_code && .venv/bin/python run_daily_pipeline.py --send
```

**Из CRON_SETUP.md (устарело):**
```cron
*/15 * * * * cd /opt/haraba-mini && ./run_pipeline.sh
```

### Есть ли flock?

**✅ Да** — `flock -n /tmp/haraba_pipeline.lock` (из memory).

### Как часто запускается?

**Каждые 10 минут** (`*/10`). CRON_SETUP.md говорит `*/15` — **устарело**.

### Куда пишутся логи?

**Из memory:** `logs/pipeline_cron.log`

### Есть ли риск параллельного запуска?

**❌ Нет** — `flock` предотвращает параллельные запуски.

### Есть ли риск, что cron запускает старый путь?

**⚠ ТРЕБУЕТ ПРОВЕРКИ** — нужно проверить `crontab -l` на VPS.

---

## 5. Systemd services

### Какие сервисы есть?

| Сервис | Статус | Файл |
|--------|--------|------|
| `haraba-feedback-bot.service` | ✅ Активен (из memory) | Локальный файл `haraba_bot.service` (устарел) |
| `haraba-admin-bot.service` | ✅ Активен (из memory) | Локального файла нет |

### Фактические параметры (из memory)

**haraba-bot (feedback bot):**
- WorkingDirectory: `/home/haraba/harabaBot_code`
- ExecStart: `.venv/bin/python telegram_feedback_bot.py`
- Restart: always
- User: `haraba`

**haraba-admin-bot:**
- WorkingDirectory: `/home/haraba/harabaBot_code`
- ExecStart: `.venv/bin/python -m admin_bot.admin_bot`
- Restart: always
- User: `haraba`

### Локальный haraba_bot.service (устарел)

```ini
[Unit]
Description=Haraba Mini Telegram Feedback Bot
After=network.target

[Service]
Type=simple
User=root                          # ⚠ На VPS: haraba
WorkingDirectory=/opt/haraba-mini  # ⚠ На VPS: /home/haraba/harabaBot_code
ExecStart=/opt/haraba-mini/venv/bin/python telegram_feedback_bot.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/haraba-mini/logs/bot.log
StandardError=append:/opt/haraba-mini/logs/bot_error.log

[Install]
WantedBy=multi-user.target
```

### Auto-restart включён?

**✅ Да** — `Restart=always` в обоих сервисах.

### Есть ли 409 Conflict polling?

**Из daily report:** Был Conflict (2 процесса feedback_bot), исправлен через `systemctl restart`. Сейчас один PID.

---

## 6. Логи

### Где смотреть логи

| Лог | Путь (VPS) | Путь (локально) |
|-----|-----------|----------------|
| Pipeline | `logs/pipeline_cron.log` | `results/daily_pipeline.log` |
| Feedback bot | `journalctl -u haraba-bot` | `logs/bot.log` (если запущен локально) |
| Admin bot | `journalctl -u haraba-admin-bot` | N/A |
| Session | N/A | `logs/session.log` |

### Команды для чтения логов (VPS)

```bash
# Pipeline логи
tail -100 /home/haraba/harabaBot_code/logs/pipeline_cron.log

# Feedback bot логи
journalctl -u haraba-bot -n 100 --no-pager

# Admin bot логи
journalctl -u haraba-admin-bot -n 100 --no-pager

# Последние ошибки
journalctl -u haraba-bot --priority=err --no-pager
```

---

## 7. Local / GitHub / VPS diff

### Локальный git статус

```
Branch: main (up to date with origin/main)
Modified: 14 файлов
Untracked: 100+ файлов
```

### Локальный код синхронизирован с GitHub?

**✅ Да** — `git status` показывает "up to date with 'origin/main'".

**Но:** 14 modified файлов **не закоммичены** — на GitHub их нет.

### VPS код синхронизирован с GitHub?

**⚠ ТРЕБУЕТ ПРОВЕРКИ** — последний deploy: commit `36ab6dc` (2026-06-12).

**Последний коммит на GitHub:** `dda439e` (Add needs_comment helper) — **после** deploy.

**Вывод:** VPS **отстаёт** на 1 коммит (`dda439e` — `needs_comment` helper).

### Есть ли modified файлы на VPS?

**⚠ ТРЕБУЕТ ПРОВЕРКИ** — из daily report: `feedback_store.py` modified на VPS (без git).

### Есть ли untracked файлы на VPS?

**⚠ ТРЕБУЕТ ПРОВЕРКИ** — `vps_*.py`, `block_*.py` могут быть на VPS.

### Есть ли risk, что VPS работает на старой версии?

**✅ Да, риск есть:**
- VPS: commit `36ab6dc` (2026-06-12)
- GitHub: commit `dda439e` (2026-06-12, позже)
- Modified файлы не закоммичены — VPS их не получит

### Есть ли bug get_enabled_recipients() на VPS?

**⚠ ТРЕБУЕТ ПРОВЕРКИ** — из daily report: "НЕ исправлено". Файл `feedback_store.py` modified локально, но не закоммичен. Если на VPS старая версия — bug persists.

### Есть ли Block 2 / config_name на VPS?

**⚠ ТРЕБУЕТ ПРОВЕРКИ** — из daily report: "НЕ закоммичен, НЕ задеплоен". VPS не имеет Block 2 код.

---

## 8. Backup

### Есть ли backup БД?

**✅ Да.**

| Файл | Размер | Дата |
|------|--------|------|
| `results/feedback_backup_20260612_143122.db` | 108 KB | 2026-06-11 23:01 |
| `results/feedback_before_users_sync.db` | 108 KB | 2026-06-11 23:01 |
| `data/state_backup.json` | — | — |

### Где лежат backup файлы?

**Путь:** `results/feedback_backup_*.db`

### Есть ли автоматический backup?

**❌ Нет.** Бэкапы созданы вручную перед операциями.

### Как сделать ручной backup?

```bash
# БД
python scripts/backup_db.py

# Или вручную
cp results/feedback.db results/feedback_backup_$(date +%Y%m%d_%H%M%S).db

# Сессия
cp data/state.json data/state_backup.json
```

### Как откатить код?

```bash
# На VPS
cd /home/haraba/harabaBot_code
git log --oneline -10          # Найти нужный коммит
git reset --hard <commit_hash>  # Откатить
systemctl restart haraba-bot
systemctl restart haraba-admin-bot
```

### Как откатить БД?

```bash
# Остановить ботов
systemctl stop haraba-bot
systemctl stop haraba-admin-bot

# Восстановить БД
cp results/feedback_backup_20260612_143122.db results/feedback.db

# Запустить ботов
systemctl start haraba-bot
systemctl start haraba-admin-bot
```

### Что обязательно backup перед Fix 7?

1. **БД:** `cp results/feedback.db results/feedback_before_fix7.db`
2. **Код:** `git status` → записать текущий хеш
3. **VPS:** `ssh haraba@109.238.95.141 "cd /home/haraba/harabaBot_code && cp results/feedback.db results/feedback_before_fix7.db"`
4. **Сессия:** `cp data/state.json data/state_backup_before_fix7.json`

---

## 9. Rollback

### Сценарий rollback

| Шаг | Команда |
|-----|---------|
| 1. Остановить ботов | `systemctl stop haraba-bot && systemctl stop haraba-admin-bot` |
| 2. Восстановить БД | `cp results/feedback_before_fix7.db results/feedback.db` |
| 3. Откатить код | `git reset --hard <pre-fix7-commit>` |
| 4. Запустить ботов | `systemctl start haraba-bot && systemctl start haraba-admin-bot` |
| 5. Проверить | `journalctl -u haraba-bot -n 20 --no-pager` |

---

## 10. Риски

| # | Риск | Уровень | Описание |
|---|------|---------|----------|
| 1 | **VPS отстаёт от GitHub** | HIGH | `36ab6dc` vs `dda439e` — 1 коммит разница |
| 2 | **14 modified файлов не закоммичены** | HIGH | VPS не получит fix до commit + push + deploy |
| 3 | **haraba_bot.service устарел** | MEDIUM | Пути `/opt/haraba-mini` vs `/home/haraba/harabaBot_code` |
| 4 | **run_pipeline.sh устарел** | MEDIUM | Пути `/opt/haraba-mini` vs `/home/haraba/harabaBot_code` |
| 5 | **CRON_SETUP.md устарел** | MEDIUM | `*/15` vs `*/10` |
| 6 | **Нет автоматического backup** | MEDIUM | Бэкапы только ручные |
| 7 | **Нет rollback script** | MEDIUM | Rollback instructions есть, но нет автоматизации |
| 8 | **VPS modified файлы** | HIGH | Если `feedback_store.py` modified на VPS без git — deploy может перезаписать |
| 9 | **Нет .env.example** | LOW | Невозможно развернуть без существующего .env |
| 10 | **Нет health check** | LOW | Нет endpoint для проверки работоспособности |

---

## 11. Требует проверки

| № | Что | Почему |
|---|-----|--------|
| 1 | **VPS: crontab -l** | Подтвердить `*/10` с `flock` |
| 2 | **VPS: git status** | Проверить modified/untracked файлы |
| 3 | **VPS: git log --oneline -5** | Подтвердить текущий коммит |
| 4 | **VPS: systemctl status haraba-bot** | Проверить статус сервиса |
| 5 | **VPS: systemctl status haraba-admin-bot** | Проверить статус сервиса |
| 6 | **VPS: journalctl -u haraba-bot -n 50** | Проверить ошибки |
| 7 | **VPS: cat /home/haraba/harabaBot_code/.env** | Подтвердить OWNER_ID, ADMIN_IDS |
| 8 | **VPS: ls -la /home/haraba/harabaBot_code/results/*.db** | Подтвердить бэкапы |
| 9 | **VPS: get_enabled_recipients()** | Проверить содержит ли `WHERE status='active'` |
| 10 | **VPS: config_name в sent_ads** | Проверить заполнен ли config_name |

---

## КРАТКИЙ ОТЧЁТ

| # | Вопрос | Ответ |
|---|--------|-------|
| 1 | Как сейчас запускается pipeline? | **cron `*/10`** с `flock -n /tmp/haraba_pipeline.lock` → `run_daily_pipeline.py --send` |
| 2 | Как запускается feedback bot? | **systemd** `haraba-bot.service` → `telegram_feedback_bot.py` |
| 3 | Как запускается admin bot? | **systemd** `haraba-admin-bot.service` → `python -m admin_bot.admin_bot` |
| 4 | Синхронизирован ли VPS с GitHub? | ⚠ **Нет** — VPS: `36ab6dc`, GitHub: `dda439e` (1 коммит разница) |
| 5 | Есть ли modified/untracked на VPS? | ⚠ **ТРЕБУЕТ ПРОВЕРКИ** — из daily report: `feedback_store.py` modified |
| 6 | Есть ли get_enabled_recipients() bug на VPS? | ⚠ **ТРЕБУЕТ ПРОВЕРКИ** — daily report: "НЕ исправлено" |
| 7 | Где смотреть логи? | `journalctl -u haraba-bot -n 100`, `logs/pipeline_cron.log`, `results/daily_pipeline.log` |
| 8 | Что обязательно сделать перед Fix 7? | 1. Backup БД, 2. Записать git hash, 3. Backup VPS БД, 4. Backup сессии |
