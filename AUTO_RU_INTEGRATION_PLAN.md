# Auto.ru интеграция в Haraba Mini

**Дата:** 2026-06-11
**Статус:** ✅ Утверждено

---

## Главное правило

**Не трогать рабочий Haraba pipeline** до тех пор, пока Auto.ru не заработает отдельно через:

```bash
python -m app.runners.run_auto_ru --debug --limit 10 --no-send
```

---

## Архитектура

```
app/
  sources/
    auto_ru/
      __init__.py
      browser.py       # Playwright browser/context для Auto.ru
      scraper.py       # open_auto_ru_search(), collect_cards()
      selectors.py     # CSS селекторы Auto.ru
      parser.py        # parse_search_card(), parse_detail_page()
      urls.py          # (позже) URL builder
      normalizer.py    # extract_auto_ru_id(), parse_price(), parse_mileage()
  runners/
    run_auto_ru.py     # единая команда запуска
```

---

## Что переиспользуем из Haraba Mini

| Модуль | Зачем |
|--------|-------|
| `base.py` | константы, логгер |
| `config_loader.py` | загрузка YAML конфига |
| `feedback_store.py` | dedup (`source + stable_car_key`) |
| `price_scorer_v2.py` | скоринг цены |
| `mileage_scorer.py` | скоринг пробега |
| `powertrain_scorer.py` | скоринг двигателя/коробки |
| `equipment_scorer.py` | скоринг комплектации |
| `model_matcher.py` | matcher карточки к конфигу |
| `telegram_sender.py` | отправка в Telegram |
| `telegram_card_formatter.py` | формат карточки |
| `region_parser.py` | парсинг региона |
| `legal_parser.py` | парсинг ограничений |

---

## Что НЕ переиспользуем

| Модуль | Почему |
|--------|--------|
| `session_manager.py` | Завязан на Haraba-сессию |
| `mobile_first_page_sampler.py` | Haraba-специфичный |
| `run_daily_pipeline.py` | **НЕ трогать** до MVP Auto.ru |

---

## Этапы реализации

### Этап 1 — Структура + Playwright открытие (Блоки 1-3)

**Создать:**
```
app/sources/auto_ru/__init__.py
app/sources/auto_ru/browser.py
app/sources/auto_ru/scraper.py
app/sources/auto_ru/selectors.py
```

**browser.py:**
- `open_auto_ru_page(url)` → `(page, context, browser)`
- Отдельный браузер, без Haraba session_manager
- HEADLESS режим из env var
- Сохранение debug HTML + screenshot

**scraper.py:**
- `open_auto_ru_search(url)` → сохранить `results/debug_auto_ru_search.html` + `.png`
- Дождаться загрузки страницы

**selectors.py:**
```python
CARD_SELECTOR = "div.ListingCars__universalSnippetWrapper"
# остальные селекторы — после диагностики
```

**Проверка:**
```bash
python -c "from app.sources.auto_ru.scraper import open_auto_ru_search; open_auto_ru_search('https://auto.ru/moskva/cars/ford/kuga/used/')"
```
- ✅ страница открылась
- ✅ HTML сохранён
- ✅ screenshot сохранён
- ✅ нет ошибки timeout

---

### Этап 2 — Сбор карточек из выдачи (Блоки 4-5)

**parser.py:**
```python
async def parse_search_card(card_element) -> dict:
    ...
```

**normalizer.py:**
```python
def parse_price(text: str) -> int | None: ...
def parse_mileage(text: str) -> int | None: ...
def extract_auto_ru_id(url: str) -> str: ...
```

**Единый формат карточки:**
```python
{
    "source": "auto_ru",
    "external_id": "1132811999-0a4690cd",
    "url": "https://auto.ru/...",
    "title": "Ford Kuga 2015",
    "brand": "Ford",
    "model": "Kuga",
    "year": 2015,
    "price": 1450000,
    "mileage": 130000,
    "region": "Москва",
    "engine": "unknown",      # пока
    "transmission": "unknown", # пока
    "drive": "unknown",        # пока
    "seller_type": "unknown",  # пока
    "created_at": "2026-06-11T...",
}
```

**stable_car_key:** `auto_ru:{external_id}`

**Проверка:**
```
1. Ford Kuga 2015 | 1 450 000 | 130000 км | Москва | url
2. Volkswagen Tiguan 2014 | 1 620 000 | 150000 км | Москва | url
```
- ✅ title не пустой
- ✅ url не пустой
- ✅ price число
- ✅ year число
- ✅ mileage число или None
- ✅ external_id есть

---

### Этап 3 — Конфиг + Matcher (Блоки 7-8)

**Конфиг:** `config/auto_ru_searches.yaml` (отдельный, пока ручной):
```yaml
sources:
  auto_ru:
    enabled: true
    searches:
      - name: ford_kuga_moscow
        url: "https://auto.ru/moskva/cars/ford/kuga/used/"
        brand: Ford
        model: Kuga
        year_from: 2013
        year_to: 2019
        price_from: 1000000
        price_to: 2000000
        regions:
          - Москва
          - Московская область
        required:
          drive: full
```

**Matcher:** переиспользовать `model_matcher.match_card_to_model()`

```python
def match_card_with_search(card: dict, search_config: dict) -> tuple[bool, list[str]]:
    # Проверить: brand, model, year_from/year_to, price_from/price_to, region, drive
    ...
```

**Проверка:**
```python
card = {"brand": "Ford", "model": "Kuga", "year": 2015, "price": 1450000, "region": "Москва"}
# matched = True, reasons = ["year ok", "price ok", "region ok"]

card2 = {"brand": "Ford", "model": "Kuga", "year": 2010, ...}
# matched = False, reasons = ["year below minimum"]
```

---

### Этап 4 — Detail page + Price Analyzer (Блоки 9-10)

**parser.py:**
```python
async def parse_detail_page(page, url: str) -> dict:
    # Достаём: engine, transmission, drive, owners, seller, description
    # Автооценка Auto.ru — если видна, иначе None
    ...
```

**price_analyzer.py:**
```python
def analyze_price(card: dict) -> dict:
    # seller_price vs auto_ru_estimate (если есть)
    # discount, discount_percent, price_verdict, price_score
    ...
```

**Проверка:**
```
seller_price = 1 545 000
auto_ru_estimate = 1 700 000
→ discount = 155000, discount_percent ≈ 9.1, verdict = below_market
```

---

### Этап 5 — Scoring + Database (Блоки 6, 11-12)

**Scoring:** переиспользовать существующие скореры:
- `price_scorer_v2.score_price()`
- `mileage_scorer.score_mileage()`
- `powertrain_scorer.score_engine()`, `score_transmission()`
- `equipment_scorer.score_equipment()`

**Dedup:** `feedback_store.py` уже поддерживает composite key.
- Для Auto.ru: `stable_car_key = "auto_ru:" + external_id`
- Уникальность: `source + external_id`

**БД:** `feedback_store.py` — `sent_ads` таблица
- `source = "auto_ru"`
- `external_id` из URL

**Проверка:**
```
1-й запуск: saved = 20, new = 20
2-й запуск: skipped_duplicate = 20, new = 0
```

---

### Этап 6 — Telegram Sender (Блок 13)

- Карточка Auto.ru проходит через **тот же** `telegram_sender.py`
- Формат: `telegram_card_formatter.py` + поле `source: auto_ru`
- Inline кнопки: те же 🟢🟡🔴
- Feedback: тот же механизм

**Формат карточки Auto.ru:**
```
🔥 Ford Kuga 2015

Цена: 1 545 000 ₽
Оценка Auto.ru: ~1 700 000 ₽ (если есть)
Выгода: ~155 000 ₽
Статус: ниже рынка

Пробег: 130 000 км
Регион: Москва
Привод: полный

Скоринг: 82/100
Вердикт: срочно смотреть

Ссылка:
https://auto.ru/...
```

---

### Этап 7 — Runner + Debug (Блоки 14-16)

**app/runners/run_auto_ru.py:**

```bash
python -m app.runners.run_auto_ru                  # полный запуск
python -m app.runners.run_auto_ru --debug           # visible браузер, debug файлы
python -m app.runners.run_auto_ru --limit 10        # лимит карточек
python -m app.runners.run_auto_ru --no-send         # без Telegram
python -m app.runners.run_auto_ru --debug --limit 10 --no-send  # MVP тест
```

**Логика runner:**
1. Загрузить конфиг Auto.ru searches
2. Для каждого search: открыть URL → собрать карточки
3. Распарсить краткую карточку
4. Проверить matcher
5. Открыть detail только для matched
6. Price analyzer + score
7. Сохранить в БД (dedup)
8. Отправить в Telegram (если score выше порога и не --no-send)

**Ожидаемый лог:**
```
Loaded searches: 1
Search ford_kuga_moscow started
Cards found: 37
Parsed: 35
Matched: 8
Details parsed: 8
Saved new: 5
Duplicates: 3
Sent to Telegram: 4
Done
```

**Error handling:**
- `safe_text()`, `safe_attr()` — не падать на одной карточке
- Если одна карточка сломалась → `continue`, остальные продолжают

---

### Этап 8 — Интеграция в daily pipeline (БЛОК 20, ПОСЛЕ MVP)

**Только когда Auto.ru стабильно работает отдельно:**

Расширить `run_daily_pipeline.py`:
- Добавить `step_collect_auto_ru_cards()`
- Объединить карточки Haraba + Auto.ru → единый audit → единый send

**НЕ ДЕЛАТЬ СЕЙЧАС.**

---

## Что НЕ делаем в MVP

- ❌ Авторизация Auto.ru
- ❌ Обход капчи
- ❌ Массовый парсинг (только 1-я страница)
- ❌ Сложный ML / самообучение
- ❌ Антидубли между источниками (пока `source + external_id`)
- ❌ Автоматическая генерация URL из конфига (вручную в YAML)
- ❌ Изменение `run_daily_pipeline.py`

---

## Порядок выполнения

| # | Этап | Проверка |
|---|------|----------|
| 1 | Блок 1-3: структура + открыть Auto.ru | debug HTML + screenshot |
| 2 | Блок 4-5: карточки найдены и распарсены | 5 карточек с title/price/year/mileage |
| 3 | Блок 7-8: конфиг + matcher | loaded searches > 0, matched/rejected |
| 4 | Блок 9-10: detail page + price analyzer | detail JSON сохраняется |
| 5 | Блок 6,12: dedup + БД | 2-й запуск не создаёт дубли |
| 6 | Блок 13: Telegram отправка | карточка пришла, реакция сохранилась |
| 7 | Блок 14-16: runner + debug + error handling | `--debug --limit 10 --no-send` работает |
| 8 | Блок 20: daily pipeline | **ПОСЛЕ MVP** |

---

## Конфигурация (первая версия)

`config/auto_ru_searches.yaml`:
```yaml
sources:
  auto_ru:
    enabled: true
    searches:
      - name: ford_kuga_moscow
        url: "https://auto.ru/moskva/cars/ford/kuga/used/"
        brand: Ford
        model: Kuga
        year_from: 2013
        year_to: 2019
        price_from: 1000000
        price_to: 2000000
        regions:
          - Москва
          - Московская область
      - name: tiguan_moscow
        url: "https://auto.ru/moskva/cars/volkswagen/tiguan/used/"
        brand: Volkswagen
        model: Tiguan
        year_from: 2013
        year_to: 2019
        price_from: 1200000
        price_to: 2200000
        regions:
          - Москва
          - Московская область
```

---

## Селекторы Auto.ru (из памяти)

**Card selector:** `div.ListingCars__universalSnippetWrapper`

**Парсинг:** `card.inner_text()` + regex (НЕ отдельные элемент-селекторы)
- Link: `a[href*='/cars/used/sale/']`
- Price: regex `([\d\s]+)\s*[₽р]`
- Mileage: regex `([\d\s]+)\s*км`
- Year: standalone 4-digit line `^20\d{2}$`

---

## Критерии готовности MVP

- [ ] `python -m app.runners.run_auto_ru --debug --limit 10 --no-send` работает без crash
- [ ] 10 карточек распарсены с title/price/year/mileage/region/url
- [ ] Matcher отсеивает неподходящие
- [ ] Detail page сохраняет engine/transmission/drive/owners
- [ ] Dedup: 2-й запуск не создаёт дубли
- [ ] Telegram: карточка пришла, кнопка нажата, feedback сохранён
- [ ] Error handling: одна сломанная карточка не роняет pipeline
