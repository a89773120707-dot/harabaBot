# HARABA MINI — BLOCK 5 FINAL STATE

**Дата:** 2026-06-24  
**Ветка:** main  
**Последний коммит Block 5:** `6f1b1a9` — Block 5G.2: remove duplicate LOW readiness header in config suggestions formatter  
**Режим:** read-only документация, точка восстановления перед Block 6

---

# 1. Executive Summary

После завершения Block 5 Haraba Mini имеет работающий analytics-слой, который превращает feedback менеджеров и owner в читаемые отчёты и консервативные рекомендации по конфигам.

| Блок | Статус | Краткое содержание |
|---|---|---|
| **Block 4A** | ✅ Completed | Manager Config Report, Manager Dashboard, Admin Dashboard, интеграция в admin bot |
| **Block 4C** | ✅ Completed | Внедрён `analytics_participant`, owner участвует в аналитике без смены роли |
| **Block 5** | ✅ Completed | Config Suggestions Engine v1, Telegram-команда `/config_suggestions`, UX polish |

Все изменения read-only по отношению к конфигам: система анализирует, объясняет и предлагает, но не редактирует YAML и не меняет параметры поиска автоматически.

---

# 2. Analytics Architecture

Текущая аналитическая цепочка построена поверх существующего pipeline и использует только данные, которые уже собираются в production.

```text
Pipeline (sender + feedback bot)
        │
        ▼
   feedback
   reaction_details
   sent_ads
   feedback.comment
   telegram_users
        │
        ▼
┌─────────────────────────────────────┐
│  Analytics Participant Selector     │
│  status = 'active'                  │
│  AND analytics_participant = 1      │
└─────────────────────────────────────┘
        │
        ├───► Manager Config Report
        │           └── per-manager/per-config stats
        │
        ├───► Manager Dashboard
        │           └── compact global + per-manager view
        │
        └───► Config Suggestions Engine
                    └── recommendations per config
                            │
                            ▼
                    Admin Bot (/config_suggestions)
                            │
                            ▼
                        Owner decision
```

Ключевые принципы архитектуры:

- Все аналитические модули работают в режиме read-only.
- Единый селектор участников аналитики используется во всех отчётах.
- Owner входит в аналитику как полноценный участник, но сохраняет роль `owner`.
- Admin bot отвечает только за доступ, разбиение длинных сообщений и доставку.

---

# 3. Analytics Participant

## Проблема

Изначально аналитика использовала фильтр `role = 'manager' AND status = 'active'`. Owner давал значительную часть feedback, но полностью исключался из:

- Manager Config Report
- Manager Dashboard
- будущих Config Suggestions

Это искажало картину, потому что owner являлся одним из главных источников сигнала о качестве конфигов.

## Решение

Внедрён флаг `analytics_participant` в таблице `telegram_users`.

**Контракт участника аналитики:**

```text
status = 'active'
AND analytics_participant = 1
```

**Что изменилось:**

- Owner с `analytics_participant = 1` попадает во все аналитические отчёты.
- Роль `owner` не меняется — owner не становится `manager`.
- Active managers с `analytics_participant = 1` продолжают участвовать.
- Admins, paused, pending, disabled пользователи по умолчанию не участвуют.
- Миграция idempotent: если колонки нет, она создаётся и backfill'ится для active managers и owner.

**Текущее production-состояние:**

- Active analytics participants: 6
- Active managers с флагом: 5
- Active owner с флагом: 1

---

# 4. Manager Dashboard

## Что показывает

Manager Dashboard — компактный read-only отчёт для owner/admin, который даёт общую картину активности менеджеров.

**Глобальная сводка:**

- 📨 Отправок — сумма `sent_count` по участникам аналитики.
- 💬 Реакций — сумма `feedback_count`.
- 🎯 Конверсия — `feedback_count / sent_count`.
- 👥 Менеджеров — количество active analytics participants.

**Глобальные топы:**

- 🏆 Самые интересные конфиги — агрегированы по положительному `interest_score`.
- ⚠️ Самые проблемные конфиги — агрегированы по отрицательному `interest_score`.

**По каждому активному менеджеру:**

- Отправлено / feedback / конверсия.
- 🔥 Лучшие конфиги — до 3 с положительным интересом.
- ⚠️ Проблемные конфиги — до 3 с отрицательным интересом.
- 🧠 Причины — топ причин по `reaction_details`.
- 💬 Что сказал менеджер — последние 2 комментария.

**Группа "Без активности":** менеджеры с `feedback_count = 0`.

## Доступ

Только owner/admin через `is_admin(user_id)`. Менеджеры и неизвестные пользователи получают `⛔ Нет доступа.`

## Ограничения

- Использует только active analytics participants.
- Исключает `config_name = unknown`, `NULL` и пустые значения.
- Комментарии берутся только из последнего feedback per (`participant_id`, `card_id`, `config_name`).
- `reason_code = comment` исключается из топа причин.
- Топы ограничены 3 элементами.

---

# 5. Manager Config Report

## Что показывает

Manager Config Report — более детальный read-only отчёт по конфигам менеджеров.

**Глобальная сводка:**

- Активных менеджеров.
- Конфигов с данными.
- Карточек с feedback.

**По каждому участнику:**

- Лучшие конфиги — до 3 с положительным `interest_score`.
- Проблемные конфиги — до 3 с отрицательным `interest_score`.
- По каждому конфигу:
  - отправлено / feedback / feedback rate;
  - review / think / skip counts и rates;
  - `interest_score`;
  - статус (`GREEN` / `YELLOW` / `RED`);
  - уверенность (`LOW` / `MEDIUM` / `HIGH`);
  - топ причин;
  - последние 3 комментария;
  - время последней реакции.

**Исторический блок:**

- Количество записей в `sent_ads`, `feedback`, `reaction_details` с `config_name IS NULL / '' / 'unknown'`.

## Как считается

- Дедупликация: для каждой пары (`participant_id`, `card_id`, `config_name`) берётся только последний feedback по `MAX(id)`.
- `interest_score = review_count * 2 + think_count - skip_count * 2`.
- `feedback_rate = feedback_count / sent_count`.
- Статус:
  - `RED` — `interest_score < 0`;
  - `GREEN` — `feedback_rate >= 0.4`, `feedback_count >= 5`, `interest_score > 0`;
  - `YELLOW` — всё остальное.
- Уверенность:
  - `HIGH` — `feedback_count >= 20`;
  - `MEDIUM` — `feedback_count >= 5`;
  - `LOW` — иначе.

## Что считается сигналом

- review — сильный положительный сигнал;
- think — слабый положительный / исследовательский сигнал;
- skip — отрицательный сигнал;
- reason_code — уточняет причину реакции;
- comment — качественная evidence.

## Что считается недостатком данных

- `feedback_count < 5` — низкая уверенность;
- `feedback_count = 0` — нет данных для оценки конфига.

## Ограничения

- Только active analytics participants.
- Исключает `unknown` / пустые `config_name` из основного рейтинга.
- Комментарии ограничены 3 последними.
- Топ причин ограничен 3.

---

# 6. Config Suggestions V1

## Цель

Config Suggestions Engine отвечает на вопрос: "Что стоит изменить в конфиге и почему?" на основании реальных решений owner и менеджеров.

Dashboard отвечает "Что происходит?", а Config Suggestions отвечает "Что делать?".

## Источники данных

- `telegram_users` — селектор участников аналитики.
- `feedback` — действия `review`, `think`, `skip`, комментарии.
- `reaction_details` — причины реакций.
- `config_name` — группировка по конфигу.

## Правила

- Учитываются только active analytics participants.
- Для каждого (`participant_id`, `card_id`, `config_name`) берётся последний feedback.
- Исключаются `config_name = unknown`, `NULL`, пустые.
- `reason_code = comment` исключается из доминирующих причин.
- Пустые комментарии и `-` не попадают в evidence.
- Комментарии ограничены 3 последними; в Telegram-форматтере показываются 2.

## Формула score

```text
interest_score = review_count * 2 + think_count - skip_count * 2
reason_pressure = top_reason_count / feedback_count
```

## Пороги readiness и confidence

| feedback_count | Readiness | Confidence | Смысл |
|---:|---|---|---|
| 0–4 | NOT_READY | LOW | Недостаточно данных для рекомендации |
| 5–9 | LOW | LOW | Осторожная рекомендация |
| 10–19 | MEDIUM | MEDIUM | Рабочая рекомендация |
| 20+ | HIGH | HIGH | Сильная рекомендация |

## Типы рекомендаций v1

| Тип | Условие | Текст |
|---|---|---|
| `insufficient_data` | feedback < 5 | "Недостаточно данных. Нужно больше реакций перед изменением конфига." |
| `review_price_range` | Доминирует `high_price` / `too_expensive` | "Проверить ценовой диапазон и price/value фильтр. Не увеличивать max_price автоматически." |
| `review_mileage` | Доминирует `high_mileage` | "Проверить ограничение пробега для этого конфига." |
| `review_condition` | Доминирует `bad_condition` / `many_owners` / `history_questions` / `legal_risk` | "Проверить фильтр состояния, истории и качества карточек." |
| `increase_priority` | Доминирует `good_price` / `liquid_model`, interest_score > 0 | "Модель даёт интересные варианты, можно рассмотреть повышение приоритета." |
| `decrease_priority` | interest_score < 0 | "Модель часто отклоняют, стоит понизить приоритет или проверить критерии поиска." |
| `keep_as_is` | interest_score > 0, нет сильных негативных причин | "Модель интересная, оставить как есть и продолжать сбор реакций." |
| `mixed_signals` | Смешанные сигналы, top reason pressure < 0.5 | "Модель интересная, но сигналы смешанные. Требуется накопление данных." |

## Owner signal

- `owner_signal_present = True`, если owner дал хотя бы 1 feedback по конфигу.
- В Telegram-выводе отображается: `👤 Owner участвовал: N реакций`.
- Owner signal усиливает evidence, но не подменяет общий confidence.

## Вывод

Форматтер группирует конфиги по readiness:

1. HIGH
2. MEDIUM
3. LOW
4. NOT_READY

Для LOW-категории показывается обзорный список `🟠 Наблюдаем:` сразу перед детальными карточками.

---

# 7. Safety Rules

Config Suggestions Engine v1 работает под строгими ограничениями безопасности:

- ✅ Engine **НЕ меняет конфиги** автоматически.
- ✅ Engine **НЕ редактирует YAML**.
- ✅ Engine **НЕ меняет max_price** автоматически.
- ✅ Engine **НЕ меняет min_year, mileage, приоритеты** в конфиг-файлах.
- ✅ Engine **НЕ выполняет auto tuning**.
- ✅ Engine **НЕ выполняет auto apply**.
- ✅ Engine только анализирует, объясняет и предлагает.
- ✅ Финальное решение принимает **owner** вручную.
- ✅ Рекомендации формулируются консервативно: "проверить", "рассмотреть", "собрать больше данных".

Пример безопасной формулировки:

> "Высокая цена" → "Проверить ценовой диапазон и price/value фильтр", а не "Увеличить max_price".

---

# 8. Current Production State

Состояние на момент закрытия Block 5 (по данным VPS DB audit Block 5B + deploy Block 5G.2).

| Параметр | Значение |
|---|---:|
| Active analytics participants | 6 |
| Active managers | 5 |
| Active owners | 1 |
| Owner share of all feedback | ~55% |
| Owner share of valid config feedback | ~56% |
| Total feedback rows | 78 |
| Valid config feedback rows (deduped) | 34 |
| Configs with valid feedback | 12 |
| Configs ready for LOW suggestions (feedback ≥ 5) | 2 |
| Configs NOT_READY (feedback < 5) | 10 |
| Configs with MEDIUM confidence | 0 |
| Configs with HIGH confidence | 0 |

**Функциональность:**

- ✅ Config Suggestions работает через `/config_suggestions` и кнопку `🧠 Обучение → 💡 Рекомендации`.
- ✅ Dashboard работает.
- ✅ Manager Config Report работает.
- ✅ Owner участвует в аналитике.

**Конфиги с LOW readiness:**

- Hyundai Santa Fe — 9 feedback, 3 participants, доминирует "Высокая цена".
- Ford Kuga — 5 feedback, 2 participants, смешанные сигналы.

---

# 9. Known Limitations

## V1 ограничения, которые нужно учитывать перед Block 6

1. **Мало данных.** Большинство конфигов (10 из 12) находятся в статусе NOT_READY.
2. **Confidence в основном LOW.** Ни один конфиг не достигает MEDIUM или HIGH.
3. **Рекомендации консервативны.** Engine часто отвечает "недостаточно данных" или "проверить вручную".
4. **Нет автоматического применения.** Owner должен сам принимать решение на основе текстовых рекомендаций.
5. **Нет истории решений.** Система не запоминает, какие рекомендации owner уже видел, принял или отклонил.
6. **Нет сравнения с рынком.** Не используются внешние цены или Auto.ru valuation.
7. **Нет fine-grained управления участниками.** Флаг `analytics_participant` задаётся через БД / миграцию, нет UI.
8. **Узкий набор reason_code.** Доминируют ценовые сигналы; другие фильтры (пробег, состояние) пока реже.
9. **Telegram output статичен.** Нет интерактивных кнопок "Принять / Отклонить".
10. **Owner signal не влияет на confidence.** Только добавляет evidence-строку.

Эти ограничения являются осознанным выбором v1. Большинство из них планируется закрыть в Block 6.

---

# 10. Block 6 Preview

## Направление: Owner Approval Workflow

Block 6 должен добавить механизм явного одобрения или отклонения рекомендаций Config Suggestions owner.

```text
Config Suggestions Engine
        │
        ▼
┌─────────────────────┐
│  Recommendation     │
│  (config + action)  │
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│ Owner sees proposal │
│  Accept / Reject    │
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  Decision history   │
│  (who, when, what)  │
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  Future config      │
│  change application │
└─────────────────────┘
```

## Что ожидается в Block 6

- Каждая рекомендация может быть представлена owner как proposal.
- Owner может принять (`accept`) или отклонить (`reject`) proposal.
- Решения сохраняются в БД.
- Появляется история решений: кто, когда, по какому конфигу, какое решение.
- Принятые решения могут стать основой для будущих изменений конфигов (за пределами v1).
- Интерфейс остаётся в admin bot, доступ только owner/admin.

## Что Block 6 НЕ должен делать без отдельного approval

- Не редактировать YAML автоматически.
- Не менять production configs без explicit owner consent.
- Не ломать существующий read-only flow Block 5.

---

# Appendix A. Key Files

| Компонент | Файл | Назначение |
|---|---|---|
| Analytics participant selector | `admin_bot/services/db_service.py` | Миграция `telegram_users.analytics_participant` |
| Manager Config Report | `ris_manager_config_report.py` | Детальный per-manager/per-config отчёт |
| Manager Dashboard | `ris_manager_dashboard.py` | Компактный dashboard |
| Config Suggestions Engine | `ris_config_suggestions.py` | Рекомендации по конфигам |
| Admin Bot handlers | `admin_bot/handlers/learning.py` | Команды и кнопки Telegram |
| Admin Bot entry point | `admin_bot/admin_bot.py` | Регистрация команд |
| Manager Config Report tests | `tests/test_manager_config_report.py` | |
| Manager Dashboard tests | `tests/test_manager_dashboard.py` | |
| Config Suggestions tests | `tests/test_config_suggestions.py` | |
| Admin Dashboard tests | `tests/test_admin_dashboard.py` | |
| Admin Config Suggestions tests | `tests/test_admin_config_suggestions.py` | |
| Analytics Participant migration tests | `tests/test_analytics_participant_migration.py` | |

# Appendix B. Production Commit

- **Commit:** `6f1b1a9`
- **Branch:** main
- **Deploy:** VPS `/home/haraba/harabaBot_code` обновлён.
- **Admin Bot:** перезапущен, active/running, PID изменился.
- **Status:** BLOCK 5 CLOSED ✅

---

*Документ создан только для анализа и onboarding. Код, БД, миграции, deploy и restart не выполнялись при создании этого файла.*
