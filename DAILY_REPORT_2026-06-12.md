# Daily Report: 2026-06-12

> **Тема:** Диагностика и исправление reaction reasons + очистка dedup для обкатки менеджеров

---

## 📋 ПЛАН С УТРА

1. **Блок 2 (config_name)** — довести до конца: commit → push → VPS deploy → проверка
2. **Проверить реакции** — убедиться что причины нажимаются и сохраняются
3. **Очистить dedup** — чтобы менеджеры получили карточки для обкатки

---

## ✅ ЧТО РЕАЛИЗОВАНО

### 1. Блок 2 — config_name (80% → остановлен)

| Шаг | Статус |
|-----|--------|
| Код написан (run_daily_pipeline.py, telegram_sender.py, feedback_store.py) | ✅ |
| Локальные тесты прошли | ✅ |
| Commit + push | ✅ `7840171` (но Block 2 файлы НЕ в коммите — они в unstaged state) |
| VPS deploy | ❌ НЕ выполнен |

**Итог:** Блок 2 НЕ завершён. Файлы `feedback_store.py`, `run_daily_pipeline.py`, `telegram_sender.py` не закоммичены и не задеплоены. config_name в sent_ads не появился.

### 2. Reaction Reasons — НАЙДЕНА И ИСПРАВЛЕНА причина

| Шаг | Статус |
|-----|--------|
| Диагноз: `ImportError: cannot import name 'needs_comment'` | ✅ Найдено |
| Фикс: добавлены `needs_comment()` + `REASONS_NEED_COMMENT` в `ris_reason_store.py` | ✅ |
| Commit | ✅ `dda439e Add needs_comment helper for reaction reasons` |
| Push | ✅ |
| VPS deploy (`git reset --hard`) | ✅ |
| Restart feedback bot | ✅ PID 95590 |
| Тест в Telegram | ✅ 5 новых реакций после рестарта |

### 3. Очистка dedup + тестовая рассылка

| Шаг | Статус |
|-----|--------|
| Backup БД | ✅ `feedback_before_clear_dedup_20260612_1929.db` |
| `DELETE FROM sent_ads` (350 → 0) | ✅ |
| feedback/reaction_details/telegram_users НЕ тронуты | ✅ |
| Тестовая рассылка `--limit 3` | ✅ 18 сообщений (3 карточки × 6 получателей) |
| Все HTTP 200 OK | ✅ |
| Failed: 0, Skipped: 0 | ✅ |

---

## 🔴 ОШИБКИ И ИХ ПРИЧИНЫ

### Ошибка 1: Reaction reasons не сохранялись

**Симптом:** Менеджеры нажимали 👀/🤔/⏭ → выбирали причину → но `reaction_details` не пополнялся.

**Диагноз:**
```
ImportError: cannot import name 'needs_comment' from 'ris_reason_store'
  File "telegram_feedback_bot.py", line 358, in reason_handler
    from ris_reason_store import needs_comment, save_reaction_detail, get_last_feedback_id
```

**Корневая причина:**
- Локально в `ris_reason_store.py` была функция `needs_comment()` + `REASONS_NEED_COMMENT`
- Но она **НЕ была закоммичена** в git
- На VPS `ris_reason_store.py` — старая версия без `needs_comment()`
- Бот при каждом callback падал с ImportError

**Исправление:**
1. Закоммитить `ris_reason_store.py` → `dda439e`
2. Push на GitHub
3. VPS: `git reset --hard origin/main`
4. `systemctl restart haraba-feedback-bot.service`
5. Проверка: 5 новых реакций записаны в `reaction_details`

### Ошибка 2: 409 Conflict в логах feedback bot

**Симптом:**
```
telegram.error.Conflict: terminated by other getUpdates request;
make sure that only one bot instance is running
```

**Диагноз:**
- Запущено 2 процесса feedback_bot (PID 91531 и 91534)
- Оба использовали `run_polling()` → конфликт за getUpdates
- Предыдущий ручной запуск через `setsid` + systemd создали дубликаты

**Исправление:**
- `systemctl restart haraba-feedback-bot.service` — systemd убил оба, запустил один
- Новый PID 95590 → 200 OK, без Conflict

### Ошибка 3: Путаница с typo в callback_data

**Симптом:** В ранних проверках VPS показывал typo (`low_mileaage`, `liquid_modell`, `commeent`)

**Диагноз:**
- Коммит `2ff2dec` уже содержал чистые callback_data
- Но VPS файл был изменён ПОСЛЕ коммита (без git) → typo в working copy
- `git diff` пустой (потому что git не видит изменений) → путаница
- Фактический typo нашёлся только в `need__more_info` (двойное подчёркивание) — закоммичен

**Итог:** Typo в callback_data — НЕ причина проблемы. Причина — `ImportError: needs_comment`.

### Ошибка 4: Pipeline не отправляет карточки (Sent: 0)

**Симптом:** Pipeline работает каждые 10 минут, `send_ready: 17`, но `Sent: 0`, `Skipped: 168`

**Диагноз:**
- Это **НЕ баг** — нормальная работа dedup
- Карточки уже были отправлены в 18:54 → dedup находит их в sent_ads → пропускает
- Новых карточек на Haraba нет → pipeline находит те же самые → skipped

**Исправление:**
- `DELETE FROM sent_ads` → очистка dedup
- Тестовая рассылка `--limit 3` → 18 сообщений отправлено всем 6 получателям
- Pipeline снова будет отправлять новые карточки

### Ошибка 5: `get_enabled_recipients()` возвращает ВСЕХ, игнорируя статус

**Симптом:** `get_enabled_recipients()` возвращает 6 пользователей включая paused/pending

**Диагноз:**
- На VPS `feedback_store.py` — старая версия без `WHERE status = 'active'`
- Фикс есть локально, но НЕ закоммичен и НЕ задеплоен

**Статус:** ⏳ НЕ исправлено (отложено)

---

## 📊 ТЕКУЩЕЕ МЕСТО

### Что работает ✅
| Компонент | Статус |
|-----------|--------|
| Cron */10 с flock | ✅ Работает |
| Pipeline collect → enrich → audit → send | ✅ Работает |
| Feedback bot (systemd) | ✅ PID 95590, 200 OK |
| Admin bot (systemd) | ✅ PID 83193 |
| Reaction reasons (👀🤔⏭ + причины) | ✅ Сохраняются в reaction_details |
| Dedup | ✅ Очищен, 18 тестовых записей |
| Telegram send | ✅ Все HTTP 200 OK |

### Что НЕ работает ⏳
| Компонент | Проблема |
|-----------|----------|
| `get_enabled_recipients()` | Возвращает ВСЕХ 6 пользователей (игнорирует status) |
| Блок 2 (config_name) | НЕ закоммичен, НЕ задеплоен |
| Новые карточки | Haraba показывает те же карточки → dedup пропускает |

### Текущие данные БД
| Таблица | Записей |
|---------|---------|
| sent_ads | 18 (тест limit=3) |
| feedback | 37 |
| reaction_details | 31 |
| telegram_users | 6 |

### Реакции после рестарта (19:07:35)
| # | Реакция | Причина | Карточка | Менеджер | Время |
|---|---------|---------|----------|----------|-------|
| 27 | 🤔 | high_mileage | 173466594 | G.I.O | 19:08 |
| 28 | 🤔 | high_mileage | 173467898 | Haraba | 19:08 |
| 29 | 👀 | good_price | 169320232 | Haraba | 19:08 |
| 30 | 🤔 | high_price | 173461457 | G.I.O | 19:09 |
| 31 | 🤔 | high_price | 173293997 | protocol_skrin | 19:14 |

---

## 📌 ПЛАН ДАЛЕЕ

### Приоритет 1: Fix `get_enabled_recipients()`
**Проблема:** Саид (paused) и 2 pending пользователя получают карточки.
**Решение:** Закоммитить `feedback_store.py` → push → VPS deploy → restart feedback bot.

### Приоритет 2: Блок 2 (config_name)
**Проблема:** `config_name` не попадает в sent_ads.
**Решение:** Закоммитить `run_daily_pipeline.py`, `telegram_sender.py`, `feedback_store.py` → push → deploy.

### Приоритет 3: Накопление реакций
- Менеджеры получают карточки → ставят реакции → собираем данные
- Цель: 50-100 реакций для Config Intelligence

### Приоритет 4: /config_report и /learning_dashboard
- После накопления реакций — аналитика по конфигам

---

## 📦 КОММИТЫ СЕГОДНЯ

```
dda439e Add needs_comment helper for reaction reasons
7840171 Add daily report 2026-06-12 — telegram_users single source of truth...
36ab6dc Fix /recipients command to show only active users...
a238e27 Fix: telegram_users as single source of truth...
```

## 🗑 ВРЕМЕННЫЕ ФАЙЛЫ (удалить после отчёта)

```
block_*.py (15 файлов)
check_*.py (8 файлов)
d0_*.py (2 файла)
vps_*.py (15 файлов)
resolve_contradiction.py
final_typo_check.py
```

## 🔐 БЕЗОПАСНОСТЬ

- Пароль VPS использовался в скриптах → **нужно сменить после этого отчёта**
- Перейти на SSH-ключ
- Удалить все `vps_*.py`, `block_*.py`, `check_*.py` с локальной машины и VPS
