CITY_TO_REGION = {
    "москва": "Москва", "щербинка": "Москва",
    "зеленоград": "Москва", "троицк": "Москва",
    "котельники": "Московская область", "чехов": "Московская область",
    "подольск": "Московская область", "электросталь": "Московская область",
    "люберцы": "Московская область", "мытищи": "Московская область",
    "королёв": "Московская область", "korolev": "Московская область",
    "новомосковск": "Тульская область",
    "тула": "Тульская область",
    "тверь": "Тверская область",
    "ярославль": "Ярославская область",
    "владимир": "Владимирская область",
    "калуга": "Калужская область",
    "рязань": "Рязанская область",
    "кесова гора": "Тверская область",
    "kesova gora": "Тверская область",
    "кириши": "Ленинградская область",
    "кириллов": "Вологодская область",
    "боровск": "Калужская область",
    "обнинск": "Калужская область",
    "суворов": "Тульская область",
    "алексин": "Тверская область",
    "переславль-залесский": "Ярославская область",
    "ростов": "Ярославская область",
    "углич": "Ярославская область",
    "суздаль": "Владимирская область",
    "гусь-хрустальный": "Владимирская область",
    "кашира": "Московская область",
    "серпухов": "Московская область",
    "наро-фоминск": "Московская область",
    "коломна": "Московская область",
    "можайск": "Московская область",
    "дмитров": "Московская область",
    "клин": "Московская область",
    "волок": "Новгородская область",
}

OBLAST_KEYWORDS = {
    "тверская": "Тверская область",
    "ярославская": "Ярославская область",
    "тульская": "Тульская область",
    "владимирская": "Владимирская область",
    "калужская": "Калужская область",
    "рязанская": "Рязанская область",
    "московская": "Московская область",
}

ALLOWED_REGIONS = [
    "Москва", "Московская область",
    "Ярославская область", "Тверская область",
    "Владимирская область", "Калужская область",
    "Рязанская область", "Тульская область",
]


def parse_region(text: str) -> dict:
    """Распознать регион — вернуть город + область.

    Возвращает:
        city: самый конкретный город (или "")
        oblast: область (или "")
        normalized: "Город, Область" или "Область" или "unknown"
        value: legacy — то же что normalized
        allowed: True если регион в allowed list
        confidence: high (city match), medium (oblast only), low (none)
        source: "city_match", "oblast_match", "unknown"

    Примеры:
        "Кесова Гора, Тверская область"
        "Подольск, Московская область"
        "Тверская область"
    """
    if not text:
        return {"city": "", "oblast": "", "value": "unknown",
                "normalized": "unknown", "allowed": False,
                "confidence": "low", "source": "not_found"}

    t = text.lower()

    # 1. Найти город (city_match)
    found_city = None
    found_region_from_city = None
    best_city_len = 0
    for city, region in CITY_TO_REGION.items():
        if city in t and len(city) > best_city_len:
            # Выбрать самый длинный match (избежать "тверь" в "тверская")
            found_city = city
            found_region_from_city = region
            best_city_len = len(city)

    # 2. Найти область (oblast_match)
    found_oblast = None
    for kw, oblast in OBLAST_KEYWORDS.items():
        if kw in t:
            found_oblast = oblast
            break

    # 3. Собрать результат
    city_name = ""
    oblast_name = ""

    if found_city:
        # Capitalize city name
        city_name = found_city.title() if found_city != "kesova gora" else "Кесова Гора"
        oblast_name = found_region_from_city

    if found_oblast:
        # Если область найдена отдельно — использовать её (может дополнять город)
        if not oblast_name:
            oblast_name = found_oblast
        elif found_oblast != oblast_name:
            # Разные области — приоритет city-based, но fallback на oblast
            pass  # оставить city-based

    # Если только oblast — поставить город в ""
    if not city_name and found_oblast:
        oblast_name = found_oblast

    # Normalized display
    if city_name and oblast_name:
        if city_name == oblast_name:
            normalized = city_name  # "Москва, Москва" → "Москва"
        else:
            normalized = f"{city_name}, {oblast_name}"
        confidence = "high"
        source = "city_match"
    elif oblast_name:
        normalized = oblast_name
        confidence = "medium"
        source = "oblast_match"
    else:
        normalized = "unknown"
        confidence = "low"
        source = "not_found"

    allowed = oblast_name in ALLOWED_REGIONS if oblast_name else False

    return {
        "city": city_name,
        "oblast": oblast_name,
        "value": normalized,
        "normalized": normalized,
        "allowed": allowed,
        "confidence": confidence,
        "source": source,
    }
