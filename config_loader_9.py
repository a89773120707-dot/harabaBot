"""
config_loader_9.py — загрузчик config/awd_liquid_9.yaml (9 новых моделей).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

BASE_DIR = Path(__file__).parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "awd_liquid_9.yaml"


@dataclass
class SearchConfig9:
    id: str
    brand: str
    model: str
    year_from: int
    year_to: Optional[int]
    price_from: int
    price_to: int
    mileage_max: Optional[int] = None
    save_name: str = ""
    # Блок 9 фильтры
    regions: Optional[list] = None
    drivetrain: Optional[str] = None
    legal_restrictions: Optional[str] = None
    seller_type: Optional[str] = None
    owners_range: Optional[str] = None
    condition: Optional[str] = None
    transmission: Optional[list] = None
    # Meta
    price_confidence: Optional[str] = None
    need_manual_review: Optional[bool] = None


_REQUIRED_FIELDS = ["id", "brand", "model", "year_from", "price_from", "price_to"]


def _generate_save_name(model_data: dict) -> str:
    name = model_data.get("name", "")
    sf = model_data.get("search_filters", {})
    yf = sf.get("year_from", "")
    yt = sf.get("year_to", "")
    parts = [name]
    if yf and yt:
        parts.append("%s-%s" % (yf, yt))
    elif yf:
        parts.append("от %s" % yf)
    return " ".join(parts).strip()


def _extract_search_config(model_data: dict) -> SearchConfig9:
    model_id = model_data.get("id")
    sf = model_data.get("search_filters", {})

    brand = sf.get("brand")
    model_name = sf.get("model")
    year_from = sf.get("year_from")
    year_to = sf.get("year_to")
    price_from = sf.get("price_from")
    price_to = sf.get("price_to")
    mileage_max = sf.get("mileage_max")
    save_name = model_data.get("save_name", _generate_save_name(model_data))
    regions = sf.get("regions")
    drivetrain = sf.get("drivetrain")
    legal_restrictions = sf.get("legal_restrictions")
    seller_type = sf.get("seller_type")
    owners_range = sf.get("owners_range")
    condition = sf.get("condition")
    transmission = sf.get("transmission")

    # Meta поля
    market_rules = model_data.get("market_rules", {})
    price_confidence = model_data.get("price_confidence") or market_rules.get("price_confidence")
    need_manual_review = model_data.get("need_manual_review") or market_rules.get("need_manual_review")

    missing = []
    for field in _REQUIRED_FIELDS:
        if field == "id":
            if not model_id:
                missing.append(field)
        else:
            if sf.get(field) is None:
                missing.append(field)
    if missing:
        raise ValueError("%s missing field(s): %s" % (model_id or "unknown", ", ".join(missing)))

    return SearchConfig9(
        id=model_id,
        brand=str(brand),
        model=str(model_name),
        year_from=int(year_from),
        year_to=int(year_to) if year_to is not None else None,
        price_from=int(price_from),
        price_to=int(price_to),
        mileage_max=int(mileage_max) if mileage_max is not None else None,
        save_name=str(save_name),
        regions=regions,
        drivetrain=str(drivetrain) if drivetrain else None,
        legal_restrictions=legal_restrictions,
        seller_type=seller_type,
        owners_range=owners_range,
        condition=condition,
        transmission=transmission,
        price_confidence=price_confidence,
        need_manual_review=need_manual_review,
    )


def load_awd_liquid_9_config(config_path=None):
    """Загрузить config/awd_liquid_9.yaml и вернуть список SearchConfig9."""
    path = config_path or DEFAULT_CONFIG_PATH
    path = Path(path) if not isinstance(path, Path) else path
    if not path.exists():
        raise FileNotFoundError("Конфиг 9 моделей не найден: %s" % path)
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not config or not config.get("models"):
        raise ValueError("Секция 'models' не найдена в конфиге 9 моделей")
    models = config["models"]
    if not isinstance(models, list):
        raise ValueError("'models' должна быть списком")
    if len(models) != 9:
        raise ValueError("Ожидалось 9 моделей, получено: %d" % len(models))
    return [_extract_search_config(m) for m in models]


def validate_search_config_9(searches):
    """Валидация 9 моделей. Возвращает список ошибок или ['PASS']."""
    errors = []
    seen_ids = set()
    for s in searches:
        if s.id in seen_ids:
            errors.append("Дубликат id: %s" % s.id)
        seen_ids.add(s.id)
        if s.year_to is not None and s.year_to < s.year_from:
            errors.append("%s: year_to < year_from" % s.id)
        if s.price_to < s.price_from:
            errors.append("%s: price_to < price_from" % s.id)
        if not s.brand.strip():
            errors.append("%s: brand пустой" % s.id)
        if not s.model.strip():
            errors.append("%s: model пустой" % s.id)
        if s.drivetrain != "awd":
            errors.append("%s: drivetrain != awd" % s.id)
        if s.regions and len(s.regions) != 7:
            errors.append("%s: регионов != 7 (получено %d)" % (s.id, len(s.regions)))
        if s.legal_restrictions != "none":
            errors.append("%s: legal_restrictions != none" % s.id)
        if s.transmission and "manual" in s.transmission:
            errors.append("%s: transmission содержит manual" % s.id)
        if not s.mileage_max:
            errors.append("%s: mileage_max пустой" % s.id)
    if not errors:
        return ["PASS"]
    return errors


def get_search_by_id(searches, search_id):
    """Найти модель по id."""
    for s in searches:
        if s.id == search_id:
            return s
    raise ValueError("Модель '%s' не найдена в конфиге 9 моделей. Доступные: %s" % (
        search_id, ", ".join(s.id for s in searches)))
