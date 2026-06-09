"""test_photo_1card.py — Быстрый тест фото на 1 карточке через sampler."""
import sys
sys.path.insert(0, '.')

from mobile_first_page_sampler import get_authenticated_page, open_mobile_detail

def main():
    page, context, browser = get_authenticated_page()

    card = {"card_id": "171340559", "title": "Nissan X-Trail"}
    card = open_mobile_detail(page, card, debug=True)

    print(f"\nPhotos: {card.get('photos', {})}")
    print(f"photo_url: {card.get('photo_url')}")
    print(f"photo_count: {card.get('photo_count')}")

    browser.close()

if __name__ == "__main__":
    main()
