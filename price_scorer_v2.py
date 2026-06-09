"""
БЛОК 6v2: price_scorer.py — ценовой скоринг v2 (калибровка)

Изменения:
- reject_if_weak → -30 (было -50), не auto-reject
- suspicious_low → -15 (было -25)
- expensive_but_ok_if_top → -15 (было -10)
- excellent → +35 (было +40)
"""
import re


def _parse_range(s: str) -> tuple[int | None, int | None]:
    """Парсит строку типа '1500000-1800000' → (low, high)."""
    if not s or not isinstance(s, str):
        return None, None
    s = s.replace(" ", "").replace("\xa0", "")
    m = re.match(r"<(\d+)", s)
    if m:
        return 0, int(m.group(1))
    m = re.match(r"(\d+)\+", s)
    if m:
        return int(m.group(1)), None
    m = re.match(r"(\d+)-(\d+)", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def score_price(card_price: int | None, model_price: dict) -> dict:
    """Скоринг цены карточки по правилам модели (v2).

    Returns:
        {
            "score": int,        # -30..+35
            "category": str,     # suspicious_low/excellent/good/fair/expensive/reject_if_weak
            "explanation": str,  # человекочитаемое объяснение
            "price_status": str, # отличная цена / хорошая цена / fair / дорого, но допустимо / выше допустимого / подозрительно дёшево
        }
    """
    if card_price is None:
        return {"score": 0, "category": "unknown", "explanation": "Цена неизвестна", "price_status": "неизвестно"}

    price = model_price or {}
    excellent = price.get("excellent", "")
    good = price.get("good", "")
    fair = price.get("fair", "")
    expensive = price.get("expensive_but_ok_if_top", "")
    reject_weak = price.get("reject_if_weak", "")
    suspicious = price.get("suspicious_low", "")

    # Парсим диапазоны
    susp_lo, susp_hi = _parse_range(suspicious)
    exc_lo, exc_hi = _parse_range(excellent)
    good_lo, good_hi = _parse_range(good)
    fair_lo, fair_hi = _parse_range(fair)
    exp_lo, exp_hi = _parse_range(expensive)
    rej_lo, rej_hi = _parse_range(reject_weak)

    # 1. Reject if_weak → -30 (не -50)
    if rej_lo and card_price >= rej_lo:
        return {"score": -30, "category": "reject_if_weak",
                "explanation": f"Цена {card_price:,} >= {rej_lo:,} — выше верхней границы допустимого",
                "price_status": "выше допустимого"}

    # 2. Suspicious low → -15 (было -25)
    if susp_hi and card_price < susp_hi:
        return {"score": -15, "category": "suspicious_low",
                "explanation": f"Цена {card_price:,} < {susp_hi:,} — подозрительно дёшево, возможна проблема",
                "price_status": "подозрительно дёшево"}

    # 3. Excellent → +35 (было +40)
    if exc_hi and card_price < exc_hi:
        return {"score": 35, "category": "excellent",
                "explanation": f"Цена {card_price:,} — отличная, ниже {exc_hi:,}",
                "price_status": "отличная цена"}

    # 4. Good → +20 (было +25)
    if good_lo and good_hi and good_lo <= card_price < good_hi:
        return {"score": 20, "category": "good",
                "explanation": f"Цена {card_price:,} — хорошая, в диапазоне {good_lo:,}–{good_hi:,}",
                "price_status": "хорошая цена"}

    # 5. Fair → +5
    if fair_lo and fair_hi and fair_lo <= card_price < fair_hi:
        return {"score": 5, "category": "fair",
                "explanation": f"Цена {card_price:,} — средняя, в диапазоне {fair_lo:,}–{fair_hi:,}",
                "price_status": "fair"}

    # 6. Expensive → -15 с детализацией позиции
    if exp_lo and exp_hi and exp_lo <= card_price < exp_hi:
        range_size = exp_hi - exp_lo
        position = card_price - exp_lo
        ratio = position / range_size if range_size > 0 else 0

        if ratio > 0.7:
            detail = "дорого, близко к верхней границе допустимого"
        elif ratio > 0.4:
            detail = "дорого, но допустимо"
        else:
            detail = "дорого, но в пределах допустимого"

        delta = card_price - good_hi if good_hi else card_price - exp_lo
        return {"score": -15, "category": "expensive_but_ok_if_top",
                "explanation": f"выше хорошей цены на {delta:,} ₽ — {detail}",
                "price_status": "дорого, но допустимо"}

    # 7. Выше всех диапазонов → -30
    # Если цена выше expensive_max (или reject пустой)
    if exp_hi and card_price >= exp_hi:
        delta = card_price - exp_hi
        return {"score": -30, "category": "reject_if_weak",
                "explanation": f"выше верхней границы на {delta:,} ₽",
                "price_status": "выше допустимого"}

    # 8. По умолчанию — нейтрально
    return {"score": 0, "category": "unknown_price",
            "explanation": f"Цена {card_price:,} не попадает в известные диапазоны",
            "price_status": "неизвестно"}
