"""photo_parser.py — Извлечь фото из mobile detail карточки."""
import re
import json
from pathlib import Path

from base import RESULTS_DIR


def extract_photos_from_card(card: dict) -> dict:
    """Извлечь фото из карточки (raw_text, mobile_detail_raw_text, specs).

    Returns:
        {
            "main_photo_url": str | None,
            "gallery": list[str],
            "photo_count": int,
            "source": str
        }
    """
    raw = card.get("mobile_detail_raw_text", "") + " " + card.get("raw_text", "")
    specs = card.get("specs", {})

    # 1. Ищем готовые фото-ссылки в карточке
    gallery = []

    # Ищем в specs
    for key in ["photos", "images", "gallery", "photo"]:
        val = specs.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.startswith("http"):
                    gallery.append(item)
                elif isinstance(item, dict) and item.get("url"):
                    gallery.append(item["url"])
        elif isinstance(val, str) and val.startswith("http"):
            gallery.append(val)

    # Ищем в top-level карточки
    for key in ["main_photo_url", "photo_url", "image_url"]:
        val = card.get(key)
        if isinstance(val, str) and val.startswith("http") and val not in gallery:
            if key == "main_photo_url":
                gallery.insert(0, val)
            else:
                gallery.append(val)

    # 2. Ищем URL в raw_text
    url_pattern = re.compile(r'https?://[\w\-._~:/?#\[\]@!$&\'()*+,;=%]+\.(?:jpg|jpeg|png|webp|avif)', re.IGNORECASE)
    found_urls = url_pattern.findall(raw)
    for url in found_urls:
        # Фильтруем иконки и логотипы
        if any(skip in url.lower() for skip in ["logo", "icon", "avatar", "sprite", "favicon"]):
            continue
        # Фильтруем дубли
        url = url.strip()
        if url not in gallery:
            gallery.append(url)

    # 3. Ищем data-src, src в HTML-подобных паттернах
    src_pattern = re.compile(r'(?:data-src|src|background-image)\s*[:=]\s*["\']?(https?://[^"\'\s>]+)', re.IGNORECASE)
    found_src = src_pattern.findall(raw)
    for url in found_src:
        if any(skip in url.lower() for skip in ["logo", "icon", "avatar", "sprite"]):
            continue
        url = url.strip()
        if url not in gallery:
            gallery.append(url)

    # Убираем дубли
    seen = set()
    unique_gallery = []
    for url in gallery:
        if url not in seen:
            seen.add(url)
            unique_gallery.append(url)

    main_photo = unique_gallery[0] if unique_gallery else None

    return {
        "main_photo_url": main_photo,
        "gallery": unique_gallery,
        "photo_count": len(unique_gallery),
        "source": "mobile_detail"
    }


def normalize_photo_url(url: str) -> str:
    """Нормализовать URL фото — убедиться что абсолютный."""
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://m.haraba.ru" + url
    return url


def enrich_cards_with_photos(cards: list) -> list:
    """Обогатить список карточек фото."""
    for card in cards:
        photos = extract_photos_from_card(card)
        card["photos"] = photos
        if photos["main_photo_url"]:
            card["photo_url"] = photos["main_photo_url"]
            card["photo_count"] = photos["photo_count"]
    return cards


def generate_photo_coverage_report(cards: list) -> dict:
    """Создать отчёт о покрытии фото."""
    total = len(cards)
    with_main = sum(1 for c in cards if c.get("photos", {}).get("main_photo_url"))
    with_gallery = sum(1 for c in cards if len(c.get("photos", {}).get("gallery", [])) > 1)
    without = total - with_main

    sample_urls = []
    for c in cards[:5]:
        photos = c.get("photos", {})
        if photos.get("main_photo_url"):
            sample_urls.append(photos["main_photo_url"])

    return {
        "total_cards": total,
        "with_main_photo": with_main,
        "with_gallery": with_gallery,
        "without_photo": without,
        "coverage_percent": round(with_main / total * 100, 1) if total > 0 else 0,
        "sample_photo_urls": sample_urls[:5],
    }
