# BLOCK 1A — DESIGN REVIEW

Дата: 2026-06-13

---

## 1. Data flow ДО фикса

```
Haraba saved search
  ↓
mobile_first_page_sampler.py — собирает карточки
  ↓
run_daily_pipeline.py → step_audit()
  ├── match_card_to_model() → model_id
  ├── get_model_by_id() → model_rules
  ├── c["config_name"] = f"{brand} {model}"  ← ✅ config_name ПРИСВОЕН
  └── save audited JSON
  ↓
telegram_candidates_audited.json — config_name есть в JSON ✅
  ↓
telegram_sender.py → load_audited_candidates()
  ├── config_name есть в карточке ✅
  ├── mark_sent_with_chat_id(card, ...) — извлекает card.get("config_name") ✅
  └── sent_ads.config_name — ✅ КОЛОНКА ЕСТЬ, но данные NULL (код не задеплоен)
  ↓
telegram_feedback_bot.py → reason_handler
  ├── _save_feedback_for_chat() — строит feedback_card dict
  │   └── config_name НЕ включён в feedback_card  ← ❌ ТЕРЯЕТСЯ ЗДЕСЬ
  ├── save_feedback(feedback_card, ...)
  │   └── feedback.config_name — ❌ КОЛОНКИ НЕТ в таблице
  └── save_reaction_detail(feedback_id, reason_code)
      └── reaction_details.config_name — ❌ КОЛОНКИ НЕТ в таблице
```

**Итого — где теряется:**

| Точка | config_name |
|-------|-------------|
| run_daily_pipeline.py step_audit() | ✅ Присвоен |
| telegram_candidates_audited.json | ✅ Есть |
| telegram_sender.py → mark_sent | ✅ Есть, но NULL в БД (не задеплоен) |
| telegram_feedback_bot.py → _save_feedback_for_chat | ❌ Не включён в feedback_card dict |
| feedback_store.py → save_feedback() | ❌ Колонки нет в таблице |
| ris_reason_store.py → save_reaction_detail() | ❌ Колонки нет в таблице |

---

## 2. Data flow ПОСЛЕ фикса

```
run_daily_pipeline.py → step_audit()
  ├── c["config_name"] = "Volkswagen Tiguan"  ✅
  └── save audited JSON
  ↓
telegram_candidates_audited.json — config_name ✅
  ↓
telegram_sender.py → mark_sent_with_chat_id(card, ...)
  └── sent_ads.config_name = "Volkswagen Tiguan"  ✅
  ↓
telegram_feedback_bot.py → reason_handler
  ├── _save_feedback_for_chat()
  │   ├── feedback_card["config_name"] = card.get("config_name", "unknown")  ✅ НОВОЕ
  │   └── save_feedback(feedback_card, ...)
  └── feedback.config_name = "Volkswagen Tiguan"  ✅ НОВОЕ
  ↓
save_reaction_detail(feedback_id, reason_code)
  ├── SELECT config_name FROM feedback WHERE id = ?  ✅ НОВОЕ
  └── reaction_details.config_name = "Volkswagen Tiguan"  ✅ НОВОЕ
```

---

## 3. Где появляется model_id

**Файл:** `model_matcher.py`

**Функция:** `match_card_to_model(card, config) → str | None`

**Вызывается в:**
- `run_daily_pipeline.py` строка 214:
  ```python
  model_id = match_card_to_model(c, config)
  c["model_id"] = model_id
  ```
- `telegram_sender.py` строка 139:
  ```python
  model_id = match_card_to_model(norm, config)
  c["model_id"] = model_id
  ```

---

## 4. Где появляется config_name (текущее состояние)

**run_daily_pipeline.py** (строка 218-224):
```python
model_rules = get_model_by_id(config, model_id) if model_id else None
if model_rules:
    c["config_name"] = f"{model_rules['brand']} {model_rules['model']}"
else:
    c["config_name"] = "unknown"
```

**telegram_sender.py** (строка 142-150):
```python
if not c.get("config_name"):
    if model_id:
        model_rules = get_model_by_id(config, model_id)
        if model_rules:
            c["config_name"] = f"{model_rules['brand']}{model_rules['model']}"
        else:
            c["config_name"] = "unknown"
    else:
        c["config_name"] = "unknown"
```

---

## 5. Где сейчас теряется config_name

### 5.1 sent_ads — данные NULL

**Причина:** Код в run_daily_pipeline.py и telegram_sender.py правильный, но НЕ закоммичен и НЕ задеплоен на VPS.

`mark_sent_with_chat_id()` в `feedback_store.py` (строка 688) уже извлекает config_name:
```python
config_name = card.get("config_name", "unknown")
```

Но на VPS этот код не работает, потому что старые версии файлов.

### 5.2 feedback — колонки нет

**Причина:** `save_feedback()` в `feedback_store.py` (строка 400):
- INSERT НЕ включает config_name
- Колонки `config_name` нет в таблице `feedback`
- `_save_feedback_for_chat()` в `telegram_feedback_bot.py` (строка 309) НЕ включает config_name в feedback_card dict

### 5.3 reaction_details — колонки нет

**Причина:** `save_reaction_detail()` в `ris_reason_store.py` (строка 28):
- INSERT: `INSERT INTO reaction_details (feedback_id, reason_code, created_at)`
- Нет config_name параметра
- Колонки `config_name` нет в таблице `reaction_details`

---

## 6. Таблицы для изменения

| Таблица | Колонка | Текущее состояние | Действие |
|---------|---------|-------------------|----------|
| `sent_ads` | `config_name TEXT` | ✅ Колонка есть, данные NULL | Только записать данные (код уже готов) |
| `feedback` | `config_name TEXT` | ❌ Колонки нет | ALTER TABLE + изменить save_feedback() |
| `reaction_details` | `config_name TEXT` | ❌ Колонки нет | ALTER TABLE + изменить save_reaction_detail() |

---

## 7. SQL-миграции

```sql
-- feedback_store.py → init_db()
-- Безопасное добавление колонок (не падает если уже есть)

ALTER TABLE feedback ADD COLUMN config_name TEXT;
ALTER TABLE reaction_details ADD COLUMN config_name TEXT;
```

Для sent_ads миграция НЕ нужна — колонка уже есть.

**Безопасная реализация в init_db():**
```python
# Проверить, есть ли колонка, перед добавлением
c.execute("PRAGMA table_info(feedback)")
existing_cols = {row[1] for row in c.fetchall()}
if "config_name" not in existing_cols:
    c.execute("ALTER TABLE feedback ADD COLUMN config_name TEXT")

c.execute("PRAGMA table_info(reaction_details)")
existing_cols = {row[1] for row in c.fetchall()}
if "config_name" not in existing_cols:
    c.execute("ALTER TABLE reaction_details ADD COLUMN config_name TEXT")
```

---

## 8. Функции для изменения

| Функция | Файл | Что изменить |
|---------|------|-------------|
| `init_db()` | `feedback_store.py` | Добавить безопасные ALTER TABLE для feedback и reaction_details |
| `save_feedback()` | `feedback_store.py` | Добавить `config_name` в INSERT; извлечь из `card.get("config_name", "unknown")` |
| `save_reaction_detail()` | `ris_reason_store.py` | Добавить `config_name` — получить из feedback по feedback_id |
| `_save_feedback_for_chat()` | `telegram_feedback_bot.py` | Включить `config_name` в feedback_card dict |

---

## 9. Файлы для изменения

| Файл | Блоки | Изменение |
|------|-------|-----------|
| `feedback_store.py` | 1B, 1E | Миграции + save_feedback с config_name |
| `ris_reason_store.py` | 1F | save_reaction_detail берёт config_name из feedback |
| `telegram_feedback_bot.py` | 1E | _save_feedback_for_chat включает config_name |
| `run_daily_pipeline.py` | 1C | config_name уже есть — убедиться что попадает в JSON |
| `telegram_sender.py` | 1D | config_name уже есть — убедиться что доходит до mark_sent |
| `tests/test_block2_config_name.py` | 1H | НОВЫЙ файл — 6 тестов |

**Файлы НЕ меняем в BLOCK 1A-1F:**
- `ris_analytics.py` — BLOCK 1G (аналитика), отдельно
- `admin_bot/` — BLOCK 1G, отдельно

---

## 10. SQL-проверки

После каждого блока:

```sql
-- Проверка sent_ads (BLOCK 1D)
SELECT card_id, title, config_name
FROM sent_ads
ORDER BY first_sent_at DESC
LIMIT 10;
-- Ожидаем: config_name != NULL

-- Проверка feedback (BLOCK 1E)
SELECT id, card_id, action, config_name
FROM feedback
ORDER BY id DESC
LIMIT 10;
-- Ожидаем: config_name != NULL

-- Проверка reaction_details (BLOCK 1F)
SELECT rd.id, rd.feedback_id, rd.reason_code, rd.config_name, f.config_name
FROM reaction_details rd
LEFT JOIN feedback f ON f.id = rd.feedback_id
ORDER BY rd.id DESC
LIMIT 10;
-- Ожидаем: rd.config_name = f.config_name
```

---

## 11. Тесты (BLOCK 1H)

Файл: `tests/test_block2_config_name.py`

| # | Тест | Что проверяет |
|---|------|---------------|
| 1 | `test_init_db_adds_config_name` | init_db() добавляет config_name в feedback и reaction_details, не падает при повторном запуске |
| 2 | `test_config_name_in_audited_card` | step_audit() добавляет config_name в карточку |
| 3 | `test_mark_sent_saves_config_name` | mark_sent_with_chat_id() сохраняет config_name в sent_ads |
| 4 | `test_save_feedback_saves_config_name` | save_feedback() сохраняет config_name в feedback |
| 5 | `test_save_reaction_detail_gets_config_name` | save_reaction_detail() берёт config_name из feedback |
| 6 | `test_config_name_consistency` | JOIN feedback → sent_ads → reaction_details возвращает один config_name |

---

## 12. Что НЕ трогаем

| Объект | Почему не трогаем |
|--------|-------------------|
| `ris_analytics.py` | BLOCK 1G — аналитика, после базового трекинга |
| `admin_bot/` | BLOCK 1G — отдельно |
| `model_matcher.py` | Логика матчинга не меняется |
| `config_loader.py` | Логика загрузки конфига не меняется |
| `run_daily_pipeline.py` — структура | Только config_name уже есть, не меняем структуру |
| `telegram_sender.py` — структура | Только config_name уже есть, не меняем структуру |
| `mobile_first_page_sampler.py` | Сбор карточек не меняется |
| `sent_ads` — удаление данных | Старые записи остаются с config_name=NULL (это OK) |
| `cron`, `.env`, токены | Правило AI_WORK_RULES.md |
| `telegram_recipients` | Legacy, не используется |

---

## ИТОГ BLOCK 1A

### Изменения минимальны — 4 файла:

1. `feedback_store.py` — миграции + save_feedback
2. `ris_reason_store.py` — save_reaction_detail берёт config_name из feedback
3. `telegram_feedback_bot.py` — включить config_name в feedback_card dict
4. `tests/test_block2_config_name.py` — новый файл тестов

### run_daily_pipeline.py и telegram_sender.py — КОД УЖЕ ЕСТЬ

Эти два файла уже содержат логику config_name. Они не закоммичены, но код верный. Не меняем — только включаем в commit.

### Источник config_name для reaction_details:

`save_reaction_detail(feedback_id, reason_code)` сам берёт config_name:
```sql
SELECT config_name FROM feedback WHERE id = ?
```

НЕ передаём config_name руками — меньше риска рассинхрона.

---

**BLOCK 1A завершён. Ожидаю утверждения.**
