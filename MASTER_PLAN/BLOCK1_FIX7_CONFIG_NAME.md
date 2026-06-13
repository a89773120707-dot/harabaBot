# BLOCK 1 — FIX 7 CONFIG_NAME

Дата: 2026-06-13

---

## Цель

Привязать каждую отправленную карточку и каждую реакцию к конкретному `config_name`.

После этого система должна понимать:

```text
какой поиск / конфиг породил карточку
какой конфиг получил реакцию
какой конфиг даёт хорошие варианты
какой конфиг даёт мусор
```

Это обязательный фундамент для:

```text
config_report
learning_dashboard
config_diagnostics
config_suggestions
```

---

# ВАЖНЫЕ ПРАВИЛА

Работать строго по `MASTER_PLAN/AI_WORK_RULES.md`.

До отдельного утверждения пользователя запрещено:

```text
commit
push
deploy
restart
git reset
изменение VPS
очистка БД
изменение cron
```

Каждый блок:

```text
сначала факты
потом diff
потом тест
потом отчёт
потом утверждение
```

Если проверка блока не прошла — остановиться.

---

# BLOCK 1A — DESIGN REVIEW

## Цель

Перед кодом доказать, где именно должен проходить `config_name`.

## Что нужно показать

### 1. Текущий путь карточки

Показать data flow:

```text
Haraba saved search
↓
mobile_first_page_sampler
↓
detail parser
↓
run_daily_pipeline.step_audit()
↓
telegram_candidates_audited.json
↓
telegram_sender.py
↓
mark_sent_with_chat_id()
↓
sent_ads
↓
telegram_feedback_bot.py
↓
save_feedback()
↓
feedback
↓
reason_handler
↓
save_reaction_detail()
↓
reaction_details
```

---

### 2. Где появляется model_id

Найти и показать код:

```text
match_card_to_model()
model_id
get_model_by_id()
```

Показать строки в:

```text
run_daily_pipeline.py
model_matcher.py
config_loader.py
```

---

### 3. Где должен появиться config_name

Ожидаемая точка:

```text
run_daily_pipeline.py → step_audit()
```

Логика:

```python
model_id = match_card_to_model(card, config)
model_rules = get_model_by_id(config, model_id)

config_name = f"{brand} {model}"
```

Если `model_rules` не найден:

```python
config_name = "unknown"
```

---

### 4. Где config_name должен храниться

Минимальный правильный путь:

```text
sent_ads.config_name
feedback.config_name
reaction_details.config_name
```

Но можно сделать поэтапно:

```text
Stage 1:
sent_ads.config_name

Stage 2:
feedback.config_name

Stage 3:
reaction_details.config_name
```

---

### 5. Почему одного sent_ads недостаточно

Через JOIN можно получить config_name:

```sql
feedback.card_id = sent_ads.card_id
AND feedback.telegram_user_id = sent_ads.chat_id
```

Но для простых отчётов лучше дублировать `config_name` в feedback/reaction_details, чтобы:

```text
аналитика была проще
меньше зависимость от JOIN
исторические реакции не терялись при изменении sent_ads
```

---

### 6. Какие файлы менять

Ожидаемый список:

```text
run_daily_pipeline.py
telegram_sender.py
feedback_store.py
telegram_feedback_bot.py
ris_analytics.py
tests/test_block2_config_name.py
```

Если ИИ хочет менять другие файлы — остановиться и объяснить зачем.

---

### 7. Какие таблицы менять

Ожидаемые колонки:

```sql
ALTER TABLE sent_ads ADD COLUMN config_name TEXT;
ALTER TABLE feedback ADD COLUMN config_name TEXT;
ALTER TABLE reaction_details ADD COLUMN config_name TEXT;
```

Миграции должны быть безопасными:

```text
если колонка уже есть — не падать
если таблица уже есть — не пересоздавать
```

---

## Проверка BLOCK 1A

ИИ должен выдать:

```text
1. Data flow до фикса
2. Data flow после фикса
3. Список файлов
4. Список таблиц
5. Список SQL-миграций
6. Какие тесты будут
7. Что НЕ будет трогаться
```

После этого остановиться и ждать утверждения.

---

# BLOCK 1B — МИГРАЦИИ БД

## Цель

Добавить `config_name` в нужные таблицы безопасно.

## Что сделать

В `feedback_store.py` / `init_db()` добавить безопасное добавление колонок:

```sql
sent_ads.config_name TEXT
feedback.config_name TEXT
reaction_details.config_name TEXT
```

## Важно

Не пересоздавать таблицы.

Не удалять данные.

Не менять существующие колонки.

## Проверка локально

Выполнить:

```python
from feedback_store import init_db
init_db()
```

Потом SQL:

```sql
PRAGMA table_info(sent_ads);
PRAGMA table_info(feedback);
PRAGMA table_info(reaction_details);
```

Ожидаем:

```text
config_name есть во всех трёх таблицах
```

## Проверка BLOCK 1B

```text
✅ миграция не падает при повторном запуске
✅ старые данные не удалены
✅ config_name появился в sent_ads
✅ config_name появился в feedback
✅ config_name появился в reaction_details
```

Если проверка не прошла — остановиться.

---

# BLOCK 1C — CONFIG_NAME В PIPELINE

## Цель

Добавить `config_name` в карточку на этапе аудита.

## Где менять

```text
run_daily_pipeline.py
step_audit()
```

## Логика

После определения `model_id`:

```python
model_rules = get_model_by_id(config, model_id)

if model_rules:
    brand = model_rules.get("brand")
    model = model_rules.get("model")
    config_name = f"{brand} {model}"
else:
    config_name = "unknown"

card["config_name"] = config_name
```

## Проверка

Запустить dry-run или локальный тест на одной карточке.

Проверить JSON:

```text
results/telegram_candidates_audited.json
```

Ожидаем:

```json
{
  "model_id": "...",
  "config_name": "Volkswagen Tiguan"
}
```

## Проверка BLOCK 1C

```text
✅ model_id есть
✅ config_name есть
✅ unknown используется только если модель не найдена
✅ JSON содержит config_name
```

---

# BLOCK 1D — CONFIG_NAME В TELEGRAM SENDER

## Цель

Прокинуть `config_name` из audited candidate до `sent_ads`.

## Где менять

```text
telegram_sender.py
```

## Проверить места

```text
load_audited_candidates()
prepare_card_text()
send_car_card_async()
mark_sent_with_chat_id()
```

## Что должно быть

Когда карточка успешно отправлена:

```python
mark_sent_with_chat_id(
    ...,
    config_name=card.get("config_name", "unknown")
)
```

## Проверка

Локально вызвать sender на тестовой карточке.

Потом SQL:

```sql
SELECT card_id, title, config_name
FROM sent_ads
ORDER BY first_sent_at DESC
LIMIT 10;
```

Ожидаем:

```text
config_name != NULL
```

## Проверка BLOCK 1D

```text
✅ telegram_sender получает config_name
✅ mark_sent_with_chat_id принимает config_name
✅ sent_ads.config_name сохраняется
```

---

# BLOCK 1E — CONFIG_NAME В FEEDBACK

## Цель

Когда менеджер нажимает реакцию, сохранять `config_name` в `feedback`.

## Где менять

```text
telegram_feedback_bot.py
feedback_store.py
```

## Логика

При сохранении feedback:

1. Получить `card_id`
2. Получить `telegram_user_id`
3. Найти config_name в sent_ads:

```sql
SELECT config_name
FROM sent_ads
WHERE card_id = ?
AND chat_id = ?
ORDER BY first_sent_at DESC
LIMIT 1
```

4. Если не найдено:

```text
config_name = "unknown"
```

5. Записать в feedback.config_name

## Проверка

Нажать реакцию.

SQL:

```sql
SELECT id, card_id, action, telegram_user_id, config_name
FROM feedback
ORDER BY id DESC
LIMIT 10;
```

Ожидаем:

```text
config_name != NULL
```

## Проверка BLOCK 1E

```text
✅ feedback.config_name сохраняется
✅ если sent_ads есть — config_name правильный
✅ если sent_ads нет — unknown
```

---

# BLOCK 1F — CONFIG_NAME В REACTION_DETAILS

## Цель

Сохранять `config_name` рядом с reason_code.

## Где менять

```text
ris_reason_store.py
telegram_feedback_bot.py
feedback_store.py если нужно
```

## Логика

Когда вызывается:

```python
save_reaction_detail(feedback_id, reason_code)
```

функция должна:

1. Получить `config_name` из feedback:

```sql
SELECT config_name FROM feedback WHERE id = ?
```

2. Записать:

```sql
INSERT INTO reaction_details (feedback_id, reason_code, config_name)
VALUES (?, ?, ?)
```

Если `config_name` не найден:

```text
unknown
```

## Проверка

SQL:

```sql
SELECT
    rd.id,
    rd.feedback_id,
    rd.reason_code,
    rd.config_name,
    f.config_name
FROM reaction_details rd
LEFT JOIN feedback f ON f.id = rd.feedback_id
ORDER BY rd.id DESC
LIMIT 10;
```

Ожидаем:

```text
rd.config_name = f.config_name
```

## Проверка BLOCK 1F

```text
✅ reaction_details.config_name сохраняется
✅ reason_code сохраняется
✅ feedback_id связь не ломается
```

---

# BLOCK 1G — ANALYTICS UPDATE

## Цель

Обновить аналитику, чтобы она группировала реакции по config_name.

## Где менять

```text
ris_analytics.py
admin_bot/services/learning_service.py
admin_bot/services/reactions_service.py если используется
```

## Что добавить

Отчёты:

```text
/config_report
/learning_report
/learning_reasons
```

должны уметь показывать:

```text
config_name
action
reason_code
count
```

## Пример SQL

```sql
SELECT
    COALESCE(rd.config_name, f.config_name, s.config_name, 'unknown') AS config_name,
    f.action,
    rd.reason_code,
    COUNT(*) AS cnt
FROM feedback f
LEFT JOIN reaction_details rd ON rd.feedback_id = f.id
LEFT JOIN sent_ads s
    ON s.card_id = f.card_id
   AND s.chat_id = f.telegram_user_id
GROUP BY config_name, f.action, rd.reason_code
ORDER BY cnt DESC;
```

## Проверка

Админка должна показывать:

```text
Volkswagen Tiguan
👀 good_price — 3
🤔 high_price — 5
⏭ too_mileage — 2
```

## Проверка BLOCK 1G

```text
✅ отчёт работает
✅ unknown минимален
✅ группировка по config_name есть
```

---

# BLOCK 1H — ЛОКАЛЬНЫЕ ТЕСТЫ

## Цель

Доказать, что вся цепочка работает без VPS.

## Создать / обновить

```text
tests/test_block2_config_name.py
```

## Тесты

1. `init_db()` добавляет config_name во все таблицы
2. `step_audit()` добавляет config_name в card
3. `mark_sent_with_chat_id()` сохраняет config_name в sent_ads
4. `save_feedback()` сохраняет config_name в feedback
5. `save_reaction_detail()` сохраняет config_name в reaction_details
6. JOIN feedback → sent_ads → reaction_details возвращает один config_name

## Запуск

```bash
python tests/test_block2_config_name.py
```

Ожидаем:

```text
ALL BLOCK 1 CONFIG_NAME TESTS PASSED
```

## Проверка BLOCK 1H

```text
✅ все тесты прошли
✅ БД не повреждена
✅ временные тестовые записи удаляются
```

---

# BLOCK 1I — PRE-COMMIT AUDIT

## Цель

Не затащить лишние файлы.

## Выполнить

```bash
git status --short
git diff --name-only
```

Ожидаемые файлы:

```text
run_daily_pipeline.py
telegram_sender.py
feedback_store.py
telegram_feedback_bot.py
ris_reason_store.py
ris_analytics.py
tests/test_block2_config_name.py
```

Если есть лишнее:

```text
results/*
logs/*
*.db
vps_*.py
block_*.py
check_*.py
debug scripts
audit_*.py
```

не добавлять.

## Проверка

Показать:

```text
В commit попадут:
...

Не попадут:
...
```

Остановиться и ждать утверждения.

---

# BLOCK 1J — COMMIT

После утверждения:

```bash
git add <только нужные файлы>
git commit -m "Add config_name tracking for feedback analytics"
```

Проверка:

```bash
git show --stat HEAD
git diff origin/main..HEAD --name-only
```

Остановиться и ждать утверждения на push.

---

# BLOCK 1K — PUSH

После утверждения:

```bash
git push origin main
```

Проверка:

```bash
git log --oneline -3
git status --short
```

Остановиться и ждать утверждения на VPS deploy.

---

# BLOCK 1L — VPS DEPLOY

После утверждения:

```bash
cd /home/haraba/harabaBot_code
git fetch origin
git reset --hard origin/main
```

Проверка:

```bash
git log --oneline -3
git status --short
```

Проверить миграции:

```bash
.venv/bin/python -c "from feedback_store import init_db; init_db(); print('INIT OK')"
```

SQL:

```sql
PRAGMA table_info(sent_ads);
PRAGMA table_info(feedback);
PRAGMA table_info(reaction_details);
```

Ожидаем:

```text
config_name есть везде
```

Остановиться и ждать утверждения на restart.

---

# BLOCK 1M — RESTART SERVICES

После утверждения:

```bash
systemctl restart haraba-feedback-bot.service
```

Если sender/pipeline использует новый код без сервиса — restart cron не нужен.

Admin bot restart только если менялись admin_bot файлы.

Проверка:

```bash
systemctl status haraba-feedback-bot.service --no-pager
journalctl -u haraba-feedback-bot.service -n 80 --no-pager
```

Ожидаем:

```text
active/running
нет ImportError
нет 409 Conflict
```

---

# BLOCK 1N — LIVE TEST

## Цель

Доказать цепочку на VPS.

## Шаги

1. Отправить тестовую карточку:

```bash
python telegram_sender.py --send --limit 1
```

2. Нажать реакцию в Telegram:

```text
👀 → Хорошая цена
```

3. Проверить SQL:

```sql
SELECT card_id, title, config_name
FROM sent_ads
ORDER BY first_sent_at DESC
LIMIT 5;
```

```sql
SELECT id, card_id, action, config_name
FROM feedback
ORDER BY id DESC
LIMIT 5;
```

```sql
SELECT id, feedback_id, reason_code, config_name
FROM reaction_details
ORDER BY id DESC
LIMIT 5;
```

## Проверка

```text
✅ sent_ads.config_name != NULL
✅ feedback.config_name != NULL
✅ reaction_details.config_name != NULL
✅ reason_code сохранён
✅ config_name одинаковый во всех трёх местах
```

---

# BLOCK 1O — FINAL REPORT

ИИ должен выдать:

```text
Блок:
Fix 7 config_name

Что сделано:
...

Что проверено:
...

Таблицы:
sent_ads — config_name есть / нет
feedback — config_name есть / нет
reaction_details — config_name есть / нет

Live test:
sent_ads.config_name:
feedback.config_name:
reaction_details.config_name:

Результат:
PASS / FAIL

Следующий шаг:
config_report или накопление реакций
```

---

# КРИТЕРИЙ УСПЕХА FIX 7

Fix 7 считается завершённым только если на VPS в живом тесте:

```text
карточка отправлена
↓
sent_ads.config_name заполнен
↓
менеджер нажал реакцию
↓
feedback.config_name заполнен
↓
менеджер выбрал причину
↓
reaction_details.config_name заполнен
↓
reason_code сохранён
```

Если хотя бы один пункт не выполнен — Fix 7 НЕ завершён.
