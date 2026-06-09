"""
test_formatter_v2.py — проверить telegram_card_formatter v2 на реальных карточках.
"""
import json
import yaml
from pathlib import Path

from telegram_card_formatter import format_car_card_v2

RESULTS = Path("results")

def main():
    # Загрузить конфиг
    config_path = RESULTS / "awd_liquid_full_config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Загрузить audited карточки
    audited_path = RESULTS / "telegram_candidates_audited.json"
    with open(audited_path, "r", encoding="utf-8") as f:
        audited = json.load(f)

    # Загрузить sample для enrichment
    sample_path = RESULTS / "mobile_first_page_sample.json"
    with open(sample_path, "r", encoding="utf-8") as f:
        sample = json.load(f)

    sample_lookup = {}
    for c in sample.get("cards", []):
        cid = c.get("card_id", "")
        if cid:
            sample_lookup[cid] = c

    # Собрать полные карточки
    cards = []
    for c in audited.get("cards", []):
        cid = c.get("card_id", "")
        s = sample_lookup.get(cid, {})
        specs = s.get("specs", {})

        card = {
            "card_id": cid,
            "title": c.get("title", s.get("title", "")),
            "url": c.get("url", s.get("url", "")),
            "mobile_url": c.get("mobile_url", s.get("mobile_url", "")),
            "brand": c.get("title", s.get("title", "")),
            "model": c.get("title", s.get("title", "")),
            "price": c.get("price", s.get("price", 0)),
            "mileage": c.get("mileage", s.get("mileage", 0)),
            "year": c.get("year", s.get("year", 0)),
            "score": c.get("score", 0),
            "decision": c.get("decision", ""),
            "engine": specs.get("engine", {}).get("value", "unknown"),
            "transmission": specs.get("transmission", {}).get("value", "unknown"),
            "drive": specs.get("drive", {}).get("value", "unknown"),
            "region": specs.get("region", {}).get("value", "unknown"),
            "owners": specs.get("owners", {}).get("value", "unknown"),
            "legal_restrictions": specs.get("legal_restrictions", {}).get("value", "unknown"),
            "autoteka_status": specs.get("autoteka_status", {}).get("value", "unknown"),
            "features": [],
            "price_score": 0,
            "mileage_score": 0,
            "engine_score": 0,
            "transmission_score": 0,
            "equipment_score": 0,
            "bonus_reasons": [],
            "penalty_reasons": [],
        }

        # Прогнать через scoring чтобы получить score breakdown
        from config_loader import get_model_by_id
        from model_matcher import match_card_to_model
        from price_scorer_v2 import score_price
        from mileage_scorer import score_mileage
        from powertrain_scorer import score_engine, score_transmission
        from equipment_scorer import score_equipment

        model_id = match_card_to_model(card, config)
        card["model_id"] = model_id
        model_rules = get_model_by_id(config, model_id) if model_id else None
        if model_rules:
            price_r = score_price(card.get("price"), model_rules.get("price", {}))
            mileage_r = score_mileage(card.get("mileage"), model_rules.get("mileage", {}))
            engine_r = score_engine(card.get("engine", ""), model_rules.get("engines", {}))
            trans_r = score_transmission(card.get("transmission", ""), model_rules.get("transmissions", {}))
            equip_r = score_equipment(card, model_rules)

            card["price_score"] = price_r["score"]
            card["mileage_score"] = mileage_r["score"]
            card["engine_score"] = engine_r["score"]
            card["transmission_score"] = trans_r["score"]
            card["equipment_score"] = equip_r["score"]
            card["price_category"] = price_r.get("category", "")
            card["price_status"] = price_r.get("price_status", "")

            if price_r["score"] > 0:
                card["bonus_reasons"].append(price_r["explanation"])
            elif price_r["score"] < 0:
                card["penalty_reasons"].append(price_r["explanation"])
            if mileage_r["score"] > 0:
                card["bonus_reasons"].append(mileage_r["explanation"])
            elif mileage_r["score"] < 0:
                card["penalty_reasons"].append(mileage_r["explanation"])
            if engine_r["score"] > 0:
                card["bonus_reasons"].append(engine_r["explanation"])
            if trans_r["score"] > 0:
                card["bonus_reasons"].append(trans_r["explanation"])
            if equip_r["score"] > 0:
                card["bonus_reasons"].append(equip_r["explanation"])

        cards.append(card)

    # Сформировать preview
    lines = ["# Telegram Cards Preview v2\n", f"Generated: cards: {len(cards)}\n", "---\n"]

    for card in cards:
        is_hold = c_action(card) == "hold"
        hold_reasons = []
        formatted = format_car_card_v2(card, config, is_hold=is_hold, hold_reasons=hold_reasons)
        lines.append(formatted)
        lines.append("---\n")

    output_path = RESULTS / "telegram_preview_v2.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Preview saved: {output_path}")
    print(f"Total cards: {len(cards)}")


def c_action(card):
    """Определить action из decision."""
    decision = card.get("decision", "")
    if "unknown" in decision:
        return "hold"
    return "send"


if __name__ == "__main__":
    main()
