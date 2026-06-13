# Блок 2: config_name к карточкам и sent_ads

> Дата: 2026-06-12  
> Статус: **УТВЕРЖДЕНО** — готово к реализации

---

## Точка инъекции

**`run_daily_pipeline.py` → `step_audit()`**

```python
model_id = match_card_to_model(c, config)
c["model_id"] = model_id
model_rules = get_model_by_id(config, model_id)
if model_rules:
    c["config_name"] = f"{model_rules['brand']} {model_rules['model']}"
else:
    c["config_name"] = "unknown"
    log.warning(f"model_id={model_id} not found in config")
```

---

## Что меняем

| Файл | Что добавить |
|------|-------------|
| `run_daily_pipeline.py` step_audit | `config_name` к карточке из model_rules |
| `telegram_sender.py` load_audited_candidates | сохранить `config_name` из входных данных |
| `telegram_sender.py` prepare_card_text | добавить `config_name` в scored_card |
| `telegram_sender.py` mark_sent_with_chat_id | передать `config_name` |
| `feedback_store.py` init_db | `ALTER TABLE sent_ads ADD COLUMN config_name TEXT` |
| `feedback_store.py` mark_sent_with_chat_id | INSERT config_name в sent_ads |
| `telegram_feedback_bot.py` | config_name НЕ добавлять в feedback |

---

## Что НЕ меняем

- ❌ **feedback таблицу** — config_name НЕ добавляем
- ❌ **sent_ads source** — пока не нужно
- ❌ **sent_ads config_version** — пока не нужно

---

## Аналитика через JOIN

```sql
SELECT
    f.id,
    f.card_id,
    f.action,
    f.comment,
    s.config_name,
    s.title
FROM feedback f
JOIN sent_ads s
    ON s.card_id = f.card_id
   AND s.chat_id = f.telegram_user_id
ORDER BY f.created_at DESC;
```

---

## Проверка

1. Новая карточка в audit JSON имеет `config_name`
2. `telegram_sender.py` видит `config_name`
3. `sent_ads` сохраняет `config_name`
4. JOIN feedback → sent_ads возвращает `config_name`
5. Если `model_id = None` → `config_name = "unknown"`

---

## Миграция sent_ads

```python
# В init_db(), после проверки таблицы sent_ads:
c.execute("PRAGMA table_info(sent_ads)")
cols = {row[1] for row in c.fetchall()}
if "config_name" not in cols:
    c.execute("ALTER TABLE sent_ads ADD COLUMN config_name TEXT")
```
