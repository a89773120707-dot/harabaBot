# MVP Plan: Модуль сохранения 8 поисков

## Принцип
Не писать с нуля — собрать модуль из готовых частей большой Haraba.

## Архитектура
- **Сессия:** login.py / check_session.py / refresh_session.py / state.json
- **Фильтры:** apply_filter.py
- **Сохранение поиска:** create_saved_search_manual.py / generate_saved_searches.py
- **Запуск пачки:** run_all_searches.py
- **Конфиги:** config_loader.py

## Новые артефакты
- `config/awd_liquid_ready_8.yaml` — конфиг 8 моделей
- `run_saved_searches_8.py` — runner для 8 поисков
- `config/saved_searches_8.yaml` — registry сохранённых поисков

## Логика price margin
```
price_from_real = price_from - 50_000
price_to_real = price_to + 50_000
```

---

## Блок 1 — Сессия и вход в Haraba
**Что делаем:** Используем готовые файлы для открытия Haraba авторизованным
**Проверка:** `python check_session.py` → session valid, authorized: true

## Блок 2 — Чтение конфига 8 моделей
**Что делаем:** Создаём config/awd_liquid_ready_8.yaml с 8 поисками
**Поля:** id, brand, model, year_from, year_to, price_from, price_to, mileage_max, save_name
**Проверка:** `python check_config.py` → loaded searches: 8, all fields ok

## Блок 3 — Расчёт price margin
**Что делаем:** Логика ±50_000 к цене из конфига
**Проверка:** `python run_saved_searches_8.py --dry-run` → показывает реальные цены

## Блок 4 — Выставление фильтров на одной модели
**Что делаем:** Тестируем одну модель (Ford Kuga AWD) — все фильтры
**Проверка:** `python run_saved_searches_8.py --only ford_kuga_awd --no-save` → фильтры применены

## Блок 5 — Сохранение одного поиска
**Что делаем:** Функция save_search() для одного поиска
**Проверка:** Поиск появляется в Haraba в сохранённых

## Блок 6 — Registry сохранённых поисков
**Что делаем:** config/saved_searches_8.yaml — запись результатов, проверка дублей
**Проверка:** Повторный запуск → skip: already saved

## Блок 7 — Прогон всех 8 моделей
**Что делаем:** Запуск всех 8 поисков, устойчивость к ошибкам
**Проверка:** Total: 8, Saved: 8, Failed: 0

## Блок 8 — Проверка сохранённых поисков
**Что делаем:** Открываем каждый сохранённый поиск, проверяем выдачу
**Проверка:** `python run_all_searches.py --preview` → каждый поиск открыт, есть карточки

---

## Главный принцип
**Сначала один поиск полностью, потом все 8.**