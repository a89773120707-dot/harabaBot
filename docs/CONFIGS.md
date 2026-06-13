# Configs / ENV Audit

> Дата: 2026-06-13
> Режим: только чтение, без изменений

---

## 1. Краткий вывод

| Параметр | Значение |
|----------|----------|
| Активных YAML конфигов | **4** (ready_8, awd_9, full_config, auto_ru_searches) |
| Активных JSON конфигов | **0** (только runtime данные) |
| ENV файл | ✅ `.env` (2 Telegram токена, OWNER_ID, DB_PATH) |
| Секретов в коде | ⚠ **Да** — OWNER_ID hardcoded в 3+ файлах |
| manager_config | ❌ **Нет** — не существует |
| Связь manager → config | ❌ **Нет** |
| config_name в sent_ads | ✅ Колонка есть, все записи NULL |
| config_name в feedback | ❌ Колонки нет |

---

## 2. Найденные config файлы

### YAML конфиги (ACTIVE)

| Файл | Назначение | Кто читает | Секреты | Статус |
|------|-----------|-----------|---------|--------|
| `config/awd_liquid_full_config.yaml` (1678 строк) | Полный конфиг 17 моделей | `run_daily_pipeline.py`, `telegram_sender.py`, `config_scoring_tester.py`, `telegram_audit.py` | ❌ Нет | **ACTIVE** |
| `config/awd_liquid_ready_8.yaml` (350 строк) | 8 исходных моделей + search_filters | `config_loader_8.py`, `run_saved_searches_8.py` | ❌ Нет | **ACTIVE** |
| `config/awd_liquid_9.yaml` (370 строк) | 9 дополнительных моделей | `config_loader_9.py` | ❌ Нет | **ACTIVE** |
| `config/auto_ru_searches.yaml` | Auto.ru search URLs (MVP) | `app/matcher/auto_ru_matcher.py` | ❌ Нет | **ACTIVE** (frozen) |

### YAML конфиги (REGISTRY / REPORTS)

| Файл | Назначение | Статус |
|------|-----------|--------|
| `config/saved_searches_8.yaml` | Registry 8 сохранённых поисков Haraba | ACTIVE |
| `config/saved_searches_9.yaml` | Registry 9 сохранённых поисков Haraba | ACTIVE |
| `config/market_input_9.yaml` | Входные данные для market analysis 9 моделей | TEST |
| `results/price_ranges_9.yaml` | Ценовые диапазоны 9 моделей | LEGACY |
| `results/price_ranges_9_v2.yaml` | Ценовые диапазоны v2 | LEGACY |
| `results/expert_rules_9_ready.yaml` | Экспертные правила 9 моделей | LEGACY |
| `results/saved_searches_9_registry.yaml` | Registry 9 поисков | ACTIVE |
| `results/awd_liquid_full_config.yaml` | Копия полного конфига в results/ | COPY |

### YAML отчёты (GENERATED)

| Файл | Генерируется | Статус |
|------|-------------|--------|
| `results/daily_pipeline_report.yaml` | `run_daily_pipeline.py` | ACTIVE |
| `results/telegram_sender_report.yaml` | `telegram_sender.py` | ACTIVE |
| `results/telegram_send_dry_run_report.yaml` | `telegram_sender.py --dry-run` | TEST |
| `results/daily_pipeline_report_2026-06-09.md` | Pipeline | LEGACY |
| `results/*_qa_report.yaml` | Тесты скоринга | TEST |
| `results/market_analysis_*.yaml` | Market analysis | TEST |
| `results/coverage_report.yaml` | Coverage report | TEST |
| `results/mobile_fields_coverage_report.yaml` | Mobile sampler | TEST |
| `results/mobile_sampler_final_report.yaml` | Mobile sampler | TEST |
| `results/enrichment_*.yaml` | Enrichment reports | TEST |
| `results/search_setup_report.yaml` | Search setup | LEGACY |
| `results/apply_all_searches_17_report.yaml` | Search verification | ACTIVE |
| `results/config_scoring_test_*.yaml` | Scoring tests | TEST |

### JSON файлы (RUNTIME DATA)

| Файл | Назначение | Статус |
|------|-----------|--------|
| `data/state.json` | Playwright session Haraba | ACTIVE (secret) |
| `data/state_backup.json` | Backup сессии | BACKUP |
| `data/auto_ru_state.json` | Playwright session Auto.ru | ACTIVE (frozen) |
| `results/mobile_first_page_sample.json` | Собранные карточки | RUNTIME |
| `results/latest_cards_raw.json` | Raw карточки pipeline | RUNTIME |
| `results/latest_cards_enriched.json` | Enriched карточки | RUNTIME |
| `results/latest_cards_audited.json` | Audited карточки | RUNTIME |
| `results/telegram_candidates_audited.json` | Кандидаты для Telegram | RUNTIME |
| `results/mobile_details_cache_17.json` | Кэш mobile detail | RUNTIME |
| `results/real_cards_matched_17.json` | Matched cars from DB | TEST |
| `results/test_cards_500.json` | Тестовые карточки | TEST |
| `results/enriched_cards_*.json` | Enriched test cards | TEST |
| `results/evaluations_*.json` | Auto.ru evaluations | TEST |
| `results/cards_*.json` | Parsed cards | TEST |
| `results/debug/*.json` | Debug данные Auto.ru | DEBUG |

### ENV файл

| Файл | Содержит | Статус |
|------|---------|--------|
| `.env` | Telegram токены, OWNER_ID, ADMIN_IDS, DB_PATH | **ACTIVE** (секрет) |

### Python config модули

| Файл | Назначение | Статус |
|------|-----------|--------|
| `config_loader.py` | Загрузка YAML → dict | ACTIVE |
| `config_loader_8.py` | Загрузка ready_8 | ACTIVE |
| `config_loader_9.py` | Загрузка awd_9 | ACTIVE |
| `admin_bot/config.py` | ENV vars для admin bot | ACTIVE |

---

## 3. Search configs

### Где находится список 17 моделей?

**Основной файл:** `config/awd_liquid_full_config.yaml`

**Содержит:**
- `config_name: awd_liquid_full_config`
- `version: '1.0'`
- `models:` — список из 17 моделей
- `global_rules:` — reject/bonus/penalty правила

**Модели (17):**

| # | ID | Brand | Model | Status | Priority |
|---|----|-------|-------|--------|----------|
| 1 | `kia_rio` | Kia | Rio | ready | high |
| 2 | `ford_kuga` | Ford | Kuga | ready | high |
| 3 | `kia_sorento_prime` | Kia | Sorento Prime | ready | very_high |
| 4 | `volkswagen_touareg_nf` | Volkswagen | Touareg | ready | very_high |
| 5 | `volkswagen_tiguan` | Volkswagen | Tiguan | ready | high |
| 6 | `nissan_xtrail` | Nissan | X-Trail | ready | very_high |
| 7 | `nissan_qashqai_j11` | Nissan | Qashqai | ready | high |
| 8 | `mercedes_glk_220_cdi` | Mercedes-Benz | GLK-Класс | ready | medium_high |
| 9 | `volkswagen_multivan_t5` | Volkswagen | Multivan | ready | high |
| 10 | `audi_q5` | Audi | Q5 | ok | very_high |
| 11 | `hyundai_santa_fe` | Hyundai | Santa Fe | ok | high |
| 12 | `kia_sorento` | Kia | Sorento | ok | high |
| 13 | `kia_sportage` | Kia | Sportage | ok | medium_high |
| 14 | `mazda_cx5` | Mazda | CX-5 | ok | high |
| 15 | `mitsubishi_pajero_iv` | Mitsubishi | Pajero | ok | medium_high |
| 16 | `hyundai_grand_santa_fe` | Hyundai | Grand Santa Fe | low_evaluation_sample | very_high |
| 17 | `nissan_pathfinder` / `volvo_xc90` | Nissan/Volvo | Pathfinder/XC90 | ok | very_high/medium_high |

**Примечание:** `ford_kuga` встречается дважды в конфиге (дубликат ID).

### Как загружается конфиг?

```python
# config_loader.py
def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)

def get_model_by_id(config, model_id):
    for m in config.get("models", []):
        if m.get("id") == model_id:
            return m
    return None
```

**Кто вызывает:**
- `run_daily_pipeline.py:step_audit()` → `load_config()`, `get_model_by_id()`
- `telegram_sender.py:load_audited_candidates()` → `load_config()`, `get_model_by_id()`
- `telegram_audit.py:main()` → `load_config()`, `get_models()`, `get_model_by_id()`
- `telegram_card_formatter.py` → `get_model_by_id()`
- `config_scoring_tester.py` → `load_config()`, `get_models()`
- `app/analyzer/*.py` → `load_config()`, `get_model_by_id()`

### Какие поля есть у поиска (модели)

**Минимальные поля (все модели):**
- `id` — уникальный идентификатор
- `name` — читаемое название
- `brand` — бренд
- `model` — модель
- `status` — ready/ok/low_evaluation_sample
- `priority` — very_high/high/medium_high

**Поля для scoring (полные модели):**
- `price:` — excellent/good/fair/expensive_but_ok_if_top/reject_if_weak
- `mileage:` — excellent/good/penalty/reject
- `engines:` — best/acceptable/avoid
- `transmissions:` — best/avoid
- `drive:` — awd/4matic
- `trims:` — best/good/acceptable
- `must_have:` — обязательные условия
- `strong_bonus:` — бонусные признаки
- `penalty:` — штрафные признаки
- `reject:` — признаки отказа
- `risk_check:` — что проверять вручную
- `notes:` — дополнительные заметки

**Поля для Haraba search (ready_8/awd_9):**
- `search_filters:` — brand, model, year_from/to, price_from/to, transmission, fuel, drivetrain, regions, legal_restrictions, seller_type, owners_range, condition, mileage_max

### Есть ли config_name?

**✅ Да.** В полном конфиге: `config_name: awd_liquid_full_config`

**Где создаётся config_name для карточки:**

1. `run_daily_pipeline.py:step_audit()` (line 205-211):
   ```python
   if model_rules:
       c["config_name"] = f"{model_rules['brand']} {model_rules['model']}"
   else:
       c["config_name"] = "unknown"
   ```

2. `telegram_sender.py:load_audited_candidates()` (line 119-128):
   ```python
   if model_rules:
       c["config_name"] = f"{model_rules['brand']} {model_rules['model']}"
   else:
       c["config_name"] = "unknown"
   ```

### Можно ли добавить новые модели без изменения кода?

**✅ Да.** Достаточно добавить новую модель в `config/awd_liquid_full_config.yaml`:

```yaml
models:
- id: new_model
  name: New Model
  brand: Brand
  model: Model
  ...
```

**Но:** Для создания Haraba saved search нужен также `search_filters` блок (как в ready_8/awd_9).

### Лимит Haraba по поискам

**Известный лимит:** Haraba позволяет ~17-20 сохранённых поисков.

**Текущее состояние:** 17 поисков создано и верифицировано.

---

## 4. 17 моделей / общий пул

### Архитектура конфигов

```
config/awd_liquid_ready_8.yaml  (8 моделей, с search_filters)
config/awd_liquid_9.yaml        (9 моделей, с search_filters)
  ↓ объединение
config/awd_liquid_full_config.yaml  (17 моделей, scoring rules)
  ↓
results/awd_liquid_full_config.yaml  (копия)
  ↓
pipeline: run_daily_pipeline.py → load_config()
```

### Структура полного конфига

```yaml
config_name: awd_liquid_full_config
description: Полный конфиг 17 моделей — 8 готовых + 9 из анализа рынка Auto.ru
version: '1.0'
global_rules:
  search_strategy:
    rule: Поиск делаем шире, скоринг делаем жестче
    avoid_too_narrow_search: true
  global_reject: [red_autoteka, airbags_deployed, ...]  # 9 правил
  global_bonus: {green_autoteka: 25, one_owner: 15, ...}  # 14 бонусов
  global_penalty: {three_owners: -5, four_plus_owners: -20, ...}  # 11 штрафов
models:
  - id: kia_rio
    name: Kia Rio
    brand: Kia
    model: Rio
    price: {excellent: "...", good: "...", ...}
    mileage: {excellent: "...", good: "...", ...}
    engines: {best: [...], acceptable: [...]}
    transmissions: {best: [...], avoid: [...]}
    ...
```

---

## 5. manager_config статус

### Есть ли manager_config сейчас?

❌ **НЕТ.** Не существует ни одного файла, таблицы, или кода, связанного с персональными конфигами менеджеров.

### Поиск по ключевым словам

| Ключевое слово | Найдено? | Где |
|----------------|----------|-----|
| `manager_config` | ❌ Нет | — |
| `managers.yaml` | ❌ Нет | — |
| `recipients.yaml` | ❌ Нет | — |
| `enabled_models` | ❌ Нет | — |
| `allowed_brands` | ❌ Нет | — |
| `per-manager` | ❌ Нет | — |
| `preferences` | ❌ Нет | — |
| `chat_id` + config | ❌ Нет | — |

### Какие заготовки есть?

| Элемент | Статус | Описание |
|---------|--------|----------|
| `config_name` в sent_ads | ✅ Колонка есть | Но все записи NULL |
| `config_name` в pipeline | ✅ Код есть | step_audit() устанавливает config_name |
| `config_name` в telegram_sender | ✅ Код есть | load_audited_candidates() пересчитывает |
| `telegram_users` таблица | ✅ Есть | Но нет связи с config_name |
| `get_enabled_recipients()` | ✅ Есть | Возвращает {chat_id, username, first_name, role} — БЕЗ config_name |

### Связь manager → config_name

❌ **Нет.** Нет таблицы, нет колонки, нет кода.

### Связь manager → allowed models

❌ **Нет.** Все менеджеры получают все 17 моделей.

### Персональная фильтрация

❌ **Нет.** Нет фильтрации карточек по менеджеру.

### Что нужно добавить минимально

1. **Вариант A (простой):** Колонка `config_name` в `telegram_users`
   ```sql
   ALTER TABLE telegram_users ADD COLUMN config_name TEXT;
   ```
   Один менеджер → один config_name.

2. **Вариант B (гибкий):** Таблица `manager_configs`
   ```sql
   CREATE TABLE manager_configs (
       telegram_id INTEGER,
       config_name TEXT,
       enabled INTEGER DEFAULT 1,
       PRIMARY KEY (telegram_id, config_name)
   );
   ```
   Один менеджер → несколько конфигов.

3. **Изменить `get_enabled_recipients()`:**
   ```python
   def get_enabled_recipients():
       # Возвращать также config_names
       SELECT telegram_id as chat_id, username, first_name, role
       FROM telegram_users WHERE status = 'active'
   ```
   → добавить config_name в результат.

4. **Изменить pipeline:** Для каждого recipient → фильтровать карточки по его config_name.

---

## 6. ENV / secrets

### Переменные окружения (.env)

| Переменная | Значение (маскированное) | Назначение |
|------------|-------------------------|------------|
| `TELEGRAM_BOT_TOKEN` | `8794875955:AAEG88lT***` | Токен основного бота (рассылка) |
| `TELEGRAM_CHAT_ID` | `8992376203` | Chat ID owner (fallback) |
| `ADMIN_BOT_TOKEN` | `8688295456:AAHnETH***` | Токен админ-бота |
| `OWNER_ID` | `8992376203` | Telegram ID владельца |
| `ADMIN_IDS` | `8992376203` | Список admin ID (comma-separated) |
| `DB_PATH` | `results/feedback.db` | Путь к SQLite БД |
| `LOG_PATH` | `logs/` | Путь к логам |
| `BACKUP_PATH` | `backups/` | Путь к бэкапам |
| `EXPORT_PATH` | `exports/` | Путь к экспортам |

### Telegram токены откуда берутся?

**Файл:** `.env` (не tracked в git — в `.gitignore`)

**Чтение:**
- `telegram_sender.py:load_telegram_config()` → `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `telegram_feedback_bot.py:load_telegram_config()` → `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `admin_bot/config.py` → `ADMIN_BOT_TOKEN`, `OWNER_ID`, `ADMIN_IDS`, `DB_PATH`

### БД путь откуда берётся?

**feedback_store.py:** `DB_PATH = RESULTS_DIR / "feedback.db"` (hardcoded)

**admin_bot/config.py:** `DB_PATH = Path(os.getenv("DB_PATH", "results/feedback.db"))` (из .env)

**ris_analytics.py:** `DB_PATH = "results/feedback.db"` (hardcoded)

**ris_reason_store.py:** `DB_PATH = "results/feedback.db"` (hardcoded)

### Haraba credentials где хранятся?

**Сессия:** `data/state.json` — Playwright storage state (cookies + localStorage).

**Это НЕ логин/пароль** — это сериализованная сессия браузера после ручного логина.

### Auto.ru credentials есть?

**Сессия:** `data/auto_ru_state.json` — Playwright storage state для Auto.ru.

**Persistent profile:** `results/auto_ru_chrome_profile/` — Chrome user data directory.

**Но:** Auto.ru модуль ЗАМОРОЖЕН (100% CAPTCHA).

### Есть ли секреты в коде?

| Секрет | Где | Риск |
|--------|-----|------|
| **Telegram токены** | `.env` (не в git) | ✅ OK |
| **OWNER_ID** | Hardcoded в 3+ файлах | ⚠ LOW — это публичный Telegram ID |
| **state.json** | `data/state.json` | ⚠ MEDIUM — сессия браузера |
| **VPS password** |曾用 в `vps_*.py` скриптах | ⚠ HIGH — если не сменён |

### Есть ли OWNER_ID hardcoded?

**✅ Да, в нескольких файлах:**

| Файл | Строка | Значение |
|------|--------|----------|
| `feedback_store.py` | 417 | `OWNER_ID = 8992376203` |
| `telegram_feedback_bot.py` | 154, 184, 203 | `OWNER_ID = 8992376203` |
| `admin_bot/config.py` | 10 | `OWNER_ID = int(os.getenv("OWNER_ID", "8992376203"))` |
| `admin_bot/permissions.py` | 4 | `return user_id == OWNER_ID` |

### Есть ли риск утечки токенов?

**Риски:**

| Риск | Уровень | Описание |
|------|---------|----------|
| `.env` в git | ❌ Нет | `.gitignore` исключает `.env` |
| Токены в логах | ⚠ MEDIUM | При ошибках могут попасть в логи |
| `state.json` в git | ⚠ MEDIUM | Сессия браузера — можно использовать для доступа к Haraba |
| VPS password в скриптах | 🔴 HIGH | `vps_*.py` файлы могут содержать пароли |
| OWNER_ID hardcoded | ✅ LOW | Telegram ID — не секрет, но сложно менять |

---

## 7. OWNER_ID / roles

### Роли

| Роль | Описание | OWNER_ID |
|------|----------|----------|
| `owner` | Полный доступ, нельзя отключить | `8992376203` |
| `admin` | Доступ к админке | Из `.env ADMIN_IDS` |
| `manager` | Получает карточки, ставит реакции | Из `telegram_users` |
| `viewer` | Fallback в feedback bot | Не в БД |

### Где хранятся роли

| Роль | Хранилище |
|------|-----------|
| owner | `.env OWNER_ID` + `telegram_users.role='owner'` |
| admin | `.env ADMIN_IDS` |
| manager | `telegram_users.role='manager'` |

### Проверка доступа

| Место | Проверка | Файл |
|-------|----------|------|
| Admin bot handlers | `is_admin(user_id)` | `admin_bot/permissions.py` |
| User modification | `can_modify_user(actor_id, target_id)` | `admin_bot/permissions.py` |
| Owner protection | `is_owner(target_id)` → нельзя модифицировать | `admin_bot/permissions.py` |

---

## 8. Config loading flow

### Flow загрузки конфигов

```
1. run_daily_pipeline.py:step_audit()
   ↓
   config_path = "config/awd_liquid_full_config.yaml"
   config = load_config(config_path)  → dict
   ↓
   get_model_by_id(config, model_id)  → model_rules dict
   ↓
   model_rules используется для:
     - config_name = f"{brand} {model}"
     - score_price(price, model_rules["price"])
     - score_mileage(mileage, model_rules["mileage"])
     - score_engine(engine, model_rules["engines"])
     - score_transmission(transmission, model_rules["transmissions"])
     - score_equipment(card, model_rules)

2. telegram_sender.py:load_audited_candidates()
   ↓
   config = load_config(CONFIG_PATH)
   ↓
   Для каждой карточки:
     model_id = match_card_to_model(card, config)
     model_rules = get_model_by_id(config, model_id)
     config_name = f"{brand} {model}"
     scoring: price, mileage, engine, transmission

3. telegram_card_formatter.py:format_car_card_v2()
   ↓
   model_rules = get_model_by_id(config, card["model_id"])
   ↓
   build_price_block_v2(card, config)
   build_score_breakdown_v2(card)
   build_why_passed(card)

4. config_scoring_tester.py (CLI)
   ↓
   config = load_config("results/awd_liquid_full_config.yaml")
   config.validate_config_basic(config)
   ↓
   Для каждой карточки:
     model_id = match_card_to_model(card, config)
     reject_check(card, model_rules, global_rules)
     scoring: price + mileage + engine + transmission + equipment
     decision = get_decision(score, rejected, ...)
```

### Что происходит при ошибке config

| Ошибка | Обработка | Файл |
|--------|-----------|------|
| YAML файл не найден | `FileNotFoundError` → pipeline abort | `run_daily_pipeline.py` |
| YAML невалидный | `yaml.YAMLError` → pipeline abort | `config_loader.py` |
| Модель не найдена | `model_rules = None` → config_name="unknown" | `run_daily_pipeline.py` |
| Нет секции models | `config.get("models", [])` → [] | `config_loader.py` |

### Есть ли валидация?

**✅ Да:** `config_loader.py:validate_config_basic()`

Проверяет:
- Все модели имеют `id`, `name`, `price`, `mileage`
- `engines` секция есть
- `search_groups` consistency (если есть)

---

## 9. Что уже готово

| Элемент | Статус | Доказательство |
|---------|--------|----------------|
| YAML конфиг 17 моделей | ✅ | `config/awd_liquid_full_config.yaml` (1678 строк) |
| Загрузка конфига | ✅ | `config_loader.py:load_config()` |
| lookup model by ID | ✅ | `config_loader.py:get_model_by_id()` |
| config_name в sent_ads | ✅ Колонка есть | `PRAGMA table_info(sent_ads)` |
| config_name в pipeline | ✅ Код есть | `run_daily_pipeline.py:205-211` |
| config_name в telegram_sender | ✅ Код есть | `telegram_sender.py:119-128` |
| config_name в mark_sent | ✅ Код есть | `feedback_store.py:547` |
| Миграция sent_ads | ✅ Код есть | `feedback_store.py:init_db()` |
| Глобальные правила | ✅ | global_reject, global_bonus, global_penalty |
| Scoring rules | ✅ | price/mileage/engine/transmission/equipment scorers |
| ENV файл | ✅ | `.env` с токенами, OWNER_ID, DB_PATH |
| Session state | ✅ | `data/state.json` |
| Auto.ru config | ✅ | `config/auto_ru_searches.yaml` (frozen) |
| Saved search registry | ✅ | `config/saved_searches_8.yaml`, `saved_searches_9.yaml` |

---

## 10. Что не готово

| Элемент | Что нужно | Приоритет |
|---------|-----------|-----------|
| config_name в feedback | ALTER TABLE + update save_feedback() | **HIGH** |
| config_name в card_data | Добавить в card_data_loader.py | **HIGH** |
| config_name в sent_ads data | Задеплоить исправленный код | **HIGH** |
| manager_config | Новая таблица или колонка | MEDIUM |
| Связь manager → config_name | Изменить get_enabled_recipients() | MEDIUM |
| Персональная фильтрация | Изменить pipeline send logic | MEDIUM |
| Валидация конфига | Расширить validate_config_basic() | LOW |
| Config versioning | Версионирование YAML файлов | LOW |
| Config suggestions | После 100+ реакций | LOW |

---

## 11. Риски

| # | Риск | Уровень | Описание |
|---|------|---------|----------|
| 1 | **OWNER_ID hardcoded в 3+ файлах** | MEDIUM | При смене owner — менять везде |
| 2 | **DB_PATH hardcoded в 3 файлах** | MEDIUM | feedback_store, ris_analytics, ris_reason_store — разные пути |
| 3 | **VPS password в vps_*.py** | HIGH | Если пароли не сменены — риск компромитации |
| 4 | **state.json не в .gitignore** | MEDIUM | Сессия браузера может попасть в git |
| 5 | **Дубликат ford_kuga в конфиге** | LOW | Два ford_kuga в full_config — может вызывать путаницу |
| 6 | **Нет config_name в feedback** | HIGH | Невозможна Config Intelligence |
| 7 | **Нет manager_config** | MEDIUM | Все менеджеры получают одинаковые карточки |
| 8 | **ENV файл с токенами** | MEDIUM | Если попадёт в git — токены скомпрометированы |
| 9 | **Нет валидации при загрузке** | LOW | Невалидный конфиг → crash pipeline |
| 10 | **config_name = NULL во всех записях** | HIGH | Код есть, но не закоммичен/не задеплоен |

---

## 12. Требует проверки

| № | Что | Почему |
|---|-----|--------|
| 1 | **VPS: .env файл** | Совпадают ли токены и OWNER_ID с локальными? |
| 2 | **VPS: state.json** | Валидна ли сессия на VPS? |
| 3 | **VPS: config/awd_liquid_full_config.yaml** | Та же версия, что локально? |
| 4 | **Дубликат ford_kuga** | Два ford_kuga в full_config — это баг или intentional? |
| 5 | **VPS password в vps_*.py** | Содержат ли файлы пароли? Сменён ли пароль? |
| 6 | **config_name на VPS sent_ads** | Заполнен ли config_name для новых записей? |
| 7 | **DB_PATH consistency** | feedback_store.py, ris_analytics.py, ris_reason_store.py — все ли используют один путь? |

---

## КРАТКИЙ ОТЧЁТ

| # | Вопрос | Ответ |
|---|--------|-------|
| 1 | Где сейчас список 17 моделей? | `config/awd_liquid_full_config.yaml` (1678 строк) |
| 2 | Есть ли manager_config? | ❌ **Нет** — не существует |
| 3 | Где создаётся config_name? | `run_daily_pipeline.py:step_audit()` и `telegram_sender.py:load_audited_candidates()` |
| 4 | Где config_name теряется? | `card_data_loader.py` → `_save_feedback_for_chat()` → `save_feedback()` → feedback table |
| 5 | Есть ли секреты в коде? | ⚠ Да — OWNER_ID hardcoded, state.json, потенциально VPS passwords в vps_*.py |
| 6 | Есть ли OWNER_ID hardcoded? | ✅ Да — в `feedback_store.py`, `telegram_feedback_bot.py`, `admin_bot/config.py` |
| 7 | Какие конфиги ACTIVE? | `awd_liquid_full_config.yaml`, `awd_liquid_ready_8.yaml`, `awd_liquid_9.yaml`, `auto_ru_searches.yaml` |
| 8 | Что нужно для персональных конфигов? | 1. ALTER TABLE или новая таблица, 2. изменить get_enabled_recipients(), 3. изменить pipeline send logic |
