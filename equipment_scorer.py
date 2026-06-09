"""
БЛОК 9: equipment_scorer.py — комплектация и опции
"""


def score_equipment(card: dict, model_rules: dict) -> dict:
    """Скоринг комплектации и опций.

    Returns:
        {
            "score": int,
            "bonuses": list[str],
            "explanation": str,
        }
    """
    features = set(card.get("features", []))
    trims = model_rules.get("trims", {})
    strong_bonus = [b.lower() for b in model_rules.get("strong_bonus", [])]

    score = 0
    bonuses = []

    # Trim бонусы
    best_trims = [t.lower() for t in trims.get("best", [])]
    good_trims = [t.lower() for t in trims.get("good", [])]

    title = (card.get("title", "") + " " + card.get("description", "")).lower()

    for bt in best_trims:
        if bt.replace("_", " ") in title or bt in title:
            score += 15
            bonuses.append(f"top_trim: {bt}")
            break

    for gt in good_trims:
        if gt.replace("_", " ") in title or gt in title:
            score += 8
            bonuses.append(f"good_trim: {gt}")
            break

    # Strong bonus опции
    bonus_points = {
        "7_seats": 15,
        "leather": 6,
        "panorama": 8,
        "ventilation": 6,
        "360_camera": 8,
        "rear_camera": 5,
        "keyless": 5,
        "heated_windshield": 5,
        "webasto": 8,
        "s_line": 10,
        "r_line": 10,
        "amg_package": 10,
        "memory_seats": 5,
        "parking_sensors": 4,
        "adaptive_cruise": 8,
        "air_suspension": 8,
        "led": 4,
        "gt_line": 8,
        "executive": 10,
        "highline": 6,
        "titanium": 6,
        "le_plus": 5,
        "tekna": 6,
        "top_trim": 10,
        "white_color": 3,
        "black_color": 3,
        "green_autoteka": 10,
        "1_2_owners": 5,
        "quattro": 8,
        "awd": 10,
        "diesel": 5,
        "clean_frame": 8,
        "good_tires": 3,
        "family_use": 5,
        "clean_service_book": 5,
        "black_headliner": 3,
        "leather_or_alcantara": 6,
        "led_or_xenon": 4,
        "parking_sensors": 4,
        "panoramic_roof": 8,
        "good_multimedia": 3,
        "white_black_grey_color": 3,
        "roof_rails": 3,
        "no_offroad_abuse": 5,
        "bose_audio": 5,
        "2_5_engine": 5,
        "white_red_black_color": 3,
    }

    for feat in features:
        feat_lower = feat.lower()
        # Проверяем по точному совпадению
        if feat_lower in bonus_points:
            pts = bonus_points[feat_lower]
            score += pts
            bonuses.append(f"{feat}: +{pts}")
        # Проверяем через strong_bonus списка модели
        elif feat_lower in strong_bonus:
            score += 5
            bonuses.append(f"strong_bonus({feat}): +5")

    if not bonuses:
        return {"score": 0, "bonuses": [],
                "explanation": "Комплектация не определена или базовая"}

    return {
        "score": score,
        "bonuses": bonuses,
        "explanation": f"Найдено опций: {', '.join(bonuses)}",
    }
