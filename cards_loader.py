"""
БЛОК 3: cards_loader.py — загрузка и нормализация карточек
"""
import json, yaml, re


def _clean_int(val) -> int | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).replace(" ", "").replace("\xa0", "").strip()
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None


def _normalize_drive(val) -> str:
    if not val:
        return "unknown"
    v = str(val).lower().strip()
    if v in ("awd", "4wd", "4matic", "quattro", "4motion", "full", "полный"):
        return "awd"
    if v in ("fwd", "передний", "front"):
        return "fwd"
    if v in ("rwd", "задний", "rear"):
        return "rwd"
    return "unknown"


def _normalize_transmission(val) -> str:
    if not val:
        return "unknown"
    v = str(val).lower().strip()
    if v in ("automatic", "автомат", "at"):
        return "automatic"
    if v in ("dsg", "s-tronic", "робот", "dct"):
        return "dsg"
    if v in ("cvt", "вариатор"):
        return "cvt"
    if v in ("manual", "механик", "mt"):
        return "manual"
    return "unknown"


def normalize_card(raw: dict) -> dict:
    """Нормализует поля карточки к единому формату."""
    title = raw.get("title", raw.get("name", ""))
    price = _clean_int(raw.get("price"))
    mileage = _clean_int(raw.get("mileage"))
    year = _clean_int(raw.get("year"))
    drive = _normalize_drive(raw.get("drive", raw.get("drivetrain", raw.get("awd"))))
    transmission = _normalize_transmission(raw.get("transmission"))

    engine = str(raw.get("engine", raw.get("engine_info", "")))
    autoteka = str(raw.get("autoteka_status", raw.get("autoteka", ""))).lower()
    autoteka_color = "unknown"
    if "red" in autoteka or "красн" in autoteka:
        autoteka_color = "red"
    elif "green" in autoteka or "зелён" in autoteka:
        autoteka_color = "green"
    elif "yellow" in autoteka or "жёлт" in autoteka or "yellow" in autoteka:
        autoteka_color = "yellow"

    owners = _clean_int(raw.get("owners", raw.get("owner_count")))

    # Извлекаем комплектацию из title/description
    description = str(raw.get("description", ""))
    text = (title + " " + description).lower()

    features = []
    feature_keywords = {
        "leather": ["кож", "leather"],
        "panorama": ["панорам", "panorama"],
        "ventilation": ["вентил", "ventilat"],
        "7_seats": ["7 мест", "7-seat", "seven_seat", "трёхрядн"],
        "360_camera": ["360", "кругов", "around_view"],
        "rear_camera": ["камер", "camera", "rear_view"],
        "keyless": ["keyless", "keyless_go", "бесключ"],
        "heated_windshield": ["подогрев лоб", "heated windsh"],
        "webasto": ["webasto", "вебасто", "предпусков"],
        "s_line": ["s-line", "s_line"],
        "r_line": ["r-line", "r_line"],
        "amg_package": ["amg"],
        "memory_seats": ["memory", "память сид"],
        "parking_sensors": ["парктрон", "parking sensor"],
        "adaptive_cruise": ["адаптивн.*круиз", "adaptive.*cruise"],
        "air_suspension": ["пневмо", "air suspension"],
        "led": ["led", "светодиод", "ксенон", "xenon"],
        "gt_line": ["gt-line", "gt_line"],
        "executive": ["executive", "эксклюзив"],
        "highline": ["highline"],
        "titanium": ["titanium"],
        "le_plus": ["le+", "le plus"],
        "tekna": ["tekna"],
        "top_trim": ["топ", "max", "ultimate", "instyle", "sumum"],
        "white_color": ["белый", "white"],
        "black_color": ["чёрн", "черн", "black"],
    }

    for feat, keywords in feature_keywords.items():
        for kw in keywords:
            if kw in text:
                features.append(feat)
                break

    return {
        "url": raw.get("url", ""),
        "title": title,
        "brand": raw.get("brand", ""),
        "model": raw.get("model", ""),
        "year": year,
        "price": price,
        "mileage": mileage,
        "drive": drive,
        "engine": engine,
        "transmission": transmission,
        "owners": owners,
        "autoteka_color": autoteka_color,
        "features": features,
        "description": description,
        "region": raw.get("region", "unknown"),
        "missing_fields": [
            k for k in ["price", "year", "mileage", "drive"]
            if not {"price": price, "year": year, "mileage": mileage, "drive": drive}.get(k)
        ],
    }


def load_cards(path: str) -> list[dict]:
    """Загружает карточки из JSON."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Поддерживаем разные форматы
    if isinstance(data, list):
        raw_cards = data
    elif isinstance(data, dict):
        raw_cards = data.get("cards", data.get("results", []))
    else:
        raw_cards = []

    return [normalize_card(c) for c in raw_cards]
