"""test_photo_debug.py — Открыть mobile detail и показать что на странице."""
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
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
    )
    page = context.new_page()

    # Try mobile URL directly
    url = "https://m.haraba.ru/search/car/171340559"
    print(f"Opening: {url}")
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
    except Exception as e:
        print(f"Error with networkidle: {e}")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e2:
            print(f"Error with domcontentloaded: {e2}")
            page.screenshot(path=str(RESULTS / "photo_debug_error.png"))
            browser.close()
            pw.stop()
            return

    time.sleep(5)

    print(f"URL: {page.url}")
    print(f"Title: {page.title()}")

    body = page.inner_text("body", timeout=5000)
    print(f"Body length: {len(body)}")
    print(f"First 300 chars: {body[:300]}")

    # Count imgs
    imgs = page.locator("img")
    count = imgs.count()
    print(f"\nImg count: {count}")

    for i in range(min(count, 10)):
        try:
            src = imgs.nth(i).get_attribute("src", timeout=500)
            alt = imgs.nth(i).get_attribute("alt", timeout=500)
            print(f"  [{i}] src={src[:60] if src else 'None'}, alt={alt[:30] if alt else 'None'}")
        except:
            pass

    page.screenshot(path=str(RESULTS / "photo_debug.png"), full_page=True)
    print(f"\nScreenshot: results/photo_debug.png")

    browser.close()
    pw.stop()

if __name__ == "__main__":
    main()
