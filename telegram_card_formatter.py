"""
telegram_card_formatter.py — Telegram Card V2

Структура карточки:
1. Фото (через send_photo, не в тексте)
2. Модель / год
3. Цена + статус + разница к хорошей
4. Рынок модели (диапазоны)
5. Регион / пробег
6. Двигатель / коробка / привод
7. Владельцы / юридический статус / автотека
8. Почему прошёл конфиг
9. Чек-лист оценки
10. Ссылка
11. Кнопки: 🟢 Купить | 🟡 Посмотреть | 🔴 Скипнуть | 📖 Описание

Описание продавца УБРАНО из карточки — только кнопка 📖 Описание.
"""
import re
from config_loader import get_model_by_id


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def format_money(value) -> str:
    """Форматировать деньги: 1510000 → '1 510 000 ₽'. None/0 → '—'."""
    if not value or value == 0:
        return "—"
    try:
        return f"{int(value):,} ₽".replace(",", " ")
    except (ValueError, TypeError):
        return "—"


def normalize_transmission(raw: str) -> str:
    """Нормализовать название коробки."""
    if not raw or raw == "unknown":
        return "unknown"
    lower = raw.lower().strip()
    if any(kw in lower for kw in ["автомат", "automatic", "at ", "at)", "акпп"]):
        if "механика" in lower or "manual" in lower:
            return "manual"
        if "робот" in lower or "dsg" in lower:
            return "dsg"
        return "automatic"
    if any(kw in lower for kw in ["робот", "dsg", "dsi", "s-tronic", "s tronic"]):
        return "dsg"
    if any(kw in lower for kw in ["вариатор", "cvt"]):
        return "cvt"
    if any(kw in lower for kw in ["механика", "manual", "мкпп"]):
        return "manual"
    return raw


def normalize_drive(raw: str) -> str:
    """Нормализовать привод."""
    if not raw or raw == "unknown":
        return "unknown"
    lower = raw.lower()
    if any(kw in lower for kw in ["полн", "awd", "4wd", "4matic", "quattro", "xdrive"]):
        return "awd"
    if any(kw in lower for kw in ["перед", "fwd"]):
        return "fwd"
    if any(kw in lower for kw in ["задн", "rwd"]):
        return "rwd"
    return raw


def display_transmission(canonical: str) -> str:
    """Человекочитаемое название коробки."""
    mapping = {
        "automatic": "автомат",
        "dsg": "робот (DSG)",
        "cvt": "вариатор",
        "manual": "механика",
    }
    return mapping.get(canonical, canonical)


def parse_seller_description(raw_text: str) -> str:
    """Извлечь описание продавца из mobile_detail_raw_text."""
    if not raw_text:
        return ""
    start_marker = "Комментарий продавца"
    end_marker = "Читать дальше"
    start_idx = raw_text.find(start_marker)
    if start_idx == -1:
        return ""
    start_idx += len(start_marker)
    end_idx = raw_text.find(end_marker, start_idx)
    desc = raw_text[start_idx:end_idx].strip() if end_idx != -1 else raw_text[start_idx:].strip()
    return " ".join(desc.split())


# ──────────────────────────────────────────────────────────────
# Price block
# ──────────────────────────────────────────────────────────────

def _parse_range_value(s: str) -> int | None:
    """Извлечь число из диапазона: '900000-1150000' → (lo, hi), '<1150000' → 1150000."""
    if not s:
        return None
    s = s.strip().replace(" ", "").replace("\xa0", "")
    if s.startswith("<"):
        try:
            return int(s[1:])
        except ValueError:
            return None
    if s.endswith("+"):
        try:
            return int(s[:-1])
        except ValueError:
            return None
    parts = re.split(r'[-–—]', s, maxsplit=1)
    if len(parts) == 2:
        try:
            return int(parts[1])  # верхняя граница
        except ValueError:
            return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse_range_bounds(s: str) -> tuple:
    """Вернуть (lo, hi) из диапазона."""
    if not s:
        return None, None
    s = s.strip().replace(" ", "").replace("\xa0", "")
    if s.startswith("<"):
        try:
            return 0, int(s[1:])
        except ValueError:
            return None, None
    if s.endswith("+"):
        try:
            return int(s[:-1]), None
        except ValueError:
            return None, None
    parts = re.split(r'[-–—]', s, maxsplit=1)
    if len(parts) == 2:
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None, None
    try:
        v = int(s)
        return v, v
    except ValueError:
        return None, None


def _format_range_label(label: str) -> str:
    """Форматировать диапазон: '900000-1150000' → '900 000–1 150 000'."""
    if not label:
        return ""
    s = label.strip().replace(" ", "").replace("\xa0", "")
    parts = re.split(r'[-–—]', s, maxsplit=1)
    if len(parts) == 2:
        try:
            lo = int(parts[0])
            hi = int(parts[1])
            return f"{lo:,}–{hi:,}".replace(",", " ")
        except ValueError:
            return label.replace("-", "–")
    if s.startswith("<"):
        try:
            val = int(s[1:])
            return f"до {val:,}".replace(",", " ")
        except ValueError:
            return label
    if s.endswith("+"):
        try:
            val = int(s[:-1])
            return f"{val:,}+".replace(",", " ")
        except ValueError:
            return label
    return label


def build_price_block_v2(card: dict, config: dict) -> str:
    """Блок цены V2 — цена + разница + ВСЕ диапазоны рынка.

    💰 1 640 000 ₽
    🔴 Выше верхней границы на 390 000 ₽

    📊 Рынок:
    🟢 Отличная: 850 000–1 000 000 ₽
    🟡 Хорошая: 1 000 000–1 150 000 ₽
    🟠 Дорого (если топ): 1 150 000–1 250 000 ₽
    🔴 Reject: 1 250 000+ ₽
    """
    model_id = card.get("model_id")
    if not model_id:
        return ""
    model_rules = get_model_by_id(config, model_id)
    if not model_rules:
        return ""

    price_cfg = model_rules.get("price", {})
    current_price = card.get("price", 0)

    excellent = price_cfg.get("excellent", "")
    good = price_cfg.get("good", "")
    fair = price_cfg.get("fair", "")
    expensive = price_cfg.get("expensive_but_ok_if_top", "")
    reject = price_cfg.get("reject_if_weak", "")

    # Парсим верхние границы
    _, excellent_max = _parse_range_bounds(excellent)
    _, good_max = _parse_range_bounds(good)
    _, expensive_max = _parse_range_bounds(expensive)
    reject_min, _ = _parse_range_bounds(reject)

    lines = []

    # Цена авто крупно
    if current_price:
        lines.append(f"💰 {format_money(current_price)}")

        # Статус цены с разницей
        if current_price and excellent_max and good_max and expensive_max:
            if current_price <= excellent_max:
                lines.append(f"🟢 Отличная цена")
            elif current_price <= good_max:
                lines.append(f"🟡 Хорошая цена")
            elif current_price <= expensive_max:
                delta = current_price - good_max
                lines.append(f"🟠 Выше хорошей цены на {format_money(delta)}")
            elif reject_min and current_price >= reject_min:
                delta = current_price - reject_min
                lines.append(f"🔴 Выше верхней границы на {format_money(delta)}")
            else:
                delta = current_price - expensive_max
                lines.append(f"🔴 Выше верхней границы на {format_money(delta)}")
        elif current_price and good_max:
            if current_price <= good_max:
                lines.append(f"🟡 Хорошая цена")
            else:
                delta = current_price - good_max
                lines.append(f"🔴 Выше хорошей цены на {format_money(delta)}")

    lines.append("")
    lines.append("📊 Рынок:")

    # ВСЕГДА показываем все диапазоны
    if excellent:
        lines.append(f"🟢 Отличная: {_format_range_label(excellent)} ₽")
    if good:
        lines.append(f"🟡 Хорошая: {_format_range_label(good)} ₽")
    elif excellent_max:
        # Fallback: good = excellent + 15%
        good_lo = excellent_max
        good_hi = int(excellent_max * 1.15)
        lines.append(f"🟡 Хорошая: {good_lo:,}–{good_hi:,} ₽".replace(",", " "))
    if expensive:
        lines.append(f"🟠 Дорого (если топ): {_format_range_label(expensive)} ₽")
    if reject:
        lines.append(f"🔴 Reject: {_format_range_label(reject)} ₽")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# Score breakdown
# ──────────────────────────────────────────────────────────────

def build_score_breakdown_v2(card: dict) -> str:
    """Прозрачный чек-лист оценки — всегда с reason.

    🧮 Оценка: 80/100
    💰 Цена: 0 — выше рынка
    🛣 Пробег: +20 — отличный
    ⚙️ Двигатель: 0 — допустимый
    🔄 Коробка: +10 — вариатор рекомендован
    🚙 Привод: +15 — полный
    """
    lines = [f"🧮 Оценка: {card.get('score', 0)}/100"]

    price_score = card.get("price_score", 0)
    mileage_score = card.get("mileage_score", 0)
    engine_score = card.get("engine_score", 0)
    trans_score = card.get("transmission_score", 0)

    # Price — всегда с reason
    price_reason = _extract_reason(card, "price_score")
    sign = "+" if price_score > 0 else ""
    lines.append(f"💰 Цена: {sign}{price_score} — {price_reason}")

    # Mileage — всегда с reason
    mileage_reason = _extract_reason(card, "mileage_score")
    sign = "+" if mileage_score > 0 else ""
    lines.append(f"🛣 Пробег: {sign}{mileage_score} — {mileage_reason}")

    # Engine — всегда с reason
    engine_reason = _extract_reason(card, "engine_score")
    sign = "+" if engine_score > 0 else ""
    lines.append(f"⚙️ Двигатель: {sign}{engine_score} — {engine_reason}")

    # Transmission — всегда с reason
    trans_val = card.get("transmission", "unknown")
    trans_reason = _extract_reason(card, "transmission_score")
    trans_display = display_transmission(trans_val)
    sign = "+" if trans_score > 0 else ""
    lines.append(f"🔄 Коробка: {sign}{trans_score} — {trans_reason}")

    # Drive
    drive_val = card.get("drive", "unknown")
    if drive_val == "awd":
        lines.append("🚙 Привод: +15 — полный")
    else:
        lines.append("🚙 Привод: 0 — не полный")

    # Owners — простой скоринг
    owners_val = card.get("owners", "unknown")
    if owners_val != "unknown":
        try:
            n = int(owners_val)
            if n == 1:
                lines.append(f"👤 Владельцы: +10 — {_format_owners(owners_val)}")
            elif n <= 2:
                lines.append(f"👤 Владельцы: +5 — {_format_owners(owners_val)}")
            elif n == 3:
                lines.append(f"👤 Владельцы: -5 — {_format_owners(owners_val)}")
            else:
                lines.append(f"👤 Владельцы: -10 — {_format_owners(owners_val)}")
        except (ValueError, TypeError):
            pass

    return "\n".join(lines)


def _extract_reason(card: dict, score_field: str) -> str:
    """Извлечь reason для score из bonus/penalty."""
    bonus = card.get("bonus_reasons", [])
    penalty = card.get("penalty_reasons", [])
    all_reasons = bonus + penalty
    for r in all_reasons:
        if _reason_matches_type(r, score_field):
            return _clean_reason(r)
    return _fallback_reason(card, score_field)


def _reason_matches_type(reason: str, score_field: str) -> bool:
    type_map = {
        "price_score": ["цена", "price"],
        "mileage_score": ["пробег", "mileage"],
        "engine_score": ["двигатель", "engine"],
        "transmission_score": ["коробка", "transmission", "trans"],
    }
    keywords = type_map.get(score_field, [])
    return any(kw in reason.lower() for kw in keywords)


def _clean_reason(reason: str) -> str:
    """Очистить reason."""
    m = re.match(r'Пробег\s+([\d,]+)\s*>\s*([\d,]+)\s*\(penalty\)', reason)
    if m:
        return f"пробег {m.group(1)} км — выше нормы"
    m = re.match(r'Пробег\s+([\d,]+)\s*<\s*([\d,]+)\s*\(excellent\)', reason)
    if m:
        return f"пробег {m.group(1)} км — отличный"
    m = re.match(r'Пробег\s+([\d,]+)\s*<\s*([\d,]+)\s*\(good\)', reason)
    if m:
        return f"пробег {m.group(1)} км — хороший"
    if " — " in reason:
        return reason.split(" — ", 1)[1].strip()
    return reason


def _fallback_reason(card: dict, score_field: str) -> str:
    score_val = card.get(score_field, 0)
    if score_field == "price_score":
        cat_map = {
            "excellent": "отличная цена",
            "good": "хорошая цена",
            "fair": "средняя цена",
            "expensive_but_ok_if_top": "дорого, но допустимо",
            "reject_if_weak": "выше допустимого",
        }
        return cat_map.get(card.get("price_category", ""), "нейтрально")
    if score_field == "mileage_score":
        if score_val > 0:
            return f"пробег {card.get('mileage', 0):,} км — отличный"
        elif score_val < 0:
            return f"пробег {card.get('mileage', 0):,} км — выше нормы"
        return "нейтрально"
    if score_field == "engine_score":
        engine_cat = card.get("engine_category", "")
        cat_map = {
            "best": "лучший мотор модели",
            "acceptable": "допустимый",
            "avoid": "проблемный мотор",
        }
        return cat_map.get(engine_cat, "нейтрально")
    if score_field == "transmission_score":
        trans_cat = card.get("transmission_category", "")
        cat_map = {
            "best": "рекомендованная",
            "avoid": "не рекомендуется",
        }
        return cat_map.get(trans_cat, "нейтрально")
    return "нейтрально"


# ──────────────────────────────────────────────────────────────
# Why passed filter
# ──────────────────────────────────────────────────────────────

def build_why_passed(card: dict) -> str:
    """🎯 Почему прошёл конфиг"""
    lines = []
    drive = card.get("drive", "unknown")
    transmission = card.get("transmission", "unknown")
    legal = card.get("legal_restrictions", "unknown")
    owners = card.get("owners", "unknown")
    region = card.get("region", "unknown")

    if drive == "awd":
        lines.append("✅ Полный привод")
    if transmission in ("automatic", "dsg", "cvt"):
        lines.append(f"✅ {display_transmission(transmission).capitalize()}")
    if legal == "Без ограничений" or (isinstance(legal, str) and "без ограничен" in legal.lower()):
        lines.append("✅ Без ограничений")
    elif legal == "unknown":
        lines.append("⚠️ Юр. статус не распознан")
    if region != "unknown":
        lines.append("✅ Регион подходит")
    elif region == "unknown":
        lines.append("⚠️ Регион не распознан")
    if owners != "unknown":
        try:
            n = int(owners)
            if n == 1:
                lines.append("✅ 1 владелец")
            elif n <= 3:
                lines.append(f"✅ {n} владельца")
        except (ValueError, TypeError):
            pass

    if not lines:
        return ""
    return "🎯 Почему прошёл конфиг:\n" + "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# Main formatter V2
# ──────────────────────────────────────────────────────────────

def format_car_card_v2(card: dict, config: dict, is_hold: bool = False, hold_reasons: list = None) -> str:
    """Карточка V2 — компактная, цифры сверху, описание только по кнопке."""
    title = card.get("title", "Unknown")
    year = card.get("year", "?")
    score = card.get("score", 0)
    decision = card.get("decision", "").replace("_candidate", "").replace("_unknown_model", "")

    # Нормализовать
    transmission_raw = card.get("transmission", "unknown")
    transmission = normalize_transmission(transmission_raw)
    card["transmission"] = transmission
    drive_raw = card.get("drive", "unknown")
    drive = normalize_drive(drive_raw)
    card["drive"] = drive

    region = card.get("region", "unknown")
    owners = card.get("owners", "unknown")
    legal = card.get("legal_restrictions", "unknown")
    autoteka = card.get("autoteka_status", "unknown")
    mileage = card.get("mileage", 0)

    # Full location (city + oblast) — без дублирования
    full_location = card.get("full_location", "")
    if not full_location:
        raw = card.get("mobile_detail_raw_text", "") + " " + card.get("raw_text", "")
        city = _extract_city(raw)
        if city:
            # Не дублировать если регион уже содержит город
            if city in (region or ""):
                full_location = region or city
            else:
                full_location = f"{city}, {region}" if region != "unknown" else city
        else:
            full_location = region if region != "unknown" else ""

    emoji = {"excellent": "🔥", "good": "✅", "watch": "👀", "weak": "⚠️", "reject": "❌"}.get(decision, "❓")

    parts = []

    # Hold warning
    if is_hold and hold_reasons:
        parts.append("⚠️ НУЖНА РУЧНАЯ ПРОВЕРКА")
        for reason in hold_reasons:
            if "region" in reason.lower():
                parts.append("• Регион: не распознан — проверить вручную")
            elif "legal" in reason.lower():
                parts.append("• Юр. статус: не распознан — проверить вручную")
            else:
                parts.append(f"• {reason}")
        parts.append("")

    # 1. Модель / год
    parts.append(f"{emoji} {title} ({year})")
    parts.append("")

    # 2-3. Цена + рынок
    price_block = build_price_block_v2(card, config)
    if price_block:
        parts.append(price_block)
        parts.append("")

    # 4. Регион / пробег
    loc_str = full_location if full_location else ("❓" if region == "unknown" else region)
    parts.append(f"📍 {loc_str}")
    parts.append(f"🛣 {format_money(mileage).replace(' ₽', ' км')}")
    parts.append("")

    # 5. Двигатель / коробка / привод
    engine_short = _shorten_engine(card.get("engine", "unknown"))
    trans_display = display_transmission(transmission)
    drive_str = "полный ✅" if drive == "awd" else drive
    parts.append(f"⚙️ {engine_short}")
    parts.append(f"🔄 {trans_display}")
    parts.append(f"🚙 {drive_str}")
    parts.append("")

    # 6. Владельцы / юр. статус (автотека убрана — почти у всех есть)
    owners_str = _format_owners(owners)
    if legal == "unknown":
        legal_str = "❓ не определён"
    elif "без ограничен" in (legal or "").lower():
        legal_str = "без ограничений ✅"
    else:
        legal_str = f"⚠️ {legal}"
    parts.append(f"👤 {owners_str}")
    parts.append(f"⚖️ {legal_str}")
    parts.append("")

    # 7. Вердикт / Почему в выборке (объединённый блок)
    verdict = _build_verdict(card)
    if verdict:
        parts.append(verdict)
        parts.append("")

    # 8. Чек-лист оценки
    score_block = build_score_breakdown_v2(card)
    if score_block:
        parts.append(score_block)
        parts.append("")

    # 9. Ссылка
    mobile_url = card.get("mobile_url", "")
    url = card.get("url", "")
    if mobile_url and not mobile_url.startswith("test://"):
        parts.append(f"🔗 {mobile_url}")
    elif url and not url.startswith("test://"):
        ad_id = ""
        if "id=" in url:
            ad_id = url.split("id=")[1].split("&")[0]
        if ad_id:
            parts.append(f"🔗 https://m.haraba.ru/search/car/{ad_id}")
        else:
            parts.append(f"🔗 {url}")

    return "\n".join(parts)


def _shorten_engine(engine: str) -> str:
    """Нормализовать двигатель: '2.0 CVT (144 л.с.) (Бензин)' → '2.0 бензин (144 л.с.)'"""
    if engine == "unknown" or not engine:
        return "не определён"

    # Fuel
    fuel_match = re.search(r'\((Бензин|Дизель|Газ|Электро)\)', engine, re.IGNORECASE)
    fuel = fuel_match.group(1) if fuel_match else None

    # Volume: try patterns in order
    # 1. "2.0" at start of string (before first space+word)
    vol_match = re.match(r'(\d+\.\d+)\s', engine)
    if vol_match:
        volume = vol_match.group(1)
    else:
        # 2. "2 л" or "2.0 л" pattern anywhere
        vol_match = re.search(r'(\d+\.\d+)\s*[лЛ]', engine)
        if not vol_match:
            vol_match = re.search(r',\s*(\d+)\s*[лЛ]', engine)  # ", 2 л"
        if not vol_match:
            vol_match = re.search(r'(\d+)\s*[лЛ](?!\.\s*[сС])', engine)
        volume = vol_match.group(1) if vol_match else None
    # Exclude if volume looks like horsepower (3 digits)
    if volume and len(volume.replace('.', '')) >= 3:
        volume = None

    # Power
    power_match = re.search(r'(\d+)\s*л\.?с\.?', engine)
    power = power_match.group(1) if power_match else None

    # Format: "2.0 бензин (144 л.с.)"
    parts = []
    if volume:
        parts.append(f"{volume}")
    if fuel:
        parts.append(fuel.lower())
    result = " ".join(parts)
    if power:
        result += f" ({power} л.с.)"

    return result if result else engine


def _format_owners(owners: str) -> str:
    """'3' → '3 владельца', '1' → '1 владелец', '4' → '4 владельца'."""
    if owners == "unknown" or not owners:
        return "❓"
    try:
        n = int(owners)
        if n == 1:
            return "1 владелец"
        elif n in (2, 3):
            return f"{n} владельца"
        else:
            return f"{n} владельцев"
    except (ValueError, TypeError):
        return f"{owners}"


def _build_verdict(card: dict) -> str:
    """🎯 Вердикт — краткий вывод для закупщика.

    Если цена выше рынка — вердикт 🟡 даже если скоринг 🟢.
    """
    drive = card.get("drive", "unknown")
    transmission = card.get("transmission", "unknown")
    legal = card.get("legal_restrictions", "unknown")
    owners = card.get("owners", "unknown")
    price_score = card.get("price_score", 0)
    price_status = card.get("price_status", "")
    original_decision = card.get("decision", "").replace("_candidate", "").replace("_unknown_model", "")

    # Override decision based on price
    if price_score and price_score < 0:
        decision = "watch"
        decision_label = "Посмотреть"
    elif original_decision in ("excellent", "good"):
        decision = original_decision
        decision_label = "Хороший вариант" if original_decision == "good" else "Отличный вариант"
    elif original_decision == "watch":
        decision = "watch"
        decision_label = "Посмотреть"
    else:
        decision = original_decision
        decision_label = original_decision

    verdict_emojis = {"excellent": "🟢", "good": "🟢", "watch": "🟡", "weak": "🟠", "reject": "🔴"}
    emoji = verdict_emojis.get(decision, "❓")

    lines = [f"🎯 Вердикт: {emoji} {decision_label}"]
    lines.append("")
    lines.append("Почему в выборке:")
    lines.append("")

    # Плюсы
    pros = []
    if drive == "awd":
        pros.append("✅ Полный привод")
    if transmission in ("automatic", "cvt", "dsg"):
        pros.append(f"✅ {display_transmission(transmission).capitalize()}")
    if legal == "Без ограничений" or (isinstance(legal, str) and "без ограничен" in legal.lower()):
        pros.append("✅ Без ограничений")
    if owners != "unknown":
        try:
            n = int(owners)
            if n <= 3:
                if n == 1:
                    pros.append("✅ 1 владелец")
                elif n in (2, 3):
                    pros.append(f"✅ {n} владельца")
        except (ValueError, TypeError):
            pass
    region = card.get("region", "unknown")
    if region != "unknown":
        pros.append("✅ Регион подходит")

    if pros:
        lines.append("\n".join(pros))

    # Минусы
    cons = []
    if price_score and price_score < 0:
        con_text = f"⚠ цена выше рынка"
        if price_status:
            con_text = f"⚠ {price_status}"
        cons.append(con_text)
    mileage_score = card.get("mileage_score", 0)
    if mileage_score and mileage_score < 0:
        cons.append("⚠ пробег выше нормы")
    if owners != "unknown":
        try:
            if int(owners) >= 4:
                cons.append(f"⚠ {_format_owners(owners)}")
        except (ValueError, TypeError):
            pass

    if cons:
        lines.append("")
        lines.append("\n".join(cons))

    return "\n".join(lines)


def _extract_city(raw_text: str) -> str:
    """Извлечь город/посёлок из raw_text перед областью.

    'Кесова Гора, Тверская область' → 'Кесова Гора'
    'Подольск, Московская область' → 'Подольск'
    'Щербинка' → 'Щербинка'
    """
    if not raw_text:
        return ""

    # Паттерн: <город>, <область>
    m = re.search(r'([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*)\s*,\s*(?:Московская|Тверская|Ярославская|Владимирская|Калужская|Рязанская|Тульская)\s*обл', raw_text)
    if m:
        return m.group(1)

    # Паттерн: <город>Частник или <город>Частник
    city_names = [
        "Котельники", "Чехов", "Подольск", "Электросталь", "Люберцы",
        "Мытищи", "Королёв", "Балашиха", "Щербинка", "Новомосковск",
        "Кесова Гора", "Ярославль", "Тверь", "Владимир", "Калуга",
        "Рязань", "Тула", "Москва", "Дмитров",
    ]
    for city in city_names:
        if city in raw_text:
            return city

    return ""


def format_car_card(card: dict, config: dict, is_hold: bool = False, hold_reasons: list = None) -> str:
    """Alias для обратной совместимости."""
    return format_car_card_v2(card, config, is_hold, hold_reasons)
