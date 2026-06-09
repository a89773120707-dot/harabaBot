"""
БЛОК 6: price_scorer.py — ценовой скоринг
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
    """Скоринг цены карточки по правилам модели.

    Returns:
        {
            "score": int,        # -50..+40
            "category": str,     # suspicious_low/excellent/good/fair/expensive/reject
            "explanation": str,  # человекочитаемое объяснение
            "price_status": str, # ниже рынка / отличная цена / хорошая цена / fair / дорого, но допустимо / выше допустимого / подозрительно дёшево
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

    # Проверка по порядку от худшего к лучшему
    # 1. Reject if weak
    if rej_lo and card_price >= rej_lo:
        status = "выше допустимого"
        return {"score": -50, "category": "reject_if_weak",
                "explanation": f"Цена {card_price:,} >= {rej_lo:,} — выше верхней границы допустимого",
                "price_status": status}

    # 2. Suspicious low
    if susp_hi and card_price < susp_hi:
        status = "подозрительно дёшево"
        return {"score": -25, "category": "suspicious_low",
                "explanation": f"Цена {card_price:,} < {susp_hi:,} — подозрительно дёшево, возможна проблема",
                "price_status": status}

    # 3. Excellent
    if exc_hi and card_price < exc_hi:
        status = "отличная цена"
        return {"score": 40, "category": "excellent",
                "explanation": f"Цена {card_price:,} — отличная, ниже {exc_hi:,}",
                "price_status": status}

    # 4. Good
    if good_lo and good_hi and good_lo <= card_price < good_hi:
        status = "хорошая цена"
        return {"score": 25, "category": "good",
                "explanation": f"Цена {card_price:,} — хорошая, в диапазоне {good_lo:,}–{good_hi:,}",
                "price_status": status}

    # 5. Fair
    if fair_lo and fair_hi and fair_lo <= card_price < fair_hi:
        status = "fair"
        return {"score": 5, "category": "fair",
                "explanation": f"Цена {card_price:,} — средняя, в диапазоне {fair_lo:,}–{fair_hi:,}",
                "price_status": status}

    # 6. Expensive but OK if top
    if exp_lo and exp_hi and exp_lo <= card_price < exp_hi:
        # Определим насколько близко к верхней границе
        range_size = exp_hi - exp_lo
        position = card_price - exp_lo
        ratio = position / range_size if range_size > 0 else 0

        if ratio > 0.7:
            detail = "дорого, близко к верхней границе допустимого"
        elif ratio > 0.4:
            detail = "дорого, но допустимо"
        else:
            detail = "дорого, но в пределах допустимого"

        status = "дорого, но допустимо"
        return {"score": -10, "category": "expensive_but_ok_if_top",
                "explanation": f"Цена {card_price:,} — {detail}, OK только если топ-комплектация и хорошее состояние",
                "price_status": status}

    # 7. По умолчанию — нейтрально
    return {"score": 0, "category": "unknown_price",
            "explanation": f"Цена {card_price:,} не попадает в известные диапазоны",
            "price_status": "неизвестно"}
