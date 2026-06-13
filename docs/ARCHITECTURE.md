# Architecture — Haraba Mini

> Дата: 2026-06-13
> Режим: только чтение, без изменений

---

## 1. Краткий вывод

Haraba Mini — это **3-сервисная архитектура** с общей SQLite БД:

| Сервис | Файл | Назначение | Production |
|--------|------|------------|------------|
| **Pipeline** | `run_daily_pipeline.py` | Сбор → Аудит → Отправка карточек | ✅ cron */10 |
| **Feedback Bot** | `telegram_feedback_bot.py` | Реакции менеджеров | ✅ systemd |
| **Admin Bot** | `admin_bot/admin_bot.py` | Управление системой | ✅ systemd |

Общая БД: `results/feedback.db` (9 таблиц, все 3 сервиса пишут/читают).

---

## 2. Точки входа

### 2.1. run_daily_pipeline.py — ОСНОВНАЯ

| Параметр | Значение |
|----------|----------|
| **Путь** | `C:\Users\Admin\haraba-mini\run_daily_pipeline.py` |
| **Назначение** | Orchestrator ежедневного pipeline: collect → enrich → audit → send |
| **Запуск** | `python run_daily_pipeline.py --send` (cron: `*/10 * * * *`) |
| **Production** | ✅ VPS cron с `flock -n /tmp/haraba_pipeline.lock` |
| **Модули** | `session_manager`, `mobile_first_page_sampler.py`, `photo_parser.py`, `telegram_audit.py`, `telegram_sender.py`, `feedback_store.py` |

### 2.2. telegram_feedback_bot.py — FEEDBACK

| Параметр | Значение |
|----------|----------|
| **Путь** | `C:\Users\Admin\haraba-mini\telegram_feedback_bot.py` |
| **Назначение** | Обработка реакций менеджеров (review/think/skip + reasons) |
| **Запуск** | `python telegram_feedback_bot.py` (systemd: `haraba-feedback-bot.service`) |
| **Production** | ✅ VPS systemd |
| **Модули** | `feedback_store.py`, `card_data_loader.py`, `ris_reason_keyboard.py`, `ris_reason_store.py` |

### 2.3. admin_bot/admin_bot.py — ADMIN

| Параметр | Значение |
|----------|----------|
| **Путь** | `C:\Users\Admin\haraba-mini\admin_bot\admin_bot.py` |
| **Назначение** | Админ-панель: менеджеры, статистика, реакции, RIS |
| **Запуск** | `python -m admin_bot.admin_bot` (systemd: `haraba-admin-bot.service`) |
| **Production** | ✅ VPS systemd |
| **Модули** | `admin_bot/config.py`, `admin_bot/handlers/*`, `admin_bot/services/*`, `ris_analytics.py` |

### 2.4. app/runners/run_auto_ru.py — AUTO.RU (ЗАМОРОЖЕН)

| Параметр | Значение |
|----------|----------|
| **Путь** | `C:\Users\Admin\haraba-mini\app\runners\run_auto_ru.py` |
| **Назначение** | CLI runner Auto.ru scraper |
| **Запуск** | `python -m app.runners.run_auto_ru --debug --limit 10 --no-send` |
| **Production** | ❌ ЗАМОРОЖЕН (100% CAPTCHA) |

### 2.5. CLI-only (не production)

| Файл | Назначение |
|------|------------|
| `telegram_sender.py` | Отправка карточек (вызывается pipeline как subprocess) |
| `telegram_audit.py` | Аудит кандидатов (вызывается pipeline) |
| `mobile_first_page_sampler.py` | Сбор карточек (вызывается pipeline как subprocess) |
| `apply_all_searches_17.py` | Активация 17 поисков (вызывается sampler) |
| `config_scoring_tester.py` | Тестирование скоринга (CLI) |
| `feedback_export.py` | Экспорт feedback (CLI) |
| `feedback_report.py` | Аналитика реакций (CLI) |

---

## 3. Основной pipeline

### Фактическая цепочка

```
cron */10
  ↓
run_daily_pipeline.py --send
  ↓
step_check_searches()  → session_manager.check_session_status()
  ↓
step_collect_cards()   → subprocess: mobile_first_page_sampler.py --limit 30
  ↓                      output: results/latest_cards_raw.json
step_enrich_cards()    → photo_parser.enrich_cards_with_photos()
  ↓                      output: results/latest_cards_enriched.json
step_audit()           → telegram_audit (region/legal/scoring)
  ↓                      output: results/latest_cards_audited.json
step_send()            → subprocess: telegram_sender.py --send
  ↓                      output: results/telegram_sender_report.yaml
step_feedback_count()  → feedback_store.get_feedback_all()
  ↓
save_daily_report()    → results/daily_pipeline_report.yaml
```

---

## 4. Haraba data flow

### Подробный разбор каждого шага

#### Шаг 1: Запуск pipeline

| Параметр | Значение |
|----------|----------|
| Файл | `run_daily_pipeline.py:main()` |
| Вход | CLI args: `--send`, `--dry-run`, `--limit N` |
| Выход | Pipeline context (results dict) |

#### Шаг 2: Проверка сессии

| Параметр | Значение |
|----------|----------|
| Файл | `run_daily_pipeline.py:step_check_searches()` |
| Функция | `session_manager.check_session_status()` |
| Вход | `data/state.json` (файл сессии) |
| Выход | `"VALID"` / `"EXPIRED"` / `"MISSING"` |
| Поля карточки | — |

#### Шаг 3: Сбор карточек

| Параметр | Значение |
|----------|----------|
| Файл | `mobile_first_page_sampler.py:main()` |
| Вызов | `subprocess.run([...], timeout=600)` |
| Вход | `--limit 30` |
| Выход | `results/latest_cards_raw.json` |

**Поля карточки (на выходе):**
```json
{
  "card_id": "173324131",           // ← ИЗВЛЕЧЁН из URL (id=...)
  "source": "auto.ru",
  "model_guess": "Hyundai",
  "title": "Hyundai Santa Fe",
  "year": 2014,
  "price": 2000000,
  "mileage": 104795,
  "url": "https://haraba.ru/common/click?id=173324131&source=1",
  "mobile_url": "https://m.haraba.ru/search/car/173324131",
  "raw_text": "...",
  "specs": {},                      // ← пусто на этом этапе
  "mobile_detail_raw_text": "",
}
```

**Как появляется card_id:** `mobile_first_page_sampler.py:parse_cards_from_rows()` — regex `id=(\d+)` из href ссылки.

#### Шаг 4: Enrichment (фото)

| Параметр | Значение |
|----------|----------|
| Файл | `run_daily_pipeline.py:step_enrich_cards()` |
| Функция | `photo_parser.enrich_cards_with_photos()` |
| Вход | `latest_cards_raw.json` |
| Выход | `latest_cards_enriched.json` |

**Поля добавляются:** `photo_url`, `photo_count`, `photos` (main_photo_url, gallery)

#### Шаг 5: Аудит (hard-stop + scoring)

| Параметр | Значение |
|----------|----------|
| Файл | `run_daily_pipeline.py:step_audit()` |
| Функции | `check_region_allowed()`, `check_legal_restrictions()`, scorers |
| Вход | `latest_cards_enriched.json` |
| Выход | `latest_cards_audited.json` |

**Поля добавляются:**
- `model_id` — через `match_card_to_model()`
- `config_name` — `f"{brand} {model}"` (line 205-211) ✅
- `score`, `decision` — через scoring pipeline
- `price_score`, `mileage_score`, `engine_score`, `transmission_score`, `equipment_score`
- `bonus_reasons`, `penalty_reasons`
- `action` — `send_ready` / `hold_manual_review` / `do_not_send`

#### Шаг 6: Telegram отправка

| Параметр | Значение |
|----------|----------|
| Файл | `telegram_sender.py:run_send()` |
| Вызов | `subprocess.run([...], timeout=300)` |
| Вход | `latest_cards_audited.json` → копируется в `telegram_candidates_audited.json` |
| Выход | `telegram_sender_report.yaml` |

**Подшаги:**
1. `load_audited_candidates()` — загрузка + enrich из sample → **config_name пересчитывается** (line 119-128)
2. `get_enabled_recipients()` — список active менеджеров
3. Для каждого recipient → для каждой карточки:
   - `check_dedup_with_chat_id(card, chat_id)` → new/same_price/price_drop/price_increased
   - `send_car_card_sync()` → Telegram API
   - `mark_sent_with_chat_id(card, chat_id)` → **config_name записывается** (line 547)

#### Шаг 7: Запись sent_ads

| Параметр | Значение |
|----------|----------|
| Файл | `feedback_store.py:mark_sent_with_chat_id()` |
| Таблица | `sent_ads` |
| PK | `(stable_car_key, chat_id)` |

**Поля записываются:** stable_car_key, chat_id, card_id, url, mobile_url, haraba_id, title, model_id, year, price, mileage, region, first_sent_at, last_seen_at, last_sent_at, send_count, source, external_id, brand, model, engine, transmission, drive, owners, Auto.ru поля, final_verdict, final_score, final_reasons_json, raw_json, sent_at, **config_name**

---

## 5. Card identity: card_id / stable_car_key

### card_id

| Где появляется | Формат | Источник |
|----------------|--------|----------|
| `mobile_first_page_sampler.py` | `"173324131"` (string digits) | Regex `id=(\d+)` из href |
| `latest_cards_raw.json` | `"173324131"` | scraper output |
| `latest_cards_audited.json` | `"173324131"` | passed through |
| `telegram_candidates_audited.json` | `"173324131"` | copied |
| `card_data_loader.py` | `"173324131"` | lookup key |
| `telegram_sender.py` | `"173324131"` | callback_data: `review:173324131` |
| `telegram_feedback_bot.py` | `"173324131"` | parsed from callback |
| `feedback` table | `"173324131"` | card_id TEXT |
| `sent_ads` table | `"173324131"` | card_id TEXT |

### stable_car_key

| Где формируется | Формат | Файл:строка |
|-----------------|--------|-------------|
| `_build_stable_key()` | `"id:173324131"` | `feedback_store.py:36-56` |
| dedup check | `"id:173324131"` | `feedback_store.py:check_dedup_with_chat_id()` |
| sent_ads PK | `"id:173324131"` | INSERT в sent_ads |

**Логика формирования (_build_stable_key):**
```python
def _build_stable_key(card):
    card_id = card.get("card_id", "")
    if card_id:
        return "id:" + card_id           # ← PRIORITITY 1 (основной путь)

    url = card.get("mobile_url", "") or card.get("url", "")
    haraba_id = _extract_haraba_id(url)  # regex [?&]id=(\d+)
    if haraba_id:
        return "haraba:" + haraba_id     # ← PRIORITITY 2

    # Fallback: title+year+price+mileage+region
    return "fallback:" + f"{title}_{year}_{price}_{mileage}_{region}"
```

### Одинаково ли используется в sent_ads и feedback?

| Таблица | stable_car_key | card_id |
|---------|---------------|---------|
| `sent_ads` | ✅ Есть (часть PK) | ✅ Есть |
| `feedback` | ❌ **Нет** | ✅ Есть |

**Риск:** feedback НЕ имеет stable_car_key. Связь feedback ↔ sent_ads только по `card_id`.

### Риски stable_car_key

| Риск | Вероятность | Описание |
|------|-------------|----------|
| Одна машина → разные ключи | ❌ Низкая | card_id всегда извлекается из одного URL → один key |
| Разные машины → один ключ | ❌ Низкая | card_id = haraba_id, уникален для каждой карточки |
| Fallback key collision | ⚠ Средняя | Если card_id пустой и haraba_id пустой → fallback по title+year+price — возможны совпадения |

**Проверка перед изменениями:** Убедиться что `card_id` всегда заполнен в mobile_first_page_sampler.py.

---

## 6. config_name flow

### Таблица потока config_name

| Шаг | Файл | Функция | Есть config_name? | Статус | Комментарий |
|-----|------|---------|-------------------|--------|-------------|
| 1. Аудит карточки | `run_daily_pipeline.py` | `step_audit()` | ✅ Устанавливается | ✅ Код есть (modified) | Line 205-211: `c["config_name"] = f"{brand} {model}"` |
| 2. audited JSON | `latest_cards_audited.json` | — | ✅ Записан | ✅ Работает | JSON содержит config_name |
| 3. Load candidates | `telegram_sender.py` | `load_audited_candidates()` | ✅ Пересчитывается | ✅ Код есть (modified) | Line 119-128: fallback расчёт |
| 4. card_data | `card_data_loader.py` | `load_card_data()` | ❌ **НЕ загружается** | ❌ **НЕ СДЕЛАНО** | Dict cards не включает config_name |
| 5. pending_feedback | `telegram_feedback_bot.py` | `button_handler()` | ❌ Нет в card_data | ❌ Передаётся как есть | card_data не имеет config_name |
| 6. feedback_card | `telegram_feedback_bot.py` | `_save_feedback_for_chat()` | ❌ **НЕ включается** | ❌ **НЕ СДЕЛАНО** | feedback_card dict не содержит config_name |
| 7. save_feedback | `feedback_store.py` | `save_feedback()` | ❌ Нет параметра | ❌ **НЕ СДЕЛАНО** | INSERT: 32 параметра, config_name нет |
| 8. feedback table | `results/feedback.db` | — | ❌ **Нет колонны** | ❌ **НЕ СДЕЛАНО** | 32 колонны, config_name отсутствует |
| 9. sent_ads | `feedback_store.py` | `mark_sent_with_chat_id()` | ✅ Записывается | ✅ Код есть (modified) | Line 547: `card.get("config_name", "unknown")` |
| 10. sent_ads table | `results/feedback.db` | — | ✅ Колонка есть | ✅ Миграция есть | Но все 10 записей = NULL |

### Что уже сделано, но не закоммичено

| Файл | Изменение | Статус |
|------|-----------|--------|
| `run_daily_pipeline.py` | step_audit() устанавливает config_name | modified, not committed |
| `telegram_sender.py` | load_audited_candidates() пересчитывает config_name | modified, not committed |
| `feedback_store.py` | mark_sent_with_chat_id() записывает config_name | modified, not committed |
| `feedback_store.py` | init_db() миграция: ADD COLUMN config_name | modified, not committed |

### Что ещё не сделано

| Файл | Что нужно |
|------|-----------|
| `feedback.db` | `ALTER TABLE feedback ADD COLUMN config_name TEXT` |
| `card_data_loader.py` | Добавить `"config_name": c.get("config_name", "")` |
| `telegram_feedback_bot.py` | `_save_feedback_for_chat()` → добавить config_name |
| `feedback_store.py` | `save_feedback()` → добавить config_name в INSERT |

---

## 7. Telegram send flow

```
telegram_sender.py:run_send()
  ↓
  load_audited_candidates()
    ↓ audited JSON + mobile sample → enriched cards
  get_enabled_recipients()
    ↓ [{chat_id, username, first_name, role}]
  for each card:
    for each recipient:
      ↓
      check_dedup_with_chat_id(card, chat_id)
        ↓ new / same_price / price_drop / price_increased
      ↓
      if new or price_drop:
        prepare_card_text(card, config)
          ↓ telegram_card_formatter.format_car_card_v2()
        build_inline_keyboard(card_id)
          ↓ callback_data: "review:{card_id}", "think:{card_id}", "skip:{card_id}"
        send_car_card_sync(bot_token, chat_id, card, config)
          ↓ HTTPXRequest (90s timeout)
          ↓ send_photo or send_message
        ↓
        if success:
          mark_sent_with_chat_id(card, chat_id, status)
            ↓ INSERT INTO sent_ads (38 колонок)
        if fail:
          log error, retry as text message
  ↓
  telegram_sender_report.yaml
```

### Где форматируется карточка

| Этап | Файл | Функция |
|------|------|---------|
| Форматирование | `telegram_card_formatter.py` | `format_car_card_v2()` |
| Подготовка текста | `telegram_sender.py` | `prepare_card_text()` |
| Клавиатура | `telegram_sender.py` | `build_inline_keyboard()` |

### Где сохраняется факт отправки

| Файл | Функция | Таблица |
|------|---------|---------|
| `feedback_store.py` | `mark_sent_with_chat_id()` | `sent_ads` |

### Где обрабатываются ошибки Telegram

`telegram_sender.py:send_car_card_async()`:
1. Primary: `send_photo()` — если фото доступно
2. Fallback 1: `send_message()` — если фото не скачалось
3. Fallback 2: `send_message()` с обрезанным текстом — если текст > 4000 chars
4. Если все fallback'и failed → `failed += 1`, карточка НЕ записывается в sent_ads

### Что происходит при ошибке отправки

- Карточка НЕ записывается в sent_ads (dedup не срабатывает)
- При следующем запуске pipeline карточка будет отправлена снова
- Error логируется в `results/daily_pipeline.log`

---

## 8. Feedback flow

```
Telegram callback: "review:171156820"
  ↓
telegram_feedback_bot.py:button_handler()
  ↓ parse: action="review", card_id="171156820"
  ↓ card_data = card_data_loader.get(card_id)
  ↓ pending_feedback[chat_id] = {card_id, action, card_data}
  ↓
reason_keyboard(action) → inline кнопки причин
  ↓
telegram_feedback_bot.py:reason_handler()
  ↓ parse: reason_code="good_price"
  ↓ pending_reason[chat_id] = "good_price"
  ↓
telegram_feedback_bot.py:text_handler() (если комментарий)
  ↓ comment = update.message.text
  ↓
_save_feedback_for_chat(chat_id, pending, user)
  ↓ feedback_card dict (30+ полей, БЕЗ config_name)
  ↓ save_feedback(feedback_card, action, comment)
    ↓ INSERT INTO feedback (32 колонны)
  ↓
get_last_feedback_id() → N
  ↓ save_reaction_detail(N, reason_code)
    ↓ INSERT INTO reaction_details (feedback_id=N, reason_code)
```

---

## 9. Database write points

### Кто пишет в какие таблицы

| Таблица | Пишет | Файл:функция |
|---------|-------|-------------|
| `sent_ads` | Pipeline | `feedback_store.py:mark_sent_with_chat_id()` |
| `feedback` | Feedback Bot | `feedback_store.py:save_feedback()` |
| `telegram_users` | Feedback Bot + Admin Bot | `feedback_store.py:upsert_telegram_user()`, `register_recipient()` |
| `telegram_recipients` | Legacy | `feedback_store.py:init_db()` (migration) |
| `pipeline_runs` | Никто | 0 строк (pipeline пишет в YAML, не в БД) |
| `reaction_reasons` | Migration | `ris_migration.py` (27 записей) |
| `reaction_details` | Feedback Bot | `ris_reason_store.py:save_reaction_detail()` |
| `learning_rules` | Никто | 0 строк (ещё не генерировались) |

---

## 10. Где теряются данные

| Поле | Где появляется | Где теряется | Почему |
|------|---------------|-------------|--------|
| **config_name** | `step_audit()` → audited JSON | `card_data_loader.py` | Не включается в dict cards |
| **config_name** | card_data (если бы был) | `_save_feedback_for_chat()` | Не включается в feedback_card |
| **config_name** | feedback_card (если бы был) | `save_feedback()` | Нет параметра в INSERT |
| **config_name** | save_feedback (если бы был) | feedback table | Нет колонны |
| **stable_car_key** | `mark_sent_with_chat_id()` | card_data | Не передаётся в feedback bot |
| **stable_car_key** | card_data | feedback_card | Не включается |
| **model_id** | audited JSON | card_data | ✅ Загружается (есть в card_data_loader) |
| **score breakdown** | audited JSON | card_data | ✅ Загружается |
| **config_name** | sent_ads | feedback | Нет JOIN, нет общей связи |

---

## 11. Риски архитектуры

| # | Риск | Уровень | Описание |
|---|------|---------|----------|
| 1 | **Нет config_name в feedback** | HIGH | Невозможно Config Intelligence без миграции + 4 файлов |
| 2 | **14 modified файлов не закоммичены** | HIGH | VPS может иметь старую версию кода |
| 3 | **card_data_loader не загружает config_name** | HIGH | Audited JSON содержит config_name, loader пропускает |
| 4 | **Нет FK между feedback и sent_ads** | MEDIUM | Связь только по card_id (текст), нет CASCADE |
| 5 | **pipeline_runs = 0 строк** | LOW | Pipeline не пишет логи в БД — только YAML |
| 6 | **sent_ads.db и dedup_store.db — мертвые файлы** | LOW | 0 строк, не используются, но занимают место |
| 7 | **telegram_recipients рассинхрон** | LOW | Legacy таблица inconsistent с telegram_users |
| 8 | **No rollback strategy** | MEDIUM | Если миграция ALTER TABLE сломается — нет backup плана |
| 9 | **Single shared DB** | MEDIUM | 3 сервиса пишут в одну БД — риск concurrent writes (но SQLite serializes) |
| 10 | **card_id parsing fragility** | LOW | Если Haraba изменит URL format — card_id может стать пустым → fallback key |

---

## 12. ASCII-схема

```
┌─────────────────────────────────────────────────────────────────┐
│                    CRON: */10 (flock)                           │
│                    run_daily_pipeline.py --send                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
│ step_check_      │ │ step_collect_    │ │ step_enrich_         │
│ searches()       │ │ cards()          │ │ cards()              │
│                  │ │                  │ │                      │
│ session_manager. │ │ subprocess:      │ │ photo_parser.        │
│ check_session_   │ │ mobile_first_    │ │ enrich_cards_        │
│ status()         │ │ page_sampler.py  │ │ with_photos()        │
│                  │ │ --limit 30       │ │                      │
│ Input: state.json│ │                  │ │ Input: raw JSON      │
│ Output: VALID    │ │ Output: raw JSON │ │ Output: enriched JSON│
└──────────────────┘ └──────────────────┘ └──────────────────────┘
                            │                       │
                            ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                        step_audit()                              │
│  run_daily_pipeline.py:step_audit()                              │
│                                                                  │
│  check_region_allowed() ─→ reject if not allowed                 │
│  check_legal_restrictions() ─→ reject if restricted             │
│  match_card_to_model() ─→ model_id                               │
│  config_name = f"{brand} {model}"  ← ✅ ЗДЕСЬ ПОЯВЛЯЕТСЯ        │
│  score_price() + score_mileage() + score_engine() + ...          │
│                                                                  │
│  Input:  enriched JSON                                           │
│  Output: audited JSON (send_ready / hold / do_not_send)          │
│  Fields: card_id, model_id, config_name, score, decision, ...   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        step_send()                               │
│  subprocess: telegram_sender.py --send                           │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ load_audited_candidates()                                  │ │
│  │   → enrich from mobile_first_page_sample.json              │ │
│  │   → config_name пересчитывается ← ✅                        │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ get_enabled_recipients()                                   │ │
│  │   → SELECT FROM telegram_users WHERE status='active'       │ │
│  │   → [{chat_id, username, first_name, role}]                │ │
│  │   ← ❌ NO config_name                                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ for card in candidates:                                    │ │
│  │   for recipient in recipients:                             │ │
│  │     check_dedup_with_chat_id(card, chat_id)                │ │
│  │     prepare_card_text(card, config)                        │ │
│  │       → format_car_card_v2()                               │ │
│  │     build_inline_keyboard(card_id)                         │ │
│  │       → "review:{card_id}", "think:{card_id}", "skip:..."  │ │
│  │     send_car_card_sync(bot_token, chat_id, card, config)   │ │
│  │       → send_photo or send_message                         │ │
│  │     mark_sent_with_chat_id(card, chat_id)                  │ │
│  │       → INSERT INTO sent_ads (38 cols)                     │ │
│  │       → config_name записывается ← ✅                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Output: telegram_sender_report.yaml                             │
│  DB:     sent_ads (stable_car_key + chat_id PK)                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TELEGRAM API                                │
│  Message sent to manager with inline buttons                     │
│  [👀 Посмотреть] [🤔 Подумать]                                   │
│  [⏭ Скип] [📖 Описание] [📷 Ещё фото]                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              telegram_feedback_bot.py (systemd)                  │
│                                                                  │
│  button_handler(): callback="review:171156820"                   │
│    → parse: action, card_id                                      │
│    → card_data = card_data_loader.get(card_id)                   │
│      ← ❌ card_data НЕ содержит config_name                      │
│    → pending_feedback[chat_id] = {action, card_id, card_data}    │
│    → reason_keyboard(action)                                     │
│                                                                  │
│  reason_handler(): callback="reason:good_price"                  │
│    → reason_code = "good_price"                                  │
│    → pending_reason[chat_id] = "good_price"                      │
│                                                                  │
│  text_handler(): comment = "хорошая цена"                        │
│    → _save_feedback_for_chat()                                   │
│      → feedback_card dict (30+ полей)                            │
│        ← ❌ НЕТ config_name                                      │
│        ← ❌ НЕТ stable_car_key                                   │
│      → save_feedback(feedback_card, action, comment)             │
│        → INSERT INTO feedback (32 колонны)                       │
│      → get_last_feedback_id() → N                                │
│      → save_reaction_detail(N, reason_code)                      │
│        → INSERT INTO reaction_details                            │
│                                                                  │
│  DB: feedback (32 cols), reaction_details                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13. Требует проверки

| № | Что | Почему |
|---|-----|--------|
| 1 | **VPS код vs локальный** | 14 modified файлов — VPS может иметь старую версию без config_name fix |
| 2 | **config_name на VPS sent_ads** | Заполнен ли config_name для новых записей после последнего deploy? |
| 3 | **pipeline_runs = 0** | Pipeline логи пишутся только в YAML — это intentional или oversight? |
| 4 | **card_data_loader на VPS** | Содержит ли VPS версия card_data_loader.py config_name? |
| 5 | **concurrent write safety** | 3 сервиса пишут в одну SQLite — есть ли риск corruption при overlap? |
| 6 | **stable_car_key fallback** | Когда срабатывает fallback key? Есть ли записи с `fallback:` префиксом? |

---

## КРАТКИЙ ОТЧЁТ

| # | Вопрос | Ответ |
|---|--------|-------|
| 1 | Главная точка входа pipeline? | `run_daily_pipeline.py:main()` — cron */10 |
| 2 | Где создаётся audited JSON? | `run_daily_pipeline.py:step_audit()` → `results/latest_cards_audited.json` |
| 3 | Где теряется config_name? | 3 точки: `card_data_loader.py` → `_save_feedback_for_chat()` → `save_feedback()` |
| 4 | Где работает dedup? | `feedback_store.py:check_dedup_with_chat_id()` — per-manager, PK `(stable_car_key, chat_id)` |
| 5 | Где записывается sent_ads? | `feedback_store.py:mark_sent_with_chat_id()` → `sent_ads` таблица |
| 6 | Где записывается feedback? | `feedback_store.py:save_feedback()` → `feedback` таблица |
| 7 | 5 критичных файлов pipeline? | 1. `run_daily_pipeline.py`, 2. `telegram_sender.py`, 3. `feedback_store.py`, 4. `mobile_first_page_sampler.py`, 5. `telegram_feedback_bot.py` |
| 8 | Какие изменения опасны? | ALTER TABLE feedback, изменение save_feedback() сигнатуры, изменение stable_car_key логики, изменение PK sent_ads |
