"""
БЛОК 7: mileage_scorer.py — скоринг пробега
"""
import re


def _parse_mileage_range(s: str) -> int | None:
    """Извлекает число из '<130000' или '130000-180000'."""
    if not s or not isinstance(s, str):
        return None
    s = s.replace(" ", "").replace("\xa0", "")
    m = re.match(r"<(\d+)", s)
    if m:
        return int(m.group(1))
    m = re.match(r"(\d+)", s)
    if m:
        return int(m.group(1))
    return None


def score_mileage(card_mileage: int | None, model_mileage: dict) -> dict:
    """Скоринг пробега.

    Returns:
        {
            "score": int,     # -20..+20
            "category": str,  # excellent/good/penalty/reject/unknown
            "explanation": str,
        }
    """
    if card_mileage is None:
        return {"score": 0, "category": "unknown", "explanation": "Пробег неизвестен"}

    exc_threshold = _parse_mileage_range(model_mileage.get("excellent", ""))
    good_hi = _parse_mileage_range(model_mileage.get("good", ""))
    penalty_hi = _parse_mileage_range(model_mileage.get("penalty", ""))
    reject_threshold = _parse_mileage_range(model_mileage.get("reject", ""))

    # Excellent
    if exc_threshold and card_mileage < exc_threshold:
        return {"score": 20, "category": "excellent",
                "explanation": f"Пробег {card_mileage:,} < {exc_threshold:,} (excellent)"}

    # Good
    if good_hi and card_mileage < good_hi:
        return {"score": 10, "category": "good",
                "explanation": f"Пробег {card_mileage:,} < {good_hi:,} (good)"}

    # Penalty
    if penalty_hi and card_mileage < penalty_hi:
        return {"score": -10, "category": "penalty",
                "explanation": f"Пробег {card_mileage:,} > {good_hi or '?'} (penalty)"}

    # Reject
    if reject_threshold and card_mileage >= reject_threshold:
        return {"score": -30, "category": "reject",
                "explanation": f"Пробег {card_mileage:,} >= {reject_threshold:,} (reject)"}

    return {"score": 0, "category": "unknown",
            "explanation": f"Пробег {card_mileage:,} не попал в диапазоны"}
