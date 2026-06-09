# Блок 1 — Сессия и вход в Haraba: Детальный план реализации

## Цель
Убедиться, что скрипт может открыть Haraba уже авторизованным, используя существующий `state.json`.

## Что используем (из haraba_bot)
- `data/state.json` — сохранённая сессия
- `session_manager.py` — функции `check_session_status()`, `refresh_session_manual()`
- `check_session.py` — быстрая проверка статуса
- `refresh_session.py` — полуручное обновление сессии
- `login.py` — ручной логин с сохранением state.json
- `check_haraba_auth.py` — проверка авторизации на странице

## Что создаём (в haraba-mini)
Ничего нового не создаём. Копируем и используем готовые файлы из haraba_bot.

## Шаги реализации

### Шаг 1.1 — Копирование базовых файлов
Скопировать из `haraba_bot` в `haraba-mini`:
- `session_manager.py`
- `check_session.py`
- `refresh_session.py`
- `login.py`
- `check_haraba_auth.py`
- `data/state.json` (если существует и валиден)

### Шаг 1.2 — Проверка зависимостей
Убедиться, что в haraba-mini установлен Playwright:
```
pip install playwright
playwright install chromium
```

Проверить, что `pyyaml` установлен.

### Шаг 1.3 — Тест сессии
Запустить:
```
python check_session.py
```

**Ожидаемый результат:**
- `Session status: VALID ✅` — всё ок, сессия жива
- `Session status: EXPIRED ❌` — нужно обновить через `refresh_session.py`
- `Session status: MISSING ⚠` — нет state.json, нужен `login.py`

### Шаг 1.4 — Тест открытия Haraba
Если сессия VALID — запустить простой тест:
- Открыть браузер с state.json
- Перейти на Haraba
- Проверить что авторизация работает (не просит логин)

## Критерий успеха Блока 1
- [ ] `python check_session.py` показывает VALID
- [ ] Haraba открывается авторизованным
- [ ] Файлы session_manager.py, check_session.py и т.д. работают в haraba-mini

## Если что-то не так
- Session EXPIRED → запустить `refresh_session.py` → залогиниться вручную → проверить снова
- Session MISSING → запустить `login.py` → залогиниться вручную → проверить снова
- Ошибка playwright → `pip install playwright && playwright install chromium`
