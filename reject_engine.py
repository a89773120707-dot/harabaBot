"""
БЛОК 5: reject_engine.py — reject-проверка
"""


def check_reject(card: dict, model_rules: dict, global_rules: dict) -> dict:
    """Проверяет reject-условия.

    Returns:
        {
            "rejected": bool,
            "reasons": list[str],
            "score_impact": int,  # 0 если rejected, иначе 0
        }
    """
    reasons = []
    model_reject = model_rules.get("reject", [])
    global_reject = global_rules.get("global_reject", [])
    all_reject = set(model_reject + global_reject)

    # --- Autoteka ---
    autoteka = card.get("autoteka_color", "unknown")
    if autoteka == "red":
        reasons.append("red_autoteka")

    # --- Accident ---
    title = (card.get("title", "") + " " + card.get("description", "")).lower()
    # Только явные accident-маркеры (убрал "damage" — слишком общий)
    accident_keywords = ["airbag", "подушк", "geometry", "геометр", "frame damage",
                         "structural damage", "битый", "после дтп", "после аварии",
                         "after accident", "crashed", "краш", "wrecked", "total loss"]
    for kw in accident_keywords:
        if kw in title:
            reasons.append("major_accident")
            break

    # --- Bad engine/gearbox ---
    engine_bad = ["bad_engine", "engine_oil_burning", "active_engine_errors",
                  "engine_overheat"]
    for r in all_reject:
        if r in engine_bad and r in title:
            reasons.append(r)

    gearbox_bad = ["bad_gearbox", "gearbox_errors", "active_gearbox_errors",
                   "cvt_slipping", "dsg_errors"]
    for r in all_reject:
        if r in gearbox_bad and r in title:
            reasons.append(r)

    # --- Twisted mileage ---
    twisted_kw = ["twisted_mileage", "mileage_twisted", "скручен", "not_original_mileage"]
    for r in all_reject:
        if "twisted" in r or "twisted_mileage" in r:
            for kw in twisted_kw:
                if kw in title:
                    reasons.append("twisted_mileage")
                    break

    # --- AWD check ---
    drive = card.get("drive", "unknown")
    model_drive = model_rules.get("drive", "").lower()
    if model_drive and model_drive != "unknown" and drive == "fwd":
        if model_drive in ("awd", "4matic", "quattro", "4motion", "4x4"):
            reasons.append("no_awd_when_required")

    # --- Taxi / commercial ---
    taxi_kw = ["taxi", "такси", "commercial", "коммерч", "shuttle"]
    for kw in taxi_kw:
        if kw in title:
            reasons.append("taxi_or_commercial")
            break

    if reasons:
        # Deduplicate
        reasons = list(dict.fromkeys(reasons))
        return {
            "rejected": True,
            "reasons": reasons,
            "score_impact": 0,
        }

    return {
        "rejected": False,
        "reasons": [],
        "score_impact": 0,
    }
