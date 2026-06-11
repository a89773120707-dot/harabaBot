# HARABA MINI — Reaction Intelligence System (RIS)

**Дата:** 2026-06-11  
**Цель:** Преобразовать реакции менеджеров в управляемые знания, которые могут улучшать скоринг карточек.

**Важное правило:** На первом этапе запрещено автоматическое изменение скоринга. Система может только собирать реакции, анализировать, предлагать правила. Применение правил возможно только после подтверждения owner.

---

## ЭТАП 0 — Подготовка

**Проверить:**
```sql
.schema feedback
.schema sent_ads
```

**Цель:** Понять структуру существующих таблиц реакций и карточек.

---

## БЛОК 1 — Нормализация реакций

**Проблема:** Сейчас реакции (👍👎🔥) не объясняют причину.

**Новые таблицы:**

### `reaction_reasons`
| Поле | Тип |
|------|-----|
| id | INTEGER PK |
| reaction_type | TEXT |
| reason_code | TEXT |
| title | TEXT |

**Данные:**
- LIKE: `good_price`, `good_mileage`, `good_equipment`, `good_region`, `good_model`, `call_now`
- DISLIKE: `expensive`, `high_mileage`, `bad_equipment`, `bad_region`, `bad_model`, `legal_risk`, `low_liquidity`
- FIRE: `rare_offer`, `below_market`, `high_margin`, `urgent_call`

### `reaction_details`
| Поле | Тип |
|------|-----|
| id | INTEGER PK |
| feedback_id | INTEGER FK → feedback |
| reason_code | TEXT |
| created_at | TEXT |

**Проверка:** Добавить тестовую реакцию → проверить `SELECT * FROM reaction_details`.

---

## БЛОК 2 — Сбор обучающих данных

**Файл:** `learning_dataset_service.py`

**Задача:** Извлекать единый датасет:
```
Модель | Год | Цена | Пробег | Регион | Комплектация | Реакция | Причина
Mazda CX-5 | 2018 | 1 890 000 | 135000 | Москва | — | LIKE | good_price
```

**Команда:** `/learning_dataset_info`

**Ответ:** Всего записей: X, LIKE: Y, DISLIKE: Z, FIRE: K

---

## БЛОК 3 — Анализ моделей

**Файл:** `model_learning_service.py`

**Считать по каждой модели:** likes, dislikes, fires

**Пример:**
```
CX-5: likes=8, dislikes=2, score=+6
BMW X5: likes=1, dislikes=5, score=-4
```

**Команда:** `/learning_models` → TOP POSITIVE / TOP NEGATIVE

---

## БЛОК 4 — Анализ причин

**Файл:** `reason_analytics_service.py`

**Считать:** самые частые причины дизлайков

**Пример:** `expensive=17, high_mileage=12, bad_equipment=5`

**Команда:** `/learning_reasons`

---

## БЛОК 5 — Таблица правил

### `learning_rules`
| Поле | Тип |
|------|-----|
| id | INTEGER PK |
| rule_type | TEXT |
| target | TEXT |
| condition_json | TEXT |
| effect_value | INTEGER |
| status | TEXT (pending/active/rejected/disabled) |
| source_reactions | INTEGER |
| created_at | TEXT |
| approved_at | TEXT |
| approved_by | TEXT |

**Проверка:** Создать тестовое правило → проверить SELECT.

---

## БЛОК 6 — Генерация правил

**Файл:** `rule_generator.py`

**Логика:**
```
Если модель:
  likes >= 5
  И likes > dislikes * 3
→ Создать предложение: model_bonus +5, status=pending
```

**Команда:** `/generate_rules`

---

## БЛОК 7 — Админ-панель обучения

**Раздел:** 🧠 Обучение

**Команды:**
- `/learning_report`
- `/rules`
- `/rule ID`
- `/approve_rule ID`
- `/reject_rule ID`
- `/disable_rule ID`

**Проверка:** Создать правило → открыть в Telegram → подтвердить → pending → active

---

## БЛОК 8 — Learning Report

**Файл:** `learning_report_service.py`

**Показывать:**
- Реакций собрано
- Модели (CX-5 +8, Tiguan +5, BMW X5 -7)
- Причины (дорого=12, пробег=9)
- Создано правил: 4

---

## БЛОК 9 — Scoring Integration

**Файл:** `reaction_learning_scorer.py`

**Цепочка:**
```
base_score → price → mileage → equipment → learning_score → final_score
```

**Важно:** Использовать только `active` правила.

**Пример логирования:**
```
Base Score = 76
Learning: +5 CX-5
Final = 81
```

---

## БЛОК 10 — Объяснение в карточке

**Добавить блок в Telegram-карточку:**
```
🧠 Learning
+5 модель часто лайкают
-3 высокий пробег
```

---

## БЛОК 11 — Безопасность

**Запретить:** автоматическое применение правил.

- Без подтверждения owner → `pending` → не участвует в скоринге.
- Только `active` правила влияют на score.

---

## БЛОК 12 — Готовность к обучению (пороги)

| Реакций | Что разрешено |
|---------|---------------|
| 50+ | `/generate_rules` |
| 100+ | Расширенные правила |
| 200+ | Semi-auto режим |

---

## ФИНАЛЬНЫЙ РЕЗУЛЬТАТ

После накопления реакций система должна:
1. Понимать причины лайков и дизлайков
2. Строить правила
3. Предлагать правила owner
4. Применять только подтверждённые правила
5. Улучшать скоринг без ручного изменения кода
