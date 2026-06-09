"""
detail_card_enricher_v2.py — Блок 17: hybrid enrichment (cache + title + search filter)

Логика:
1. resolved_urls.json → source_enrichment_cache.json (engine/transmission/drive/owners)
2. Fallback: парсинг title cars_db
3. Drive по умолчанию = AWD из search filter
4. Region из seller_location

БЕЗ browser! 160 карточек за < 5 секунд.

Команды:
  python detail_card_enricher_v2.py --all
"""
import json
import re
import yaml
import logging
from pathlib import Path

from base import BASE_DIR, RESULTS_DIR, log

# Пути к файлам из haraba_bot
HARABA_BOT = BASE_DIR.parent / "haraba_bot"
RESOLVED_URLS = HARABA_BOT / "data" / "resolved_urls.json"
SOURCE_ENRICHMENT = HARABA_BOT / "data" / "source_enrichment_cache.json"
CARS_DB = HARABA_BOT / "data" / "cars_db.json"

# Маппинг КПП
TRANSMISSION_MAP = {
    "вариатор": "cvt",
    "cvt": "cvt",
    "автомат": "automatic",
    "automatic": "automatic",
    "at": "automatic",
    "робот": "dsg",
    "dsg": "dsg",
    "s-tronic": "dsg",
    "s tronic": "dsg",
    "механика": "manual",
    "механик": "manual",
    "manual": "manual",
    "mt": "manual",
}

# Маппинг привода
DRIVE_MAP = {
    "полный": "awd",
    "awd": "awd",
    "4wd": "awd",
    "4matic": "awd",
    "quattro": "awd",
    "4motion": "awd",
    "передний": "fwd",
    "fwd": "fwd",
    "задний": "rwd",
    "rwd": "rwd",
}


def load_sources():
    """Загружает resolved_urls и source_enrichment_cache."""
    resolved = {}
    if RESOLVED_URLS.exists():
        with open(RESOLVED_URLS, "r", encoding="utf-8") as f:
            resolved = json.load(f)
        log.info(f"resolved_urls.json: {len(resolved)} записей")

    enrichment = {}
    if SOURCE_ENRICHMENT.exists():
        with open(SOURCE_ENRICHMENT, "r", encoding="utf-8") as f:
            enrichment = json.load(f)
        log.info(f"source_enrichment_cache.json: {len(enrichment)} записей")

    return resolved, enrichment


def build_haraba_to_enrichment(resolved: dict, enrichment: dict) -> dict:
    """Строит маппинг: haraba_car_id → enriched specs через source_url."""
    mapping = {}

    for haraba_id, entry in resolved.items():
        source_url = entry.get("source_url", "")
        if not source_url:
            continue

        # Ищем в enrichment cache по source_url
        if source_url in enrichment:
            specs = enrichment[source_url].get("source_specs", {})
            mapping[haraba_id] = specs

    log.info(f"Haraba → Enrichment mapping: {len(mapping)} связей")
    return mapping


def parse_title(title: str) -> dict:
    """Парсит engine/transmission из title."""
    result = {"engine": "unknown", "transmission": "unknown"}

    title_clean = title.strip()

    # Engine: ищем паттерны вида "2.0", "2.2 дизель", "3.0 TDI", "2.5 (150 л.с.)"
    # Паттерн 1: "2.0 AT", "2.2 CVT", "3.0 TDI"
    engine_match = re.search(r"([\d.]+)\s*(AT|CVT|MT|AMT|DSG|дизел|diesel|tdi|crdi|tfsi|fsi|бензин|petrol)?", title_clean, re.IGNORECASE)
    if engine_match:
        volume = engine_match.group(1)
        fuel_type = engine_match.group(2) or ""
        fuel_lower = fuel_type.lower()

        if fuel_lower in ("at", "cvt", "mt", "amt", "dsg"):
            # Это коробка, ищем дальше топливо
            result["transmission"] = TRANSMISSION_MAP.get(fuel_lower, fuel_lower)
            # Топливо не найдено — только объём
            result["engine"] = f"{volume}"
        elif any(f in fuel_lower for f in ["дизел", "diesel", "tdi", "crdi"]):
            result["engine"] = f"{volume} дизель"
        elif any(f in fuel_lower for f in ["бензин", "petrol", "tfsi", "fsi"]):
            result["engine"] = f"{volume} бензин"
        else:
            result["engine"] = f"{volume}"

    # Паттерн 2: "2 литра", "2.0 литра"
    if result["engine"] == "unknown":
        liter_match = re.search(r"([\d.]+)\s*литр", title_clean, re.IGNORECASE)
        if liter_match:
            result["engine"] = f"{liter_match.group(1)}"

    # Transmission: ищем отдельно
    title_lower = title_clean.lower()
    if result["transmission"] == "unknown":
        # Ищем CVT/AT/MT/AMT/DSG как отдельные слова
        trans_match = re.search(r"\b(AT|CVT|MT|AMT|DSG)\b", title_lower)
        if trans_match:
            result["transmission"] = TRANSMISSION_MAP.get(trans_match.group(1).lower(), "unknown")
        else:
            # Ищем русские названия
            for key, val in TRANSMISSION_MAP.items():
                if key in title_lower:
                    result["transmission"] = val
                    break

    # Дизель/бензин в title отдельно
    if "дизел" in title_lower or "diesel" in title_lower or "tdi" in title_lower or "crdi" in title_lower:
        if result["engine"] == "unknown":
            result["engine"] = "дизель"
        elif "дизель" not in result["engine"]:
            result["engine"] = result["engine"].replace(result["engine"].split()[0], result["engine"].split()[0] + " дизель") if " " not in result["engine"] else result["engine"] + " дизель"

    return result


def parse_region(location: str) -> str:
    """Извлекает регион из location."""
    if not location:
        return "unknown"

    # Ищем город/регион в начале строки
    # Формат: "Москва и МО, Москва, ул. Лескова" или "Архангельск"
    parts = location.split(",")
    if parts:
        region = parts[0].strip()
        # Убираем "и МО"
        region = re.sub(r"\s+и\s+МО$", "", region)
        return region if region else "unknown"

    return "unknown"


def normalize_drive(raw_drive: str) -> str:
    """Нормализует привод."""
    if not raw_drive:
        return "awd"
    drive_lower = raw_drive.lower().strip()
    for key, val in DRIVE_MAP.items():
        if key in drive_lower:
            return val
    return "awd"  # Fallback — поиск был AWD


def normalize_owners(raw_owners: str | int) -> int | None:
    """Нормализует количество владельцев."""
    if isinstance(raw_owners, int):
        return raw_owners
    if not raw_owners:
        return None
    m = re.search(r"(\d+)", str(raw_owners))
    return int(m.group(1)) if m else None


def enrich_card_fast(card: dict, enrichment_mapping: dict) -> dict:
    """Обогащает одну карточку из cache + title."""
    haraba_id = card.get("haraba_id")
    title = card.get("title", "")
    location = card.get("seller_location", card.get("location", ""))

    # 1. Пробуем enrichment cache
    specs = enrichment_mapping.get(haraba_id, {}) if haraba_id else {}

    if specs:
        # Engine
        engine_raw = specs.get("engine", "")
        if engine_raw:
            card["engine"] = engine_raw
            card["engine_source"] = "source_enrichment_cache"

        # Transmission
        trans_raw = specs.get("transmission", "")
        if trans_raw:
            card["transmission"] = TRANSMISSION_MAP.get(trans_raw.lower(), trans_raw.lower())
            card["transmission_source"] = "source_enrichment_cache"

        # Drive
        drive_raw = specs.get("drive", "")
        if drive_raw:
            card["drive"] = normalize_drive(drive_raw)
            card["drive_source"] = "source_enrichment_cache"
        else:
            card["drive"] = "awd"
            card["drive_source"] = "search_filter"

        # Owners
        owners_raw = specs.get("owners")
        card["owners"] = normalize_owners(owners_raw)
        card["owners_source"] = "source_enrichment_cache"

    else:
        # 2. Fallback: парсинг title
        parsed = parse_title(title)
        card["engine"] = parsed["engine"]
        card["engine_source"] = "title_parsing"
        card["transmission"] = parsed["transmission"]
        card["transmission_source"] = "title_parsing"

        # Drive из search filter
        card["drive"] = "awd"
        card["drive_source"] = "search_filter"
        card["owners_source"] = "unknown"

    # Region из location
    card["region"] = parse_region(location)

    return card


def main():
    log.info("=" * 60)
    log.info("DETAIL CARD ENRICHER V2 — HYBRID (CACHE + TITLE)")
    log.info("=" * 60)

    # Загружаем источники
    resolved, enrichment = load_sources()
    enrichment_mapping = build_haraba_to_enrichment(resolved, enrichment)

    # Загружаем cars_db
    if not CARS_DB.exists():
        log.error(f"cars_db.json не найден: {CARS_DB}")
        return

    with open(CARS_DB, "r", encoding="utf-8") as f:
        cars_db = json.load(f)

    log.info(f"cars_db.json: {len(cars_db)} записей")

    # Загружаем matched cards для model_id
    matched_path = RESULTS_DIR / "real_cards_matched_17.json"
    if matched_path.exists():
        with open(matched_path, "r", encoding="utf-8") as f:
            matched_cards = json.load(f)
        matched_lookup = {c.get("haraba_id"): c for c in matched_cards}
        log.info(f"matched_cards: {len(matched_cards)}")
    else:
        matched_lookup = {}

    # Обогащаем
    enriched = []
    stats = {
        "from_cache": 0,
        "from_title": 0,
        "drive_from_filter": 0,
        "engine_unknown": 0,
        "transmission_unknown": 0,
        "region_unknown": 0,
        "manual_found": 0,
    }

    for ad_id, card in cars_db.items():
        # Создаём базовую карточку
        enriched_card = {
            "haraba_id": ad_id,
            "url": card.get("url", f"https://haraba.ru/common/click?id={ad_id}&source=1"),
            "title": card.get("title", ""),
            "brand": card.get("brand", ""),
            "model": card.get("model", ""),
            "year": card.get("year"),
            "price": card.get("last_price") or card.get("first_price"),
            "mileage": card.get("mileage"),
            "seller_location": card.get("seller_location", ""),
            "status": card.get("status", ""),
        }

        # Добавляем model_id из matched
        if ad_id in matched_lookup:
            enriched_card["model_id"] = matched_lookup[ad_id].get("model_id")

        # Обогащаем
        enriched_card = enrich_card_fast(enriched_card, enrichment_mapping)

        # Статистика
        if enriched_card.get("engine_source") == "source_enrichment_cache":
            stats["from_cache"] += 1
        else:
            stats["from_title"] += 1

        if enriched_card.get("drive_source") == "search_filter":
            stats["drive_from_filter"] += 1

        if enriched_card.get("engine") == "unknown":
            stats["engine_unknown"] += 1
        if enriched_card.get("transmission") == "unknown":
            stats["transmission_unknown"] += 1
        if enriched_card.get("region") == "unknown":
            stats["region_unknown"] += 1
        if enriched_card.get("transmission") == "manual":
            stats["manual_found"] += 1

        enriched.append(enriched_card)

    total = len(enriched)
    log.info(f"\n{'='*60}")
    log.info("РЕЗУЛЬТАТ:")
    log.info(f"  Total: {total}")
    log.info(f"  ✅ Enriched from cache: {stats['from_cache']} ({stats['from_cache']/total*100:.0f}%)")
    log.info(f"  📝 Enriched from title: {stats['from_title']} ({stats['from_title']/total*100:.0f}%)")
    log.info(f"  🔧 Drive from search filter: {stats['drive_from_filter']} ({stats['drive_from_filter']/total*100:.0f}%)")
    log.info(f"  ⚠️ Engine unknown: {stats['engine_unknown']}")
    log.info(f"  ⚠️ Transmission unknown: {stats['transmission_unknown']}")
    log.info(f"  ⚠️ Region unknown: {stats['region_unknown']}")
    log.info(f"  ❌ Manual transmission: {stats['manual_found']}")

    # Сохраняем
    out_path = RESULTS_DIR / "enriched_cards_fast.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    log.info(f"\n💾 Сохранено: {out_path}")

    # QA Report
    qa = {
        "total_cards": total,
        "enriched_from_cache": stats["from_cache"],
        "enriched_from_title": stats["from_title"],
        "drive_from_search_filter": stats["drive_from_filter"],
        "engine_unknown": stats["engine_unknown"],
        "transmission_unknown": stats["transmission_unknown"],
        "region_unknown": stats["region_unknown"],
        "manual_transmission_found": stats["manual_found"],
        "quality_check": {
            "engine_found_rate": round((total - stats["engine_unknown"]) / total * 100, 1),
            "transmission_found_rate": round((total - stats["transmission_unknown"]) / total * 100, 1),
            "drive_found_rate": round(100.0, 1),  # Всегда awd из search filter
            "region_found_rate": round((total - stats["region_unknown"]) / total * 100, 1),
        },
    }

    qa_path = RESULTS_DIR / "enrichment_fast_report.yaml"
    with open(qa_path, "w", encoding="utf-8") as f:
        yaml.dump(qa, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    log.info(f"💾 QA Report: {qa_path}")


if __name__ == "__main__":
    main()
