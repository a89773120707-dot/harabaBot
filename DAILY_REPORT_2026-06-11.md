# Daily Report: 2026-06-11

## Тема: Auto.ru интеграция — полный pipeline

---

## ✅ ЧТО СДЕЛАНО СЕГОДНЯ

### Этап 1-2: Структура + Парсинг выдачи
- Создана структура `app/sources/auto_ru/` (11 файлов)
- Persistent Chrome профиль для Auto.ru (`persistent_browser.py`)
- Парсинг выдачи: brand, model, year, price, mileage, region
- **Баг цены починен** — фильтр склейки ext_id с ценой
- **Китайские бренды добавлены** — MG, Chery, Haval, FAW, Dongfeng, Geely и др.
- **Overlay фильтр** — "Ещё 6 фото" и подобные строки убираются

### Этап 3: Detail Page Parser
- `parser.py` — parse_detail_page() извлекает:
  - engine (полное описание + volume/power/fuel)
  - transmission, drive, owners, seller_type
  - description, region, VIN, PTS, configuration
- Покрытие на реальных данных: engine 4/4, transmission 4/4, drive 4/4, owners 4/4

### Этап 4: Matcher
- `app/matcher/auto_ru_matcher.py` — фильтрация по brand/model/year/price/drive/region
- `config/auto_ru_searches.yaml` — 5 поисков (Kia Rio, Ford Kuga, Geely Atlas, Honda Freed, Suzuki Swift)
- Тест на 19 карточках: 4 matched, 15 rejected по brand

### Этап 5: Price Analyzer + Score Aggregator
- `app/analyzer/price_analyzer.py` — MVP v2: использует текстовый статус Auto.ru
- `app/analyzer/score.py` — агрегатор существующих скореров (price, mileage, engine, transmission, equipment)
- `app/analyzer/internal_price_analysis.py` — отдельная оценка из YAML-конфига

### Этап 6: Valuation Page Parser (КЛЮЧЕВОЙ)
- `app/sources/auto_ru/valuation_page_parser.py` — парсинг диапазона оценки с отдельной страницы
- URL: `https://auto.ru/evaluation/cars/?offer_id=<external_id>&utm_source=card_offer`
- Извлекает: low, high, estimate_mid (среднее), status, delta_percent
- **Результат**: 3/4 машин получили полный диапазон оценки

### Этап 7: Final Price Decision Engine
- `app/analyzer/final_price_decision.py` — итоговый вердикт для закупщика
- 5 уровней: excellent_deal → good_deal → fair_price → slightly_overpriced → strong_overpriced
- Объединяет Auto.ru диапазон + YAML конфиг
- Пример: Ford Kuga 1.8 млн → ❌ Сильно выше рынка (+380к к Auto.ru high)

### Этап 8: SQLite Integration
- `app/database/migrations.py` — 21 новая колонка в sent_ads + unique index
- `app/database/auto_ru_repo.py` — map_auto_ru_card_to_db(), save_auto_ru_card()
- Dedup работает: UPDATE существующих, INSERT новых, 0 дублей
- raw_json содержит полную карточку + decision

### Этап 9: Telegram Formatter + Dry Run
- `app/telegram/auto_ru_formatter.py` — формат карточки для Telegram
- `test_auto_ru_formatter.py` — тест на карточках из SQLite
- `test_auto_ru_telegram_dry_run.py` — Dry Run без отправки
- Превью сохранено: `results/debug/telegram_preview.txt`

### Этап 10: Full Pipeline Test (5 авто)
- Видимый браузер, ручной проход CAPTCHA
- 4 из 5 успешно:
  - **Honda Stepwgn** 2021 | 1.85 млн | Auto.ru: 2.03–2.33 млн | 🔥 Отличная сделка
  - **Kia Seltos** 2026 | 1.95 млн | Auto.ru: 1.27–1.33 млн | ❌ Сильно выше рынка
  - **Chevrolet Orlando** 2023 | 1.52 млн | Auto.ru: 1.65–1.84 млн | 🔥 Отличная сделка
  - **Hyundai Creta** 2021 | 1.75 млн | Auto.ru: 1.75–1.91 млн | 🔥 Отличная сделка
- 1 CAPTCHA (20%)

---

## ❌ ПРОБЛЕМЫ

### 1. Собираем НЕ те авто
- Сейчас: любые авто из общей выдачи
- Нужно: ТОЛЬКО 17 моделей из `awd_liquid_full_config.yaml`
- Ford Kuga, Kia Sorento, Kia Sportage, Mazda CX-5, Nissan X-Trail, и т.д.

### 2. CAPTCHA 20-60%
- Persistent профиль помогает, но не полностью
- При частых запросах Auto.ru показывает "Вы не робот?"
- В видимом браузере можно пройти вручную

### 3. Valuation не всегда находится
- Honda Freed: статус "ниже оценки" найден, но диапазон — нет
- Suzuki Swift: диапазон найден, но статус — unknown
- Причина: разные форматы страницы оценки для разных авто

---

## 📊 СТАТИСТИКА

| Метрика | Значение |
|---------|----------|
| Файлов создано | 25+ |
| Модулей | 5 (sources, matcher, analyzer, database, telegram) |
| Unit тестов | 19/19 passed |
| Записей в БД | 7 (3 старых + 4 новых) |
| CAPTCHA блокировок | 3-6 из 10 запросов |
| Valuation найден | 3/4 (75%) |
| Final decision | 4/4 (100% когда есть данные) |
| Dedup работает | ✅ 0 дублей |

---

## ⏭️ ЧТО ОСТАЛОСЬ

| # | Задача | Приоритет |
|---|--------|-----------|
| 1 | Создать Auto.ru поиски по 17 моделям из конфига | 🔴 КРИТИЧНО |
| 2 | Собирать авто ТОЛЬКО из этих поисков | 🔴 КРИТИЧНО |
| 3 | Real Telegram Send — отправка excellent/good сделок | 🟡 ВАЖНО |
| 4 | CAPTCHA mitigation — увеличить delay или уменьшить batch | 🟡 ВАЖНО |
| 5 | Интеграция в daily pipeline | 🟢 ПОТОМ |

---

## 📁 СОЗДАННЫЕ ФАЙЛЫ (25+)

### app/sources/auto_ru/
- `browser.py` — Playwright browser/context
- `persistent_browser.py` — Persistent Chrome профиль
- `scraper.py` — скрапинг search page
- `parser.py` — parse_detail_page()
- `full_card_parser.py` — полный pipeline (detail + valuation)
- `selectors.py` — CSS селекторы
- `normalizer.py` — parse_price, parse_mileage, parse_brand_model
- `urls.py` — URL builder
- `valuation_parser.py` — парсинг оценки из текста
- `valuation_page_parser.py` — парсинг valuation page
- `__init__.py`

### app/matcher/
- `auto_ru_matcher.py` — match_card_to_config()

### app/analyzer/
- `price_analyzer.py` — анализ цены (MVP v2)
- `internal_price_analysis.py` — оценка из YAML
- `final_price_decision.py` — итоговый вердикт
- `score.py` — агрегатор скореров

### app/database/
- `migrations.py` — миграции БД
- `auto_ru_repo.py` — сохранение карточек

### app/telegram/
- `auto_ru_formatter.py` — формат карточки

### Тесты
- `tests/test_auto_ru_valuation_parser.py` (12 тестов)
- `tests/test_auto_ru_valuation_page_parser.py` (7 тестов)
- `tests/test_internal_price_analysis.py` (6 тестов)
- `test_auto_ru_full_pipeline_5.py`
- `test_auto_ru_sqlite_save.py`
- `test_auto_ru_formatter.py`
- `test_auto_ru_telegram_dry_run.py`
- `collect_fresh_cars_v2.py`

---

## 🗃️ СОСТОЯНИЕ БД (sent_ads)

### Колонки добавлены (21):
```
source, external_id, brand, model, engine, transmission, drive, owners,
auto_ru_price_low, auto_ru_price_high, auto_ru_estimate_mid,
auto_ru_status, auto_ru_status_text, auto_ru_delta_percent, auto_ru_valuation_url,
final_verdict, final_recommendation, final_score, final_reasons_json, raw_json, sent_at
```

### Unique index:
```sql
CREATE UNIQUE INDEX idx_sent_ads_source_external_id ON sent_ads(source, external_id)
```

### Записи auto_ru:
| Авто | Год | Цена | Auto.ru диапазон | Вердикт |
|------|-----|------|------------------|---------|
| Honda Freed | 2021 | 1.3 млн | — | no_data |
| Kia Rio | 2021 | 1.39 млн | 1.34–1.49 млн | good_deal |
| Suzuki Swift | 2021 | 1.2 млн | 1.27–1.33 млн | excellent_deal |
| Honda Stepwgn | 2021 | 1.85 млн | 2.03–2.33 млн | excellent_deal |
| Kia Seltos | 2026 | 1.95 млн | 1.27–1.33 млн | strong_overpriced |
| Chevrolet Orlando | 2023 | 1.52 млн | 1.65–1.84 млн | excellent_deal |
| Hyundai Creta | 2021 | 1.75 млн | 1.75–1.91 млн | excellent_deal |

---

## 📝 ЗАМЕТКИ

- **Не тронуто:** Telegram sender, daily pipeline, Haraba scraper
- **Haraba pipeline:** работает отдельно, не затронут
- **Auto.ru оценка:** числовая (low/high) парсится с отдельной страницы, не с карточки
- **estimate_mid:** вычисляется как среднее (low+high)/2, это НЕ оценка Auto.ru
- **CAPTCHA:** persistent профиль снижает с 100% до 20-40%, но не убирает полностью
