"""
БЛОК 2: config_loader.py — загрузка и валидация awd_liquid_full_config.yaml
"""
import yaml


def load_config(path: str) -> dict:
    """Загружает конфиг из YAML."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_models(config: dict) -> list[dict]:
    """Возвращает список моделей."""
    return config.get("models", [])


def get_model_by_id(config: dict, model_id: str) -> dict | None:
    """Находит модель по id."""
    for m in get_models(config):
        if m["id"] == model_id:
            return m
    return None


def validate_config_basic(config: dict) -> dict:
    """Базовая валидация конфига."""
    errors = []
    warnings = []

    models = get_models(config)
    if not models:
        errors.append("No models found")
        return {"status": "fail", "errors": errors, "warnings": warnings}

    ids = [m["id"] for m in models]
    if len(ids) != len(set(ids)):
        dups = [x for x in ids if ids.count(x) > 1]
        errors.append(f"Duplicate model ids: {set(dups)}")

    for m in models:
        mid = m["id"]
        if not m.get("price"):
            errors.append(f"{mid}: no price")
        if not m.get("reject"):
            errors.append(f"{mid}: no reject")
        if not m.get("engines", {}).get("best"):
            warnings.append(f"{mid}: no engines.best")
        if not m.get("mileage"):
            warnings.append(f"{mid}: no mileage rules")

    sg = config.get("search_groups", {})
    all_ids = set(ids)
    for group_name, group_ids in sg.items():
        missing = set(group_ids) - all_ids
        if missing:
            errors.append(f"search_groups.{group_name} references unknown ids: {missing}")

    return {
        "status": "ok" if not errors else "fail",
        "models_total": len(models),
        "errors": errors,
        "warnings": warnings,
    }
