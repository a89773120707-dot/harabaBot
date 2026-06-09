"""test_photo_parser.py — Проверка photo_parser на текущих данных."""
import json
import yaml
from photo_parser import extract_photos_from_card, generate_photo_coverage_report, enrich_cards_with_photos
from base import RESULTS_DIR

def main():
    # Загрузить карточки
    with open(RESULTS_DIR / "mobile_first_page_sample.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    cards = data.get("cards", [])
    print(f"Total cards: {len(cards)}")

    # Обогатить фото
    cards = enrich_cards_with_photos(cards)

    # Показать первые 5
    for c in cards[:5]:
        photos = c.get("photos", {})
        main_url = photos.get("main_photo_url") if photos else None
        print(f"\n{c['card_id']} {c['title']}")
        print(f"  main: {main_url[:80] if main_url else 'None'}")
        print(f"  count: {photos.get('photo_count', 0) if photos else 0}")
        print(f"  gallery: {len(photos.get('gallery', [])) if photos else 0}")

    # Отчёт
    report = generate_photo_coverage_report(cards)
    print(f"\n{'='*50}")
    print(f"Photo Coverage Report:")
    print(f"  Total: {report['total_cards']}")
    print(f"  With main photo: {report['with_main_photo']}")
    print(f"  With gallery: {report['with_gallery']}")
    print(f"  Without photo: {report['without_photo']}")
    print(f"  Coverage: {report['coverage_percent']}%")

    # Сохранить отчёт
    with open(RESULTS_DIR / "photo_coverage_report.yaml", "w", encoding="utf-8") as f:
        yaml.dump(report, f, allow_unicode=True, default_flow_style=False)
    print(f"\n  Saved: results/photo_coverage_report.yaml")

    # Сохранить enriched cards
    data["cards"] = cards
    with open(RESULTS_DIR / "mobile_first_page_sample.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Updated: results/mobile_first_page_sample.json")

if __name__ == "__main__":
    main()
