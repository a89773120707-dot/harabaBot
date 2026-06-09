# PRE-DEPLOYMENT PLAN — HARABA MINI

**Дата:** 2026-06-09
**Цель:** Подготовить код к серверному запуску (VPS)

---

## ЭТАП 0 — PRE-GITHUB AUDIT

**Цель:** Убедиться, что в репозиторий попадёт только рабочий код.

### Блок 0.1 — Инвентаризация проекта
**Задача:**
- Просканировать весь проект.
- Построить дерево файлов.
- Сохранить: `results/project_inventory.md`

**Вывод:**
```
ROOT
 ├── src
 ├── config
 ├── data
 ├── results
 ├── tests
 ├── scripts
```

**Проверка:**
- ✅ все файлы найдены
- ✅ структура сохранена

### Блок 0.2 — Поиск мусора
**Найти:**
- `debug_*.py`
- `check_*.py`
- `tmp_*.py`
- `test_*.py`
- `old_*.py`
- `backup_*.py`

**Разделить:**
- `KEEP` (нужно для продакшна)
- `DELETE` (мусор)
- `ARCHIVE` (нужно, но не сейчас)

**Сохранить:** `results/github_cleanup_report.md`

**Проверка:**
- ✅ найден весь мусор
- ✅ ничего не удалено автоматически

### Блок 0.3 — Проверка дубликатов
**Проверить:**
- `telegram_sender*`
- `telegram_feedback_bot*`
- `run_pipeline*`

**Найти:**
- старые версии
- копии
- черновики

**Проверка:**
- ✅ для каждого модуля осталась 1 рабочая версия

---

## ЭТАП 1 — GIT READY

### Блок 1.1 — Проверка .gitignore
**Проверить что НЕ попадут:**
- `__pycache__`
- `*.db`
- `*.log`
- `.env`
- `playwright session`
- `venv`

**Проверка:**
- Команда: `git status`
- Не должно быть: `.env`, `feedback.db`, `state.json`

**PASS:**
- ✅ секреты не попадут в GitHub

### Блок 1.2 — Проверка конфигов
**Проверить:**
- `config/*.yaml`

**Вопрос:** Все ли используются?
**Сохранить:** `results/config_audit.md`

**Проверка:**
- ✅ неиспользуемых конфигов нет

### Блок 1.3 — Проверка импортов
**Запустить:**
```bash
python -m compileall .
```

**Проверка:**
- ✅ SyntaxError = 0

---

## ЭТАП 2 — ПРЕДДЕПЛОЙ

### Блок 2.1 — Проверка БД
**Проверить:**
- `feedback.db`
- `telegram_recipients`
- `sent_ads`

**Сохранить:** `results/db_audit.md`
**Проверить:**
- feedback count
- recipient count
- sent_ads count

**Проверка:**
- ✅ БД читается
- ✅ миграции применены

### Блок 2.2 — Проверка пайплайна
**Запуск:**
```bash
python run_daily_pipeline.py --dry-run
```

**Проверить этапы:**
1. collect
2. enrich
3. audit
4. send
5. report

**PASS:**
- ✅ ошибок нет

### Блок 2.3 — Проверка Telegram
**Тест:**
```bash
python telegram_sender.py --send --limit 1
```

**Проверить:**
- Фото
- Карточка
- Кнопки

**PASS:**
- ✅ карточка пришла

---

## ЭТАП 3 — GITHUB PUSH

### Блок 3.1 — Git статус
**Команда:**
```bash
git status
```

**Проверить:**
- изменения ожидаемые
- мусора нет

**PASS:**
- ✅ git status чистый

### Блок 3.2 — Commit
**Команда:**
```bash
git add .
git commit -m "Haraba Mini MVP ready for VPS deployment"
```

**Проверка:**
```bash
git log --oneline -1
```

**PASS:**
- ✅ коммит создан

### Блок 3.3 — Push
**Команда:**
```bash
git push origin main
```

**Проверка:**
- Открыть репозиторий: `harabaBot GitHub Repository`

**PASS:**
- ✅ новый коммит виден на GitHub

---

## ЭТАП 4 — VPS DEPLOY

### Блок 4.1 — Обновить сервер
**На VPS:**
```bash
cd ~/harabaBot
git pull
```

**Проверка:**
```bash
git log --oneline -1
```
Хэш должен совпадать с GitHub.

**PASS:**
- ✅ сервер получил новый код

### Блок 4.2 — Проверка зависимостей
```bash
pip install -r requirements.txt
```

**Проверка:**
```bash
python --version
playwright --version
```

**PASS:**
- ✅ окружение готово

### Блок 4.3 — Dry Run на сервере
```bash
python run_daily_pipeline.py --dry-run
```

**Проверить:**
- collect
- enrich
- audit
- report

**PASS:**
- ✅ сервер обрабатывает карточки

### Блок 4.4 — Реальная отправка
```bash
python run_daily_pipeline.py --send
```

**Проверить:**
- фото
- карточка
- кнопки
- реакция
- `feedback.db`

**PASS:**
- ✅ полный цикл работает

---

## ЭТАП 5 — ПЕРЕХОД В ПРОД

**После успешного VPS запуска:**
1. Запустить feedback bot как service.
2. Настроить cron каждые 15 минут.
3. Включить pipeline.
4. Начать копить реакции.

---

## 🛑 СТОП ДО 50 РЕАКЦИЙ

**До накопления 50+ реакций:**

❌ не менять скоринг
❌ не менять веса
❌ не менять конфиги
❌ не делать самообучение

**Только:**
✅ собирать карточки
✅ собирать реакции owner
✅ собирать реакции manager
✅ контролировать стабильность

**После 50–100 реакций начинается следующая большая итерация — аналитика и обучение скоринга.**
