"""test_photo_scrape.py — Открыть 1 карточку и проверить фото."""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

STATE = Path("data/state.json")
RESULTS = Path("results")

def main():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=False)
    context = browser.new_context(
        storage_state=str(STATE),
        viewport={"width": 375, "height": 812},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    )
    page = context.new_page()

    card_id = "171340559"
    url = f"https://m.haraba.ru/search/car/{card_id}?source=Telegram&fromMonolith=true"
    print(f"Opening: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=20000)
    time.sleep(5)

    # Найти все img
    imgs = page.locator("img")
    count = imgs.count()
    print(f"\nTotal img elements: {count}")

    photos = []
    for i in range(count):
        try:
            img = imgs.nth(i)
            src = img.get_attribute("src", timeout=1000)
            alt = img.get_attribute("alt", timeout=1000) or ""

            if not src:
                continue

            # Фильтр
            if any(skip in src.lower() or skip in alt.lower()
                   for skip in ["logo", "icon", "avatar", "sprite", "favicon", "arrow", "chevron", "star"]):
                continue

            if any(kw in src.lower() for kw in [".jpg", ".jpeg", ".png", ".webp", ".avif", "img", "photo", "image"]):
                print(f"  [{i}] {src[:100]}")
                photos.append(src)
        except Exception as e:
            pass

    print(f"\nPhotos found: {len(photos)}")

    # Также попробовать найти hero image
    try:
        hero = page.locator("[class*='hero'], [class*='MainPhoto'], [class*='mainPhoto'], [class*='swiper-slide-active'] img")
        if hero.count() > 0:
            hero_src = hero.first.get_attribute("src", timeout=1000)
            print(f"Hero: {hero_src[:100] if hero_src else 'None'}")
    except Exception as e:
        print(f"Hero error: {e}")

    page.screenshot(path=str(RESULTS / "test_photo_scrape.png"), full_page=True)
    print(f"\nScreenshot: results/test_photo_scrape.png")

    browser.close()
    pw.stop()

if __name__ == "__main__":
    main()
