# Telegram Card V2 — Утверждённый формат (2026-06-09)

## Структура карточки

```
[ФОТО] — главное фото, если доступно

{emoji} {title} ({year})

💰 {price} ₽

📊 Рынок:
🟢 Отличная: {range} ₽
🟡 Хорошая: {range} ₽
🟠 Дорого (если топ): {range} ₽
🔴 Reject: {range} ₽

📍 {city}, {oblast}
🛣 {mileage} км

⚙️ {volume} {fuel} ({power} л.с.)
🔄 {transmission}
🚙 {drive} ✅

👤 {owners_formatted}
⚖️ {legal_status}

🎯 Почему в выборке:
✅ Полный привод
✅ {transmission_capitalize}
✅ Без ограничений
✅ {owners_formatted}
✅ Регион подходит
⚠ цена выше рынка (если есть)

🧮 Оценка: {score}/100
💰 Цена: {sign}{score} — {reason}
🛣 Пробег: {sign}{score} — {reason}
⚙️ Двигатель: {sign}{score} — {reason}
🔄 Коробка: {sign}{score} — {reason}
🚙 Привод: {sign}{score} — {reason}
👤 Владельцы: {sign}{score} — {reason}

🔗 {mobile_url}

🟢 Купить  🟡 Посмотреть
🔴 Скипнуть  📖 Описание  📷 Ещё фото (если >1 фото)
```

## Правила

1. **Hard-stop:** engine/transmission/drive = unknown → do_not_send
2. **Фото:** send_photo если есть main_photo_url, fallback → send_message
3. **Описание продавца:** только кнопка 📖, не в карточке
4. **Вердикт:** объединён с "Почему в выборке" — один блок
5. **Кнопки:** 🟢🟡 сверху, 🔴📖📷 снизу (только 📖 если есть описание, только 📷 если >1 фото)
6. **Регион:** city + oblast без дублирования
7. **Двигатель:** "{volume} {fuel} ({power} л.с.)"
8. **Владельцы:** "1 владелец", "2 владельца", "3 владельца", "4+ владельцев"
9. **Автотека:** скрыта (почти у всех есть)

## Files

- `telegram_card_formatter.py` — формат карточки
- `telegram_sender.py` — отправка с фото fallback
- `telegram_audit.py` — audit с hard-stop на unknown specs
- `telegram_feedback_bot.py` — кнопки + описание + фото
- `photo_parser.py` — парсинг фото из mobile detail
- `mobile_first_page_sampler.py` — сбор карточек + фото
