"""
detail_card_enricher.py — Блок 17: обогащение карточек из detail-страницы Haraba

Использует авторизованную сессию Haraba, открывает m.haraba.ru/search/car/{id},
кликает "Показать все" и парсит характеристики.

Команды:
  python detail_card_enricher.py --limit 5       # тест на 5 карточках
  python detail_card_enricher.py --limit 160     # все карточки
"""
import argparse
import json
import re
import time
import logging
from pathlib import Path

from session_manager import get_authenticated_page
from base import BASE_DIR, RESULTS_DIR, log

CARDS_PATH = RESULTS_DIR / "real_cards_matched_17.json"

# Маппинг КПП → нормализованное значение
TRANSMISSION_MAP = {
    "вариатор": "cvt",
    "cvt": "cvt",
    "автомат": "automatic",
    "automatic": "automatic",
    "робот": "dsg",
    "dsg": "dsg",
    "механика": "manual",
    "механик": "manual",
    "manual": "manual",
    "s-tronic": "dsg",
    "dsг": "dsg",
}

# Маппинг привода → нормализованное значение
DRIVE_MAP = {
    "передний": "fwd",
    "задний": "rwd",
    "полный": "awd",
    "awd": "awd",
    "4matic": "awd",
    "quattro": "awd",
    "4motion": "awd",
}


def parse_specs_from_page(page) -> dict:
    """Парсит характеристики с detail-страницы Haraba."""
    specs = {}

    try:
        # 1. Кликаем "Показать все"
        show_all = page.get_by_text("Показать все").first
        if show_all.count() > 0:
            show_all.click()
            page.wait_for_timeout(2000)

        # 2. Получаем текст
        body = page.inner_text("body", timeout=5000)

        # 3. Парсим паттернами
        patterns = {
            "модификация": r"Модификация\s*\n\s*(.+)",
            "тип_двигателя": r"Тип двигателя\s*\n\s*(.+)",
            "объём_двигателя": r"Объём двигателя\s*\n\s*(.+)",
            "кпп": r"КПП\s*\n\s*(.+)",
            "привод": r"Привод\s*\n\s*(.+)",
            "тип_кузова": r"Тип кузова\s*\n\s*(.+)",
            "цвет": r"Цвет\s*\n\s*(.+)",
            "руль": r"Руль\s*\n\s*(.+)",
            "состояние": r"Состояние\s*\n\s*(.+)",
            "владельцы": r"Владельцы\s*\n\s*(\d+)",
            "пробег": r"Пробег\s*\n\s*([\d\s]+)\s*км",
            "поколение": r"Поколение\s*\n\s*(.+)",
        }

        for key, pattern in patterns.items():
            m = re.search(pattern, body, re.IGNORECASE)
            if m:
                specs[key] = m.group(1).strip()

    except Exception as e:
        log.debug(f"  Ошибка парсинга specs: {e}")

    return specs


def normalize_enriched(specs: dict, search_drive: str = "awd") -> dict:
    """Нормализует распарсенные характеристики."""
    enriched = {
        "engine": "unknown",
        "transmission": "unknown",
        "drive": "unknown",
        "drive_source": "unknown",
        "region": "unknown",
        "owners": None,
        "mileage": None,
        "fuel_type": "unknown",
        "engine_volume": None,
        "body_type": "unknown",
        "color": "unknown",
    }

    # Двигатель: модификация + тип топлива
    mod = specs.get("модификация", "")
    fuel = specs.get("тип_двигателя", "")
    volume = specs.get("объём_двигателя", "")

    if mod:
        enriched["engine"] = mod
    elif volume and fuel:
        enriched["engine"] = f"{volume} {fuel}"

    if fuel:
        enriched["fuel_type"] = fuel.lower()

    if volume:
        vol_match = re.search(r"([\d.]+)\s*л", volume)
        if vol_match:
            enriched["engine_volume"] = float(vol_match.group(1))

    # Коробка
    kpp = specs.get("кпп", "").lower()
    for key, val in TRANSMISSION_MAP.items():
        if key in kpp:
            enriched["transmission"] = val
            break

    # Привод: приоритет — из detail, fallback — из поиска
    privod = specs.get("привод", "").lower()
    if privod:
        for key, val in DRIVE_MAP.items():
            if key in privod:
                enriched["drive"] = val
                enriched["drive_source"] = "haraba_detail"
                break
        else:
            # Не распознали из detail — берём из поиска
            enriched["drive"] = search_drive
            enriched["drive_source"] = "search_filter"
    else:
        enriched["drive"] = search_drive
        enriched["drive_source"] = "search_filter"

    # Регион
    enriched["region"] = specs.get("регион", "unknown")

    # Владельцы
    owners = specs.get("владельцы")
    if owners:
        try:
            enriched["owners"] = int(owners)
        except:
            pass

    # Пробег
    mileage = specs.get("пробег")
    if mileage:
        try:
            enriched["mileage"] = int(mileage.replace(" ", "").replace("\xa0", ""))
        except:
            pass

    # Кузов
    body = specs.get("тип_кузова", "")
    if body:
        enriched["body_type"] = body

    # Цвет
    color = specs.get("цвет", "")
    if color:
        enriched["color"] = color

    return enriched


def extract_car_id(url: str) -> str | None:
    """Извлекает car_id из Haraba URL."""
    m = re.search(r"/car/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"id=(\d+)", url)
    if m:
        return m.group(1)
    return None


def enrich_card(card: dict, page, search_drive: str = "awd") -> dict:
    """Обогащает одну карточку из detail-страницы Haraba."""
    url = card.get("url", "")
    car_id = extract_car_id(url)

    if not car_id:
        card["enrichment_status"] = "no_url"
        return card

    detail_url = f"https://m.haraba.ru/search/car/{car_id}"

    try:
        page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(3000)

        # Проверяем что страница не пустая / не ошибка
        title = page.title()
        if "Haraba" not in title:
            card["enrichment_status"] = f"bad_page_title: {title}"
            return card

        # Парсим характеристики
        specs = parse_specs_from_page(page)

        if not specs:
            card["enrichment_status"] = "no_specs_found"
            return card

        # Нормализуем
        enriched = normalize_enriched(specs, search_drive)

        # Извлекаем регион из заголовка (город есть в title страницы)
        try:
            body_text = page.inner_text("body", timeout=2000)
            # Город обычно в формате: "дата ГородПродавца"
            city_match = re.search(r"\d+\s+[а-я]+\s+20\d{2}\s+([А-Яа-яЁё\s]+?)(?:Частник|Дилер|Компания)", body_text)
            if city_match:
                enriched["region"] = city_match.group(1).strip()
        except:
            pass

        # Применяем обогащение
        card.update(enriched)
        card["enrichment_status"] = "success"
        card["specs_raw"] = specs
        card["detail_url"] = detail_url

    except Exception as e:
        card["enrichment_status"] = f"error: {e}"
        log.debug(f"  Ошибка обогащения {car_id}: {e}")

    return card


def main():
    parser = argparse.ArgumentParser(description="Detail Card Enricher")
    parser.add_argument("--limit", type=int, default=5, help="Сколько карточек обогатить")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("DETAIL CARD ENRICHER — БЛОК 17")
    log.info("=" * 60)

    # Загружаем карточки
    with open(CARDS_PATH, "r", encoding="utf-8") as f:
        cards = json.load(f)

    cards = cards[:args.limit]
    log.info(f"Карточек для обогащения: {len(cards)}")

    # Открываем авторизованную сессию
    page, context, browser = get_authenticated_page()

    try:
        stats = {"success": 0, "no_url": 0, "no_specs": 0, "error": 0}

        for i, card in enumerate(cards):
            url = card.get("url", "")
            title = card.get("title", "unknown")[:40]
            log.info(f"[{i+1}/{len(cards)}] {title}...")

            card = enrich_card(card, page)
            cards[i] = card

            status = card.get("enrichment_status", "unknown")
            if status == "success":
                stats["success"] += 1
                log.info(f"  ✅ engine={card.get('engine','?')}, trans={card.get('transmission','?')}, drive={card.get('drive','?')}")
            elif status == "no_url":
                stats["no_url"] += 1
            elif status == "no_specs_found":
                stats["no_specs"] += 1
            else:
                stats["error"] += 1
                log.info(f"  ❌ {status}")

            # Пауза между карточками
            time.sleep(1.5)

    finally:
        browser.close()

    # Статистика
    total = len(cards)
    log.info(f"\n{'='*60}")
    log.info("РЕЗУЛЬТАТ:")
    log.info(f"  Total: {total}")
    log.info(f"  ✅ Success: {stats['success']} ({stats['success']/total*100:.0f}%)")
    log.info(f"  ❌ No URL: {stats['no_url']}")
    log.info(f"  ❌ No specs: {stats['no_specs']}")
    log.info(f"  ❌ Error: {stats['error']}")

    # Поля
    engine_found = sum(1 for c in cards if c.get("engine") and c["engine"] != "unknown")
    trans_found = sum(1 for c in cards if c.get("transmission") and c["transmission"] != "unknown")
    drive_found = sum(1 for c in cards if c.get("drive") and c["drive"] != "unknown")
    region_found = sum(1 for c in cards if c.get("region") and c["region"] != "unknown")

    log.info(f"\nЗаполненность полей:")
    log.info(f"  engine: {engine_found}/{total} ({engine_found/total*100:.0f}%)")
    log.info(f"  transmission: {trans_found}/{total} ({trans_found/total*100:.0f}%)")
    log.info(f"  drive: {drive_found}/{total} ({drive_found/total*100:.0f}%)")
    log.info(f"  region: {region_found}/{total} ({region_found/total*100:.0f}%)")

    # Сохраняем
    out_path = RESULTS_DIR / f"enriched_cards_test_{total}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

    log.info(f"\n💾 Сохранено: {out_path}")


if __name__ == "__main__":
    main()
