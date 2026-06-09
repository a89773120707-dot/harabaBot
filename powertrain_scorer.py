"""
БЛОК 8: powertrain_scorer.py — двигатель + коробка
"""


def score_engine(card_engine: str, model_engines: dict) -> dict:
    """Скоринг двигателя.

    Returns:
        {"score": int, "category": str, "explanation": str}
    """
    if not card_engine or not model_engines:
        return {"score": 0, "category": "unknown", "explanation": "Двигатель неизвестен"}

    engine_lower = card_engine.lower()
    best = [e.lower() for e in model_engines.get("best", [])]
    acceptable = [e.lower() for e in model_engines.get("acceptable", [])]
    avoid = [e.lower() for e in model_engines.get("avoid", [])]

    # Check best
    for b in best:
        clean = b.replace("_", " ").replace(" ", "")
        if clean in engine_lower.replace(" ", "") or b.replace("_", " ") in engine_lower:
            return {"score": 15, "category": "best",
                    "explanation": f"Двигатель '{card_engine}' — рекомендованный (best)"}

    # Check avoid
    for a in avoid:
        clean = a.replace("_", " ").replace(" ", "")
        if clean in engine_lower.replace(" ", "") or a.replace("_", " ") in engine_lower:
            return {"score": -15, "category": "avoid",
                    "explanation": f"Двигатель '{card_engine}' — проблемный (avoid)"}

    # Check acceptable
    for ac in acceptable:
        clean = ac.replace("_", " ").replace(" ", "")
        if clean in engine_lower.replace(" ", "") or ac.replace("_", " ") in engine_lower:
            return {"score": 0, "category": "acceptable",
                    "explanation": f"Двигатель '{card_engine}' — допустимый (acceptable)"}

    return {"score": 0, "category": "unknown",
            "explanation": f"Двигатель '{card_engine}' не определён в правилах"}


def score_transmission(card_transmission: str, model_transmissions: dict) -> dict:
    """Скоринг коробки передач."""
    if not card_transmission or not model_transmissions:
        return {"score": 0, "category": "unknown", "explanation": "Коробка неизвестна"}

    trans_lower = card_transmission.lower()

    # Нормализация: "автомат" → matching "automatic", "ат" → "automatic"
    normalized_aliases = {
        "автомат": "automatic", "акпп": "automatic", "at ": "automatic",
        "ат)": "automatic", "автоматическая": "automatic",
        "робот": "dsg", "dsi": "dsg", "s-tronic": "dsg", "s tronic": "dsg",
        "вариатор": "cvt",
        "механика": "manual", "мкпп": "manual", "ручная": "manual",
    }
    for alias, canonical in normalized_aliases.items():
        if alias in trans_lower:
            trans_lower = canonical
            break

    best = [t.lower() for t in model_transmissions.get("best", [])]
    avoid = [t.lower() for t in model_transmissions.get("avoid", [])]

    # Best
    for b in best:
        if b in trans_lower:
            display = _transmission_display(card_transmission)
            return {"score": 10, "category": "best",
                    "explanation": f"Коробка '{display}' — рекомендованная (best)"}

    # Avoid symptoms
    for a in avoid:
        clean = a.replace("_", " ")
        if clean in trans_lower or a in trans_lower:
            return {"score": -20, "category": "avoid",
                    "explanation": f"Коробка '{card_transmission}' — проблема (avoid: {a})"}

    display = _transmission_display(card_transmission)
    return {"score": 0, "category": "neutral",
            "explanation": f"Коробка '{display}' — нейтрально"}


def _transmission_display(raw: str) -> str:
    """Вернуть человекочитаемое название коробки."""
    lower = raw.lower()
    if any(kw in lower for kw in ["автомат", "automatic", "at ", "at)", "акпп"]):
        if "робот" in lower or "dsg" in lower:
            return "робот (DSG)"
        return "автомат"
    if any(kw in lower for kw in ["робот", "dsg", "s-tronic"]):
        return "робот (DSG)"
    if any(kw in lower for kw in ["вариатор", "cvt"]):
        return "вариатор"
    if any(kw in lower for kw in ["механика", "manual", "мкпп"]):
        return "механика"
    return raw
