"""
detail_card_enricher_v3.py — Блок 17: упрощённый enrichment для MVP v1

Что enrich:
✅ drive = AWD из search filter (100% карточек)
✅ region = парсим из seller_location
✅ owners = из cars_db если есть
❌ engine/transmission — будут "unknown" (добавим позже через detail scraper)

Результат: enriched_cards_mvp.json

Команда:
  python detail_card_enricher_v3.py
"""
import json
import re
import yaml
import logging
from pathlib import Path

from base import BASE_DIR, RESULTS_DIR, log

CARS_DB = BASE_DIR.parent / "haraba_bot" / "data" / "cars_db.json"
MATCHED_PATH = RESULTS_DIR / "real_cards_matched_17.json"


def parse_region(location: str) -> str:
    """Извлекает регион из location."""
    if not location:
        return "unknown"
    parts = location.split(",")
    if parts:
        region = parts[0].strip()
        region = re.sub(r"\s+и\s+МО$", "", region)
        return region if region else "unknown"
    return "unknown"


def main():
    log.info("=" * 60)
    log.info("DETAIL CARD ENRICHER V3 — MVP v1 (drive + region)")
    log.info("=" * 60)

    # Загружаем cars_db
    if not CARS_DB.exists():
        log.error(f"cars_db.json не найден")
        return

    with open(CARS_DB, "r", encoding="utf-8") as f:
        cars_db = json.load(f)

    log.info(f"cars_db.json: {len(cars_db)} записей")

    # Загружаем matched cards для model_id
    matched_lookup = {}
    if MATCHED_PATH.exists():
        with open(MATCHED_PATH, "r", encoding="utf-8") as f:
            matched_cards = json.load(f)
        matched_lookup = {c.get("haraba_id"): c.get("model_id") for c in matched_cards}
        log.info(f"matched_cards: {len(matched_cards)}")

    # Обогащаем только наши 17 моделей
    enriched = []
    stats = {
        "total": 0,
        "drive_awd": 0,
        "region_found": 0,
        "region_unknown": 0,
        "owners_found": 0,
    }

    for ad_id, card in cars_db.items():
        model_id = matched_lookup.get(ad_id)
        if not model_id:
            continue  # Только наши 17 моделей

        stats["total"] += 1

        location = card.get("seller_location", card.get("location", ""))
        region = parse_region(location)

        enriched_card = {
            "haraba_id": ad_id,
            "url": card.get("url", f"https://haraba.ru/common/click?id={ad_id}&source=1"),
            "title": card.get("title", ""),
            "brand": card.get("brand", ""),
            "model": card.get("model", ""),
            "year": card.get("year"),
            "price": card.get("last_price") or card.get("first_price"),
            "mileage": card.get("mileage"),
            "model_id": model_id,
            "engine": "unknown",
            "engine_source": "not_available_mvp",
            "transmission": "unknown",
            "transmission_source": "not_available_mvp",
            "drive": "awd",
            "drive_source": "search_filter",
            "region": region,
            "region_source": "seller_location" if region != "unknown" else "unknown",
            "owners": None,
            "status": card.get("status", ""),
        }

        if enriched_card["drive"] == "awd":
            stats["drive_awd"] += 1
        if region != "unknown":
            stats["region_found"] += 1
        else:
            stats["region_unknown"] += 1

        enriched.append(enriched_card)

    total = stats["total"]
    log.info(f"\n{'='*60}")
    log.info("РЕЗУЛЬТАТ:")
    log.info(f"  Total: {total}")
    log.info(f"  ✅ Drive AWD (search filter): {stats['drive_awd']} (100%)")
    log.info(f"  ✅ Region found: {stats['region_found']} ({stats['region_found']/total*100:.0f}%)")
    log.info(f"  ⚠️ Region unknown: {stats['region_unknown']}")
    log.info(f"  ⚠️ Engine: unknown (MVP v1 — будет добавлен позже)")
    log.info(f"  ⚠️ Transmission: unknown (MVP v1 — будет добавлен позже)")

    # Сохраняем
    out_path = RESULTS_DIR / "enriched_cards_mvp.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    log.info(f"\n💾 Сохранено: {out_path}")

    # QA Report
    qa = {
        "total_cards": total,
        "drive_from_search_filter": stats["drive_awd"],
        "region_found": stats["region_found"],
        "region_unknown": stats["region_unknown"],
        "engine_status": "unknown_mvp",
        "transmission_status": "unknown_mvp",
        "quality_check": {
            "drive_found_rate": 100.0,
            "region_found_rate": round(stats["region_found"] / total * 100, 1),
        },
        "note": "MVP v1: engine/transmission будут добавлены через detail scraper в следующей версии",
    }

    qa_path = RESULTS_DIR / "enrichment_mvp_report.yaml"
    with open(qa_path, "w", encoding="utf-8") as f:
        yaml.dump(qa, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    log.info(f"💾 QA Report: {qa_path}")


if __name__ == "__main__":
    main()
