# Haraba — Прогресс

## Статус: ✅ Phase 1 завершён, 🔄 Phase 2 (Telegram v1) в работе

---

## Phase 2 — Telegram v1 + Feedback Loop

### Блок 12 — Сбор свежих карточек (mobile_first_page_sampler.py)
- ✅ 30 карточек собраны из 17 активных поисков Haraba
- ✅ mobile detail парсинг: engine, transmission, drive, region, owners, autoteka
- ✅ Coverage: engine 100%, transmission 100%, drive 100%, owners 100%, region 70%, autoteka 73%
- ✅ Файлы: `results/mobile_first_page_sample.json`, `results/mobile_details_cache_17.json`

### Блок 15 — Аудит Telegram-кандидатов (telegram_audit.py)
- ✅ 16 кандидатов: 6 send_ready + 10 hold_manual_review + 0 do_not_send
- ✅ Проверки: region, legal, transmission, drive, completeness, score_explanation
- ✅ Файл: `results/telegram_candidates_audited.json`

### Блок 16 — Telegram Sender v1 + Feedback Bot
- ✅ telegram_sender.py — отправка карточек с inline кнопками
- ✅ telegram_card_formatter.py — формат карточки v1 (модель/год/цена/регион/пробег/двигатель/коробка/привод/оценка)
- ✅ telegram_feedback_bot.py — обработка 🟢🟡🔴 + комментарии с reply_to_message_id
- ✅ feedback_store.py — SQLite: sent_ads + feedback таблицы
- ✅ feedback_export.py — экспорт feedback за N дней
- ✅ card_data_loader.py — загрузка полных данных карточек (engine/transmission/drive/region/owners)
- ✅ .env создан с TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID
- ✅ Mobile URL для ссылок в Telegram (desktop ссылки не работали)
- ✅ Dedup работает (повторно не отправляет)
- ✅ 3 тестовые реакции сохранены в feedback.db

---

## Phase 1 — Search Builder (ЗАВЕРШЁН)
- ✅ `state.json` из haraba_bot
- ✅ `check_session.py` / `login.py` / `refresh_session.py`

### Блок 2 — Чтение конфига 8 моделей
- ✅ `config/awd_liquid_ready_8.yaml` — 8 моделей
- ✅ `SearchConfig` dataclass
- ✅ `load_searches()` / `get_model_by_id()`

### Блок 3 — Price margin ±50 000
- ✅ `price_from_real = max(0, price_from - 50000)`
- ✅ `price_to_real = price_to + 50000`
- ✅ `ExpandedSearchConfig` dataclass

### Блок 4 — Выставление фильтров
- ✅ `apply_filters_from_expanded_config()` — brand, model, year, price
- ✅ JS клик через `button.mat-warn[aria-haspopup='menu']`
- ✅ Сценарий 1: галочки стоят → снять все → фильтр появился
- ✅ Сценарий 2: галочек нет → повторный клик → фильтр появился

### Блок 5 — Сохранение одного поиска
- ✅ `save_current_search()` — диалог сохранения
- ✅ `check_search_exists()` — через registry (не через dropdown)
- ✅ Registry обновление при сохранении

### Блок 6 — Registry сохранённых поисков
- ✅ `config/saved_searches_8.yaml`
- ✅ `load_registry()` / `save_registry()`
- ✅ `upsert_registry_success()` / `upsert_registry_failed()`
- ✅ `should_skip_search()` — skip saved, retry failed
- ✅ `--force` — пересоздать все
- ✅ `--only <id>` — один поиск

### Блок 7 — Прогон всех 8 моделей
- ✅ `run_saved_searches_8.py`
- ✅ `ensure_filters_visible_once()` — ОДИН РАЗ при старте
- ✅ Ошибка одного поиска → остальные продолжаются
- ✅ Dry-run режим
- ✅ SUMMARY: Total/Saved/Skipped/Failed

### Блок 8 — Применение всех поисков
- ✅ В конце `run_saved_searches_8.py` — проверка галочек
- ✅ Если хотя бы одна не стоит → поставить все → применить
- ✅ Подсчёт результатов (tr.mat-row)

### Блок 9 — Дополнительные фильтры
- ✅ **Пробег до** (mileage_max) — `#srch_fltr_mileage_to`
- ✅ **КПП** (transmission) — `#srch_fltr_transmission`, мульти-выбор:
  - Автомат → "Автомат"
  - DSG → "Робот"
  - CVT → "Вариатор"
  - Manual → "Механика"
- ✅ **Регионы** (7): Москва и МО, Ярославская обл., Тверская обл., Владимирская обл., Калужская обл., Рязанская обл., Тульская обл.
- ✅ **Привод** (drivetrain) → "Полный"
- ✅ **Ограничения** → "Без ограничения" (ед. число, не мн.)
- ✅ **Продавец** → "Частник"
- ✅ **Владельцы** → "1-3"
- ✅ **Состояние** → "Кроме битых"

---

## Отказанные решения

### 1. Проверка поиска через dropdown "Мои поиски"
- ❌ Отказано: dropdown нестабилен, overlay блокирует, mat-list-option = 0
- ✅ Заменено на: `check_search_exists()` через registry

### 2. Удаление дубликатов через /search/my-searches карточки
- ❌ Отказано: нет `mat-card` селекторов, структура SPA не совпадает
- ✅ Заменено на: ручное удаление + `check_search_exists()` предотвращает дубли

### 3. Переоткрытие фильтра перед каждым поиском
- ❌ Отказано: браузер закрывается после 2-3 циклов
- ✅ Заменено на: `ensure_filters_visible_once()` — ОДИН РАЗ при старте

### 4. Верификация каждого поиска отдельно
- ❌ Отказано: `verify_saved_search()` через dropdown нестабилен
- ✅ Заменено на: единый `verify_saved_searches_8.py` — проверка галочек + results_count

### 5. Scoring и Telegram уведомления
- ❌ Отказано (не входит в scope Search Builder)
- 📋 Запланировано: отдельный модуль

### 6. Парсинг детальных карточек
- ❌ Отказано (не входит в scope Search Builder)
- 📋 Запланировано: отдельный модуль

---

## Ключевые файлы

| Файл | Назначение |
|------|------------|
| `config/awd_liquid_ready_8.yaml` | Конфиг 8 моделей с доп. фильтрами |
| `config_loader_8.py` | Загрузка YAML → SearchConfig |
| `search_expander_8.py` | Price margin → ExpandedSearchConfig |
| `apply_filters_8.py` | Применение фильтров к Haraba UI |
| `filters_block9.py` | Дополнительные фильтры (Блок 9) |
| `saved_search_helper_8.py` | Сохранение и проверка поисков |
| `registry_8.py` | Registry: saved/failed/skip logic |
| `run_saved_searches_8.py` | Главный runner (все 8) |
| `verify_saved_searches_8.py` | Проверка всех сохранённых |

---

## Результаты

| Метрика | Значение |
|---------|----------|
| Поисков создано | 8/8 |
| Verified | 8/8 |
| Failed | 0 |
| Дубликатов | 0 |
| Results per search | 30 |
| Тестов пройдено | 114+ |

---

## Формат registry (config/saved_searches_8.yaml)

```yaml
saved_searches:
  ford_kuga:
    id: ford_kuga
    save_name: "Ford Kuga 2013-2018"
    status: saved
    verify_status: verified
    results_count: 30
    verify_error: null
    verified_at: "2026-06-07 22:41:56"
    updated_at: "2026-06-07 22:41:07"
```

---

## Команды запуска

```bash
# Создать все 8 поисков
python run_saved_searches_8.py

# Пересоздать все
python run_saved_searches_8.py --force

# Один поиск
python run_saved_searches_8.py --only ford_kuga

# Dry-run
python run_saved_searches_8.py --dry-run

# Проверить все
python verify_saved_searches_8.py
```
