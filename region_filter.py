"""
region_filter.py — Блок 4: региональный фильтр
"""

ALLOWED_REGIONS = [
    "москва",
    "московская",
    "ярославская",
    "тверская",
    "владимирская",
    "калужская",
    "рязанская",
    "тульская",
    # Добавляем сокращения и варианты
    "мо",
]


def check_region(card_region: str | None, allowed: list[str] | None = None) -> dict:
    """Проверяет регион карточки.

    Returns:
        {"allowed": bool, "reason": str}
    """
    if not card_region:
        return {"allowed": True, "reason": "region_unknown_warning"}

    region_lower = card_region.lower().strip()
    allowed_lower = [r.lower() for r in (allowed or ALLOWED_REGIONS)]

    for ar in allowed_lower:
        if ar in region_lower or region_lower in ar:
            return {"allowed": True, "reason": ""}

    return {"allowed": False, "reason": "region_not_allowed"}


def extract_region_from_card(card: dict) -> str | None:
    """Извлекает регион из location/title/description карточки."""
    location = card.get("location", card.get("region", ""))
    title = card.get("title", "")
    description = card.get("description", "")

    text = (location + " " + title + " " + description).lower()

    for region in ALLOWED_REGIONS:
        if region in text:
            return region.capitalize()

    return None
