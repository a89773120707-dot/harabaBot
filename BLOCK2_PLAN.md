# Блок 2 — Чтение конфига 8 моделей: Детальный план реализации

## Цель
Научиться читать `config/awd_liquid_ready_8.yaml` и извлекать из него 8 поисков с параметрами.

## Что используем (из haraba_bot)
- `config_loader.py` — пример загрузки YAML конфигов
- `check_config.py` — пример проверки конфига

## Что создаём (в haraba-mini)
1. `config_loader_8.py` — загрузчик awd_liquid_ready_8.yaml
2. `check_config_8.py` — проверка конфига 8 моделей
3. `test_block2.py` — тесты Блока 2

## Шаги реализации

### Шаг 2.1 — config_loader_8.py
Функции:
- `load_8_config()` → загрузить awd_liquid_ready_8.yaml
- `get_models(config)` → вернуть список всех 8 моделей
- `get_model_by_id(config, model_id)` → найти модель по id (например "kia_sorento_prime")
- `get_search_filters(config, model_id)` → получить search_filters для конкретной модели

Структура извлечения для каждого поиска:
```python
{
    "id": "kia_sorento_prime",
    "name": "Kia Sorento Prime",
    "brand": "Kia",
    "model": "Sorento Prime",
    "year_from": 2016,
    "year_to": 2019,
    "price_from": 1800000,
    "price_to": 2600000,
    "drive": "awd",
    "transmission": "automatic",
    "fuel": ["diesel", "petrol"],
}
```

### Шаг 2.2 — check_config_8.py
Запуск:
```
python check_config_8.py
```

Проверки:
- Файл awd_liquid_ready_8.yaml существует
- YAML валидный
- Есть секция models
- models — список из 8 элементов
- У каждой модели есть обязательные поля: id, name, search_filters
- У search_filters есть: brand, model, year_from, year_to, price_from, price_to

Ожидаемый вывод:
```
loaded searches: 8
all required fields: ok
```

### Шаг 2.3 — test_block2.py
Тесты:
1. Конфиг загружается без ошибок
2. 8 моделей найдено
3. Каждая модель имеет все обязательные поля
4. get_model_by_id работает для каждой модели
5. search_filters извлекаются корректно

## Критерий успеха Блока 2
- [ ] `python check_config_8.py` → loaded searches: 8, all required fields: ok
- [ ] `python test_block2.py` → все тесты пройдены
- [ ] config_loader_8.py экспортирует функции для следующих блоков
