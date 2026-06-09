# HARABA MINI — ИТЕРАЦИЯ 4 (v2)
## Сбор реакций и подготовка к серверному запуску

**Дата:** 2026-06-09

**Принцип:** Не распыляться на будущий "самообучающийся" слой.
Сначала поставить рабочий pipeline на сервер → начать собирать реакции.

**Цель ближайшего этапа:**

- ✅ Стабильный серверный запуск
- ✅ owner и manager получают карточки
- ✅ реакции сохраняются раздельно
- ✅ каждый запуск оставляет отчёт
- ✅ копим 50 реакций

---

## Итерация 1 — Закрыть Multi-recipient до конца

### Блок 1.1 — Проверить регистрацию owner/manager

**Проверить таблицу:** `telegram_recipients`

**Должно быть:**
```
owner:
  enabled: true
  chat_id: заполнен

manager:
  enabled: true
  chat_id: заполнен
```

**Проверка:**
- ✅ owner есть
- ✅ manager есть
- ✅ chat_id заполнен
- ✅ role заполнен
- ✅ enabled = 1

### Блок 1.2 — Проверить отправку одной карточки двум получателям

**Команда:**
```bash
python telegram_sender.py --send --limit 1
```

**Проверка:**
- ✅ карточка пришла owner
- ✅ карточка пришла manager
- ✅ фото пришло обоим
- ✅ кнопки есть у обоих

### Блок 1.3 — Проверить feedback по ролям

Owner и manager должны нажать реакцию и написать комментарий.

**Проверка в БД:**
- ✅ owner reaction saved
- ✅ manager reaction saved
- ✅ reviewer_role не NULL
- ✅ telegram_chat_id не NULL
- ✅ telegram_username не NULL

### Блок 1.4 — Проверить dedup по chat_id

Одна и та же машина должна отправляться:
- owner — 1 раз
- manager — 1 раз

**Повторный запуск:**
```bash
python telegram_sender.py --send --limit 1
```

**Проверка:**
- ✅ owner duplicate skip
- ✅ manager duplicate skip
- ✅ если owner уже получил, а manager нет — manager получает

---

## Итерация 2 — Daily Pipeline Report

### Блок 2.1 — Доработать run_daily_pipeline.py

**Добавить режимы:**
```bash
python run_daily_pipeline.py --dry-run
python run_daily_pipeline.py --send
python run_daily_pipeline.py --full-run --send
```

**Pipeline:**
1. check searches
2. collect cards
3. enrich
4. audit
5. dedup
6. send to recipients
7. save report

**Проверка:**
- ✅ dry-run не отправляет
- ✅ send отправляет
- ✅ full-run собирает свежие карточки

### Блок 2.2 — Создать daily report

**Файл:** `results/daily_pipeline_report.yaml`

**Поля:**
```yaml
run_id:
started_at:
duration_seconds:
cards_collected:
send_ready:
do_not_send:
hold_manual_review:
sent_new:
sent_price_drop:
skipped_duplicate:
sent_failed:
feedback_count_after_run:
recipients:
  owner:
  manager:
steps:
  check_searches:
  collect_cards:
  audit:
  send:
```

**Проверка:**
- ✅ report создаётся
- ✅ цифры совпадают с логом
- ✅ recipients разделены
- ✅ ошибки видны

### Блок 2.3 — Error recovery

**Если ошибка:**
- фото не скачалось
- Telegram не ответил
- один получатель недоступен
- одна карточка не открылась

**Pipeline не должен падать полностью.**

**Проверка:**
- ✅ ошибка записана в report
- ✅ остальные карточки продолжают отправляться
- ✅ остальные получатели получают карточки

---

## Итерация 3 — Local Final QA перед сервером

### Блок 3.1 — Три последовательных dry-run

**Команды:**
```bash
python run_daily_pipeline.py --dry-run
python run_daily_pipeline.py --dry-run
python run_daily_pipeline.py --dry-run
```

**Проверка:**
- ✅ 3/3 без crash
- ✅ report создаётся каждый раз
- ✅ unknown engine/transmission/drive не попадают в send_ready

### Блок 3.2 — Один реальный тест

**Команда:**
```bash
python run_daily_pipeline.py --send --limit 1
```

**Проверка:**
- ✅ карточка пришла owner + manager
- ✅ оба могут нажать реакцию
- ✅ комментарии сохранились
- ✅ dedup сработал на повторном запуске

### Блок 3.3 — Проверка БД

**Проверить:**
- feedback.db
- sent_ads
- telegram_recipients

**Проверка:**
- ✅ feedback не пустой
- ✅ sent_ads не пустой
- ✅ recipients = owner + manager
- ✅ нет NULL в новых feedback по reviewer_role/chat_id

---

## Итерация 4 — Подготовка к серверу

### Блок 4.1 — Список файлов для переноса

**Перенести на сервер:**
```
project/
.env
config/
results/feedback.db
session/auth files
requirements.txt
```

**Важно:**
- feedback.db не потерять
- sent_ads не потерять
- telegram_recipients не потерять

### Блок 4.2 — Проверка окружения

**На сервере:**
```bash
python --version
pip install -r requirements.txt
playwright install
python check_session.py
```

**Проверка:**
- ✅ Python работает
- ✅ зависимости стоят
- ✅ Playwright работает
- ✅ Haraba session valid

### Блок 4.3 — Проверка Telegram bot на сервере

**Запустить:**
```bash
python telegram_feedback_bot.py
```

**Проверка:**
- ✅ /help отвечает
- ✅ /recipients отвечает
- ✅ кнопки работают
- ✅ комментарии пишутся в feedback.db

---

## Итерация 5 — Серверный запуск

### Блок 5.1 — Запуск бота как сервис

**Использовать:**
```bash
systemd
```
или временно:
```bash
nohup python telegram_feedback_bot.py &
```

**Проверка:**
- ✅ бот живёт после закрытия терминала
- ✅ бот перезапускается после ошибки
- ✅ логи пишутся

### Блок 5.2 — Первый серверный pipeline dry-run

```bash
python run_daily_pipeline.py --dry-run
```

**Проверка:**
- ✅ карточки собираются
- ✅ audit проходит
- ✅ report создаётся
- ✅ Telegram не отправляет

### Блок 5.3 — Первый серверный send

```bash
python run_daily_pipeline.py --send --limit 3
```

**Проверка:**
- ✅ owner получил карточки
- ✅ manager получил карточки
- ✅ фото есть
- ✅ кнопки работают
- ✅ feedback пишется
- ✅ dedup работает

---

## Итерация 6 — Регулярный запуск

### Блок 6.1 — Расписание

**Пока поставить запуск:**
каждые 3–4 часа

**Например cron:**
```cron
0 */4 * * * cd /path/to/haraba-mini && python run_daily_pipeline.py --send >> logs/pipeline.log 2>&1
```

**Проверка:**
- ✅ запуск происходит по расписанию
- ✅ дубли не летят
- ✅ новые карточки летят
- ✅ report обновляется

### Блок 6.2 — Ежедневный feedback report

**Создать:** `daily_feedback_report.py`

**Считает:**
```yaml
total_reactions:
today_reactions:
by_action:
  buy:
  watch:
  skip:
by_role:
  owner:
  manager:
top_models:
top_comments:
```

**Проверка:**
- ✅ report создаётся
- ✅ owner/manager разделены
- ✅ цифры совпадают с feedback.db

---

## Итерация 7 — Накопление данных

### Правило

**До 50 реакций:**
- ❌ не менять скоринг
- ❌ не менять конфиг
- ❌ не менять веса

**Только:**
- ✅ отправляем карточки
- ✅ ставим реакции
- ✅ пишем комментарии

### Цель
- **50 реакций** — первая аналитика
- **100 реакций** — suggested_rules.yaml

**Проверка:**
- ✅ feedback_count >= 50
- ✅ owner и manager оба участвуют
- ✅ комментарии есть

---

## Что откладываем

**Пока НЕ делаем:**
- ❌ rule_generator.py
- ❌ rule_approval.py
- ❌ самообучение
- ❌ KPI report
- ❌ сложную аналитику

**Это делать только после 50–100 реакций.**

---

## Ближайший конкретный шаг

1. Закрыть multi-recipient QA
2. Закрыть daily_pipeline_report
3. Сделать local final QA
4. Перенести на сервер

**После сервера главная задача — накопить 50 реакций.**

---

## ТЕКУЩИЙ ПРОГРЕСС

| Итерация | Блок | Статус | Прогресс |
|----------|------|--------|----------|
| 1 | 1.1 — Регистрация | ✅ готов | owner + manager |
| 1 | 1.2 — Отправка обоим | ✅ готов | 4 фото отправлено |
| 1 | 1.3 — Feedback по ролям | ✅ готов | 2 manager реакции |
| 1 | 1.4 — Dedup по chat_id | ✅ готов | работает |
| 2 | 2.1 — run_daily_pipeline.py | ✅ готов | dry-run + send |
| 2 | 2.2 — Daily report | ✅ готов | создаётся |
| 2 | 2.3 — Error recovery | ✅ готов | try/except везде |
| 3 | 3.1 — 3x dry-run | ⏳ требуется | - |
| 3 | 3.2 — Реальный тест | ⏳ требуется | - |
| 3 | 3.3 — Проверка БД | ⏳ требуется | - |
| 4 | 4.1 — Файлы для сервера | ⏳ требуется | - |
| 4 | 4.2 — Окружение сервера | ⏳ требуется | - |
| 4 | 4.3 — Bot на сервере | ⏳ требуется | - |
| 5 | 5.1 — Bot как сервис | ⏳ требуется | - |
| 5 | 5.2 — Server dry-run | ⏳ требуется | - |
| 5 | 5.3 — Server send | ⏳ требуется | - |
| 6 | 6.1 — Расписание | ⏳ требуется | - |
| 6 | 6.2 — Daily feedback report | ⏳ требуется | - |
| 7 | Накопление 50 реакций | 🔄 в работе | **17/50** |
