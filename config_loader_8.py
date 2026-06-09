"""
config_loader_8.py — загрузчик awd_liquid_ready_8.yaml.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

BASE_DIR = Path(__file__).parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "awd_liquid_ready_8.yaml"


@dataclass
class SearchConfig:
    id: str
    brand: str
    model: str
    year_from: int
    year_to: Optional[int]
    price_from: int
    price_to: int
    mileage_max: Optional[int] = None
    save_name: str = ""
    # Блок 9
    regions: Optional[list] = None
    drivetrain: Optional[str] = None
    legal_restrictions: Optional[str] = None
    seller_type: Optional[str] = None
    owners_range: Optional[str] = None
    condition: Optional[str] = None
    transmission: Optional[str] = None


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


def _extract_search_config(model_data: dict) -> SearchConfig:
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

    return SearchConfig(
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
    )


def load_searches(config_path=None):
    path = config_path or DEFAULT_CONFIG_PATH
    path = Path(path) if not isinstance(path, Path) else path
    if not path.exists():
        raise FileNotFoundError("Конфиг не найден: %s" % path)
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not config or not config.get("models"):
        raise ValueError("Секция 'models' не найдена")
    models = config["models"]
    if not isinstance(models, list):
        raise ValueError("'models' должна быть списком")
    return [_extract_search_config(m) for m in models]


def get_model_by_id(searches, model_id):
    for s in searches:
        if s.id == model_id:
            return s
    return None


def validate_searches(searches):
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
    return errors
