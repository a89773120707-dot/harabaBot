"""
legal_parser.py — Определение юридического статуса из raw_text.
"""

# Фразы, подтверждающие отсутствие ограничений
CLEAR_KEYWORDS = [
    "без ограничен",
    "ограничений нет",
    "юридически чист",
    "нет ограничений",
    "не числится",
]

# Фразы, подтверждающие наличие ограничений
RESTRICTED_KEYWORDS = [
    "есть ограничение",
    "запрет регистрационных",
    "запрет на регистрацию",
    "арест",
    "залог",
    "розыск",
    "обременение",
    "ограничен в праве",
]

# Заголовки секций Avtoteka — НЕ являются статусом (игнорируем)
AVTOTEDA_HEADERS = [
    "сведения о залоге",
    "сведения о пробеге",
    "ограничение на регистрацию",
    "сведения о розыске",
    "предпроверка от автотеки",
    "подключить предпроверку",
    "получить отчёт",
]


def parse_legal(text):
    """Определить юридический статус.

    Returns:
        {"value": str, "status": "clear"/"restricted"/"unknown",
         "confidence": "high"/"medium"/"low"}
    """
    if not text or len(text) < 10:
        return {"value": "unknown", "status": "unknown",
                "confidence": "low"}

    t = text.lower()

    # Сначала ищем подтверждение ограничений (конкретные фразы)
    for kw in RESTRICTED_KEYWORDS:
        if kw in t:
            # Проверяем что это НЕ заголовок секции Avtoteka
            is_header = any(h in t and t.count(h) <= t.count(kw) + 1
                          for h in AVTOTEDA_HEADERS if kw in h)
            # "залог" в "сведения о залоге" — header, игнорируем
            # "залог" в "залог не найден" — OK
            if not is_header:
                return {"value": kw, "status": "restricted",
                        "confidence": "high"}

    # Ищем подтверждение отсутствия ограничений
    for kw in CLEAR_KEYWORDS:
        if kw in t:
            return {"value": kw, "status": "clear",
                    "confidence": "high"}

    return {"value": "unknown", "status": "unknown",
            "confidence": "low"}
