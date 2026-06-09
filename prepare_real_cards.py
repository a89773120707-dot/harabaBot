"""prepare_real_cards.py — Блок 13.1-13.3: подготовка реальных карточек"""
import json
import yaml
import re
import sys
sys.path.insert(0, '.')

from config_loader import load_config, get_models
from model_matcher import match_card_to_model
from cards_loader import normalize_card
from base import BASE_DIR, RESULTS_DIR

CONFIG_PATH = RESULTS_DIR / "awd_liquid_full_config.yaml"
CARS_DB_PATH = BASE_DIR.parent / "haraba_bot" / "data" / "cars_db.json"

# Загружаем конфиг
config = load_config(str(CONFIG_PATH))
models = get_models(config)
print(f"Конфиг загружен: {len(models)} моделей")

# Загружаем cars_db
with open(CARS_DB_PATH, "r", encoding="utf-8") as f:
    cars_db = json.load(f)

print(f"cars_db.json: {len(cars_db)} записей")

# Фильтруем: только наши 17 моделей
our_17_ids = set(m["id"] for m in models)
our_brands = set(m["brand"].lower() for m in models)
our_models_set = set(m["model"].lower() for m in models)

matched = []
skipped = 0
brand_model_counts = {}

for ad_id, card in cars_db.items():
    brand = card.get("brand", "").lower()
    model = card.get("model", "").lower()

    # Быстрая фильтрация по brand+model
    raw_card = {
        "url": card.get("url", ""),
        "title": card.get("title", ""),
        "brand": card.get("brand", ""),
        "model": card.get("model", ""),
        "year": card.get("year"),
        "price": card.get("last_price") or card.get("first_price"),
        "mileage": card.get("mileage"),
        "status": card.get("status", ""),
        "score": card.get("score", 0),
    }

    # Нормализуем
    norm = normalize_card(raw_card)

    # Определяем модель
    model_id = match_card_to_model(norm, config)
    if not model_id:
        skipped += 1
        continue

    norm["model_id"] = model_id
    norm["haraba_id"] = ad_id
    norm["cars_db_status"] = card.get("status", "")
    norm["cars_db_score"] = card.get("score", 0)
    norm["first_price"] = card.get("first_price")

    matched.append(norm)

    key = model_id
    brand_model_counts[key] = brand_model_counts.get(key, 0) + 1

print(f"\nРезультат:")
print(f"  Всего в cars_db: {len(cars_db)}")
print(f"  Совпало с 17 моделями: {len(matched)}")
print(f"  Пропущено (unknown model): {skipped}")

print(f"\nПо моделям:")
for mid, cnt in sorted(brand_model_counts.items(), key=lambda x: -x[1]):
    print(f"  {mid}: {cnt}")

# Сохраняем
out_path = RESULTS_DIR / "real_cards_matched_17.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(matched, f, ensure_ascii=False, indent=2)

print(f"\n💾 Сохранено: {out_path}")

# QA отчёт
qa = {
    "total_in_cars_db": len(cars_db),
    "matched_cards": len(matched),
    "skipped_unknown": skipped,
    "model_counts": brand_model_counts,
    "has_price": sum(1 for c in matched if c.get("price")),
    "has_year": sum(1 for c in matched if c.get("year")),
    "has_mileage": sum(1 for c in matched if c.get("mileage")),
    "has_url": sum(1 for c in matched if c.get("url")),
    "has_title": sum(1 for c in matched if c.get("title")),
}

qa_path = RESULTS_DIR / "real_cards_qa.yaml"
with open(qa_path, "w", encoding="utf-8") as f:
    yaml.dump(qa, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

print(f"\n💾 QA: {qa_path}")
print(f"  has_price: {qa['has_price']}/{qa['matched_cards']}")
print(f"  has_year: {qa['has_year']}/{qa['matched_cards']}")
print(f"  has_mileage: {qa['has_mileage']}/{qa['matched_cards']}")
