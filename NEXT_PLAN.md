# PLAN — Next Steps (after 2026-06-11)

## Текущий статус
- ✅ Admin Bot MVP
- ✅ Feedback V2 UX v3 (4 причины + комментарий, без дублей)
- ✅ RIS аналитика (learning_report, learning_reasons, config_report)
- ✅ Деплой на VPS (оба бота 24/7)

---

## 🎯 СЛЕДУЮЩИЙ ШАГ — Fix 7: Привязать реакцию к config_name

**Проблема:** Сейчас reaction_details не знает какой config породил карточку.
Без config_name невозможно сделать:
- config_report (по какой модели сколько реакций)
- config_suggestions (поднять max_price для Tiguan)

**Что делать:**
1. При сохранении feedback — брать config_name из sent_ads (или из card_data)
2. Сохранять config_name в feedback table (или в reaction_details)
3. Обновить ris_analytics.py — группировать по config_name
4. Проверить что config_report показывает реальные данные

**Файлы для изменения:**
- `telegram_feedback_bot.py` — при save_feedback добавить config_name
- `feedback_store.py` — возможно добавить колонку в feedback
- `ris_analytics.py` — group by config_name

---

## 📋 ПОСЛЕ FIX 7 — Накопить 50-100 реакций

- Отправлять карточки каждый день (cron работает)
- Менеджеры реагируют через кнопки
- Проверять что reason_code сохраняется
- НЕ менять ничего в системе пока не наберём 100 реакций

---

## 🚀 ПОСЛЕ 100 РЕАКЦИЙ — Config Intelligence

### 1. config_suggestions
- Анализировать реакции по моделям
- Если много "Высокая цена" для Tiguan → предложить поднять max_price
- Если много "Хорошая цена" для CX-5 → подтвердить config

### 2. /config_report
- По каждой модели: реакции, причины, тренды
- Пример: Tiguan — 👀 8, 🤔 4, ⏭ 2
- ТОП причины: Высокая цена (12), Большой пробег (7)

### 3. /approve_config_change
- Owner подтверждает изменения конфигов
- pending → active
- rejected → не применяется

---

## 🚫 ЗАМОРОЖЕНО (не делать)
- learning_score
- reaction_learning_scorer.py
- Автоматическое изменение score
- Автоматическое изменение конфигов

---

## 📌 ВАЖНО — порядок действий

1. **Сначала обсудить** Fix 7 с пользователем — как именно привязывать config_name
2. **Потом реализовать** — после утверждения плана
3. **Потом копить реакции** — 50-100 штук
4. **Потом config_suggestions** — только после 100 реакций

**НЕ начинать реализацию без обсуждения!**
